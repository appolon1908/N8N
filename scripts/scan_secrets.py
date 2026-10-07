#!/usr/bin/env python3
"""Conservative repository secret scan with no network or third-party dependency."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
GITHUB_TOKEN = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")
SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")
ASSIGNMENT = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])(password|passwd|secret|token|api[_-]?key|client[_-]?secret)\b"
    r"\s*[:=]\s*[\"']?([^\s\"',#]{6,})"
)
ALLOWED_PREFIXES = ("${", "__", "<", "UNSET", "NOT_", "REPLACE", "ci-", "example-", "placeholder")
SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__"}


def candidate_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.name == "scan_secrets.py" or path.stat().st_size > 1_000_000:
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()

    findings: list[str] = []
    for path in candidate_files(args.root.resolve()):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(args.root.resolve())
        for line_number, line in enumerate(text.splitlines(), start=1):
            if PRIVATE_KEY.search(line):
                findings.append(f"{relative}:{line_number}:private-key material")
            if AWS_KEY.search(line):
                findings.append(f"{relative}:{line_number}:AWS access key")
            if GITHUB_TOKEN.search(line):
                findings.append(f"{relative}:{line_number}:GitHub token")
            if SLACK_TOKEN.search(line):
                findings.append(f"{relative}:{line_number}:Slack token")
            for match in ASSIGNMENT.finditer(line):
                value = match.group(2)
                if value.lower() in {"true", "false", "null", "none"}:
                    continue
                if value.startswith(ALLOWED_PREFIXES):
                    continue
                findings.append(
                    f"{relative}:{line_number}:possible assigned secret for {match.group(1)}"
                )

    if findings:
        print("SECRET_SCAN=FAIL")
        for finding in findings:
            print(f"ERROR={finding}")
        return 1
    print("SECRET_SCAN=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
