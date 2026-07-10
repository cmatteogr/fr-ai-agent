import pytest

from fr_agent.bootstrap import build_container
from fr_agent.config import Settings
from fr_agent.domain.property import Property, Seller
from fr_agent.infrastructure.llm.fake_llm import FakeLLM
from fr_agent.infrastructure.messaging.console import ConsoleMessenger
from fr_agent.infrastructure.persistence.in_memory import InMemorySessionRepository


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def container(fake_llm):
    return build_container(
        settings=Settings(max_turns=5, _env_file=None),
        llm=fake_llm,
        messaging=ConsoleMessenger(),
        sessions=InMemorySessionRepository(),
    )


@pytest.fixture
def demo_property() -> Property:
    return Property(
        id="p-1",
        seller=Seller(name="Test Seller", phone="+571111111111"),
        known_facts={"listed_price": "100"},
    )
