"""OpenAI-compatible adapter for LLMPort (Qwen vía base_url custom).
complete(): el system prompt va como mensaje role="system" (OpenAI no tiene
            parámetro system separado ni cache_control como Anthropic).
extract():  salida estructurada portable: pedimos JSON vía prompt y validamos
            con Pydantic. Funciona aunque el endpoint no tenga structured outputs.
"""

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from fr_agent.application.ports.llm import ChatMessage

T = TypeVar("T", bound=BaseModel)


def _strip_code_fences(text: str) -> str:
    """Algunos modelos envuelven el JSON en ```json ... ```; lo limpiamos."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


class OpenAICompatibleLLM:
    def __init__(
        self, *, model: str, api_key: str, base_url: str, client: OpenAI | None = None
    ):
        self._client = client or OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def complete(
        self, *, system: str, messages: list[ChatMessage], max_tokens: int
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}]
            + [m.model_dump() for m in messages],
        )
        return (response.choices[0].message.content or "").strip()

    def extract(
        self, *, system: str, messages: list[ChatMessage], output_type: type[T]
    ) -> T:
        schema = json.dumps(output_type.model_json_schema(), ensure_ascii=False)
        full_system = (
            f"{system}\n\n"
            "Respondé ÚNICAMENTE con un objeto JSON válido que cumpla EXACTAMENTE este schema, "
            "sin texto adicional ni bloques de código:\n"
            f"{schema}"
        )
        raw = self.complete(system=full_system, messages=messages, max_tokens=4096)
        return output_type.model_validate(json.loads(_strip_code_fences(raw)))
