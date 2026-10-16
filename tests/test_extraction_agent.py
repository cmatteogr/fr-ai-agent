"""ExtractionAgent's safety net when the model returns broken JSON."""

from fr_agent.agents.extraction_agent import ExtractionAgent
from fr_agent.application.ports.llm import ExtractionParseError
from fr_agent.domain.conversation import Conversation


class _BrokenLLM:
    """Simulates a model answer cut off at the token limit."""

    def __init__(self, raw: str):
        self._raw = raw

    def extract(self, **_):
        raise ExtractionParseError("Unterminated string", self._raw)


def test_cut_off_answer_still_ends_the_conversation():
    raw = '{"wants_to_stop": true, "updates": [{"field": "motivation", "status": "ski'
    result = ExtractionAgent(_BrokenLLM(raw)).run(Conversation(), "no me escriban más")
    assert result.wants_to_stop is True
    assert result.updates == []


def test_cut_off_answer_without_stop_signal_is_just_empty():
    raw = '{"wants_to_stop": false, "updates": [{"field": "motivation", "status": "ski'
    result = ExtractionAgent(_BrokenLLM(raw)).run(Conversation(), "hola")
    assert result.wants_to_stop is False
    assert result.updates == []
