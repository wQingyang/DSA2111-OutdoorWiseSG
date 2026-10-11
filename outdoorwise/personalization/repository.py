import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .models import CompletedRun, DifficultyFeedback, FavouriteRoute


class PersonalizationRepository:
    """Atomic JSON-file persistence isolated below runtime/personalization."""

    def __init__(self, data_root: Path):
        self.root = Path(data_root) / "runtime" / "personalization"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._files = {
            "runs": self.root / "completed_runs.json",
            "favourites": self.root / "favourites.json",
            "feedback": self.root / "difficulty_feedback.json",
        }
        with self._lock:
            for path in self._files.values():
                if not path.exists():
                    self._atomic_write(path, [])

    def _read(self, kind):
        with self._files[kind].open() as handle:
            return json.load(handle)

    def _atomic_write(self, path, value):
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _append(self, kind, item):
        with self._lock:
            rows = self._read(kind)
            rows.append(item.model_dump(mode="json"))
            self._atomic_write(self._files[kind], rows)

    def save_completed_run(self, run: CompletedRun) -> CompletedRun:
        self._append("runs", run)
        return run

    def list_completed_runs(self, user_id: str) -> list[CompletedRun]:
        with self._lock:
            return [CompletedRun.model_validate(row) for row in self._read("runs") if row["user_id"] == user_id]

    def get_completed_run(self, user_id: str, completed_run_id: str) -> CompletedRun | None:
        return next((r for r in self.list_completed_runs(user_id) if r.completed_run_id == completed_run_id), None)

    def add_favourite(self, favourite: FavouriteRoute) -> FavouriteRoute:
        with self._lock:
            rows = self._read("favourites")
            existing = next((r for r in rows if r["user_id"] == favourite.user_id and
                             r["route_id"] == favourite.route_id), None)
            if existing is not None:
                return FavouriteRoute.model_validate(existing)
            rows.append(favourite.model_dump(mode="json"))
            self._atomic_write(self._files["favourites"], rows)
        return favourite

    def list_favourites(self, user_id: str) -> list[FavouriteRoute]:
        with self._lock:
            return [FavouriteRoute.model_validate(row) for row in self._read("favourites") if row["user_id"] == user_id]

    def remove_favourite(self, user_id: str, route_id: str) -> bool:
        with self._lock:
            rows = self._read("favourites")
            kept = [r for r in rows if not (r["user_id"] == user_id and r["route_id"] == route_id)]
            removed = len(kept) != len(rows)
            if removed:
                self._atomic_write(self._files["favourites"], kept)
            return removed

    def save_feedback(self, feedback: DifficultyFeedback) -> DifficultyFeedback:
        self._append("feedback", feedback)
        return feedback

    def list_feedback(self, user_id: str) -> list[DifficultyFeedback]:
        with self._lock:
            return [DifficultyFeedback.model_validate(row) for row in self._read("feedback") if row["user_id"] == user_id]
