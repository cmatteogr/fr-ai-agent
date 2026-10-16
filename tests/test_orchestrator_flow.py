"""End-to-end flow through use cases + orchestrator with a fake LLM."""

from fr_agent.agents.extraction_agent import ExtractionResult, MinPriceCheck
from fr_agent.domain.conversation import ConversationState
from fr_agent.domain.validation import FieldName, FieldStatus, FieldUpdate


def test_start_sends_opening_message(container, demo_property, fake_llm):
    fake_llm.replies.append("Hola! Vi tu propiedad en Laureles...")

    session = container.start_validation.execute(demo_property)

    assert container.messaging.sent == [
        ("+571111111111", "Hola! Vi tu propiedad en Laureles...")
    ]
    assert session.conversation.agent_turns == 1


def test_inbound_message_updates_checklist_and_replies(container, demo_property, fake_llm):
    fake_llm.replies.extend(["opening", "next question"])
    fake_llm.extractions.append(
        ExtractionResult(
            updates=[
                FieldUpdate(
                    field=FieldName.ADDRESS,
                    status=FieldStatus.CONFIRMED,
                    value="Calle 35 #70-20",
                    evidence="queda en la calle 35 con 70",
                )
            ]
        )
    )

    container.start_validation.execute(demo_property)
    container.handle_inbound_message.execute(
        from_phone="+571111111111", text="queda en la calle 35 con 70"
    )

    session = container.sessions.get_by_phone("+571111111111")
    assert session.checklist.fields[FieldName.ADDRESS].status == FieldStatus.CONFIRMED
    assert len(container.messaging.sent) == 2  # opening + follow-up


def test_opt_out_asks_first_then_closes(container, demo_property, fake_llm):
    fake_llm.replies.extend(["opening", "do you want us to stop?", "goodbye"])
    phone = "+571111111111"
    container.start_validation.execute(demo_property)

    # First stop signal: the agent asks for confirmation, conversation stays open.
    fake_llm.extractions.extend([ExtractionResult(wants_to_stop=True), ExtractionResult(wants_to_stop=True)])
    container.handle_inbound_message.execute(from_phone=phone, text="no me interesa, no escriba más")
    session = container.sessions.get_by_phone(phone)
    assert session.conversation.state == ConversationState.ACTIVE
    assert session.conversation.stop_confirmation_pending is True
    assert container.messaging.sent[-1][1] == "do you want us to stop?"

    # Confirmed: now it closes, with a farewell.
    fake_llm.extractions.extend([ExtractionResult(wants_to_stop=True), ExtractionResult(wants_to_stop=True)])
    container.handle_inbound_message.execute(from_phone=phone, text="sí")
    session = container.sessions.get_by_phone(phone)
    assert session.conversation.state == ConversationState.OPTED_OUT
    assert container.messaging.sent[-1][1] == "goodbye"


def test_stop_confirmation_answered_no_keeps_going(container, demo_property, fake_llm):
    phone = "+571111111111"
    container.start_validation.execute(demo_property)
    fake_llm.extractions.extend([ExtractionResult(wants_to_stop=True), ExtractionResult(wants_to_stop=True)])
    container.handle_inbound_message.execute(from_phone=phone, text="ya, sin más vueltas")
    # Seller says to continue: no stop signal -> back to normal questions.
    container.handle_inbound_message.execute(from_phone=phone, text="no, sigamos")
    session = container.sessions.get_by_phone(phone)
    assert session.conversation.state == ConversationState.ACTIVE
    assert session.conversation.stop_confirmation_pending is False
    assert session.conversation.pending_fields  # questions are being asked again


def test_unknown_number_is_ignored(container):
    container.handle_inbound_message.execute(from_phone="+579999999999", text="hola?")
    assert container.messaging.sent == []


def test_bot_question_turn_spends_no_attempts(container, demo_property, fake_llm):
    fake_llm.replies.extend(["opening", "first question", "honest bot answer"])
    fake_llm.extractions.append(ExtractionResult())  # turn 1: normal, nothing extracted
    container.start_validation.execute(demo_property)
    container.handle_inbound_message.execute(from_phone="+571111111111", text="hola")

    session = container.sessions.get_by_phone("+571111111111")
    attempts_before = {f: c.attempts for f, c in session.checklist.fields.items()}
    streak_before = session.conversation.off_topic_streak

    # turn 2: the seller asks if this is a bot (first pass + recheck both say so)
    fake_llm.extractions.extend([ExtractionResult(asked_if_bot=True), ExtractionResult(asked_if_bot=True)])
    container.handle_inbound_message.execute(from_phone="+571111111111", text="¿usted es un programa?")

    session = container.sessions.get_by_phone("+571111111111")
    assert {f: c.attempts for f, c in session.checklist.fields.items()} == attempts_before
    assert session.conversation.pending_fields == []
    assert session.conversation.off_topic_streak == streak_before
    assert container.messaging.sent[-1][1] == "honest bot answer"


def _price_turn(container, demo_property, fake_llm, check_says: bool):
    fake_llm.replies.extend(["opening", "next"])
    fake_llm.extractions.extend([
        ExtractionResult(updates=[
            FieldUpdate(field=FieldName.MIN_PRICE, status=FieldStatus.CONFIRMED, number=900000000)
        ]),
        ExtractionResult(),  # recheck pass for the other open fields
        MinPriceCheck(reason="test", is_sellers_own_minimum=check_says),
    ])
    container.start_validation.execute(demo_property)
    container.handle_inbound_message.execute(from_phone="+571111111111", text="un mensaje con una cifra")
    return container.sessions.get_by_phone("+571111111111").checklist.fields[FieldName.MIN_PRICE]


