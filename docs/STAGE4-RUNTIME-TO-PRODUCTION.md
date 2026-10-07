# Stage 4 Runtime Gate to Production

N8N is not production-ready because workflow branches exist. Production requires
runtime evidence in the exact order below, with Middleware remaining the only
cross-system write authority.

## Required order

1. Middleware PR #45 or its successor passes exact-head CI for original bearer
   authorization.
2. Staging Middleware migration ancestry is repaired, including the missing
   `0053_callback_worker_grants` revision problem.
3. `auth.codestra.co` and `api.codestra.co` resolve and are reachable from the
   staging execution environment.
4. The live Keycloak -> Kong -> Middleware authorization matrix passes.
5. CP-ODOO runs in staging through Middleware with all delivery flags off and
   zero unexpected DLQ entries.
6. Production approval is attached to an immutable release manifest with source
   SHA, image digest, workflow export hashes, backup/restore proof, rollback
   proof, and independent approval.

The executable gate lives in the Middleware repository:

```bash
python scripts/verify_stage4_runtime_gate.py --allow-no-go
```

Strict production mode must fail until all six steps are `PASS`:

```bash
python scripts/verify_stage4_runtime_gate.py
```

Do not activate n8n workflows, add direct provider credentials, enable SMTP/SMS/
telephony/social/crawler delivery, mutate Odoo, or import active production
workflows while that gate reports `NO_GO`.
