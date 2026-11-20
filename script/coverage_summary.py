'''从 coverage.py JSON 与 JUnit XML 输出测试结果和覆盖率汇总，不隐藏失败。'''

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _module_name(name):
    parts = name.replace('\\', '/').split('/')
    # 仓库根目录下的 hook/__init__ 文件不应各自形成一行，统一归入 root。
    if len(parts) > 2 and parts[1]:
        return parts[1]
    return 'root'


def _module_totals(files):
    modules = {}
    for name, details in files.items():
        summary = details['summary']
        module = modules.setdefault(
            _module_name(name),
            {
                'covered_lines': 0,
                'num_statements': 0,
                'covered_branches': 0,
                'num_branches': 0,
                'missing_lines': 0,
                'missing_branches': 0,
            },
        )
        for field in module:
            module[field] += summary.get(field, 0)
    return modules


def _write_stdout(text):
    '''输出中文摘要；本地编码无法表示时回退到 UTF-8，兼容 Windows CI 的 cp1252。'''
    try:
        print(text)
    except UnicodeEncodeError:
        reconfigure = getattr(sys.stdout, 'reconfigure', None)
        if reconfigure is None:
            raise
        reconfigure(encoding='utf-8')
        print(text)


def _markdown_cell(value, limit=200):
    text = ' '.join(str(value or '').split()).replace('|', '\\|')
    if len(text) > limit:
        text = text[:limit - 1] + '…'
    return text or '-'


def _count_junit_cases(root):
    total = 0
    failures = 0
    errors = 0
    skipped = 0
    duration = 0.0
    for case in root.iter('testcase'):
        total += 1
        try:
            duration += float(case.get('time') or 0)
        except ValueError:
            pass
        if case.find('failure') is not None:
            failures += 1
        elif case.find('error') is not None:
            errors += 1
        elif case.find('skipped') is not None:
            skipped += 1
    return {
        'total': total,
        'passed': max(total - failures - errors - skipped, 0),
        'failures': failures,
        'errors': errors,
        'skipped': skipped,
        'duration': duration,
    }


def _junit_summary(path):
    if path is None or not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    suites = [root] if root.tag == 'testsuite' else root.findall('.//testsuite')
    if suites and all(suite.get('tests') is not None for suite in suites):
        def total_of(field):
            return sum(int(suite.get(field) or 0) for suite in suites)

        total = total_of('tests')
        failures = total_of('failures')
        errors = total_of('errors')
        skipped = total_of('skipped')
        duration = 0.0
        for suite in suites:
            try:
                duration += float(suite.get('time') or 0)
            except ValueError:
                pass
        summary = {
            'total': total,
            'passed': max(total - failures - errors - skipped, 0),
            'failures': failures,
            'errors': errors,
            'skipped': skipped,
            'duration': duration,
        }
    else:
        summary = _count_junit_cases(root)
    failed_cases = []
    for case in root.iter('testcase'):
        failure = case.find('failure')
        error = case.find('error')
        detail = error if error is not None else failure
        if detail is None:
            continue
        classname = case.get('classname') or ''
        name = case.get('name') or 'unknown'
        identifier = f'{classname}::{name}' if classname else name
        message = detail.get('message') or (detail.text or '').strip()
        failed_cases.append((identifier, '错误' if error is not None else '失败', message))
    summary['failed_cases'] = failed_cases
    return summary


def _test_section(summary):
    if summary is None:
        return ['JUnit 报告不可用；请检查测试步骤中的收集或运行失败。']
    report = [
        '| 总数 | 通过 | 失败 | 错误 | 跳过 | 耗时 |',
        '| ---: | ---: | ---: | ---: | ---: | ---: |',
        '| {} | {} | {} | {} | {} | {:.2f} 秒 |'.format(
            summary['total'], summary['passed'], summary['failures'],
            summary['errors'], summary['skipped'], summary['duration'],
        ),
    ]
    failed_cases = summary['failed_cases']
    if failed_cases:
        report.extend(['', '| 失败或错误用例 | 结果 | 摘要 |', '| --- | --- | --- |'])
        for identifier, outcome, message in failed_cases[:20]:
            report.append(
                f'| `{_markdown_cell(identifier)}` | {outcome} | {_markdown_cell(message)} |'
            )
        if len(failed_cases) > 20:
            report.extend(['', f'另有 {len(failed_cases) - 20} 条失败或错误，请在 JUnit 报告或日志中查看。'])
    return report


