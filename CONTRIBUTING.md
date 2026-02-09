# Contributing

Thanks for contributing.

This document defines branch policy, pull request flow, commit conventions, and release expectations used across repositories in this organization.

## Branch model

- `main` is production/stable.
- `develop` is staging/integration.
- Short-lived branches:
  - `feature/*`
  - `feat/*`
  - `fix/*`
  - `refactor/*`
  - `chore/*`
  - `docs/*`
  - `hotfix/*`

## Pull request routing rules

- PRs into `develop` are allowed only from `feature/*`, `feat/*`, `fix/*`, `refactor/*`, `chore/*`, `docs/*`, `hotfix/*`.
- PRs into `main` are allowed only from `develop`.
- Direct pushes to `main` and `develop` should be blocked with branch protection.

## Pull requests

- Use the organization PR templates.
- Keep PRs scoped to one change objective.
- Include validation steps and rollback notes for risky changes.
- Ensure required checks are green before merge.

## Commit convention

Use Conventional Commits:

`type(scope): subject`

Examples:

- `feat(auth): add oidc callback validation`
- `fix(ci): pin action version for stability`
- `refactor(core): split service bootstrap`

For breaking changes:

- `feat(api)!: replace token schema`
- or include `BREAKING CHANGE:` in the commit body.

## Releases and versioning

- Semantic Versioning (`MAJOR.MINOR.PATCH`) is required.
- `develop` builds are pre-release/integration.
- `main` builds are stable releases.
- Release PRs should be `develop` -> `main`.

## Security

- Never commit secrets.
- Use repository/environment secrets and secret scanning.
- Report vulnerabilities through `SECURITY.md`, not public issues.

