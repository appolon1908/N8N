# Automation control plane v2.1 review corrections

This document records the binding corrections applied after protected review.

## Canonical changes

- Generic `automation.execute` and `automation.command` scopes are prohibited.
- Every endpoint has a granular scope in `contracts/operation-policy.v2.json`.
- Every machine client is restricted to explicit workflow families and command prefixes.
- `n8n-social-automation` is dedicated to `social.postly`; SMS/email credentials cannot publish social content.
- Wake-bound claims require `job_id` and one-use `delivery_token` plus workflow and execution identity.
- Step evidence requires the current `lease_token` and `execution_id`.
- Commands require job, lease, execution, workflow and step context.
- Middleware derives the authoritative tenant and actor from the durable job.
- Dead-letter replay requires protected approval, idempotency key, expected version, original-effect fingerprint and safe-replay classification.
- The exact dated branch map replaces stale non-dated branch references.
- `appolon1908-hue/social.codestra.co` is the Postly/Postiz domain authority and has its own source-only contract branch and PR.

## Safety state

```text
SOURCE_ONLY=YES
WORKFLOWS_ACTIVE=NO
CREDENTIALS_CREATED=NO
LIVE_KEYCLOAK_APPLY=NO
SOCIAL_PUBLISH=false
EXTERNAL_EFFECTS_ENABLED=NO
PRODUCTION_CHANGED=NO
```

The source contracts must merge before `shared/automation-runtime-v2-20260827` receives an executable n8n graph.
