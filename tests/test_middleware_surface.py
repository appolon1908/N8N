from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import validate_workflows


ROOT = Path(__file__).resolve().parents[1]


class MiddlewareSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.surface = json.loads(
            (ROOT / "contracts" / "middleware-surface.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.operations = {
            (operation["method"], operation["path"]): operation
            for operation in self.surface["operations"]
        }

    def test_one_canonical_command_submission_path(self) -> None:
        commands = [
            operation
            for operation in self.surface["operations"]
            if operation["purpose"] == "Submit one durable governed command"
        ]
        self.assertEqual(1, len(commands))
        self.assertEqual("POST", commands[0]["method"])
        self.assertEqual("/v2/automation/commands", commands[0]["path"])
        self.assertEqual(
            "/v2/automation/commands", self.surface["command_endpoint"]
        )
        self.assertEqual(1, self.surface["invariants"]["command_paths_distinct"])

    def test_surface_matches_all_thirteen_automation_operations(self) -> None:
        expected = {
            ("POST", "/v2/automation/jobs/claim"),
            ("GET", "/v2/automation/jobs/{job_id}"),
            ("POST", "/v2/automation/jobs/{job_id}/heartbeat"),
            ("POST", "/v2/automation/jobs/{job_id}/steps"),
            ("POST", "/v2/automation/jobs/{job_id}/complete"),
            ("POST", "/v2/automation/jobs/{job_id}/fail"),
            ("POST", "/v2/automation/commands"),
            ("GET", "/v2/automation/commands/{command_id}"),
            ("POST", "/v2/automation/approvals"),
            ("GET", "/v2/automation/approvals/{approval_id}"),
            ("POST", "/v2/automation/dead-letters/{dead_letter_id}/replay"),
            ("POST", "/v2/automation/jobs/reconcile"),
            ("GET", "/v2/automation/capabilities/{capability}"),
        }
        actual = {
            key for key in self.operations if key[1].startswith("/v2/automation/")
        }
        self.assertEqual(expected, actual)

    def test_result_submit_and_read_pair_is_canonical(self) -> None:
        submit = self.operations[("POST", "/api/v1/integrations/n8n/results")]
        read = self.operations[("GET", "/api/v1/integrations/n8n/results/{event_id}")]
        self.assertEqual("n8n.results.submit", submit["scope"])
        self.assertEqual("n8n.results.read", read["scope"])
        self.assertIn("Idempotency-Key", submit["required_headers"])
        self.assertNotIn("Idempotency-Key", read["required_headers"])

    def test_claim_response_requires_lease_payload_and_correlation(self) -> None:
        contract = (
            ROOT / "contracts" / "automation-control-api.v2.yaml"
        ).read_text(encoding="utf-8")
        claim_path = contract.split("  /v2/automation/jobs/claim:\n", 1)[1].split(
            "  /v2/automation/jobs/{job_id}:\n", 1
        )[0]
        self.assertIn(
            "$ref: '#/components/schemas/ClaimedAutomationJob'", claim_path
        )
        claimed_schema = contract.split("    ClaimedAutomationJob:\n", 1)[1].split(
            "    HeartbeatRequest:\n", 1
        )[0]
        self.assertIn(
            "required: [lease_token, lease_expires_at, correlation_id, payload]",
            claimed_schema,
        )
        self.assertIn(
            "lease_token: {type: string, minLength: 16}", claimed_schema
        )
        self.assertIn(
            "lease_expires_at: {type: string, format: date-time}",
            claimed_schema,
        )
        self.assertIn(
            "correlation_id: {type: string, minLength: 1, maxLength: 180}",
            claimed_schema,
        )
        self.assertIn("payload: {type: object}", claimed_schema)

    def test_reconciliation_request_is_explicit_and_dry_run_only(self) -> None:
        operation = self.operations[("POST", "/v2/automation/jobs/reconcile")]
        self.assertEqual("ReconciliationRequest", operation["envelope_schema"])
        contract = (
            ROOT / "contracts" / "automation-control-api.v2.yaml"
        ).read_text(encoding="utf-8")
        reconcile_path = contract.split(
            "  /v2/automation/jobs/reconcile:\n", 1
        )[1].split("  /v2/automation/capabilities/{capability}:\n", 1)[0]
        self.assertIn(
            "$ref: '#/components/schemas/ReconciliationRequest'",
            reconcile_path,
        )
        schema = contract.split("    ReconciliationRequest:\n", 1)[1].split(
            "    CapabilityState:\n", 1
        )[0]
        self.assertIn("required: [requested_by, dry_run]", schema)
        self.assertIn("dry_run: {type: boolean, const: true}", schema)

    def test_legacy_command_routes_are_not_allowed_for_new_workflows(self) -> None:
        self.assertNotIn(
            ("POST", "/v1/integrations/n8n/commands"), self.operations
        )
        self.assertNotIn(
            ("GET", "/v1/integrations/n8n/operations/{command_id}"),
            self.operations,
        )
        self.assertEqual(
            [
                "/v1/integrations/n8n/commands",
                "/v1/integrations/n8n/operations/{command_id}",
                "/v1/integrations/n8n/operations/",
            ],
            self.surface["invariants"]["legacy_command_paths_prohibited"],
        )

    def test_validator_rejects_legacy_aliases_outside_http_urls(self) -> None:
        policy = validate_workflows.load_policy()
        blocked_values = [
            "/v1/integrations/n8n/commands",
            "/v1/integrations/n8n/operations/{command_id}",
            "/v1/integrations/n8n/operations/command-123",
            "/v1/integrations/n8n/operations/{{$json.command_id}}",
        ]
        for blocked in blocked_values:
            with self.subTest(blocked=blocked), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "workflows" / "_templates" / "legacy.v1.json"
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "name": "template.legacy.reference.v1",
                            "nodes": [
                                {
                                    "parameters": {
                                        "assignments": {
                                            "assignments": [
                                                {
                                                    "id": "legacy-path",
                                                    "name": "deprecated_path",
                                                    "value": blocked,
                                                    "type": "string",
                                                }
                                            ]
                                        },
                                        "options": {},
                                    },
                                    "id": "set-legacy-path",
                                    "name": "Set Legacy Path",
                                    "type": "n8n-nodes-base.set",
                                    "typeVersion": 3.4,
                                    "position": [0, 0],
                                }
                            ],
                            "connections": {},
                            "pinData": {},
                            "active": False,
                            "settings": {
                                "executionOrder": "v1",
                                "saveDataSuccessExecution": "none",
                                "saveManualExecutions": False,
                            },
                            "meta": {
                                "codestra": {
                                    "activation_state": "DISABLED",
                                    "network_policy": "MIDDLEWARE_ONLY",
                                    "endpoint_binding": "UNVERIFIED_TEMPLATE_ONLY",
                                    "credential_binding": "NO_CREDENTIALS",
                                    "timeout_semantics": "READ_STATE_BEFORE_RETRY",
                                    "automatic_retry_on_timeout": False,
                                }
                            },
                            "tags": [],
                        }
                    ),
                    encoding="utf-8",
                )
                self.assertIn(
                    "workflow contains a prohibited legacy middleware command path",
                    validate_workflows.validate(path, policy),
                )

    def test_every_operation_declares_governance_semantics(self) -> None:
        required = {
            "method",
            "path",
            "purpose",
            "envelope_schema",
            "required_headers",
            "responses",
            "idempotency",
            "timeout",
        }
        for operation in self.surface["operations"]:
            self.assertFalse(required - set(operation), operation["path"])
            self.assertIn("Authorization", operation["required_headers"])
            self.assertTrue(operation["responses"])
            self.assertTrue(operation["idempotency"])
            self.assertTrue(operation["timeout"])

    def test_surface_remains_disabled_and_middleware_only(self) -> None:
        self.assertEqual(0, self.surface["safety"]["active_workflows"])
        self.assertFalse(self.surface["safety"]["external_effects_enabled"])
        self.assertFalse(self.surface["safety"]["production_changed"])
        self.assertFalse(self.surface["safety"]["direct_provider_access"])
        self.assertFalse(self.surface["safety"]["ODOO_WRITE"])
        self.assertTrue(
            self.surface["invariants"]["unknown_outcome_requires_reconciliation"]
        )


if __name__ == "__main__":
    unittest.main()
