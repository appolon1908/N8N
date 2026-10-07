# n8n node security policy

Stage 4 permits control-flow, data-shaping, triggers, and HTTP Request nodes. HTTP Request is constrained by static validation to `/v2/automation/*` on the reviewed Middleware origin. Authentication belongs to the n8n credential store.

The example `NODES_EXCLUDE` policy removes Execute Command, Code, SSH, FTP, Git, local file access, arbitrary database/Redis nodes, Odoo, Twilio, and direct email. These nodes can bypass the command ledger, outbox, Temporal verification, capability flags, or audit trail. Environment access, external modules, and access to n8n's own files are also blocked.

An exception requires a threat model, named owner, exact node/type and destination, least-privilege credential reference, expiry date, tests, security review, and a policy change through pull request. Provider transport is not an exception: Middleware is the cross-system write authority.
