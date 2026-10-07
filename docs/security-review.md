# Security and deployment-scaffold review

## Decision

**SOURCE_SCAFFOLD: ACCEPTABLE FOR DRAFT REVIEW**

**MERGE: BLOCKED UNTIL EXACT-HEAD CI AND PROTECTION**
**LIVE DEPLOYMENT: BLOCKED**

The repository was empty before this branch. No existing CI, ruleset, runtime manifest, immutable image reference, service catalog, or deployment evidence existed. This branch adds source validation and non-applying deployment preflight only.

## Findings

| ID | Severity | Finding | Treatment in this branch |
|---|---|---|---|
| SR-001 | Blocker | Live n8n Compose, data, environment, proxy, secret-provider, and backup paths are not verified. | `config/runtime-paths.json` remains `UNVERIFIED`; preflight refuses approval. |
| SR-002 | Blocker | No immutable n8n image digest, SBOM, provenance, signature bundle, vulnerability report, restore evidence, or rollback evidence exists. | The release validator requires non-placeholder evidence and an independently approved exact release tuple. |
| SR-003 | High | Repository had no branch rules or required checks. | CODEOWNERS, exact-head CI, PR template, and issue #2 define the controls; repository administration must still enable them. |
| SR-004 | High | Direct n8n access to service databases or providers could bypass tenant, privacy, and delivery policy. | Service and workflow policy permits n8n to orchestrate Codestra middleware only; direct service nodes and endpoints are rejected. |
| SR-005 | High | The n8n edition plus safe middleware endpoint, credential-binding, and editor-access mechanisms are unknown. Environment access is blocked, while custom variables may depend on edition. | `config/n8n-policy.json` remains `UNVERIFIED`; templates use disabled requests to `middleware.invalid` with no credential; executable exports are rejected until endpoint, egress, credential, editor, and session strategies are independently reviewed. |
| SR-006 | High | User-provided Code can expose credentials and instance data without isolated task runners. | Code is excluded with `NODES_EXCLUDE`. Enabling it later requires a separate design with external task-runner isolation and matching immutable runner images. |
| SR-007 | High | Static webhook authentication alone does not prevent replay. | Middleware contract requires timestamp, event id, canonical HMAC, replay window, and durable deduplication before side effects. |
| SR-008 | High | A queued event can outlive consent, suppression, or an integration-pause decision. | Dispatch contract requires suppression, consent, retention, integration-pause, and global kill-switch re-check immediately before external submission. |
| SR-009 | High | Queue-mode filesystem binary storage is not safe/supported across workers. | Compose explicitly uses database binary-data mode; external object storage can be designed later after edition and runtime verification. |
| SR-010 | Medium | n8n's public API, API playground, local file nodes, SSH, FTP, Git, and command execution increase attack surface. | Public API/playground are disabled and dangerous nodes are explicitly excluded. |
| SR-011 | Medium | Workflow exports can accidentally include credentials, pin data, active state, direct endpoints, or IP literals. | Secret scan and workflow validation are required in CI; template HTTP nodes are disabled. |
| SR-012 | Medium | A broad automation repository can become an unreviewable monolith. | The umbrella branch establishes contracts and policy; executable work is split into focused product/service branches. |
| SR-013 | Medium | Third-party or mutable GitHub Actions can execute unreviewed code. | Source CI allows only reviewed action identities at exact approved commit SHAs and rejects write permissions, secrets, self-hosted runners, and deployment environments. |
| SR-014 | Medium | A queue worker can be running while its PostgreSQL or Redis dependency is unavailable. | Workers enable a local readiness endpoint and Compose probes `/healthz/readiness`; exact-image behavior still requires isolated staging evidence. |
| SR-015 | High | The n8n editor route, native user authentication, gateway OIDC, session controls, and edition-dependent SSO behavior are not verified. | The editor has no published host port, direct public routing is prohibited by policy, and release preflight requires independent editor/session evidence before staging. |

## Deployment exclusions

This branch contains no SSH, SCP, rsync, remote Docker context, registry login, artifact publication, `docker compose up`, `systemctl`, Kubernetes apply, database migration, workflow import, workflow activation, public callback registration, or API deployment action. The manual workflow is a preflight only.

## Required evidence before a staging deployment implementation may be added

1. Exact-head source CI exists and passes on the unchanged final SHA.
2. `main` protection requires PR review, independent approval, conversation resolution, the exact-head check, and no force push or bypass.
3. Read-only runtime audit proves server identity, Compose labels, mounts, networks, paths, ownership, modes, n8n image/version, and n8n edition.
4. Sanitized runtime evidence is hashed and independently reviewed; `config/runtime-paths.json` becomes `VERIFIED` in a separate PR.
5. Middleware endpoint binding, exact approved HTTPS base, credential type/name binding, protected editor access, session policy, authentication, egress controls, excluded-node policy, and any task-runner requirement are reviewed; `config/n8n-policy.json` becomes `VERIFIED`.
6. Exact immutable n8n image digest plus vulnerability report, SBOM, provenance, signature identity/issuer, and signature bundle are verified.
7. PostgreSQL and n8n-state backups are restored successfully in isolation.
8. Staging secrets are provisioned outside Git with least-privilege database and Redis identities.
9. All live-write, delivery, messaging, dialing, publishing, crawler-writeback, payment, and replay flags remain false.
10. Kong/Caddy routing, identity mapping, rate limit, allowlist, HMAC, duplicate-delivery, replay, tenant-isolation, and egress tests pass.
11. Rollback to a different previously approved immutable digest is exercised with measured recovery time.
12. A future deployment implementation uses a protected staging environment for the exact release tuple; the current preflight remains read-only and has no deployment-environment access.
