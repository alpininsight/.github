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
  - branded starters for organization repositories that call the private catalog in `.github-private`
- Public reusable workflows for policy, Python quality, release identity, and stable GitHub Release creation; see `docs/public-ci-and-release-reusables.md`
- Public-safe workflow starter adoption guidance

## Atomic design model used here

- Atoms: policy documents (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`)
- Molecules: collaboration templates (`.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE/*`)
- Organisms: branded starter templates (`.github/workflow-templates/*`)
- Templates: repository bootstrap standards and examples in `docs/centralized-workflows.md`

## Workflow templates

These files are public starter templates. When copied into a repository, they
keep a visible Alpin Insight source header and delegate to the private reusable
workflow catalog in `alpininsight/.github-private`.

They are meant for Alpin Insight organization repositories. The public repo is
the discovery and branding surface; the private repo remains the implementation
source of record.

| Template | Purpose | Prerequisites |
|----------|---------|---------------|
| `changelog.yml` | Thin caller for the Alpin Insight changelog backend | `cliff.toml`, `CHANGELOG_BOT_TOKEN` available to the repo |
| `container-build.yml` | Thin caller for the Alpin Insight Python/Django container backend | Dockerfile, repo-specific `public_base_url` |
| `feature-ci.yml` | Thin caller for repository policy and Python/Django quality backends | `pyproject.toml` |
| `gitversion.yml` | Thin caller for the Alpin Insight GitVersion backend | `GitVersion.yml` |
| `monorepo-version-manifests.yml` | Thin caller for `projects/*` monorepo version manifests | `GitVersion.yml`, `projects/<component>/` layout |
| `pr-branch-guard.yml` | Thin caller for branch-routing policy only | -- |
| `pr-title-lint.yml` | Thin caller for Alpin Insight PR title validation | -- |
| `release.yml` | Thin caller for the Alpin Insight GitVersion release backend | `GitVersion.yml` |
| `scheduled-pre-commit-update.yml` | Thin caller for automated pre-commit updates | `.pre-commit-config.yaml`, `INSIGHT_TOKEN` available to the repo |

### Adoption checklist (per repo)

- [ ] Copy the template to `.github/workflows/`
- [ ] Keep the Alpin Insight source header in the copied file
- [ ] Replace placeholder inputs such as `public_base_url`
- [ ] Ensure any referenced GitHub Actions secrets are available to the repo, preferably via org-wide secrets
- [ ] Prefer extending `.github-private` over forking copied workflow logic

## Public reusable workflows

Public product repositories can call the reusable workflows in
`.github/workflows/` directly. Pin each `uses:` line to a reviewed commit
SHA of this repository. These workflows run on GitHub-hosted Ubuntu and do
not use the private catalog.

| Workflow | Purpose |
|----------|---------|
| `repository-policy.yml` | Branch routing and Conventional Commit policy |
| `python-quality.yml` | Python quality matrix, Gitleaks, and a quality gate |
| `release-version-contract.yml` | RC and stable version identity without publication |
| `create-release.yml` | Publish or reuse a GitHub Release on an exact source SHA |

Adoption notes, inputs, and the shareable Renovate pre-commit preset are in
[`docs/public-ci-and-release-reusables.md`](docs/public-ci-and-release-reusables.md).

## Notes

- Keep these files generic and organization-wide.
- Repository-specific ownership (`CODEOWNERS`) and delivery pipelines should stay in each individual repository.

Copyright 2026 Alpin Insight Solutions GmbH & Co. KG
