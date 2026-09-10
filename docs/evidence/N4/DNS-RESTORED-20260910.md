# n8n editor DNS repair — 2026-09-10

The existing GoDaddy API integration on provider host `37.27.128.39` restored the missing editor DNS records for the core application host.

| Name | Type | Value | TTL |
| --- | --- | --- | --- |
| n8n.codestra.co | A | 65.109.65.169 | 600 |
| automation.codestra.co | A | 65.109.65.169 | 600 |

Both narrowly scoped writes returned HTTP 200. GoDaddy readback confirms the two records, and all 39 previous zone records are unchanged. A protected before/after snapshot, plan, and verification evidence are retained on the execution host at the path in the adjacent JSON record.

At 11:17:18 UTC, both authoritative nameservers (ns25.domaincontrol.com and ns26.domaincontrol.com) and both checked public resolvers (1.1.1.1 and 8.8.8.8) returned 65.109.65.169 for both names. All eight DNS checks passed.

DNS repair does not certify the editor rollout. An HTTPS probe directed to the core server still failed its TLS handshake for both hostnames. The N8N/Keycloak v1 hostname contract and the Caddy v2 automation hostname contract also require reviewed reconciliation. The existing runtime, authentication gates, and workflow activation states were not changed.

The older COMMUNITY-AUTHORITY-STATUS.md is historical evidence. Its missing-DNS finding is superseded by this record; its remaining deployment prerequisites are not cleared by DNS creation.
