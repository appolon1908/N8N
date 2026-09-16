#!/usr/bin/env python3
"""Validate source-only repository invariants without network or third-party packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from .policy_actions import (
        BANNED_WORKFLOW_PATTERNS,
        validate_action_reference,
        validate_workflow_files,
    )
    from .policy_common import ROOT, load_json, string_set, valid_https_base
    from .policy_community_runtime import validate_community_runtime_policy
    from .policy_compose import validate_compose
    from .policy_n8n import (
        REQUIRED_DANGEROUS_NODES,
        validate_n8n_policy,
    )
except ImportError:  # `python3 scripts/validate_repository.py`
    from policy_actions import (  # type: ignore
        BANNED_WORKFLOW_PATTERNS,
        validate_action_reference,
        validate_workflow_files,
    )
    from policy_common import ROOT, load_json, string_set, valid_https_base  # type: ignore
    from policy_community_runtime import validate_community_runtime_policy  # type: ignore
    from policy_compose import validate_compose  # type: ignore
    from policy_n8n import REQUIRED_DANGEROUS_NODES, validate_n8n_policy  # type: ignore


STAGING_BINDING_PATH = ROOT / "release" / "staging-runtime-bindings.v1.yaml"
REQUIRED_STAGING_BINDING_TOKENS = (
    "schema_version: '1.2'",
    "status: PREPARED_NOT_APPLIED",
    "canonical_policy: config/n8n-policy.json",
    "community_runtime_contract: config/n8n-community-runtime.v1.json",
    "egress_policy: deploy/egress/n8n-egress-policy.v1.json",
    "authority: Caddy -> Kong -> Middleware",
    "base_url: https://api.codestra.co",
    "command_route: POST /v2/automation/commands",
    "operation_route: GET /v2/automation/commands/{command_id}",
    "result_submit_route: POST /api/v1/integrations/n8n/results",
    "result_read_route: GET /api/v1/integrations/n8n/results/{event_id}",
    "direct_private_middleware_listener_allowed: false",
    "direct_provider_endpoints_allowed: false",
    "owner: codestra-n8n-service-owner",
    "personal_account_allowed: false",
    "name: Codestra Middleware Service",
    "keycloak_client_id: n8n-automation",
    "strategy: caddy-oauth2-proxy-keycloak-plus-native-owner",
    "native_owner_login_required: true",
    "direct_public_n8n_exposure: false",
    "default_action: DENY",
    "runtime_network_enforcement_required: true",
    "workflows_active: false",
    "production_bindability:",
    "status: NO_GO",
    "runtime_execution_allowed: false",
    "production_control_plane_executable: false",
    "prepared_endpoint_base_url: https://api.codestra.co",
    "template_endpoint_base_url: https://middleware.invalid",
)
FORBIDDEN_STAGING_BINDING_TOKENS = (
    "base_url_source: OpenBao",
    "status: DECLARATION_DEFINED_NOT_APPLIED",
    "direct_private_middleware_listener_allowed: true",
    "direct_provider_endpoints_allowed: true",
    "personal_account_allowed: true",
    "direct_public_n8n_exposure: true",
    "default_action: ALLOW",
    "workflows_active: true",
    "status: GO",
    "runtime_execution_allowed: true",
    "production_control_plane_executable: true",
)
EXPECTED_N8N_CERTIFICATION = {
    "schema_version": "1.0",
    "certification_id": "codestra.n8n.source-certification.v1",
    "status": "SOURCE_CERTIFIED_RUNTIME_NO_GO",
    "source_contract_certified": True,
    "runtime_policy_certified": False,
    "production_bindability": "NO_GO",
    "production_promotion_authorized": False,
    "workflow_activation_allowed": False,
    "runtime_execution_allowed": False,
    "policy_status": "UNVERIFIED",
    "endpoint_binding_status": "UNVERIFIED",
    "credential_binding_status": "UNVERIFIED",
    "editor_binding_status": "UNVERIFIED",
    "staging_binding_status": "PREPARED_NOT_APPLIED",
    "community_runtime_status": "PREPARED_NOT_APPLIED",
    "prepared_endpoint_base_url": "https://api.codestra.co",
    "template_endpoint_base_url": "https://middleware.invalid",
}
EXPECTED_N8N_CERTIFICATION_EVIDENCE = {
    "config/n8n-policy.json",
    "config/n8n-community-runtime.v1.json",
    "release/staging-runtime-bindings.v1.yaml",
    "docs/STAGING-CERTIFICATION-2.36.8.md",
    "docs/evidence/N4/COMMUNITY-AUTHORITY-STATUS.md",
}
EXPECTED_N8N_CERTIFICATION_RUNTIME_REQUIREMENTS = {
    "endpoint_binding.status=VERIFIED",
    "credential_binding.status=VERIFIED",
    "editor_access.status=VERIFIED",
    "staging_binding_contract.status=APPLIED_VERIFIED",
    "N4 command-envelope convention resolved in estate integration authority",
    "cross-repository Middleware/N8N contract tests pass",
    "CP-ODOO staging dry-run passes with delivery flags off",
    "observability correlation evidence captured",
    "DLQ contains no unexpected records",
}


def validate_staging_binding(path: Path) -> list[str]:
    if not path.exists():
        return ["staging runtime binding declaration is missing"]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"staging runtime binding cannot be read: {exc}"]
    errors = [
        f"staging runtime binding lacks reviewed marker: {marker}"
        for marker in REQUIRED_STAGING_BINDING_TOKENS
        if marker not in text
    ]
    errors.extend(
        f"staging runtime binding contains forbidden marker: {marker}"
        for marker in FORBIDDEN_STAGING_BINDING_TOKENS
        if marker in text
    )
    return errors


def validate_n8n_certification(
    certification: dict[str, Any],
    policy: dict[str, Any],
    community_runtime: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for field, expected in EXPECTED_N8N_CERTIFICATION.items():
        if certification.get(field) != expected:
            errors.append(f"n8n certification {field} differs from reviewed source certification")
    if string_set(certification.get("evidence")) != EXPECTED_N8N_CERTIFICATION_EVIDENCE:
        errors.append("n8n certification evidence set differs from reviewed source certification")
    if (
        string_set(certification.get("required_before_runtime_go"))
        != EXPECTED_N8N_CERTIFICATION_RUNTIME_REQUIREMENTS
    ):
        errors.append("n8n certification runtime requirements differ from reviewed source certification")

    endpoint = policy.get("endpoint_binding", {})
    credential = policy.get("credential_binding", {})
    editor = policy.get("editor_access", {})
    staging = policy.get("staging_binding_contract", {})
    production = policy.get("production_bindability", {})
    comparisons = {
        "policy_status": policy.get("status"),
        "endpoint_binding_status": endpoint.get("status") if isinstance(endpoint, dict) else None,
        "credential_binding_status": credential.get("status") if isinstance(credential, dict) else None,
        "editor_binding_status": editor.get("status") if isinstance(editor, dict) else None,
        "staging_binding_status": staging.get("status") if isinstance(staging, dict) else None,
        "community_runtime_status": community_runtime.get("status"),
        "production_bindability": production.get("status") if isinstance(production, dict) else None,
        "workflow_activation_allowed": production.get("workflow_activation_allowed")
        if isinstance(production, dict)
        else None,
        "runtime_execution_allowed": production.get("runtime_execution_allowed")
        if isinstance(production, dict)
        else None,
        "prepared_endpoint_base_url": production.get("prepared_endpoint_base_url")
        if isinstance(production, dict)
        else None,
        "template_endpoint_base_url": production.get("template_endpoint_base_url")
        if isinstance(production, dict)
        else None,
    }
    for field, actual in comparisons.items():
        if certification.get(field) != actual:
            errors.append(f"n8n certification {field} does not match canonical policy")
    return errors


def _unique_ids(rows: Any, label: str, errors: list[str]) -> set[str]:
    if not isinstance(rows, list) or not rows:
        errors.append(f"{label} catalog is missing or empty")
        return set()
    values: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            errors.append(f"{label} row has a missing or invalid id")
            continue
        values.append(row["id"])
    if len(set(values)) != len(values):
        errors.append(f"{label} ids must be unique")
    return set(values)


def validate_catalogs(
    runtime: dict[str, Any],
    capabilities: dict[str, Any],
    services: dict[str, Any],
    products: dict[str, Any],
    catalog: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if runtime.get("status") not in {"UNVERIFIED", "VERIFIED"}:
        errors.append(f"runtime status is invalid: {runtime.get('status')!r}")

    flags = capabilities.get("capabilities")
    if not isinstance(flags, dict) or not flags:
        errors.append("capability map is missing or empty")
    else:
        enabled = sorted(name for name, value in flags.items() if value is not False)
        if enabled:
            errors.append("source-only scaffold has non-false capabilities: " + ", ".join(enabled))
    if capabilities.get("safety_mode") != "SOURCE_ONLY":
        errors.append("source-only scaffold requires safety_mode=SOURCE_ONLY")

    service_rows = services.get("services")
    service_ids = _unique_ids(service_rows, "service", errors)
    if isinstance(service_rows, list):
        reachable = [
            row
            for row in service_rows
            if isinstance(row, dict) and row.get("access_from_n8n") != "DENY_DIRECT"
        ]
        if len(reachable) != 1 or reachable[0].get("id") != "codestra-middleware":
            errors.append("only codestra-middleware may be reachable directly from n8n")
        for row in service_rows:
            if not isinstance(row, dict):
                continue
            if row.get("direct_database_access") is not False:
                errors.append(f"service {row.get('id')} permits direct database access")
            if row.get("runtime_status") not in {"UNVERIFIED", "VERIFIED"}:
                errors.append(f"service {row.get('id')} has invalid runtime status")

    product_rows = products.get("products")
    product_ids = _unique_ids(product_rows, "product", errors)
    if isinstance(product_rows, list):
        for row in product_rows:
            if isinstance(row, dict) and row.get("status") != "DESIGN_ONLY":
                errors.append(f"product {row.get('id')} is not DESIGN_ONLY")

    if catalog.get("default_activation") != "DISABLED":
        errors.append("automation catalog default activation must be DISABLED")
    automation_rows = catalog.get("automations")
    _unique_ids(automation_rows, "automation", errors)
    seen_routes: set[str] = set()
    if isinstance(automation_rows, list):
        for row in automation_rows:
            if not isinstance(row, dict):
                continue
            automation_id = row.get("id")
            if row.get("product") not in product_ids:
                errors.append(f"automation {automation_id} references an unknown product")
            if row.get("service") not in service_ids:
                errors.append(f"automation {automation_id} references an unknown service")
            if row.get("state") != "DESIGN_ONLY":
                errors.append(f"automation {automation_id} is not DESIGN_ONLY")
            if not isinstance(row.get("external_effect"), bool) or not isinstance(
                row.get("human_review"), bool
            ):
                errors.append(f"automation {automation_id} must declare boolean effect/review flags")
            route = row.get("middleware_route")
            if (
                not isinstance(route, str)
                or not route.startswith("/v1/")
                or any(marker in route for marker in ("?", "#"))
                or ".." in route.split("/")
            ):
                errors.append(f"automation {automation_id} lacks a safe versioned middleware route")
            elif route in seen_routes:
                errors.append(f"automation {automation_id} duplicates middleware route {route}")
            else:
                seen_routes.add(route)
    return errors


def main() -> int:
    errors: list[str] = []
    names = {
        "runtime": "config/runtime-paths.json",
        "capabilities": "config/capabilities.json",
        "services": "config/services.json",
        "products": "config/products.json",
        "catalog": "automations/catalog.json",
        "n8n_policy": "config/n8n-policy.json",
        "community_runtime": "config/n8n-community-runtime.v1.json",
        "egress_policy": "deploy/egress/n8n-egress-policy.v1.json",
        "n8n_certification": "release/n8n-certification.v1.json",
    }
    try:
        documents = {name: load_json(path) for name, path in names.items()}
    except (OSError, json.JSONDecodeError) as exc:
        print("REPOSITORY_VALIDATION=FAIL")
        print(f"ERROR=configuration cannot be read: {exc}")
        return 1
    malformed = [name for name, value in documents.items() if not isinstance(value, dict)]
    if malformed:
        print("REPOSITORY_VALIDATION=FAIL")
        print("ERROR=top-level JSON documents must be objects: " + ", ".join(malformed))
        return 1

    errors.extend(validate_staging_binding(STAGING_BINDING_PATH))
    errors.extend(
        validate_catalogs(
            documents["runtime"],
            documents["capabilities"],
            documents["services"],
            documents["products"],
            documents["catalog"],
        )
    )
    policy_errors, excluded_nodes = validate_n8n_policy(documents["n8n_policy"])
    errors.extend(policy_errors)
    errors.extend(
        validate_community_runtime_policy(
            documents["n8n_policy"],
            documents["community_runtime"],
            documents["egress_policy"],
        )
    )
    errors.extend(
        validate_n8n_certification(
            documents["n8n_certification"],
            documents["n8n_policy"],
            documents["community_runtime"],
        )
    )
    errors.extend(validate_workflow_files(ROOT / ".github" / "workflows"))
    errors.extend(
        validate_compose(ROOT / "deploy" / "compose" / "compose.staging.yml", excluded_nodes)
    )

    if errors:
        print("REPOSITORY_VALIDATION=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        return 1
    print("REPOSITORY_VALIDATION=PASS")
    print(f"RUNTIME_PATHS={documents['runtime'].get('status')}")
    print(f"N8N_POLICY={documents['n8n_policy'].get('status')}")
    print(
        "N8N_COMMUNITY_DESIRED_STATE="
        + str(documents["community_runtime"].get("status"))
    )
    print("N8N_EGRESS_POLICY=PREPARED_NOT_APPLIED")
    print(f"N8N_CERTIFICATION={documents['n8n_certification'].get('status')}")
    print("STAGING_BINDING=PREPARED_NOT_APPLIED")
    print("LIVE_SERVER_MUTATION_CAPABILITY=ABSENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
