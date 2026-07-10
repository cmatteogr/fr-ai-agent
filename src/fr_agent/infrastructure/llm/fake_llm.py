"""Deterministic fake LLM for tests and offline development.

- complete(): pops queued replies (or echoes a stub).
- extract(): pops queued structured results (or returns the type's defaults).
"""

from collections import deque
from typing import TypeVar

from pydantic import BaseModel

from fr_agent.application.ports.llm import ChatMessage

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    def __init__(self):
        self.replies: deque[str] = deque()
        self.extractions: deque[BaseModel] = deque()
        self.complete_calls: list[dict] = []
        self.extract_calls: list[dict] = []

    def complete(self, *, system: str, messages: list[ChatMessage], max_tokens: int) -> str:
        self.complete_calls.append({"system": system, "messages": messages})
        return self.replies.popleft() if self.replies else "(fake reply)"

    def extract(self, *, system: str, messages: list[ChatMessage], output_type: type[T]) -> T:
        self.extract_calls.append({"system": system, "messages": messages})
        if self.extractions:
            result = self.extractions.popleft()
            assert isinstance(result, output_type)
            return result
        return output_type()