def _coverage_section(data):
    totals = data['totals']
    covered_lines = totals['covered_lines']
    num_statements = totals['num_statements']
    covered_branches = totals.get('covered_branches', 0)
    num_branches = totals.get('num_branches', 0)
    lines = covered_lines / max(num_statements, 1) * 100
    branches = covered_branches / max(num_branches, 1) * 100
    report = [
        f'行：**{lines:.2f}%** ({covered_lines}/{num_statements})；'
        f'分支：**{branches:.2f}%** ({covered_branches}/{num_branches})。', '',
        'HTML 报告包含未覆盖行、分支与测试上下文。'
        'JavaScript 行为由浏览器测试覆盖；Python 覆盖率不计量 JavaScript。', '',
        '| 模块 | 行覆盖率 | 分支覆盖率 | 未覆盖行 | 未覆盖分支 |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    modules = _module_totals(data['files'])
    ordered_modules = sorted(modules.items(), key=lambda item: item[1]['missing_lines'], reverse=True)
    for name, summary in ordered_modules:
        line_ratio = summary['covered_lines'] / max(summary['num_statements'], 1) * 100
        branch_ratio = summary['covered_branches'] / max(summary['num_branches'], 1) * 100
        missing_lines = summary['missing_lines']
        missing_branches = summary['missing_branches']
        report.append(
            f'| `{name}` | {line_ratio:.2f}% | {branch_ratio:.2f}% | '
            f'{missing_lines} | {missing_branches} |'
        )
    report.extend(['', '| 未覆盖行较多的文件 | 未覆盖行 |', '| --- | ---: |'])
    files = sorted(data['files'].items(), key=lambda item: item[1]['summary']['missing_lines'], reverse=True)
    for name, details in files[:15]:
        missing_lines = details['summary']['missing_lines']
        report.append(f'| `{name}` | {missing_lines} |')
    report.extend(['', '| 未覆盖分支较多的文件 | 未覆盖分支 |', '| --- | ---: |'])
    files = sorted(data['files'].items(), key=lambda item: item[1]['summary']['missing_branches'], reverse=True)
    for name, details in files[:15]:
        missing_branches = details['summary']['missing_branches']
        report.append(f'| `{name}` | {missing_branches} |')
    return report


def _load_coverage(path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def build_report(coverage_path, junit_path=None):
    coverage_path = Path(coverage_path)
    if junit_path is None:
        junit_path = coverage_path.with_name('junit.xml')
    data = _load_coverage(coverage_path)
    report = ['## Python 功能测试与覆盖率', '', '### 测试执行结果', '']
    report.extend(_test_section(_junit_summary(Path(junit_path))))
    report.extend(['', '### 覆盖率', ''])
    if data is None:
        report.append('覆盖率报告不可用；请检查测试步骤中的收集或运行失败。')
    else:
        report.extend(_coverage_section(data))
    return '\n'.join(report) + '\n', data is not None


def main():
    coverage_path = Path(sys.argv[1])
    junit_path = Path(sys.argv[2]) if len(sys.argv) > 2 else coverage_path.with_name('junit.xml')
    text, coverage_available = build_report(coverage_path, junit_path)
    _write_stdout(text)
    destination = os.environ.get('GITHUB_STEP_SUMMARY')
    if destination:
        with open(destination, 'a', encoding='utf-8') as stream:
            stream.write(text)
    return 0 if coverage_available else 1


if __name__ == '__main__':
    raise SystemExit(main())
