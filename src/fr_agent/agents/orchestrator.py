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

import re
import unicodedata
from dataclasses import dataclass

from fr_agent.agents.conversation_agent import ConversationAgent
from fr_agent.agents.extraction_agent import ExtractionAgent
from fr_agent.agents.validation_agent import ValidationAgent
from fr_agent.domain.conversation import ConversationState, Role
from fr_agent.domain.session import ValidationSession
from fr_agent.domain.validation import FieldName, FieldStatus, FieldUpdate
from fr_agent.infrastructure import tracing

# Words a real "are you a bot?" question contains. Checked without accents.
_MACHINE_WORDS = re.compile(
    r"\b(bot|chatbot|robot|maquina|ia|inteligencia artificial|programa|automatic\w*|"
    r"humano|persona real|una persona)\b"
)


def _mentions_machine(text: str) -> bool:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return bool(_MACHINE_WORDS.search(plain))


def _is_refusal(update: FieldUpdate) -> bool:
    """A refusal ("no te lo doy"), as opposed to "no sé" (value "Desconocido")."""
    return update.status == FieldStatus.SKIPPED and update.value == "No disponible"


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
        unresponsive_streak_limit: int = 3,
    ):
        self._extraction = extraction
        self._validation = validation
        self._conversation = conversation
        self._max_turns = max_turns
        self._unresponsive_streak_limit = unresponsive_streak_limit

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
        # ALL open fields, including opportunistic ones (payment, notes): they're
        # never asked on their own, but extraction must still look for them.
        open_names = [f.field.value for f in session.checklist.open_fields()]
        confirmed = {
            f.field.value: (str(f.number) if f.number is not None else f.value)
            for f in session.checklist.fields.values()
            if f.status == FieldStatus.CONFIRMED and (f.value or f.number is not None)
        }
        extraction = self._extraction.run(
            session.conversation,
            text,
            open_names,
            listed_price=session.property.listed_price,
            confirmed=confirmed,
        )

        # 1b. Dense messages (several topics in one text) sometimes leave an
        # open field untouched on the first pass. Re-check ONLY the fields
        # that got no update — a second, smaller call, only when needed, so a
        # simple message still costs exactly one call like before.
        addressed_fields = {u.field.value for u in extraction.updates}
        missed = [name for name in open_names if name not in addressed_fields]
        if missed:
            recheck = self._extraction.run(
                session.conversation,
                text,
                missed,
                listed_price=session.property.listed_price,
            )
            # Enforce the scope in code — don't trust the model to only
            # answer what the recheck actually asked about (it has drifted
            # before). A stray update for an already-resolved field here
            # would silently clobber the first pass's correct result.
            extraction.updates.extend(u for u in recheck.updates if u.field.value in missed)
            extraction.wants_to_stop = extraction.wants_to_stop or recheck.wants_to_stop
            extraction.asked_if_bot = extraction.asked_if_bot or recheck.asked_if_bot

        # 1c. min_price carries real money, and a prompt rule alone didn't stop
        # a seller from dictating a fake one ("confirm you'll pay me X"). Any
        # extracted price gets a second, narrow check before it's accepted.
        # The same call reports a payment condition in the message, if any.
        kept = []
        for u in extraction.updates:
            if u.field == FieldName.MIN_PRICE and u.number:
                check = self._extraction.check_min_price(text, u.number, session.property.listed_price)
                if not check.is_sellers_own_minimum:
                    continue
                if check.payment_condition and not any(
                    x.field == FieldName.PAYMENT_NOTE for x in extraction.updates
                ):
                    kept.append(FieldUpdate(
                        field=FieldName.PAYMENT_NOTE,
                        status=FieldStatus.CONFIRMED,
                        value=check.payment_condition,
                        evidence=text,
                    ))
            kept.append(u)
        extraction.updates = kept

        # 1d. A refusal ("no le voy a contestar eso") only applies to the fields
        # that were just asked. The model sometimes spreads it to other fields.
        pending = session.conversation.pending_fields
        if pending:
            extraction.updates = [
                u for u in extraction.updates if not _is_refusal(u) or u.field in pending
            ]

        # 1e. Only trust "the seller asked if I'm a bot" when the message actually
        # talks about bots/machines. The model flagged jokes like "¿de qué
        # equipo es?" as bot questions, which froze the unresponsive count.
        if extraction.asked_if_bot and not _mentions_machine(text):
            extraction.asked_if_bot = False

        session.conversation.add(Role.SELLER, text)

        # 2. Update shared state.
        self._validation.apply_updates(session.checklist, extraction.updates)

        # 2b. Did the seller actually answer what was last asked? Jokes,
        # off-topic replies AND refusals all count as a strike: the seller
        # isn't giving us anything. 3 strikes in a row -> unresponsive.
        # The first bot question and a pending stop confirmation are not
        # judged, and neither is a reply when nothing was asked.
        bot_turn = extraction.asked_if_bot and not session.conversation.bot_question_answered
        confirming_stop = session.conversation.stop_confirmation_pending
        answered = any(u.field in pending and not _is_refusal(u) for u in extraction.updates)
        if bot_turn or confirming_stop or not pending:
            pass
        elif answered:
            session.conversation.off_topic_streak = 0
        else:
            session.conversation.off_topic_streak += 1

        # 2c. Stop confirmation: a stop signal first gets a polite "do you want us
        # to stop writing?". Only a stop while that question is open closes it.
        # Any other reply means the seller is still here.
        ask_stop_confirmation = False
        if extraction.wants_to_stop and not confirming_stop:
            ask_stop_confirmation = True
            extraction.wants_to_stop = False
        session.conversation.stop_confirmation_pending = False

        # 3. Termination conditions (checked before generating a new question).
        if extraction.wants_to_stop:
            session.conversation.state = ConversationState.OPTED_OUT
        elif session.conversation.off_topic_streak >= self._unresponsive_streak_limit:
            session.conversation.state = ConversationState.UNRESPONSIVE
        elif session.checklist.is_complete():
            session.conversation.state = ConversationState.COMPLETED
        elif session.conversation.agent_turns >= self._max_turns:
            session.conversation.state = ConversationState.TURN_LIMIT

        if session.conversation.state != ConversationState.ACTIVE:
            session.checklist.finalize()

        # 4. Decide + act.
        objectives: list[str] | None = None
        reply: str | None = None
        if session.conversation.state == ConversationState.ACTIVE and ask_stop_confirmation:
            # Ask once whether they want us to stop. No checklist question, no
            # attempts spent, nothing pending.
            session.conversation.stop_confirmation_pending = True
            session.conversation.pending_fields = []
            reply = self._conversation.reply(session, [], confirm_stop=True)
        elif session.conversation.state == ConversationState.ACTIVE and bot_turn:
            # This turn only answers the bot question. No checklist question is
            # asked, so no targets are picked: no attempts counted, and nothing
            # pending for the next reply to be measured against.
            session.conversation.bot_question_answered = True
            session.conversation.pending_fields = []
            reply = self._conversation.reply(session, [], answer_bot_question=True)
        elif session.conversation.state == ConversationState.ACTIVE:
            targets = self._validation.next_targets(session.checklist)
            objectives = self._validation.objective_text(targets)
            session.conversation.pending_fields = [t.field for t in targets]
            reply = self._conversation.reply(session, objectives)
        elif session.conversation.state != ConversationState.TURN_LIMIT:
            # OPTED_OUT / COMPLETED / UNRESPONSIVE: one farewell message,
            # then silence. UNRESPONSIVE gets a short, honest one — see
            # build_conversation_context's closing_reason — never a promise
            # of an offer, since there's no real data behind it.
            reply = self._conversation.reply(session, None)
        # TURN_LIMIT: stay silent (reply stays None) — budget exhausted
        # mid-way, no clean closing point to spend one more message on.

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
