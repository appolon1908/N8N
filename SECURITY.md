# Security policy

## Supported state

Only pull-request heads that pass exact-SHA validation are supported. The current repository state is source-only and not approved for production activation.

## Never commit

- n8n credential exports or encryption keys
- database, Redis, SMTP, SMPP, OAuth, API, webhook, or signing secrets
- private keys, certificates with private material, tokens, cookies, or session data
- live `.env` files, server backups, database dumps, or Odoo filestore archives
- raw runtime audit output that includes secrets or customer data

## Reporting

Open a private security report with the repository owner. Do not include a usable secret in an issue or pull-request comment. Revoke and rotate any exposed secret before continuing review.

## Security invariants

1. n8n communicates with business systems only through Codestra middleware.
2. Inbound machine events use a canonical timestamped HMAC signature, replay window, and durable event-id deduplication before side effects.
3. Every external effect is guarded by tenant authorization, suppression/privacy checks, integration pause flags, and a global kill switch immediately before dispatch.
4. Production images are immutable digest references with SBOM, provenance, signature verification, and exact source-SHA identity.
5. Runtime paths and ownership must be verified read-only before any deploy command is added or enabled.
