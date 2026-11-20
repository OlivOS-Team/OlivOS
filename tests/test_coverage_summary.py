'''覆盖率汇总脚本：测试执行结果与覆盖率组合输出。'''

import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def _summary_module():
    path = Path(__file__).resolve().parents[1] / 'script' / 'coverage_summary.py'
    spec = importlib.util.spec_from_file_location('coverage_summary_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_coverage(path):
    data = {
        'totals': {
            'covered_lines': 5,
            'num_statements': 10,
            'covered_branches': 2,
            'num_branches': 4,
        },
        'files': {
            'OlivOS/core/demo.py': {
                'summary': {
                    'covered_lines': 5,
                    'num_statements': 10,
                    'covered_branches': 2,
                    'num_branches': 4,
                    'missing_lines': 5,
                    'missing_branches': 2,
                },
            },
        },
    }
    path.write_text(json.dumps(data), encoding='utf-8')


def _write_junit(path, cases, totals=None):
    root = ET.Element('testsuites')
    suite = ET.SubElement(root, 'testsuite', {'name': 'pytest', **(totals or {})})
    for classname, name, duration, outcome, message in cases:
        case = ET.SubElement(
            suite,
            'testcase',
            {'classname': classname, 'name': name, 'time': duration},
        )
        if outcome:
            result = ET.SubElement(case, outcome)
            if message:
                result.set('message', message)
                if outcome in ('failure', 'error'):
                    result.text = 'trace'
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def test_report_combines_test_counts_and_coverage(tmp_path):
    '''同一份报告中同时显示通过/失败/跳过数量与覆盖率。'''
    coverage_path = tmp_path / 'coverage.json'
    junit_path = tmp_path / 'junit.xml'
    _write_coverage(coverage_path)
    _write_junit(
        junit_path,
        [
            ('tests.test_sample', 'test_ok', '0.10', None, None),
            ('tests.test_sample', 'test_ok_too', '0.15', None, None),
            ('tests.test_sample', 'test_skip', '0.00', 'skipped', 'skip'),
            ('tests.test_sample', 'test_broken', '1.00', 'failure', 'boom'),
        ],
        {'tests': '4', 'failures': '1', 'errors': '0', 'skipped': '1', 'time': '1.25'},
    )
    text, available = _summary_module().build_report(coverage_path, junit_path)
    assert available is True
    # 两项通过、一项跳过、一项失败，统计必须与 JUnit 汇总一致。
    assert '| 4 | 2 | 1 | 0 | 1 | 1.25 秒 |' in text
    # 失败用例和覆盖率摘要应位于同一份 Markdown。
    assert 'tests.test_sample::test_broken' in text
    assert '行：**50.00%** (5/10)' in text
    assert text.index('### 测试执行结果') < text.index('### 覆盖率')


def test_report_counts_cases_when_suite_totals_are_missing(tmp_path):
    '''JUnit 缺少 testsuite 汇总属性时按 testcase 子节点计数。'''
    coverage_path = tmp_path / 'coverage.json'
    junit_path = tmp_path / 'junit.xml'
    _write_coverage(coverage_path)
    _write_junit(
        junit_path,
        [
            ('tests.test_sample', 'test_ok', '0.10', None, None),
            ('tests.test_sample', 'test_skip', '0.00', 'skipped', None),
            ('tests.test_sample', 'test_error', '0.00', 'error', 'collection'),
        ],
    )
    text, available = _summary_module().build_report(coverage_path, junit_path)
    assert available is True
    assert '| 3 | 1 | 0 | 1 | 1 | 0.10 秒 |' in text
    assert 'tests.test_sample::test_error' in text


def test_report_keeps_coverage_when_junit_is_missing(tmp_path):
    '''JUnit 缺失时仍输出覆盖率，并明确提示测试结果不可用。'''
    coverage_path = tmp_path / 'coverage.json'
    _write_coverage(coverage_path)
    text, available = _summary_module().build_report(coverage_path)
    assert available is True
    assert 'JUnit 报告不可用' in text
    assert '行：**50.00%** (5/10)' in text


def test_report_marks_coverage_missing_but_keeps_test_result(tmp_path):
    '''覆盖率缺失时保留测试统计，并以返回值标记失败。'''
    junit_path = tmp_path / 'junit.xml'
    _write_junit(
        junit_path,
        [('tests.test_sample', 'test_ok', '0.10', None, None)],
        {'tests': '1', 'failures': '0', 'errors': '0', 'skipped': '0', 'time': '0.10'},
    )
    text, available = _summary_module().build_report(tmp_path / 'coverage.json', junit_path)
    assert available is False
    assert '| 1 | 1 | 0 | 0 | 0 | 0.10 秒 |' in text
    assert '覆盖率报告不可用' in text


def test_combined_report_shows_all_platforms_and_totals(tmp_path):
    '''跨平台汇总应显示每个平台的结果、合计与明细。'''
    ubuntu = tmp_path / 'test-summary-ubuntu-latest'
    windows = tmp_path / 'test-summary-windows-latest'
    ubuntu.mkdir()
    windows.mkdir()
    _write_coverage(ubuntu / 'coverage.json')
    _write_junit(
        ubuntu / 'junit.xml',
        [
            ('tests.test_sample', 'test_ok', '0.10', None, None),
            ('tests.test_sample', 'test_ok_too', '0.20', None, None),
        ],
        {'tests': '2', 'failures': '0', 'errors': '0', 'skipped': '0', 'time': '0.30'},
    )
    _write_coverage(windows / 'coverage.json')
    _write_junit(
        windows / 'junit.xml',
        [
            ('tests.test_sample', 'test_ok', '0.10', None, None),
            ('tests.test_sample', 'test_ok_too', '0.20', None, None),
            ('tests.test_sample', 'test_skip', '0.00', 'skipped', 'skip'),
        ],
        {'tests': '3', 'failures': '0', 'errors': '0', 'skipped': '1', 'time': '0.30'},
    )
    module = _summary_module()
    results = module.collect_results(tmp_path)
    text, available = module.build_combined_report(results)
    assert available is True
    # 每个平台的测试统计必须出现在同一张表，并提供跨平台合计。
    assert '| `ubuntu-latest` | 2 | 2 | 0 | 0 | 0 |' in text
    assert '| `windows-latest` | 3 | 2 | 0 | 0 | 1 |' in text
    assert '| **合计** | 5 | 4 | 0 | 0 | 1 |' in text
    # 覆盖率按平台分别展示，不做跨平台平均。
    assert '| `ubuntu-latest` | 50.00% | 50.00% | 5 | 2 |' in text
    assert '不同平台覆盖率分别统计，不跨平台平均。' in text
    # 平台明细放在可折叠区块中，避免汇总页过长。
    assert '<summary>`ubuntu-latest` 明细</summary>' in text


def test_collect_results_finds_reports_in_nested_test_results(tmp_path):
    '''artifact 保留 test-results 子目录时仍能找到覆盖率与 JUnit 报告。'''
    reports = tmp_path / 'test-summary-macos-latest' / 'test-results'
    reports.mkdir(parents=True)
    _write_coverage(reports / 'coverage.json')
    _write_junit(
        reports / 'junit.xml',
        [('tests.test_sample', 'test_ok', '0.10', None, None)],
        {'tests': '1', 'failures': '0', 'errors': '0', 'skipped': '0', 'time': '0.10'},
    )
    results = _summary_module().collect_results(tmp_path)
    assert [result['name'] for result in results] == ['macos-latest']
    assert results[0]['coverage']['totals']['covered_lines'] == 5
    assert results[0]['tests']['passed'] == 1
