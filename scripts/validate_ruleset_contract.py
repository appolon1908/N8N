#!/usr/bin/env python3
"""Validate the desired no-bypass main-branch ruleset contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RULESET = ROOT / "config" / "github-main-ruleset.v1.json"


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("target") != "branch":
        errors.append("ruleset target must be branch")
    if data.get("enforcement") != "active":
        errors.append("ruleset enforcement must be active")
    if data.get("bypass_actors") != []:
        errors.append("ruleset must have no bypass actors")
    include = ((data.get("conditions") or {}).get("ref_name") or {}).get("include")
    if include != ["~DEFAULT_BRANCH"]:
        errors.append("ruleset must target only the default branch")

    rules = data.get("rules")
    if not isinstance(rules, list):
        return errors + ["ruleset rules must be a list"]
    by_type: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
            errors.append("ruleset contains a malformed rule")
            continue
        if rule["type"] in by_type:
            errors.append(f"ruleset duplicates rule type {rule['type']}")
        by_type[rule["type"]] = rule

    for required in ("deletion", "non_fast_forward", "pull_request", "required_status_checks"):
        if required not in by_type:
            errors.append(f"ruleset lacks required rule {required}")

    pull = (by_type.get("pull_request") or {}).get("parameters") or {}
    expected_pull = {
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": True,
        "require_last_push_approval": True,
        "required_approving_review_count": 1,
        "required_review_thread_resolution": True,
    }
    for name, expected in expected_pull.items():
        if pull.get(name) is not expected and pull.get(name) != expected:
            errors.append(f"pull-request rule requires {name}={expected!r}")
    methods = pull.get("allowed_merge_methods")
    if not isinstance(methods, list) or not methods or any(
        method not in {"merge", "squash"} for method in methods
    ):
        errors.append("allowed merge methods must be a non-empty subset of merge/squash")

    checks = (by_type.get("required_status_checks") or {}).get("parameters") or {}
    if checks.get("strict_required_status_checks_policy") is not True:
        errors.append("required status checks must require an up-to-date branch")
    if checks.get("do_not_enforce_on_create") is not False:
        errors.append("required status checks must apply immediately")
    contexts = checks.get("required_status_checks")
    if contexts != [{"context": "Validate exact repository SHA"}]:
        errors.append("ruleset must require only the reviewed exact-head validation context")
    return errors


def main() -> int:
    try:
        data = json.loads(RULESET.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("GITHUB_RULESET_CONTRACT=FAIL")
        print(f"ERROR=ruleset contract cannot be read: {type(exc).__name__}")
        return 1
    if not isinstance(data, dict):
        print("GITHUB_RULESET_CONTRACT=FAIL")
        print("ERROR=ruleset contract must be an object")
        return 1
    errors = validate(data)
    if errors:
        print("GITHUB_RULESET_CONTRACT=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        return 1
    print("GITHUB_RULESET_CONTRACT=PASS")
    print("LIVE_GITHUB_RULESET_APPLICATION=NOT_PERFORMED_BY_SOURCE_VALIDATION")
    return 0


if __name__ == "__main__":
    sys.exit(main())
