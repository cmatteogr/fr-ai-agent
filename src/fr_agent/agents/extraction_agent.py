"""Extraction agent: seller message -> structured checklist updates.

Uses schema-constrained output (LLMPort.extract) — the endpoint is asked to
enforce the schema server-side, which is usually valid. "Usually" is not
"always": a model can still ramble past the token budget and hand back
truncated/invalid JSON (seen in testing — one off-topic seller reply caused
this). We do NOT retry (retrying the same input risks the same rambling
failure and doubles cost on exactly the calls that already went wrong) — we
log it and treat the turn as "no updates", so one bad completion never
crashes a real seller's conversation.
"""

import logging

from pydantic import BaseModel, Field

from fr_agent.agents.prompts.extraction import EXTRACTION_SYSTEM
from fr_agent.application.ports.llm import ChatMessage, LLMPort
from fr_agent.domain.conversation import Conversation, Role
from fr_agent.domain.validation import FieldUpdate

logger = logging.getLogger(__name__)


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
        try:
            return self._llm.extract(
                system=EXTRACTION_SYSTEM, messages=messages, output_type=ExtractionResult
            )
        except Exception:
            logger.warning(
                "Extraction failed to parse for message %r — treating as no updates this turn.",
                inbound_text,
                exc_info=True,
            )
            return ExtractionResult()


def _render_transcript(conversation: Conversation) -> str:
    label = {Role.AGENT: "Agent", Role.SELLER: "Seller"}
    return "\n".join(f"{label[m.role]}: {m.text}" for m in conversation.messages)
