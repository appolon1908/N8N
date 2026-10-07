## Purpose

Describe the product, service, middleware contract, automation, design, or deployment-control change.

## Safety declaration

- [ ] Live servers were not changed by this pull request.
- [ ] No secret, credential export, customer data, or private key is included.
- [ ] All workflow exports are inactive.
- [ ] n8n calls middleware only; no direct business-system access was added.
- [ ] External delivery and live-write capabilities remain disabled unless a separately approved activation change is attached.
- [ ] Runtime paths are still `UNVERIFIED`, or new verification evidence is attached with a digest and independent review.

## Evidence

- Exact head SHA:
- CI run:
- Runtime audit digest, when applicable:
- SBOM/provenance/signature evidence, when applicable:
- Rollback evidence, when applicable:

## Review gates

- [ ] Exact-head source validation passes.
- [ ] Security boundary review passes.
- [ ] Independent approval applies to the final unchanged SHA.
- [ ] Protected merge only; no admin bypass.
