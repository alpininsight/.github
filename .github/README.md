# Organization GitHub Configuration

This folder contains organization-wide GitHub defaults and templates.

## Atomic structure

- Atoms
  - Root policy files (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`)
- Molecules
  - Collaboration templates in:
    - `.github/ISSUE_TEMPLATE/`
    - `.github/PULL_REQUEST_TEMPLATE/`
- Organisms
  - Automation standards:
    - `.github/workflow-templates/` for new repository bootstrap
      - Includes `release-pr-auto-merge.yml` for release-please automation
      - Includes `monorepo-version-manifests.yml` for `projects/*` monorepos
    - `.github/workflows/monorepo-version-manifests-reusable.yml` as reusable GitVersion manifest workflow
    - `.github/workflows/sync-labels.yml` for org label sync

## Labels

Labels are defined in `.github/labels.yml` and synced across organization repositories.

Sync modes:

1. Push trigger when `.github/labels.yml` changes on `main`
2. Weekly schedule (`0 0 * * 0`)
3. Manual `workflow_dispatch` (supports `dry_run`)

## Required secret

Configure organization secret:

- Name: `ORG_LABEL_SYNC_TOKEN`
- Scope: token with `repo` permission

## Manual label sync

```bash
./scripts/sync-labels-all-repos.sh --dry-run
./scripts/sync-labels-all-repos.sh
```
