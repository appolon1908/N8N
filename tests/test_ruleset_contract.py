from __future__ import annotations

import copy
import json
import unittest

from scripts import validate_ruleset_contract


class MainRulesetContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(
            validate_ruleset_contract.RULESET.read_text(encoding="utf-8")
        )

    def test_reviewed_contract_passes(self) -> None:
        self.assertEqual([], validate_ruleset_contract.validate(self.contract))

    def test_bypass_actor_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["bypass_actors"] = [{"actor_type": "RepositoryRole", "actor_id": 5}]
        errors = validate_ruleset_contract.validate(contract)
        self.assertTrue(any("no bypass actors" in error for error in errors))

    def test_stale_and_last_push_approval_cannot_be_disabled(self) -> None:
        contract = copy.deepcopy(self.contract)
        pull = next(rule for rule in contract["rules"] if rule["type"] == "pull_request")
        pull["parameters"]["dismiss_stale_reviews_on_push"] = False
        pull["parameters"]["require_last_push_approval"] = False
        errors = validate_ruleset_contract.validate(contract)
        self.assertTrue(any("dismiss_stale_reviews_on_push" in error for error in errors))
        self.assertTrue(any("require_last_push_approval" in error for error in errors))

    def test_status_check_must_be_exact_and_strict(self) -> None:
        contract = copy.deepcopy(self.contract)
        status = next(
            rule for rule in contract["rules"] if rule["type"] == "required_status_checks"
        )
        status["parameters"]["strict_required_status_checks_policy"] = False
        status["parameters"]["required_status_checks"] = [{"context": "some-other-check"}]
        errors = validate_ruleset_contract.validate(contract)
        self.assertTrue(any("up-to-date branch" in error for error in errors))
        self.assertTrue(any("exact-head validation context" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
