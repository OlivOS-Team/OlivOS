"""Publish coverage totals and the largest gaps from coverage.py JSON, without hiding failures."""

import json
import os
import sys
from pathlib import Path


def main():
    path = Path(sys.argv[1])
    if not path.is_file():
        print('Coverage report unavailable; inspect the test step for collection or runtime failures.')
        return 1
    data = json.loads(path.read_text(encoding='utf-8'))
    totals = data['totals']
    lines = totals['covered_lines'] / max(totals['num_statements'], 1) * 100
    branches = totals.get('covered_branches', 0) / max(totals.get('num_branches', 0), 1) * 100
    report = [
        '## Python functional test coverage', '',
        f'Lines: **{lines:.2f}%** ({totals["covered_lines"]}/{totals["num_statements"]}); '
        f'branches: **{branches:.2f}%** '
        f'({totals.get("covered_branches", 0)}/{totals.get("num_branches", 0)}).', '',
        'HTML reports include missing lines, branches and test contexts. '
        'JavaScript behavior is exercised by browser tests; Python coverage does not measure JavaScript.', '',
        '| Module with uncovered lines | Missing lines |', '| --- | ---: |',
    ]
    files = sorted(data['files'].items(), key=lambda item: item[1]['summary']['missing_lines'], reverse=True)
    for name, details in files[:15]:
        report.append(f'| `{name}` | {details["summary"]["missing_lines"]} |')
    text = '\n'.join(report) + '\n'
    print(text)
    destination = os.environ.get('GITHUB_STEP_SUMMARY')
    if destination:
        with open(destination, 'a', encoding='utf-8') as stream:
            stream.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
