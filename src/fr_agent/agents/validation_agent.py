"""Validation agent: decides what to pursue next.

Deliberately deterministic (code, not LLM): applying extracted updates and
picking the next objective is a policy decision, and keeping it in code makes
the loop cheap, testable, and predictable. If you later need fuzzy judgment
(e.g. "is this answer really specific enough?"), add an LLM consistency check
here behind the same interface.
"""

from fr_agent.domain.validation import (
    FIELD_DESCRIPTIONS,
    FieldStatus,
    FieldUpdate,
    ValidationChecklist,
    OPTIONAL_FIELDS
)


class ValidationAgent:
    def __init__(self, *, batch_size: int = 2):
        self._batch_size = batch_size

    def apply_updates(self, checklist: ValidationChecklist, updates: list[FieldUpdate]) -> None:
        for update in updates:
            checklist.apply(update)   # solo aplica; NO toca attempts

    def next_targets(self, checklist: ValidationChecklist):
        """The actual fields the next message will ask about (bumps
        `attempts` — call this once per turn, not next_objectives too)."""
        open_fields = checklist.askable_open_fields()
        open_fields.sort(key=lambda f: (f.field in OPTIONAL_FIELDS, -f.priority.value))
        targets = open_fields[: self._batch_size]
        for target in targets:
            target.attempts += 1      # lo estamos preguntando AHORA
        return targets

    def objective_text(self, targets) -> list[str]:
        return [self._objective_for(t) for t in targets]

    def next_objectives(self, checklist: ValidationChecklist) -> list[str]:
        return self.objective_text(self.next_targets(checklist))

    def _objective_for(self, target) -> str:
        description = FIELD_DESCRIPTIONS[target.field]
        if target.status == FieldStatus.CONFLICTING:
            return (
                f"Clarify contradiction about: {description} "
                f"(current: '{target.value}')."
            )
        if target.status == FieldStatus.PARTIAL:
            return (
                f"Complete this partial topic: {description} "
                f"(have so far: '{target.value}')."
            )
        return f"Ask about: {description}"
