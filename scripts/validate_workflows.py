#!/usr/bin/env python3
"""Validate committed n8n exports against the disabled, middleware-only source policy."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*\.v[1-9][0-9]*$")
IP_LITERAL = re.compile(r"(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9])")
SAFE_CREDENTIAL_ID = re.compile(r"^[A-Za-z0-9._:@+-]{1,256}$")
HTTP_URL = re.compile(r"https?://[^\s\"'<>]+", flags=re.IGNORECASE)
CONNECTION_SCHEME = re.compile(
    r"\b(?:postgresql|postgres|redis|mysql|mariadb|mongodb|smtp|smtps|smpp|ftp|ssh)://",
    flags=re.IGNORECASE,
)
BLOCKED_HOST_LABELS = {
    "vicidial",
    "jasmin",
    "postal",
    "keycloak",
    "kong",
    "odoo",
    "redis",
    "postgres",
    "postgresql",
    "mysql",
    "mariadb",
    "mongodb",
    "twilio",
}
FORBIDDEN_NODE_TYPES = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.executecommand",
    "n8n-nodes-base.ftp",
    "n8n-nodes-base.git",
    "n8n-nodes-base.localfiletrigger",
    "n8n-nodes-base.readwritefile",
    "n8n-nodes-base.ssh",
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.mysql",
    "n8n-nodes-base.mariadb",
    "n8n-nodes-base.redis",
    "n8n-nodes-base.mongodb",
    "n8n-nodes-base.odoo",
    "n8n-nodes-base.twilio",
    "n8n-nodes-base.emailsend",
}
# Default-deny: additions require a reviewed policy change. Only control/data-shaping
# nodes and the Middleware-bound HTTP Request node are allowed initially.
ALLOWED_NODE_TYPES = {
    "n8n-nodes-base.aggregate",
    "n8n-nodes-base.datetime",
    "n8n-nodes-base.errortrigger",
    "n8n-nodes-base.filter",
    "n8n-nodes-base.httprequest",
    "n8n-nodes-base.if",
    "n8n-nodes-base.limit",
    "n8n-nodes-base.manualtrigger",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.noop",
    "n8n-nodes-base.removeduplicates",
    "n8n-nodes-base.scheduletrigger",
    "n8n-nodes-base.set",
    "n8n-nodes-base.sort",
    "n8n-nodes-base.splitinbatches",
    "n8n-nodes-base.stopanderror",
    "n8n-nodes-base.switch",
}
CUSTOM_VARIABLE_PREFIX = "={{$vars.MIDDLEWARE_BASE_URL}}/"
MIDDLEWARE_AUTOMATION_PREFIX = "/v2/automation/"


def strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def load_policy() -> dict[str, Any]:
    with (ROOT / "config" / "n8n-policy.json").open(encoding="utf-8") as handle:
        policy = json.load(handle)
    if not isinstance(policy, dict):
        raise ValueError("n8n policy must be a JSON object")
    return policy


def decoded_safe_path(path: str) -> str | None:
    """Decode repeatedly and reject ambiguous or traversal-capable URL paths."""
    if not isinstance(path, str) or not path.startswith("/"):
        return None
    candidate = path
    try:
        for _ in range(4):
            decoded = unquote(candidate, errors="strict")
            if decoded == candidate:
                break
            candidate = decoded
    except UnicodeDecodeError:
        return None
    if "%" in candidate or "\\" in candidate or "//" in candidate:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        return None
    if any(segment in {".", ".."} for segment in candidate.split("/")):
        return None
    return candidate


def _normalize_safe_n8n_path_template(value: str) -> str | None:
    if "{{" not in value and "}}" not in value:
        return value
    parsed = urlsplit(value)
    prefix = value[: value.find(parsed.path or "")]
    if "{{" in prefix or "}}" in prefix or parsed.query or parsed.fragment:
        return None
    normalized = re.sub(r"\{\{[^{}]+\}\}", "template", value)
    if "{{" in normalized or "}}" in normalized:
        return None
    return normalized


def https_url_under_base(value: str, base: str) -> bool:
    """Return true only when value is an HTTPS URL below the exact reviewed base origin/path."""
    normalized_value = _normalize_safe_n8n_path_template(value)
    if normalized_value is None:
        return False
    try:
        parsed = urlsplit(normalized_value)
        approved = urlsplit(base)
        parsed_port = parsed.port
        approved_port = approved.port
    except ValueError:
        return False
    if approved.scheme.lower() != "https" or parsed.scheme.lower() != "https":
        return False
    if not approved.hostname or not parsed.hostname:
        return False
    if approved.username or approved.password or parsed.username or parsed.password:
        return False
    if approved.query or approved.fragment or parsed.fragment:
        return False
    if parsed.hostname.lower() != approved.hostname.lower() or parsed_port != approved_port:
        return False
    approved_path = decoded_safe_path(approved.path or "/")
    parsed_path = decoded_safe_path(parsed.path or "/")
    if approved_path is None or parsed_path is None:
        return False
    base_path = approved_path.rstrip("/")
    required_prefix = f"{base_path}/" if base_path else "/"
    if not parsed_path.startswith(required_prefix):
        return False
    relative_path = parsed_path[len(base_path) :] if base_path else parsed_path
    return relative_path.startswith(MIDDLEWARE_AUTOMATION_PREFIX)


def valid_custom_variable_target(value: str) -> bool:
    if not value.startswith(CUSTOM_VARIABLE_PREFIX):
        return False
    suffix = value[len(CUSTOM_VARIABLE_PREFIX) :]
    if not suffix or suffix.startswith(("/", ".")):
        return False
    if any(character.isspace() for character in suffix) or "\\" in suffix:
        return False
    if "://" in suffix or "$env" in suffix or "?" in suffix or "#" in suffix:
        return False
    if "{{" in suffix or "}}" in suffix:
        return False
    decoded = decoded_safe_path(f"/{suffix}")
    return decoded is not None and decoded.startswith(MIDDLEWARE_AUTOMATION_PREFIX)


def allowed_http_target(value: str, *, is_template: bool, policy: dict[str, Any]) -> bool:
    if not isinstance(value, str) or "$env" in value:
        return False
    endpoint = policy.get("endpoint_binding", {})
    if is_template:
        base = endpoint.get("template_base_url")
        return isinstance(base, str) and https_url_under_base(value, base)
    if endpoint.get("status") != "VERIFIED":
        return False
    strategy = endpoint.get("production_strategy")
    if strategy == "verified-custom-variable":
        return valid_custom_variable_target(value)
    if strategy in {"verified-custom-node", "verified-fixed-private-dns"}:
        approved_base = endpoint.get("approved_base_url")
        return isinstance(approved_base, str) and https_url_under_base(value, approved_base)
    return False


def node_type_allowed(node_type: str) -> bool:
    return isinstance(node_type, str) and node_type.lower() in ALLOWED_NODE_TYPES


def contains_direct_service_reference(value: str) -> bool:
    lowered = value.lower()
    if "kong_admin" in lowered or CONNECTION_SCHEME.search(value):
        return True
    for candidate in HTTP_URL.findall(value):
        try:
            hostname = urlsplit(candidate).hostname
        except ValueError:
            return True
        if not hostname:
            continue
        labels = set(re.split(r"[^a-z0-9]+", hostname.lower()))
        if labels & BLOCKED_HOST_LABELS:
            return True
    return False


def credential_references_allowed(credentials: Any, policy: dict[str, Any]) -> bool:
    binding = policy.get("credential_binding", {})
    if binding.get("status") != "VERIFIED" or not isinstance(credentials, dict) or not credentials:
        return False
    approved_types = set(binding.get("approved_types") or [])
    approved_names = set(binding.get("approved_names") or [])
    if not approved_types or not approved_names:
        return False
    for credential_type, reference in credentials.items():
        if credential_type not in approved_types or not isinstance(reference, dict):
            return False
        if set(reference) - {"id", "name"}:
            return False
        name = reference.get("name")
        if not isinstance(name, str) or name not in approved_names:
            return False
        credential_id = reference.get("id")
        if credential_id is not None and (
            not isinstance(credential_id, str) or not SAFE_CREDENTIAL_ID.fullmatch(credential_id)
        ):
            return False
    return True


def validate(path: Path, policy: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    policy = policy or load_policy()
    if not isinstance(policy, dict):
        return ["n8n policy must be a JSON object"]
    is_template = "_templates" in path.parts
    endpoint = policy.get("endpoint_binding", {})
    credential_binding = policy.get("credential_binding", {})

    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot parse JSON: {exc}"]

    if not is_template and (
        policy.get("status") != "VERIFIED"
        or endpoint.get("status") != "VERIFIED"
        or credential_binding.get("status") != "VERIFIED"
    ):
        errors.append(
            "executable workflow exports are blocked until n8n, endpoint, and credential policy are VERIFIED"
        )

    name = workflow.get("name")
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        errors.append("workflow name must match <namespace>.<domain>.<action>.v<major>")
    if workflow.get("active") is not False:
        errors.append("workflow active must be false")
    if workflow.get("pinData") not in ({}, None):
        errors.append("pinData must be empty")
    if "credentials" in workflow:
        errors.append("top-level credential material is prohibited")

    codestra_meta = workflow.get("meta", {}).get("codestra", {})
    if codestra_meta.get("network_policy") != "MIDDLEWARE_ONLY":
        errors.append("meta.codestra.network_policy must be MIDDLEWARE_ONLY")
    if codestra_meta.get("activation_state") != "DISABLED":
        errors.append("meta.codestra.activation_state must be DISABLED")
    if is_template:
        if codestra_meta.get("endpoint_binding") != "UNVERIFIED_TEMPLATE_ONLY":
            errors.append("templates must declare endpoint_binding=UNVERIFIED_TEMPLATE_ONLY")
        if codestra_meta.get("credential_binding") != "NO_CREDENTIALS":
            errors.append("templates must declare credential_binding=NO_CREDENTIALS")
    else:
        if codestra_meta.get("endpoint_binding") != "VERIFIED":
            errors.append("executable exports must declare endpoint_binding=VERIFIED")
        if codestra_meta.get("credential_binding") != "VERIFIED":
            errors.append("executable exports must declare credential_binding=VERIFIED")

    nodes = workflow.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes must be a non-empty list")
        return errors

    node_ids: set[str] = set()
    node_names: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"node {index} is not an object")
            continue
        node_id = node.get("id")
        node_name = node.get("name")
        node_type = str(node.get("type", ""))
        lowered_type = node_type.lower()
        if not node_id or node_id in node_ids:
            errors.append(f"node {index} has a missing or duplicate id")
        node_ids.add(node_id)
        if not node_name or node_name in node_names:
            errors.append(f"node {index} has a missing or duplicate name")
        node_names.add(node_name)

        if not node_type_allowed(node_type):
            errors.append(
                f"node {node_name!r} uses type {node_type!r} outside the reviewed allowlist"
            )
        if lowered_type in FORBIDDEN_NODE_TYPES:
            errors.append(f"node {node_name!r} uses prohibited type {node_type!r}")
        if "webhook" in lowered_type:
            errors.append(f"node {node_name!r} exposes a webhook; callbacks must terminate at middleware")

        credentials = node.get("credentials")
        if credentials is not None:
            if is_template or not credential_references_allowed(credentials, policy):
                errors.append(f"node {node_name!r} contains unapproved credential references")

        if "httprequest" in lowered_type:
            parameters = node.get("parameters", {})
            url_value = parameters.get("url") if isinstance(parameters, dict) else None
            if not isinstance(url_value, str) or not url_value:
                errors.append(f"HTTP node {node_name!r} has no string URL expression")
            else:
                if not allowed_http_target(url_value, is_template=is_template, policy=policy):
                    errors.append(f"HTTP node {node_name!r} uses an unapproved endpoint binding")
                if IP_LITERAL.search(url_value):
                    errors.append(f"HTTP node {node_name!r} contains an IP literal")
            if is_template and node.get("disabled") is not True:
                errors.append(f"template HTTP node {node_name!r} must be disabled")

    serialized = json.dumps(workflow, sort_keys=True).lower()
    if "$env" in serialized:
        errors.append("workflow uses $env while environment access in nodes is blocked")
    if any(contains_direct_service_reference(value) for value in strings(workflow)):
        errors.append("workflow contains a direct service/provider endpoint reference")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()

    files = sorted(args.directory.rglob("*.json"))
    if not files:
        print("WORKFLOW_VALIDATION=FAIL")
        print("ERROR=no workflow JSON files found")
        return 1

    try:
        policy = load_policy()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("WORKFLOW_VALIDATION=FAIL")
        print(f"ERROR=n8n policy cannot be read: {exc}")
        return 1
    failures = 0
    for path in files:
        errors = validate(path, policy)
        if errors:
            failures += 1
            for error in errors:
                print(f"ERROR={path}:{error}")
        else:
            print(f"WORKFLOW_PASS={path}")

    if failures:
        print("WORKFLOW_VALIDATION=FAIL")
        return 1
    print("WORKFLOW_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
