"""Tests for scripts/check-docs.py. Run: python3 -I scripts/tests/test_check_docs.py"""

import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "check-docs.py")

REGISTER = """# 대장

| ID | 결정 |
| --- | --- |
| D-O01 | 첫 결정 |
| D-O02 | 둘째 결정. D-O01을 참조한다 |

| 요구사항 | 근거 |
| --- | --- |
| D-O01 | 참조 표의 첫 칸은 정의가 아니다 |
"""


class CheckDocsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "repo")
        os.makedirs(os.path.join(self.root, "docs"))
        self.write("AGENTS.md", "# 규칙\n\n[상태](docs/status.md)\n")
        self.write("README.md", "# 저장소\n\n[대장](docs/decision-register.md#표기)\n[외부](https://example.com/x)\n")
        self.write("docs/status.md", "# 상태\n\n[대장](decision-register.md)\n")
        self.write("docs/decision-register.md", REGISTER)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def run_check(self, *extra):
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT, "--root", self.root, "--no-git"] + list(extra),
            capture_output=True, text=True,
        )
        return proc.returncode, proc.stdout

    def test_valid_documents_pass(self):
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)
        self.assertIn("2 identifier definitions", out)

    def test_reference_in_other_table_is_not_duplicate(self):
        rc, out = self.run_check()
        self.assertNotIn("[id-dup]", out)

    def test_duplicate_definition_fails(self):
        self.write("docs/other.md", "| ID | 내용 |\n| --- | --- |\n| D-O02 | 같은 식별자 재정의 |\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("[id-dup] D-O02", out)

    def test_duplicate_definition_in_same_file_fails(self):
        self.write("docs/decision-register.md", REGISTER + "\n| ID | 결정 |\n| --- | --- |\n| D-O01 | 재사용 |\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("[id-dup] D-O01", out)

    def test_missing_link_fails(self):
        self.write("docs/status.md", "[없음](missing.md)\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("[link] missing.md does not exist", out)

    def test_link_outside_root_fails_without_following(self):
        self.write("docs/status.md", "[밖](../../outside.md)\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("points outside the root", out)

    def test_symlinked_file_outside_root_is_error(self):
        outside = os.path.join(self.tmp.name, "outside.md")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("outside\n")
        os.symlink(outside, os.path.join(self.root, "docs", "link.md"))
        rc, out = self.run_check()
        self.assertEqual(rc, 2, out)
        self.assertIn("resolves outside the root", out)

    def test_missing_required_file_fails(self):
        os.remove(os.path.join(self.root, "docs", "status.md"))
        self.write("AGENTS.md", "# 규칙\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 1, out)
        self.assertIn("docs/status.md: [required]", out)

    def test_public_information_fails(self):
        cases = {
            "local-path": "/" + "Users/someone/project",
            "email": "person" + "@" + "example.org",
            "co-author": "Co-" + "Authored-By: bot",
            "generated-by": "Generated " + "with tool",
            "session-link": "https://" + "claude" + ".ai/code/session",
        }
        for rule, text in cases.items():
            with self.subTest(rule=rule):
                self.write("docs/leak.md", "line\n" + text + "\n")
                rc, out = self.run_check()
                self.assertEqual(rc, 1, out)
                self.assertIn("docs/leak.md:2: [public:%s]" % rule, out)

    def test_tool_name_as_fact_is_allowed(self):
        self.write("docs/review.md", "AI 리뷰 후보: Claude 기반 Actions, CodeRabbit\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)

    def test_root_not_directory_is_error(self):
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT, "--root", os.path.join(self.root, "nope"), "--no-git"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("RESULT: ERROR", proc.stdout)

    def test_git_mode_outside_repository_is_error(self):
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT, "--root", self.root],
            capture_output=True, text=True,
            env={"PATH": os.environ.get("PATH", ""), "GIT_CEILING_DIRECTORIES": self.tmp.name},
        )
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("git ls-files failed", proc.stdout)

    def test_unreadable_encoding_is_error(self):
        with open(os.path.join(self.root, "docs", "bad.md"), "wb") as f:
            f.write(b"\xff\xfe\x00broken")
        rc, out = self.run_check()
        self.assertEqual(rc, 2, out)
        self.assertIn("cannot read docs/bad.md", out)

    def test_no_definitions_is_error(self):
        self.write("docs/decision-register.md", "# 비어 있음\n")
        rc, out = self.run_check()
        self.assertEqual(rc, 2, out)
        self.assertIn("no identifier definitions found", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
