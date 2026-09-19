"""The prepared N8N → Middleware V3 automation mapping stays dark and covers the surface.

contracts/middleware-v3-automation-mapping.v1.json records, for every operation of
middleware-surface.v1.json, whether it is executor transport the V3 N8N adapter
reuses, a workflow primitive that stays, or a call that maps onto a V3 kernel route.
Until the Middleware V3 route contract is frozen no workflow may target a kernel
route, and N8N never gains provider or Odoo business-effect access.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "contracts" / "middleware-v3-automation-mapping.v1.json"
SURFACE = ROOT / "contracts" / "middleware-surface.v1.json"
CONTROL_PLANE = ROOT / "contracts" / "platform-control-plane.v1.json"
KERNEL = {
    "submit": ("POST", "/platform/v1/commands"),
    "status": ("GET", "/platform/v1/operations/{operation_id}"),
    "timeline": ("GET", "/platform/v1/operations/{operation_id}/timeline"),
    "cancel": ("POST", "/platform/v1/operations/{operation_id}/cancel"),
    "replay": ("POST", "/platform/v1/operations/{operation_id}/replay"),
    "describe": ("GET", "/platform/v1/kernel/describe"),
}
STATES = {"EXECUTOR_TRANSPORT_REUSED", "STAYS_WORKFLOW_PRIMITIVE", "MAPS_TO_V3_SUBMIT", "MAPS_TO_V3_STATUS", "MAPS_TO_V3_REPLAY", "MAPS_TO_V3_DESCRIBE"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class MiddlewareV3AutomationMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapping = load(MAPPING)
        self.surface = load(SURFACE)

    def test_mapping_is_dark_and_extends_the_surface(self) -> None:
        mapping = self.mapping
        self.assertEqual(mapping["status"], "V3_PENDING_FINAL_MIDDLEWARE_CONTRACT")
        self.assertTrue(mapping["V3_PENDING_FINAL_MIDDLEWARE_CONTRACT"])
        self.assertFalse(mapping["runtime_apply_authorized"])
        self.assertEqual(mapping["extends"], SURFACE.name)
        self.assertEqual(mapping["authority"]["gateway_host"], self.surface["production_gateway_host"])
        self.assertEqual(mapping["authority"]["canonical_upstream"], "middleware-integration-api:8095")
        self.assertIn("appolon-middleware-integration-api", mapping["authority"]["retired_upstream_aliases"])
        self.assertEqual(mapping["activation"]["blocked_on"], "BLOCKED_ON_MIDDLEWARE_V3_FINAL_SHA")
        for key, (method, path) in KERNEL.items():
            with self.subTest(route=key):
                self.assertEqual((mapping["v3_kernel_routes"][key]["method"], mapping["v3_kernel_routes"][key]["path"]), (method, path))

    def test_every_surface_operation_is_mapped_exactly_once(self) -> None:
        surface_ops = {(o["method"], o["path"]) for o in self.surface["operations"]}
        mapped = [(o["method"], o["path"]) for o in self.mapping["operations"]]
        self.assertEqual(len(mapped), len(set(mapped)), "duplicate mapping rows")
        self.assertEqual(set(mapped), surface_ops)
        kernel_routes = {f"{m} {p}" for m, p in KERNEL.values()}
        for row in self.mapping["operations"]:
            with self.subTest(op=f"{row['method']} {row['path']}"):
                self.assertIn(row["v3_state"], STATES)
                if row["v3_state"].startswith("MAPS_TO_V3"):
                    self.assertIn(row["v3_route"], kernel_routes)
                else:
                    self.assertIsNone(row["v3_route"])
        submit = next(r for r in self.mapping["operations"] if r["path"] == self.surface["command_endpoint"] and r["method"] == "POST")
        self.assertEqual(submit["v3_state"], "MAPS_TO_V3_SUBMIT")
        self.assertTrue(submit["effectful"])
        replay = next(r for r in self.mapping["operations"] if r["v3_state"] == "MAPS_TO_V3_REPLAY")
        self.assertEqual(replay["v3_route"], "POST /platform/v1/operations/{operation_id}/replay")
        self.assertEqual(self.mapping["identity"]["v3_replay_realm_role"], "platform-operator")

    def test_executor_transport_rows_match_the_transport_list(self) -> None:
        transport = set(self.mapping["executor_transport"]["operations"])
        rows = {f"{r['method']} {r['path']}" for r in self.mapping["operations"] if r["v3_state"] == "EXECUTOR_TRANSPORT_REUSED"}
        self.assertEqual(rows, transport)
        self.assertFalse(any(r["effectful"] for r in self.mapping["operations"] if r["v3_state"] == "EXECUTOR_TRANSPORT_REUSED"))

    def test_n8n_never_gains_provider_or_business_effect_access(self) -> None:
        prohibited = self.mapping["prohibited"]
        self.assertFalse(prohibited["n8n_to_provider_privileged_write"])
        self.assertFalse(prohibited["n8n_to_odoo_business_effect"])
        self.assertFalse(prohibited["workflow_targets_v3_kernel_before_freeze"])
        self.assertEqual(prohibited["legacy_command_paths"], self.surface["invariants"]["legacy_command_paths_prohibited"])
        self.assertFalse(self.surface["invariants"]["direct_business_system_access"])
        self.assertFalse(self.surface["safety"]["direct_provider_access"])
        self.assertFalse(self.surface["safety"]["ODOO_WRITE"])

    def test_no_workflow_targets_a_kernel_route_before_the_freeze(self) -> None:
        for directory in ("workflows", "automations"):
            base = ROOT / directory
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.json")):
                text = path.read_text(encoding="utf-8", errors="replace")
                with self.subTest(workflow=path.relative_to(ROOT).as_posix()):
                    self.assertNotIn("/platform/v1/commands", text)
                    self.assertNotIn("/platform/v1/operations", text)
                    self.assertNotIn("/platform/v1/kernel", text)
                    self.assertNotIn("appolon-middleware-integration-api", text)

    def test_client_id_discrepancy_is_recorded_not_hidden(self) -> None:
        identity = self.mapping["identity"]
        control_plane = load(CONTROL_PLANE)
        self.assertEqual(identity["control_plane_contract_client_id"], control_plane["n8n_to_middleware"]["client_id"])
        self.assertEqual(identity["audience"], control_plane["n8n_to_middleware"]["audience"])
        self.assertNotEqual(identity["keycloak_client_id"], identity["control_plane_contract_client_id"])
        self.assertIn("Owner decision required", identity["client_id_discrepancy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
