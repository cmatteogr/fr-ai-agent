"""Application settings, loaded from environment variables / .env.

Everything configurable lives here so no other module reads os.environ directly.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FR_AGENT_", env_file=".env", extra="ignore"
    )

    # LLM
    llm_provider: str = "openai"
    model: str = "qwen.qwen3-32b"
    llm_api_key: str = ""
    llm_base_url: str = ""
    max_reply_tokens: int = 1024
    # 0 = as deterministic as the endpoint allows. Agreed with the team:
    # random ordering/skipped fields between identical runs made dataset
    # regressions unreadable (same input, different output every time).
    llm_temperature: float = 0.0

    # WhatsApp (Meta Cloud API)
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "change-me"
    whatsapp_api_version: str = "v21.0"

    # Conversation policy
    conversation_language: str = "es"
    max_turns: int = 30
    # How many turns in a row the seller can reply without addressing what
    # was actually asked (off-topic, jokes, deflection) before the agent
    # gives up on that seller instead of continuing to spend turns/tokens.
    unresponsive_streak_limit: int = 3
    
    # MLflow tracing
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    mlflow_experiment: str = "fr-ai-agent"


@lru_cache
def get_settings() -> Settings:
    return Settings()
