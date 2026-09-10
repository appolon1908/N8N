# Codestra editor login

The login assets in `orbit/login/` provide the Codestra entry page for the community-edition editor at `https://n8n.codestra.agency`. They use oauth2-proxy's supported Go HTML templates and the shared Codestra black-and-white identity language.

The visual source of truth is the Codestra social authentication shell: near-black `#0b0b0b` page background, `#171717` bordered panel, white primary controls and typography, muted `#a1a1aa` supporting text, restrained 16 px / 10 px radii, and responsive desktop/mobile layouts. The n8n page uses the same design language without copying product imagery or introducing external fonts, tracking, or JavaScript.

`sign_in.html` submits to the gateway's `/oauth2/start` route and preserves the requested workspace path. Keycloak handles credentials and MFA. The gateway requires the `n8n_operator` or `n8n_admin` role. After that gate, n8n's native account login, sessions, CSRF protection and workspace permissions still apply. `error.html` renders generic errors without provider messages or configuration details.

## Integration

The companion Caddy repository mounts the complete `orbit/login` directory read-only at `/etc/oauth2-proxy/templates`, enables custom templates and keeps the provider button visible. Set `N8N_LOGIN_TEMPLATE_DIR` to that directory in the approved, revision-verified N8N checkout. Both template files are required because they share definitions. The bind mount refuses to create a missing source directory.

The shared Keycloak repository owns the credential and MFA appearance. The realm remains on the specialized `codestra-identity` theme; that theme inherits the `codestra` visual base so specialized identity/OTP templates are retained while the common black-and-white CSS is applied.

## Verification

Run `python3 scripts/test_editor_login.py` or `make validate` with Docker available. The test renders both templates using oauth2-proxy v7.15.2 pinned by digest in the script. It checks the black-and-white visual contract, the entry form and return path, PKCE/state creation, secure CSRF cookie, anonymous editor denial and generic access error. The disposable container has no network and no published ports, and uses only synthetic credentials. This verifies rendering and the unauthenticated protocol boundary; it does not certify a successful production login or role-bearing token exchange.

For inspecting rendered HTML, pass `--render-dir` with a temporary directory outside the checkout. Browser visual acceptance still requires a rendered authenticated implementation comparison at desktop and narrow widths.

## Runtime status on 2026-09-10

The production editor's Caddy route still restricts access to the staff network and returns `Staff identity network required` elsewhere. Previous read-only inspection found no deployed `n8n-editor-gateway` Keycloak client, gateway container or gateway secret directory. Identity production mutation is controlled by the existing certification contract. Complete the normal reviewed identity and ingress apply path before replacing that boundary with the gateway. These source files do not activate workflows, authorize database migration or certify runtime deployment.

The `.agency` HTTPS certificate passed public-chain and hostname validation and expires on 2026-10-18. Chrome's reported Dangerous warning remains unresolved; Google's public report returned no available data for the hostname. Browser visual and successful user-login verification remain outstanding.
