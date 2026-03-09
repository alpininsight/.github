# Atomic Design Plan for Org Workflow Standardization

Status: active  
Owner: Org `.github` repository  
Reference implementation: `insight-lima-k8s-capi`

## Goal

Create one organization-wide workflow standard that repositories consume from
`alpininsight/.github` instead of inventing local variants.

The authoritative release strategy is **GitVersion**. `release-please` is not
the org standard and should be migrated out of repositories that still use it.

## Reference Model

`insight-lima-k8s-capi` is the release reference unless a repo class needs a
better domain-specific example.

Why it is the reference:

- it uses GitVersion for release calculation
- it already carries `release.yml`, `changelog.yml`, `branch-guard.yml`
- it models the branch split `develop -> main`
- it exposes where repo-specific CI differs from the central standard

## Current Release Strategy Inventory

### GitVersion repos

- `insight-lima-k8s-capi`
- `capi-provider-ssh`
- `sources`
- `insight-ci-codex`
- `insight-ci-claude`
- `insight-ci-claude-docs`
- `insight-lima-k8s-dev`
- `hybrid-hw-foundation`

### Migration exceptions to remove

- `insight-ui`
- `insight-ci`
- `visa_statistiken`

Rule:
- New repos must not adopt `release-please`.
- Existing `release-please` repos must be migrated to GitVersion.

## Atomic Design Map

### Atoms

- `A1` Versioning contract
  GitVersion configuration, SemVer bump rules, tag prefix, `main`/`develop`
  branch semantics.
- `A2` Release branch routing
  Allowed source -> target branch patterns and guard messages.
- `A3` Change artifact ownership
  `CHANGELOG.md`, tags, GitHub Releases, PR comments, container images.
- `A4` Secrets and auth
  `CHANGELOG_BOT_TOKEN`, optional read token for private GitHub dependencies,
  package registry credentials.
- `A5` Python/Django toolchain baseline
  Python matrix, `uv`, `ruff`, `pytest`, optional `manage.py check`.
- `A6` Container build contract
  Docker context, Dockerfile path, build args, registry target, platforms.

### Molecules

- `M1` Release strategy molecule
  `GitVersion.yml` + `release.yml` + release policy documentation.
- `M2` Changelog molecule
  `changelog.yml` + token contract + merge behavior.
- `M3` Branch guard molecule
  PR source/target validation.
- `M4` Release backlog advisory molecule
  Tree-diff advisory for `develop -> main`.
- `M5` Python/Django quality molecule
  Reusable workflow for `uv sync`, `ruff`, Django system checks, `pytest`.
- `M6` Python/Django container build molecule
  Reusable workflow for Docker build validation or publish flows.
- `M7` Consumer adoption molecule
  Repo-local wiring that consumes org workflows with minimal local glue.

### Organisms

- `O1` Release organism
  `M1 + M2 + M3 + M4` combined for a GitVersion-based release repo.
- `O2` Python/Django delivery organism
  `M5 + M6 + M7` for repos that ship a Django app or notebook-style Python UI.

### Templates

- `T1` GitVersion release repo template
  Repos with `develop -> main`, changelog automation, GitHub Releases.
- `T2` Python/Django app template
  Repos with `pyproject.toml`, `Dockerfile`, Django checks, tests, and image
  packaging.

## Execution Order

1. `M1` Make GitVersion the explicit org release policy and mark
   `release-please` as migration-only legacy.
2. `M5` Add reusable Python/Django quality workflow to `.github`.
3. `M6` Add reusable Python/Django container build workflow to `.github`.
4. `M7` Migrate `insight-ui-flow` to consume the central molecules.
5. Migrate `release-please` repos to GitVersion:
   `insight-ui`, `insight-ci`, `visa_statistiken`.

## Status Board

| ID | Layer | Scope | Status | PR |
|----|-------|-------|--------|----|
| `M1` | Molecule | GitVersion release policy | merged | `#14` |
| `M2` | Molecule | Changelog automation | existing in `.github` | n/a |
| `M3` | Molecule | Branch guard | existing in `.github` | n/a |
| `M4` | Molecule | Release backlog advisory | merged | `#11` |
| `M5` | Molecule | Python/Django quality reusable workflow | in review | `#15` |
| `M6` | Molecule | Python/Django container build reusable workflow | in review | `#16` |
| `M7` | Molecule | `insight-ui-flow` adoption | planned | tbd |

## Update Log

- 2026-03-09: Plan initialized in `.github`.
- 2026-03-09: Release strategy reference fixed to `insight-lima-k8s-capi`.
- 2026-03-09: `release-please` classified as migration legacy, not org standard.
- 2026-03-09: `M1` opened as PR `#14` to make GitVersion the explicit org release standard.
- 2026-03-09: `M1` merged as PR `#14`.
- 2026-03-09: `M5` opened as PR `#15` for the reusable Python/Django quality workflow.
- 2026-03-09: `M6` opened as PR `#16` for the reusable Python/Django container-build workflow.
