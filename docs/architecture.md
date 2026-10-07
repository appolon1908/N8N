# Architecture

## Control plane

```text
Business and provider systems
+---------------------------------------------------------------------+
| Odoo | MoneyBee | Beyvra | LARIM-A | Freight | Breero              |
| Booked4Seasons | Trading | VICIdial | Telnexa | Klyrow             |
| Kyqra | Postly | Provisioning                                      |
+-------------------------------+-------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
| Caddy TLS edge -> Kong API gateway -> Keycloak identity validation  |
+-------------------------------+-------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
| Codestra Middleware: policy, tenant, idempotency, inbox/outbox, DLQ  |
+-------------------------------+-------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
| n8n orchestration workers: sequencing, approvals, retries, timers   |
+-------------------------------+-------------------------------------+
                                |
                                v
+---------------------------------------------------------------------+
| Codestra Middleware adapters: all destination writes and callbacks   |
+---------------------------------------------------------------------+
```

## Trust boundaries

### Public edge

Caddy terminates public TLS. Kong enforces route-specific authentication, rate limits, allowlists, and machine identity mapping. Public callbacks must not terminate directly at n8n.

### Middleware boundary

Middleware is the only component allowed to translate automation intent into service-specific commands. It owns:

- tenant and actor authorization
- idempotency and optimistic concurrency
- timestamped HMAC verification and replay protection
- suppression, consent, privacy deletion, and retention rules
- per-integration pause controls and the global external-delivery kill switch
- durable inbox/outbox state, retries, dead-letter handling, and audit records

### n8n boundary

n8n coordinates approved sequences. It does not own authorization, canonical business state, credentials for direct database access, or policy decisions. Workflow exports are inactive in Git and may reference only `MIDDLEWARE_BASE_URL` for outbound HTTP.

## Data ownership

| Domain | System of record | n8n role |
|---|---|---|
| Identity and machine clients | Keycloak / middleware identity map | consume scoped identity context |
| CRM records | Odoo through middleware | orchestrate approved commands |
| Calls and dispositions | VICIdial plus middleware audit | schedule and reconcile |
| SMS delivery | Jasmin through middleware | sequence approved sends |
| Email delivery | Postal/Klyrow through middleware | sequence approved sends |
| Crawl jobs and results | Kyqra through middleware | schedule and reconcile |
| Social publication | Postly through middleware | coordinate approved publications |
| Provisioning | Middleware provisioning adapters | sequence approved lifecycle commands |
| MoneyBee workflows | MoneyBee through middleware | coordinate non-financial operations |
| Beyvra workflows | Beyvra backend through middleware | coordinate Beyvra platform support, compliance, reports, and status workflows; separate from Trading |
| LARIM-A workflows | LARIM-A through middleware | coordinate booking and dispatch |
| Freight workflows | Freight platform through middleware | coordinate shipment and document operations |
| Breero workflows | Breero through middleware | coordinate marketplace operations |
| Booked4Seasons workflows | Booked4Seasons through middleware | coordinate booking operations |
| Trading workflows | Trading platform through middleware | coordinate the separate Trading lane under its own approval and capability policy |
| Delivery state | middleware inbox/outbox | monitor, retry only through governed APIs |
| Workflow definitions | this repository | reviewed source of truth |

## Isolation

Every command carries tenant, correlation, event, and idempotency identifiers. Batch jobs must preserve per-company isolation: one company failure cannot roll back, unlock, or replay another company without an explicit operator action.
