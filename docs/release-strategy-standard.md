# Release Strategy Standard

Status: normative org standard

## Policy

Alpine Insight repositories must use **GitVersion** as the release strategy
standard.

This means:

- semantic version calculation comes from `GitVersion.yml`
- Git tags and GitHub Releases are created from the GitVersion-derived version
- release branch semantics are based on `main`, `develop`, and conventional
  short-lived branches

`release-please` is **not** an organization standard. Repositories that still
use it are migration exceptions and should be moved to GitVersion.

## Why GitVersion is the standard

GitVersion matches the current org branching model better than `release-please`:

- it supports `develop -> main` release flows directly
- it works with branch-based prerelease labels such as `alpha`, `beta`, and `rc`
- it keeps semantic versioning tied to conventional commits and branch state
- it fits repos that already use release branches or batch/squash release PRs

## Reference Implementation

Use `insight-lima-k8s-capi` as the reference release repo unless a repository
class needs a stronger domain-specific example.

What it demonstrates:

- `release.yml` calculates the release version from GitVersion
- `GitVersion.yml` defines the main/develop/release branch model
- `changelog.yml` owns `CHANGELOG.md` separately from release creation
- `branch-guard.yml` constrains source/target branch routing

## Required Building Blocks

Every GitVersion-standard release repo should use these org-level building
blocks:

- `.github/workflow-templates/gitversion.yml`
- `.github/workflow-templates/release.yml`
- `GitVersion.yml`

Usually also:

- `.github/workflow-templates/changelog.yml`
- `.github/workflow-templates/pr-branch-guard.yml`
- `.github/workflows/release-backlog-advisory-reusable.yml`

## Migration Rule

Repositories currently using `release-please` should be treated as migration
backlog, not as acceptable long-term variants.

Current migration examples from the planning inventory:

- `insight-ui`
- `insight-ci`
- `visa_statistiken`

## Non-goals

This standard does not require all repositories to share the same feature-CI or
container-build logic. Those stay repo-class-specific and are handled by later
molecules in the Atomic Design plan.
