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


def _to_strict_schema(schema: dict) -> dict:
    """Make a Pydantic JSON schema satisfy OpenAI 'strict' structured outputs:
    every object needs additionalProperties=false and EVERY property listed
    in 'required' (fields with defaults just always get sent back explicitly).
    Applied recursively to the top-level schema and every entry in $defs.
    """

    def fix_object(node: dict) -> None:
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
            for prop in node["properties"].values():
                fix_object(prop)
                for branch in prop.get("anyOf", []):
                    fix_object(branch)
        if node.get("type") == "array" and "items" in node:
            fix_object(node["items"])

    fix_object(schema)
    for definition in schema.get("$defs", {}).values():
        fix_object(definition)
    return schema


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.0,
        client: OpenAI | None = None,
    ):
        self._client = client or OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature

    def complete(
        self, *, system: str, messages: list[ChatMessage], max_tokens: int
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[{"role": "system", "content": system}]
            + [m.model_dump() for m in messages],
        )
        return (response.choices[0].message.content or "").strip()

    def extract(
        self, *, system: str, messages: list[ChatMessage], output_type: type[T]
    ) -> T:
        strict_schema = _to_strict_schema(output_type.model_json_schema())
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=4096,
            temperature=self._temperature,
            messages=[{"role": "system", "content": system}]
            + [m.model_dump() for m in messages],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": output_type.__name__,
                    "schema": strict_schema,
                    "strict": True,
                },
            },
        )
        raw = (response.choices[0].message.content or "").strip()
        return output_type.model_validate(json.loads(_strip_code_fences(raw)))
