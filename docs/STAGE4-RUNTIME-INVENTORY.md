# Stage 4 runtime-to-Git inventory

Read-only inspection on 2026-08-28 covered `/opt/codestra/compose` (production) and `/opt/codestra/n8n-staging` (staging). Neither directory was modified.

| Item | Production | Staging |
|---|---|---|
| Compose | `compose.yaml` plus n8n hardening/trust overlays | `compose.yaml`, `compose.queue.override.yaml` |
| n8n image | digest `sha256:115240...ca8` in base production compose | digest `sha256:cfe270...478` |
| PostgreSQL | external env/secrets; named volume | `postgres`, database/user `n8n_staging`, external env file |
| Redis | external env/secrets | queue override, ACL files, named volume |
| workflow mount | runtime-managed database | `./workflows:/staging-import:ro` |
| credentials | encrypted n8n data/external secret files | `/etc/codestra/secrets/n8n-staging/n8n.env` and encrypted n8n data |
| Middleware | internal Middleware service/network references | Middleware URLs on ports 8095 |
| direct providers | production platform contains provider services | direct Odoo and callback variables exist; synthetic VICIdial URL exists |
| `NODES_EXCLUDE` | not present in inspected active wiring | not present in inspected active wiring |
| import mechanism | no Git-controlled automatic import found | read-only `/staging-import` mount; no approved immutable import release found |

Secret-bearing references were recorded without values: `DB_POSTGRESDB_PASSWORD=SET`, `N8N_ENCRYPTION_KEY=SET`, `REDIS_PASSWORD=SET`, provider/API secret-file references=`SET`. No secret value was read or copied.

The current staging runtime is not Middleware-only because `ODOO_STAGING_BASE_URL`, `N8N_ODOO_BASE_URL`, and an Odoo provisioning callback URL are configured. Write flags observed in compose remain false. Git templates do not contain these direct targets. This unsafe drift blocks a staging release until a separately approved immutable cutover removes direct-provider ownership and applies the node policy.
