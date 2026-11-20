'''Publish coverage totals and the largest gaps from coverage.py JSON, without hiding failures.'''

import json
import os
import sys
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


def main():
    path = Path(sys.argv[1])
    if not path.is_file():
        print('Coverage report unavailable; inspect the test step for collection or runtime failures.')
        return 1
    data = json.loads(path.read_text(encoding='utf-8'))
    totals = data['totals']
    covered_lines = totals['covered_lines']
    num_statements = totals['num_statements']
    covered_branches = totals.get('covered_branches', 0)
    num_branches = totals.get('num_branches', 0)
    lines = covered_lines / max(num_statements, 1) * 100
    branches = covered_branches / max(num_branches, 1) * 100
    report = [
        '## Python functional test coverage', '',
        f'Lines: **{lines:.2f}%** ({covered_lines}/{num_statements}); '
        f'branches: **{branches:.2f}%** ({covered_branches}/{num_branches}).', '',
        'HTML reports include missing lines, branches and test contexts. '
        'JavaScript behavior is exercised by browser tests; Python coverage does not measure JavaScript.', '',
    ]
    module_header = '| Module | Line coverage | Branch coverage | Missing lines | Missing branches |'
    report.extend([module_header, '| --- | ---: | ---: | ---: | ---: |'])
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
    report.extend(['', '| File with uncovered lines | Missing lines |', '| --- | ---: |'])
    files = sorted(data['files'].items(), key=lambda item: item[1]['summary']['missing_lines'], reverse=True)
    for name, details in files[:15]:
        missing_lines = details['summary']['missing_lines']
        report.append(f'| `{name}` | {missing_lines} |')
    report.extend(['', '| File with uncovered branches | Missing branches |', '| --- | ---: |'])
    files = sorted(data['files'].items(), key=lambda item: item[1]['summary']['missing_branches'], reverse=True)
    for name, details in files[:15]:
        missing_branches = details['summary']['missing_branches']
        report.append(f'| `{name}` | {missing_branches} |')
    text = '\n'.join(report) + '\n'
    print(text)
    destination = os.environ.get('GITHUB_STEP_SUMMARY')
    if destination:
        with open(destination, 'a', encoding='utf-8') as stream:
            stream.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
