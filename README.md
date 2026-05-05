# alpininsight/.github

Organization-level GitHub defaults and standards for all repositories in `alpininsight`.

## What this repository provides

- Default community health files for repositories that do not define their own:
  - `CONTRIBUTING.md`
  - `CODE_OF_CONDUCT.md`
  - `SECURITY.md`
  - `SUPPORT.md`
- Organization-wide issue and pull request templates
- Organization-wide workflow templates for new repositories. `.github-private`
  is the process source of truth, while this public repo provides
  public-compatible templates and mirrors where private workflow calls would not
  be reachable.
- Label definitions and sync automation

## Atomic design model used here

- Atoms: policy documents (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`)
- Molecules: collaboration templates (`.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE/*`)
- Organisms: automation templates (`.github/workflow-templates/*`) and public
  reusable workflow mirrors where public repositories cannot call private
  workflows directly.
- Templates: repository bootstrap standards and examples in `.github/README.md`

## Workflow templates

Canonical workflow templates that repositories should adopt. Private internal
repositories should use `.github-private@main` where possible. Public
repositories must use public-compatible templates or public workflow mirrors,
because GitHub does not allow public repositories to call private reusable
workflows. See
[docs/centralized-workflows.md](docs/centralized-workflows.md) for full
documentation, troubleshooting, and adoption checklist.

| Template | Purpose | Prerequisites |
|----------|---------|---------------|
| `changelog.yml` | Auto-generate CHANGELOG.md via git-cliff with PR-based auto-merge | `cliff.toml`, `CHANGELOG_BOT_TOKEN` org secret |
| `feature-ci.yml` | Public-compatible quality workflow caller | `pyproject.toml`, `uv.lock` |
| `gitversion.yml` | Calculate SemVer metadata from conventional commits | `GitVersion.yml` in repo root |
| `monorepo-version-manifests.yml` | Generate per-component version manifest artifacts for `projects/*` monorepos | `GitVersion.yml`, `projects/<component>/` layout |
| `pr-title-lint.yml` | Public-compatible PR title workflow | -- |
| `pr-branch-guard.yml` | Enforce branch naming conventions on PRs | -- |
| `release.yml` | Public-compatible GitVersion release workflow | `GitVersion.yml` |

### Adoption checklist (per repo)

- [ ] Copy `changelog.yml` to `.github/workflows/`
- [ ] Copy `feature-ci.yml`, `pr-title-lint.yml`, and `release.yml` to `.github/workflows/`
- [ ] For private repos, prefer `.github-private@main` callers when available
- [ ] For public repos, keep public-compatible templates or public reusable workflow mirrors
- [ ] Ensure `cliff.toml` exists in repo root
- [ ] Ensure `GitVersion.yml` exists with `prevent-increment-of-merged-branch-version: false` on `main`
- [ ] Ensure `GitVersion.yml` uses `develop` with `tag: alpha` and `increment: Patch` to stay aligned with `main`
- [ ] Verify `CHANGELOG_BOT_TOKEN` org secret is accessible (visibility: ALL)
- [ ] Enable "Allow auto-merge" in repo Settings > General (recommended)
- [ ] For monorepos: copy `monorepo-version-manifests.yml` and keep components under `projects/*`

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
