import subprocess
import sys
import site
from pathlib import Path

excludeList = [
    'pip',
    'setuptools',
    'wheel',
    'nuitka',
    'pyinstaller',
    'webview'
]

includeList = [
    'tkinter'
]


def get_all_site_packages():
    packages = []

    for site_dir in site.getsitepackages():
        site_path = Path(site_dir)
        if site_path.exists():
            for item in site_path.iterdir():
                if item.name in ['__pycache__', '.dist-info', '.egg-info', '.pth']:
                    continue
                if item.is_dir():
                    init_file = item / "__init__.py"
                    if init_file.exists():
                        packages.append(item.name)
                    elif item.suffix == '.py':
                        packages.append(item.stem)

    return packages


def build_with_site_packages():
    print("Scan site-packages Path...")
    print(f"Exclude List {excludeList}")
    print(f"Include List {includeList}")
    packages: 'list[str]' = get_all_site_packages()
    print(f"Found {len(packages)} :")
    packages.extend(includeList)
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
    ]
    cmd.extend([
        "--standalone",
        "--onefile",
        "--output-dir=./dist",
        "--output-filename=OlivOS",
        "--windows-icon-from-ico=./resource/favoricon.ico",
        "--windows-console-mode=attach",
        "--assume-yes-for-downloads",
        "--follow-imports",
        "--follow-stdlib",
        "--enable-plugin=tk-inter",
        "--enable-plugin=pywebview",
        "--low-memory",
        "--jobs=2",
        "--show-scons",
        "--show-progress"
    ])
    for pkg in packages:
        if pkg.lower() not in excludeList:
            print(f"Hit {pkg}")
            cmd.extend([f"--include-package={pkg}"])
        else:
            print(f"Skip {pkg}")
    cmd.extend([
        "main.py"
    ])
    print("\nbuild...")
    subprocess.run(cmd)


if __name__ == "__main__":
    build_with_site_packages()
