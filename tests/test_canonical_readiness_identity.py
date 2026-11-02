"""Canonical rename preserves the exact reviewed reusable code and trust boundary."""
import unittest
from pathlib import Path
from scripts.policy_actions import validate_action_reference, reviewed_deploy_readiness_caller


class CanonicalReadinessIdentityTests(unittest.TestCase):
    canonical = 'appolon1908/Infustruction-repo/.github/workflows/reusable-codestra-deploy-readiness.yml'
    former = 'appolon1908-hue/Infustruction-repo/.github/workflows/reusable-codestra-deploy-readiness.yml'
    sha = '1b4a90810eb03db3eae2b676b2d418daa434ec16'

    def test_exact_same_code_at_canonical_repository_is_accepted(self):
        self.assertIsNone(validate_action_reference(self.canonical, self.sha))

    def test_former_namespace_is_replaced_instead_of_added(self):
        self.assertIsNotNone(validate_action_reference(self.former, self.sha))

    def test_unknown_workflow_or_revision_still_rejected(self):
        for action, revision in [(self.canonical, 'main'), (self.canonical, 'f' * 40),
                                 (self.canonical.replace('reusable-codestra-', 'unreviewed-'), self.sha)]:
            self.assertIsNotNone(validate_action_reference(action, revision))

    def test_reviewed_caller_only_accepts_the_canonical_exact_sha(self):
        path = Path('.github/workflows/codestra-deploy-readiness.yml')
        text = path.read_text()
        self.assertTrue(reviewed_deploy_readiness_caller(path, text))
        self.assertFalse(reviewed_deploy_readiness_caller(path, text.replace(self.canonical, self.former)))
        self.assertFalse(reviewed_deploy_readiness_caller(path, text.replace(self.sha, 'f' * 40)))


if __name__ == '__main__': unittest.main()
