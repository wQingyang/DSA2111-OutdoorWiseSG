"""Copy the tracked synthetic demonstration fixture to a NEW data directory.

Refuses existing destinations and fixtures containing active sessions or unknown users.
Never use this helper to initialize a public deployment.
"""
import argparse
import json
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_fixture(destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Destination must not exist; existing user data will not be overwritten.')
    source = ROOT / 'data/runtime'
    with sqlite3.connect(f'file:{source / "accounts.sqlite3"}?mode=ro', uri=True) as db:
        users = db.execute('SELECT user_id, username FROM users').fetchall()
        if {row[1] for row in users} != {'test_runner_1', 'test_runner_2'}:
            raise ValueError('Fixture must contain only the documented synthetic accounts.')
        if db.execute('SELECT count(*) FROM sessions').fetchone()[0]:
            raise ValueError('Fixture contains sessions; refusing to copy.')
    ids = {row[0] for row in users}
    names = ['completed_runs.json', 'difficulty_feedback.json']
    for name in names:
        rows = json.loads((source / 'personalization' / name).read_text())
        if any(row['user_id'] not in ids for row in rows):
            raise ValueError('Fixture history has an unexpected user.')
    (destination / 'runtime/personalization').mkdir(parents=True)
    shutil.copytree(ROOT / 'data/catalog', destination / 'catalog')
    shutil.copy2(source / 'accounts.sqlite3', destination / 'runtime/accounts.sqlite3')
    for name in names:
        shutil.copy2(source / 'personalization' / name, destination / 'runtime/personalization' / name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True)
    args = parser.parse_args()
    copy_fixture(args.data_root)
    print('Synthetic fixture copied. Run in demo mode only.')
