# Branching strategy

## Baseline branch

`platform/services-middleware-automations-designs` is the umbrella baseline for repository governance, schemas, catalogs, workflow design rules, read-only runtime discovery, CI, and deployment preflight.

## Implementation branches

Create focused branches from the merged baseline rather than placing every executable workflow into one pull request:

- `contract/automation-control-plane-v2-20260827`
- `shared/automation-runtime-v2-20260827`
- `automation/odoo-crm-v2-20260827`
- `automation/vicidial-telephony-v2-20260827`
- `automation/telnexa-sms-v2-20260827`
- `automation/klyrow-email-v2-20260827`
- `automation/postly-social-v2-20260827`
- `automation/kyqra-crawler-v2-20260827`
- `automation/provisioning-v2-20260827`
- `automation/identity-keycloak-v2-20260827`
- `automation/moneybee-loans-v2-20260827`
- `automation/beyvra-operations-v2-20260827`
- `automation/larim-a-booking-v2-20260827`
- `automation/freight-operations-v2-20260827`
- `automation/breero-marketplace-v2-20260827`
- `automation/booked4seasons-v2-20260827`
- `automation/trading-operations-v2-20260827`
- `operations/retry-dead-letter-v2-20260827`
- `operations/reconciliation-v2-20260827`
- `observability/n8n-v2-20260827`
- `testing/staging-no-effect-e2e-v2-20260827`
- `release/automation-v1-20260827`

Each branch must include its contract, inactive workflow exports, tests, failure paths, rollback notes, and capability impact. Dependency branches merge in order; do not merge a final stacked branch directly into `main` while its prerequisites remain open.
