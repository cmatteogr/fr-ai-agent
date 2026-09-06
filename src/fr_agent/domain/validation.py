"""The validation checklist: the shared state every agent works against.

This is the core of the system. The orchestrator's goal is to drive every
field to a terminal status (CONFIRMED or CONFLICTING) within the turn budget.
Add or remove fields here and the whole pipeline (extraction, questioning,
completion criteria) follows — no prompt surgery needed elsewhere.
"""

from enum import StrEnum, IntEnum

from pydantic import BaseModel, Field


class FieldName(StrEnum):
    ADDRESS = "address"  # street + number, specific
    NEIGHBORHOOD = "neighborhood"    # Neighborhood 
    CITY = "city"               # city / municipality
    LEGAL_STATUS = "legal_status"  # liens, disputes, clean title, inheritance issues
    OCCUPANCY = "occupancy"                # owner-occupied, rented, vacant, squatted
    OCCUPANCY_NOTE = "occupancy_note"  # free-text occupancy detail
    RENOVATIONS = "renovations"            # needed repairs / recent remodels
    MIN_PRICE = "min_price"                # minimum price the seller would accept
    PAYMENT_METHODS = "payment_methods"    # cash, mortgage subrogation, installments, etc.
    MOTIVATION = "motivation"              # reason for the sale
    URGENCY = "urgency"                    # urgency or deadline


class FieldPriority(IntEnum):
    """Higher = more important, insist more before skipping."""

    HIGH = 3
    MEDIUM = 2
    LOW = 1


# Human-readable descriptions injected into agent prompts. Keep these in sync
# with FieldName — they are the single place where each field's meaning is defined.
FIELD_DESCRIPTIONS: dict[FieldName, str] = {
    FieldName.ADDRESS: (
        "Exact street address: street name + number. A barrio or city alone is NOT an address."
    ),
    FieldName.NEIGHBORHOOD: "Barrio / sector where the property is located.",
    FieldName.CITY: "City / municipality of the property.",
    FieldName.LEGAL_STATUS: (
        "Legal situation: clean title, liens/mortgages, embargoes, succession or "
        "co-ownership disputes, up-to-date taxes."
    ),
    FieldName.OCCUPANCY: (
        "Occupancy status, normalized to ONE of: owner-occupied, rented, vacant, "
        "occupied by a third party."
    ),
    FieldName.OCCUPANCY_NOTE: (
        "Free-text details about occupancy (lease end date, who lives there, etc.)."
    ),
    FieldName.RENOVATIONS: "Repairs or renovations needed, and any recent remodels.",
    FieldName.MIN_PRICE: "Minimum price the seller accepts, and how firm it is.",
    FieldName.PAYMENT_METHODS: (
        "Payment methods accepted: cash, bank financing, mortgage subrogation, "
        "installments, trade-ins."
    ),
    FieldName.MOTIVATION: (
        "Underlying REASON for selling (divorce, inheritance, relocation, debt, "
        "need cash, investment). This is the WHY — not the speed."
    ),
    FieldName.URGENCY: "How urgent the sale is / desired timeframe (must sell soon, no rush, max "
    "days to wait). A wish to 'sell fast' belongs HERE, not in motivation.",
}

FIELD_PRIORITIES: dict[FieldName, FieldPriority] = {
    FieldName.ADDRESS: FieldPriority.MEDIUM,
    FieldName.NEIGHBORHOOD: FieldPriority.HIGH,
    FieldName.CITY: FieldPriority.HIGH,
    FieldName.LEGAL_STATUS: FieldPriority.HIGH,
    FieldName.OCCUPANCY: FieldPriority.MEDIUM,
    FieldName.OCCUPANCY_NOTE: FieldPriority.LOW,
    FieldName.RENOVATIONS: FieldPriority.MEDIUM,
    FieldName.MIN_PRICE: FieldPriority.HIGH,
    FieldName.PAYMENT_METHODS: FieldPriority.HIGH,
    FieldName.MOTIVATION: FieldPriority.HIGH,  # subió de importancia
    FieldName.URGENCY: FieldPriority.LOW,
}

MAX_ATTEMPTS: dict[FieldPriority, int] = {
    FieldPriority.HIGH: 3,
    FieldPriority.MEDIUM: 2,
    FieldPriority.LOW: 1,
}
# Passive fields: extraction fills them if the seller mentions them; the
# conversation agent never asks about them and they never block completion.
OPPORTUNISTIC_FIELDS: set[FieldName] = {FieldName.OCCUPANCY_NOTE}


class FieldStatus(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    CONFIRMED = "confirmed"
    CONFLICTING = "conflicting"
    SKIPPED = "skipped"


class FieldUpdate(BaseModel):
    field: FieldName
    status: FieldStatus
    value: str = Field(
        description="Extracted info, normalized to a short FORMAL statement"
    )
    evidence: str = Field(default="", description="Verbatim quote from seller")


class ChecklistField(BaseModel):
    field: FieldName
    status: FieldStatus = FieldStatus.PENDING
    value: str = ""
    evidence: list[str] = Field(default_factory=list)
    attempts: int = 0

    @property
    def priority(self) -> FieldPriority:
        return FIELD_PRIORITIES[self.field]

    @property
    def max_attempts(self) -> int:
        return MAX_ATTEMPTS[self.priority]

    def should_skip(self) -> bool:
        return self.attempts >= self.max_attempts and self.status in (
            FieldStatus.PENDING,
            FieldStatus.PARTIAL,
        )


class ValidationChecklist(BaseModel):
    fields: dict[FieldName, ChecklistField] = Field(
        default_factory=lambda: {name: ChecklistField(field=name) for name in FieldName}
    )

    def apply(self, update: FieldUpdate) -> None:
        current = self.fields[update.field]
        if current.status == FieldStatus.CONFIRMED and update.value != current.value:
            current.status = FieldStatus.CONFLICTING
        else:
            current.status = update.status
        current.value = update.value
        if update.evidence:
            current.evidence.append(update.evidence)

    def open_fields(self) -> list[ChecklistField]:
        for f in self.fields.values():
            if f.should_skip():
                f.status = FieldStatus.SKIPPED
        return [
            f
            for f in self.fields.values()
            if f.status
            in (FieldStatus.PENDING, FieldStatus.PARTIAL, FieldStatus.CONFLICTING)
        ]

    def askable_open_fields(self) -> list[ChecklistField]:
        """Open fields the agent may actually ask about (excludes passive ones)."""
        return [f for f in self.open_fields() if f.field not in OPPORTUNISTIC_FIELDS]

    def is_complete(self) -> bool:
        return not self.askable_open_fields()

    def finalize(self) -> None:
        """Call once when the conversation ends: passive fields left empty are
        marked SKIPPED so the final summary reads clean."""
        for f in self.fields.values():
            if f.field in OPPORTUNISTIC_FIELDS and f.status in (
                FieldStatus.PENDING,
                FieldStatus.PARTIAL,
            ):
                f.status = FieldStatus.SKIPPED

    def summary(self) -> str:
        lines = []
        for f in self.fields.values():
            value = f.value or "-"
            lines.append(f"- {f.field}: [{f.status}] {value}")
        return "\n".join(lines)
