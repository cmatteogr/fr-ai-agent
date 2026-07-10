"""Meta WhatsApp Cloud API webhook.

GET  /webhook — subscription verification handshake (hub.challenge echo).
POST /webhook — inbound message notifications.

Payload reference:
https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/webhook")
def verify_webhook(
    request: Request,
    mode: str = Query(alias="hub.mode", default=""),
    token: str = Query(alias="hub.verify_token", default=""),
    challenge: str = Query(alias="hub.challenge", default=""),
) -> PlainTextResponse:
    settings = request.app.state.container.settings
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks) -> dict:
    # TODO(production): verify the X-Hub-Signature-256 header against the app
    # secret before trusting the payload.
    payload = await request.json()
    container = request.app.state.container

    for from_phone, text in _extract_text_messages(payload):
        # Respond 200 immediately; LLM work happens off the request path so
        # Meta doesn't retry the webhook while we think.
        background.add_task(
            container.handle_inbound_message.execute, from_phone=from_phone, text=text
        )
    return {"status": "received"}


def _extract_text_messages(payload: dict) -> list[tuple[str, str]]:
    """Pull (sender, text) pairs out of Meta's nested webhook envelope."""
    results: list[tuple[str, str]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []):
                if message.get("type") == "text":
                    results.append((message["from"], message["text"]["body"]))
                else:
                    logger.info("Ignoring non-text message type: %s", message.get("type"))
    return results
