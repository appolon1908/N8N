# Runtime-path verification

Runtime discovery is a read-only evidence task. It is not deployment.

## Candidate server identity

Prior inventory identifies public IP `65.109.65.169`, private IP `10.40.0.1`, and candidate working tree `/root/codestra-production-completion`. These values remain candidates until the audit proves the hostname, container labels, mount sources, Compose files, service ownership, and network attachment on the live host.

## Collect evidence

Run the repository's audit script locally on the target host from a trusted checkout:

```bash
python3 operations/runtime_path_audit.py
```

The script prints JSON to standard output and performs no write. It does not inspect container environment variables, secret contents, database rows, workflow credentials, or customer data.

## Evidence required for each path

- absolute canonical path
- file type or directory type
- owner UID/GID and permission mode
- related container and Compose project labels
- mount source and destination, when applicable
- filesystem/device identity where relevant
- audit timestamp in UTC
- auditor identity
- SHA-256 of the sanitized audit artifact
- independent reviewer identity and review timestamp

## State transition

`UNVERIFIED -> VERIFIED` requires a pull request that updates `config/runtime-paths.json`, includes evidence digests, passes exact-head CI, and receives independent approval. A path may not be inferred from a prior chat, README, process name, or expected convention.

## Prohibited during discovery

Do not restart containers, render secret-bearing Compose output, run migrations, import workflows, change file ownership or modes, create symlinks, write `.env` files, attach networks, rotate credentials, or modify Caddy/Kong routes.
