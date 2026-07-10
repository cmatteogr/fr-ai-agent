# fr-ai-agent

WhatsApp agent that converses with property sellers to validate listing information:
location, legal status, occupancy, renovations needed, minimum acceptable price, and
accepted payment methods.

Architecture: hexagonal layering (domain / application / infrastructure) with an
orchestrator + specialist-agents workflow. See [docs/architecture.md](docs/architecture.md).

## Project layout

```
src/fr_agent/
├── domain/          # Pure business models: Property, Conversation, ValidationChecklist
├── application/
│   ├── ports/       # Interfaces: LLMPort, MessagingPort, SessionRepository
│   └── use_cases/   # StartValidation, HandleInboundMessage
├── agents/          # Orchestrator + Extraction/Validation/Conversation agents + prompts
├── infrastructure/  # Adapters: Anthropic LLM, Meta WhatsApp, in-memory persistence
├── api/             # FastAPI app + WhatsApp webhook
├── bootstrap.py     # Composition root (all wiring happens here)
├── cli.py           # Local conversation simulator (no WhatsApp needed)
└── config.py        # Settings from environment / .env
```

## Setup

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
copy .env.example .env           # then fill in your keys
```

## Try it locally (no WhatsApp required)

```sh
set ANTHROPIC_API_KEY=sk-ant-...
python -m fr_agent.cli
```

You play the seller in the terminal; the agent runs the full
extraction → validation → conversation pipeline against the real model.

## Run the webhook server

```sh
uvicorn fr_agent.api.main:app --reload --port 8000
```

Expose it with a tunnel (`ngrok http 8000`), then configure the Meta app webhook to
`https://<tunnel>/webhook` using `FR_AGENT_WHATSAPP_VERIFY_TOKEN`.

## Tests

```sh
pytest
```

Tests run fully offline against `FakeLLM` — no API key needed.
