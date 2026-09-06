"""Orchestrator: deterministic control flow over the specialist agents.

Pattern: orchestrator-workers with explicit shared state (the session) and
explicit termination conditions — the loop cannot run away:

    inbound message
        │
        ▼
    ExtractionAgent  ── structured updates ──►  ValidationAgent (apply + pick objectives)
        │                                             │
        ▼                                             ▼
    termination check (opt-out / complete / turn budget)
        │
        ▼
    ConversationAgent ── next WhatsApp message ──► outbound

The orchestrator never talks to the LLM directly and never touches I/O;
it only coordinates agents and mutates the session. Delivery/persistence
happen in the use-case layer. Observability (MLflow) lives here too:
one run per session, one JSON artifact per turn.
"""

from dataclasses import dataclass

from fr_agent.agents.conversation_agent import ConversationAgent
from fr_agent.agents.extraction_agent import ExtractionAgent
from fr_agent.agents.validation_agent import ValidationAgent
from fr_agent.domain.conversation import ConversationState, Role
from fr_agent.domain.session import ValidationSession
from fr_agent.infrastructure import tracing


@dataclass
class OrchestratorResult:
    reply: str | None  # message to send to the seller (None = stay silent)
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
        """Open the MLflow session run and send the pure greeting."""
        phone = session.seller_phone
        tracing.start_session(phone)
        reply = self._conversation.reply(session, [])  # [] = first contact, no data yet
        session.conversation.add(Role.AGENT, reply)
        tracing.log_turn(
            phone,
            0,
            {"inbound": None, "reply": reply, "state": session.conversation.state},
        )
        return OrchestratorResult(reply=reply, session=session)

    def handle_inbound(
        self, session: ValidationSession, text: str
    ) -> OrchestratorResult:
        phone = session.seller_phone
        if not session.conversation.is_open():
            return OrchestratorResult(reply=None, session=session)

        turn_index = len(session.conversation.messages)

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

        if session.conversation.state != ConversationState.ACTIVE:
            session.checklist.finalize()

        # 4. Decide + act.
        objectives: list[str] | None = None
        reply: str | None = None
        if session.conversation.state == ConversationState.ACTIVE:
            objectives = self._validation.next_objectives(session.checklist)
            reply = self._conversation.reply(session, objectives)
        elif session.conversation.state != ConversationState.TURN_LIMIT:
            # OPTED_OUT / COMPLETED: one farewell message, then silence.
            reply = self._conversation.reply(session, None)
        # TURN_LIMIT: stay silent (reply stays None).

        if reply is not None:
            session.conversation.add(Role.AGENT, reply)

        # 5. Trace the whole turn inside the session run.
        tracing.log_turn(
            phone,
            turn_index,
            {
                "inbound": text,
                "updates": [u.model_dump(mode="json") for u in extraction.updates],
                "objectives": objectives,
                "reply": reply,
                "state": session.conversation.state,
            },
        )

        # 6. Close the session run on terminal states.
        if session.conversation.state != ConversationState.ACTIVE:
            tracing.end_session(
                phone,
                {
                    "state": session.conversation.state,
                    "checklist": session.checklist.summary(),
                },
            )

        return OrchestratorResult(reply=reply, session=session)
