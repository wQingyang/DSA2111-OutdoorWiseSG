"""Worker heartbeat probe; source failures are disclosed without restart storms."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def healthy(root, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        report = json.loads((Path(root) / 'runtime/collection_worker.json').read_text())
        age = (now - datetime.fromisoformat(report['updated_at'])).total_seconds()
        # Eight bounded collector sequences can take over 15 minutes when APIs fail.
        return report['state'] == 'running' and 0 <= age <= 1800
    except (OSError, ValueError, KeyError, TypeError):
        return False


if __name__ == '__main__':
    raise SystemExit(0 if healthy(os.environ.get('OUTDOORWISE_DATA_ROOT', '/app/data')) else 1)
