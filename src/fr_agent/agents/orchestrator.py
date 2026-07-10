"""Orchestrator: deterministic control flow over the specialist agents.

Pattern: orchestrator-workers with explicit shared state (the session) and
explicit termination conditions — the loop cannot run away:

    inbound message
        │
        ▼
    ExtractionAgent  ── structured updates ──►  ValidationAgent (apply + pick objective)
        │                                             │
        ▼                                             ▼
    termination check (opt-out / complete / turn budget)
        │
        ▼
    ConversationAgent ── next WhatsApp message ──► outbound

The orchestrator never talks to the LLM directly and never touches I/O;
it only coordinates agents and mutates the session. Delivery/persistence
happen in the use-case layer.
"""

from dataclasses import dataclass

from fr_agent.agents.conversation_agent import ConversationAgent
from fr_agent.agents.extraction_agent import ExtractionAgent
from fr_agent.agents.validation_agent import ValidationAgent
from fr_agent.domain.conversation import ConversationState, Role
from fr_agent.domain.session import ValidationSession


@dataclass
class OrchestratorResult:
    reply: str | None          # message to send to the seller (None = stay silent)
    session: ValidationSession


class Orchestrator:
    def __init__(
        self,
        *,
        extraction: ExtractionAgent,
        validation: ValidationAgent,
        conversation: ConversationAgent,
        max_turns: int,
    ):
        self._extraction = extraction
        self._validation = validation
        self._conversation = conversation
        self._max_turns = max_turns

    def start(self, session: ValidationSession) -> OrchestratorResult:
        """Produce the opening message for a fresh session."""
        objective = self._validation.next_objective(session.checklist)
        reply = self._conversation.reply(session, objective)
        session.conversation.add(Role.AGENT, reply)
        return OrchestratorResult(reply=reply, session=session)

    def handle_inbound(self, session: ValidationSession, text: str) -> OrchestratorResult:
        if not session.conversation.is_open():
            return OrchestratorResult(reply=None, session=session)

        # 1. Understand: extract structured facts from the seller's message.
        extraction = self._extraction.run(session.conversation, text)
        session.conversation.add(Role.SELLER, text)

        # 2. Update shared state.
        self._validation.apply_updates(session.checklist, extraction.updates)

        # 3. Termination conditions (checked before generating a new question).
        if extraction.wants_to_stop:
            session.conversation.state = ConversationState.OPTED_OUT
        elif session.checklist.is_complete():
            session.conversation.state = ConversationState.COMPLETED
        elif session.conversation.agent_turns >= self._max_turns:
            session.conversation.state = ConversationState.TURN_LIMIT

        # 4. Decide + act: one farewell/wrap-up message on terminal states,
        #    otherwise pursue the next objective.
        if session.conversation.state == ConversationState.TURN_LIMIT:
            return OrchestratorResult(reply=None, session=session)

        objective = (
            None
            if session.conversation.state != ConversationState.ACTIVE
            else self._validation.next_objective(session.checklist)
        )
        reply = self._conversation.reply(session, objective)
        session.conversation.add(Role.AGENT, reply)
        return OrchestratorResult(reply=reply, session=session)
