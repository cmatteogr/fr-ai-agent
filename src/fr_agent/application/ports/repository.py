"""Persistence port for validation sessions.

Implementations: infrastructure/persistence/in_memory.py (dev/tests).
A Postgres/SQLAlchemy adapter slots in here when you need durability.
"""

from typing import Protocol

from fr_agent.domain.session import ValidationSession


class SessionRepository(Protocol):
    def get_by_phone(self, phone: str) -> ValidationSession | None:
        """Return the active session for a seller phone, if any."""
        ...

    def save(self, session: ValidationSession) -> None:
        ...
