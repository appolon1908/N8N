# Codestra complete n8n integration and automation blueprint

## Status

```text
SOURCE_ONLY=YES
WORKFLOWS_ACTIVE_IN_GIT=NO
DIRECT_PROVIDER_ACCESS=NO
EXTERNAL_EFFECTS_ENABLED=NO
PRODUCTION_CHANGED=NO
```

n8n is the Codestra orchestration engine. It is not an authorization authority, integration gateway, provider adapter, durable business ledger, or system of record.

## Runtime topology

```text
Public clients and provider callbacks
                 |
               Caddy
                 |
                Kong
                 |
             Middleware
  durable inbox / event ledger / outbox
                 |
       private wake-up and claim
                 v
                n8n
     timing, branching and approvals
                 |
        governed commands only
                 v
             Middleware
                 |
  Odoo / VICIdial / Asterisk / Telnexa /
  Klyrow / Kyqra / Postly / Provisioning /
  MoneyBee / Breero / LARIM-A / Freight /
  Beyvra / approved future adapters
```

## Non-negotiable trust boundaries

1. Public webhooks terminate at Caddy, Kong and Middleware—not n8n.
2. n8n may call the reviewed Middleware API only.
3. n8n never receives credentials for Odoo, VICIdial, Asterisk, Jasmin, Postal, Mautic, Kyqra, Postly, Keycloak administration, Kong administration, product databases, PostgreSQL, Redis or provider APIs.
4. Middleware owns authentication context, tenant isolation, canonical validation, idempotency, semantic replay detection, capabilities, consent, suppression, provider adapters, command state, retry, dead letters, audit and reconciliation.
5. A successful n8n execution is not proof that an external effect succeeded. Destination read-back through Middleware is authoritative.
6. Every workflow export is inactive in Git. Import, publish, activate and enable a Middleware capability are separate reviewed operations.

## Durable wake-and-claim handoff

A direct n8n webhook alone is not durable enough.

Middleware creates, in one database transaction:

```text
normalized_event
automation_job
automation_dispatch_outbox
audit_record
```

The outbox worker sends n8n a private wake containing identifiers only:

```json
{
  "job_id": "uuid",
  "workflow_key": "codestra.crm.lead-intake.v1",
  "workflow_version": 1,
  "correlation_id": "correlation-id",
  "delivery_token": "one-use-signed-token"
}
```

The workflow then calls `POST /v2/automation/jobs/claim`. Middleware validates the n8n machine client, workflow scope, tenant, workflow version, effective capability and policy snapshot before granting a lease and returning the safe payload.

During execution n8n records safe steps and sends heartbeats. Every business or provider effect is requested through `POST /v2/automation/commands`. Commands are idempotent and may return `ACCEPTED`, `BLOCKED`, `SUBMITTED`, `UNKNOWN`, `COMPLETED`, `FAILED` or `CANCELLED`.

`UNKNOWN` requires destination reconciliation before another externally effective request is allowed.

The workflow completes through exactly one terminal endpoint:

```text
POST /v2/automation/jobs/{job_id}/complete
POST /v2/automation/jobs/{job_id}/fail
```

A lost wake is redelivered from the durable outbox. A dead n8n worker loses its lease. A stale execution cannot complete the job.

## Automation state machine

```text
PENDING
  -> DISPATCHING
  -> CLAIMED
  -> RUNNING
      -> WAITING_APPROVAL
      -> WAITING_TIMER
      -> WAITING_COMMAND
      -> RETRY_SCHEDULED
      -> COMPLETED
      -> FAILED_TERMINAL
      -> DEAD_LETTER
      -> CANCELLED

DEAD_LETTER
  -> OPERATOR_REVIEW
  -> REPLAY_APPROVED
  -> PENDING
```

Long human waits should be stored by Middleware. n8n records `WAITING_APPROVAL` or `WAITING_TIMER` and exits. Middleware creates a new resume job when the approval or time condition becomes effective.

## Shared reusable workflows

Every product workflow should use versioned shared components:

```text
00 Validate Wake Envelope
01 Claim Middleware Job
02 Verify Workflow and Capability
03 Start or Extend Lease
04 Request Governed Command
05 Poll or Reconcile Command
06 Record Safe Step Evidence
07 Request Human Approval
08 Schedule Durable Resume
09 Complete Job
10 Fail or Retry Job
11 Report Dead Letter
12 Sanitize Incident Alert
13 Release Local Resources
```

## System ownership

| Domain | Authority | n8n role |
|---|---|---|
| Human and machine identity | Keycloak | Consume validated subject, tenant and scopes |
| Cross-system writes | Middleware | Request governed commands |
| CRM and business history | Odoo 19 | Sequence approved CRM operations |
| Calls and campaigns | VICIdial/Asterisk | Follow call-result and callback workflows |
| SMS control/delivery | Telnexa/Jasmin | Sequence sends and reconcile MO/DLR events |
| Email control/delivery | Klyrow/Postal | Sequence approved sends and lifecycle handling |
| Crawler jobs/results | Kyqra/Crawlee/Playwright | Sequence jobs and human review |
| Social publication | Postly adapter | Coordinate approved publications |
| Provisioning | Provisioning service | Coordinate multi-system lifecycle requests |
| Product business state | Product backend | Sequence product-specific commands |
| Durable automation state | Middleware PostgreSQL | Execute leased jobs only |
| n8n queue coordination | n8n Redis | Worker dispatch only |

