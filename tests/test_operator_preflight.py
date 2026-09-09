import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ops.check_n8n_operator_preflight import (
    INSTALLATIONS, RULE, collect, inspect_file, read_source_bytes, report,
)


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

    def test_source_bytes_bind_to_selected_historical_commit(self):
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.root, check=True,
                                  capture_output=True).stdout.strip().decode('ascii')

        git('init')
        git('config', 'user.name', 'Preflight test')
        git('config', 'user.email', 'preflight@example.invalid')
        git('config', 'commit.gpgsign', 'false')
        self.path.write_bytes(b'first revision\r\n')
        git('add', 'fixture')
        git('commit', '-m', 'first revision')
        selected = git('rev-parse', 'HEAD')
        self.path.write_bytes(b'second revision\n')
        git('add', 'fixture')
        git('commit', '-m', 'second revision')
        with patch('ops.check_n8n_operator_preflight.ROOT', self.root):
            self.assertEqual(read_source_bytes(selected, 'fixture'), b'first revision\r\n')
            with self.assertRaises(OSError):
                read_source_bytes(selected, 'missing')

    def test_source_lookup_failure_is_redacted_and_stops_inventory(self):
        with patch('ops.check_n8n_operator_preflight.source_identity',
                   return_value={'status': 'PASS'}), patch(
                       'ops.check_n8n_operator_preflight.read_source_bytes',
                       side_effect=OSError('PRIVATE_ERROR_DO_NOT_OUTPUT')), patch(
                       'ops.check_n8n_operator_preflight.inspect_file') as inspect:
            result = collect('a' * 40)
        inspect.assert_not_called()
        self.assertEqual(result['installation_preflight'], 'BLOCKED')
        self.assertNotIn('PRIVATE_ERROR', str(result))

    def test_git_timeout_fails_closed_without_raw_error(self):
        with patch('ops.check_n8n_operator_preflight.subprocess.run',
                   side_effect=subprocess.TimeoutExpired('PRIVATE_COMMAND', 15)):
            with self.assertRaisesRegex(OSError, '^SOURCE_UNREADABLE$'):
                read_source_bytes('a' * 40, 'fixture')

    def test_collect_uses_commit_policy_bytes_for_comparison_and_syntax(self):
        selected = 'a' * 40

        def source_bytes(sha, source):
            self.assertEqual(sha, selected)
            return (RULE + '\n').encode() if source == INSTALLATIONS[1][1] else b'fixture'

        with patch('ops.check_n8n_operator_preflight.source_identity',
                   return_value={'status': 'PASS'}), patch(
                       'ops.check_n8n_operator_preflight.read_source_bytes',
                       side_effect=source_bytes), patch(
                       'ops.check_n8n_operator_preflight.inspect_file',
                       return_value={'status': 'PASS'}) as inspect, patch(
                       'ops.check_n8n_operator_preflight.run_check',
                       return_value=subprocess.CompletedProcess([], 0)), patch.object(
                       Path, 'read_bytes', side_effect=AssertionError('worktree read')), patch.object(
                       Path, 'read_text', side_effect=AssertionError('worktree read')):
            result = collect(selected)
        self.assertEqual(result['installation_preflight'], 'PASS')
        self.assertEqual(result['checks']['source_artifacts']['reason'], 'EXACT_COMMIT_BLOBS')
        policy_calls = [call for call in inspect.call_args_list
                        if str(call.args[0]) == INSTALLATIONS[1][2]]
        self.assertEqual(policy_calls[0].kwargs['expected'], (RULE + '\n').encode())
