## Agent skills

### Issue tracker

Issues tracked as GitHub Issues in jhulten/src-get via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical triage labels (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root (created lazily as concepts get resolved). See `docs/agents/domain.md`.

### src-get usage skill

Agent-facing skill for using the `src-get` tool lives at `skills/src-get/SKILL.md`. Update it whenever the CLI surface or the stdout/stderr contract changes: flags or args (`main()` in `src/src_get/__init__.py`), root resolution precedence, the get-vs-update behavior, or the "repo path is the last line of stdout" guarantee. Keep it in sync with `README.md` and `SPEC.md`.

### Release task

The `mise run release` task lives in `mise.toml` (interactive next-version picker: shows the diff since the last `v*` tag, then patch/minor/major/exact). Keep the README "Release" section in sync whenever the task's interface changes: the accepted arguments (`patch`/`minor`/`major`/exact version), the interactive flow, or the branch/PR steps. The downstream half lives in `.github/workflows/finish-release.yml`.
### Branch hygiene

When cleaning up merged branches, **leave release branches alone** (e.g. `release/v*`). Do not delete them locally or on the remote. Only prune feature/fix/docs/test branches whose content is fully contained in `main`.
