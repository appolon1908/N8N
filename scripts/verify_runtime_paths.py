#!/usr/bin/env python3
"""Validate the reviewed runtime-path state file without touching the target host."""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import posixpath
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,511}$")
SAFE_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:@+-]{0,255}$")
HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
MODE = re.compile(r"^[0-7]{3,4}$")
ALLOWED_PATH_STATES = {"UNVERIFIED", "CANDIDATE", "VERIFIED"}
ALLOWED_SERVER_STATES = {"UNVERIFIED", "CANDIDATE", "VERIFIED"}
FILESYSTEM_KINDS = {"directory", "file", "file-or-directory"}
PATH_OR_REFERENCE_KINDS = {"directory-or-volume", "directory-or-object-store"}
REFERENCE_KINDS = {"secret-provider-reference"}
ALLOWED_KINDS = FILESYSTEM_KINDS | PATH_OR_REFERENCE_KINDS | REFERENCE_KINDS


def non_placeholder_sha256(value: Any) -> bool:
    text = str(value or "")
    return bool(SHA256.fullmatch(text)) and set(text) != {"0"}


def parse_iso8601(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def meaningful_identity(value: Any) -> bool:
    return isinstance(value, str) and bool(SAFE_IDENTITY.fullmatch(value.strip()))


def valid_filesystem_path(expected: str) -> bool:
    if not expected.startswith("/") or expected.startswith("//"):
        return False
    if any(character in expected for character in ("\n", "\r", "\x00", "\\")):
        return False
    parts = PurePosixPath(expected).parts
    if ".." in parts or "." in parts:
        return False
    return posixpath.normpath(expected) == expected


def valid_reference(expected: str) -> bool:
    return bool(SAFE_REFERENCE.fullmatch(expected)) and ".." not in expected.split("/")


def valid_expected(kind: Any, expected: Any) -> bool:
    if not isinstance(kind, str) or not isinstance(expected, str) or not expected:
        return False
    if any(character in expected for character in ("\n", "\r", "\x00")):
        return False
    if kind in FILESYSTEM_KINDS:
        return valid_filesystem_path(expected)
    if kind in PATH_OR_REFERENCE_KINDS:
        return valid_filesystem_path(expected) if expected.startswith("/") else valid_reference(expected)
    if kind in REFERENCE_KINDS:
        return valid_reference(expected)
    return False


def valid_owner(value: Any) -> bool:
    if isinstance(value, int):
        return value >= 0
    return meaningful_identity(value)


def validate(data: dict[str, Any], *, require_verified: bool) -> list[str]:
    errors: list[str] = []
    status = data.get("status")
    if status not in {"UNVERIFIED", "VERIFIED"}:
        errors.append(f"invalid overall status {status!r}")

    verified_by = data.get("verified_by")
    independent_reviewer = data.get("independent_reviewer")
    seen: set[str] = set()
    path_rows = data.get("paths", [])
    if not isinstance(path_rows, list) or not path_rows:
        errors.append("runtime path list is missing or empty")
        path_rows = []

    for row in path_rows:
        if not isinstance(row, dict):
            errors.append("runtime path row is not an object")
            continue
        path_id = row.get("id")
        if not isinstance(path_id, str) or not path_id or path_id in seen:
            errors.append(f"duplicate or missing path id {path_id!r}")
        if isinstance(path_id, str):
            seen.add(path_id)
        if row.get("required") is not True:
            errors.append(f"path {path_id} must explicitly declare required=true")
        kind = row.get("kind")
        if kind not in ALLOWED_KINDS:
            errors.append(f"path {path_id} has unsupported kind {kind!r}")
        row_status = row.get("status")
        if row_status not in ALLOWED_PATH_STATES:
            errors.append(f"path {path_id} has invalid status {row_status!r}")
        expected = row.get("expected")
        if expected is not None and not valid_expected(kind, expected):
            errors.append(f"path {path_id} has an invalid expected value for kind {kind!r}")
        if row_status == "CANDIDATE" and not expected:
            errors.append(f"candidate path {path_id} has no expected value")
        if row_status == "VERIFIED":
            if not expected:
                errors.append(f"verified path {path_id} has no expected value")
            if not non_placeholder_sha256(row.get("evidence_sha256")):
                errors.append(f"verified path {path_id} lacks a non-placeholder evidence SHA-256")
            if not valid_owner(row.get("owner")):
                errors.append(f"verified path {path_id} lacks a valid owner")
            if kind in FILESYSTEM_KINDS and not MODE.fullmatch(str(row.get("mode") or "")):
                errors.append(f"verified filesystem path {path_id} lacks a valid octal mode")

    server = data.get("server", {})
    if not isinstance(server, dict):
        errors.append("server record is missing")
        server = {}
    server_status = server.get("status")
    if server_status not in ALLOWED_SERVER_STATES:
        errors.append(f"server has invalid status {server_status!r}")
    for field in ("expected_public_ip", "expected_private_ip"):
        value = server.get(field)
        if value:
            try:
                ipaddress.ip_address(value)
            except ValueError:
                errors.append(f"server {field} is not a valid IP address")

    claimed_verified = status == "VERIFIED"
    if require_verified and not claimed_verified:
        errors.append("runtime paths are not VERIFIED")

    if claimed_verified:
        verified_at = parse_iso8601(data.get("verified_at"))
        if verified_at is None:
            errors.append("verified runtime state requires a timezone-aware verified_at timestamp")
        elif verified_at > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
            errors.append("verified_at cannot be materially in the future")
        if not meaningful_identity(verified_by):
            errors.append("verified runtime state requires a valid verified_by identity")
        if not meaningful_identity(independent_reviewer):
            errors.append("verified runtime state requires a valid independent_reviewer identity")
        if (
            meaningful_identity(verified_by)
            and meaningful_identity(independent_reviewer)
            and verified_by.strip().casefold() == independent_reviewer.strip().casefold()
        ):
            errors.append("runtime verifier and independent reviewer must be different")
        if not non_placeholder_sha256(data.get("evidence_sha256")):
            errors.append("verified runtime state requires a non-placeholder evidence SHA-256")
        hostname = server.get("expected_hostname")
        if server_status != "VERIFIED" or not isinstance(hostname, str) or not HOSTNAME.fullmatch(hostname):
            errors.append("verified runtime state requires a verified valid server hostname")
        if not non_placeholder_sha256(server.get("evidence_sha256")):
            errors.append("verified server identity requires an evidence SHA-256")
        for row in path_rows:
            if not isinstance(row, dict):
                continue
            if row.get("required") and row.get("status") != "VERIFIED":
                errors.append(f"required path {row.get('id')} is not VERIFIED")
            if row.get("required") and not row.get("expected"):
                errors.append(f"required path {row.get('id')} has no expected value")
    elif status == "UNVERIFIED":
        for field in ("verified_at", "verified_by", "independent_reviewer", "evidence_sha256"):
            if data.get(field) is not None:
                errors.append(f"unverified runtime state must not claim {field}")
        if server_status == "VERIFIED" or server.get("evidence_sha256") is not None:
            errors.append("unverified runtime state must not claim verified server evidence")
        if any(row.get("status") == "VERIFIED" for row in path_rows if isinstance(row, dict)):
            errors.append("unverified runtime state must not contain verified paths")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--allow-unverified", action="store_true")
    group.add_argument("--require-verified", action="store_true")
    args = parser.parse_args()

    path = ROOT / "config" / "runtime-paths.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("RUNTIME_PATH_VALIDATION=FAIL")
        print(f"ERROR=runtime path state cannot be read: {exc}")
        return 1
    if not isinstance(data, dict):
        print("RUNTIME_PATH_VALIDATION=FAIL")
        print("ERROR=runtime path state must be a JSON object")
        return 1
    errors = validate(data, require_verified=args.require_verified)

    if errors:
        print("RUNTIME_PATH_VALIDATION=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        return 1
    print("RUNTIME_PATH_VALIDATION=PASS")
    print(f"RUNTIME_PATHS={data.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
