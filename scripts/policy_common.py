"""Shared strict validators for repository policy tooling."""

from __future__ import annotations

import datetime as dt
import ipaddress
import json
import posixpath
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:@+-]{0,255}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,255}$")


def load_json(path: str) -> Any:
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


def non_placeholder_sha256(value: Any) -> bool:
    text = str(value or "")
    return bool(SHA256.fullmatch(text)) and set(text) != {"0"}


def valid_iso8601(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def meaningful_identity(value: Any) -> bool:
    return isinstance(value, str) and bool(SAFE_IDENTITY.fullmatch(value.strip()))


def string_set(value: Any) -> set[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return set(value)


def valid_https_base(value: Any) -> bool:
    """Accept only canonical HTTPS DNS origins with an optional canonical base path."""
    if (
        not isinstance(value, str)
        or any(character in value for character in ("\n", "\r", "\x00", "\\", "%"))
        or any(character.isspace() for character in value)
    ):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    host = parsed.hostname.casefold()
    if host in {"localhost", "invalid"} or host.endswith(
        (".localhost", ".invalid", ".example", ".test")
    ):
        return False
    if not re.fullmatch(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
        host,
    ):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return False
    if port == 0:
        return False
    path = parsed.path.rstrip("/")
    return not path or (
        path.startswith("/")
        and ".." not in path.split("/")
        and posixpath.normpath(path) == path
    )
