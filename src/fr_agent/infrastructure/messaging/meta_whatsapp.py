"""Meta WhatsApp Cloud API adapter for MessagingPort.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
Note: outside the 24-hour customer-service window WhatsApp only allows
pre-approved template messages — that path is a TODO below.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class MetaWhatsAppMessenger:
    def __init__(self, *, token: str, phone_number_id: str, api_version: str = "v21.0"):
        self._url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {token}"}

    def send_text(self, *, to: str, text: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        response = httpx.post(self._url, headers=self._headers, json=payload, timeout=15)
        if response.status_code >= 400:
            logger.error("WhatsApp send failed (%s): %s", response.status_code, response.text)
        response.raise_for_status()

    # TODO: send_template(to, template_name, params) — required to *initiate*
    # conversations (outside the 24h service window WhatsApp rejects free text).
