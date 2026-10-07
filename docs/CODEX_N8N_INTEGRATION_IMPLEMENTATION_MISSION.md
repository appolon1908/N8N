# Codex mission — complete Codestra n8n integration control plane

## Repository authority

```text
N8N repository: appolon1908-hue/N8N
Baseline branch: platform/services-middleware-automations-designs
Mission branch: contract/automation-control-plane-v2-20260827
Middleware repository: appolon1908-hue/Middleware-
Production deployment: NOT AUTHORIZED
```

Read completely before modifying code:

```text
docs/complete-integration-automation-blueprint.md
config/branch-dependency-map.v2.json
automations/catalog.v2.json
contracts/automation-control-api.v2.yaml
```

## Objective

Implement the durable Middleware automation API and the shared inactive n8n workflow foundation. Do not connect n8n directly to any application, provider or unrelated database. Do not activate workflows or change production.

## Phase 0 — exact Git state and conflict certification

```bash
git fetch --all --prune
git status --short
git branch --show-current
git fsck --full
test -z "$(git ls-files -u)"
git diff --check
! git grep -nE '^(<<<<<<<|=======|>>>>>>>)' -- . ':!*.md' ':!docs/evidence/**'
```

Record the exact baseline head/base, open PR stack, checks, review state and unresolved conversations. Do not assume the branch identities in this document are still current.

## Phase 1 — baseline governance

Before executable workflow work:

1. Finish exact-head CI for the source-governance baseline.
2. Obtain independent approval for the unchanged SHA.
3. Protect `main` with required PR review, conversation resolution, exact-head checks, no force push/deletion and no administrator bypass.
4. Merge the baseline through protected controls.
5. Refresh this branch without rewriting reviewed lineage.

## Phase 2 — Middleware contract implementation

Implement, in focused Middleware branches:

```text
core/integration-contracts
platform/postgresql
platform/redis
integration/keycloak
core/event-ledger-outbox
core/webhook-inbox-replay
core/workers-scheduler
integration/n8n
```

Required durable models:

```text
automation_jobs
automation_job_attempts
automation_job_steps
automation_job_leases
automation_approvals
automation_commands
automation_command_attempts
automation_dead_letters
automation_reconciliation_runs
automation_dispatch_outbox
```

Implement the endpoints and schemas in `automation-control-api.v2.yaml` with:

- authoritative tenant and actor mapping;
- exact workflow-key and major-version authorization;
- stable idempotency and semantic conflict handling;
- row-lock or optimistic transition safety;
- expiring leases and stale-execution denial;
- capability checks at claim and immediately before an effect;
- consent/suppression/pause checks at dispatch time;
- bounded retries and durable dead letters;
- destination reconciliation for unknown outcomes;
- redacted audit and metrics;
- no credentials or customer payloads in logs.

## Phase 3 — shared n8n runtime branch

Create `shared/automation-runtime` after the contract is reviewed. Add inactive reusable workflows for:

```text
wake validation
job claim
capability preflight
lease heartbeat
governed command request
command reconciliation
safe step evidence
approval request and resume
durable timer resume
terminal completion
retry and failure
dead-letter reporting
sanitized incident notification
resource cleanup
```

Every export must have:

```text
active=false
pinData={}
no embedded credentials
no public webhook
no direct provider or database endpoint
no Code, command, file, SSH, FTP or Git node
Middleware-only HTTP access
```

## Phase 4 — runtime verification

Use separate focused branches for:

```text
platform/runtime-path-verification
platform/n8n-runtime-policy
platform/n8n-queue-mode
platform/n8n-editor-identity
platform/n8n-secrets
```

Verify with evidence:

- exact n8n version and edition;
- main and worker image identity;
- PostgreSQL and Redis roles, TLS/ACL and readiness;
- data and backup paths;
- Middleware private endpoint and egress allowlist;
- exact credential aliases and types;
- protected editor authentication and session policy;
- execution retention and redaction;
- encryption-key versioning and rotation;
- immutable image, SBOM, signature, provenance and vulnerability evidence;
- backup/restore and rollback.

Keep every external-effect capability false.

## Phase 5 — product branches

Implement one independently reviewable branch at a time:

```text
automation/identity-provisioning
automation/odoo-crm
automation/vicidial-telephony
automation/telnexa-sms
automation/klyrow-email
automation/kyqra-crawler
automation/postly-social
automation/moneybee-loans
automation/breero-marketplace
automation/larim-a-booking
automation/freight-operations
automation/beyvra
```

Each branch must depend on a merged Middleware event/command contract, use only Middleware credentials, declare its required capability and add tests for exact replay, conflicting replay, concurrent duplicates, tenant isolation, expiry, lease loss, capability denial, unknown outcome, bounded retry, dead letter and rollback.

## Phase 6 — operations and privacy

Create separate branches:

```text
operations/human-approvals
operations/retry-dead-letter
operations/reconciliation
operations/incident-alerting
operations/release-canary
privacy/data-rights
observability/n8n
```

Dead-letter replay and privacy deletion require protected approval. Do not implement destructive automatic repair.

## Phase 7 — isolated staging only

After exact-head review and immutable release evidence:

1. Import workflows inactive.
2. Verify export hashes, workflow IDs and version IDs.
3. Keep all capabilities false.
4. Run synthetic no-effect E2E paths.
5. Test queue, restart, lease recovery, duplicate, conflict, replay, approval, dead letter, Middleware outage, tenant isolation, egress denial and rollback.
6. Prove zero calls, SMS, emails, social publications, crawler writebacks, lead publications, payments and provider writes.

## Required evidence

```text
SOURCE_SHA_IDENTITY=PASS
CONFLICT_MARKER_SCAN=PASS
WORKFLOW_JSON_SCHEMA=PASS
WORKFLOWS_ACTIVE_FALSE=PASS
PIN_DATA_EMPTY=PASS
EMBEDDED_CREDENTIALS=NONE
PUBLIC_WEBHOOKS=NONE
DIRECT_PROVIDER_ENDPOINTS=NONE
DIRECT_DATABASE_NODES=NONE
BLOCKED_NODES=NONE
TENANT_ISOLATION=PASS
EXACT_REPLAY=PASS
CONFLICTING_REPLAY=PASS
CONCURRENT_DUPLICATE=PASS
CAPABILITY_DISABLED=PASS
LEASE_LOSS=PASS
UNKNOWN_OUTCOME_RECONCILIATION=PASS
BOUNDED_RETRY=PASS
DEAD_LETTER=PASS
APPROVAL_REJECTION=PASS
N8N_RESTART_RECOVERY=PASS
MIDDLEWARE_OUTAGE_RECOVERY=PASS
STAGING_EXTERNAL_EFFECTS=ZERO
BACKUP_RESTORE=PASS
ROLLBACK_REHEARSAL=PASS
```

## Final report

Return repository, directory, starting and final SHAs, branches, commits, PRs, contract version, workflow export hashes, tests, runtime evidence, credential/endpoint/editor/egress evidence, backup/restore evidence, image evidence, staging no-effect evidence, rollback result and unresolved blockers.

End with:

```text
BASELINE_MERGED=YES|NO
WORKFLOWS_IMPORTED=YES|NO
WORKFLOWS_ACTIVE=YES|NO
PRODUCTION_CHANGED=YES|NO
```
