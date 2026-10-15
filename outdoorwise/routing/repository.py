import json
import os
import threading
from pathlib import Path

from .models import GeneratedRoute


class GeneratedRouteRepository:
    def __init__(self, data_root: Path):
        self.path = data_root / "runtime" / "generated_routes.json"
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return {item["route_id"]: item for item in json.loads(self.path.read_text())}

    def save_all(self, routes: list[GeneratedRoute]) -> None:
        with self._lock:
            records = self._read()
            records.update({route.route_id: route.model_dump(mode="json") for route in routes})
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(list(records.values()), indent=2))
            os.replace(temporary, self.path)

    def get(self, route_id: str) -> GeneratedRoute | None:
        with self._lock:
            value = self._read().get(route_id)
        return GeneratedRoute.model_validate(value) if value else None

