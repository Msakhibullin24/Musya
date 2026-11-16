#!/usr/bin/env python3
"""Check local Markdown links, Python syntax and the evaluation driver."""

from pathlib import Path
import re
import subprocess
import sys


def main():
    package = Path(__file__).resolve().parents[1]
    errors = []
    links = 0
    for path in package.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in link or link.startswith("#"):
                continue
            links += 1
            if not (path.parent / link.split("#", 1)[0]).exists():
                errors.append(f"Broken local link: {path}: {link}")
    for path in package.rglob("*.py"):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            errors.append(str(error))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Local links checked: {links}; Python syntax: OK", flush=True)
    return subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(package / "tests"), "-v"],
        cwd=package,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
