"""Render a per-user launchd job. Never install, load or start it automatically."""
import argparse
from pathlib import Path
import plistlib

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'sg.outdoorwise.collector'


def configuration(root=ROOT, log_dir=None):
    root = Path(root).resolve()
    log_dir = Path(log_dir or Path.home()/'Library/Logs/OutdoorWiseSG').expanduser().absolute()
    return {
        'Label': LABEL,
        'ProgramArguments': ['/bin/zsh', str(root/'scripts/run_macos_collector.zsh')],
        'WorkingDirectory': str(root),
        'EnvironmentVariables': {'PYTHONUNBUFFERED': '1'},
        'RunAtLoad': True,
        'KeepAlive': True,
        'ThrottleInterval': 30,
        'ExitTimeOut': 180,
        'ProcessType': 'Background',
        'StandardOutPath': str(log_dir/'collector.stdout.log'),
        'StandardErrorPath': str(log_dir/'collector.stderr.log'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--log-dir', type=Path)
    args = parser.parse_args()
    # The caller chooses the output path; no LaunchAgents/log directories are created.
    with args.output.open('wb') as handle:
        plistlib.dump(configuration(log_dir=args.log_dir), handle)
    print(f'Rendered {args.output}; no service installed or started.')


if __name__ == '__main__':
    main()
