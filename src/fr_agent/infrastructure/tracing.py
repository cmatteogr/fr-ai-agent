"""MLflow tracing: one trace per conversation (session root span), turns nested."""

from contextlib import contextmanager

import mlflow

from fr_agent.config import Settings

# Candidate keys MLflow versions use for session grouping; setting all is harmless.
SESSION_TAG_KEYS = ("session_id", "mlflow.sessionId", "mlflow.trace.session")


def setup_tracing(settings: Settings) -> None:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment)


def _tag_session(key: str) -> None:
    mlflow.update_current_trace(tags={k: key for k in SESSION_TAG_KEYS})


@contextmanager
def session_span(key: str):
    with mlflow.start_span(name=f"session-{key}") as span:
        span.set_attributes({"session_id": key})
        _tag_session(key)
        yield span


def start_session(key: str, **params) -> None:
    return None


def log_turn(key: str, turn_index: int, data: dict) -> None:
    with mlflow.start_span(name=f"turn_{turn_index:02d}") as span:
        span.set_inputs({"inbound": data.get("inbound")})
        span.set_outputs({"reply": data.get("reply")})
        span.set_attributes(
            {
                "session_id": key,
                "state": str(data.get("state")),
                "objectives": str(data.get("objectives")),
                "updates": str(data.get("updates")),
            }
        )
        _tag_session(key)


def end_session(key: str, summary: dict) -> None:
    with mlflow.start_span(name="session_summary") as span:
        span.set_inputs({"session_id": key})
        span.set_outputs(summary)
        span.set_attributes({"session_id": key, "state": str(summary.get("state"))})
        _tag_session(key)
