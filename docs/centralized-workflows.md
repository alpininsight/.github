# Centralized Workflows

Public `.github/workflow-templates/*` files are Alpine Insight starter
templates. They are meant to be copied into organization repositories and keep
their visible Alpine Insight source header after copy.

Canonical workflow logic does not live in this public repository. It lives in
`alpininsight/.github-private`, and the copied starter files call the private
reusable backends from `@main`.

## What this public repo provides

- branded starter templates for new Alpine Insight repositories
- public-safe prerequisites and adoption notes
- no active central workflow implementation
- no internal runbooks, secret inventories, or operational automation

## Template catalog

| Starter template | Private backend |
|---|---|
| `changelog.yml` | `changelog-reusable.yml@main` |
| `container-build.yml` | `python-django-container-build-reusable.yml@main` |
| `feature-ci.yml` | `repository-policy-reusable.yml@main` and `python-django-quality-reusable.yml@main` |
| `gitversion.yml` | `gitversion-reusable.yml@main` |
| `monorepo-version-manifests.yml` | `monorepo-version-manifests-reusable.yml@main` |
| `pr-branch-guard.yml` | `repository-policy-reusable.yml@main` |
| `pr-title-lint.yml` | `reusable-pr-title.yml@main` |
| `release.yml` | `reusable-release.yml@main` |
| `scheduled-pre-commit-update.yml` | `scheduled-pre-commit-update-reusable.yml@main` |

## Public usage guidance

When copying a starter template into a repository:

1. Keep the Alpine Insight source header in the copied file.
2. Replace any placeholder values such as `public_base_url`.
3. Ensure referenced GitHub Actions secrets are available to the repo.
4. Prefer org-wide GitHub Actions secrets where appropriate.
5. Extend `.github-private` instead of forking copied logic whenever possible.

Copied workflow files should stay thin callers. Do not paste the reusable
workflow implementation into product repositories to make local fixes. If the
same behavior should apply across Alpine Insight repositories, change the
matching reusable workflow in `alpininsight/.github-private` and let repository
callers keep using the public starter template shape.

For example, changelog formatting, PR creation, and auto-merge behavior belong
in `.github-private/.github/workflows/changelog-reusable.yml`. Product
repositories should copy the public `.github/workflow-templates/changelog.yml`
starter into `.github/workflows/changelog.yml` and keep only that caller plus
their repository-specific secrets.

## Notes on secrets

The public starter templates refer only to the GitHub Actions secret names that
the caller expects. The underlying secret source of truth may be managed
elsewhere, for example through organization-wide GitHub secrets, Apple
Keychain-backed operator workflows, or OpenBao-backed secret provisioning.

## Internal details

Implementation details, reusable workflow behavior, internal release policy, and
operational guidance belong in `.github-private`, not in this public repository.
