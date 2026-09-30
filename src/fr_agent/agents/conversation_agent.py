"""Conversation agent: produces the next WhatsApp message to the seller."""

from fr_agent.agents.prompts.conversation import (
    CONVERSATION_SYSTEM,
    build_conversation_context,
)
from fr_agent.application.ports.llm import ChatMessage, LLMPort
from fr_agent.domain.conversation import Role
from fr_agent.domain.session import ValidationSession


def _known_facts_text(session: ValidationSession) -> str:
    prop = getattr(session, "property", None)
    facts = getattr(prop, "known_facts", {}) or {}
    return "\n".join(f"- {k}: {v}" for k, v in facts.items())


class ConversationAgent:
    def __init__(self, llm: LLMPort, *, language: str, max_reply_tokens: int):
        self._llm = llm
        self._language = language
        self._max_reply_tokens = max_reply_tokens

    def reply(self, session: ValidationSession, objectives: list[str] | None) -> str:
        system = CONVERSATION_SYSTEM.format(language=self._language)
        context = build_conversation_context(
            known_facts=_known_facts_text(session),
            checklist_summary=session.checklist.summary(),
            objectives=objectives,
            closing_reason=session.conversation.state.value if objectives is None else None,
        )
        history = [
            ChatMessage(
                role="assistant" if m.role == Role.AGENT else "user",
                content=m.text,
            )
            for m in session.conversation.messages[-6:]
        ]
        messages = history + [ChatMessage(role="user", content=context)]
        return self._llm.complete(
            system=system,
            messages=messages,
            max_tokens=self._max_reply_tokens,
        )
