#!/usr/bin/env python3
"""Read-only discovery of candidate n8n runtime paths and safe Docker metadata."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import socket
import stat
import subprocess
from pathlib import Path
from typing import Any

RELEVANT = ("n8n", "middleware", "caddy", "kong", "keycloak", "odoo", "redis", "postgres")
SEARCH_ROOTS = (Path("/root"), Path("/opt"), Path("/srv"), Path("/etc/codestra"))
COMPOSE_NAMES = {"compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}
PRUNE_DIRS = {".git", "node_modules", "__pycache__", ".cache", "overlay2", "containers"}


def run(command: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
            env={"PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")},
        )
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"unavailable: {type(exc).__name__}"


def machine_fingerprint() -> str | None:
    try:
        value = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def safe_path_metadata(path: Path, kind: str) -> dict[str, Any]:
    row: dict[str, Any] = {"kind": kind, "path": str(path)}
    try:
        details = path.lstat()
    except OSError as exc:
        row["stat_error"] = type(exc).__name__
        return row
    row.update(
        {
            "uid": details.st_uid,
            "gid": details.st_gid,
            "mode": f"{stat.S_IMODE(details.st_mode):04o}",
            "is_symlink": stat.S_ISLNK(details.st_mode),
            "device": details.st_dev,
            "inode": details.st_ino,
        }
    )
    return row


def find_candidates(max_depth: int = 5, max_results: int = 250) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        root_depth = len(root.parts)
        for current, directories, filenames in os.walk(root, topdown=True, onerror=lambda _: None):
            current_path = Path(current)
            depth = len(current_path.parts) - root_depth
            directories[:] = [
                name for name in directories if name not in PRUNE_DIRS and depth < max_depth
            ]
            for name in filenames:
                lowered = name.lower()
                if lowered in COMPOSE_NAMES or (
                    lowered.startswith("compose.") and lowered.endswith((".yml", ".yaml"))
                ):
                    results.append(safe_path_metadata(current_path / name, "compose-candidate"))
            for name in directories:
                if name in {".n8n", "n8n_data", "n8n-data"}:
                    results.append(
                        safe_path_metadata(current_path / name, "n8n-directory-candidate")
                    )
            if len(results) >= max_results:
                return sorted(results, key=lambda row: (row["kind"], row["path"]))
    return sorted(results, key=lambda row: (row["kind"], row["path"]))


def image_repo_digests(image_id: str | None) -> list[str]:
    if not image_id:
        return []
    code, output = run(["docker", "image", "inspect", image_id], timeout=15)
    if code != 0:
        return []
    try:
        rows = json.loads(output)
        return sorted(rows[0].get("RepoDigests") or [])
    except (json.JSONDecodeError, IndexError, KeyError, TypeError):
        return []


def docker_inventory() -> dict[str, Any]:
    code, output = run(["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}"])
    if code != 0:
        return {"available": False, "error": output, "containers": []}

    containers: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        container_id, name, image, status = parts
        if not any(token in f"{name} {image}".lower() for token in RELEVANT):
            continue
        inspect_code, inspect_output = run(["docker", "inspect", container_id], timeout=15)
        row: dict[str, Any] = {
            "id": container_id,
            "name": name,
            "image_from_ps": image,
            "status": status,
        }
        if inspect_code == 0:
            try:
                raw = json.loads(inspect_output)[0]
                config = raw.get("Config", {})
                host_config = raw.get("HostConfig", {})
                state = raw.get("State", {})
                labels = config.get("Labels") or {}
                safe_label_names = (
                    "com.docker.compose.project",
                    "com.docker.compose.project.working_dir",
                    "com.docker.compose.project.config_files",
                    "com.docker.compose.service",
                    "org.opencontainers.image.created",
                    "org.opencontainers.image.revision",
                    "org.opencontainers.image.source",
                    "org.opencontainers.image.version",
                )
                image_id = raw.get("Image")
                row.update(
                    {
                        "image": config.get("Image"),
                        "image_id": image_id,
                        "image_repo_digests": image_repo_digests(image_id),
                        "configured_user": config.get("User"),
                        "readonly_rootfs": host_config.get("ReadonlyRootfs"),
                        "privileged": host_config.get("Privileged"),
                        "cap_drop": sorted(host_config.get("CapDrop") or []),
                        "security_opt": sorted(host_config.get("SecurityOpt") or []),
                        "restart_policy": (host_config.get("RestartPolicy") or {}).get("Name"),
                        "apparmor_profile": raw.get("AppArmorProfile"),
                        "health_status": (state.get("Health") or {}).get("Status"),
                        "compose_labels": {
                            key: labels[key] for key in safe_label_names if key in labels
                        },
                        "mounts": [
                            {
                                "type": mount.get("Type"),
                                "source": mount.get("Source"),
                                "destination": mount.get("Destination"),
                                "rw": mount.get("RW"),
                            }
                            for mount in raw.get("Mounts", [])
                        ],
                        "networks": sorted(
                            (raw.get("NetworkSettings", {}).get("Networks") or {}).keys()
                        ),
                        "container_port_keys": sorted(
                            (raw.get("NetworkSettings", {}).get("Ports") or {}).keys()
                        ),
                    }
                )
            except (json.JSONDecodeError, IndexError, KeyError, TypeError) as exc:
                row["inspect_error"] = type(exc).__name__
        else:
            row["inspect_error"] = inspect_output
        containers.append(row)
    return {"available": True, "containers": containers}


def os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
            values[key.lower()] = value.strip().strip('"')
    return values


def main() -> None:
    _, addresses = run(["hostname", "-I"])
    report = {
        "audit_version": "1.1",
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": "READ_ONLY_NO_SECRET_CONTENT",
        "mutation_performed": False,
        "host": {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "addresses": addresses.split() if addresses and not addresses.startswith("unavailable") else [],
            "machine_fingerprint_sha256_prefix": machine_fingerprint(),
            "uid": os.getuid(),
            "gid": os.getgid(),
            "kernel_release": platform.release(),
            "architecture": platform.machine(),
            "os_release": os_release(),
        },
        "docker": docker_inventory(),
        "path_candidates": find_candidates(),
        "manual_follow_up_required": [
            "confirm n8n version from immutable image digest",
            "confirm n8n edition and licensed feature availability",
            "confirm reverse-proxy and middleware endpoint ownership",
            "confirm secret-provider references without collecting secret values",
            "confirm PostgreSQL and n8n-state backup destinations",
        ],
        "excluded": [
            "container environment variables",
            "secret contents",
            "database queries",
            "workflow data",
            "container logs",
            "customer data",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
