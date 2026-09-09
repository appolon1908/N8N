import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ops.check_n8n_operator_preflight import collect, inspect_file, report


class OperatorPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'fixture'
        self.path.write_bytes(b'nonsecret fixture')
        self.path.chmod(0o600)

    def test_matching_bytes_and_mode_pass(self):
        result = inspect_file(self.path, modes={0o600}, expected=b'nonsecret fixture')
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(len(result['sha256']), 64)

    def test_changed_bytes_and_mode_block(self):
        self.assertEqual(inspect_file(self.path, expected=b'other')['reason'],
                         'CONTENT_MISMATCH')
        self.assertEqual(inspect_file(self.path, modes={0o400})['reason'],
                         'MODE_MISMATCH')

    def test_missing_empty_and_symlink_block(self):
        self.assertEqual(inspect_file(self.root / 'missing')['reason'], 'MISSING')
        self.path.write_bytes(b'')
        self.assertEqual(inspect_file(self.path)['reason'], 'EMPTY_FILE')
        link = self.root / 'link'
        link.symlink_to(self.path)
        self.assertEqual(inspect_file(link)['status'], 'BLOCKED')

    def test_symlink_parent_and_fifo_block_without_hanging(self):
        link = self.root / 'directory-link'
        link.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(inspect_file(link / 'fixture')['reason'], 'SYMLINK_PARENT')
        fifo = self.root / 'pipe'
        os.mkfifo(fifo)
        self.assertEqual(inspect_file(fifo)['reason'], 'NOT_REGULAR_FILE')

    def test_configuration_contents_are_never_reported(self):
        self.path.write_bytes(b'PRIVATE_CONFIG_VALUE_DO_NOT_OUTPUT')
        result = inspect_file(self.path, modes={0o600})
        self.assertNotIn('PRIVATE_CONFIG_VALUE', str(result))
        self.assertNotIn('sha256', result)

    def test_source_mismatch_stops_before_host_inventory(self):
        with patch('ops.check_n8n_operator_preflight.source_identity',
                   return_value={'status': 'BLOCKED'}), patch(
                       'ops.check_n8n_operator_preflight.inspect_file') as inspect:
            result = collect('a' * 40)
        inspect.assert_not_called()
        self.assertEqual(result['installation_preflight'], 'BLOCKED')

    def test_installation_success_does_not_certify_any_issue(self):
        result = report({'fixture': {'status': 'PASS'}})
        self.assertEqual(result['installation_preflight'], 'PASS')
        for name in ('database', 'deploy_key', 'middleware'):
            self.assertEqual(result[name + '_certification'], 'NOT_RUN')
        self.assertFalse(result['runtime_mutation_performed'])
