"""The validation checklist: the shared state every agent works against.

This is the core of the system. The orchestrator's goal is to drive every
field to a terminal status (CONFIRMED or CONFLICTING) within the turn budget.
Add or remove fields here and the whole pipeline (extraction, questioning,
completion criteria) follows — no prompt surgery needed elsewhere.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class FieldName(StrEnum):
    LOCATION = "location"
    LEGAL_STATUS = "legal_status"          # liens, disputes, clean title, inheritance issues
    OCCUPANCY = "occupancy"                # owner-occupied, rented, vacant, squatted
    RENOVATIONS = "renovations"            # needed repairs / recent remodels
    MIN_PRICE = "min_price"                # minimum price the seller would accept
    PAYMENT_METHODS = "payment_methods"    # cash, mortgage subrogation, installments, etc.


# Human-readable descriptions injected into agent prompts. Keep these in sync
# with FieldName — they are the single place where each field's meaning is defined.
FIELD_DESCRIPTIONS: dict[FieldName, str] = {
    FieldName.LOCATION: "Exact location of the property: address or neighborhood, city.",
    FieldName.LEGAL_STATUS: (
        "Legal situation: clean title, liens/mortgages, embargoes, succession or "
        "co-ownership disputes, up-to-date taxes."
    ),
    FieldName.OCCUPANCY: (
        "Current occupancy: owner-occupied, rented (lease end date), vacant, or occupied "
        "by a third party."
    ),
    FieldName.RENOVATIONS: "Repairs or renovations the property needs, and any recent remodels.",
    FieldName.MIN_PRICE: "Minimum price the seller is willing to accept, and how firm it is.",
    FieldName.PAYMENT_METHODS: (
        "Payment methods the seller accepts: cash, bank financing, mortgage subrogation, "
        "installments, trade-ins."
    ),
}


class FieldStatus(StrEnum):
    PENDING = "pending"          # not discussed yet
    PARTIAL = "partial"          # mentioned, but incomplete or vague
    CONFIRMED = "confirmed"      # seller gave a clear, specific answer
    CONFLICTING = "conflicting"  # seller contradicted an earlier statement or a known fact
    SKIPPED = "skipped"          #seller cant confirm information, continue


class FieldUpdate(BaseModel):
    """One piece of information extracted from a seller message."""

    field: FieldName
    status: FieldStatus
    value: str = Field(description="The extracted information, normalized to a short statement")
    evidence: str = Field(default="", description="Verbatim quote from the seller's message")


class ChecklistField(BaseModel):
    field: FieldName
    status: FieldStatus = FieldStatus.PENDING
    value: str = ""
    evidence: list[str] = Field(default_factory=list)
    attempts: int = 0 


class ValidationChecklist(BaseModel):
    fields: dict[FieldName, ChecklistField] = Field(
        default_factory=lambda: {name: ChecklistField(field=name) for name in FieldName}
    )

    def apply(self, update: FieldUpdate) -> None:
        current = self.fields[update.field]
        # Never silently downgrade a confirmed answer; a new contradicting
        # statement flips it to CONFLICTING so the orchestrator re-asks.
        if current.status == FieldStatus.CONFIRMED and update.value != current.value:
            current.status = FieldStatus.CONFLICTING
        else:
            current.status = update.status
        current.value = update.value
        if update.evidence:
            current.evidence.append(update.evidence)

    def open_fields(self) -> list[ChecklistField]:
        """Fields that still need work, in declaration order (= priority order)."""
        return [
            f for f in self.fields.values()
            if f.status in (FieldStatus.PENDING, FieldStatus.PARTIAL, FieldStatus.CONFLICTING)
        ]

    def is_complete(self) -> bool:
        return not self.open_fields()

    def summary(self) -> str:
        """Compact plain-text state, injected into agent prompts."""
        lines = []
        for f in self.fields.values():
            value = f.value or "-"
            lines.append(f"- {f.field}: [{f.status}] {value}")
        return "\n".join(lines)
