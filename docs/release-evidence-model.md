# Release evidence model

The source repository separates three gates that must not be conflated.

## 1. Source and policy validation

`make validate` checks source invariants, inactive workflows, secret patterns, semantic Compose policy, and the current runtime-policy state. It does not contact a runtime or provider.

## 2. Release-manifest schema validation

`scripts/release_manifest_schema_check.py` checks that a proposed manifest:

- names an exact full Git SHA;
- names immutable candidate and distinct rollback image digests;
- binds the current runtime, capability, and n8n policy file digests;
- carries non-placeholder references for required evidence;
- records independent requester and approver identities;
- keeps the source-only capability matrix disabled.

A pass means only:

```text
RELEASE_MANIFEST_SCHEMA_VALIDATION=PASS
```

It does not establish that the referenced evidence artifacts are authentic or correct.

## 3. Protected artifact verification

A later protected workflow or operator procedure must receive the actual artifacts and independently:

- calculate every SHA-256;
- verify the image digest and exact source identity;
- verify the signature bundle, issuer, and identity;
- verify provenance subjects and materials;
- evaluate the vulnerability report against policy;
- inspect and exercise backup/restore evidence;
- inspect network-policy evidence;
- exercise rollback to a distinct approved digest.

Only that separate gate may report signature, provenance, vulnerability, backup/restore, network, or rollback verification. Neither gate deploys by itself.
