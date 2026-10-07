# Reference baseline

Reviewed against official documentation on 2026-08-26. Runtime behavior must still be tested against the exact immutable n8n image selected for release.

## GitHub Actions

- Workflow syntax and permissions: https://docs.github.com/actions/writing-workflows/workflow-syntax-for-github-actions
- Secure use reference: https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- Repository Actions settings: https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/disabling-or-limiting-github-actions-for-a-repository

## n8n deployment and security

- Security environment variables: https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/security/
- Block specific nodes: https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/block-specific-nodes/
- Disable the public REST API: https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/disable-the-public-api/
- Queue mode: https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode/
- Queue-mode environment variables: https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/queue-mode/
- Binary data in queue mode: https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/handle-binary-data/
- Task runners and production isolation: https://docs.n8n.io/deploy/host-n8n/configure-n8n/set-up-task-runners/
- File-based environment configuration: https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/
- Community versus paid feature availability: https://docs.n8n.io/deploy/host-n8n/community-edition-features/
- Health and readiness monitoring: https://docs.n8n.io/deploy/host-n8n/keep-n8n-running/monitor-n8n/
- User management: https://docs.n8n.io/deploy/host-n8n/configure-n8n/user-management/
- OIDC setup and edition-dependent SSO: https://docs.n8n.io/administer/manage-users-and-access/verify-user-identity/use-oidc/set-up-oidc/
- User-access best practices: https://docs.n8n.io/administer/manage-users-and-access/follow-best-practices/
- Credential management: https://docs.n8n.io/build/understand-workflows/create-and-edit-credentials/

## Review rule

Documentation is not runtime evidence. Version, edition, configuration parsing, health endpoints, database/Redis behavior, secret-file support, reverse-proxy behavior, and migration/rollback compatibility must be proven using the exact release digest in isolated staging.
