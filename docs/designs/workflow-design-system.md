# Workflow design system

## Naming

Workflow names use:

```text
<product>.<domain>.<action>.v<major>
```

Examples:

- `codestra.crm.lead-intake.v1`
- `telnexa.sms.delivery-reconcile.v1`
- `klyrow.email.delivery-reconcile.v1`
- `kyqra.crawler.job-result.v1`
- `moneybee.application.intake.v1`

Node names start with a verb and describe one responsibility: `Validate Envelope`, `Load Policy`, `Request Middleware Command`, `Record Result`, `Route Failure`.

## Canvas layout

1. Flow left to right.
2. Keep the success path on the center line.
3. Put validation and policy gates above the success path.
4. Put retries, dead-letter routing, and operator escalation below it.
5. Use sticky notes for trust boundaries, capability gates, and data-classification warnings.
6. One node performs one side effect.
7. Every side effect has a named error branch and a deterministic idempotency key.

## Required sections

Every executable workflow design contains:

- trigger and source identity
- reviewed middleware endpoint binding
- reviewed credential type/name binding, with no secret material in Git
- envelope validation
- tenant and correlation context
- idempotency/replay decision
- capability and integration-pause gate
- middleware command
- deterministic result handling
- bounded retry policy
- dead-letter/operator path
- audit fields and redaction rule

## Visual semantics

Use labels rather than relying on color alone:

- `INPUT` — trigger and envelope
- `POLICY` — authorization, consent, suppression, capability, pause
- `COMMAND` — middleware request
- `RESULT` — accepted, completed, rejected, duplicate
- `RETRY` — bounded transient retry
- `DLQ` — durable failure and human review

## Data minimization

Do not place raw passwords, tokens, full payment data, government identifiers, message bodies, call recordings, or unnecessary personal data into node names, static JSON, execution logs, or error messages. Use opaque record identifiers and retrieve protected fields only through the middleware when authorized.

## Activation

Git exports always use `"active": false`. Templates also declare `credential_binding=NO_CREDENTIALS`; executable exports are rejected until endpoint, credential, and editor-access policies are independently verified. Activation is a separately reviewed runtime operation bound to an immutable workflow checksum and a capability approval.
