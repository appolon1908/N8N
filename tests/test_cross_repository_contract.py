from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/middleware-public-api-route-contract.v2.json"
PINNED = ROOT / "contracts/middleware-public-api-route-contract.sha256"
SURFACE = ROOT / "contracts/middleware-surface.v1.json"
RUNTIME = ROOT / "config/n8n-community-runtime.v1.json"
TEMPLATES = ROOT / "workflows/_templates"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(document: dict) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def http_nodes(document: dict) -> list[dict]:
    return [node for node in document["nodes"] if node["type"] == "n8n-nodes-base.httpRequest"]


def test_vendored_contract_hash_and_all_automation_routes_are_exact():
    contract = load(CONTRACT)
    assert PINNED.read_text(encoding="utf-8").strip() == digest(contract)
    contract_v2 = {
        (row["method"], row["path"])
        for row in contract["routes"]
        if row["classification"] == "shared_edge" and row["path"].startswith("/v2/automation/")
    }
    surface_v2 = {
        (row["method"], row["path"])
        for row in load(SURFACE)["operations"]
        if row["path"].startswith("/v2/automation/")
    }
    assert surface_v2 == contract_v2
    assert len(contract_v2) == 13


def test_result_submit_and_read_routes_are_in_surface_runtime_and_templates():
    expected = {
        ("POST", "/api/v1/integrations/n8n/results", "n8n.results.submit"),
        ("GET", "/api/v1/integrations/n8n/results/{event_id}", "n8n.results.read"),
    }
    contract = load(CONTRACT)
    contract_rows = {
        (row["method"], row["path"], row["scope"])
        for row in contract["routes"]
        if row["classification"] == "shared_edge" and row["path"].startswith("/api/v1/integrations/n8n/results")
    }
    assert contract_rows == expected
    for path in (SURFACE, RUNTIME):
        document = load(path)
        rows = document["operations"] if path == SURFACE else document["endpoint"]["routes"]
        actual = {(row["method"], row["path"], row.get("scope")) for row in rows}
        assert expected <= actual

    submit = load(TEMPLATES / "submit-integration-result.v2.json")
    read = load(TEMPLATES / "read-integration-result.v2.json")
    for workflow in (submit, read):
        assert workflow["active"] is False
        assert "credentials" not in json.dumps(workflow)
        assert workflow["meta"]["codestra"]["automatic_retry_on_timeout"] is False
    assert http_nodes(submit)[0]["parameters"]["url"] == "https://middleware.invalid/api/v1/integrations/n8n/results"
    assert http_nodes(read)[0]["parameters"]["url"] == "https://middleware.invalid/api/v1/integrations/n8n/results/{{$json.event_id}}"


def test_runtime_binding_uses_only_canonical_routes_and_stays_no_go():
    text = (ROOT / "release/staging-runtime-bindings.v1.yaml").read_text(encoding="utf-8")
    assert "command_route: POST /v2/automation/commands" in text
    assert "operation_route: GET /v2/automation/commands/{command_id}" in text
    assert "result_submit_route: POST /api/v1/integrations/n8n/results" in text
    assert "result_read_route: GET /api/v1/integrations/n8n/results/{event_id}" in text
    assert "/v1/integrations/n8n/commands" not in text
    assert "/v1/integrations/n8n/operations" not in text
    assert "production_bindability:\n  status: NO_GO" in text
    assert "workflows_active: false" in text
