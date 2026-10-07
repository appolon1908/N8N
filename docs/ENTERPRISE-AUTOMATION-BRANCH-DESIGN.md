# Enterprise automation branch design

## Platform rule

Codestra runs one shared enterprise n8n platform. n8n coordinates automation steps, timers, approvals, retries, reminders, and exception routing. Middleware remains the only cross-system command and event authority.

Every automation path follows this shape:

```text
source software
  -> Middleware durable event or command boundary
  -> n8n orchestration workflow
  -> Middleware governed command API
  -> destination software
```

n8n must not call Odoo, product databases, SMTP, SMS providers, telephony systems, social providers, crawlers, Keycloak administration, Redis, PostgreSQL, NATS, Temporal, Kong, or Caddy directly.

## Professional operating model

```text
+---------------------------------------------------------------------+
| Business and provider systems                                       |
| Odoo | MoneyBee | Beyvra | LARIM-A | Freight | Breero              |
| Booked4Seasons | Trading | VICIdial | Telnexa | Klyrow             |
| Kyqra | Postly | Provisioning                                      |
+-------------------------------+-------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
| Middleware: tenant, actor, policy, idempotency, ledger, outbox, DLQ  |
+-------------------------------+-------------------------------------+
                                | private authenticated wake/claim
                                v
+---------------------------------------------------------------------+
| n8n enterprise orchestration platform                               |
| CP-COMMON-ERROR-* plus one isolated CP-* workflow family per domain  |
+-------------------------------+-------------------------------------+
                                | governed command only
                                v
+---------------------------------------------------------------------+
| Middleware adapters translate approved commands to destination APIs  |
+---------------------------------------------------------------------+
```

## Individual branch lanes

| Lane | Branch | Workflow group | Direct n8n access |
|---|---|---|---|
| Shared runtime and error handling | `shared/automation-runtime-v2-20260827` | `CP-COMMON-ERROR-*` | Middleware only |
| Automation contract | `contract/automation-control-plane-v2-20260827` | contract source | Middleware only |
| Odoo CRM | `automation/odoo-crm-v2-20260827` | `CP-ODOO-*` | denied |
| VICIdial telephony | `automation/vicidial-telephony-v2-20260827` | `CP-VICIDIAL-*` | denied |
| Telnexa SMS | `automation/telnexa-sms-v2-20260827` | `CP-TELNEXA-*` | denied |
| Klyrow email and SMTP relay | `automation/klyrow-email-v2-20260827` | `CP-KLYROW-*` | denied |
| Kyqra crawler | `automation/kyqra-crawler-v2-20260827` | `CP-KYQRA-*` | denied |
| Postly social | `automation/postly-social-v2-20260827` | `CP-POSTLY-*` | denied |
| Provisioning lifecycle | `automation/provisioning-v2-20260827` | `CP-PROVISIONING-*` | denied |
| Identity service identities | `automation/identity-keycloak-v2-20260827` | `CP-PROVISIONING-*` support | denied |
| MoneyBee | `automation/moneybee-loans-v2-20260827` | product family | denied |
| Beyvra | `automation/beyvra-operations-v2-20260827` | product family | denied |
| LARIM-A | `automation/larim-a-booking-v2-20260827` | product family | denied |
| Freight Platform | `automation/freight-operations-v2-20260827` | product family | denied |
| Breero | `automation/breero-marketplace-v2-20260827` | product family | denied |
| Booked4Seasons | `automation/booked4seasons-v2-20260827` | product family | denied |
| Trading operations | `automation/trading-operations-v2-20260827` | product family | denied |

## Review gates

Each branch must carry its own workflow exports, tests, rollback notes, capability flags, and runtime evidence. Branches are imported inactive by default. Credentials stay in the n8n credential store. The only allowed outbound automation endpoint is the reviewed Middleware automation API:

```text
POST /v2/automation/commands
GET  /v2/automation/commands/{command_id}
```
