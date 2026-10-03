"""Run tests in temporary installations; never load the developer's bot configuration."""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_installation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = str(Path(__file__).resolve().parents[1])
    monkeypatch.setenv('PYTHONPATH', repo + os.pathsep + os.environ.get('PYTHONPATH', ''))
    for name in ('OLIVOS_WEBUI_HOST', 'OLIVOS_WEBUI_PORT'):
        monkeypatch.delenv(name, raising=False)


def pytest_collection_modifyitems(items):
    for item in items:
        if 'browser' in item.name or item.originalname in (
            'test_obsolete_login_cannot_finish_a_new_attempt',
            'test_grouped_navigation_preserves_all_pages',
        ):
            # Only Selenium tests are opt-in; HTTP tests mentioning browser URLs remain in the unit suite.
            if any('OLIVOS_WEBUI_BROWSER' in str(mark.kwargs.get('reason', ''))
                   or 'Chrome' in str(mark.kwargs.get('reason', ''))
                   for mark in item.iter_markers('skipif')):
                item.add_marker(pytest.mark.browser)
