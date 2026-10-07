#!/usr/bin/env python3
"""Verify an immutable, independently approved release tuple; never deploy it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
IMAGE_DIGEST = re.compile(
    r"^(?P<name>ghcr\.io/(?P<namespace>appolon1908-hue|codestra)/"
    r"(?P<repository>[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*))"
    r"@sha256:(?P<digest>[0-9a-f]{64})$"
)
CHANGE_ID = re.compile(r"^CHG-[A-Z0-9][A-Z0-9._-]{5,127}$")
ALLOWED_ENDPOINT_STRATEGIES = {
    "verified-custom-variable",
    "verified-custom-node",
    "verified-fixed-private-dns",
}
ALLOWED_CREDENTIAL_STRATEGIES = {
    "verified-n8n-credential",
    "verified-custom-node-credential",
}
ALLOWED_EDITOR_STRATEGIES = {
    "verified-private-admin-network",
    "verified-gateway-oidc-and-native-auth",
}
PLACEHOLDERS = {"", "UNSET", "NOT_APPROVED", "NOT_EVALUATED", "UNKNOWN"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def non_placeholder_sha256(value: Any) -> bool:
    text = str(value or "")
    return bool(SHA256.fullmatch(text)) and set(text) != {"0"}


def non_placeholder_git_sha(value: Any) -> bool:
    text = str(value or "")
    return bool(GIT_SHA.fullmatch(text)) and set(text) != {"0"}


def image_digest(value: Any) -> str | None:
    match = IMAGE_DIGEST.fullmatch(str(value or ""))
    if not match or set(match.group("digest")) == {"0"}:
        return None
    return match.group("digest")


def valid_image_reference(value: Any) -> bool:
    return image_digest(value) is not None


def meaningful_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().upper() not in PLACEHOLDERS


def validate(manifest: dict[str, Any], *, target: str, actual_sha: str) -> list[str]:
    errors: list[str] = []

    if manifest.get("schema_version") != "1.1":
        errors.append("release manifest schema_version must be 1.1")
    if manifest.get("deployment_mode") != "preflight-only":
        errors.append("deployment_mode must be preflight-only in this repository")
    if manifest.get("target") != target:
        errors.append("manifest target does not match requested target")

    source_sha = str(manifest.get("source_sha", ""))
    if not non_placeholder_git_sha(source_sha):
        errors.append("source_sha must be a non-placeholder full Git SHA")
    if not non_placeholder_git_sha(actual_sha):
        errors.append("checked-out repository SHA is invalid")
    elif source_sha != actual_sha:
        errors.append(f"source_sha {source_sha!r} does not match checked-out SHA {actual_sha!r}")

    image = manifest.get("image")
    rollback_release = manifest.get("rollback_release")
    image_sha = image_digest(image)
    rollback_sha = image_digest(rollback_release)
    if image_sha is None:
        errors.append("image must be a non-placeholder immutable digest in an approved GHCR namespace")
    if manifest.get("image_digest_verified") is not True:
        errors.append("image digest verification is not recorded as true")
    if rollback_sha is None:
        errors.append("rollback_release must be a previously approved immutable GHCR digest")
    if image_sha is not None and rollback_sha is not None and image_sha == rollback_sha:
        errors.append("rollback_release digest must differ from the candidate image digest")

    evidence_fields = (
        "sbom_sha256",
        "provenance_sha256",
        "signature_bundle_sha256",
        "vulnerability_report_sha256",
        "backup_restore_evidence_sha256",
        "network_validation_sha256",
        "rollback_evidence_sha256",
    )
    for field in evidence_fields:
        if not non_placeholder_sha256(manifest.get(field)):
            errors.append(f"{field} must be a non-placeholder SHA-256")

    if manifest.get("signature_verified") is not True:
        errors.append("signature verification is not recorded as true")
    if not meaningful_text(manifest.get("signature_identity")):
        errors.append("signature_identity is missing")
    if not meaningful_text(manifest.get("signature_issuer")):
        errors.append("signature_issuer is missing")
    if manifest.get("vulnerability_policy") != "PASS":
        errors.append("vulnerability_policy is not PASS")

    runtime_path = ROOT / "config" / "runtime-paths.json"
    capabilities_path = ROOT / "config" / "capabilities.json"
    n8n_policy_path = ROOT / "config" / "n8n-policy.json"
    expected_digests = {
        "runtime_paths_sha256": digest(runtime_path),
        "capabilities_sha256": digest(capabilities_path),
        "n8n_policy_sha256": digest(n8n_policy_path),
    }
    for field, expected in expected_digests.items():
        if manifest.get(field) != expected:
            errors.append(f"{field} does not match the reviewed file")

    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    if runtime.get("status") != "VERIFIED":
        errors.append("reviewed runtime paths are not VERIFIED")

    n8n_policy = json.loads(n8n_policy_path.read_text(encoding="utf-8"))
    endpoint = n8n_policy.get("endpoint_binding", {})
    credential = n8n_policy.get("credential_binding", {})
    editor = n8n_policy.get("editor_access", {})
    if (
        n8n_policy.get("status") != "VERIFIED"
        or endpoint.get("status") != "VERIFIED"
        or credential.get("status") != "VERIFIED"
        or editor.get("status") != "VERIFIED"
    ):
        errors.append("reviewed n8n endpoint/security/credential/editor policy is not VERIFIED")
    if endpoint.get("production_strategy") not in ALLOWED_ENDPOINT_STRATEGIES:
        errors.append("n8n production endpoint strategy is not approved")
    if credential.get("strategy") not in ALLOWED_CREDENTIAL_STRATEGIES:
        errors.append("n8n credential-binding strategy is not approved")
    if editor.get("strategy") not in ALLOWED_EDITOR_STRATEGIES:
        errors.append("n8n editor-access strategy is not approved")
    if editor.get("publicly_routable") is not False:
        errors.append("n8n editor must not be directly publicly routable")
    if not non_placeholder_sha256(endpoint.get("egress_policy_evidence_sha256")):
        errors.append("n8n endpoint policy lacks egress evidence")
    if not non_placeholder_sha256(credential.get("evidence_sha256")):
        errors.append("n8n credential policy lacks evidence")
    if not non_placeholder_sha256(editor.get("evidence_sha256")):
        errors.append("n8n editor-access policy lacks evidence")
    if not non_placeholder_sha256(editor.get("session_policy_evidence_sha256")):
        errors.append("n8n editor session policy lacks evidence")

    requested_by = manifest.get("requested_by")
    approved_by = manifest.get("approved_by")
    if manifest.get("approval_status") != "APPROVED":
        errors.append("approval_status is not APPROVED")
    if not meaningful_text(requested_by) or not meaningful_text(approved_by):
        errors.append("release requester and approver must be named")
    elif requested_by.strip().casefold() == approved_by.strip().casefold():
        errors.append("release approver must be independent from requester")
    change_id = manifest.get("change_id")
    if not isinstance(change_id, str) or not CHANGE_ID.fullmatch(change_id):
        errors.append("change_id must match CHG-<UPPERCASE-ID>")

    capabilities_document = json.loads(capabilities_path.read_text(encoding="utf-8"))
    if capabilities_document.get("safety_mode") != "SOURCE_ONLY":
        errors.append("release preflight requires safety_mode=SOURCE_ONLY")
    capabilities = capabilities_document.get("capabilities", {})
    if not isinstance(capabilities, dict) or not capabilities:
        errors.append("release preflight capability map is missing")
    else:
        enabled = sorted(name for name, value in capabilities.items() if value is not False)
        if enabled:
            errors.append("preflight scaffold requires all external-effect capabilities false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--target", choices=("staging", "production"), required=True)
    args = parser.parse_args()

    manifest_path = args.path if args.path.is_absolute() else ROOT / args.path
    if not manifest_path.exists():
        print("RELEASE_PREFLIGHT=FAIL")
        print(f"ERROR=release manifest does not exist: {manifest_path}")
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("RELEASE_PREFLIGHT=FAIL")
        print(f"ERROR=release manifest cannot be read: {exc}")
        return 1
    if not isinstance(manifest, dict):
        print("RELEASE_PREFLIGHT=FAIL")
        print("ERROR=release manifest must be a JSON object")
        return 1

    try:
        actual_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print("RELEASE_PREFLIGHT=FAIL")
        print(f"ERROR=checked-out Git SHA cannot be determined: {type(exc).__name__}")
        return 1

    errors = validate(manifest, target=args.target, actual_sha=actual_sha)

    if errors:
        print("RELEASE_PREFLIGHT=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        return 1
    print("RELEASE_PREFLIGHT=PASS")
    print("DEPLOYMENT_PERFORMED=NO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
