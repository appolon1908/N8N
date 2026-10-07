# N8N Automation Platform

Canonical governed source for Codestra n8n workflow packs, consumed contracts, deployment policy, operational evidence, and release controls.

## Current state

- **Canonical repository:** `appolon1908-hue/N8N`
- **Protected branch:** `main`
- **Live server:** unchanged
- **Runtime paths:** `UNVERIFIED`
- **n8n edition/endpoint/credential/editor policy:** `UNVERIFIED`
- **External delivery:** disabled
- **Production deployment:** blocked
- **Workflow activation:** disabled by policy and CI

This repository contains no secret values and no live-server write or SSH deployment action. Product automations remain workflow packs in this repository; separate product-specific n8n repositories are prohibited.

## Architecture boundary

n8n may call the Codestra middleware API only. It must not connect directly to Odoo, VICIdial, Jasmin, Postal/Klyrow, Kyqra, PostgreSQL, Redis, Keycloak administration, Kong administration, or provider APIs. The middleware owns authorization, tenant isolation, idempotency, replay protection, suppression checks, kill switches, auditing, and delivery state.

```text
Caddy -> Kong -> Keycloak identity -> Codestra middleware -> governed service adapters
                                      ^
                                      |
                                  n8n workers
```

## Repository map

| Path | Purpose |
|---|---|
| `automations/` | Product and service automation catalog |
| `config/` | Capabilities, services, products, n8n security/endpoint policy, and runtime-path state |
| `contracts/` | Consumed integration schemas; canonical Middleware source lives elsewhere |
| `deploy/` | Non-applying Compose and release-preflight templates |
| `docs/` | Architecture, security review, branching, and runbooks |
| `observability/` | Monitoring and alerting definitions for n8n dependencies |
| `operations/` | Read-only inventory, recovery, release, and audit tooling |
| `scripts/` | Repository, workflow, secret, runtime, and release validators |
| `tests/` | Policy, contract, deployment, and workflow validation |
| `workflows/` | Inactive, governed workflow packs and safe templates |

## Local validation

```bash
make validate
```

The manual `deployment-preflight` workflow performs validation only. It deliberately fails until runtime paths and the n8n endpoint/security/credential/editor policy are independently verified and a complete immutable release manifest exists. It never connects to or changes the live server.

Stage 4 production movement is additionally governed by `docs/STAGE4-RUNTIME-TO-PRODUCTION.md` and the executable Middleware gate `scripts/verify_stage4_runtime_gate.py`. That gate must remain `NO_GO` until the six ordered runtime proofs are attached and reviewed.

Templates use a disabled request to `https://middleware.invalid`. Executable workflow exports are blocked until the deployed n8n edition, a safe middleware endpoint-binding strategy, an approved credential-binding profile, and a protected editor-access strategy are verified. Code and other high-risk local-execution nodes are excluded from the deployment template.

## Required merge gates

1. Exact-head CI passes on the unchanged PR SHA.
2. Runtime-path state remains `UNVERIFIED` unless evidence is attached and independently reviewed.
3. Every n8n workflow remains inactive in Git; only disabled templates are allowed while endpoint binding is unverified.
4. All external-effect capability flags remain false.
5. No direct service credentials, direct service endpoints, public webhooks, IP literals, Code nodes, or local-execution nodes appear in workflow exports.
6. The n8n edition, endpoint binding, credential binding, editor access, and runtime paths remain unverified unless separate evidence-backed reviews approve them.
7. An independent reviewer approves the final unchanged SHA.
8. Merge occurs through protected branch controls without admin bypass.
