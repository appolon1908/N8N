#!/usr/bin/env python3
"""Validate release-manifest assertions without claiming artifact verification."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from . import verify_release_manifest
except ImportError:  # Direct execution from the repository root.
    import verify_release_manifest  # type: ignore

ROOT = verify_release_manifest.ROOT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--target", choices=("staging", "production"), required=True)
    args = parser.parse_args()

    manifest_path = args.path if args.path.is_absolute() else ROOT / args.path
    if not manifest_path.exists():
        print("RELEASE_MANIFEST_SCHEMA_VALIDATION=FAIL")
        print(f"ERROR=release manifest does not exist: {manifest_path}")
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("RELEASE_MANIFEST_SCHEMA_VALIDATION=FAIL")
        print(f"ERROR=release manifest cannot be read: {type(exc).__name__}")
        return 1
    if not isinstance(manifest, dict):
        print("RELEASE_MANIFEST_SCHEMA_VALIDATION=FAIL")
        print("ERROR=release manifest must be a JSON object")
        return 1
    try:
        actual_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print("RELEASE_MANIFEST_SCHEMA_VALIDATION=FAIL")
        print(f"ERROR=checked-out Git SHA cannot be determined: {type(exc).__name__}")
        return 1

    errors = verify_release_manifest.validate(
        manifest, target=args.target, actual_sha=actual_sha
    )
    if errors:
        print("RELEASE_MANIFEST_SCHEMA_VALIDATION=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        return 1
    print("RELEASE_MANIFEST_SCHEMA_VALIDATION=PASS")
    print("EVIDENCE_ARTIFACT_VERIFICATION=NOT_PERFORMED_BY_THIS_VALIDATOR")
    print("DEPLOYMENT_PERFORMED=NO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
