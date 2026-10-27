"""Isolate the module-level FastAPI app before test collection imports it.

Individual tests already pass temporary repositories. This also protects local
accounts/CSV files when api.app creates its default application at import time.
"""
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory


def pytest_configure(config):
    root = Path(__file__).resolve().parents[1]
    directory = TemporaryDirectory(prefix='outdoorwise-pytest-app-')
    shutil.copytree(root / 'data/catalog', Path(directory.name) / 'catalog')
    config._outdoorwise_test_directory = directory
    config._outdoorwise_previous_data_root = os.environ.get('OUTDOORWISE_DATA_ROOT')
    os.environ['OUTDOORWISE_DATA_ROOT'] = directory.name


def pytest_unconfigure(config):
    previous = getattr(config, '_outdoorwise_previous_data_root', None)
    if previous is None:
        os.environ.pop('OUTDOORWISE_DATA_ROOT', None)
    else:
        os.environ['OUTDOORWISE_DATA_ROOT'] = previous
    directory = getattr(config, '_outdoorwise_test_directory', None)
    if directory is not None:
        directory.cleanup()
