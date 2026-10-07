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
    from .policy_common import ROOT, load_json, valid_https_base
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
    from policy_common import ROOT, load_json, valid_https_base  # type: ignore
    from policy_compose import validate_compose  # type: ignore
    from policy_n8n import REQUIRED_DANGEROUS_NODES, validate_n8n_policy  # type: ignore


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
                or any(token in route for token in ("?", "#"))
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
    print("LIVE_SERVER_MUTATION_CAPABILITY=ABSENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
