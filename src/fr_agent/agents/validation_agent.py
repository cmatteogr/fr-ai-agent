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
    def apply_updates(self, checklist: ValidationChecklist, updates: list[FieldUpdate]) -> None:
        for update in updates:
            checklist.apply(update)

    def next_objective(self, checklist: ValidationChecklist) -> str | None:
        """Human-readable objective for the conversation agent, or None if done."""
        open_fields = checklist.open_fields()
        if not open_fields:
            return None
        target = open_fields[0]
        description = FIELD_DESCRIPTIONS[target.field]
        if target.status == FieldStatus.CONFLICTING:
            return (
                f"The seller gave contradictory information about: {description} "
                f"Current value on record: '{target.value}'. Politely clarify which is correct."
            )
        if target.status == FieldStatus.PARTIAL:
            return (
                f"Complete this partially-answered topic: {description} "
                f"What we have so far: '{target.value}'."
            )
        return f"Ask about: {description}"
