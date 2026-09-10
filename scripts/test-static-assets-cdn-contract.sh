#!/usr/bin/env bash
set -euo pipefail

workflow=".github/workflows/static-assets-reusable.yml"

if [[ ! -f "$workflow" ]]; then
  echo "Missing workflow: $workflow" >&2
  exit 1
fi

# The upload job runs with ``set -o pipefail``.  A ``find | grep -q`` probe
# returns a false negative for non-empty asset directories because grep closes
# the pipe after the first match and find exits with SIGPIPE.  Keep the probe
# pipeline-free and stop find after the first matching file.
if ! grep -Fq -- 'first_matching_asset="$(find "$ASSET_DIRECTORY" -type f \( "${find_expr[@]:1}" \) -print -quit)"' "$workflow" \
  || ! grep -Fq -- 'if [[ -z "$first_matching_asset" ]]; then' "$workflow"; then
  echo "CDN asset validation must use a pipeline-free first-match probe under pipefail." >&2
  exit 1
fi

if grep -Fq -- 'find "$ASSET_DIRECTORY" -type f \( "${find_expr[@]:1}" \) | grep -q .' "$workflow"; then
  echo "CDN asset validation must not use find | grep -q under pipefail." >&2
  exit 1
fi

mutable_upload="$({
  awk '
    /- name: Upload mutable aliases/ { capture = 1 }
    capture { print }
    /- name: Verify mutable alias R2 metadata/ { exit }
  ' "$workflow"
})"

if grep -Eq '^[[:space:]]+--ignore-times([[:space:]]+\\)?$' <<< "$mutable_upload"; then
  echo "Mutable CDN aliases must not use the R2-incompatible rclone forced-transfer path." >&2
  exit 1
fi

if ! grep -Fq -- '--header-upload "Cache-Control: ${CDN_MUTABLE_CACHE_CONTROL}"' <<< "$mutable_upload"; then
  echo "Mutable CDN aliases must upload the caller-provided Cache-Control header." >&2
  exit 1
fi

if ! grep -Fq -- 'aws s3 cp "${ASSET_DIRECTORY%/}/" "s3://${CDN_BUCKET}/${CDN_PREFIX}/${alias}/"' <<< "$mutable_upload" \
  || ! grep -Fq -- '--recursive' <<< "$mutable_upload" \
  || ! grep -Fq -- '"${aws_inc[@]}"' <<< "$mutable_upload" \
  || ! grep -Fq -- '--cache-control "$CDN_MUTABLE_CACHE_CONTROL"' <<< "$mutable_upload"; then
  echo "Mutable CDN aliases must force a filtered PutObject refresh with Cache-Control." >&2
  exit 1
fi

if ! grep -Fq -- '- name: Verify mutable alias R2 metadata' "$workflow" \
  || ! grep -Fq -- 'aws s3api head-object' "$workflow" \
  || ! grep -Fq -- 'if [[ "$cache_control" != "$CDN_MUTABLE_CACHE_CONTROL" ]]' "$workflow"; then
  echo "Mutable CDN aliases must verify stored Cache-Control metadata directly in R2." >&2
  exit 1
fi

if ! grep -Fq -- 'echo "::error::Unexpected mutable alias Cache-Control' "$workflow"; then
  echo "Public mutable Cache-Control drift must fail the CDN verification." >&2
  exit 1
fi

if grep -Fq -- 'echo "::warning::Unexpected mutable alias Cache-Control' "$workflow"; then
  echo "Public mutable Cache-Control drift must not be warning-only." >&2
  exit 1
fi

immutable_verify_line="$(grep -nF -- '- name: Verify immutable CDN upload' "$workflow" | cut -d: -f1)"
mutable_upload_line="$(grep -nF -- '- name: Upload mutable aliases' "$workflow" | cut -d: -f1)"
if [[ -z "$immutable_verify_line" || -z "$mutable_upload_line" || "$immutable_verify_line" -ge "$mutable_upload_line" ]]; then
  echo "The immutable version must pass public verification before mutable aliases are moved." >&2
  exit 1
fi

if ! grep -Fq -- 'run: &verify_cdn_upload |' "$workflow" \
  || ! grep -Fq -- 'run: *verify_cdn_upload' "$workflow"; then
  echo "Immutable and mutable paths must share the same CDN verification contract." >&2
  exit 1
fi

if ! grep -Fq -- 'representative_assets="$(mktemp)"' "$workflow" \
  || ! grep -Fq -- 'done < "$representative_assets"' "$workflow"; then
  echo "Public verification must sample representative assets instead of probing every object." >&2
  exit 1
fi

if ! grep -Fq -- '--user-agent "AlpinInsight-CDN-Verifier/1.0"' "$workflow" \
  || ! grep -Fq -- 'cf-ray=${cf_ray:-unavailable}' "$workflow" \
  || ! grep -Fq -- 'cf-mitigated=${cf_mitigated:-none}' "$workflow"; then
  echo "Blocked CDN probes must expose stable verifier identity and Cloudflare diagnostics." >&2
  exit 1
