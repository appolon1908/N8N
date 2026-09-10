# Klyrow workflow pack

Klyrow automations governed as a pack in this canonical repository.

n8n never connects directly to Klyrow, Postal, or SMTP. It requests durable jobs from Codestra Middleware; Middleware owns authorization, idempotency, provider submission, reconciliation, and the fixed alert-recipient policy. See `../observability/README.md` and `../../contracts/observability-alert-observer.v1.json`.
