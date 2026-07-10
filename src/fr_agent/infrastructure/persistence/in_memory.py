"""In-memory SessionRepository — dev and tests.

Sessions are Pydantic models, so a durable adapter (Postgres, DynamoDB, ...)
can serialize them with model_dump_json() / model_validate_json() without any
schema mapping layer. Implement it against the same SessionRepository port.
"""

from fr_agent.domain.session import ValidationSession


class InMemorySessionRepository:
    def __init__(self):
        self._by_phone: dict[str, ValidationSession] = {}

    def get_by_phone(self, phone: str) -> ValidationSession | None:
        return self._by_phone.get(phone)

    def save(self, session: ValidationSession) -> None:
        self._by_phone[session.seller_phone] = session
