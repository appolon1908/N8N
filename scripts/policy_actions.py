"""GitHub Actions policy: reviewed code only, no mutation or privileged execution."""

from __future__ import annotations

import re
from pathlib import Path

HEX_SHA = re.compile(r"^[0-9a-f]{40}$")
USES_ANY = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")
USES_PINNED = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@([^\s#]+)")
ALLOWED_ACTIONS = {
    "actions/checkout": {"fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"},
}
BANNED_WORKFLOW_PATTERNS = {
    r"^\s*pull_request_target\s*:": "pull_request_target trigger",
    r"^\s*workflow_run\s*:": "privileged workflow chaining",
    r"\$\{\{\s*secrets\.": "repository or environment secret access",
    r"\$\{\{\s*github\.token\b": "automatic GitHub token expression access",
    r"^\s*permissions\s*:\s*write-all\s*(?:#.*)?$": "write-all GitHub token permission",
    r"^\s*permissions\s*:\s*\{[^}]*\bwrite\b": "inline write-scoped GitHub token permission",
    r"^\s*[a-z0-9_-]+\s*:\s*[\"']?write[\"']?\s*(?:#.*)?$": "write-scoped GitHub token permission",
    r"^\s*runs-on\s*:.*\bself-hosted\b": "self-hosted runner access",
    r"^\s*-\s*self-hosted\s*(?:#.*)?$": "self-hosted runner access",
    r"^\s*environment\s*:": "GitHub deployment environment access",
    r"^\s*container\s*:": "job container execution",
    r"^\s*services\s*:": "service container execution",
    r"^\s*continue-on-error\s*:\s*true\s*(?:#.*)?$": "validation bypass",
    r"^\s*submodules\s*:\s*(?:true|recursive)\s*(?:#.*)?$": "unreviewed Git submodules",
    r"^\s*lfs\s*:\s*true\s*(?:#.*)?$": "unreviewed Git LFS download",
    r"\b(?:curl|wget)\b": "network download command",
    r"\b(?:pip|pip3)\s+install\b": "runtime Python package installation",
    r"\bpython(?:3)?\s+-m\s+pip\s+install\b": "runtime Python package installation",
    r"\b(?:npm|pnpm|yarn)\s+(?:install|add)\b": "runtime JavaScript package installation",
    r"\bapt(?:-get)?\s+(?:install|update|upgrade)\b": "runtime OS package installation",
    r"\b(?:ssh|scp|rsync)\b": "remote host access",
    r"docker\s+(?:compose\s+up|stack\s+deploy|login|pull|build|buildx)\b": "Docker mutation",
    r"\bsystemctl\b": "service mutation",
    r"kubectl\s+(?:apply|delete|patch|replace)": "Kubernetes mutation",
    r"\bgit\s+push\b": "Git push",
    r"\bgh\s+(?:api|pr\s+merge|release\s+create)\b": "GitHub mutation",
    r"\b(?:cosign|oras)\s+(?:sign|push|attach)\b": "artifact mutation",
    r"docker\.sock": "Docker socket access",
}


def validate_action_reference(action: str, ref: str) -> str | None:
    allowed = ALLOWED_ACTIONS.get(action)
    if allowed is None:
        return f"external action {action!r} is not allowlisted"
    if not HEX_SHA.fullmatch(ref) or set(ref) == {"0"}:
        return f"action {action!r} is not pinned to a non-placeholder 40-character SHA"
    if ref not in allowed:
        return f"action {action!r} uses an unreviewed SHA {ref!r}"
    return None


def validate_workflow_files(directory: Path) -> list[str]:
    errors: list[str] = []
    paths = sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")])
    if not paths:
        return ["no GitHub Actions workflow files found"]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        label = str(path)
        if not re.search(r"^permissions:\s*$", text, flags=re.MULTILINE):
            errors.append(f"{label} lacks explicit top-level permissions")
        for number, line in enumerate(text.splitlines(), 1):
            if not USES_ANY.match(line):
                continue
            match = USES_PINNED.match(line)
            if not match:
                errors.append(f"{label}:{number} action reference is not SHA-pinned")
                continue
            problem = validate_action_reference(*match.groups())
            if problem:
                errors.append(f"{label}:{number} {problem}")
        lowered = text.lower()
        for pattern, description in BANNED_WORKFLOW_PATTERNS.items():
            if re.search(pattern, lowered, flags=re.MULTILINE):
                errors.append(f"{label} contains prohibited {description} capability")
        if "actions/checkout@" in text and "persist-credentials: false" not in text:
            errors.append(f"{label} checkout must disable persisted credentials")
    return errors
