from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class AutomationIntegrationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load("contracts/operation-policy.v2.json")
        self.layer = load("config/integration-layer.v2.json")
        self.branches = load("config/branch-dependency-map.v2.json")
        self.beyvra = load("automations/beyvra.catalog.v2.json")

    def test_generic_scopes_are_absent(self) -> None:
        all_scopes = {
            scope
            for client in self.policy["clients"].values()
            for scope in client["scopes"]
        }
        self.assertNotIn("automation.execute", all_scopes)
        self.assertNotIn("automation.command", all_scopes)
        self.assertFalse(self.policy["invariants"]["generic_execute_scope_allowed"])
        self.assertFalse(self.policy["invariants"]["generic_command_scope_allowed"])

    def test_postly_has_dedicated_client_and_family(self) -> None:
        client = self.policy["clients"]["n8n-social-automation"]
        self.assertEqual(["social.postly"], client["workflow_families"])
        self.assertEqual(["social."], client["command_prefixes"])
        self.assertIn("automation.command.social", client["scopes"])
        messaging = self.policy["clients"]["n8n-messaging-automation"]
        self.assertNotIn("social.", messaging["command_prefixes"])
        self.assertNotIn("automation.command.social", messaging["scopes"])

    def test_beyvra_frontend_is_not_an_automation_client(self) -> None:
        repositories = {row["id"]: row for row in self.layer["repositories"]}
        self.assertIn("beyvra-backend", repositories)
        self.assertIn("beyvra-frontend", repositories)
        self.assertFalse(repositories["beyvra-frontend"]["is_n8n_client"])
        boundary = self.policy["product_boundaries"]["product.beyvra-platform"]
        self.assertFalse(boundary["frontend_is_automation_client"])
        self.assertFalse(self.beyvra["frontend_is_machine_client"])

    def test_beyvra_is_platform_lane_and_prefix_limited(self) -> None:
        client = self.policy["clients"]["n8n-product-automation"]
        self.assertIn("product.beyvra-platform", client["workflow_families"])
        self.assertIn("beyvra.operations.", client["command_prefixes"])
        self.assertNotIn("beyvra.", client["command_prefixes"])
        self.assertEqual(["beyvra.operations."], self.beyvra["allowed_command_prefixes"])
        self.assertIn("separate from the Trading platform", self.beyvra["lane_description"])
        self.assertFalse(self.beyvra["invariants"]["financial_effects_allowed"])
        self.assertFalse(self.beyvra["invariants"]["demo_order_effects_allowed"])
        for forbidden in ("trade.", "wallet.", "payment.", "custody.", "chain."):
            self.assertIn(forbidden, self.beyvra["prohibited_command_prefixes"])

    def test_beyvra_workflows_are_inactive_and_middleware_only(self) -> None:
        self.assertGreaterEqual(len(self.beyvra["workflows"]), 5)
        for workflow in self.beyvra["workflows"]:
            self.assertFalse(workflow["active"])
            self.assertFalse(workflow["direct_service_access"])
            self.assertEqual("DESIGN_ONLY", workflow["state"])
            self.assertTrue(workflow["middleware_route"].startswith("/v2/automation/beyvra/"))
            self.assertTrue(workflow["command_types"])
            for command in workflow["command_types"]:
                self.assertTrue(command.startswith("beyvra.operations."))

    def test_branch_map_contains_postly_and_beyvra_contracts(self) -> None:
        stack = {(row["repository"], row["branch"]) for row in self.branches["contract_stack"]}
        self.assertIn(
            ("appolon1908-hue/klyrow.com", "integration/codestra-email-fabric-v2"),
            stack,
        )
        self.assertIn(
            ("appolon1908-hue/social.codestra.co", "integration/n8n-postly-automation-v2-20260827"),
            stack,
        )
        self.assertIn(
            ("appolon1908-hue/beyvra-backend", "integration/n8n-automation-v2-20260827"),
            stack,
        )
        self.assertIn(
            ("appolon1908-hue/beyvra-frontend", "integration/automation-status-ui-v2-20260827"),
            stack,
        )
        self.assertIn(
            "automation/beyvra-operations-v2-20260827", self.branches["n8n_branches"]
        )
        self.assertIn(
            "automation/provisioning-v2-20260827", self.branches["n8n_branches"]
        )

    def test_each_enterprise_system_has_an_individual_branch_lane(self) -> None:
        expected = {
            "automation/odoo-crm-v2-20260827",
            "automation/vicidial-telephony-v2-20260827",
            "automation/telnexa-sms-v2-20260827",
            "automation/klyrow-email-v2-20260827",
            "automation/kyqra-crawler-v2-20260827",
            "automation/postly-social-v2-20260827",
            "automation/provisioning-v2-20260827",
            "automation/moneybee-loans-v2-20260827",
            "automation/beyvra-operations-v2-20260827",
            "automation/larim-a-booking-v2-20260827",
            "automation/freight-operations-v2-20260827",
            "automation/breero-marketplace-v2-20260827",
            "automation/booked4seasons-v2-20260827",
            "automation/trading-operations-v2-20260827",
        }
        workflow_packs = load("config/workflow-packs.v2.json")
        pack_branches = {row["branch"] for row in workflow_packs["packs"]}

        self.assertTrue(expected <= set(self.branches["n8n_branches"]))
        self.assertTrue(expected <= pack_branches)

    def test_every_business_system_denies_direct_n8n_access(self) -> None:
        service_rows = load("config/services.json")["services"]
        services = {row["id"]: row for row in service_rows}
        direct_allowed = [
            row["id"]
            for row in service_rows
            if row["access_from_n8n"] != "DENY_DIRECT"
        ]
        self.assertEqual(["codestra-middleware"], direct_allowed)
        for service_id in {
            "odoo-19",
            "vicidial",
            "jasmin",
            "postal-klyrow",
            "klyrow-smtp",
            "kyqra",
            "postly-social",
            "moneybee",
            "beyvra",
            "larim-a",
            "freight-platform",
            "breero",
            "booked4seasons",
            "trading-platform",
            "codestra-provisioning",
            "nats",
            "temporal",
        }:
            self.assertEqual("DENY_DIRECT", services[service_id]["access_from_n8n"])
            self.assertFalse(services[service_id]["direct_database_access"])

    def test_klyrow_email_smtp_connection_is_explicit(self) -> None:
        repositories = {row["id"]: row for row in self.layer["repositories"]}
        services = {row["id"]: row for row in load("config/services.json")["services"]}
        self.assertEqual("appolon1908-hue/klyrow.com", repositories["klyrow"]["repo"])
        self.assertEqual("integration/codestra-email-fabric-v2", repositories["klyrow"]["branch"])
        self.assertEqual(
            "email-and-smtp-domain-authority-through-middleware-only",
            repositories["klyrow"]["role"],
        )
        self.assertEqual(["codestra-middleware"], self.layer["network_policy"]["outbound_targets_from_n8n"])
        self.assertNotIn("klyrow", self.layer["network_policy"]["outbound_targets_from_n8n"])
        self.assertNotIn("klyrow-smtp", self.layer["network_policy"]["outbound_targets_from_n8n"])
        self.assertIn("klyrow-smtp", self.layer["network_policy"]["prohibited_direct_targets"])
        self.assertEqual("DENY_DIRECT", services["postal-klyrow"]["access_from_n8n"])
        self.assertEqual("DENY_DIRECT", services["klyrow-smtp"]["access_from_n8n"])

    def test_active_lease_context_is_required_for_steps_and_commands(self) -> None:
        operations = {
            (row["method"], row["path"]): row for row in self.policy["operations"]
        }
        steps = operations[("POST", "/v2/automation/jobs/{job_id}/steps")]
        commands = operations[("POST", "/v2/automation/commands")]
        self.assertIn("lease_token", steps["required_fields"])
        self.assertIn("execution_id", steps["required_fields"])
        for field in (
            "job_id",
            "lease_token",
            "execution_id",
            "workflow_key",
            "workflow_version",
            "step_key",
        ):
            self.assertIn(field, commands["required_fields"])


