# Controlled Stage 4 staging cutover

This document specifies a future release; it does not authorize deployment.

1. Validate an exact Git SHA in CI, including workflow, secret, architecture, and policy gates.
2. Build an immutable n8n artifact/image and record its digest, workflow inventory, and configuration hashes.
3. Review and approve a staging manifest pinned to that digest and an external credential-store binding.
4. Compare the manifest with the runtime using `scripts/audit_runtime_drift.py`.
5. Deploy only in a separately approved change window. Never use `git pull` as a runtime release mechanism.

Rollback selects the previous approved image digest and configuration release, reapplies the prior manifest, and verifies workflow inventory and inactive state. Database rollback is a separate, explicitly approved procedure; this preparation does not alter PostgreSQL.
