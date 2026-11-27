"""Tests for scripts/check-docs.py. Run: python3 -I scripts/tests/test_check_docs.py"""

import contextlib
import io
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def run_full(self, args, env=None):
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT] + list(args),
            capture_output=True, text=True, env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr

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

    # Output must not expose local paths (defect 1). Paths are assembled from
    # parts so that this file does not match the public checks itself.

    def test_link_output_hides_absolute_and_outside_targets(self):
        users = "Us" + "ers"
        cases = (
            ("/" + users + "/someone/secret.md", "is an absolute path"),
            ("D:" + "/work/someone-secret.md", "is an absolute path"),
            ("C:" + "\\" + users + "\\someone\\secret.md", "is an absolute path"),
            ("../../someone-secret.md", "points outside the root"),
            ("sub/" + users + "/someone/x.md", "<redacted> does not exist"),
        )
        for target, message in cases:
            with self.subTest(target=target):
                self.write("docs/status.md", "[x](%s)\n" % target)
                rc, out, err = self.run_full(["--root", self.root, "--no-git"])
                self.assertEqual(rc, 1, out)
                self.assertIn(message, out)
                self.assertNotIn("someone", out + err)

    def test_missing_relative_link_is_still_shown(self):
        self.write("docs/status.md", "[x](missing-page.md)\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 1, out)
        self.assertIn("[link] missing-page.md does not exist", out)

    def test_windows_local_paths_are_detected(self):
        users = "Us" + "ers"
        lower = users.lower()
        bs = "\\"
        cases = (
            "C:" + bs + users + bs + "someone" + bs + "x",
            "C:/" + users + "/someone/x",
            "c:/" + lower + "/someone/x",
            "C:" + bs * 2 + users + bs * 2 + "someone",
            "C:" + bs + users + "/someone",
            "c:/" + lower + bs + "someone",
            "/c/" + lower + "/someone",
            "/c/" + users + "/someone",
            "/mnt/c/" + users + "/someone",
            "\"/d/" + lower + "/someone\"",
        )
        for text in cases:
            with self.subTest(text=text):
                self.write("docs/leak.md", "line\n" + text + "\n")
                rc, out, err = self.run_full(["--root", self.root, "--no-git"])
                self.assertEqual(rc, 1, out)
                self.assertIn("docs/leak.md:2: [public:local-path]", out)
                self.assertNotIn("someone", out + err)

    def test_existing_unix_local_paths_are_still_detected(self):
        cases = (
            "/" + "Users/someone/x",
            "/" + "home/someone/x",
            "/" + "var/folders/ab/someone",
            "/" + "private/tmp/someone",
        )
        for text in cases:
            with self.subTest(text=text):
                self.write("docs/leak.md", text + "\n")
                rc, out, err = self.run_full(["--root", self.root, "--no-git"])
                self.assertEqual(rc, 1, out)
                self.assertIn("[public:local-path]", out)
                self.assertNotIn("someone", out + err)

    def test_api_style_paths_are_not_local_paths(self):
        self.write("docs/api.md", "GET /users/{id}\nPOST /v1/users/1\nhttps://example.com/c/users/1\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 0, out)

    def test_public_findings_do_not_print_matched_value(self):
        self.write("docs/leak.md", "person-private" + "@" + "example.org\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 1, out)
        self.assertIn("[public:email]", out)
        self.assertNotIn("person-private", out + err)

    def test_error_messages_do_not_expose_root_path(self):
        marker = "private-marker-dir"
        missing = os.path.join(self.tmp.name, marker)
        rc, out, err = self.run_full(["--root", missing, "--no-git"])
        self.assertEqual(rc, 2, out)
        self.assertIn("root is not a directory", out)
        self.assertNotIn(marker, out + err)

        os.makedirs(missing)
        env = {"PATH": os.environ.get("PATH", ""), "GIT_CEILING_DIRECTORIES": self.tmp.name}
        if "SYSTEMROOT" in os.environ:
            env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        rc, out, err = self.run_full(["--root", missing], env=env)
        self.assertEqual(rc, 2, out)
        self.assertIn("git ls-files failed (exit", out)
        self.assertNotIn(marker, out + err)

    # Git mode (defect 2). The temporary repository is isolated from the user's
    # global and system git configuration, signing and hooks.

    def git_env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        empty = os.path.join(self.tmp.name, "empty-gitconfig")
        if not os.path.exists(empty):
            open(empty, "w").close()
        env.update({
            "GIT_CONFIG_GLOBAL": empty,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CEILING_DIRECTORIES": self.tmp.name,
        })
        return env

    def git(self, *args, input=None):
        hooks = os.path.join(self.tmp.name, "no-hooks")
        os.makedirs(hooks, exist_ok=True)
        return subprocess.run(
            ["git", "-C", self.root,
             "-c", "user.name=test", "-c", "user.email=test" + "@" + "example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + hooks,
             "-c", "core.autocrlf=false"] + list(args),
            check=True, capture_output=True, env=self.git_env(), input=input,
        ).stdout

    def init_repo(self):
        self.write("docs/extra.md", "# 추가\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def run_git_mode(self):
        return self.run_full(["--root", self.root], env=self.git_env())

    def test_git_mode_committed_files_pass(self):
        self.init_repo()
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("WARN", out)

    def test_git_mode_file_deleted_only_in_working_tree_fails(self):
        self.init_repo()
        os.remove(os.path.join(self.root, "docs", "extra.md"))
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/extra.md: [missing-tracked]", out)

    def test_git_mode_staged_deletion_is_not_missing(self):
        self.init_repo()
        self.git("rm", "-q", "docs/extra.md")
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("[missing-tracked]", out)

    def test_git_mode_untracked_text_file_warns(self):
        self.init_repo()
        self.write("docs/new.md", "# 새 문서\n")
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 0, out + err)
        self.assertIn("WARN: docs/new.md: [untracked]", out)

    def test_git_mode_untracked_warning_hides_sensitive_path(self):
        self.init_repo()
        self.write("docs/" + "Us" + "ers/someone/note.md", "x\n")
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 0, out + err)
        self.assertIn("WARN: <redacted>: [untracked]", out)
        self.assertNotIn("someone", out + err)

    def test_git_mode_required_file_removed_from_index_fails(self):
        self.init_repo()
        self.git("rm", "-q", "--cached", "docs/status.md")
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/status.md: [required] required file is not tracked", out)

    def test_git_mode_required_file_staged_deletion_fails(self):
        self.init_repo()
        self.git("rm", "-q", "docs/status.md")
        self.write("AGENTS.md", "# 규칙\n")
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/status.md: [required] missing required file", out)

    # Fenced code blocks (defect 4).

    DUP_TABLE = "| ID | 내용 |\n| --- | --- |\n| D-O01 | 예시 |\n"

    def test_fenced_block_is_excluded_from_id_and_link_checks(self):
        cases = {
            "backtick": "```\n" + self.DUP_TABLE + "[x](missing.md)\n```\n",
            "tilde": "~~~\n" + self.DUP_TABLE + "[x](missing.md)\n~~~\n",
            "info string": "```text\n" + self.DUP_TABLE + "```\n",
            "indented 3": "   ```\n" + self.DUP_TABLE + "   ```\n",
            "longer close": "```\n" + self.DUP_TABLE + "`````\n",
            "close with trailing spaces": "```\n" + self.DUP_TABLE + "```  \n",
            "shorter fence does not close": "````\n```\n" + self.DUP_TABLE + "````\n",
            "other char does not close": "~~~\n```\n" + self.DUP_TABLE + "~~~\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.write("docs/other.md", "# 예시\n\n" + text)
                rc, out, err = self.run_full(["--root", self.root, "--no-git"])
                self.assertEqual(rc, 0, out)
                self.assertIn("2 identifier definitions", out)

    def test_non_fences_are_still_checked(self):
        cases = {
            "indented 4": "    ```\n" + self.DUP_TABLE + "    ```\n",
            "two backticks": "``\n" + self.DUP_TABLE + "``\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.write("docs/other.md", text)
                rc, out, err = self.run_full(["--root", self.root, "--no-git"])
                self.assertEqual(rc, 1, out)
                self.assertIn("[id-dup] D-O01", out)

    def test_backtick_in_info_string_is_not_a_fence(self):
        self.write("docs/other.md", "``` a`b\n" + self.DUP_TABLE)
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 1, out)
        self.assertIn("[id-dup] D-O01", out)
        self.assertNotIn("[fence]", out)

    def test_public_check_still_scans_fenced_block(self):
        self.write("docs/other.md", "```\n" + "/" + "Users/someone/x\n```\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 1, out)
        self.assertIn("docs/other.md:2: [public:local-path]", out)

    def test_unclosed_fence_fails(self):
        cases = {
            "no close": "# 예시\n```\n" + self.DUP_TABLE,
            "close with text": "```\n" + self.DUP_TABLE + "``` x\n",
            "tilde closed by backticks": "~~~\n" + self.DUP_TABLE + "```\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.write("docs/other.md", text)
                rc, out, err = self.run_full(["--root", self.root, "--no-git"])
                self.assertEqual(rc, 1, out)
                self.assertIn("[fence] code block is not closed", out)

    # Definition location by prefix (defect 3).

    def test_definition_outside_its_home_file_fails(self):
        cases = {
            "D-O99": "docs/other.md",
            "C-99": "docs/other.md",
            "FM-99": "docs/other.md",
            "TH-99": "docs/other.md",
            "S9": "docs/poc/plan.md",
        }
        for ident, rel in cases.items():
            with self.subTest(ident=ident):
                self.write(rel, "| ID | 내용 |\n| --- | --- |\n| %s | 잘못된 위치 |\n" % ident)
                rc, out, err = self.run_full(["--root", self.root, "--no-git"])
                self.assertEqual(rc, 1, out)
                self.assertIn("%s:3: [id-location] %s" % (rel, ident), out)
                os.remove(os.path.join(self.root, rel))

    def test_definition_in_home_file_passes(self):
        self.write("docs/poc/plan.md", "| SC | 내용 |\n| --- | --- |\n| SC-X01 | 시나리오 |\n\n"
                   "| ID | 내용 |\n| --- | --- |\n| FM-01 | 실패 모드 |\n")
        self.write("docs/security/threat-model.md", "| ID | 내용 |\n| --- | --- |\n| S1 | 가정 |\n| TA-1 | 자산 |\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 0, out)
        self.assertIn("6 identifier definitions", out)

    def test_reference_table_in_other_file_is_not_a_definition(self):
        self.write("docs/other.md", "| 요구사항 | 근거 |\n| --- | --- |\n| D-O99 | 참조 |\n| SC-X01 | 참조 |\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 0, out)
        self.assertNotIn("[id-location]", out)

    def test_unlisted_prefix_is_only_checked_for_duplicates(self):
        self.write("docs/other.md", "| ID | 내용 |\n| --- | --- |\n| X-01 | 미지정 접두어 |\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 0, out)
        self.write("docs/more.md", "| ID | 내용 |\n| --- | --- |\n| X-01 | 재정의 |\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 1, out)
        self.assertIn("[id-dup] X-01", out)
        self.assertNotIn("[id-location]", out)

    # Masking of every diagnostic value (review follow-up).

    def run_in_process(self, args, patcher):
        out, err = io.StringIO(), io.StringIO()
        with patcher, mock.patch.object(sys, "argv", [SCRIPT] + list(args)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                runpy.run_path(SCRIPT, run_name="__main__")
        return cm.exception.code, out.getvalue(), err.getvalue()

    def test_file_names_are_masked_in_findings_without_git(self):
        # Both definitions are in masked files, so the result does not depend
        # on the directory walk order.
        users = "Us" + "ers"
        self.write("docs/" + users + "/someone/a.md", self.DUP_TABLE + "| X-01 | 정의 |\n\n[x](missing.md)\n"
                   + "a" + "@" + "example.org\n```\n")
        self.write("docs/" + users + "/someone/b.md", "| ID | 내용 |\n| --- | --- |\n| X-01 | 재정의 |\n")
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 1, out)
        for rule in ("[id-location]", "[id-dup]", "[link]", "[public:email]", "[fence]"):
            self.assertIn(rule, out)
        self.assertRegex(out, r"<redacted>:\d+: \[id-dup\] X-01 already defined at <redacted>:\d+")
        self.assertNotIn("someone", out + err)

    def test_git_mode_missing_tracked_name_is_masked(self):
        rel = "docs/" + "Us" + "ers/someone/n.md"
        self.write(rel, "# x\n")
        self.init_repo()
        os.remove(os.path.join(self.root, *rel.split("/")))
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("<redacted>: [missing-tracked]", out)
        self.assertNotIn("someone", out + err)

    def test_required_value_is_masked(self):
        rc, out, err = self.run_full(
            ["--root", self.root, "--no-git", "--require", "/" + "Users/someone/x.md"])
        self.assertEqual(rc, 1, out)
        self.assertIn("<redacted>: [required]", out)
        self.assertNotIn("someone", out + err)

    def test_argument_errors_do_not_echo_input(self):
        cases = (
            ["--bogus", "/" + "Users/someone/x"],
            ["--root"],
            ["--root", self.root, "someone-extra"],
        )
        for args in cases:
            with self.subTest(args=args):
                rc, out, err = self.run_full(args)
                self.assertEqual(rc, 2, out + err)
                self.assertIn("invalid command-line arguments", err)
                self.assertIn("RESULT: ERROR", err)
                self.assertNotIn("someone", out + err)

    def test_read_error_shows_only_error_type(self):
        real_open = open

        def fake_open(path, *args, **kwargs):
            if str(path).endswith("status.md"):
                raise PermissionError(13, "private-marker", str(path))
            return real_open(path, *args, **kwargs)

        code, out, err = self.run_in_process(
            ["--root", self.root, "--no-git"], mock.patch("builtins.open", fake_open))
        self.assertEqual(code, 2, out)
        self.assertIn("cannot read docs/status.md: PermissionError", out)
        self.assertNotIn("private-marker", out + err)
        self.assertNotIn(self.tmp.name, out + err)

    def test_unexpected_exception_shows_only_type(self):
        boom = RuntimeError("private-marker " + self.root)
        code, out, err = self.run_in_process(
            ["--root", self.root, "--no-git"], mock.patch("os.walk", side_effect=boom))
        self.assertEqual(code, 2, out)
        self.assertIn("ERROR: unexpected RuntimeError", out)
        self.assertIn("RESULT: ERROR", out)
        self.assertNotIn("private-marker", out + err)
        self.assertNotIn(self.tmp.name, out + err)

    # Tracked paths that are no longer regular files (review follow-up).

    def test_git_mode_tracked_file_replaced_by_directory_fails(self):
        self.init_repo()
        path = os.path.join(self.root, "docs", "extra.md")
        os.remove(path)
        os.makedirs(path)
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/extra.md: [not-regular]", out)

    def test_git_mode_tracked_file_replaced_by_symlink_inside_root_fails(self):
        self.init_repo()
        path = os.path.join(self.root, "docs", "extra.md")
        os.remove(path)
        os.symlink("status.md", path)
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/extra.md: [not-regular]", out)

    def test_git_mode_tracked_file_replaced_by_symlink_outside_root_fails(self):
        self.init_repo()
        outside = os.path.join(self.tmp.name, "outside-private-marker.md")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("outside\n")
        path = os.path.join(self.root, "docs", "extra.md")
        os.remove(path)
        os.symlink(outside, path)
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/extra.md: [not-regular]", out)
        self.assertNotIn("private-marker", out + err)

    # Independent review follow-up (F01-F04).

    def test_git_mode_missing_non_text_tracked_file_fails(self):
        self.write(".gitignore", "*.log\n")
        self.init_repo()
        os.remove(os.path.join(self.root, ".gitignore"))
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn(".gitignore: [missing-tracked]", out)

    def test_git_mode_symlink_in_index_fails_without_creating_a_symlink(self):
        self.init_repo()
        self.git("config", "core.symlinks", "false")
        blob = self.git("hash-object", "-w", "--stdin", input=b"status.md").decode("ascii").strip()
        self.git("update-index", "--add", "--cacheinfo", "120000,%s,docs/link.md" % blob)
        # What a core.symlinks=false checkout leaves in the working tree.
        self.write("docs/link.md", "status.md")
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/link.md: [not-regular] tracked path is not a regular file in the git index (mode 120000)", out)

    def test_git_mode_unparsable_ls_files_output_fails_closed(self):
        bad = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"not an index entry\0", stderr=b"")
        code, out, err = self.run_in_process(["--root", self.root], mock.patch("subprocess.run", return_value=bad))
        self.assertEqual(code, 2, out)
        self.assertIn("git ls-files output could not be parsed", out)

    def test_required_path_outside_root_fails_even_if_it_exists(self):
        outside = os.path.join(self.tmp.name, "outside-private-marker.md")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("# outside\n")
        values = ("../outside-private-marker.md", outside)
        for git_mode in (False, True):
            if git_mode:
                self.init_repo()
            for value in values:
                with self.subTest(git_mode=git_mode, value=value):
                    args = ["--root", self.root, "--require", value]
                    if not git_mode:
                        args.append("--no-git")
                    rc, out, err = self.run_full(args, env=self.git_env() if git_mode else None)
                    self.assertEqual(rc, 1, out + err)
                    self.assertIn("<redacted>: [required] required path is outside the root", out)
                    self.assertNotIn("private-marker", out + err)

    def test_git_mode_required_symlink_resolving_outside_fails(self):
        self.init_repo()
        outside = os.path.join(self.tmp.name, "outside-private-marker.md")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("# outside\n")
        os.symlink(outside, os.path.join(self.root, "docs", "req.md"))
        rc, out, err = self.run_full(["--root", self.root, "--require", "docs/req.md"], env=self.git_env())
        self.assertEqual(rc, 1, out + err)
        self.assertIn("<redacted>: [required] required path is outside the root", out)
        self.assertNotIn("private-marker", out + err)

    def test_identifier_matching_public_pattern_is_masked(self):
        ident = "D-" + "CO-" + "AUTHORED-" + "BY1"
        self.write("docs/other.md", "| ID | 내용 |\n| --- | --- |\n| %s | x |\n| %s | y |\n" % (ident, ident))
        rc, out, err = self.run_full(["--root", self.root, "--no-git"])
        self.assertEqual(rc, 1, out)
        self.assertIn("docs/other.md:3: [id-location] <redacted> must be defined in docs/decision-register.md", out)
        self.assertIn("docs/other.md:4: [id-dup] <redacted> already defined at docs/other.md:3", out)
        self.assertNotIn("AUTHORED", out + err)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "os.mkfifo is not available on this platform")
    def test_git_mode_tracked_file_replaced_by_fifo_fails(self):
        self.init_repo()
        path = os.path.join(self.root, "docs", "extra.md")
        os.remove(path)
        os.mkfifo(path)
        rc, out, err = self.run_git_mode()
        self.assertEqual(rc, 1, out + err)
        self.assertIn("docs/extra.md: [not-regular]", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
