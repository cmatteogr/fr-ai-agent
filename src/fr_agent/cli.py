"""Interactive CLI simulator: play the seller, watch the agent work.

Runs the full pipeline (extraction -> validation -> conversation) against the
real Anthropic API, with console messaging and in-memory persistence — no
WhatsApp setup needed.

Usage:
    python -m fr_agent.cli
"""

from fr_agent.bootstrap import build_container
from fr_agent.config import get_settings
from fr_agent.domain.property import Property, Seller
from fr_agent.infrastructure.messaging.console import ConsoleMessenger
from fr_agent.infrastructure.persistence.in_memory import InMemorySessionRepository


def main() -> None:
    settings = get_settings()
    container = build_container(
        settings=settings,
        messaging=ConsoleMessenger(),
        sessions=InMemorySessionRepository(),
    )

    property_ = Property(
        id="demo-1",
        seller=Seller(name="Demo Seller", phone="+570000000000"),
        # Structured — what the listing actually has, pre-fills the checklist as CONFIRMED.
        address="Calle 4 Casa 12-22",
        neighborhood="Laureles",
        city="Medellín",
        # Free text — never treated as confirmed (listed price != seller's min_price).
        known_facts={
            "listed_price": "350,000,000 COP",
            "source": "listing portal (demo)",
        },
    )

    print("=== fr-ai-agent conversation simulator ===")
    print("You are the SELLER. Type your replies; Ctrl+C or 'exit' to quit.\n")

    session = container.start_validation.execute(property_)

    while session.conversation.is_open():
        try:
            text = input("[seller] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nbye")
            return
        if not text or text.lower() in {"exit", "quit"}:
            break
        container.handle_inbound_message.execute(from_phone=session.seller_phone, text=text)
        session = container.sessions.get_by_phone(session.seller_phone)

    print(f"\n=== conversation ended: {session.conversation.state} ===")
    print("Checklist result:")
    print(session.checklist.summary())


if __name__ == "__main__":
    main()
