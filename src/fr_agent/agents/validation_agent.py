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
)


class ValidationAgent:
    def __init__(self, *, batch_size: int = 2):
        self._batch_size = batch_size

    def apply_updates(self, checklist: ValidationChecklist, updates: list[FieldUpdate]) -> None:
        for update in updates:
            checklist.apply(update)   # solo aplica; NO toca attempts

    def next_objectives(self, checklist: ValidationChecklist) -> list[str]:
        open_fields = checklist.askable_open_fields()
        if not open_fields:
            return []
        objectives = []
        for target in open_fields[: self._batch_size]:
            target.attempts += 1      # lo estamos preguntando AHORA
            objectives.append(self._objective_for(target))
        return objectives

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
