# Deployment scaffolding

This directory is intentionally non-applying.

- `compose/compose.staging.yml` is a hardened template that publishes no host port and requires externally provisioned secrets, PostgreSQL, Redis, the n8n data volume, a Middleware network, and an immutable image input.
- `env/ci.env` contains non-secret syntax-validation values only.
- `env/staging.example.env` contains placeholders only.
- `manifests/release.example.json` documents the fail-closed release-manifest assertion contract. The deployment preflight can validate this committed example for wiring, a repository-relative manifest path, or a compact manifest supplied through the manual workflow input.
- The GitHub `deployment-preflight` workflow validates repository state and manifest assertions, then exits. It contains no remote connection or deploy command.

The Compose policy renders the template with `docker compose config --format json` and validates the semantic model. It requires exactly the main and worker services, an external data volume, external secrets and private network, immutable image references, non-root/read-only hardening, exact secret/network mounts, reviewed environment controls, and fail-closed readiness probes.

The template disables n8n's public API and API playground, blocks workflow access to environment variables and local n8n files, excludes dangerous nodes including Code and Execute Command, uses database binary-data mode because queue mode does not support filesystem binary storage, and gives each worker a local readiness probe for its database and Redis connections.

The Middleware endpoint, credential, and editor-access bindings are deliberately unresolved. Templates use `middleware.invalid` with no credential reference; no routable endpoint or authentication profile is introduced until the n8n edition, private DNS/network path, egress policy, credential mechanism, and non-public editor access are verified.

## Evidence boundary

`release_manifest_schema_check.py` validates the manifest shape, exact source binding, repository policy digests, declared approvals, and declared evidence digests. It does **not** open, hash, cryptographically verify, or evaluate the referenced SBOM, provenance, signature bundle, vulnerability report, backup/restore, network, or rollback artifacts. Those checks require a later protected evidence-verification job with the exact artifact files available.

Do not describe a passing manifest check as signature, provenance, vulnerability, backup, network, or rollback verification. Do not run the Compose template against a live server until `config/runtime-paths.json` and `config/n8n-policy.json` are independently verified and a separate deployment-implementation pull request is approved.
