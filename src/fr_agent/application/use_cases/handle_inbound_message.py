"""Use case: process an inbound WhatsApp message from a seller.

This is the webhook's single entry point into the core. It owns I/O
sequencing (load -> orchestrate -> send -> persist); all reasoning lives
in the orchestrator and agents.
"""

import logging

from fr_agent.agents.orchestrator import Orchestrator
from fr_agent.application.ports.messaging import MessagingPort
from fr_agent.application.ports.repository import SessionRepository

logger = logging.getLogger(__name__)


class HandleInboundMessage:
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

    def execute(self, *, from_phone: str, text: str) -> None:
        session = self._sessions.get_by_phone(from_phone)
        if session is None:
            # Message from an unknown number: nothing to validate. Log and drop.
            logger.info("Ignoring message from unknown number %s", from_phone)
            return

        result = self._orchestrator.handle_inbound(session, text)
        if result.reply:
            self._messaging.send_text(to=from_phone, text=result.reply)
        self._sessions.save(result.session)
