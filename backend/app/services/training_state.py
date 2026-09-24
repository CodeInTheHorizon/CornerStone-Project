from datetime import datetime, timezone
from threading import Lock
from typing import Any

_lock = Lock()
_state: dict[str, dict[str, Any]] = {}


def start(training_id: str) -> None:
    with _lock:
        _state[training_id] = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
        }


def finish(training_id: str, result: dict | None = None, error: str | None = None) -> None:
    with _lock:
        if training_id not in _state:
            return
        _state[training_id]["status"] = "failed" if error else "completed"
        _state[training_id]["result"] = result
        _state[training_id]["error"] = error
        _state[training_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


def get(training_id: str) -> dict[str, Any] | None:
    with _lock:
        return _state.get(training_id, {}).copy() or None


def all_active() -> dict[str, dict[str, Any]]:
    with _lock:
        return {k: v.copy() for k, v in _state.items() if v["status"] == "running"}
