"""Run tests in temporary installations; never load the developer's bot configuration."""

import os
from pathlib import Path

import pytest

from frontend_coverage_support import coverage_enabled, prepare_frontend_coverage


def pytest_sessionstart(session):
    """清空上一次运行的前端覆盖率 raw 数据，保证报告只反映本次会话。"""
    prepare_frontend_coverage()


@pytest.fixture(autouse=True)
def isolated_installation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = str(Path(__file__).resolve().parents[1])
    monkeypatch.setenv('PYTHONPATH', repo + os.pathsep + os.environ.get('PYTHONPATH', ''))
    for name in ('OLIVOS_WEBUI_HOST', 'OLIVOS_WEBUI_PORT'):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope='module')
def chrome_session(tmp_path_factory):
    if not os.environ.get('OLIVOS_WEBUI_BROWSER'):
        pytest.skip('Set OLIVOS_WEBUI_BROWSER=1 to run Chrome')
    from webui_test_support import ChromeSession

    session = ChromeSession(tmp_path_factory.mktemp('browser-profile'))
    session.open()
    try:
        yield session
    finally:
        session.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == 'call':
        item._frontend_coverage_outcome = report.outcome


@pytest.fixture(autouse=True)
def frontend_browser_coverage(request):
    if not coverage_enabled() or request.node.get_closest_marker('browser') is None:
        yield
        return
    session = request.getfixturevalue('chrome_session')
    session.set_coverage_context(request.node.nodeid)
    try:
        yield
    finally:
        outcome = getattr(request.node, '_frontend_coverage_outcome', 'unknown')
        session.set_coverage_context(request.node.nodeid, outcome)
        try:
            session.take_coverage()
        finally:
            session.set_coverage_context(None)


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
