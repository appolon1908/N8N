"""Validate the prepared-but-not-applied n8n Community runtime contract."""

from __future__ import annotations

from typing import Any

try:
    from .policy_common import string_set, valid_https_base
    from .policy_n8n import REQUIRED_DANGEROUS_NODES
except ImportError:  # Direct script execution through sibling entry points.
    from policy_common import string_set, valid_https_base  # type: ignore
    from policy_n8n import REQUIRED_DANGEROUS_NODES  # type: ignore

EXPECTED_REPOSITORIES = {
    "runtime": "appolon1908-hue/N8N",
    "edge": "appolon1908-hue/Caddy",
    "gateway": "appolon1908-hue/Kong",
    "identity": "appolon1908-hue/Keycloak",
    "write_boundary": "appolon1908-hue/Middleware-",
}
WRITE_HEADERS = frozenset(
    {
        "Authorization",
        "X-Tenant-ID",
        "X-Request-ID",
        "X-Correlation-ID",
        "Idempotency-Key",
    }
)
READ_HEADERS = frozenset(
    {
        "Authorization",
        "X-Tenant-ID",
        "X-Request-ID",
        "X-Correlation-ID",
    }
)
EXPECTED_ROUTES = {
    ("POST", "/v2/automation/jobs/claim", "automation.job.claim", WRITE_HEADERS),
    ("GET", "/v2/automation/jobs/{job_id}", "automation.job.read", READ_HEADERS),
    (
        "POST",
        "/v2/automation/jobs/{job_id}/heartbeat",
        "automation.job.heartbeat",
        WRITE_HEADERS,
    ),
    (
        "POST",
        "/v2/automation/jobs/{job_id}/steps",
        "automation.job.step.write",
        WRITE_HEADERS,
    ),
    (
        "POST",
        "/v2/automation/jobs/{job_id}/complete",
        "automation.job.complete",
        WRITE_HEADERS,
    ),
    (
        "POST",
        "/v2/automation/jobs/{job_id}/fail",
        "automation.job.fail",
        WRITE_HEADERS,
    ),
    ("POST", "/v2/automation/commands", "automation.command.crm", WRITE_HEADERS),
    (
        "GET",
        "/v2/automation/commands/{command_id}",
        "automation.command.read",
        READ_HEADERS,
    ),
    (
        "POST",
        "/v2/automation/approvals",
        "automation.approval.request",
        WRITE_HEADERS,
    ),
    (
        "GET",
        "/v2/automation/approvals/{approval_id}",
        "automation.approval.read",
        READ_HEADERS,
    ),
    (
        "POST",
        "/v2/automation/dead-letters/{dead_letter_id}/replay",
        "automation.operations.replay.request",
        WRITE_HEADERS,
    ),
    (
        "POST",
        "/v2/automation/jobs/reconcile",
        "automation.operations.reconcile",
        WRITE_HEADERS,
    ),
    (
        "GET",
        "/v2/automation/capabilities/{capability}",
        "automation.capability.read",
        READ_HEADERS,
    ),
    (
        "POST",
        "/api/v1/integrations/n8n/results",
        "n8n.results.submit",
        WRITE_HEADERS,
    ),
    (
        "GET",
        "/api/v1/integrations/n8n/results/{event_id}",
        "n8n.results.read",
        READ_HEADERS,
    ),
}
EXPECTED_CREDENTIAL_SCOPES = {route[2] for route in EXPECTED_ROUTES}
EXPECTED_ALLOWED_HOSTNAMES = {"api.codestra.co", "auth.codestra.co"}
EXPECTED_BLOCKED_IP_RANGES = {"0.0.0.0/0", "::/0"}
EXPECTED_EGRESS_ALLOW_RULES = {
    "middleware-gateway": {
        "id": "middleware-gateway",
        "protocol": "tcp",
        "port": 443,
        "destination_dns": "api.codestra.co",
    },
    "keycloak-token": {
        "id": "keycloak-token",
        "protocol": "tcp",
        "port": 443,
        "destination_dns": "auth.codestra.co",
        "application_path": "/realms/codestra/protocol/openid-connect/token",
    },
    "postgres": {
        "id": "postgres",
        "protocol": "tcp",
        "destination_source": "POSTGRES_HOST",
        "port_source": "POSTGRES_PORT",
    },
    "redis": {
        "id": "redis",
        "protocol": "tcp",
        "destination_source": "REDIS_HOST",
        "port_source": "REDIS_PORT",
    },
    "dns": {
        "id": "dns",
        "protocol": "udp+tcp",
        "port": 53,
        "destination_source": "RUNTIME_APPROVED_DNS_RESOLVERS",
    },
}
REQUIRED_DENY_CATEGORIES = {
    "arbitrary-public-internet",
    "direct-odoo",
    "direct-provider-apis",
    "direct-keycloak-admin",
    "cloud-metadata",
    "unapproved-private-networks",
    "unapproved-databases",
}


