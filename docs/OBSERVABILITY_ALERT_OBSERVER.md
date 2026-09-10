# Governed observability alert observer

n8n participates in the alert system as an orchestration and status-observation layer. It does not send email or SMS directly.

## Runtime path

```text
Prometheus -> Alertmanager -> Middleware alert API
  -> durable command/outbox -> Temporal -> Klyrow email adapter
  -> Klyrow private API -> fixed recipient
```

Middleware may publish authenticated lifecycle events to n8n for correlation, escalation bookkeeping, and operator visibility. n8n returns results only through Middleware.

## Security boundary

- Public n8n webhooks are prohibited.
- n8n may call only Codestra Middleware.
- Klyrow, Postal, SMTP, Telnexa, and Jasmin credentials do not belong in n8n.
- Recipient and sender policy are fixed in Middleware, not workflow input.
- SMS live delivery is not required for email alerting and remains disabled.
- Repository workflows remain inactive until the reviewed production activation step.

The machine identity issuer is `https://auth.codestra.co/realms/codestra`. Runtime credentials are injected server-side and must never be committed.
