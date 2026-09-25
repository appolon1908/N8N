#!/usr/bin/env python3
"""Validate the n8n side of the observability control plane.

Pinned consumer of appolon1908-hue/Middleware-'s canonical
contracts/observability-control-plane.v1.json (same pinning convention as
this repo's existing contracts/platform-control-plane.v1.json). Confirms
this repo's own observability files still match what the canonical
contract says n8n's role is: observe alert lifecycle from Middleware only,
never receive Alertmanager directly, never deliver alerts itself.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "observability-control-plane.v1.json"
ALERT_OBSERVER = ROOT / "contracts" / "observability-alert-observer.v1.json"
SCRAPE_CONTRACT = ROOT / "observability" / "n8n-scrape-contract.v1.json"


def fail(message: str) -> None:
    raise SystemExit(f"OBSERVABILITY_CONTROL_PLANE=FAIL {message}")


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    if contract.get("contract_id") != "codestra.observability-control-plane":
        fail("unexpected contract identity")
    if contract.get("canonical_owner") != "appolon1908-hue/Middleware-":
        fail("Middleware is not the declared canonical owner")
    if contract.get("source_repository") != "appolon1908-hue/Middleware-":
        fail("pinned contract is missing its source_repository pin")
    if not contract.get("source_commit"):
        fail("pinned contract is missing its source_commit pin")

    n8n_endpoints = contract.get("endpoints", {}).get("appolon1908-hue/N8N")
    if n8n_endpoints is None:
        fail("canonical contract no longer declares an N8N endpoints entry")
    if n8n_endpoints.get("alertmanager_receiver_present") is not False:
        fail("contract no longer asserts N8N has no Alertmanager receiver")

    alertmanager_service = next(
        (s for s in contract["services"] if s["service"] == "alertmanager"), None
    )
    if alertmanager_service is None or alertmanager_service.get("authorized_receiver") != (
        "appolon1908-hue/Middleware-"
    ):
        fail("contract no longer names Middleware as the sole Alertmanager receiver")

    # This repo's own alert-observer contract must still agree with the
    # canonical contract's description of it: ingress only from Middleware,
    # never a public webhook, and no direct delivery to any provider.
    try:
        observer = json.loads(ALERT_OBSERVER.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"{ALERT_OBSERVER} is missing - canonical contract references it")
        return 1
    if observer.get("ingress", {}).get("authority") != "codestra-middleware":
        fail("observability-alert-observer.v1.json no longer restricts ingress to Middleware")
    if observer.get("ingress", {}).get("public_webhook") is not False:
        fail("observability-alert-observer.v1.json now allows a public webhook")
    egress = observer.get("egress", {})
    if egress.get("allowed_targets") != ["codestra-middleware"]:
        fail("observability-alert-observer.v1.json now allows egress beyond Middleware")
    for direct_flag in ("direct_klyrow", "direct_postal", "direct_smtp", "direct_telnexa", "direct_jasmin"):
        if egress.get(direct_flag) is not False:
            fail(f"observability-alert-observer.v1.json now allows {direct_flag}")

    # This repo's own Prometheus scrape contract must still be private-only
    # and n8n-native, matching what the canonical contract records for it.
    try:
        scrape = json.loads(SCRAPE_CONTRACT.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"{SCRAPE_CONTRACT} is missing - canonical contract references it")
        return 1
    if scrape.get("privacy", {}).get("public_metrics") is not False:
        fail("n8n-scrape-contract.v1.json now allows public metrics")
    for target in scrape.get("targets", []):
        if target.get("network_scope") != "private":
            fail(f"n8n-scrape-contract.v1.json target {target.get('component')} is not private-scoped")

    print("OBSERVABILITY_CONTROL_PLANE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
