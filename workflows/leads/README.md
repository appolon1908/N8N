# Leads Workstation integration

Branch: `mission/leads-workstation-integration-20260923`

## Responsibility

N8N is the downstream automation engine after a lead is accepted into canonical lead state.

Examples:
- enrichment;
- assignment;
- notifications;
- campaign routing;
- scheduled next actions;
- external-system synchronization.

## Authority rule

N8N must call the Leads-Workstation API or another governed command boundary. It must not write canonical lead PostgreSQL tables directly.

## Event path

`Leads-Workstation outbox/event -> N8N workflow -> governed action -> Leads-Workstation API -> audit/readback`

## Acceptance

- replay/idempotency;
- auth/callback protection;
- dead-letter/failure behavior;
- no direct canonical DB credential;
- exact input/output fixtures;
- readback proving the intended lead change.
