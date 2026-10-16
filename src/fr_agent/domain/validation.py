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

# The "doesn't know" option of each option field.
UNKNOWN_OPTIONS: set[str] = {OccupancyStatus.UNKNOWN.value, LegalStatusOption.UNKNOWN.value}

# Numeric fields: extraction fills .number (COP). Urgency is free text, not days.
NUMERIC_FIELDS: set[FieldName] = {FieldName.MIN_PRICE}

# Passive: never asked; filled only if mentioned (or derived).
OPPORTUNISTIC_FIELDS: set[FieldName] = {
    FieldName.OCCUPANCY_NOTE,
    # Payment is extra detail of the price answer: never asked on its own,
    # captured when the seller mentions it (the min_price question invites it).
    FieldName.PAYMENT_METHODS,
    FieldName.PAYMENT_NOTE,
}

# Fields that are asked but do NOT block completion. Empty on purpose: min_price
# and urgency used to live here, so the conversation always finished before
# reaching them. Kept so a field can be made non-blocking again in one place.
OPTIONAL_FIELDS: set[FieldName] = set()
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
    FieldName.MIN_PRICE: (
        "Minimum price the seller accepts (a number), and in the same question how "
        "they would like to be paid (cash, mortgage credit, etc.)."
    ),
    FieldName.PAYMENT_METHODS: (
        "Payment methods accepted: cash, bank financing, mortgage subrogation, "
        "installments, trade-ins."
    ),
    FieldName.MOTIVATION: (
        "Underlying REASON for selling (divorce, inheritance, relocation, debt, "
        "need cash, investment). This is the WHY — not the speed."
    ),
    FieldName.URGENCY: (
        "How fast the seller wants to sell and any deadline they have (free text). "
        "A wish to 'sell fast' belongs HERE, not in motivation."
    ),
}

FIELD_PRIORITIES: dict[FieldName, FieldPriority] = {
    FieldName.ADDRESS: FieldPriority.MEDIUM,
    FieldName.NEIGHBORHOOD: FieldPriority.HIGH,
    FieldName.CITY: FieldPriority.HIGH,
    FieldName.LEGAL_STATUS: FieldPriority.HIGH,
    FieldName.OCCUPANCY: FieldPriority.MEDIUM,
    FieldName.OCCUPANCY_NOTE: FieldPriority.LOW,
    FieldName.RENOVATIONS: FieldPriority.MEDIUM,
    FieldName.MOTIVATION: FieldPriority.HIGH,  # subió de importancia
    # Required now; MEDIUM so they're asked after location/legal/motivation,
    # which reads more naturally than opening with money.
    FieldName.MIN_PRICE: FieldPriority.MEDIUM,
    FieldName.URGENCY: FieldPriority.MEDIUM,
    FieldName.PAYMENT_METHODS: FieldPriority.LOW,  # opportunistic, never asked alone
    FieldName.PAYMENT_NOTE: FieldPriority.LOW,
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

    @property
    def out_of_attempts(self) -> bool:
        return self.attempts >= self.max_attempts

    def should_skip(self) -> bool:
        # Only a field with NO answer becomes skipped. A PARTIAL answer the
        # seller did give is kept as partial: we stop asking, we don't erase it.
        return self.out_of_attempts and self.status == FieldStatus.PENDING


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
        # Guard 0: numeric fields hold a number, never text. Any text the model
        # put there ("no ha pensado en un número") is dropped before anything else.
        if update.field in NUMERIC_FIELDS:
            update.value = ""
        # Guard 0b: 'selection' only exists for fields with fixed options. On a
        # free-text field the model sometimes puts the answer there by mistake
        # (neighborhood=["Belén La Mota"], value=""): move it into value.
        if update.field not in FIELD_OPTIONS:
            if not update.value.strip() and update.selection:
                update.value = ", ".join(update.selection)
            update.selection = []
        # Guard 1: a "confirmed"/"partial" update with nothing in it carries no
        # information. The model sometimes emits these for fields nobody
        # mentioned; they must not change the checklist.
        has_content = bool(update.value.strip() or update.selection or update.number)
        if update.status in (FieldStatus.CONFIRMED, FieldStatus.PARTIAL) and not has_content:
            return
        # Guard 1a: a city can't be the barrio's own name ("Belén" filed as city
        # when the neighborhood is "Belén La Mota"). That's a barrio misfiled.
        if update.field == FieldName.CITY and update.status in (
            FieldStatus.CONFIRMED,
            FieldStatus.PARTIAL,
        ):
            barrio = self.fields[FieldName.NEIGHBORHOOD].value
            city = update.value.strip().casefold()
            if barrio and city and (_same_value(city, barrio) or city in barrio.casefold()):
                return
        # Guard 1b: an address always has a number ("Calle 45B #12-30"). Without
        # one it's a barrio or a city filed in the wrong place ("Belén",
        # "laurles medellin"). Known limit: a rural "Finca X, vereda Y" with no
        # number would be rejected too.
        if (
            update.field == FieldName.ADDRESS
            and update.status in (FieldStatus.CONFIRMED, FieldStatus.PARTIAL)
            and not any(ch.isdigit() for ch in update.value)
        ):
            return
        options = FIELD_OPTIONS.get(update.field, [])
        # The model sometimes writes the option in 'value' instead of 'selection'.
        if options and not update.selection and update.value:
            update.selection = _normalize_selection(update.field, [update.value])
        if options and update.selection:
            clean = list(dict.fromkeys(_normalize_selection(update.field, update.selection)))
            if update.field not in FIELD_MULTI:
                clean = clean[:1]
            if clean:
                update.selection = clean
                update.value = ", ".join(clean)
            # SKIPPED means "doesn't know / refuses". If the model also picked a
            # real option, the seller did give an answer, just unsure -> PARTIAL.
            if update.status == FieldStatus.SKIPPED and any(
                opt not in UNKNOWN_OPTIONS for opt in update.selection
            ):
                update.status = FieldStatus.PARTIAL
        # Guard 2: a number of 0 is never a real price — treat as absent.
        new_number = update.number if update.number is not None and update.number > 0 else None

        # Guard 3: restating an already-trusted value (typo, casing) keeps the
        # trusted canonical value. Only a genuinely different value conflicts.
        # Numeric fields compare the number (their text value is always empty).
        if current.status == FieldStatus.CONFIRMED:
            if update.field in NUMERIC_FIELDS:
                same = new_number is None or new_number == current.number
            else:
                same = _same_value(update.value, current.value)
            if same:
                if update.evidence:
                    current.evidence.append(update.evidence)
                return
            current.status = FieldStatus.CONFLICTING
        else:
            current.status = update.status
        if new_number is not None:
            current.number = new_number
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
            if f.status in (FieldStatus.PENDING, FieldStatus.CONFLICTING)
            # a partial answer stays open until its attempts run out, then it
            # stays partial but is no longer asked (and doesn't block completion)
            or (f.status == FieldStatus.PARTIAL and not f.out_of_attempts)
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
