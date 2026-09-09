# Issue certification handoff

Repository authority: `appolon1908-hue/N8N`. Source validation does not certify
host installation, database recovery, or orchestration runtime behavior.

## Recovery wrapper (#56)

The wrapper exports the reviewed configuration fields required by child helpers.
Both fresh and cached restore paths bind the signed backup release/image tuple to
the approved configuration. Before reporting PASS, the wrapper binds the checked
restore result to the archive SHA-256, release SHA, both image digests, and isolated
target class. Temporary-fixture tests exercise these paths without database access.

This wrapper differs from the bytes originally staged in issue #56. The old staged
wrapper must not be represented as the revised implementation. After this change
is protected-merged, a root operator must stage the wrapper from that exact merged
commit, review it, and verify these hashes before following the issue's existing
installation and pre-execution gates:

| File | SHA-256 |
| --- | --- |
| `operations/backup/codestra-n8n-database-certify` | `a2380aa8b17df01a46420cb703a3af03660b6f99fe109bed1b97ab3526a07793` |
| `operations/sudoers/codestra-n8n-database-certify` | `72203d6410af02d11f637384a1d76b6a49373b322885259a8caa91459b9257f2` |

The four operator-produced artifacts recorded in #56 are still required: the
signed backup tuple, signed status checksum, staging Compose checksum, and redacted
staging Compose file. Reconcile the signed tuple against the active database
consumer before certification. No replacement tuple may be inferred from an old
comment or a template. General sudo and changes to live databases are outside this
handoff. Keep #56 open until the installed checksums, modes, sudo policy,
certification result, backup stamp, and restore evidence checksums are recorded.

## Read-only repository access (#3)

The bootstrap now rejects an explicit false or null `enabled` field both in the
existing-key lookup and the API readback. An absent field remains compatible with
API responses that omit it. Execute the protected-merged bootstrap only on the
intended n8n host as its Git-reading Unix account; follow
[the bootstrap runbook](ssh-deploy-key-bootstrap.md). Keep #3 open until its
repository identity, read-only API state, modes, and `git ls-remote` host evidence
pass. Local mocked tests are not host evidence.

## Middleware orchestration (#52)

This patch does not certify #52. The exact Middleware source/image candidate and
approved staging workflows must be established before executing synthetic cases.
Existing exports remain inactive. Callbacks terminate at Middleware's durable
inbox; n8n must not gain a callback-signing or direct-provider authority.

Closure requires evidence for the exact workflow digests and identity claims,
signed callbacks, replay/duplicate/changed-payload behavior, tenant isolation,
timeout/retry/dead-letter behavior, restart recovery, zero direct provider calls,
and zero live delivery. Metadata backup, rollback rehearsal, and the bounded
production read-only canary remain release gates. The existing NO_GO certification
manifest must not be changed based only on passing source tests.

## Session limitation (2026-09-09)

The workspace has no configured `codestra-app` SSH alias and that hostname did not
resolve during the read-only connection attempt. Host installation and runtime
checks were not performed. The original recovery and deploy-key source PRs (#55
and #51) were already merged at baseline commit
`0e300df832c56600b864bb8a54afde8919e05daf`.

## Read-only installation preflight

From a clean checkout of the reviewed, protected-merged commit on the target host,
run `python3 ops/check_n8n_operator_preflight.py --expected-source-sha SHA`, replacing
`SHA` with that independently selected full commit SHA. The command returns JSON
and exits 1 when any installation check is blocked; it exits 0 only when all
installation checks pass. A mismatched or dirty checkout stops host inventory.

The tool compares installed wrapper, sudo policy, and recovery helper bytes with
the selected commit's regular Git blobs, checks their root ownership and modes,
checks configuration
metadata without reading its contents, inventories the four operator evidence
files, and invokes `visudo -cf` only for an exact matching sudo policy. It rejects
symlinks and nonregular files and never prints file contents or raw command errors.
All expected source files are resolved before host inventory; unavailable commit
objects stop the check. Policy syntax validation uses the same commit bytes as
the installed-file comparison. Git replacement objects and worktree conversion
filters are excluded from the authority reads.
It neither invokes sudo nor grants installation authority. A delegated account
without read access receives BLOCKED; the authorized root operator can perform
these read-only checks without adding a new sudo rule.

`installation_preflight=PASS` is only an installation inventory result. Evidence
file presence does not authenticate a signed tuple or reconcile the active runtime.
The tool does not inspect effective sudo privileges, validate restore credentials,
execute the certifier, bootstrap a key, or run workflows. Its three certification
fields remain `NOT_RUN`. Complete the remaining gates above before closing #3,
#52, or #56; do not use the JSON inventory as production certification evidence.
