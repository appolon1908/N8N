# Stage 4 divergence reconciliation

Canonical Stage 4 is `f5693d41ce190c343bcb6644334699b335352343`. The server recovery line ending at `413db0fba13dde5cef987ccbe32b282a2b352500` remains preserved and was not cherry-picked.

| SHA | Subject | Classification | Affected files | Stage 4 replacement | Recommendation and forward risk |
|---|---|---|---|---|---|
| `413db0f` | fix: close recurring recovery review gaps | recovery tooling; should be ported separately | readiness rules, backup script, systemd timer | No | Rebase as a dedicated operations PR after review. Medium risk: timers and retention operate on live state. |
| `9af8855` | Automate complete n8n recovery points | recovery tooling; should remain separate | metrics script; backup script/service/timer | No | Keep outside Stage 4 authority work and port through an operations release. High risk: backup consistency, permissions, storage and scheduling. |
| `2bd5725` | Merge PR #14 runtime certification | runtime operations; should remain separate | merge commit (content from `ae3ccbe`) | Partly superseded by this inventory, not by code | Do not replay merge commits. Low code risk, high risk of stale certification claims. |
| `ae3ccbe` | Record runtime certification and readiness controls | runtime operations/configuration; should be ported selectively | credential audit, activation intent, staging certification, metrics/readiness | This mission replaces inventory claims only | Revalidate evidence and port observability separately. Medium risk: dated runtime evidence can be mistaken for current approval. |
| `5703d0e` | Merge PR #12 governance baseline | configuration; obsolete merge commit | merge commit (baseline ancestry) | Yes, canonical Stage 4 contains the evolved baseline | Do not cherry-pick. High conflict/duplicate-history risk. |

Stage-4-only commits are `5b07017` (governance fixes), `99709a1` (Klyrow dependency), `9374b34` (Middleware-routed SMTP clarification), and `f5693d4` (CP templates). They remain canonical.
