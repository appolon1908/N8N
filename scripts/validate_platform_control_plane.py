#!/usr/bin/env python3
"""Validate the n8n side of the four-repository platform control plane."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "platform-control-plane.v1.json"
POLICY = ROOT / "config" / "n8n-policy.json"
OPERATION_POLICY = ROOT / "contracts" / "operation-policy.v2.json"
COMMAND_SCHEMA = ROOT / "contracts" / "command-envelope.schema.json"
SURFACE = ROOT / "contracts" / "middleware-surface.v1.json"
TEMPLATE = ROOT / "workflows" / "_templates" / "disabled-odoo-lead-via-middleware.json"
COMMAND_TEMPLATES = (
    ROOT / "workflows" / "_templates" / "disabled-odoo-lead-via-middleware.json",
    ROOT / "workflows" / "_templates" / "disabled-middleware-command.json",
    ROOT / "workflows" / "_templates" / "request-governed-command.v2.json",
)
SENTINEL_BASE = "https://middleware.invalid"
CANONICAL_COMMAND_PATH = "/v2/automation/commands"
CANONICAL_COMMAND_READ = "/v2/automation/commands/{command_id}"
LEGACY_PATHS = (
    "/v1/integrations/n8n/commands",
    "/v1/integrations/n8n/operations/{command_id}",
)


def fail(message: str) -> None:
    raise SystemExit(f"PLATFORM_CONTROL_PLANE=FAIL {message}")


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    operation_policy = json.loads(OPERATION_POLICY.read_text(encoding="utf-8"))
    schema = json.loads(COMMAND_SCHEMA.read_text(encoding="utf-8"))
    surface = json.loads(SURFACE.read_text(encoding="utf-8"))
    workflow = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    repositories = contract.get("repositories", {})
    expected = {
        "orchestration": "appolon1908-hue/N8N",
        "write_authority": "appolon1908-hue/Middleware-",
        "business_authority": "appolon1908-hue/Odoo",
        "gateway_authority": "appolon1908-hue/Kong",
    }
    if repositories != expected:
        fail("repository authority map drifted")
    if contract.get("status") != "PREPARED_DISABLED":
        fail("source contract must remain PREPARED_DISABLED")
    if contract.get("decision") != "middleware_adopts_automation_v2":
        fail("automation authority decision drifted")

    edge = contract.get("n8n_to_middleware", {})
    expected_edge = {
        "gateway_host": "api.codestra.co",
        "canonical_submit_path": CANONICAL_COMMAND_PATH,
        "canonical_read_path": CANONICAL_COMMAND_READ,
        "client_id": "n8n-crm-automation",
        "audience": "middleware-api",
        "submit_scope": "automation.command.crm",
        "read_scope": "automation.command.read",
        "tenant_authority": "verified_token_and_durable_job",
        "header_body_agreement_required": True,
        "direct_provider_access": False,
    }
    for key, value in expected_edge.items():
        if edge.get(key) != value:
            fail(f"n8n edge field {key} drifted")
    required_headers = {
        "Authorization",
        "X-Tenant-ID",
        "X-Request-ID",
        "X-Correlation-ID",
        "Idempotency-Key",
    }
    if set(edge.get("required_headers", [])) != required_headers:
        fail("canonical command headers drifted")

    operations = {
        (item.get("method"), item.get("path")): item
        for item in operation_policy.get("operations", [])
        if isinstance(item, dict)
    }
    if len(operations) != 13:
        fail("operation policy must expose exactly 13 canonical automation operations")
    if ("POST", CANONICAL_COMMAND_PATH) not in operations:
        fail("canonical automation command submit operation is missing")
    if ("GET", CANONICAL_COMMAND_READ) not in operations:
        fail("canonical automation command read operation is missing")
    if any((method, path) in operations for method in ("POST", "GET") for path in LEGACY_PATHS):
        fail("legacy n8n command paths remain canonical operations")

    schema_required = set(schema.get("required", []))
    required_command_fields = {
        "job_id",
        "lease_token",
        "execution_id",
        "workflow_key",
        "workflow_version",
        "step_key",
        "event_id",
        "tenant_id",
        "requested_by",
        "correlation_id",
        "causation_id",
        "idempotency_key",
        "command_type",
        "command_version",
        "occurred_at",
        "payload",
    }
    if schema_required != required_command_fields:
        fail("automation command schema required field set drifted")
    properties = schema.get("properties", {})
    if properties.get("command_version", {}).get("type") != "string":
        fail("command_version must be a string such as 1.0")
    if properties.get("command_type", {}).get("pattern") != r"^(?!.*\.v[0-9]+$)[a-z0-9]+(?:[.-][a-z0-9]+)*$":
        fail("command_type must not carry a duplicate .vN suffix")
    mirrors = schema.get("x-codestra-headers", {}).get("mirrors", {})
    if mirrors != {
        "X-Tenant-ID": "/tenant_id",
        "X-Correlation-ID": "/correlation_id",
        "Idempotency-Key": "/idempotency_key",
    }:
        fail("header/body identity agreement contract drifted")

    surface_operations = {
        (item.get("method"), item.get("path"))
        for item in surface.get("operations", [])
        if isinstance(item, dict) and str(item.get("path", "")).startswith("/v2/automation/")
    }
    if surface.get("command_endpoint") != CANONICAL_COMMAND_PATH:
        fail("middleware surface command endpoint drifted")
    if len(surface_operations) != 13 or set(operations) != surface_operations:
        fail("middleware surface and operation policy operation sets differ")
    if surface.get("invariants", {}).get("command_paths_distinct") != 1:
        fail("middleware surface must declare one canonical command path")
    if any((method, path) in surface_operations for method in ("POST", "GET") for path in LEGACY_PATHS):
        fail("legacy n8n command routes remain in the allowed workflow surface")
    result_operations = {
        (item.get("method"), item.get("path"), item.get("scope"))
        for item in surface.get("operations", [])
        if isinstance(item, dict) and str(item.get("path", "")).startswith("/api/v1/integrations/n8n/results")
    }
    if result_operations != {
        ("POST", "/api/v1/integrations/n8n/results", "n8n.results.submit"),
        ("GET", "/api/v1/integrations/n8n/results/{event_id}", "n8n.results.read"),
    }:
        fail("canonical n8n result submit/read surface drifted")

    boundary = contract.get("middleware_to_odoo", {})
    expected_boundary = {
        "target": "odoo-19",
        "capability": "ODOO_WRITE",
        "bridge_module": "codestra_middleware_bridge",
        "canonical_command_type": "crm.lead.upsert",
        "canonical_command_version": "1.0",
        "canonical_command_path": "/codestra/middleware/v1/commands/crm.lead.upsert",
        "canonical_status_path": "/codestra/middleware/v1/commands/{command_id}/status",
        "readback_required": True,
        "unknown_outcome_policy": "query_command_status_before_any_retry",
        "blind_resubmission_allowed": False,
    }
    for key, value in expected_boundary.items():
        if boundary.get(key) != value:
            fail(f"Odoo boundary field {key} drifted")

    if policy.get("status") != "UNVERIFIED":
        fail("source branch must not self-certify runtime n8n policy")
    endpoint = policy.get("endpoint_binding", {})
    credentials = policy.get("credential_binding", {})
    if endpoint.get("status") != "UNVERIFIED":
        fail("endpoint binding requires staging evidence before verification")
    if endpoint.get("template_base_url") != SENTINEL_BASE:
        fail("unverified template base must remain middleware.invalid")
    if credentials.get("status") != "UNVERIFIED":
        fail("credential binding requires staging evidence before verification")

    if workflow.get("active") is not False:
        fail("Odoo workflow template must remain inactive")
    meta = workflow.get("meta", {}).get("codestra", {})
    if meta.get("network_policy") != "MIDDLEWARE_ONLY":
        fail("workflow must declare MIDDLEWARE_ONLY network policy")
    if meta.get("activation_state") != "DISABLED":
        fail("workflow activation state must remain DISABLED")
    if meta.get("credential_binding") != "NO_CREDENTIALS":
        fail("template must not bind credentials")
    if meta.get("automatic_retry_on_timeout") is not False:
        fail("unknown command outcome must never be retried automatically")

    assigned = {
        assignment.get("name"): assignment.get("value")
        for node in workflow.get("nodes", [])
        for assignment in node.get("parameters", {})
        .get("assignments", {})
        .get("assignments", [])
    }
    if required_command_fields - set(assigned):
        fail("Odoo command template does not assign the complete v2 envelope")
    if assigned.get("command_type") != "crm.lead.upsert":
        fail("Odoo command template must use crm.lead.upsert")
    if assigned.get("command_version") != "1.0":
        fail("Odoo command template must use command_version 1.0 as a string")
    payload_expression = str(assigned.get("payload", ""))
    for marker in (
        "source_record_id",
        "initial_stage",
        "review_pending",
        "review_required",
        "allow_external_contact",
        "provenance",
        "consent",
    ):
        if marker not in payload_expression:
            fail(f"Odoo command payload is missing {marker}")

    http_nodes = [
        node
        for node in workflow.get("nodes", [])
        if str(node.get("type", "")).lower() == "n8n-nodes-base.httprequest"
    ]
    if len(http_nodes) != 1:
        fail("Odoo template must contain exactly one reviewed HTTP boundary")
    node = http_nodes[0]
    if node.get("disabled") is not True:
        fail("template HTTP node must remain disabled")
    if node.get("parameters", {}).get("url") != SENTINEL_BASE + CANONICAL_COMMAND_PATH:
        fail("Odoo template must use the canonical v2 command path on middleware.invalid")
    headers = {
        item.get("name"): item.get("value")
        for item in node.get("parameters", {})
        .get("headerParameters", {})
        .get("parameters", [])
    }
    if set(headers) != required_headers:
        fail("template must carry canonical gateway headers")
    if headers["Authorization"] != "={{$json.authorization}}":
        fail("template Authorization must remain an unbound runtime expression")
    body = node.get("parameters", {}).get("body", "")
    for field in required_command_fields:
        if f"{field}:$json.{field}" not in body:
            fail(f"HTTP body does not explicitly serialize {field}")
    for forbidden in ("target:$json.target", "capability:$json.capability", "actor:$json.actor"):
        if forbidden in body:
            fail(f"caller-controlled authority field is prohibited: {forbidden}")

    for template_path in COMMAND_TEMPLATES:
        serialized = template_path.read_text(encoding="utf-8")
        if CANONICAL_COMMAND_PATH not in serialized:
            fail(f"{template_path.name} does not use the canonical command route")
        if any(path in serialized for path in LEGACY_PATHS):
            fail(f"{template_path.name} still contains a legacy command route")
        document = json.loads(serialized)
        if document.get("active") is not False:
            fail(f"{template_path.name} must remain inactive")

    serialized = json.dumps(workflow).lower()
    forbidden_targets = (
        "http://odoo",
        "https://odoo",
        "jasmin",
        "postal",
        "vicidial",
        "smtp://",
        "postgres://",
        "redis://",
        "api.codestra.co",
    )
    found = [value for value in forbidden_targets if value in serialized]
    if found:
        fail("unverified template contains direct runtime targets: " + ", ".join(found))

    safety = contract.get("safety", {})
    for flag in ("workflows_active", "ODOO_WRITE", "ENABLE_EXTERNAL_DELIVERY", "LIVE_WRITE"):
        if safety.get(flag) is not False:
            fail(f"{flag} must remain false")

    print("PLATFORM_CONTROL_PLANE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