def test_rejected_min_price_never_reaches_the_checklist(container, demo_property, fake_llm):
    field = _price_turn(container, demo_property, fake_llm, check_says=False)
    assert field.status == FieldStatus.PENDING
    assert field.number is None


def test_accepted_min_price_is_kept(container, demo_property, fake_llm):
    field = _price_turn(container, demo_property, fake_llm, check_says=True)
    assert field.status == FieldStatus.CONFIRMED
    assert field.number == 900000000


def test_second_bot_question_counts_as_off_topic(container, demo_property, fake_llm):
    container.start_validation.execute(demo_property)
    phone = "+571111111111"
    # turn 1: normal (nothing extracted) -> questions get asked
    container.handle_inbound_message.execute(from_phone=phone, text="hola")
    # turn 2: off-topic -> streak 1
    container.handle_inbound_message.execute(from_phone=phone, text="jaja")
    assert container.sessions.get_by_phone(phone).conversation.off_topic_streak == 1
    # turn 3: first bot question -> streak frozen, nothing asked this turn
    fake_llm.extractions.extend([ExtractionResult(asked_if_bot=True), ExtractionResult(asked_if_bot=True)])
    container.handle_inbound_message.execute(from_phone=phone, text="¿usted es un programa?")
    assert container.sessions.get_by_phone(phone).conversation.off_topic_streak == 1
    # turn 4: reply after the bot turn -> nothing was asked, streak unchanged (not reset)
    container.handle_inbound_message.execute(from_phone=phone, text="ok")
    assert container.sessions.get_by_phone(phone).conversation.off_topic_streak == 1
    # turn 5: second bot question -> no exception anymore, counts as off-topic
    fake_llm.extractions.extend([ExtractionResult(asked_if_bot=True), ExtractionResult(asked_if_bot=True)])
    container.handle_inbound_message.execute(from_phone=phone, text="¿de verdad es un programa?")
    assert container.sessions.get_by_phone(phone).conversation.off_topic_streak == 2


def _ask_once(container, demo_property):
    """Start + one normal turn, so the agent has asked questions (pending fields)."""
    container.start_validation.execute(demo_property)
    container.handle_inbound_message.execute(from_phone="+571111111111", text="hola")
    return container.sessions.get_by_phone("+571111111111")


def test_joke_flagged_as_bot_question_is_not_trusted(container, demo_property, fake_llm):
    session = _ask_once(container, demo_property)
    assert session.conversation.off_topic_streak == 0
    # The model wrongly says "bot question", but the message has no machine words.
    fake_llm.extractions.extend([ExtractionResult(asked_if_bot=True), ExtractionResult(asked_if_bot=True)])
    container.handle_inbound_message.execute(from_phone="+571111111111", text="¿y usted de qué ciudad es?")
    session = container.sessions.get_by_phone("+571111111111")
    assert session.conversation.bot_question_answered is False
    assert session.conversation.off_topic_streak == 1  # counted as off-topic


def test_refusal_only_turn_counts_as_a_strike(container, demo_property, fake_llm):
    session = _ask_once(container, demo_property)
    asked = session.conversation.pending_fields[0]
    refusal = FieldUpdate(field=asked, status=FieldStatus.SKIPPED, value="No disponible")
    fake_llm.extractions.extend([ExtractionResult(updates=[refusal]), ExtractionResult()])
    container.handle_inbound_message.execute(from_phone="+571111111111", text="eso no lo respondo")
    session = container.sessions.get_by_phone("+571111111111")
    assert session.checklist.fields[asked].status == FieldStatus.SKIPPED  # still recorded
    assert session.conversation.off_topic_streak == 1


def test_refusal_on_a_field_not_asked_is_dropped(container, demo_property, fake_llm):
    session = _ask_once(container, demo_property)
    not_asked = next(f for f in FieldName if f not in session.conversation.pending_fields
                     and session.checklist.fields[f].status == FieldStatus.PENDING)
    refusal = FieldUpdate(field=not_asked, status=FieldStatus.SKIPPED, value="No disponible")
    fake_llm.extractions.extend([ExtractionResult(updates=[refusal]), ExtractionResult()])
    container.handle_inbound_message.execute(from_phone="+571111111111", text="no tenemos esa información")
    session = container.sessions.get_by_phone("+571111111111")
    assert session.checklist.fields[not_asked].status == FieldStatus.PENDING


def test_price_check_also_fills_the_payment_condition(container, demo_property, fake_llm):
    fake_llm.extractions.extend([
        ExtractionResult(updates=[
            FieldUpdate(field=FieldName.MIN_PRICE, status=FieldStatus.CONFIRMED, number=300000000)
        ]),
        ExtractionResult(),
        MinPriceCheck(reason="ok", is_sellers_own_minimum=True,
                      payment_condition="Negociable solo con pago en efectivo"),
    ])
    container.start_validation.execute(demo_property)
    container.handle_inbound_message.execute(from_phone="+571111111111", text="un mensaje con cifra")
    note = container.sessions.get_by_phone("+571111111111").checklist.fields[FieldName.PAYMENT_NOTE]
    assert note.status == FieldStatus.CONFIRMED
    assert note.value == "Negociable solo con pago en efectivo"
