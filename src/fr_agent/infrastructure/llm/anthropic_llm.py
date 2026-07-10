"""Anthropic adapter for LLMPort.

- complete(): plain text generation with the system prompt cached
  (cache_control on the stable prefix — see agents/prompts/conversation.py).
- extract(): structured outputs via messages.parse(), which guarantees the
  response validates against the given Pydantic model.
"""

from typing import TypeVar

import anthropic
from pydantic import BaseModel

from fr_agent.application.ports.llm import ChatMessage

T = TypeVar("T", bound=BaseModel)


class AnthropicLLM:
    def __init__(self, *, model: str, client: anthropic.Anthropic | None = None):
        # Zero-arg client resolves ANTHROPIC_API_KEY / auth profile from the env.
        self._client = client or anthropic.Anthropic()
        self._model = model

    def complete(self, *, system: str, messages: list[ChatMessage], max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[m.model_dump() for m in messages],
        )
        return next(b.text for b in response.content if b.type == "text").strip()

    def extract(self, *, system: str, messages: list[ChatMessage], output_type: type[T]) -> T:
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[m.model_dump() for m in messages],
            output_format=output_type,
        )
        return response.parsed_output
