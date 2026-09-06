"""MLflow session tracing: ONE run per conversation session.
Each turn is logged as a JSON artifact inside that run, so the UI shows a
single row per session containing all its turns (instead of one trace per
inbound message).
"""

import mlflow

from fr_agent.config import Settings

# seller_phone -> mlflow run_id (in-process registry)
_runs: dict[str, str] = {}


def setup_tracing(settings: Settings) -> None:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment)


def start_session(key: str, **params) -> None:
    """Open the session run and remember its id."""
    with mlflow.start_run(run_name=f"session-{key}") as run:
        for name, value in params.items():
            mlflow.log_param(name, value)
        _runs[key] = run.info.run_id


def log_turn(key: str, turn_index: int, data: dict) -> None:
    """Attach one turn (inbound/outbound/updates) to the session run."""
    run_id = _runs.get(key)
    if not run_id:
        return
    with mlflow.start_run(run_id=run_id):
        mlflow.log_dict(data, f"turn_{turn_index:02d}.json")


def end_session(key: str, summary: dict) -> None:
    """Log the final checklist/state and close the session run."""
    run_id = _runs.pop(key, None)
    if not run_id:
        return
    with mlflow.start_run(run_id=run_id):
        mlflow.log_dict(summary, "session_summary.json")
        mlflow.set_tag("status", str(summary.get("state", "")))
