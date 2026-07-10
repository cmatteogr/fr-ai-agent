"""FastAPI application entry point.

Run locally:
    uvicorn fr_agent.api.main:app --reload --port 8000

Expose it to Meta's webhook with a tunnel (e.g. `ngrok http 8000`) and set the
callback URL to https://<tunnel>/webhook with your verify token.
"""

from fastapi import FastAPI

from fr_agent.api.routes.webhook import router as webhook_router
from fr_agent.bootstrap import build_container

app = FastAPI(title="fr-ai-agent")
app.state.container = build_container()
app.include_router(webhook_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
