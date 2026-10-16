"""Composition root: the only place that wires concrete adapters to ports.

Both entry points (FastAPI webhook, CLI simulator) build their object graph
here. Swap any adapter (LLM, messaging, persistence) in one place.
"""

from dataclasses import dataclass

from fr_agent.agents.conversation_agent import ConversationAgent
from fr_agent.agents.extraction_agent import ExtractionAgent
from fr_agent.agents.orchestrator import Orchestrator
from fr_agent.agents.validation_agent import ValidationAgent
from fr_agent.application.ports.llm import LLMPort
from fr_agent.application.ports.messaging import MessagingPort
from fr_agent.application.ports.repository import SessionRepository
from fr_agent.application.use_cases.handle_inbound_message import HandleInboundMessage
from fr_agent.application.use_cases.start_validation import StartValidation
from fr_agent.config import Settings, get_settings
from fr_agent.infrastructure.llm.anthropic_llm import AnthropicLLM
from fr_agent.infrastructure.messaging.meta_whatsapp import MetaWhatsAppMessenger
from fr_agent.infrastructure.persistence.in_memory import InMemorySessionRepository
from fr_agent.infrastructure.llm.anthropic_llm import AnthropicLLM
from fr_agent.infrastructure.llm.openai_llm import OpenAICompatibleLLM
from fr_agent.infrastructure.tracing import setup_tracing


@dataclass
class Container:
    settings: Settings
    sessions: SessionRepository
    messaging: MessagingPort
    orchestrator: Orchestrator
    start_validation: StartValidation
    handle_inbound_message: HandleInboundMessage


def build_container(
    *,
    settings: Settings | None = None,
    llm: LLMPort | None = None,
    messaging: MessagingPort | None = None,
    sessions: SessionRepository | None = None,
) -> Container:
    """Production wiring by default; pass fakes for tests / local dev."""
    settings = settings or get_settings()
    setup_tracing(settings)
    llm = llm or _build_llm(settings)
    messaging = messaging or MetaWhatsAppMessenger(
        token=settings.whatsapp_token,
        phone_number_id=settings.whatsapp_phone_number_id,
        api_version=settings.whatsapp_api_version,
    )
    sessions = sessions or InMemorySessionRepository()

    orchestrator = Orchestrator(
        extraction=ExtractionAgent(llm),
        validation=ValidationAgent(),
        conversation=ConversationAgent(
            llm,
            language=settings.conversation_language,
            max_reply_tokens=settings.max_reply_tokens,
        ),
        max_turns=settings.max_turns,
        unresponsive_streak_limit=settings.unresponsive_streak_limit,
    )
    return Container(
        settings=settings,
        sessions=sessions,
        messaging=messaging,
        orchestrator=orchestrator,
        start_validation=StartValidation(
            orchestrator=orchestrator, sessions=sessions, messaging=messaging
        ),
        handle_inbound_message=HandleInboundMessage(
            orchestrator=orchestrator, sessions=sessions, messaging=messaging
        ),
    )


def _build_llm(settings: Settings) -> LLMPort:
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(model=settings.model)
    return OpenAICompatibleLLM(
        model=settings.model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
    )
