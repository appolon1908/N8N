from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "bootstrap_github_deploy_key.sh"
MANIFEST = ROOT / "config" / "ssh-deploy-key-bootstrap.v1.json"
OFFICIAL_ED25519_KEY = (
    "github.com ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
)


class SshDeployKeyBootstrapSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SCRIPT.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_shell_syntax_and_mode(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        self.assertEqual(0o755, SCRIPT.stat().st_mode & 0o777)

    def test_manifest_remains_source_only_and_unverified(self) -> None:
        self.assertEqual("SOURCE_READY_SERVER_UNVERIFIED", self.manifest["status"])
        self.assertEqual("UNVERIFIED", self.manifest["server_validation"]["status"])
        self.assertTrue(self.manifest["deploy_key"]["read_only"])
        self.assertTrue(self.manifest["deploy_key"]["private_key_generated_on_target"])
        self.assertTrue(self.manifest["deploy_key"]["private_key_export_prohibited"])
        self.assertTrue(all(value is False for value in self.manifest["runtime_effects"].values()))

    def test_deploy_key_is_explicitly_read_only(self) -> None:
        self.assertIn("-F read_only=true", self.text)
        self.assertNotIn("read_only=false", self.text)
        self.assertIn("existing GitHub deploy key has write access", self.text)
        self.assertIn("deploy-key read-only readback failed", self.text)

    def test_private_key_is_not_uploaded_or_printed(self) -> None:
        self.assertIn('-f "key=${PUBLIC_KEY}"', self.text)
        self.assertNotIn('cat "$KEY_PATH"', self.text)
        self.assertNotIn('printf \'%s\\n\' "$PUBLIC_KEY"', self.text)
        self.assertIn("PRIVATE_KEY_EXPORTED=NO", self.text)

    def test_github_host_key_and_ssh_identity_are_fail_closed(self) -> None:
        self.assertIn(
            "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU",
            self.text,
        )
        for fragment in (
            "ssh-keyscan",
            "StrictHostKeyChecking yes",
            "IdentitiesOnly yes",
            "IdentityAgent none",
            "ForwardAgent no",
            'grep -Fq "Hi ${REPOSITORY}!"',
        ):
            self.assertIn(fragment, self.text)

    def test_script_does_not_deploy_or_change_a_checkout(self) -> None:
        lowered = self.text.lower()
        for prohibited in (
            "git clone",
            "git pull",
            "git remote set-url",
            "docker compose up",
            "systemctl restart",
            "kubectl apply",
            "workflow import",
        ):
            self.assertNotIn(prohibited, lowered)
        self.assertIn("git ls-remote", lowered)
        self.assertIn("LIVE_APPLICATION_DEPLOYMENT=NO", self.text)

    @unittest.skipUnless(
        shutil.which("ssh-keygen") and shutil.which("jq"),
        "OpenSSH ssh-keygen and jq are required for the isolated execution test",
    )
    def test_isolated_mocked_bootstrap_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            shims = root / "bin"
            home.mkdir()
            shims.mkdir()
            state = root / "gh-state.json"
            key_path = home / ".ssh" / "n8n_readonly_deploy_ed25519"
            evidence_path = home / ".ssh" / "evidence.json"

            def shim(name: str, body: str) -> None:
                path = shims / name
                path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
                path.chmod(0o755)

            shim(
                "ssh-keyscan",
                f"""\
                #!/usr/bin/env bash
                printf '%s\\n' '{OFFICIAL_ED25519_KEY}'
                """,
            )
            shim(
                "ssh",
                """\
                #!/usr/bin/env bash
                set -Eeuo pipefail
                if [[ " $* " == *" -G "* ]]; then
                  printf 'identitiesonly yes\\n'
                  printf 'stricthostkeychecking true\\n'
                  printf 'identityfile %s\\n' "$KEY_PATH"
                  printf 'userknownhostsfile %s\\n' "$KNOWN_HOSTS_PATH"
                  exit 0
                fi
                printf '%s\\n' \
                  "Hi appolon1908-hue/N8N! You've successfully authenticated, but GitHub does not provide shell access." >&2
                exit 1
                """,
            )
            shim(
                "git",
                """\
                #!/usr/bin/env bash
                set -Eeuo pipefail
                [[ "${1:-}" == "ls-remote" ]]
                printf '%040d\\tHEAD\\n' 1
                """,
            )
            shim(
                "gh",
                """\
                #!/usr/bin/env bash
                set -Eeuo pipefail
                if [[ "${1:-}" == "auth" ]]; then
                  exit 0
                fi
                [[ "${1:-}" == "api" ]]
                if [[ " $* " == *" --method POST "* ]]; then
                  key=''
                  for argument in "$@"; do
                    case "$argument" in
                      key=*) key="${argument#key=}" ;;
                    esac
                  done
                  python3 - "$key" "$FAKE_GH_STATE" <<'PY'
import json
import pathlib
import sys
payload = {
    "id": 123,
    "key": sys.argv[1],
    "read_only": True,
    "enabled": True,
}
pathlib.Path(sys.argv[2]).write_text(
    json.dumps(payload) + "\\n", encoding="utf-8"
)
print(json.dumps(payload))
PY
                  exit 0
                fi
                if [[ " $* " == *"/keys/123"* ]]; then
                  if [[ "${FAKE_DISABLED:-false}" == true ]]; then
                    jq '.enabled = false' "$FAKE_GH_STATE"
                  else
                    cat "$FAKE_GH_STATE"
                  fi
                  exit 0
                fi
                if [[ " $* " == *"keys?per_page=100"* ]]; then
                  if [[ "${FAKE_EXISTING:-false}" == true ]]; then
                    jq '.enabled = false' "$FAKE_GH_STATE"
                  fi
                  exit 0
                fi
                exit 2
                """,
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(home),
                    "PATH": f"{shims}:{environment['PATH']}",
                    "GH_TOKEN": "unit-test-value",
                    "FAKE_GH_STATE": str(state),
                    "KEY_PATH": str(key_path),
                    "KNOWN_HOSTS_PATH": str(home / ".ssh" / "known_hosts.github-n8n"),
                    "EVIDENCE_PATH": str(evidence_path),
                }
            )
            result = subprocess.run(
                ["bash", str(SCRIPT)],
                check=False,
                text=True,
                capture_output=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            for marker in (
                "SSH_DEPLOY_KEY_BOOTSTRAP=PASS",
                "DEPLOY_KEY_MODE=READ_ONLY",
                "SSH_AUTH_IDENTITY=appolon1908-hue/N8N",
                "PRIVATE_KEY_MODE=0600",
                "PUBLIC_KEY_MODE=0644",
                "LIVE_APPLICATION_DEPLOYMENT=NO",
            ):
                self.assertIn(marker, result.stdout)

            self.assertEqual(0o600, key_path.stat().st_mode & 0o777)
            self.assertEqual(0o644, key_path.with_suffix(".pub").stat().st_mode & 0o777)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual("PASS", evidence["status"])
            self.assertTrue(evidence["deploy_key_read_only"])
            self.assertEqual("appolon1908-hue/N8N", evidence["ssh_authenticated_repository"])
            self.assertFalse(evidence["application_deployed"])
            self.assertFalse(evidence["workflow_imported"])

            for existing in (False, True):
                with self.subTest(disabled_existing_key=existing):
                    evidence_path.unlink(missing_ok=True)
                    environment['FAKE_DISABLED'] = 'true'
                    environment['FAKE_EXISTING'] = str(existing).lower()
                    disabled = subprocess.run(
                        ['bash', str(SCRIPT)], capture_output=True, text=True,
                        env=environment, timeout=30,
                    )
                    self.assertNotEqual(disabled.returncode, 0)
                    self.assertIn('deploy key is disabled', disabled.stderr)
                    self.assertNotIn('SSH_DEPLOY_KEY_BOOTSTRAP=PASS', disabled.stdout)
                    self.assertFalse(evidence_path.exists())


if __name__ == "__main__":
    unittest.main()
