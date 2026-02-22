# alpininsight/.github

Organization-level GitHub defaults and standards for all repositories in `alpininsight`.

## What this repository provides

- Default community health files for repositories that do not define their own:
  - `CONTRIBUTING.md`
  - `CODE_OF_CONDUCT.md`
  - `SECURITY.md`
  - `SUPPORT.md`
- Organization-wide issue and pull request templates
- Organization-wide workflow templates for new repositories
- Label definitions and sync automation

## Atomic design model used here

- Atoms: policy documents (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`)
- Molecules: collaboration templates (`.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE/*`)
- Organisms: automation templates (`.github/workflow-templates/*`, `.github/workflows/sync-labels.yml`)
- Templates: repository bootstrap standards and examples in `.github/README.md`

## Workflow templates

Canonical workflow templates that all repositories should adopt. See
[docs/centralized-workflows.md](docs/centralized-workflows.md) for full
documentation, troubleshooting, and adoption checklist.

| Template | Purpose | Prerequisites |
|----------|---------|---------------|
| `changelog.yml` | Auto-generate CHANGELOG.md via git-cliff with PR-based auto-merge | `cliff.toml`, `CHANGELOG_BOT_TOKEN` org secret |
| `gitversion.yml` | Calculate SemVer metadata from conventional commits | `GitVersion.yml` in repo root |
| `pr-branch-guard.yml` | Enforce branch naming conventions on PRs | -- |
| `release-pr-auto-merge.yml` | Auto-merge release PRs after checks pass | -- |

### Adoption checklist (per repo)

- [ ] Copy `changelog.yml` to `.github/workflows/`
- [ ] Ensure `cliff.toml` exists in repo root
- [ ] Ensure `GitVersion.yml` exists with `prevent-increment-of-merged-branch-version: false` on `main`
- [ ] Verify `CHANGELOG_BOT_TOKEN` org secret is accessible (visibility: ALL)
- [ ] Enable "Allow auto-merge" in repo Settings > General (recommended)

### Currently synchronized repositories

Tier 1 (active, with `develop` branch):
`insight-lima-k8s-capi`, `capi-provider-ssh`, `insight-ai-models`,
`hybrid-hw-foundation`, `insight-ci-claude`, `insight-ci`,
`insight-ci-claude-docs`, `insight-lima-k8s-dev`, `sources`

Tier 2 (adopted):
`legi-flow`, `posidra-gateway`, `sre`, `parl-q`, `insight-ui` (pending)

## Notes

- Keep these files generic and organization-wide.
- Repository-specific ownership (`CODEOWNERS`) and delivery pipelines should stay in each individual repository.

Copyright 2026 Alpin Insight Solutions GmbH & Co. KG
