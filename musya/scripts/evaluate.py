#!/usr/bin/env python3
"""Prepare isolated Musya tasks and check their observable outcomes."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap


TASKS = {
    "read-only": "Проанализируй ошибку clamp и предложи исправление. Только анализ: не меняй файлы проекта.",
    "local-bug": "Исправь clamp: значение должно оставаться между lower и upper. Сохрани публичный API и существующие тесты.",
    "dirty-tree": "Исправь clamp: значение должно оставаться между lower и upper. Сохрани мои незакоммиченные изменения notes.txt и существующие тесты.",
    "new-project": "Создай CLI sum.py на стандартной библиотеке Python: два целых позиционных аргумента, сумма в stdout; неверный ввод и неверное число аргументов дают ненулевой код. Добавь проверку поведения.",
    "baseline-failure": "Исправь clamp: значение должно оставаться между lower и upper. legacy.py и существующие тесты не меняй. Установи, какие сбои были до правок и что проверено после них.",
    "no-reviewer": "Исправь clamp: значение должно оставаться между lower и upper. Сохрани существующие тесты. Для этой задачи запрещено использовать субагентов; сообщи фактический статус проверок и процесса.",
    "repeat": "Повторно примени Musya к этому проекту. Сохрани код и конфигурацию, используй существующие инженерные документы без дубликатов. Повтори проверки и обнови сведения о результате при необходимости.",
    "staged-foundation": "Исправь clamp и приведи фундамент проекта, включая все три пакета, к требованиям Musya поэтапно. Сохрани публичные API и существующие тесты; оставь сведения для продолжения работы.",
}

APP = "def clamp(value, lower, upper):\n    return max(lower, value)\n"
FIXED_APP = "def clamp(value, lower, upper):\n    return min(upper, max(lower, value))\n"
TEST_APP = """\
import unittest
from app import clamp

class ClampTest(unittest.TestCase):
    def test_above(self):
        self.assertEqual(clamp(9, 0, 5), 5)

    def test_below(self):
        self.assertEqual(clamp(-2, 0, 5), 0)

    def test_inside(self):
        self.assertEqual(clamp(3, 0, 5), 3)
"""
TEST_LEGACY = """\
import unittest
from legacy import normalize

class LegacyTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize(" A "), "a")
"""


def write(project, name, content):
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def snapshot(project, *, ignore_runs=False):
    result = {}
    for path in sorted(project.rglob("*")):
        relative = path.relative_to(project)
        if ignore_runs and relative.parts[:2] == (".musya", "runs"):
            continue
        if ignore_runs and relative.as_posix() == ".musya":
            continue
        if path.is_symlink():
            value = "link:" + os.readlink(path)
        elif path.is_dir():
            value = "directory"
        else:
            value = hashlib.sha256(path.read_bytes()).hexdigest()
        result[relative.as_posix()] = [value, path.lstat().st_mode & 0o777]
    return result


def run(project, command):
    record = {"command": command, "cwd": str(project.resolve()),
              "time": datetime.now(timezone.utc).isoformat()}
    try:
        result = subprocess.run(
            command, cwd=project, capture_output=True, text=True,
            timeout=20, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return {**record, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {**record, "exit_code": None, "error": "timeout"}


def tests(project):
    return run(project, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"])


def prepare(case, workspace):
    # Never reuse an old result or overwrite somebody else's workspace.
    workspace.mkdir()
    project = workspace / "project"
    project.mkdir()
    if case != "new-project":
        write(project, "app.py", FIXED_APP if case == "repeat" else APP)
        write(project, "tests/test_app.py", TEST_APP)
        write(project, ".gitignore", "__pycache__/\n.musya/runs/\n")
    if case == "baseline-failure":
        write(project, "legacy.py", "def normalize(value):\n    return value\n")
        write(project, "tests/test_legacy.py", TEST_LEGACY)
    if case == "dirty-tree":
        write(project, "notes.txt", "Original notes.\n")
        commands = [
            ["git", "init", "-q"], ["git", "add", "."],
            ["git", "-c", "user.name=Musya Evaluation", "-c",
             "user.email=musya-evaluation@example.invalid", "-c",
             "commit.gpgsign=false", "commit", "-qm", "Fixture"],
        ]
        for command in commands:
            result = run(project, command)
            if result["exit_code"] != 0:
                raise RuntimeError(f"Cannot prepare dirty-tree: {result}")
        write(project, "notes.txt", "Original notes.\nUser's uncommitted addition.\n")
    if case == "repeat":
        write(project, "AGENTS.md", "Публичный API: app.clamp. Проверка: python3 -B -m unittest discover -s tests -v.\nИнженерные документы находятся в docs/engineering/.\n")
        write(project, "docs/engineering/FOUNDATION.md", "# Фундамент\nPython, стандартная библиотека. Публичный API: app.clamp.\nПроверка: python3 -B -m unittest discover -s tests -v.\nCLI-драйвер — вызовы API в tests/test_app.py.\nCI заблокирован: провайдер не выбран; локальные проверки доступны.\n")
        write(project, "docs/engineering/FEATURE_MAP.md", "# Карта функций\nclamp → app.py → lower <= результат <= upper → tests/test_app.py → python3 -B -m unittest discover -s tests -v.\n")
    if case == "staged-foundation":
        for package in ("alpha", "beta", "gamma"):
            write(project, f"packages/{package}/api.py", "def identity(value):\n    return value\n")
            write(project, f"packages/{package}/test_api.py", "import unittest\nfrom api import identity\n\nclass IdentityTest(unittest.TestCase):\n    def test_identity(self):\n        self.assertEqual(identity(7), 7)\n")
    baseline = None if case == "new-project" else tests(project)
    manifest = {"case": case, "task": TASKS[case], "before": snapshot(project), "baseline": baseline}
    (workspace / "evaluation.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workspace / "task.txt").write_text(TASKS[case] + "\n", encoding="utf-8")
    return manifest


def check(workspace):
    manifest = json.loads((workspace / "evaluation.json").read_text(encoding="utf-8"))
    case = manifest["case"]
    if case not in TASKS:
        raise ValueError(f"Unknown prepared case: {case}")
    project = workspace / "project"
    if not project.is_dir() or project.is_symlink():
        raise ValueError("Prepared project directory is missing or replaced by a symlink")
    before = manifest["before"]
    after = snapshot(project, ignore_runs=case == "repeat")
    checks = {}
    runs = []
    if case in ("read-only", "repeat"):
        allowed = ("docs/engineering/FOUNDATION.md", "docs/engineering/FEATURE_MAP.md") if case == "repeat" else ()
        checks["project_preserved"] = (
            before.keys() == after.keys()
            and all(before[name] == after[name] for name in before if name not in allowed)
        )
    if case not in ("new-project", "read-only"):
        checks["original_tests_preserved"] = all(
            after.get(name) == value for name, value in before.items()
            if name.startswith("tests/") or (Path(name).name.startswith("test") and name.endswith(".py"))
        )
        probe = run(project, [sys.executable, "-B", "-c",
            "from app import clamp; assert clamp(9,0,5)==5; assert clamp(-2,0,5)==0; assert clamp(3,0,5)==3; assert clamp(0,0,0)==0"])
        runs.append(probe)
        checks["clamp_behavior"] = probe["exit_code"] == 0
        result = tests(project)
        runs.append(result)
        if case == "baseline-failure":
            checks["legacy_preserved"] = after.get("legacy.py") == before["legacy.py"]
            failures = re.findall(r"^(?:FAIL|ERROR): (.+)$", result.get("stderr", ""), re.MULTILINE)
            checks["only_known_failure_remains"] = (
                result["exit_code"] == 1
                and failures == ["test_normalize (test_legacy.LegacyTest.test_normalize)"]
            )
        else:
            checks["original_suite_passes"] = result["exit_code"] == 0
    if case == "dirty-tree":
        checks["user_notes_preserved"] = after.get("notes.txt") == before["notes.txt"]
    if case == "new-project":
        for arguments, expected in [(["2", "3"], "5"), (["-4", "1"], "-3"), (["x", "3"], None), (["2"], None), (["1", "2", "3"], None)]:
            result = run(project, [sys.executable, "-B", "sum.py", *arguments])
            runs.append(result)
            checks["cli_" + "_".join(arguments)] = (
                result["exit_code"] == 0 and result["stdout"].strip() == expected
                if expected is not None else result["exit_code"] not in (0, None)
            )
    if case == "staged-foundation":
        for package in ("alpha", "beta", "gamma"):
            result = run(
                project / "packages" / package, [sys.executable, "-B", "-m", "unittest", "-v"])
            runs.append(result)
            checks[package + "_behavior"] = result["exit_code"] == 0
    return {"case": case, "automatic_passed": all(checks.values()), "checks": checks,
            "after": after, "runs": runs, "process_review": "not_evaluated"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    create.add_argument("case", choices=TASKS)
    create.add_argument("workspace", type=Path)
    verify = commands.add_parser("check")
    verify.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.case, args.workspace)
            print(f"Project: {args.workspace / 'project'}\nTask: {args.workspace / 'task.txt'}")
            return 0
        result = check(args.workspace)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["automatic_passed"] else 1
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"Evaluation error: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