fi

if grep -Fq -- '--retry-all-errors' "$workflow"; then
  echo "Deterministic CDN security denials must not be retried as transport failures." >&2
  exit 1
fi

python3 - <<'PY'
import base64
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import textwrap
import unittest


workflow = Path(".github/workflows/static-assets-reusable.yml").read_text()


def anchored_script(name):
    match = re.search(rf"^        run: &{name} \|\n((?:          .*\n|\n)*)", workflow, re.M)
    if match is None:
        raise AssertionError(f"Missing shared shell block: {name}")
    return textwrap.dedent(match.group(1))


PREPARE = anchored_script("prepare_private_git_auth")
COMMAND = anchored_script("run_static_asset_command")
CLEAR = anchored_script("clear_private_git_auth")
VERIFY_CDN = anchored_script("verify_cdn_upload")


class PrivateDependencyAuthContract(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="static-assets-auth-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.global_config = self.home / ".gitconfig"
        self.global_before = (
            '[url "https://stale.invalid/"]\n'
            '    insteadOf = ssh://git@github.com/\n'
            '[http "https://github.com/"]\n'
            '    extraheader = AUTHORIZATION: basic stale\n'
        )
        self.global_config.write_text(self.global_before)
        self.env_file = self.root / "github-env"
        self.env_file.touch()
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("GIT_", "STATIC_ASSETS_", "GITHUB_READ_TOKEN"))
        }
        self.env.update(
            HOME=str(self.home), GITHUB_ENV=str(self.env_file),
            GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="audit.marker", GIT_CONFIG_VALUE_0="inherited",
        )

    def shell(self, script, **extra):
        return subprocess.run(
            ["bash", "-euo", "pipefail", "-c", script],
            cwd=self.root, env=self.env | extra, text=True, capture_output=True, check=False,
        )

    def refresh_env(self):
        for line in self.env_file.read_text().splitlines():
            key, value = line.split("=", 1)
            self.env[key] = value

    def prepare(self):
        token = "fake-read-token-for-offline-tests"
        result = self.shell(PREPARE, GITHUB_READ_TOKEN=token)
        self.assertEqual(result.returncode, 0, result.stderr)
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        self.assertEqual(result.stdout, f"::add-mask::{encoded}\n")
        self.assertNotIn(token, self.env_file.read_text())
        self.refresh_env()
        self.assertEqual(self.env["STATIC_ASSETS_GITHUB_AUTH_HEADER"], f"AUTHORIZATION: basic {encoded}")

    def test_both_jobs_use_optional_auth_and_always_cleanup(self):
        self.assertIn(
            "      github_read_token:\n"
            "        description: Optional read-only token for private GitHub build dependencies.\n"
            "        required: false", workflow,
        )
        self.assertNotIn("ssh_private_key", workflow)
        self.assertNotIn("git config --global", PREPARE + COMMAND + CLEAR)
        for job, command_count in (("assets", 5), ("cdn", 2)):
            with self.subTest(job=job):
                section = workflow.split(f"  {job}:\n", 1)[1]
                if job == "assets":
                    section = section.split("  cdn:\n", 1)[0]
                self.assertEqual(section.count("name: Prepare private GitHub dependency access"), 1)
                self.assertIn("GITHUB_READ_TOKEN: ${{ secrets.github_read_token }}", section)
                self.assertEqual(section.count("STATIC_ASSETS_COMMAND:"), command_count)
                self.assertEqual(section.count("run_static_asset_command"), command_count)
                self.assertIn(
                    "      - name: Clear private GitHub dependency access\n"
                    "        if: ${{ always() }}", section,
                )
                self.assertLess(section.index("Prepare private GitHub"), section.index("Install JavaScript"))
                self.assertGreater(section.index("Clear private GitHub"), section.rindex("STATIC_ASSETS_COMMAND:"))
        commit_step = workflow.split("      - name: Commit generated assets for trusted PR\n", 1)[1]
        commit_step = commit_step.split("      - name:", 1)[0]
        self.assertNotIn("run_static_asset_command", commit_step)
        self.assertNotIn("GIT_CONFIG_", commit_step)

    def test_omitted_secret_preserves_commands_and_git_configuration(self):
        for secret in ({}, {"GITHUB_READ_TOKEN": ""}):
            with self.subTest(secret_supplied=bool(secret)):
                self.assertEqual(self.shell(PREPARE, **secret).returncode, 0)
                self.assertEqual(self.env_file.read_text(), "")
                command = "printf 'unchanged\\n'; git config --get audit.marker"
                before = self.shell('bash -euo pipefail -c "$STATIC_ASSETS_COMMAND"', STATIC_ASSETS_COMMAND=command)
                after = self.shell(COMMAND, STATIC_ASSETS_COMMAND=command)
                self.assertEqual((after.returncode, after.stdout, after.stderr), (before.returncode, before.stdout, before.stderr))
                self.assertEqual(self.shell(CLEAR).returncode, 0)
                self.assertEqual(self.env_file.read_text(), "")
                self.assertEqual(self.global_config.read_text(), self.global_before)

    def test_masked_header_and_ssh_rewrites_are_process_scoped(self):
        self.prepare()
        probe = r'''
import json, os, subprocess
def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout.strip()
print(json.dumps({
    "urls": [git("ls-remote", "--get-url", url) for url in (
        "ssh://git@github.com/alpininsight/insight-ui.git",
        "git@github.com:alpininsight/insight-ui.git",
        "https://github.com/alpininsight/insight-ui.git")],
    "header": git("config", "--get-urlmatch", "http.extraheader", "https://github.com/alpininsight/insight-ui.git"),
    "other_header": git("config", "--get-urlmatch", "http.extraheader", "https://example.com/dependency.git"),
    "helper": git("config", "--get-urlmatch", "credential.helper", "https://github.com/alpininsight/insight-ui.git"),
    "inherited": git("config", "--get", "audit.marker"),
    "count": os.environ["GIT_CONFIG_COUNT"],
    "global": os.environ["GIT_CONFIG_GLOBAL"],
}))
'''
        result = self.shell(COMMAND, STATIC_ASSETS_COMMAND="python3 -c " + shlex.quote(probe))
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(result.stdout)
        self.assertEqual(state["urls"], ["https://github.com/alpininsight/insight-ui.git"] * 3)
        self.assertEqual(state["header"], self.env["STATIC_ASSETS_GITHUB_AUTH_HEADER"])
        self.assertEqual(state["other_header"], "")
        self.assertEqual(state["helper"], "")
        self.assertEqual(state["inherited"], "inherited")
        self.assertEqual(state["count"], "6")
        self.assertEqual(state["global"], "/dev/null")
        self.assertEqual(self.global_config.read_text(), self.global_before)
        # The next runner step, including auto-commit, does not inherit the child exports.
        self.assertEqual(self.shell('printf "%s" "$GIT_CONFIG_COUNT"').stdout, "1")
        self.assertEqual(self.shell("git config --get-urlmatch http.extraheader https://github.com/").stdout.strip(), "AUTHORIZATION: basic stale")
        self.assertEqual(self.shell(CLEAR).returncode, 0)
        self.refresh_env()
        self.assertEqual(self.env["STATIC_ASSETS_GITHUB_AUTH_HEADER"], "")

    def test_failed_command_keeps_exit_status_and_cleanup_works(self):
        self.prepare()
        self.assertEqual(self.shell(COMMAND, STATIC_ASSETS_COMMAND="exit 19").returncode, 19)
        self.assertEqual(self.shell(CLEAR).returncode, 0)
        self.refresh_env()
        self.assertEqual(self.env["STATIC_ASSETS_GITHUB_AUTH_HEADER"], "")
        self.assertEqual(self.global_config.read_text(), self.global_before)

    def test_auth_works_without_inherited_git_environment(self):
        for key in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
            self.env.pop(key)
        self.prepare()
        command = 'printf "%s\\n" "$GIT_CONFIG_COUNT"; git ls-remote --get-url ssh://git@github.com/owner/dependency.git'
        result = self.shell(COMMAND, STATIC_ASSETS_COMMAND=command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "5\nhttps://github.com/owner/dependency.git\n")
        self.assertEqual(self.shell(CLEAR).returncode, 0)
        self.assertEqual(self.global_config.read_text(), self.global_before)

    def test_invalid_inherited_count_fails_without_running_asset_command(self):
        self.prepare()
        result = self.shell(COMMAND, GIT_CONFIG_COUNT="invalid", STATIC_ASSETS_COMMAND="printf should-not-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("should-not-run", result.stdout)
        self.assertEqual(self.shell(CLEAR).returncode, 0)


class CdnVerificationContract(unittest.TestCase):
    def test_shared_verifier_is_valid_bash(self):
        result = subprocess.run(
            ["bash", "-n"], input=VERIFY_CDN, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verifier_keeps_full_r2_check_and_samples_the_public_edge(self):
        self.assertIn('rclone check "$ASSET_DIRECTORY"', VERIFY_CDN)
        self.assertIn('done < "$assets_file"', VERIFY_CDN)
        self.assertIn('done < "$representative_assets"', VERIFY_CDN)
        self.assertEqual(VERIFY_CDN.count("curl --fail"), 1)
        self.assertIn('--header "Origin: $CDN_CORS_VERIFY_ORIGIN"', VERIFY_CDN)
        self.assertNotIn("--retry-all-errors", VERIFY_CDN)

    def test_verifier_reports_cloudflare_block_evidence(self):
        self.assertIn('cf_ray="$(header_value cf-ray)"', VERIFY_CDN)
        self.assertIn('cf_mitigated="$(header_value cf-mitigated)"', VERIFY_CDN)
        self.assertIn("CDN public verification failed", VERIFY_CDN)


unittest.main()
PY

echo "Static assets CDN alias and private dependency auth contracts are enforced."
