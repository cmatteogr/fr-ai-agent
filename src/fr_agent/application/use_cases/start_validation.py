"""Use case: kick off a validation conversation for a property."""

from fr_agent.agents.orchestrator import Orchestrator
from fr_agent.application.ports.messaging import MessagingPort
from fr_agent.application.ports.repository import SessionRepository
from fr_agent.domain.property import Property
from fr_agent.domain.session import ValidationSession
from fr_agent.domain.validation import ValidationChecklist


class StartValidation:
    def __init__(
        self,
        *,
        orchestrator: Orchestrator,
        sessions: SessionRepository,
        messaging: MessagingPort,
    ):
        self._orchestrator = orchestrator
        self._sessions = sessions
        self._messaging = messaging

    def execute(self, property_: Property) -> ValidationSession:
        checklist = ValidationChecklist.seeded_from(property_.known_checklist_fields())
        session = ValidationSession(property=property_, checklist=checklist)
        result = self._orchestrator.start(session)
        if result.reply:
            self._messaging.send_text(to=session.seller_phone, text=result.reply)
        self._sessions.save(result.session)
        return result.session
