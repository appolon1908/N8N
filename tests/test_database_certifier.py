"""Execute the wrapper against temporary files and non-effectful helper stubs."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DatabaseCertifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.stamp = '20260909T120000Z'
        self.backup = self.root / 'backup'
        self.artifact = self.backup / self.stamp
        self.artifact.mkdir(parents=True)
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.settings = {
            'CODESTRA_RELEASE_SHA': 'a' * 40,
            'CODESTRA_N8N_PRODUCTION_IMAGE_DIGEST': 'sha256:' + 'b' * 64,
            'CODESTRA_N8N_STAGING_IMAGE_DIGEST': 'sha256:' + 'c' * 64,
            'CODESTRA_DATABASE_BACKUP_GPG_HOME': '/fixture/gpg',
            'CODESTRA_DATABASE_BACKUP_GPG_SIGNING_FINGERPRINT': 'D' * 40,
            'N8N_RECOVERY_WORK_ROOT': '/fixture/work',
            'N8N_PRODUCTION_RESTORE_URL': 'postgresql://fixture@fixture/production_restore',
            'N8N_PRODUCTION_RESTORE_PGPASSFILE': '/fixture/production.pgpass',
            'N8N_STAGING_RESTORE_URL': 'postgresql://fixture@fixture/staging_restore',
            'N8N_STAGING_RESTORE_PGPASSFILE': '/fixture/staging.pgpass',
        }
        self.config = self.root / 'config'
        self.config.write_text(''.join(f'{k}={v}\n' for k, v in self.settings.items()))
        self.config.chmod(0o600)
        self.status = self.artifact / 'STATUS.txt'
        self.tuple_text = (
            'RELEASE_SHA=' + 'a' * 40 + '\n'
            'PRODUCTION_IMAGE_DIGEST=sha256:' + 'b' * 64 + '\n'
            'STAGING_IMAGE_DIGEST=sha256:' + 'c' * 64 + '\n'
        )
        self.status.write_text(self.tuple_text)
        archive = self.artifact / f'n8n-recovery-{self.stamp}.tar.gz.gpg'
        archive.write_bytes(b'nonsecret fixture, not a real backup')
        self.result = self.evidence / f'RESTORE-RESULT-{self.stamp}'
        self.result.write_text(self.tuple_text + 'TARGET_CLASS=ISOLATED\nBACKUP_SHA256='
                               + hashlib.sha256(archive.read_bytes()).hexdigest() + '\n')
        for directory in (self.backup, self.evidence):
            (directory / 'LAST_SUCCESS').write_text(self.stamp + '\n')
        # The helpers do no crypto or database work. They validate the wrapper's
        # subprocess environment; actual recovery helpers have separate tests.
        check = self.root / 'check'
        expected = {k: v for k, v in self.settings.items() if not k.startswith('CODESTRA_RELEASE')
                    and not k.startswith('CODESTRA_N8N_')}
        check.write_text('#!/usr/bin/env python3\nimport os\n'
                         + f'expected = {expected!r}\n'
                         + 'assert all(os.environ.get(k) == v for k, v in expected.items())\n')
        restore = self.root / 'restore'
        restore.write_text('#!/bin/sh\nprintf "%s\\n" ' + self.stamp
                           + ' > "' + str(self.evidence / 'LAST_SUCCESS') + '"\n')
        for helper in (check, restore):
            helper.chmod(0o700)
        source = (ROOT / 'operations/backup/codestra-n8n-database-certify').read_text()
        replacements = {
            '/etc/codestra/backup/database-certification.env': self.config,
            '/opt/codestra/backups/n8n-recovery': self.backup,
            '/opt/codestra/backups/n8n-restore-evidence': self.evidence,
            '/opt/codestra/operations/backup/check-n8n-backup-freshness.sh': check,
            '/opt/codestra/operations/backup/verify-n8n-recovery.sh': restore,
            '/opt/codestra/operations/backup/check-n8n-recovery-freshness.sh': check,
        }
        for original, replacement in replacements.items():
            source = source.replace(original, str(replacement))
        # Permit the fixture owner in the temporary copy only, for non-root CI.
        source = source.replace('== "0"', f'== "{os.getuid()}"')
        self.wrapper = self.root / 'wrapper'
        self.wrapper.write_text(source)

    def run_wrapper(self):
        return subprocess.run(['bash', str(self.wrapper), 'certify'], capture_output=True,
                              text=True, timeout=10, env={'PATH': '/usr/bin:/bin'})

    def test_plain_config_assignments_reach_helpers_and_cached_result_passes(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('N8N_DATABASE_CERTIFICATION=PASS', result.stdout)

    def test_fresh_restore_path_passes(self):
        (self.evidence / 'LAST_SUCCESS').unlink()
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_release_is_rejected_even_with_cached_restore(self):
        self.status.write_text(self.tuple_text.replace('a' * 40, 'e' * 40))
        result = self.run_wrapper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('backup release SHA mismatch', result.stderr)

    def test_cached_restore_must_match_archive_tuple_and_isolated_class(self):
        original = self.result.read_text()
        for field in ('BACKUP_SHA256', 'RELEASE_SHA', 'PRODUCTION_IMAGE_DIGEST',
                      'STAGING_IMAGE_DIGEST', 'TARGET_CLASS'):
            with self.subTest(field=field):
                self.result.write_text('\n'.join(
                    field + '=MISMATCH' if line.startswith(field + '=') else line
                    for line in original.splitlines()) + '\n')
                result = self.run_wrapper()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('N8N_DATABASE_CERTIFICATION=PASS', result.stdout)
                self.assertIn('restore evidence', result.stderr)
