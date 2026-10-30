"""Explicit collection and inspection commands; the API never starts this worker."""
import argparse
import json
import signal
import threading

from .config import Settings
from .bootstrap import build_pipeline
from .contracts.models import Preferences


def main():
    """Dispatch collection, status, compatibility recommendations or schema output."""
    parser = argparse.ArgumentParser(description='OutdoorWise collection and pipeline commands')
    parser.add_argument('command', choices=['collect', 'watch', 'status', 'run', 'schemas'])
    parser.add_argument('--horizon', type=int, choices=[30, 60], default=30)
    parser.add_argument('--due', action='store_true')
    parser.add_argument(
        '--tick-seconds', type=float, default=30,
        help='Worker due-check interval; source polling comes from TOML',
    )
    parser.add_argument('--max-cycles', type=int, help='Optional finite worker run for verification')
    args = parser.parse_args()
    if args.command == 'schemas':
        from .contracts import environment, models
        print(json.dumps({
            name: obj.model_json_schema()
            for name in ['EnvironmentObservation', 'Location', 'IngestionRun',
                         'RouteEnvironment', 'Conditions', 'Prediction', 'Preferences', 'Run']
            if (obj := getattr(environment, name, None) or getattr(models, name))
        }, indent=2))
        return

    pipeline = build_pipeline(Settings.from_env())
    if args.command == 'collect':
        print(json.dumps(pipeline.refresh(due_only=args.due)))
    elif args.command == 'status':
        print(json.dumps(pipeline.repository.database_status(pipeline.mode), default=str, indent=2))
    elif args.command == 'watch':
        from .pipeline.worker import CollectionWorker
        stop = threading.Event()

        def request_stop(signum, frame):
            worker.request_stop(signal.Signals(signum).name)

        worker = CollectionWorker(
            pipeline, args.tick_seconds, args.max_cycles, stop,
            emit=lambda event: print(json.dumps(event, default=str), flush=True),
        )
        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, request_stop)
        try:
            worker.run()
        except (ValueError, RuntimeError) as exc:
            parser.exit(1, str(exc) + '\n')
    else:
        print(pipeline.run(Preferences(horizon_min=args.horizon)).model_dump_json(indent=2))


if __name__ == '__main__':
    main()
