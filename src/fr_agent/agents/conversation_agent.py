"""Conversation agent: produces the next WhatsApp message to the seller."""

from fr_agent.agents.prompts.conversation import (
    CONVERSATION_SYSTEM,
    build_conversation_context,
)
from fr_agent.application.ports.llm import ChatMessage, LLMPort
from fr_agent.domain.conversation import Role
from fr_agent.domain.session import ValidationSession


class ConversationAgent:
    def __init__(self, llm: LLMPort, *, language: str, max_reply_tokens: int = 1024):
        self._llm = llm
        self._system = CONVERSATION_SYSTEM.format(language=language)
        self._max_reply_tokens = max_reply_tokens

    def reply(self, session: ValidationSession, objective: str | None) -> str:
        messages = _to_chat_messages(session)
        known_facts = "\n".join(f"- {k}: {v}" for k, v in session.property.known_facts.items())
        messages.append(
            ChatMessage(
                role="user",
                content=build_conversation_context(
                    known_facts=known_facts,
                    checklist_summary=session.checklist.summary(),
                    objective=objective,
                ),
            )
        )
        return self._llm.complete(
            system=self._system, messages=messages, max_tokens=self._max_reply_tokens
        )


def _to_chat_messages(session: ValidationSession) -> list[ChatMessage]:
    """Map the domain transcript to LLM roles (seller=user, agent=assistant)."""
    role_map = {Role.SELLER: "user", Role.AGENT: "assistant"}
    return [
        ChatMessage(role=role_map[m.role], content=m.text)
        for m in session.conversation.messages
    ]
