# Codestra Integration Fabric — n8n Automation v2

## Role

n8n is the business-orchestration layer. It coordinates timers, branching, reusable subworkflows, human approvals, reminders, exception handling, and SLA escalation. It is not an identity authority, integration boundary, system of record, financial engine, provider adapter, webhook verifier, or durable command ledger.

```text
Middleware durable job -> private wake -> n8n claim -> orchestration
n8n -> governed Middleware command -> adapter/service -> read-back
Middleware -> terminal operation state -> n8n result -> durable job completion
```

## Runtime cells

- **n8n-core** — Odoo CRM, Klyrow, Telnexa, Postly, Kyqra, public forms, support, and provisioning coordination.
- **n8n-beyvra** — Beyvra platform onboarding, compliance, support, reports, notifications, and reconciliation only; separate from the Trading lane.
- **n8n-contact-center** — private callbacks, call-result handling, appointment coordination, QA sampling, and agent/campaign monitoring.

Each cell has its own PostgreSQL database, Redis namespace, encryption key, service client, credential store, network policy, execution retention, workflow project, and monitoring labels.

## Network boundary

n8n may call only the private Middleware automation API through the internal Kong listener. It may not call Odoo, Keycloak administration, PostgreSQL application databases, Redis application databases, VICIdial, Asterisk, Jasmin, Postal, Mautic, social providers, crawler providers, brokers, wallets, payment providers, or public Internet endpoints.

## Shared runtime

Every workflow uses the same reviewed sequence:

1. validate the private wake envelope;
2. claim the durable automation run;
3. verify workflow family, version, tenant, and capability snapshot;
4. heartbeat the lease;
5. perform orchestration only;
6. request any effect through a governed Middleware command;
7. wait for reconciled operation state;
8. report step evidence;
9. complete or fail the durable run idempotently.

A timeout is `UNKNOWN`, not proof of failure. Middleware reconciles before another effect is attempted.

## Workflow design rules

- every export is inactive in Git;
- every effectful HTTP node is disabled in source;
- no embedded credentials, pin data, secrets, tokens, provider URLs, database nodes, Code, shell, SSH, Git, FTP, or local-file nodes;
- one workflow has one business outcome;
- tenant differences come from runtime configuration, never copied workflows;
- every workflow has a workflow key, major version, owner, risk class, capability, maximum duration, timeout policy, retry policy, and approval class;
- no success is reported before Middleware returns a reconciled operation state.

## Product workflow packs

### Core and identity

- tenant onboarding and readiness;
- team invitation and access review;
- agent onboarding/suspension coordination;
- connection health and credential-rotation coordination;
- public form routing and submission reconciliation.

### Odoo and contact center

- lead intake, deduplication, assignment, pipeline SLA, consent reconciliation;
- callback and appointment scheduling;
- pre-call checks, post-call synchronization, QA sampling, agent-state monitoring;
- no PSTN effect while `PRODUCTION_DIALING=false`.

### Klyrow

- tenant and domain onboarding;
- sender approval;
- transactional message requests;
- campaign readiness;
- bounce, complaint, unsubscribe, suppression, usage, and deliverability reconciliation.

Keycloak SECURITY email remains outside synchronous n8n orchestration.

### Telnexa

- sender and template approval;
- transactional/campaign SMS coordination;
- DLR and inbound-message reconciliation;
- opt-out suppression;
- provider-health and capacity alerts.

### Postly

- content intake, approval chain, publication scheduling, result reconciliation, failure handling, engagement lead candidates, analytics digests, and account-health alerts.

Provider OAuth tokens remain in Postly.

### Kyqra

- job intake, sharding coordination, monitoring, review routing, approved writeback, delivery reconciliation, suppression, privacy deletion, retention, and capacity alerts.

Crawler execution remains in Kyqra/Crawlee/Playwright.

### Beyvra

Allowed: onboarding progress, compliance reminders, support escalation, security alerts, report requests/readiness, notifications, approved CRM projections, and webhook reconciliation.

Beyvra is its own platform automation lane and is not the separate Trading system. Forbidden for n8n: order execution, wallets, ledgers, holds, payments, deposits, withdrawals, transfers, custody, chain broadcasts, broker/provider credentials, and demo-order effects.

## Promotion

```text
development export -> feature branch -> exact-head CI -> independent review
-> protected merge -> inactive staging import -> no-effect E2E
-> publish tested workflow version -> immutable release manifest
-> inactive production import -> separate activation approval
-> separate Middleware capability canary
```

Import, publish, activate, and enable a capability are four separate operations.

## Branches

```text
contract/automation-control-plane-v2-20260827
shared/automation-runtime-v2-20260827
automation/identity-keycloak-v2-20260827
automation/odoo-crm-v2-20260827
automation/vicidial-telephony-v2-20260827
automation/klyrow-email-v2-20260827
automation/telnexa-sms-v2-20260827
automation/postly-social-v2-20260827
automation/kyqra-crawler-v2-20260827
automation/beyvra-operations-v2-20260827
operations/human-approvals-v2-20260827
operations/retry-dead-letter-v2-20260827
operations/reconciliation-v2-20260827
privacy/data-rights-v2-20260827
observability/n8n-v2-20260827
testing/staging-no-effect-e2e-v2-20260827
```

No branch is deployed directly.
