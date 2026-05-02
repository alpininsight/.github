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
  - public starter templates only; canonical workflow logic lives in `.github-private`
- Label definitions and sync automation

## Atomic design model used here

- Atoms: policy documents (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`)
- Molecules: collaboration templates (`.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE/*`)
- Organisms: branded starter templates (`.github/workflow-templates/*`)
- Templates: repository bootstrap standards and examples in `.github/README.md`

## Workflow templates

These files are public starter templates. When copied into a repository, they
keep a visible Alpine Insight source header and delegate to the private reusable
workflow catalog in `alpininsight/.github-private`.

They are meant for Alpine Insight organization repositories. The public repo is
the discovery and branding surface; the private repo remains the implementation
source of record.

| Template | Purpose | Prerequisites |
|----------|---------|---------------|
| `changelog.yml` | Thin caller for the Alpine Insight changelog backend | `cliff.toml`, `CHANGELOG_BOT_TOKEN` available to the repo |
| `container-build.yml` | Thin caller for the Alpine Insight Python/Django container backend | Dockerfile, repo-specific `public_base_url` |
| `feature-ci.yml` | Thin caller for repository policy and Python/Django quality backends | `pyproject.toml` |
| `gitversion.yml` | Thin caller for the Alpine Insight GitVersion backend | `GitVersion.yml` |
| `monorepo-version-manifests.yml` | Thin caller for `projects/*` monorepo version manifests | `GitVersion.yml`, `projects/<component>/` layout |
| `pr-branch-guard.yml` | Thin caller for branch-routing policy only | -- |
| `pr-title-lint.yml` | Thin caller for Alpine Insight PR title validation | -- |
| `release.yml` | Thin caller for the Alpine Insight GitVersion release backend | `GitVersion.yml` |
| `scheduled-pre-commit-update.yml` | Thin caller for automated pre-commit updates | `.pre-commit-config.yaml`, `INSIGHT_TOKEN` available to the repo |

### Adoption checklist (per repo)

- [ ] Copy the template to `.github/workflows/`
- [ ] Keep the Alpine Insight source header in the copied file
- [ ] Replace placeholder inputs such as `public_base_url`
- [ ] Ensure any referenced GitHub Actions secrets are available to the repo, preferably via org-wide secrets
- [ ] Prefer extending `.github-private` over forking copied workflow logic

## Notes

- Keep these files generic and organization-wide.
- Repository-specific ownership (`CODEOWNERS`) and delivery pipelines should stay in each individual repository.

Copyright 2026 Alpin Insight Solutions GmbH & Co. KG
