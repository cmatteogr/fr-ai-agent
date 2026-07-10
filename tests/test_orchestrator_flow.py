"""End-to-end flow through use cases + orchestrator with a fake LLM."""

from fr_agent.agents.extraction_agent import ExtractionResult
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
                    field=FieldName.LOCATION,
                    status=FieldStatus.CONFIRMED,
                    value="Calle 35 #70-20, Laureles, Medellín",
                    evidence="queda en la calle 35 con 70 en Laureles",
                )
            ]
        )
    )

    container.start_validation.execute(demo_property)
    container.handle_inbound_message.execute(
        from_phone="+571111111111", text="queda en la calle 35 con 70 en Laureles"
    )

    session = container.sessions.get_by_phone("+571111111111")
    assert session.checklist.fields[FieldName.LOCATION].status == FieldStatus.CONFIRMED
    assert len(container.messaging.sent) == 2  # opening + follow-up


def test_opt_out_closes_conversation(container, demo_property, fake_llm):
    fake_llm.replies.extend(["opening", "goodbye"])
    fake_llm.extractions.append(ExtractionResult(wants_to_stop=True))

    container.start_validation.execute(demo_property)
    container.handle_inbound_message.execute(
        from_phone="+571111111111", text="no me interesa, no escriba más"
    )

    session = container.sessions.get_by_phone("+571111111111")
    assert session.conversation.state == ConversationState.OPTED_OUT
    # A farewell was still sent
    assert container.messaging.sent[-1][1] == "goodbye"


def test_unknown_number_is_ignored(container):
    container.handle_inbound_message.execute(from_phone="+579999999999", text="hola?")
    assert container.messaging.sent == []
