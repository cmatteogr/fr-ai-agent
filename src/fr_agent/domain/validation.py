"""The validation checklist: the shared state every agent works against.

This is the core of the system. The orchestrator's goal is to drive every
field to a terminal status (CONFIRMED or CONFLICTING) within the turn budget.
Add or remove fields here and the whole pipeline (extraction, questioning,
completion criteria) follows — no prompt surgery needed elsewhere.
"""

import difflib
from enum import StrEnum, IntEnum

from pydantic import BaseModel, Field

# Case/typo tolerance for "is this actually the same answer restated?" when
# deciding whether a new value conflicts with an already-CONFIRMED one.
# Tuned so "laurles"/"laureles" (0.93) and "medellin"/"medellín" (0.88) count
# as the same, while "belen"/"belen la mota" (0.56) and "belen"/"belencito"
# (0.71) still count as different — see distinct neighborhoods in the same
# city, don't lower this without re-checking those numbers.
SAME_VALUE_THRESHOLD = 0.85


def _same_value(a: str, b: str) -> bool:
    a, b = a.strip().casefold(), b.strip().casefold()
    if a == b:
        return True
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= SAME_VALUE_THRESHOLD


class FieldName(StrEnum):
    #location
    ADDRESS = "address"  # street + number, specific
    NEIGHBORHOOD = "neighborhood"    # Neighborhood 
    CITY = "city"               # city / municipality
    #Validation
    LEGAL_STATUS = "legal_status"  # liens, disputes, clean title, inheritance issues
    OCCUPANCY = "occupancy"                # owner-occupied, rented, vacant, squatted
    OCCUPANCY_NOTE = "occupancy_note"  # free-text occupancy detail
    RENOVATIONS = "renovations"            # needed repairs / recent remodels
    MOTIVATION = "motivation"              # reason for the sale
    #negotiation
    MIN_PRICE = "min_price"                # minimum price the seller would accept
    PAYMENT_METHODS = "payment_methods"    # cash, mortgage subrogation, installments, etc.
    PAYMENT_NOTE = "payment_note"
    URGENCY = "urgency"                  


class OccupancyStatus(StrEnum):
    OWNER = "Ocupada por propietario"
    TENANT = "Ocupada por inquilino"
    VACANT = "Desocupada"
    UNKNOWN = "Desconocida"


class LegalStatusOption(StrEnum):
    CLEAN = "Sin problemas legales"
    MORTGAGE = "Con hipoteca"
    EMBARGO = "Con embargo/gravamen"
    SUCCESSION = "En proceso de sucesión"
    LITIGATION = "En litigio"
    UNKNOWN = "Desconocido"


class PaymentMethod(StrEnum):
    CASH = "Efectivo"
    LEASING = "Leasing habitacional"
    CREDIT = "Crédito hipotecario"         
    SUBROGATION = "Subrogación"
    DIRECT_FINANCING = "Financiación directa"
    TRADE = "Permuta"
    OTHER = "Otro"


class FieldPriority(IntEnum):
    """Higher = more important, insist more before skipping."""

    HIGH = 3
    MEDIUM = 2
    LOW = 1

FIELD_OPTIONS: dict[FieldName, list[str]] = {
    FieldName.OCCUPANCY: [o.value for o in OccupancyStatus],
    FieldName.LEGAL_STATUS: [o.value for o in LegalStatusOption],
    FieldName.PAYMENT_METHODS: [p.value for p in PaymentMethod],
}

FIELD_MULTI: set[FieldName] = {FieldName.PAYMENT_METHODS}

# Numeric fields: extraction fills .number (COP / days)
NUMERIC_FIELDS: set[FieldName] = {FieldName.MIN_PRICE, FieldName.URGENCY}

# Passive: never asked; filled only if mentioned (or derived).
OPPORTUNISTIC_FIELDS: set[FieldName] = {
    FieldName.OCCUPANCY_NOTE,
    FieldName.PAYMENT_NOTE,
}

# Negotiation group: asked if there's room, but does NOT block completion (optional tab).
OPTIONAL_FIELDS: set[FieldName] = {
    FieldName.MIN_PRICE,
    FieldName.URGENCY,
    FieldName.PAYMENT_METHODS,
    FieldName.PAYMENT_NOTE,
}
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
    FieldName.PAYMENT_NOTE: FieldPriority.LOW,
    FieldName.MIN_PRICE: FieldPriority.MEDIUM,  # opcional
    FieldName.PAYMENT_METHODS: FieldPriority.MEDIUM,  # opcional
}

