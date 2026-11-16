import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "evaluate", Path(__file__).resolve().parents[1] / "scripts/evaluate.py")
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


class EvaluationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="musya-driver-")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name) / "case"

    def prepare(self, case):
        manifest = evaluate.prepare(case, self.workspace)
        self.project = self.workspace / "project"
        return manifest

    def fix(self):
        (self.project / "app.py").write_text(evaluate.FIXED_APP, encoding="utf-8")

    def test_read_only_detects_changed_added_deleted_and_empty_directory(self):
        self.prepare("read-only")
        self.assertTrue(evaluate.check(self.workspace)["automatic_passed"])
        self.fix()
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])
        (self.project / "app.py").write_text(evaluate.APP, encoding="utf-8")
        extra = self.project / "extra"
        extra.mkdir()
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])
        extra.rmdir()
        (self.project / "app.py").unlink()
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])

    def test_existing_workspace_is_never_overwritten(self):
        self.prepare("read-only")
        with self.assertRaises(FileExistsError):
            evaluate.prepare("local-bug", self.workspace)

    def test_unknown_case_cannot_report_success(self):
        self.prepare("read-only")
        manifest = self.workspace / "evaluation.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["case"] = "unknown"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            evaluate.check(self.workspace)

    def test_bug_requires_real_behavior_and_preserved_tests(self):
        for case in ("local-bug", "no-reviewer", "dirty-tree", "staged-foundation"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                self.workspace = Path(directory) / "case"
                manifest = self.prepare(case)
                self.assertEqual(manifest["baseline"]["exit_code"], 1)
                self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])
                self.fix()
                result = evaluate.check(self.workspace)
                self.assertTrue(result["automatic_passed"], result)
                self.assertEqual(result["process_review"], "not_evaluated")
                (self.project / "tests/test_app.py").write_text("", encoding="utf-8")
                self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])

    def test_dirty_user_change_is_preserved(self):
        self.prepare("dirty-tree")
        self.fix()
        (self.project / "notes.txt").write_text("Original notes.\n", encoding="utf-8")
        self.assertFalse(evaluate.check(self.workspace)["checks"]["user_notes_preserved"])

    def test_baseline_failure_is_not_hidden_by_target_fix(self):
        manifest = self.prepare("baseline-failure")
        self.assertIn("FAIL: test_above", manifest["baseline"]["stderr"])
        self.assertIn("FAIL: test_normalize", manifest["baseline"]["stderr"])
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])
        self.fix()
        result = evaluate.check(self.workspace)
        self.assertTrue(result["automatic_passed"], result)
        self.assertEqual(result["runs"][-1]["exit_code"], 1)
        (self.project / "legacy.py").write_text("def normalize(value):\n    return value.strip().lower()\n", encoding="utf-8")
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])

    def test_baseline_rejects_an_additional_failure(self):
        self.prepare("baseline-failure")
        self.fix()
        evaluate.write(self.project, "tests/test_regression.py", "import unittest\nclass NewTest(unittest.TestCase):\n    def test_new_failure(self):\n        self.fail('New regression')\n")
        result = evaluate.check(self.workspace)
        self.assertFalse(result["automatic_passed"])
        self.assertFalse(result["checks"]["only_known_failure_remains"])

    def test_staged_rejects_deleting_package_tests(self):
        self.prepare("staged-foundation")
        self.fix()
        (self.project / "packages/alpha/test_api.py").unlink()
        result = evaluate.check(self.workspace)
        self.assertFalse(result["automatic_passed"])
        self.assertFalse(result["checks"]["original_tests_preserved"])

    def test_repeat_allows_run_artifacts_but_rejects_duplicate_docs(self):
        self.prepare("repeat")
        evaluate.write(self.project, ".musya/runs/run.json", "{}\n")
        self.assertTrue(evaluate.check(self.workspace)["automatic_passed"])
        evaluate.write(self.project, "docs/engineering/FOUNDATION-2.md", "Duplicate\n")
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])

    def test_new_cli_requires_success_and_invalid_input_rejection(self):
        self.prepare("new-project")
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])
        evaluate.write(self.project, "sum.py", """\
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument('a', type=int)
            parser.add_argument('b', type=int)
            args = parser.parse_args()
            print(args.a + args.b)
        """)
        self.assertTrue(evaluate.check(self.workspace)["automatic_passed"])
        evaluate.write(self.project, "sum.py", "print(5)\n")
        self.assertFalse(evaluate.check(self.workspace)["automatic_passed"])


if __name__ == "__main__":
    unittest.main()
