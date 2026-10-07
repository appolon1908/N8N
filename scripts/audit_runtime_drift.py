#!/usr/bin/env python3
"""Read-only comparison of a Git source tree and an n8n runtime directory."""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

PROVIDER = re.compile(r"https?://[^\s\"']*(?:odoo|telnexa|jasmin|klyrow|postal|kyqra|vicidial|postly)[^\s\"']*", re.I)
def digest(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()
def workflows(root: Path) -> dict[str,str]:
    out={}
    for p in root.rglob("*.json"):
        try:
            d=json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict): continue
            name=d.get("name")
            if isinstance(name,str) and "nodes" in d: out[name]=digest(p)
        except (OSError,json.JSONDecodeError): pass
    return out
def git_sha(root: Path) -> str:
    try: return subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError: return "NOT_A_GIT_CHECKOUT"
def audit(source: Path, runtime: Path) -> tuple[list[str],dict]:
    expected, actual=workflows(source),workflows(runtime); unsafe=[]
    only_git=sorted(expected.keys()-actual.keys()); only_runtime=sorted(actual.keys()-expected.keys())
    modified=sorted(k for k in expected.keys()&actual.keys() if expected[k]!=actual[k])
    provider=[]; active=[]; unresolved=[]
    for p in runtime.rglob("*"):
        if (not p.is_file() or p.stat().st_size>5_000_000 or p.name == ".env"
                or p.suffix == ".env" or "secrets" in p.parts): continue
        try: text=p.read_text(errors="replace")
        except OSError: continue
        provider += [f"{p}:{m.group(0)}" for m in PROVIDER.finditer(text)]
        if p.suffix==".json":
            try:
                d=json.loads(text)
                if not isinstance(d, dict): continue
                if d.get("active") is True: active.append(str(p))
                if "nodes" in d and any(n.get("credentials") in ({},None) for n in d.get("nodes",[]) if "credentials" in n): unresolved.append(str(p))
            except json.JSONDecodeError: pass
    security_source=(source/"config/n8n-security-policy.env.example").exists()
    security_runtime=any("NODES_EXCLUDE" in p.read_text(errors="replace") for p in runtime.rglob("*") if p.is_file() and p.stat().st_size<5_000_000 and p.name != ".env" and p.suffix != ".env" and "secrets" not in p.parts)
    if only_git or only_runtime or modified or provider or active or unresolved or not security_runtime: unsafe.append("unsafe runtime drift detected")
    report={"git_sha":git_sha(source),"expected_workflow_inventory":sorted(expected),"runtime_workflow_inventory":sorted(actual),"only_in_git":only_git,"only_in_runtime":only_runtime,"modified_workflow_hashes":modified,"compose_files":[str(p) for p in sorted(runtime.rglob("*compose*.y*ml"))],"security_policy_source":security_source,"security_policy_runtime":security_runtime,"direct_provider_urls":provider,"active_workflows":active,"unresolved_credential_references":unresolved}
    return unsafe,report
def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--source",type=Path,required=True); ap.add_argument("--runtime",type=Path,required=True); ns=ap.parse_args()
    errors,report=audit(ns.source.resolve(),ns.runtime.resolve()); print(json.dumps(report,indent=2)); print("RUNTIME_DRIFT="+("UNSAFE" if errors else "SAFE")); return bool(errors)
if __name__=="__main__": sys.exit(main())