MAX_ATTEMPTS: dict[FieldPriority, int] = {
    FieldPriority.HIGH: 3,
    FieldPriority.MEDIUM: 2,
    FieldPriority.LOW: 1,
}
OPTION_ALIASES: dict[FieldName, dict[str, str]] = {
    FieldName.OCCUPANCY: {
        "dueño": OccupancyStatus.OWNER,
        "dueno": OccupancyStatus.OWNER,
        "propietario": OccupancyStatus.OWNER,
        "vivo yo": OccupancyStatus.OWNER,
        "inquilino": OccupancyStatus.TENANT,
        "alquilad": OccupancyStatus.TENANT,
        "arrendad": OccupancyStatus.TENANT,
        "desocupad": OccupancyStatus.VACANT,
        "vac": OccupancyStatus.VACANT,
        "no sé": OccupancyStatus.UNKNOWN,
        "no se": OccupancyStatus.UNKNOWN,
    },
    FieldName.LEGAL_STATUS: {
        "embargo": LegalStatusOption.EMBARGO,
        "gravamen": LegalStatusOption.EMBARGO,
        "hipoteca": LegalStatusOption.MORTGAGE,
        "limpio": LegalStatusOption.CLEAN,
        "sin problemas": LegalStatusOption.CLEAN,
        "sucesion": LegalStatusOption.SUCCESSION,
        "sucesión": LegalStatusOption.SUCCESSION,
        "litigio": LegalStatusOption.LITIGATION,
        "demanda": LegalStatusOption.LITIGATION,
        "no sé": LegalStatusOption.UNKNOWN,
        "no se": LegalStatusOption.UNKNOWN,
    },
    FieldName.PAYMENT_METHODS: {
        "efectivo": PaymentMethod.CASH,
        "contado": PaymentMethod.CASH,
        "cash": PaymentMethod.CASH,
        "credito": PaymentMethod.CREDIT,
        "crédito": PaymentMethod.CREDIT,
        "leasing": PaymentMethod.LEASING,
        "subrog": PaymentMethod.SUBROGATION,
        "financiaci": PaymentMethod.DIRECT_FINANCING,
        "permuta": PaymentMethod.TRADE,
        "trueque": PaymentMethod.TRADE,
        "otro": PaymentMethod.OTHER,
    },
}


def _normalize_selection(field: FieldName, raw: list[str]) -> list[str]:
    """Map LLM paraphrases to the exact DB option text."""
    options = FIELD_OPTIONS.get(field, [])
    aliases = OPTION_ALIASES.get(field, {})
    out = []
    for token in raw:
        t = token.strip()
        if t in options:
            out.append(t)
            continue
        low = t.lower()
        hit = next((opt for key, opt in aliases.items() if key in low), None)
        if hit:
            out.append(hit)
    return out


class FieldStatus(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    CONFIRMED = "confirmed"
    CONFLICTING = "conflicting"
    SKIPPED = "skipped"


class FieldUpdate(BaseModel):
    field: FieldName
    status: FieldStatus
    value: str = Field(default="", description="Free-text normalized statement")
    selection: list[str] = Field(default_factory=list, description="Chosen option(s)")
    number: int | None = Field(
        default=None, description="Bare number for numeric fields"
    )
    evidence: str = Field(default="", description="Verbatim quote from seller")


class ChecklistField(BaseModel):
    field: FieldName
    status: FieldStatus = FieldStatus.PENDING
    value: str = ""
    selection: list[str] = Field(default_factory=list)
    number: int | None = None
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

    @classmethod
    def seeded_from(cls, known: dict[FieldName, str]) -> "ValidationChecklist":
        """Start a checklist with whatever fields THIS listing actually
        supplies already CONFIRMED, so the conversation never asks about
        them. Which fields that is varies per listing — not a fixed trio.
        Anything not in `known` stays PENDING and gets asked normally.
        `known` values go into `number` for NUMERIC_FIELDS, `value` otherwise.
        """
        checklist = cls()
        for field, given in known.items():
            if given in (None, ""):
                continue
            target = checklist.fields[field]
            target.status = FieldStatus.CONFIRMED
            if field in NUMERIC_FIELDS:
                target.number = int(given)
            else:
                target.value = str(given)
        return checklist

    def apply(self, update: FieldUpdate) -> None:
        current = self.fields[update.field]
        options = FIELD_OPTIONS.get(update.field, [])
        if options and update.selection:
            clean = list(dict.fromkeys(_normalize_selection(update.field, update.selection)))
            if update.field not in FIELD_MULTI:
                clean = clean[:1]
            if clean:
                update.selection = clean
                update.value = ", ".join(clean)
        if update.number is not None:
            current.number = update.number

        if current.status == FieldStatus.CONFIRMED and not _same_value(update.value, current.value):
            current.status = FieldStatus.CONFLICTING
        else:
            current.status = update.status
        current.value = update.value
        current.selection = update.selection
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
        return [f for f in self.open_fields() if f.field not in OPPORTUNISTIC_FIELDS]

    def required_open_fields(self) -> list[ChecklistField]:
        return [f for f in self.askable_open_fields() if f.field not in OPTIONAL_FIELDS]

    def is_complete(self) -> bool:
        return not self.required_open_fields()

    def finalize(self) -> None:
        for f in self.fields.values():
            if f.field in (OPPORTUNISTIC_FIELDS | OPTIONAL_FIELDS):
                if f.status in FieldStatus.PENDING:
                    f.status = FieldStatus.SKIPPED


    def summary(self) -> str:
        lines = []
        for f in self.fields.values():
            value = f.value or "-"
            extra = f" (number: {f.number})" if f.number is not None else ""
            lines.append(f"- {f.field}: [{f.status}] {value}{extra}")
        return "\n".join(lines)
