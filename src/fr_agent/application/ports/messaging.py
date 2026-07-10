"""Messaging port: outbound channel to the seller.

Implementations: infrastructure/messaging/meta_whatsapp.py (production),
infrastructure/messaging/console.py (local dev / CLI simulator).
Swapping to Twilio or another provider means writing one new adapter —
nothing in the application or agent layers changes.
"""

from typing import Protocol


class MessagingPort(Protocol):
    def send_text(self, *, to: str, text: str) -> None:
        """Send a plain-text message to a phone number (E.164)."""
        ...