def _version_tuple(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _non_placeholder_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
        and set(value) != {"0"}
    )


def _route_set(
    routes: Any,
) -> set[tuple[str, str, str, frozenset[str]]] | None:
    if not isinstance(routes, list):
        return None
    parsed: set[tuple[str, str, str, frozenset[str]]] = set()
    for row in routes:
        if not isinstance(row, dict):
            return None
        headers = string_set(row.get("required_headers"))
        if headers is None:
            return None
        method = row.get("method")
        path = row.get("path")
        scope = row.get("scope")
        if not all(
            isinstance(value, str) and value for value in (method, path, scope)
        ):
            return None
        parsed.add((method, path, scope, frozenset(headers)))
    return parsed


def validate_community_runtime_policy(
    canonical_policy: dict[str, Any],
    runtime: dict[str, Any],
    egress: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    if runtime.get("schema_version") != "1.0":
        errors.append("community runtime schema_version must be 1.0")
    if runtime.get("contract_id") != "codestra.n8n-community-runtime":
        errors.append("community runtime contract_id is invalid")
    if runtime.get("status") != "PREPARED_NOT_APPLIED":
        errors.append("community runtime must remain PREPARED_NOT_APPLIED")
    if runtime.get("edition") != "community":
        errors.append("community runtime must declare edition=community")
    if runtime.get("repositories") != EXPECTED_REPOSITORIES:
        errors.append(
            "community runtime repository authorities differ from reviewed topology"
        )
    if runtime.get("activation_authorized") is not False:
        errors.append("community runtime source must not authorize activation")
    if runtime.get("minimum_runtime_version") != "2.32.1":
        errors.append(
            "community runtime minimum security baseline must be 2.32.1"
        )

    runtime_image = runtime.get("runtime_image")
    if not isinstance(runtime_image, dict):
        errors.append("community runtime image evidence section is missing")
    else:
        if runtime_image.get("minimum_runtime_version") != runtime.get(
            "minimum_runtime_version"
        ):
            errors.append(
                "community runtime image evidence must bind the minimum version"
            )
        image_status = runtime_image.get("status")
        if image_status not in {"UNVERIFIED", "VERIFIED"}:
            errors.append("community runtime image evidence status is invalid")
        approved_version = runtime_image.get("approved_image_version")
        minimum = _version_tuple(runtime.get("minimum_runtime_version"))
        approved = _version_tuple(approved_version)
        if image_status == "UNVERIFIED":
            for field in (
                "approved_image",
                "approved_image_version",
                "image_digest_evidence_sha256",
                "version_evidence_sha256",
            ):
                if runtime_image.get(field) is not None:
                    errors.append(
                        f"unverified runtime image evidence must not claim {field}"
                    )
        if image_status == "VERIFIED":
            if approved is None or minimum is None or approved < minimum:
                errors.append(
                    "verified runtime image version is below the required minimum"
                )
            if not _non_placeholder_sha256(
                runtime_image.get("image_digest_evidence_sha256")
            ):
                errors.append(
                    "verified runtime image requires digest evidence SHA-256"
                )
            if not _non_placeholder_sha256(
                runtime_image.get("version_evidence_sha256")
            ):
                errors.append(
                    "verified runtime image requires version evidence SHA-256"
                )

    endpoint = runtime.get("endpoint")
    if not isinstance(endpoint, dict):
        errors.append("community runtime endpoint section is missing")
    else:
        if endpoint.get(
            "base_url"
        ) != "https://api.codestra.co" or not valid_https_base(
            endpoint.get("base_url")
        ):
            errors.append(
                "community runtime must use the fixed HTTPS Middleware gateway"
            )
        if endpoint.get("fixed_https_gateway") is not True:
            errors.append(
                "community runtime fixed HTTPS gateway flag is not true"
            )
        if (
            endpoint.get("direct_private_middleware_listener_allowed")
            is not False
        ):
            errors.append(
                "community runtime must deny direct private Middleware listeners"
            )
        if endpoint.get("direct_provider_endpoints_allowed") is not False:
            errors.append(
                "community runtime must deny direct provider endpoints"
            )
        if _route_set(endpoint.get("routes")) != EXPECTED_ROUTES:
            errors.append(
                "community runtime Middleware route contract differs from reviewed routes"
            )

    credential = runtime.get("credential")
    expected_credential = {
        "owner": "codestra-n8n-service-owner",
        "personal_account_allowed": False,
        "name": "Codestra Middleware Service",
        "type": "oAuth2Api",
        "grant_type": "clientCredentials",
        "keycloak_client_id": "n8n-automation",
        "token_url": (
            "https://auth.codestra.co/realms/codestra/"
            "protocol/openid-connect/token"
        ),
        "audience": "middleware-api",
        "secret_source": "root-owned-bootstrap-secret-files",
        "secret_material_in_repository": False,
        "secret_material_in_workflow_json": False,
    }
    if not isinstance(credential, dict):
        errors.append("community runtime credential section is missing")
    else:
        for field, expected in expected_credential.items():
            if credential.get(field) != expected:
                errors.append(
                    f"community runtime credential {field} differs from reviewed policy"
                )
        if string_set(credential.get("scopes")) != EXPECTED_CREDENTIAL_SCOPES:
            errors.append(
                "community runtime credential scopes differ from reviewed policy"
            )

    editor = runtime.get("editor")
    expected_editor = {
        "strategy": "caddy-oauth2-proxy-keycloak-plus-native-owner",
        "issuer": "https://auth.codestra.co/realms/codestra",
        "authorization_code_flow": True,
        "pkce_method": "S256",
        "native_owner_login_required": True,
        "native_owner_identity": "codestra-n8n-service-owner",
        "enterprise_sso_required": False,
        "direct_n8n_public_exposure": False,
        "caddy_contract_path": "config/n8n-editor-community.v1.json",
    }
    if not isinstance(editor, dict):
        errors.append("community runtime editor section is missing")
    else:
        for field, expected in expected_editor.items():
            if editor.get(field) != expected:
                errors.append(
                    f"community runtime editor {field} differs from reviewed policy"
                )
        if string_set(editor.get("required_any_roles")) != {
            "n8n_operator",
            "n8n_admin",
        }:
            errors.append(
                "community runtime editor roles differ from reviewed policy"
            )

    security = runtime.get("security")
    expected_security = {
        "environment_access_in_nodes": False,
        "public_api_enabled": False,
        "code_node_enabled": False,
        "community_packages_enabled": False,
    }
    if not isinstance(security, dict):
        errors.append("community runtime security section is missing")
    else:
        for field, expected in expected_security.items():
            if security.get(field) is not expected:
                errors.append(
                    f"community runtime security requires {field}={expected!r}"
                )
        if (
            string_set(security.get("dangerous_nodes_excluded"))
            != REQUIRED_DANGEROUS_NODES
        ):
            errors.append(
                "community runtime dangerous-node exclusions differ from reviewed policy"
            )

    runtime_egress = runtime.get("egress")
    expected_runtime_egress = {
        "policy_path": "deploy/egress/n8n-egress-policy.v1.json",
        "default_action": "DENY",
        "runtime_network_enforcement_required": True,
        "n8n_ssrf_protection_enabled": True,
        "evidence_required_before_verified": True,
    }
    if not isinstance(runtime_egress, dict):
        errors.append("community runtime egress section is missing")
    else:
        for field, expected in expected_runtime_egress.items():
            if runtime_egress.get(field) != expected:
                errors.append(
                    f"community runtime egress {field} differs from reviewed policy"
                )
        if (
            string_set(runtime_egress.get("allowed_https_hostnames"))
            != EXPECTED_ALLOWED_HOSTNAMES
        ):
            errors.append(
                "community runtime HTTPS egress allowlist differs from reviewed policy"
            )
        if (
            string_set(runtime_egress.get("blocked_ip_ranges"))
            != EXPECTED_BLOCKED_IP_RANGES
        ):
            errors.append(
                "community runtime SSRF blocked ranges differ from reviewed policy"
            )

    operations = runtime.get("operations")
    if not isinstance(operations, dict):
        errors.append("community runtime operations section is missing")
    else:
        if operations.get("active_workflows") != 0:
            errors.append("community runtime must keep active_workflows=0")
        if operations.get("external_effects_enabled") is not False:
            errors.append(
                "community runtime must keep external effects disabled"
            )
        if operations.get("production_changed") is not False:
            errors.append(
                "community runtime must not claim production changes"
            )

    if (
        egress.get("schema_version") != "1.0"
        or egress.get("policy_id") != "codestra.n8n-egress"
    ):
        errors.append("n8n egress policy identity is invalid")
    if egress.get("status") != "PREPARED_NOT_APPLIED":
        errors.append("n8n egress policy must remain PREPARED_NOT_APPLIED")
    if string_set(egress.get("source_services")) != {"n8n-main", "n8n-worker"}:
        errors.append(
            "n8n egress policy source services differ from reviewed Compose services"
        )
    if egress.get("default_action") != "DENY":
        errors.append("n8n egress policy must default deny")
    if string_set(egress.get("enforcement_layers")) != {
        "n8n-ssrf",
        "runtime-network-firewall",
    }:
        errors.append(
            "n8n egress enforcement layers differ from reviewed policy"
        )

    app_ssrf = egress.get("application_ssrf")
    expected_env = {
        "N8N_SSRF_PROTECTION_ENABLED": "true",
        "N8N_SSRF_ALLOWED_HOSTNAMES": (
            "api.codestra.co,auth.codestra.co"
        ),
        "N8N_SSRF_BLOCKED_IP_RANGES": "0.0.0.0/0,::/0",
    }
    if not isinstance(app_ssrf, dict):
        errors.append("n8n application SSRF policy is missing")
    else:
        if app_ssrf.get("enabled") is not True:
            errors.append("n8n application SSRF protection must be enabled")
        if (
            string_set(app_ssrf.get("allowed_hostnames"))
            != EXPECTED_ALLOWED_HOSTNAMES
        ):
            errors.append(
                "n8n application SSRF hostname allowlist differs from reviewed policy"
            )
        if (
            string_set(app_ssrf.get("blocked_ip_ranges"))
            != EXPECTED_BLOCKED_IP_RANGES
        ):
            errors.append(
                "n8n application SSRF blocked ranges differ from reviewed policy"
            )
        if app_ssrf.get("environment") != expected_env:
            errors.append(
                "n8n application SSRF environment differs from reviewed Compose policy"
            )

    network = egress.get("runtime_network")
    if not isinstance(network, dict):
        errors.append("n8n runtime network policy is missing")
    else:
        if network.get("required_before_verification") is not True:
            errors.append(
                "n8n runtime network enforcement must be required before verification"
            )
        if network.get("evidence_sha256") is not None:
            errors.append(
                "prepared n8n egress policy must not claim runtime evidence"
            )
        allow = network.get("allow")
        if not isinstance(allow, list) or any(
            not isinstance(row, dict) for row in allow
        ):
            errors.append(
                "n8n runtime egress allow rules are missing or malformed"
            )
        else:
            allow_by_id = {row.get("id"): row for row in allow}
            if len(allow_by_id) != len(
                allow
            ) or allow_by_id != EXPECTED_EGRESS_ALLOW_RULES:
                errors.append(
                    "n8n runtime egress allow rules differ from reviewed policy"
                )
        denied = string_set(network.get("deny_categories"))
        if denied is None or not REQUIRED_DENY_CATEGORIES.issubset(denied):
            errors.append(
                "n8n runtime egress deny categories are incomplete"
            )

    if egress.get("secret_material_in_policy") is not False:
        errors.append("n8n egress policy must not contain secret material")
    if egress.get("runtime_apply_authorized") is not False:
        errors.append("n8n egress source must not authorize runtime apply")

    desired = canonical_policy.get("desired_state")
    if not isinstance(desired, dict):
        errors.append(
            "canonical n8n policy does not consume the community runtime contract"
        )
    else:
        cross_checks = {
            "status": runtime.get("status"),
            "edition": runtime.get("edition"),
            "runtime_contract_path": "config/n8n-community-runtime.v1.json",
            "egress_policy_path": (
                runtime_egress or {}
            ).get("policy_path")
            if isinstance(runtime_egress, dict)
            else None,
            "endpoint_base_url": (
                endpoint or {}
            ).get("base_url")
            if isinstance(endpoint, dict)
            else None,
            "credential_name": (
                credential or {}
            ).get("name")
            if isinstance(credential, dict)
            else None,
            "credential_owner": (
                credential or {}
            ).get("owner")
            if isinstance(credential, dict)
            else None,
            "editor_strategy": (
                editor or {}
            ).get("strategy")
            if isinstance(editor, dict)
            else None,
            "egress_default_action": egress.get("default_action"),
            "activation_authorized": runtime.get("activation_authorized"),
        }
        for field, expected in cross_checks.items():
            if desired.get(field) != expected:
                errors.append(
                    f"canonical n8n desired_state does not bind {field}"
                )
        if (
            string_set(desired.get("dangerous_nodes_excluded"))
            != REQUIRED_DANGEROUS_NODES
        ):
            errors.append(
                "canonical n8n desired_state does not bind dangerous-node exclusions"
            )

    if canonical_policy.get("status") == "VERIFIED":
        policy_endpoint = canonical_policy.get("endpoint_binding")
        policy_credential = canonical_policy.get("credential_binding")
        policy_editor = canonical_policy.get("editor_access")
        if (
            not isinstance(policy_endpoint, dict)
            or policy_endpoint.get("approved_base_url")
            != (endpoint or {}).get("base_url")
        ):
            errors.append(
                "verified n8n endpoint binding must match the community runtime gateway"
            )
        if (
            not isinstance(policy_endpoint, dict)
            or policy_endpoint.get("production_strategy")
            != "verified-fixed-private-dns"
        ):
            errors.append(
                "verified n8n endpoint binding must use the fixed gateway strategy"
            )
        if (
            not isinstance(policy_credential, dict)
            or policy_credential.get("approved_names")
            != [(credential or {}).get("name")]
        ):
            errors.append(
                "verified n8n credential binding must match the service-owned credential"
            )
        if (
            not isinstance(policy_credential, dict)
            or policy_credential.get("approved_types")
            != [(credential or {}).get("type")]
        ):
            errors.append(
                "verified n8n credential type must match the community runtime credential"
            )
        if (
            not isinstance(policy_editor, dict)
            or policy_editor.get("strategy")
            != "verified-gateway-oidc-and-native-auth"
        ):
            errors.append(
                "verified n8n editor access must use gateway OIDC plus native auth"
            )
        if (
            not isinstance(policy_editor, dict)
            or policy_editor.get("publicly_routable") is not False
        ):
            errors.append(
                "verified n8n editor access must remain non-public"
            )
        if (
            not isinstance(runtime_image, dict)
            or runtime_image.get("status") != "VERIFIED"
        ):
            errors.append(
                "verified n8n policy requires verified runtime image evidence"
            )

    return errors
