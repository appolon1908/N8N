.PHONY: validate repository policy-tests workflows secrets compose runtime-status ruleset-contract

validate: repository policy-tests workflows secrets compose runtime-status ruleset-contract

repository:
	python3 scripts/validate_repository.py

policy-tests:
	python3 -m unittest discover -s tests -p 'test_*.py'

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
