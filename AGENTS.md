## Agent skills

### Issue tracker

Issues tracked as GitHub Issues in jhulten/src-get via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical triage labels (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root (created lazily as concepts get resolved). See `docs/agents/domain.md`.

### Branch hygiene

When cleaning up merged branches, **leave release branches alone** (e.g. `release/v*`). Do not delete them locally or on the remote. Only prune feature/fix/docs/test branches whose content is fully contained in `main`.