## Software flows

### Odoo CRM

```text
Form or product event -> Middleware validation -> automation job -> n8n
-> Middleware Odoo command -> Odoo read-back -> optional Kyqra review
-> approved Odoo update -> optional Klyrow/Telnexa message request
```

### Telephony

```text
VICIdial/Asterisk adapter -> Middleware inbox -> normalized call event
-> Odoo history -> n8n follow-up -> Middleware callback/message commands
```

n8n never places a call directly.

### SMS

```text
Odoo/product request -> Middleware -> n8n timing/approval
-> Middleware Telnexa command -> Jasmin/provider
-> MO/DLR -> Middleware -> n8n reconciliation -> business history
```

Opt-out events take the privacy/suppression path before any later send.

### Email

```text
Odoo/product/Klyrow request -> Middleware policy -> optional n8n timing/approval
-> Middleware Klyrow command -> Postal -> lifecycle event
-> Middleware -> n8n reconciliation -> business history
```

Keycloak SECURITY email is not synchronously orchestrated by n8n.

### Crawler

```text
Discovery request -> Middleware target policy -> n8n
-> Middleware Kyqra command -> crawler execution -> signed result
-> Middleware -> human review -> approved writeback
```

### Provisioning

```text
Manager approval -> Middleware -> n8n lifecycle coordination
-> Middleware provisioning command -> destination adapters and read-back
-> completion only when the required resource tuple agrees
```

### Privacy

```text
Privacy request -> identity and tenant validation -> protected approval
-> n8n coordinates Middleware commands -> every adapter returns read-back
-> Middleware reconciliation -> final privacy evidence
```

n8n never deletes directly from databases.

## Runtime hardening

Target queue-mode topology:

```text
protected editor route -> n8n-main -> PostgreSQL -> Redis queue -> n8n workers
```

Required controls:

- one immutable n8n version across main and workers;
- external secret provider;
- least-privilege PostgreSQL and Redis identities;
- no public host port for the editor or webhooks without reviewed gateway policy;
- public API, community packages, templates, diagnostics and personalization disabled;
- Code, shell, SSH, FTP, Git and local-file nodes excluded;
- success execution payloads not retained by default;
- bounded, redacted error retention;
- readiness for main and every worker;
- egress allowlist to Middleware only;
- backup, restore and rollback evidence before staging.

## Credential model

Recommended machine clients:

```text
n8n-platform-runtime
n8n-crm-automation
n8n-telephony-automation
n8n-messaging-automation
n8n-crawler-automation
n8n-product-automation
n8n-privacy-automation
n8n-operations-automation
```

All audiences target Middleware only. Credential aliases and types are reviewed runtime configuration; values never appear in workflow exports.

## Branch and promotion model

```text
feature branch -> exact-head CI -> independent review -> protected merge
-> inactive staging import -> no-effect E2E -> published workflow version
-> immutable release manifest -> inactive production import
-> separate workflow activation -> separate Middleware capability canary
```

Do not push and pull source from the same n8n instance. Production is a one-way consumer of reviewed releases and is not a normal editing environment.

## Test requirements

Every workflow branch must prove:

```text
WORKFLOW_ACTIVE_FALSE=PASS
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
EXPIRED_JOB_BLOCKED=PASS
LEASE_LOSS_BLOCKS_COMPLETION=PASS
UNKNOWN_OUTCOME_RECONCILED=PASS
BOUNDED_RETRY=PASS
DEAD_LETTER=PASS
APPROVAL_REJECTION=PASS
N8N_RESTART_RECOVERY=PASS
MIDDLEWARE_OUTAGE_RECOVERY=PASS
STAGING_EXTERNAL_EFFECTS=ZERO
BACKUP_RESTORE=PASS
ROLLBACK_REHEARSAL=PASS
```

## Release evidence

A release manifest binds source SHA, n8n image digest, workflow export hash, n8n workflow and version IDs, published version, active state, Middleware contract version, credential alias, required capability, runtime-policy hash, backup evidence, rollback evidence, approval and change ID.

## Current release state

```text
BASELINE_GOVERNANCE_MERGED=NO
RUNTIME_PATHS_VERIFIED=NO
N8N_EDITION_VERIFIED=NO
ENDPOINT_BINDING_VERIFIED=NO
CREDENTIAL_BINDING_VERIFIED=NO
EDITOR_POLICY_VERIFIED=NO
WORKFLOWS_IMPORTED=NO
WORKFLOWS_ACTIVE=NO
EXTERNAL_EFFECTS_ENABLED=NO
PRODUCTION_CHANGED=NO
```
