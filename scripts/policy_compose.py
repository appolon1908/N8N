"""Semantic fail-closed checks for the non-applying n8n Compose template."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CI_ENV = ROOT / "deploy" / "env" / "ci.env"
PROFILE = "staging-after-runtime-verification"
EXPECTED_SERVICES = {"n8n-main", "n8n-worker"}
EXPECTED_SECRETS = {"n8n_encryption_key", "postgres_password", "redis_password"}
IMAGE_BY_DIGEST = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")

REQUIRED_STATIC_TOKENS = {
    "${N8N_IMAGE:?": "explicit immutable image input",
    PROFILE: "verification-only profile",
    "${N8N_DATA_VOLUME:?": "verified external data-volume input",
    "${MIDDLEWARE_NETWORK:?": "verified private-network input",
}
PROHIBITED_SOURCE_PATTERNS = (
    (r"^\s*ports:\s*$", "host-published ports"),
    (r"^\s*privileged:\s*true\s*$", "privileged containers"),
    (r"^\s*(?:network_mode|pid|ipc):\s*host\s*$", "host namespace access"),
    (r"docker\.sock", "Docker socket mount"),
    (r"^\s*env_file:\s*", "unreviewed env_file loading"),
    (r"^\s*build:\s*", "source image build"),
    (r"image:\s*[^\n]+:latest(?:\s|$)", "mutable latest image tag"),
)
REQUIRED_COMMON_ENV = {
    "DB_TYPE": "postgresdb",
    "DB_POSTGRESDB_PASSWORD_FILE": "/run/secrets/postgres_password",
    "EXECUTIONS_MODE": "queue",
    "OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS": "true",
    "N8N_DEFAULT_BINARY_DATA_MODE": "database",
    "QUEUE_BULL_REDIS_PASSWORD_FILE": "/run/secrets/redis_password",
    "N8N_ENCRYPTION_KEY_FILE": "/run/secrets/n8n_encryption_key",
    "N8N_PORT": "5678",
    "N8N_PROTOCOL": "https",
    "N8N_PROXY_HOPS": "1",
    "N8N_SECURE_COOKIE": "true",
    "N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS": "true",
    "N8N_BLOCK_ENV_ACCESS_IN_NODE": "true",
    "N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES": "true",
    "N8N_RESTRICT_FILE_ACCESS_TO": "/tmp/n8n-files",
    "N8N_GIT_NODE_DISABLE_BARE_REPOS": "true",
    "N8N_GIT_NODE_ENABLE_HOOKS": "false",
    "N8N_PUBLIC_API_DISABLED": "true",
    "N8N_PUBLIC_API_SWAGGERUI_DISABLED": "true",
    "N8N_HIRING_BANNER_ENABLED": "false",
    "N8N_DIAGNOSTICS_ENABLED": "false",
    "N8N_PERSONALIZATION_ENABLED": "false",
    "N8N_VERSION_NOTIFICATIONS_ENABLED": "false",
    "N8N_TEMPLATES_ENABLED": "false",
    "N8N_COMMUNITY_PACKAGES_ENABLED": "false",
    "NODE_FUNCTION_ALLOW_BUILTIN": "",
    "NODE_FUNCTION_ALLOW_EXTERNAL": "",
    "EXECUTIONS_DATA_SAVE_ON_SUCCESS": "none",
    "EXECUTIONS_DATA_SAVE_ON_ERROR": "all",
    "EXECUTIONS_DATA_PRUNE": "true",
    "EXECUTIONS_DATA_MAX_AGE": "168",
    "N8N_METRICS": "true",
    "N8N_METRICS_INCLUDE_QUEUE_METRICS": "true",
    "N8N_GRACEFUL_SHUTDOWN_TIMEOUT": "30",
    "N8N_LOG_LEVEL": "info",
}
REQUIRED_DYNAMIC_ENV = {
    "DB_POSTGRESDB_HOST",
    "DB_POSTGRESDB_PORT",
    "DB_POSTGRESDB_DATABASE",
    "DB_POSTGRESDB_USER",
    "QUEUE_BULL_REDIS_HOST",
    "QUEUE_BULL_REDIS_PORT",
    "N8N_HOST",
    "WEBHOOK_URL",
    "N8N_EDITOR_BASE_URL",
    "NODES_EXCLUDE",
}


def _names(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value)
    if not isinstance(value, list):
        return set()
    names: set[str] = set()
    for item in value:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            source = item.get("source") or item.get("target") or item.get("name")
            if isinstance(source, str):
                names.add(source)
    return names


def _mount_present(service: dict[str, Any], source: str, target: str) -> bool:
    for mount in service.get("volumes") or []:
        if isinstance(mount, str):
            if mount == f"{source}:{target}":
                return True
            continue
        if not isinstance(mount, dict):
            continue
        if mount.get("source") == source and mount.get("target") == target:
            return mount.get("type") in {None, "volume"}
    return False


def _health_contains(service: dict[str, Any], expected: str) -> bool:
    test = (service.get("healthcheck") or {}).get("test")
    if isinstance(test, list):
        return expected in " ".join(str(value) for value in test)
    return expected in str(test or "")


def render_compose(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    command = [
        "docker",
        "compose",
        "--env-file",
        str(CI_ENV),
        "--profile",
        PROFILE,
        "-f",
        str(path),
        "config",
        "--format",
        "json",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, [f"Compose semantic rendering unavailable: {type(exc).__name__}"]
    if result.returncode != 0:
        return None, [f"Compose semantic rendering failed with exit code {result.returncode}"]
    try:
        model = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, ["Compose semantic rendering did not return valid JSON"]
    if not isinstance(model, dict):
        return None, ["Compose semantic rendering did not return an object"]
    return model, []


def validate_rendered_compose(model: dict[str, Any], excluded_nodes: list[str]) -> list[str]:
    errors: list[str] = []
    services = model.get("services")
    if not isinstance(services, dict):
        return ["rendered Compose model has no services object"]
    if set(services) != EXPECTED_SERVICES:
        errors.append(
            "rendered Compose services must be exactly: " + ", ".join(sorted(EXPECTED_SERVICES))
        )

    volume = (model.get("volumes") or {}).get("n8n_data")
    if not isinstance(volume, dict) or volume.get("external") is not True:
        errors.append("n8n_data must be an externally provisioned Compose volume")
    network = (model.get("networks") or {}).get("middleware_network")
    if not isinstance(network, dict) or network.get("external") is not True:
        errors.append("middleware_network must be an externally provisioned Compose network")
    top_secrets = model.get("secrets") or {}
    if not isinstance(top_secrets, dict) or set(top_secrets) != EXPECTED_SECRETS:
        errors.append("rendered Compose secrets must be exactly the reviewed three secret aliases")
    else:
        for name in EXPECTED_SECRETS:
            if not isinstance(top_secrets.get(name), dict) or top_secrets[name].get("external") is not True:
                errors.append(f"Compose secret {name} must be external")

    for service_name in sorted(EXPECTED_SERVICES):
        service = services.get(service_name)
        if not isinstance(service, dict):
            errors.append(f"rendered Compose model lacks service {service_name}")
            continue
        image = service.get("image")
        if not isinstance(image, str) or not IMAGE_BY_DIGEST.fullmatch(image):
            errors.append(f"service {service_name} image is not an immutable SHA-256 digest")
        if service.get("read_only") is not True:
            errors.append(f"service {service_name} must use a read-only root filesystem")
        if service.get("user") != "1000:1000":
            errors.append(f"service {service_name} must run as numeric non-root user 1000:1000")
        if service.get("restart") != "no":
            errors.append(f"service {service_name} must remain non-autostarting in source scaffold")
        if service.get("privileged") not in (None, False):
            errors.append(f"service {service_name} must not be privileged")
        if service.get("ports"):
            errors.append(f"service {service_name} must not publish host ports")
        if PROFILE not in set(service.get("profiles") or []):
            errors.append(f"service {service_name} lacks the verified-staging profile gate")
        if "ALL" not in {str(value).upper() for value in service.get("cap_drop") or []}:
            errors.append(f"service {service_name} must drop all Linux capabilities")
        if "no-new-privileges:true" not in set(service.get("security_opt") or []):
            errors.append(f"service {service_name} must enable no-new-privileges")
        if _names(service.get("networks")) != {"middleware_network"}:
            errors.append(f"service {service_name} must attach only to middleware_network")
        if _names(service.get("secrets")) != EXPECTED_SECRETS:
            errors.append(f"service {service_name} must mount exactly the reviewed secrets")
        if not _mount_present(service, "n8n_data", "/home/node/.n8n"):
            errors.append(f"service {service_name} lacks the reviewed n8n_data mount")

        environment = service.get("environment")
        if not isinstance(environment, dict):
            errors.append(f"service {service_name} has no rendered environment map")
            continue
        for name, expected in REQUIRED_COMMON_ENV.items():
            if str(environment.get(name, "")) != expected:
                errors.append(f"service {service_name} requires {name}={expected!r}")
        missing_dynamic = sorted(name for name in REQUIRED_DYNAMIC_ENV if not environment.get(name))
        if missing_dynamic:
            errors.append(
                f"service {service_name} lacks required rendered environment keys: "
                + ", ".join(missing_dynamic)
            )
        try:
            excluded = set(json.loads(str(environment.get("NODES_EXCLUDE", "[]"))))
        except (json.JSONDecodeError, TypeError):
            excluded = set()
        missing_nodes = sorted(set(excluded_nodes) - excluded)
        if missing_nodes:
            errors.append(
                f"service {service_name} NODES_EXCLUDE misses: " + ", ".join(missing_nodes)
            )

    main = services.get("n8n-main") if isinstance(services.get("n8n-main"), dict) else {}
    worker = services.get("n8n-worker") if isinstance(services.get("n8n-worker"), dict) else {}
    if not _health_contains(main, "http://127.0.0.1:5678/healthz/readiness"):
        errors.append("n8n-main lacks the reviewed readiness probe")
    worker_env = worker.get("environment") if isinstance(worker, dict) else {}
    if not isinstance(worker_env, dict) or worker_env.get("QUEUE_HEALTH_CHECK_ACTIVE") != "true":
        errors.append("n8n-worker must enable its queue health endpoint")
    if not isinstance(worker_env, dict) or worker_env.get("QUEUE_HEALTH_CHECK_PORT") != "5680":
        errors.append("n8n-worker must use the dedicated queue health port 5680")
    if not _health_contains(worker, "http://127.0.0.1:5680/healthz/readiness"):
        errors.append("n8n-worker lacks the reviewed database/Redis readiness probe")
    command = worker.get("command") if isinstance(worker, dict) else None
    if "worker" not in " ".join(str(value) for value in command or []):
        errors.append("n8n-worker command does not start a worker process")
    return errors


def validate_compose(path: Path, excluded_nodes: list[str]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors = [
        f"Compose template lacks {label}"
        for token, label in REQUIRED_STATIC_TOKENS.items()
        if token not in text
    ]
    for pattern, label in PROHIBITED_SOURCE_PATTERNS:
        if re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE):
            errors.append(f"Compose template contains prohibited {label}")
    model, render_errors = render_compose(path)
    errors.extend(render_errors)
    if model is not None:
        errors.extend(validate_rendered_compose(model, excluded_nodes))
    return errors
