#!/usr/bin/env python3
"""Read-only installation inventory; never runs recovery or certifies runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RULE = 'codestra-admin ALL=(root) NOPASSWD: /usr/local/sbin/codestra-n8n-database-certify certify'
INSTALLATIONS = (
    ('wrapper', 'operations/backup/codestra-n8n-database-certify',
     '/usr/local/sbin/codestra-n8n-database-certify', 0o755),
    ('sudoers', 'operations/sudoers/codestra-n8n-database-certify',
     '/etc/sudoers.d/codestra-n8n-database-certify', 0o440),
)
HELPERS = (
    'check-n8n-backup-freshness.sh', 'verify-n8n-recovery.sh',
    'check-n8n-recovery-freshness.sh',
)
OPERATOR_FILES = (
    'n8n-signed-backup-tuple.txt', 'n8n-signed-backup-status.sha256',
    'n8n-staging-compose.sha256', 'n8n-staging-compose.redacted.yaml',
)


def inspect_file(path: Path, *, modes=None, root_owned=False, expected=None):
    """Return metadata only. Never echo contents or exception text."""
    result = {'path': str(path), 'status': 'BLOCKED'}
    try:
        # Do not follow symlinked parents, even when the final file is regular.
        if any(parent.is_symlink() for parent in path.parents):
            return {**result, 'reason': 'SYMLINK_PARENT'}
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                return {**result, 'reason': 'NOT_REGULAR_FILE'}
            result.update(uid=info.st_uid, gid=info.st_gid,
                          mode=f'{stat.S_IMODE(info.st_mode):04o}',
                          mtime_ns=info.st_mtime_ns)
            if root_owned and (info.st_uid != 0 or info.st_gid != 0):
                return {**result, 'reason': 'OWNER_MISMATCH'}
            if modes is not None and stat.S_IMODE(info.st_mode) not in modes:
                return {**result, 'reason': 'MODE_MISMATCH'}
            if info.st_size == 0:
                return {**result, 'reason': 'EMPTY_FILE'}
            if expected is not None:
                if info.st_size != len(expected):
                    return {**result, 'reason': 'CONTENT_MISMATCH'}
                content = handle.read(len(expected) + 1)
                result['sha256'] = hashlib.sha256(content).hexdigest()
                if content != expected:
                    return {**result, 'reason': 'CONTENT_MISMATCH'}
        return {**result, 'status': 'PASS'}
    except FileNotFoundError:
        return {**result, 'reason': 'MISSING'}
    except PermissionError:
        return {**result, 'reason': 'UNREADABLE'}
    except OSError:
        return {**result, 'reason': 'UNSAFE_OR_UNREADABLE_FILE'}


def run_check(command, *, cwd=None):
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                              timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def source_identity(expected_sha):
    head = run_check(['git', 'rev-parse', 'HEAD'], cwd=ROOT)
    dirty = run_check(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT)
    passed = (head is not None and head.returncode == 0
              and head.stdout.strip() == expected_sha
              and dirty is not None and dirty.returncode == 0 and not dirty.stdout)
    return {'status': 'PASS' if passed else 'BLOCKED', 'expected_sha': expected_sha,
            'reason': 'EXACT_CLEAN_CHECKOUT' if passed else 'SOURCE_IDENTITY_UNVERIFIED'}


def collect(expected_sha):
    checks = {'source': source_identity(expected_sha)}
    # Source mismatch stops before using checkout bytes as installation authority.
    if checks['source']['status'] != 'PASS':
        return report(checks)
    for name, source, installed, mode in INSTALLATIONS:
        try:
            expected = (ROOT / source).read_bytes()
        except OSError:
            checks[name] = {'status': 'BLOCKED', 'reason': 'SOURCE_UNREADABLE'}
            continue
        checks[name] = inspect_file(Path(installed), modes={mode},
                                    root_owned=True, expected=expected)
    for name in HELPERS:
        try:
            expected = (ROOT / 'operations/backup' / name).read_bytes()
        except OSError:
            checks[name] = {'status': 'BLOCKED', 'reason': 'SOURCE_UNREADABLE'}
            continue
        checks[name] = inspect_file(Path('/opt/codestra/operations/backup') / name,
                                    modes={0o500, 0o700, 0o755}, root_owned=True,
                                    expected=expected)
    checks['configuration'] = inspect_file(
        Path('/etc/codestra/backup/database-certification.env'),
        modes={0o400, 0o600}, root_owned=True)
    for name in OPERATOR_FILES:
        checks[name] = inspect_file(Path('/home/codestra-admin') / name)
    # Validate syntax only after the installed policy matches the exact source.
    if checks['sudoers']['status'] == 'PASS':
        policy = (ROOT / INSTALLATIONS[1][1]).read_text()
        rules = [line for line in policy.splitlines() if line and not line.startswith('#')]
        syntax = run_check(['/usr/sbin/visudo', '-cf', INSTALLATIONS[1][2]])
        passed = rules == [RULE] and syntax is not None and syntax.returncode == 0
        checks['sudoers_syntax'] = {'status': 'PASS' if passed else 'BLOCKED'}
    else:
        checks['sudoers_syntax'] = {'status': 'BLOCKED', 'reason': 'POLICY_NOT_VERIFIED'}
    return report(checks)


def report(checks):
    return {
        'schema_version': '1.0',
        'installation_preflight': 'PASS' if all(
            item['status'] == 'PASS' for item in checks.values()) else 'BLOCKED',
        'checks': checks,
        'database_certification': 'NOT_RUN',
        'deploy_key_certification': 'NOT_RUN',
        'middleware_certification': 'NOT_RUN',
        'runtime_mutation_performed': False,
        'remaining_gates': [
            'operator evidence authenticity and active runtime tuple reconciliation',
            'reviewed restore targets and effective delegated sudo authority',
            'bounded database certification and checksum-bound restore evidence',
            'target-account deploy-key bootstrap and readback (#3)',
            'exact-candidate Middleware staging and read-only canary evidence (#52)',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source-sha', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.expected_source_sha):
        parser.error('--expected-source-sha must be an exact 40-character lowercase Git SHA')
    result = collect(args.expected_source_sha)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['installation_preflight'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
