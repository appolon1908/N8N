# n8n workflows

All committed exports must be inactive. Templates demonstrate structure only, contain no credential references, and are not approved production automations.

## Endpoint binding

The n8n edition and the live middleware endpoint strategy are still unverified. For that reason, templates use the reserved non-routable host `https://middleware.invalid` and their outbound HTTP nodes are disabled.

Executable workflows are prohibited until `config/n8n-policy.json` records reviewed endpoint, credential-binding, and editor-access strategies. The later implementation must use one of these approved endpoint patterns:

- a verified n8n custom variable on an edition that supports it;
- a reviewed custom node that owns the middleware endpoint; or
- a fixed, verified private DNS name enforced by egress policy.

Environment-variable access from workflow nodes stays blocked. Do not use `$env` to work around endpoint governance. Credential references are permitted only in future executable exports when their exact n8n credential types and names are approved by the verified policy; templates declare `credential_binding=NO_CREDENTIALS`.

## Stage 4 orchestration templates

The `CP-*` source templates live under `_templates` until Stage 2 and Stage 3 verification is complete. They are versioned in Git, inactive by default, and carry no credential material. The common error workflow is defined first as `CP-COMMON-ERROR-HANDLER`; every domain workflow records that dependency in `meta.codestra.depends_on`.

Each CP workflow may call only the Middleware automation API. Odoo, Telnexa/Jasmin, Klyrow/SMTP, Kyqra, VICIdial, Postly, and provisioning systems remain behind Middleware adapters.

## Rules

- Outbound HTTP may target only the Codestra middleware endpoint selected by the reviewed policy.
- Do not embed secret values or credential exports. Future executable exports may reference only exact credential types and names approved by policy; direct database nodes, provider endpoints, public service URLs, and IP literals remain prohibited.
- Public webhooks are prohibited. Provider callbacks terminate at Kong/middleware, where signatures and replay controls are enforced before n8n receives an internal event.
- Each workflow needs a deterministic idempotency key, bounded retry path, dead-letter path, and capability declaration before implementation review.
- Export workflow JSON without execution data, pin data, credential material, or active state.
- Code, Execute Command, local file, SSH, FTP, and Git nodes remain excluded until a separate security design is approved. If Code is ever enabled, external task-runner isolation is mandatory.

Run:

```bash
python3 scripts/validate_workflows.py workflows
```
