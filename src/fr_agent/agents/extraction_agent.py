"""Extraction agent: seller message -> structured checklist updates.

Uses schema-constrained output (LLMPort.extract), so the result is always a
valid ExtractionResult — no JSON parsing or retry logic needed here.
"""

from pydantic import BaseModel, Field

from fr_agent.agents.prompts.extraction import EXTRACTION_SYSTEM
from fr_agent.application.ports.llm import ChatMessage, LLMPort
from fr_agent.domain.conversation import Conversation, Role
from fr_agent.domain.validation import FieldUpdate


class ExtractionResult(BaseModel):
    updates: list[FieldUpdate] = Field(default_factory=list)
    wants_to_stop: bool = False


class ExtractionAgent:
    def __init__(self, llm: LLMPort):
        self._llm = llm

    def run(self, conversation: Conversation, inbound_text: str) -> ExtractionResult:
        transcript = _render_transcript(conversation)
        messages = [
            ChatMessage(
                role="user",
                content=(
                    f"Conversation so far:\n{transcript or '(start of conversation)'}\n\n"
                    f"New seller message to analyze:\n{inbound_text}"
                ),
            )
        ]
        return self._llm.extract(
            system=EXTRACTION_SYSTEM, messages=messages, output_type=ExtractionResult
        )


def _render_transcript(conversation: Conversation) -> str:
    label = {Role.AGENT: "Agent", Role.SELLER: "Seller"}
    return "\n".join(f"{label[m.role]}: {m.text}" for m in conversation.messages)
