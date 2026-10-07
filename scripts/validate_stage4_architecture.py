#!/usr/bin/env python3
"""Structural Stage 4 workflow architecture gate."""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import validate_workflows

CP_GROUPS = {"CP-COMMON-ERROR-*", "CP-ODOO-*", "CP-TELNEXA-*", "CP-KLYROW-*", "CP-KYQRA-*", "CP-VICIDIAL-*", "CP-POSTLY-*", "CP-PROVISIONING-*"}
ERROR_KEY = "CP-COMMON-ERROR-HANDLER"

def check(path: Path, policy: dict) -> list[str]:
    errors = validate_workflows.validate(path, policy)
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return errors
    meta = data.get("meta", {}).get("codestra", {})
    group = meta.get("workflow_group")
    if group not in CP_GROUPS and path.name.startswith(("cp-", "00-cp-")):
        errors.append("unsupported CP workflow group")
    if group in CP_GROUPS - {"CP-COMMON-ERROR-*"} and ERROR_KEY not in meta.get("depends_on", []):
        errors.append("missing CP-COMMON-ERROR dependency")
    if group in CP_GROUPS - {"CP-COMMON-ERROR-*"}:
        blob = json.dumps(data)
        for required in ("Idempotency-Key", "$execution.id", '"dry_run", "value": true'):
            if required.lower() not in blob.lower(): errors.append(f"missing contract marker: {required}")
    if group == "CP-COMMON-ERROR-*":
        contract = set(meta.get("preserves", []))
        required = {"correlation_id", "workflow_id", "execution_id", "tenant_context", "campaign_context"}
        if not required <= contract: errors.append("common error preservation contract incomplete")
        if meta.get("retry_classification") is not True: errors.append("common error retry classification missing")
        if meta.get("recursive_error_guard") is not True: errors.append("common error recursion guard missing")
        if meta.get("unrecoverable_route") != "MIDDLEWARE_DLQ": errors.append("common error DLQ route missing")
    return errors

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("directory", nargs="?", type=Path, default=Path("workflows")); ns=ap.parse_args()
    policy=validate_workflows.load_policy(); failures=0; files=sorted(ns.directory.rglob("*.json"))
    for path in files:
        errs=check(path, policy)
        if errs:
            failures += 1
            for err in errs: print(f"ERROR={path}:{err}")
        else: print(f"STAGE4_PASS={path}")
    print(f"INVALID_WORKFLOW_JSON=0" if all(not e.startswith("cannot parse") for p in files for e in check(p,policy)) else "INVALID_WORKFLOW_JSON>0")
    print("ARCHITECTURE_VALIDATION=" + ("FAIL" if failures else "PASS"))
    return bool(failures)
if __name__ == "__main__": sys.exit(main())
