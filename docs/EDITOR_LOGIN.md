# Codestra editor login

The login assets in `orbit/login/` provide the Codestra entry page for the community-edition editor at `https://n8n.codestra.agency`. They use oauth2-proxy's supported Go HTML templates and the colors of the existing Codestra Keycloak theme.

`sign_in.html` submits to the gateway's `/oauth2/start` route and preserves the requested workspace path. Keycloak handles credentials and MFA. The gateway requires the `n8n_operator` or `n8n_admin` role. After that gate, n8n's native account login, sessions, CSRF protection and workspace permissions still apply. `error.html` renders generic errors without provider messages or configuration details.

## Integration

The companion Caddy repository change mounts the complete `orbit/login` directory read-only at `/etc/oauth2-proxy/templates`, enables custom templates and keeps the provider button visible. Set `N8N_LOGIN_TEMPLATE_DIR` to that directory in the approved, revision-verified N8N checkout. Both template files are required because they share definitions. The bind mount refuses to create a missing source directory.

The companion Keycloak change aligns the `n8n-editor-gateway` callback, origin and logout allowlists with the production and staging `.codestra.agency` editor hosts. It selects the existing `codestra` login theme for this client. The deployed Keycloak image must include that theme.

## Verification

Run `python3 scripts/test_editor_login.py` or `make validate` with Docker available. The test renders both templates using oauth2-proxy v7.15.2 pinned by digest in the script. It checks the entry form and return path, PKCE/state creation, secure CSRF cookie, anonymous editor denial and generic access error. The disposable container has no network and no published ports, and uses only synthetic credentials. This verifies rendering and the unauthenticated protocol boundary; it does not certify a successful production login or role-bearing token exchange.

For inspecting rendered HTML, pass `--render-dir` with a temporary directory outside the checkout. The page uses no JavaScript, external fonts, tracking or local password collection.

## Runtime status on 2026-09-10

The production editor's Caddy route still restricts access to the staff network and returns `Staff identity network required` elsewhere. Read-only inspection found no deployed `n8n-editor-gateway` Keycloak client, gateway container or gateway secret directory. Identity production mutation is disabled by the existing certification contract. Complete the normal reviewed identity and ingress apply path before replacing that boundary with the gateway. These source files do not activate workflows, authorize database migration or certify runtime deployment.

The `.agency` HTTPS certificate passed public-chain and hostname validation and expires on 2026-10-18. Chrome's reported Dangerous warning remains unresolved; Google's public report returned no available data for the hostname. Browser visual and successful user-login verification remain outstanding.