class Stage4OrchestrationTemplateTests(unittest.TestCase):
    def test_cp_workflow_groups_are_present_inactive_and_middleware_only(self) -> None:
        required_groups = {
            "CP-COMMON-ERROR-*",
            "CP-ODOO-*",
            "CP-TELNEXA-*",
            "CP-KLYROW-*",
            "CP-KYQRA-*",
            "CP-VICIDIAL-*",
            "CP-POSTLY-*",
            "CP-PROVISIONING-*",
        }
        templates = sorted((ROOT / "workflows" / "_templates").glob("*.json"))
        workflows = [json.loads(path.read_text(encoding="utf-8")) for path in templates]
        by_group = {
            workflow.get("meta", {}).get("codestra", {}).get("workflow_group"): workflow
            for workflow in workflows
        }
        self.assertTrue(required_groups <= set(by_group))

        for group in required_groups:
            workflow = by_group[group]
            codestra = workflow["meta"]["codestra"]
            self.assertFalse(workflow["active"])
            self.assertNotIn("credentials", workflow)
            self.assertEqual("MIDDLEWARE_ONLY", codestra["network_policy"])
            self.assertEqual("NO_CREDENTIALS", codestra["credential_binding"])
            self.assertEqual("N8N_CREDENTIAL_STORE_ONLY", codestra["credentials_location"])
            self.assertFalse(codestra["direct_service_access"])
            if group != "CP-COMMON-ERROR-*":
                self.assertIn("CP-COMMON-ERROR-HANDLER", codestra["depends_on"])
            for node in workflow["nodes"]:
                if node.get("type") != "n8n-nodes-base.httpRequest":
                    continue
                url = node["parameters"]["url"]
                parsed = urlsplit(url)
                self.assertTrue(node["disabled"])
                self.assertEqual("middleware.invalid", parsed.hostname)
                self.assertTrue(parsed.path.startswith("/v2/automation/"))


if __name__ == "__main__":
    unittest.main()
