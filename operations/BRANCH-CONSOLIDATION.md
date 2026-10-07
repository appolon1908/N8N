# Pre-canonical branch preservation

The exact pre-consolidation remote references were captured on 2026-08-28 before branch deletion. `pre-canonical-branch-map.tsv` groups the 72 remote references by their 16 unique commit tips. The unmerged live-server evidence branch is retained separately as `import/server-n8n-20260828`.

Before removing stacked remote branches, each unique non-main, non-capture tip must be preserved by an immutable `archive/pre-canonical-20260828/<short-sha>` tag. The source branch map and archive tags are evidence, not deployable release references.
