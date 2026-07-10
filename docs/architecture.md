# Architecture

WhatsApp agent that holds a conversation with a property seller to validate listing
information (location, legal status, occupancy, renovations, minimum price, payment
methods).

The design borrows from two references:

- **LLM Engineer's Handbook** (Iusztin & Labonne): clean layered architecture
  (domain / application / infrastructure), ports & adapters so every external
  dependency is swappable, prompts treated as versioned code, and a clear path from
  local dev to production.
- **Designing Multi-Agent Systems**: an orchestrator-workers pattern with *deterministic*
  control flow, explicit shared state, and explicit termination conditions — LLM calls
  are steps inside a workflow, not an open-ended autonomous loop.

## Layers

```
        ┌──────────────────────────────────────────────────────────┐
entry   │  api/ (FastAPI webhook)              cli.py (simulator)  │
        └───────────────┬──────────────────────────┬───────────────┘
                        ▼                          ▼
        ┌──────────────────────────────────────────────────────────┐
app     │  application/use_cases   StartValidation                 │
        │                          HandleInboundMessage            │
        │  application/ports       LLMPort MessagingPort           │
        │                          SessionRepository               │
        └───────────────┬──────────────────────────────────────────┘
                        ▼
        ┌──────────────────────────────────────────────────────────┐
agents  │  Orchestrator (deterministic control flow)               │
        │    ├── ExtractionAgent    message -> FieldUpdates        │
        │    ├── ValidationAgent    apply updates, next objective  │
        │    └── ConversationAgent  next WhatsApp message          │
        └───────────────┬──────────────────────────────────────────┘
                        ▼
        ┌──────────────────────────────────────────────────────────┐
domain  │  ValidationSession = Property + Conversation + Checklist │
        │  (pure Pydantic models, zero framework/LLM imports)      │
        └──────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
infra   │  AnthropicLLM / FakeLLM                                  │
        │  MetaWhatsAppMessenger / ConsoleMessenger                │
        │  InMemorySessionRepository (Postgres adapter: TODO)      │
        └──────────────────────────────────────────────────────────┘
```

Dependency rule: arrows only point downward/inward. The domain imports nothing from
the outer layers; agents depend only on ports and domain; infrastructure implements
ports. `bootstrap.py` is the single composition root where adapters are wired.

## The turn loop

Every inbound seller message runs this pipeline (see `agents/orchestrator.py`):

1. **ExtractionAgent** (LLM, structured output) parses the message into typed
   `FieldUpdate`s + an opt-out signal. Schema-constrained generation means no JSON
   parsing failures.
2. **ValidationAgent** (pure code) applies updates to the `ValidationChecklist` —
   including conflict detection when the seller contradicts a confirmed answer — and
   picks the next objective (first open field, priority = declaration order).
3. **Termination check** (pure code): seller opted out, checklist complete, or turn
   budget exhausted. The loop cannot run forever.
4. **ConversationAgent** (LLM, free text) writes the next WhatsApp message pursuing
   the single current objective, or a wrap-up/farewell on terminal states.

Why this split: the *state* (checklist) and the *policy* (what to ask next, when to
stop) are deterministic and unit-testable; the LLM is used only for the two things it
is uniquely good at — understanding free text and producing natural conversation.

## Key decisions

| Decision | Rationale |
|---|---|
| Workflow, not autonomous agent | The task is well-specified; deterministic orchestration is cheaper, safer, and debuggable. |
| `ValidationChecklist` as single source of truth | Add/remove fields in one enum; extraction schema, questioning policy and completion criteria all derive from it. |
| Structured outputs for extraction | `messages.parse()` guarantees schema-valid results; no fragile JSON handling. |
| Prompt caching | Stable system prompts are byte-identical across sessions; per-turn state goes in the last user block. |
| Ports for LLM / messaging / persistence | Swap Twilio for Meta, Postgres for in-memory, or another model without touching core logic. |
| `FakeLLM` + CLI simulator | Full pipeline testable offline; conversations testable interactively without WhatsApp. |

## Production TODOs (intentionally out of scaffold scope)

- **Durable persistence**: Postgres adapter for `SessionRepository` (sessions serialize
  via `model_dump_json()`).
- **Webhook security**: verify `X-Hub-Signature-256`; dedupe Meta's webhook retries by
  message id.
- **Template messages**: initiating a WhatsApp conversation outside the 24h service
  window requires pre-approved templates (`MetaWhatsAppMessenger.send_template`).
- **Observability**: log each agent step with token usage (`response.usage`); consider
  Opik/Langfuse-style tracing per the LLM Engineer's Handbook monitoring chapter.
- **Evaluation**: build a small set of scripted seller personas (cooperative, vague,
  contradictory, hostile) and run them through the orchestrator with the real model as
  a regression suite.
- **Human handoff**: on `CONFLICTING` fields that survive one clarification round, or
  legal questions, flag the session for a human instead of looping.
