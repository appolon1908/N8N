.PHONY: validate repository catalog-reconciliation operator-adoption deploy-key-bootstrap policy-tests workflows secrets compose runtime-status ruleset-contract platform-control-plane v2-client-cells

validate: repository catalog-reconciliation operator-adoption deploy-key-bootstrap policy-tests workflows secrets compose runtime-status ruleset-contract platform-control-plane v2-client-cells

repository:
	python3 scripts/validate_repository.py

catalog-reconciliation:
	python3 scripts/validate_catalog_reconciliation.py

operator-adoption:
	python3 scripts/validate_operator_adoption.py

deploy-key-bootstrap:
	python3 scripts/validate_ssh_deploy_key_bootstrap.py

policy-tests:
	python3 -m unittest tests.test_attest_n8n_policy tests.test_catalog_reconciliation tests.test_community_runtime_policy tests.test_compose_semantics tests.test_integration_contracts tests.test_middleware_surface tests.test_n8n_recovery_source tests.test_database_certifier tests.test_observability_authority tests.test_operator_adoption tests.test_ssh_deploy_key_bootstrap tests.test_policy_guards tests.test_ruleset_contract tests.test_runtime_node_denylist tests.test_runtime_path_audit tests.test_runtime_path_privileged_stat tests.test_shared_templates tests.test_umbrella_readback
	python3 scripts/validate_workflow_completeness.py
	./tests/test_n8n_recovery_contract.sh

workflows:
	python3 scripts/validate_workflows.py workflows

secrets:
	python3 scripts/scan_secrets.py .

compose:
	docker compose --env-file deploy/env/ci.env -f deploy/compose/compose.staging.yml config --quiet

runtime-status:
	python3 scripts/verify_runtime_paths.py --allow-unverified

ruleset-contract:
	python3 scripts/validate_ruleset_contract.py

platform-control-plane:
	python3 scripts/validate_platform_control_plane.py

v2-client-cells:
	python3 scripts/validate_v2_client_cells.py
	python3 -m unittest tests.test_v2_client_cells
