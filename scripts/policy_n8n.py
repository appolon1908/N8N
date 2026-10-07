"""Fail-closed validation of the reviewed n8n security and binding policy."""

from __future__ import annotations

import re
from typing import Any

try:
    from .policy_common import (
        meaningful_identity,
        non_placeholder_sha256,
        string_set,
        valid_https_base,
        valid_iso8601,
    )
except ImportError:  # Direct script execution through sibling entry points.
    from policy_common import (  # type: ignore
        meaningful_identity,
        non_placeholder_sha256,
        string_set,
        valid_https_base,
        valid_iso8601,
    )

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
REQUIRED_DANGEROUS_NODES = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.executeCommand",
    "n8n-nodes-base.ftp",
    "n8n-nodes-base.git",
    "n8n-nodes-base.localFileTrigger",
    "n8n-nodes-base.readWriteFile",
    "n8n-nodes-base.ssh",
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.mysql",
    "n8n-nodes-base.mariadb",
    "n8n-nodes-base.redis",
    "n8n-nodes-base.mongodb",
    "n8n-nodes-base.odoo",
    "n8n-nodes-base.twilio",
    "n8n-nodes-base.emailSend",
}
SAFE_CREDENTIAL_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_n8n_policy(policy: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    status = policy.get("status")
    endpoint = policy.get("endpoint_binding", {})
    credential = policy.get("credential_binding", {})
    editor = policy.get("editor_access", {})
    security = policy.get("security", {})

    if policy.get("schema_version") != "1.1":
        errors.append("n8n policy schema_version must be 1.1")
    if status not in {"UNVERIFIED", "VERIFIED"}:
        errors.append(f"n8n policy status is invalid: {status!r}")
    for name, value in (("endpoint", endpoint), ("credential", credential), ("editor", editor)):
        if not isinstance(value, dict) or value.get("status") not in {"UNVERIFIED", "VERIFIED"}:
            errors.append(f"n8n {name}-binding status is invalid")
    if not all(isinstance(value, dict) for value in (endpoint, credential, editor, security)):
        return errors + ["n8n policy sections must be objects"], []

    reviewed_sets = (
        (endpoint.get("allowed_strategies"), ALLOWED_ENDPOINT_STRATEGIES, "endpoint"),
        (credential.get("allowed_strategies"), ALLOWED_CREDENTIAL_STRATEGIES, "credential"),
        (editor.get("allowed_strategies"), ALLOWED_EDITOR_STRATEGIES, "editor"),
    )
    for configured, expected, label in reviewed_sets:
        if string_set(configured) != expected:
            errors.append(f"n8n {label} allowed_strategies differs from reviewed code policy")
    if editor.get("publicly_routable") is not False:
        errors.append("n8n editor must not be directly publicly routable")
    if endpoint.get("template_base_url") != "https://middleware.invalid":
        errors.append("template middleware URL must remain https://middleware.invalid")

    required_security = {
        "environment_access_in_nodes": False,
        "public_api_enabled": False,
        "code_node_enabled": False,
        "external_task_runners_required_if_code_enabled": True,
    }
    for field, expected in required_security.items():
        if security.get(field) is not expected:
            errors.append(f"n8n security policy requires {field}={expected!r}")
    excluded = string_set(security.get("dangerous_nodes_excluded"))
    if excluded is None:
        errors.append("dangerous n8n node exclusion list is missing or malformed")
        excluded = set()
    missing = sorted(REQUIRED_DANGEROUS_NODES - excluded)
    if missing:
        errors.append("n8n dangerous-node policy misses: " + ", ".join(missing))

    if status == "UNVERIFIED":
        if any(section.get("status") != "UNVERIFIED" for section in (endpoint, credential, editor)):
            errors.append("unverified n8n policy cannot contain verified endpoint, credential, or editor state")
        if policy.get("edition") != "UNVERIFIED":
            errors.append("unverified n8n policy must keep edition=UNVERIFIED")
        for field in ("verified_at", "verified_by", "independent_reviewer", "evidence_sha256"):
            if policy.get(field) is not None:
                errors.append(f"unverified n8n policy must not claim {field}")
        for field in (
            "production_strategy",
            "approved_base_url",
            "custom_variables_supported",
            "egress_policy_evidence_sha256",
        ):
            if endpoint.get(field) is not None:
                errors.append(f"unverified endpoint binding must not claim {field}")
        if credential.get("strategy") is not None or credential.get("evidence_sha256") is not None:
            errors.append("unverified credential binding must not claim strategy or evidence")
        if credential.get("approved_types") not in ([], None):
            errors.append("unverified credential binding must not approve credential types")
        if credential.get("approved_names") not in ([], None):
            errors.append("unverified credential binding must not approve credential names")
        for field in ("strategy", "evidence_sha256", "session_policy_evidence_sha256"):
            if editor.get(field) is not None:
                errors.append(f"unverified editor access must not claim {field}")
        return errors, sorted(excluded)

    if status != "VERIFIED":
        return errors, sorted(excluded)
    if any(section.get("status") != "VERIFIED" for section in (endpoint, credential, editor)):
        errors.append("verified n8n policy requires verified endpoint, credential, and editor bindings")
    edition = policy.get("edition")
    if not meaningful_identity(edition) or str(edition).strip().casefold() == "unverified":
        errors.append("verified n8n policy requires a named edition")
    if not valid_iso8601(policy.get("verified_at")):
        errors.append("verified n8n policy requires a timezone-aware verified_at")
    verified_by = policy.get("verified_by")
    reviewer = policy.get("independent_reviewer")
    if not meaningful_identity(verified_by) or not meaningful_identity(reviewer):
        errors.append("verified n8n policy requires verifier and independent reviewer identities")
    elif str(verified_by).strip().casefold() == str(reviewer).strip().casefold():
        errors.append("n8n policy verifier and reviewer must be different")
    if not non_placeholder_sha256(policy.get("evidence_sha256")):
        errors.append("verified n8n policy requires evidence SHA-256")

    endpoint_strategy = endpoint.get("production_strategy")
    if endpoint_strategy not in ALLOWED_ENDPOINT_STRATEGIES:
        errors.append("n8n production endpoint strategy is not approved")
    if not valid_https_base(endpoint.get("approved_base_url")):
        errors.append("verified endpoint binding requires an approved HTTPS base URL")
    if not non_placeholder_sha256(endpoint.get("egress_policy_evidence_sha256")):
        errors.append("verified endpoint binding requires egress-policy evidence SHA-256")
    if endpoint_strategy == "verified-custom-variable" and endpoint.get(
        "custom_variables_supported"
    ) is not True:
        errors.append("custom-variable endpoint strategy requires proven custom-variable support")

    if credential.get("strategy") not in ALLOWED_CREDENTIAL_STRATEGIES:
        errors.append("n8n credential-binding strategy is not approved")
    approved_types = credential.get("approved_types")
    approved_names = credential.get("approved_names")
    if not isinstance(approved_types, list) or not approved_types or any(
        not isinstance(value, str) or not SAFE_CREDENTIAL_TYPE.fullmatch(value)
        for value in approved_types
    ):
        errors.append("verified credential binding requires safe approved credential types")
    if not isinstance(approved_names, list) or not approved_names or any(
        not meaningful_identity(value) for value in approved_names
    ):
        errors.append("verified credential binding requires safe approved credential names")
    if isinstance(approved_types, list) and len(set(approved_types)) != len(approved_types):
        errors.append("approved credential types must be unique")
    if isinstance(approved_names, list) and len(set(approved_names)) != len(approved_names):
        errors.append("approved credential names must be unique")
    if not non_placeholder_sha256(credential.get("evidence_sha256")):
        errors.append("verified credential binding requires evidence SHA-256")

    if editor.get("strategy") not in ALLOWED_EDITOR_STRATEGIES:
        errors.append("n8n editor-access strategy is not approved")
    if not non_placeholder_sha256(editor.get("evidence_sha256")):
        errors.append("verified editor access requires evidence SHA-256")
    if not non_placeholder_sha256(editor.get("session_policy_evidence_sha256")):
        errors.append("verified editor access requires session-policy evidence SHA-256")
    return errors, sorted(excluded)
