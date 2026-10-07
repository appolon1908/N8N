from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from scripts import audit_runtime_drift, validate_stage4_architecture, validate_workflows

ROOT=Path(__file__).resolve().parents[1]
class Stage4Tests(unittest.TestCase):
    def test_committed_cp_workflows_pass(self):
        policy=validate_workflows.load_policy()
        for p in (ROOT/"workflows/_templates").glob("*cp-*.json"):
            self.assertEqual([],validate_stage4_architecture.check(p,policy),p)
    def test_drift_audit_is_read_only_and_detects_provider(self):
        with tempfile.TemporaryDirectory() as td:
            runtime=Path(td); before=list(runtime.iterdir())
            (runtime/"compose.yaml").write_text("URL: http://odoo:8069\n")
            errors, report=audit_runtime_drift.audit(ROOT,runtime)
            self.assertTrue(errors); self.assertTrue(report["direct_provider_urls"])
            self.assertEqual({"compose.yaml"},{p.name for p in runtime.iterdir()})
class CommonErrorTests(unittest.TestCase):
    def test_common_error_contract(self):
        d=json.loads((ROOT/"workflows/_templates/00-cp-common-error-handler.v1.json").read_text())
        meta=d["meta"]["codestra"]
        self.assertEqual("MIDDLEWARE_DLQ",meta["unrecoverable_route"])
        self.assertFalse(d["active"])

class CpOdooRuntimeShapeTests(unittest.TestCase):
    def test_cp_odoo_exercises_full_middleware_lifecycle(self):
        d=json.loads((ROOT/"workflows/_templates/cp-odoo-crm-state-sync.v1.json").read_text())
        urls=[
            node.get("parameters",{}).get("url","")
            for node in d["nodes"]
            if node.get("type") == "n8n-nodes-base.httpRequest"
        ]
        body=json.dumps(d)
        for marker in (
            "/v2/automation/jobs/claim",
            "/heartbeat",
            "/steps",
            "/v2/automation/commands",
            "/v2/automation/commands/",
            "/complete",
            "/fail",
        ):
            self.assertIn(marker, body)
        for url in urls:
            self.assertIn("middleware.invalid", url)
        self.assertEqual(
            ["claim", "heartbeat", "record-step", "command", "read-command", "complete-or-fail"],
            d["meta"]["codestra"]["runtime_sequence"],
        )

class CpKlyrowRuntimeShapeTests(unittest.TestCase):
    def test_cp_klyrow_separates_email_smtp_and_events_through_middleware(self):
        d=json.loads((ROOT/"workflows/_templates/cp-klyrow-email-dispatch.v1.json").read_text())
        body=json.dumps(d)
        for marker in (
            "email.klyrow.send",
            "email.klyrow.smtp-relay",
            "email.klyrow.event",
            "KLYROW_THROUGH_MIDDLEWARE",
            "KLYROW_SMTP_RELAY_THROUGH_MIDDLEWARE",
        ):
            self.assertIn(marker, body)
        for node in d["nodes"]:
            if node.get("type") != "n8n-nodes-base.httpRequest":
                continue
            self.assertTrue(node["disabled"])
            self.assertEqual("https://middleware.invalid/v2/automation/commands", node["parameters"]["url"])
