# Deployment runbook

## Phase 0 — source review

1. Review the final pull-request diff and exact head SHA.
2. Confirm exact-head CI exists and passes; a missing status is not a pass.
3. Confirm every workflow is inactive, only disabled no-credential templates exist while endpoint, credential, or editor policy is unverified, and every external-effect capability is false.
4. Confirm GitHub Actions use only reviewed SHA-pinned actions with read-only permissions and no secret, self-hosted-runner, or deployment-environment access.
5. Obtain independent approval on the unchanged final SHA.
6. Merge only through an active protected-branch ruleset.

## Phase 1 — runtime and edition verification

1. Run `operations/runtime_path_audit.py` read-only on the target server.
2. Sanitize and hash the output.
3. Verify hostname/IP identity, Compose project labels and files, n8n data storage, reverse-proxy configuration, external secret references, networks, owners, modes, backup locations, container image/version, and edition/license capabilities.
4. Update `config/runtime-paths.json` in a separate PR with per-item evidence digests.
5. Select and review one middleware endpoint strategy in `config/n8n-policy.json`: proven custom variable, reviewed custom node, or fixed verified private DNS with egress enforcement.
6. Verify a credential-binding strategy, exact allowed credential types/names, and evidence digest; keep raw credentials out of Git. Keep workflow environment access, public API, Code, command, local-file, SSH, FTP, and Git nodes disabled unless a separate security design proves an alternative.
7. Verify the editor route is not directly public, select a reviewed private-admin or gateway-OIDC-plus-native-auth strategy, and record session-policy evidence. Record independent verifier/reviewer identities and evidence digests for endpoint, egress, credential, edition, editor, and runtime decisions. Do not deploy in this phase.

## Phase 2 — immutable release preparation

1. Build from the exact protected merged SHA.
2. Publish n8n and any required companion image by immutable digest; never deploy a mutable tag alone.
3. Generate and verify SBOM, provenance, signature bundle, signing identity/issuer, vulnerability report, and source-to-image identity.
4. Prove PostgreSQL and n8n-state backup/restore in isolation.
5. Exercise rollback to a different previously approved immutable digest.
6. Create `deploy/manifests/release.json` outside the feature branch with exact digests for runtime policy, n8n policy, capabilities, restore, network, and rollback evidence.
7. Run `deployment-preflight`; it validates only and never deploys.

## Phase 3 — isolated staging

1. Restore sanitized state into isolated PostgreSQL and n8n storage.
2. Keep every capability in `config/capabilities.json` false.
3. Start staging only after runtime paths, endpoint binding, credential binding, editor access, secret provider, database role, Redis identity, and private network are verified.
4. Use database binary-data mode in queue mode unless a separately reviewed shared object-storage design is approved.
5. If Code is required, use external task-runner sidecars for every execution worker, matching immutable versions and hardened with no secret mounts or unapproved modules. Otherwise keep Code excluded.
6. Validate main-process health plus each worker's `/healthz/readiness` database/Redis probe, version identity, restart behavior, queue behavior, migrations, rollback, HMAC replay rejection, idempotency, tenant/company isolation, dead-letter review, Odoo/n8n duplicate delivery, egress controls, and Kong/Caddy controls.
7. Confirm zero calls, messages, emails, lead publications, payments, callbacks, crawler writebacks, or provider writes.

## Phase 4 — production canary

A later, separately approved change may add a production deployment implementation. The first production deployment must still keep external effects disabled, prove the exact source/image/runtime tuple, validate monitoring and rollback, and receive explicit protected-environment approval before any narrowly scoped capability canary.

## Rollback invariant

Rollback selects a different previously approved immutable image and a compatible, tested schema/state path. It never rebuilds from source during an incident and never assumes database downgrade safety without restore and rollback evidence.
