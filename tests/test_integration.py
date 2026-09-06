from fr_agent.config import get_settings
from fr_agent.bootstrap import build_container
from fr_agent.infrastructure.llm.openai_llm import OpenAICompatibleLLM
from fr_agent.application.ports.llm import ChatMessage
import os


settings = get_settings()
print("Provider:", settings.llm_provider, "| Model:", settings.model)
print(
    "key cargada:",
    bool(settings.llm_api_key),
    "| base_url cargado:",
    bool(settings.llm_base_url),
)  # <-- esta línea

container = build_container()
print("Container armado OK ✅")

# 2) El adaptador habla con Qwen usando la config del proyecto
llm = OpenAICompatibleLLM(
    model=settings.model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)
k = settings.llm_api_key
print("len:", len(k), "| empieza:", repr(k[:4]), "| termina:", repr(k[-4:]))
reply = llm.complete(
    system="Sos un asistente.",
    messages=[ChatMessage(role="user", content="Respondé solo: integración ok")],
    max_tokens=50,
)
print("Respuesta del LLM:", reply)
