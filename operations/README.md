# Operations tooling

`runtime_path_audit.py` performs read-only discovery of:

- host identity, OS/kernel summary, and a non-reversible machine-id fingerprint prefix;
- relevant Docker container names, configured images, local image repo digests, safe Compose/OCI labels, mounts, networks, exposed container-port keys, health, configured user, read-only-rootfs state, capability drops, security options, and restart policy;
- candidate Compose file paths under `/root`, `/opt`, `/srv`, and `/etc/codestra`;
- candidate n8n directories plus owner IDs and permission modes, without reading file contents.

It deliberately excludes container environment variables, secret contents, database queries, workflow data, logs, and customer information. It does not restart, exec into, update, or otherwise mutate a container.

```bash
python3 operations/runtime_path_audit.py
```

Review the JSON before storing it as evidence. Remove unrelated internal paths, hash the sanitized artifact, and attach only the digest and approved evidence location to the runtime-verification pull request. The audit cannot determine licensed n8n features by itself; edition and endpoint-binding support require a separate read-only verification.
