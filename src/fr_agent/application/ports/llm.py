"""LLM port: the only surface through which agents talk to a language model.

Two operations cover every agent need:
  - complete: free-text generation (conversation agent)
  - extract:  schema-constrained generation into a Pydantic model (extraction agent)

Implementations: infrastructure/llm/anthropic_llm.py (production),
infrastructure/llm/fake_llm.py (tests / offline dev).
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class LLMPort(Protocol):
    def complete(self, *, system: str, messages: list[ChatMessage], max_tokens: int) -> str:
        """Generate a free-text reply."""
        ...

    def extract(self, *, system: str, messages: list[ChatMessage], output_type: type[T]) -> T:
        """Generate a response guaranteed to validate against `output_type`."""
        ...
