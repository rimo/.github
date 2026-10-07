"""Tests for the script embedded in .github/workflows/cloud-run-env-guard.yml.

The workflow is a single self-contained file (an org ruleset runs it in every
repository, so it cannot load a helper from this repository). These tests
extract the embedded Python and exercise it directly.

Run: python3 -m unittest discover -s tests -v

The flag names are assembled at runtime (see flag()) so that this file does not
trip the guard when it is changed in a pull request.
"""

import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "cloud-run-env-guard.yml"
HEREDOC_OPEN = "python3 - <<'PY'"


def embedded_source():
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == HEREDOC_OPEN), None)
    assert start is not None, "%s not found in %s" % (HEREDOC_OPEN, WORKFLOW)
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for line in lines[start + 1:]:
        if line.strip() == "PY" and len(line) - len(line.lstrip()) == indent:
            break
        body.append(line[indent:] if line.strip() else "")
    else:
        raise AssertionError("the heredoc is not closed")
    return "\n".join(body) + "\n"


def load_guard():
    module = types.ModuleType("cloud_run_env_guard")
    exec(compile(embedded_source(), str(WORKFLOW), "exec"), module.__dict__)
    return module


def flag(verb, kind):
    return "--" + verb + "-" + kind


def replace_cmd(resource):
    return "gcloud run " + resource + " " + "replace"


def diff(path, added, start=1):
    header = [
        "diff --git a/%s b/%s" % (path, path),
        "--- a/%s" % path,
        "+++ b/%s" % path,
        "@@ -0,0 +%d,%d @@" % (start, len(added)),
    ]
    return "\n".join(header + ["+" + line for line in added]) + "\n"


class ScanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = load_guard()

    def findings(self, text, files=None, warnings=None):
        read_file = None if files is None else files.get
        return [(f.path, f.line, f.rule) for f in self.guard.scan(text, read_file, warnings)]

    def test_every_env_and_secret_flag_is_reported(self):
        flags = [flag(verb, kind) for verb in ("set", "update", "remove", "clear") for kind in ("env-vars", "secrets")]
        flags.append("--env-vars" + "-file")
        for name in flags:
            with self.subTest(flag=name):
                text = diff(".github/workflows/deploy.yml", ['  gcloud run deploy svc %s "A=b"' % name])
                self.assertEqual(self.findings(text), [(".github/workflows/deploy.yml", 1, "env-flag")])

    def test_flag_with_equals_form_is_reported(self):
        text = diff("deploy.sh", ["gcloud run services update svc %s=A=b" % flag("update", "env-vars")])
        self.assertEqual(self.findings(text), [("deploy.sh", 1, "env-flag")])

    def test_image_only_deploy_is_not_reported(self):
        text = diff(
            ".github/workflows/deploy.yml",
            [
                'gcloud run deploy svc --image "$IMAGE" --region "$REGION"',
                'gcloud run services update svc --image "$IMAGE"',
                'gcloud run jobs update job --image "$IMAGE"',
            ],
        )
        self.assertEqual(self.findings(text), [])

    def test_replace_of_a_service_or_job_is_reported(self):
        for command in (replace_cmd("services"), replace_cmd("jobs"), replace_cmd("services").replace("gcloud run", "gcloud beta run")):
            with self.subTest(command=command):
                text = diff("tools/deploy.sh", [command + " /tmp/service.yaml"])
                self.assertEqual(self.findings(text), [("tools/deploy.sh", 1, "replace")])

    def test_removed_and_context_lines_are_ignored(self):
        text = "\n".join(
            [
                "diff --git a/deploy.sh b/deploy.sh",
                "--- a/deploy.sh",
                "+++ b/deploy.sh",
                "@@ -3,2 +3,2 @@",
                " gcloud run deploy svc %s A=b" % flag("set", "env-vars"),
                "-  %s A=b" % flag("update", "secrets"),
                "+  --image img",
            ]
        ) + "\n"
        self.assertEqual(self.findings(text), [])

    def test_line_numbers_follow_the_hunk_header(self):
        text = diff("deploy.sh", ["echo start", "gcloud run deploy svc %s A=b" % flag("set", "env-vars")], start=41)
        self.assertEqual(self.findings(text), [("deploy.sh", 42, "env-flag")])

    def test_second_hunk_and_second_file_are_tracked(self):
        text = (
            diff("a.sh", ["echo ok"], start=1)
            + "@@ -9,0 +10,1 @@\n+" + replace_cmd("jobs") + " job.yaml\n"
            + diff("b.sh", ["x %s K=v" % flag("set", "secrets")], start=7)
        )
        self.assertEqual(self.findings(text), [("a.sh", 10, "replace"), ("b.sh", 7, "env-flag")])

    def test_documentation_is_skipped(self):
        line = "gcloud run deploy svc %s A=b" % flag("set", "env-vars")
        for path in ("README.md", "docs/deploy.yaml", "service/docs/howto.sh", "notes.txt", "guide.mdx"):
            with self.subTest(path=path):
                self.assertEqual(self.findings(diff(path, [line])), [])

    def test_deleted_file_does_not_crash(self):
        text = "\n".join(
            [
                "diff --git a/old.sh b/old.sh",
                "deleted file mode 100755",
                "--- a/old.sh",
                "+++ /dev/null",
                "@@ -1,1 +0,0 @@",
                "-gcloud run deploy svc %s A=b" % flag("set", "env-vars"),
            ]
        ) + "\n"
        self.assertEqual(self.findings(text), [])

    def test_execution_override_is_not_reported(self):
        text = diff(
            ".github/workflows/run.yml",
            [
                'gcloud run jobs execute "$JOB" \\',
                '  %s "RUN_URL=$URL" \\' % flag("update", "env-vars"),
                "  --async",
            ],
        )
        self.assertEqual(self.findings(text), [])

    def test_flag_on_a_continued_update_command_is_reported_at_its_own_line(self):
        text = diff(
            ".github/workflows/deploy.yml",
            [
                'gcloud run jobs update "$JOB" \\',
                '  --image "$IMAGE" \\',
                '  %s "A=b"' % flag("update", "env-vars"),
            ],
            start=20,
        )
        self.assertEqual(self.findings(text), [(".github/workflows/deploy.yml", 22, "env-flag")])

    def test_replace_split_over_continued_lines_is_reported_at_the_first_line(self):
        text = diff("deploy.sh", ["gcloud run services \\", "  " + "replace" + " service.yaml"], start=5)
        self.assertEqual(self.findings(text), [("deploy.sh", 5, "replace")])

    def test_comment_lines_are_ignored(self):
        text = diff(
            ".github/workflows/deploy.yml",
            [
                "# this deploy no longer passes %s" % flag("set", "env-vars"),
                "          # " + replace_cmd("services") + " is done by the preview workflow",
            ],
        )
        self.assertEqual(self.findings(text), [])

    def workflow_with_step(self, uses, key_line, value_line="            A=b"):
        lines = [
            "jobs:",
            "  deploy:",
            "    steps:",
            "      - uses: actions/checkout@v4",
            "      - name: Deploy",
            "        uses: " + uses,
            "        with:",
            "          service: example",
            "          " + key_line,
            value_line,
            "      - run: echo done",
        ]
        return "\n".join(lines) + "\n", 9

    def test_env_inputs_of_the_cloud_run_deploy_action_are_reported(self):
        path = ".github/workflows/deploy.yml"
        for key_line in ("env" + "_vars: |", "secrets: |", "metadata: service.yaml"):
            with self.subTest(key=key_line):
                content, line = self.workflow_with_step("google-github-actions/deploy-cloudrun@v2", key_line)
                text = diff(path, ["          " + key_line], start=line)
                self.assertEqual(self.findings(text, {path: content}), [(path, line, "action-input")])

    def test_same_keys_of_other_actions_are_not_reported(self):
        path = ".github/workflows/build.yml"
        cases = [
            ("docker/build-push-action@v6", "secrets: |"),
            ("google-github-actions/deploy-cloud-functions@v3", "env" + "_vars: |"),
            ("some/other-action@v1", "metadata: x.yaml"),
        ]
        for uses, key_line in cases:
            with self.subTest(uses=uses):
                content, line = self.workflow_with_step(uses, key_line)
                text = diff(path, ["          " + key_line], start=line)
                self.assertEqual(self.findings(text, {path: content}), [])

    def test_job_level_secrets_of_a_reusable_workflow_call_are_not_reported(self):
        path = ".github/workflows/call.yml"
        content = "\n".join(
            [
                "jobs:",
                "  deploy:",
                "    uses: ./.github/workflows/deploy.yml",
                "    secrets: inherit",
                "  other:",
                "    uses: ./.github/workflows/deploy.yml",
                "    secrets:",
                "      TOKEN: x",
            ]
        ) + "\n"
        text = diff(path, ["    secrets: inherit"], start=4) + "@@ -6,0 +7,1 @@\n+    secrets:\n"
        self.assertEqual(self.findings(text, {path: content}), [])

    def test_action_inputs_outside_dot_github_are_not_reported(self):
        content, line = self.workflow_with_step("google-github-actions/deploy-cloudrun@v2", "secrets: |")
        text = diff("config/pipeline.yml", ["          secrets: |"], start=line)
        self.assertEqual(self.findings(text, {"config/pipeline.yml": content}), [])

    def test_without_the_file_only_the_unambiguous_input_is_reported(self):
        path = ".github/workflows/deploy.yml"
        self.assertEqual(
            self.findings(diff(path, ["          %s: |" % ("env" + "_vars")])), [(path, 1, "action-input")]
        )
        self.assertEqual(self.findings(diff(path, ["          secrets: |"])), [])

    def test_execution_exclusion_needs_a_pure_execute_command(self):
        update = "gcloud run jobs update job %s A=b" % flag("update", "env-vars")
        cases = {
            "comment mentions execute": (["# see: gcloud run jobs execute \\", update], 2),
            "chained after execute": (["gcloud run jobs execute job && " + update], 1),
            "trailing comment": ([update + "  # like jobs execute"], 1),
            "execute chained on the next line": ([update + " \\", "  && gcloud run jobs execute job"], 1),
        }
        for name, (added, line) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.findings(diff("run.sh", added)), [("run.sh", line, "env-flag")])

    def test_added_or_removed_content_that_looks_like_a_file_header_is_not_a_header(self):
        text = "\n".join(
            [
                "diff --git a/deploy.sh b/deploy.sh",
                "--- a/deploy.sh",
                "+++ b/deploy.sh",
                "@@ -1,1 +1,3 @@",
                "--- old banner",
                "+++ new banner",
                "+gcloud run deploy svc %s A=b" % flag("set", "env-vars"),
                "+echo done",
            ]
        ) + "\n"
        self.assertEqual(self.findings(text), [("deploy.sh", 2, "env-flag")])

    def test_quoted_path_is_reported_as_unchecked(self):
        text = "\n".join(
            [
                'diff --git "a/de\\tploy.sh" "b/de\\tploy.sh"',
                '--- "a/de\\tploy.sh"',
                '+++ "b/de\\tploy.sh"',
                "@@ -0,0 +1,1 @@",
                "+gcloud run deploy svc %s A=b" % flag("set", "env-vars"),
            ]
        ) + "\n"
        warnings = []
        self.assertEqual(self.findings(text, warnings=warnings), [])
        self.assertEqual(len(warnings), 1)

    def test_the_workflow_does_not_report_itself(self):
        added = WORKFLOW.read_text(encoding="utf-8").splitlines()
        self.assertEqual(self.findings(diff(".github/workflows/cloud-run-env-guard.yml", added)), [])


class DecideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = load_guard()

    def finding(self):
        return self.guard.Finding("deploy.sh", 3, "env-flag")

    def test_no_findings_passes(self):
        self.assertEqual(self.guard.decide([], []), 0)

    def test_findings_fail_without_the_label(self):
        self.assertEqual(self.guard.decide([self.finding()], ["bug"]), 1)

    def test_findings_pass_with_the_label(self):
        self.assertEqual(self.guard.decide([self.finding()], ["bug", self.guard.OVERRIDE_LABEL]), 0)

    def test_unknown_labels_fail(self):
        self.assertEqual(self.guard.decide([self.finding()], None), 1)


class EndToEndTest(unittest.TestCase):
    """Runs the embedded script the way the workflow does (python3 - <<PY) in a scratch git repo.

    actions/checkout gives a pull request's merge commit, so the script diffs HEAD against
    its first parent. Without a merge commit it falls back to BASE_SHA...HEAD_SHA.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")
        self.write("deploy.sh", 'gcloud run deploy svc --image "$IMAGE"\n')
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    def write(self, name, content):
        (self.repo / name).write_text(content, encoding="utf-8")

    def pull_request(self, name, content, merge=True):
        """Commits a change on a branch; with merge=True leaves HEAD on the merge commit."""
        self.git("switch", "-q", "-c", "feature")
        self.write(name, content)
        self.git("add", ".")
        self.git("commit", "-q", "-m", "change")
        head = self.git("rev-parse", "HEAD")
        if merge:
            self.git("switch", "-q", "main")
            self.write("unrelated.txt", "base moved on\n")
            self.git("add", ".")
            self.git("commit", "-q", "-m", "base moved on")
            self.git("merge", "-q", "--no-ff", "-m", "merge", "feature")
        return head

    def run_guard(self, base=None, head=None):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GITHUB_")}
        for key in ("PR_NUMBER", "BASE_SHA", "HEAD_SHA"):
            env.pop(key, None)
        if base:
            env.update({"BASE_SHA": base, "HEAD_SHA": head})
        return subprocess.run(
            [sys.executable, "-"], input=embedded_source(), cwd=self.repo, env=env, capture_output=True, text=True
        )

    def test_clean_change_passes(self):
        self.pull_request("deploy.sh", 'gcloud run deploy svc --image "$IMAGE" --region asia-northeast1\n')
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("::error", result.stdout)
        self.assertNotIn("::warning", result.stdout)

    def test_added_flag_fails_and_does_not_print_the_line(self):
        secret_looking = "TOKEN=do-not-print-me"
        self.pull_request("deploy.sh", 'gcloud run deploy svc --image "$IMAGE" %s %s\n' % (flag("set", "env-vars"), secret_looking))
        result = self.run_guard()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("::error file=deploy.sh,line=1", result.stdout)
        self.assertNotIn("do-not-print-me", result.stdout + result.stderr)

    def test_change_made_only_on_the_base_branch_is_not_reported(self):
        self.pull_request("other.sh", "echo ok\n", merge=False)
        self.git("switch", "-q", "main")
        self.write("base.sh", "gcloud run deploy svc %s A=b\n" % flag("set", "env-vars"))
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base adds a flag")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "feature")
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_non_ascii_file_name_is_checked(self):
        self.pull_request("デプロイ.sh", "gcloud run deploy svc %s A=b\n" % flag("set", "env-vars"))
        result = self.run_guard()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_action_input_is_resolved_from_the_file(self):
        workflow = "\n".join(
            [
                "jobs:",
                "  deploy:",
                "    steps:",
                "      - uses: google-github-actions/deploy-cloudrun@v2",
                "        with:",
                "          service: example",
                "          secrets: |",
                "            KEY=name:latest",
                "      - uses: docker/build-push-action@v6",
                "        with:",
                "          secrets: |",
                "            token=abc",
            ]
        ) + "\n"
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        self.pull_request(".github/workflows/deploy.yml", workflow)
        result = self.run_guard()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("line=7", result.stdout)
        self.assertNotIn("line=11", result.stdout)

    def test_without_a_merge_commit_it_uses_the_given_revisions(self):
        head = self.pull_request("deploy.sh", "gcloud run deploy svc %s A=b\n" % flag("set", "env-vars"), merge=False)
        result = self.run_guard(self.base, head)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_internal_error_does_not_block(self):
        self.pull_request("deploy.sh", "echo ok\n", merge=False)
        result = self.run_guard("0" * 40, "1" * 40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("::warning", result.stdout)


if __name__ == "__main__":
    unittest.main()
