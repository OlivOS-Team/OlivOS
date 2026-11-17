# -*- encoding: utf-8 -*-
"""WebUI 展示的版本必须等于打包用的实际版本。"""

import re
from pathlib import Path

import OlivOS


def test_webui_version_matches_project_version():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'pyproject.toml').read_text(encoding='utf-8')
    match = re.search(r'(?m)^version = "([^"]+)"', text)
    assert match is not None
    assert OlivOS.infoAPI.OlivOS_Version == match.group(1)
