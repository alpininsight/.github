# Centralized Workflows

This document describes the standardized GitHub Actions workflows that all
Alpine Insight repositories should adopt. These workflows are designed to work
consistently across repos with and without branch protection rules, and each
section explains why a workflow exists so developers can decide when it is
required versus optional.

Related planning document:
- [Atomic Design Workflow Standardization Plan](./atomic-design-workflow-standardization-plan.md)
- [Release Strategy Standard](./release-strategy-standard.md)

## Table of Contents

- [Reusable Workflow Consumer Contract](#reusable-workflow-consumer-contract)
- [Changelog Workflow](#changelog-workflow)
- [Release Strategy Standard](#release-strategy-standard)
- [Release Backlog Advisory](#release-backlog-advisory)
- [Python Django Quality Reusable Workflow](#python-django-quality-reusable-workflow)
- [Python Django Container Build Reusable Workflow](#python-django-container-build-reusable-workflow)
- [Feature CI](#feature-ci)
- [PR Title Lint](#pr-title-lint)
- [Scheduled Pre-commit Update](#scheduled-pre-commit-update)
- [Monorepo Version Manifests](#monorepo-version-manifests)
- [GitVersion Configuration](#gitversion-configuration)
- [Required Secrets](#required-secrets)
- [Repository Settings](#repository-settings)

---

## Reusable Workflow Consumer Contract

When a repository consumes a reusable workflow from `alpininsight/.github`, two
rules apply:

1. Pin the reusable workflow to a commit SHA, not `@main`.
2. Grant required permissions in the caller job or workflow; a called workflow
   cannot elevate the token beyond what the caller grants.

This matters in practice for two recurring failure modes:

- `zizmor` flags `uses: ...@main` as `unpinned-uses`
- comment-writing reusable workflows fail silently if the caller keeps only
  `contents: read`

Example:

```yaml
permissions:
  contents: read

jobs:
  release-backlog-advisory:
    permissions:
      contents: read
      pull-requests: write
    uses: alpininsight/.github-private/.github/workflows/release-backlog-advisory-reusable.yml@<org-workflow-sha>
    with:
      pr-number: ${{ github.event.pull_request.number }}
```

---

## Release Strategy Standard

**Standard:** GitVersion
**Reference repo:** `insight-lima-k8s-capi`

GitVersion is the organization release standard. New repositories should adopt
the GitVersion templates from `.github` rather than introducing
`release-please`.

`release-please` is migration legacy only. Existing repos that still use it are
temporary exceptions and should be moved onto the GitVersion model.

See the full policy in [Release Strategy Standard](./release-strategy-standard.md).

---

## Changelog Workflow

**File:** `.github/workflows/changelog.yml`

Automatically generates `CHANGELOG.md` using [git-cliff](https://git-cliff.org/)
when commits are pushed to the `develop` branch.

### How It Works

1. **Trigger:** Push to `develop` (excluding changes to `CHANGELOG.md` itself)
2. **Generate:** Runs `git-cliff` to produce an updated `CHANGELOG.md`
3. **PR Creation:** Creates (or updates) a PR from `chore/changelog-update` to `develop`
4. **Auto-merge:** Uses `gh pr merge --auto` to let GitHub merge the PR once
   all required checks pass. Falls back to direct merge for repos without
   required checks or without auto-merge enabled.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| PR-based merge (not direct push) | Works with branch protection rules that require PRs |
| `CHANGELOG_BOT_TOKEN` PAT | `GITHUB_TOKEN` cannot merge PRs when branch protection requires reviews or status checks from a different actor |
| `gh pr merge --auto` | Lets GitHub handle check-waiting natively; no fragile polling loops or timeouts |
| `paths-ignore: ['CHANGELOG.md']` | Prevents infinite trigger loops when the changelog PR merges |
| No `[skip ci]` in commit message | Required checks must run on the changelog PR for it to be mergeable |
| `concurrency` group | Prevents race conditions when multiple pushes happen in quick succession |
| Fallback to direct merge | Repos without required checks or auto-merge enabled still work |

### Adapting for Your Repo

The workflow is identical across all repos. No repo-specific customization is
needed. The auto-merge fallback handles the difference between repos with and
without required checks.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Missing CHANGELOG_BOT_TOKEN secret` error | Secret not configured | Add `CHANGELOG_BOT_TOKEN` in repo Settings > Secrets |
| PR created but not merged | Auto-merge not enabled + required checks exist | Enable "Allow auto-merge" in repo Settings > General |
| `Auto-merge unavailable, attempting direct merge` then fails | Required checks block direct merge | Enable auto-merge in repo settings |
| Changelog not updating | `cliff.toml` missing or misconfigured | Ensure `cliff.toml` exists in repo root |

---

## Release Backlog Advisory

**Reusable workflow:** `alpininsight/.github-private/.github/workflows/release-backlog-advisory-reusable.yml@<org-workflow-sha>`

Advises on `develop -> main` release backlog by comparing the actual file tree
between `main` and `develop`, not raw commit counts.

### Why It Exists

Repositories that release into `main` via squash or batch merges often show
hundreds of commits of apparent drift even when only a few files still differ.
Commit-count heuristics create noisy, misleading PR comments in that model.

This workflow answers the question developers actually care about:
"What still differs between `develop` and `main` right now?"

### How It Works

1. Checks out the caller repository with full history
2. Computes `git diff --name-only origin/main..origin/develop`
3. Excludes docs/changelog/meta-only paths from the substantive count
4. Upserts a single PR comment only when the remaining file drift crosses the thresholds
5. Deletes the old advisory comment automatically after the backlog is cleared

### Substantive vs non-substantive files

Excluded from the substantive count:

- `CHANGELOG.md`
- Markdown-only docs (`*.md`, `*.mdx`, `docs/**`)
- issue/PR templates and repo-meta files such as `.gitignore`,
  `.gitattributes`, `.editorconfig`, `.github/labels.yml`

Still treated as substantive:

- `.github/workflows/**`
- source code
- scripts
- tests
- manifests and deployment/config files

### Thresholds

| Condition | Comment |
|----------|---------|
| `> 5` substantive files | `Consider a release PR` |
| `> 15` total files and at least 1 substantive file | `Strongly recommend a release PR` |
| only docs/changelog/meta drift | no advisory comment |

### Usage

Call the reusable workflow from a repo-local CI workflow that already runs on
PRs into `develop`:

```yaml
release-backlog-advisory:
  permissions:
    contents: read
    pull-requests: write
  if: github.base_ref == 'develop'
  uses: alpininsight/.github-private/.github/workflows/release-backlog-advisory-reusable.yml@<org-workflow-sha>
  with:
    pr-number: ${{ github.event.pull_request.number }}
```

### Design Notes

- Advisory only: it never fails the build
- One comment marker: avoids PR comment spam on every push
- Tree-diff first: matches real release scope better than commit ancestry counts
- Caller must grant `pull-requests: write`, otherwise the reusable workflow
  cannot post or update the advisory comment

---

## Python Django Quality Reusable Workflow

**Reusable workflow:** `alpininsight/.github-private/.github/workflows/python-django-quality-reusable.yml@<org-workflow-sha>`

This is the organization standard quality workflow for repositories that ship:

- a Django application
- a Python-based notebook UI
- another Python UI repo with `pyproject.toml`, `uv`, `ruff`, and `pytest`

### Why It Exists

The earlier `feature-ci` template standardized the basic checks, but each repo
still had to carry a local copy and then drift over time. This reusable
workflow centralizes the actual quality contract so repos can keep only a thin
caller workflow.

It also makes the reason for each step explicit for developers:

- `uv sync`: reproduce the locked dependency graph
- `pre-commit`: enforce repository-wide file hygiene
- `ruff check` and `ruff format --check`: keep lint and formatting consistent
- optional `manage.py check`: validate Django configuration before runtime
- `pytest`: verify application behavior
- quality gate: provide one stable required check for branch protection

For Django repos and notebook-style UI repos, pair this workflow with the
container-build molecule so code quality and runtime packaging are both covered.

### How It Works

1. The caller passes a Python version matrix and optional repo-specific commands
2. Each matrix job checks out the repo, installs Python and `uv`, then runs the quality steps
3. An optional secret can unlock private GitHub dependencies during `uv sync`
4. The final gate runs with `always()` and fails if any matrix leg failed or was cancelled

### Inputs

| Input | Purpose | Default |
|-------|---------|---------|
| `python_versions` | JSON array for the test matrix | `["3.12", "3.13", "3.14"]` |
| `working_directory` | Project directory for commands | `.` |
| `uv_sync_args` | Arguments appended to `uv sync` | `--frozen --dev` |
| `run_pre_commit` | Enable or disable pre-commit | `true` |
| `pre_commit_command` | Override the pre-commit command | `uvx pre-commit run --all-files` |
| `lint_command` | Override the lint command | `uv run ruff check .` |
| `format_command` | Override the format check command | `uv run ruff format --check .` |
| `django_check_command` | Optional Django system check command | empty |
| `test_command` | Override the test command | `uv run pytest` |

### Secrets

| Secret | Purpose |
|--------|---------|
| `github_read_token` | Optional read token for private GitHub dependencies during `uv sync` |

### Usage

```yaml
name: Feature CI

on:
  pull_request:
    branches: [develop, main]
    types: [opened, reopened, synchronize, ready_for_review]

permissions:
  contents: read

jobs:
  python-quality:
    uses: alpininsight/.github-private/.github/workflows/python-django-quality-reusable.yml@<org-workflow-sha>
    with:
      python_versions: '["3.12", "3.13"]'
      uv_sync_args: --all-groups
      django_check_command: uv run python manage.py check --deploy --fail-level ERROR
    secrets:
      github_read_token: ${{ secrets.INSIGHT_TOKEN_RO }}
```

### Design Notes

- Prefer this reusable workflow for new Python/Django repos instead of copying `feature-ci.yml`
- Keep the repo-local caller file small so required check names remain stable
- If the repo has no Django layer, leave `django_check_command` empty
- If the repo ships a containerized Django app or notebook UI, add the container-build workflow as a companion check

---

## Python Django Container Build Reusable Workflow

**Reusable workflow:** `alpininsight/.github-private/.github/workflows/python-django-container-build-reusable.yml@<org-workflow-sha>`

This is the organization standard container-build workflow for repositories that
ship:

- a Django application image
- a Python-based notebook UI with a Docker runtime
- another Python UI service that deploys via OCI image

### Why It Exists

For these repos, code quality alone is not enough. A PR can pass linting and
tests while still failing to build or package into the runtime artifact that
gets deployed.

This workflow makes the packaging contract explicit for developers:

- Docker context and Dockerfile must stay valid
- multi-stage builds must keep working
- optional private dependency access must remain wired correctly
- image metadata and tags are generated consistently
- PR validation can build without pushing, while release flows can push the same definition

If a repo is a Django project or a notebook-style UI with a container runtime,
this workflow should be present alongside the Python/Django quality workflow.

### How It Works

1. The caller passes the image name, context, Dockerfile, and optional build settings
2. The workflow sets up QEMU and Buildx for reproducible Docker builds
3. It can log in to a registry when the caller enables `push`
4. Docker metadata is generated consistently for SHA and branch tags
5. The image is built, and optionally pushed, from the same reusable definition

### Inputs

| Input | Purpose | Default |
|-------|---------|---------|
| `image_name` | Full image name | required |
| `context` | Docker build context | `.` |
| `dockerfile` | Dockerfile path | `Dockerfile` |
| `target` | Optional build target | empty |
| `platforms` | Comma-separated Docker platforms | `linux/amd64` |
| `push` | Push after successful build | `false` |
| `build_args` | Multiline Docker build arguments | empty |
| `additional_tags` | Extra metadata-action tag rules | empty |

### Secrets

| Secret | Purpose |
|--------|---------|
| `github_read_token` | Optional read token for private GitHub dependencies during docker build |
| `registry_username` | Required for push workflows to registries other than `ghcr.io` |
| `registry_password` | Required for push workflows to registries other than `ghcr.io` |

### Usage

```yaml
name: Container Build

on:
  pull_request:
    branches: [develop, main]
  push:
    branches: [develop, main]
    paths:
      - Dockerfile
      - pyproject.toml
      - uv.lock
      - src/**

permissions:
  contents: read
  packages: write

jobs:
  container-build:
    uses: alpininsight/.github-private/.github/workflows/python-django-container-build-reusable.yml@<org-workflow-sha>
    with:
      image_name: ghcr.io/alpininsight/insight-ui-flow
      platforms: linux/amd64,linux/arm64
      push: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}
    secrets:
      github_read_token: ${{ secrets.INSIGHT_TOKEN_RO }}
```

### Design Notes

- Default `push: false` keeps PR validation safe
- Use the same workflow for publish flows by enabling `push` in the caller
- For private GitHub dependencies, pass `github_read_token`; new Dockerfiles should use `RUN --mount=type=secret,id=insight_token ...`, while the reusable workflow keeps `GIT_ACCESS_TOKEN` build-arg compatibility for older consumers during migration
- Only `ghcr.io` may use default GitHub credentials; all other registries require explicit `registry_username` and `registry_password`
- Prefer explicit `paths` filters in the caller so container builds only run when the packaged runtime can actually change

---

## Feature CI

**Template file:** `.github/workflow-templates/feature-ci.yml`

Runs linting, formatting, and tests on every pull request targeting `main` or
`develop`.

This template remains useful as a starter or transitional local workflow, but
the org standard for new Python/Django repos is the reusable workflow above.

### How It Works

1. **Trigger:** Pull request opened/updated against `main` or `develop`
2. **Matrix:** Tests across Python 3.12, 3.13, and 3.14
3. **Checks:** pre-commit, ruff lint, ruff format, pytest
4. **Quality Gate:** Summary job that reports pass/fail status

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `uv sync --frozen --dev` | Reproducible installs from lockfile |
| `fail-fast: false` | All Python versions tested even if one fails |
| `concurrency` with cancel-in-progress | Saves runner minutes on rapid pushes |
| Separate quality-gate job | Single required check for branch protection |
| `enable-cache: true` on uv | Faster installs on subsequent runs |

### Adapting for Your Repo

| Customization | How |
|---------------|-----|
| Reduce Python versions | Edit the `python-version` matrix |
| Add Django checks | Add `uv run python manage.py check --deploy --fail-level ERROR` step |
| Add mypy | Add `uv run mypy .` step (use `\|\| true` until types are added) |
| Private dependencies | Add git auth step with `INSIGHT_TOKEN_RO` (see visa_statistiken) |
| Container build | Add a separate job for Docker build verification |

---

## PR Title Lint

**Template file:** `.github/workflow-templates/pr-title-lint.yml`

Validates that pull request titles follow the Conventional Commits specification.

### How It Works

1. **Trigger:** PR opened, reopened, or title edited
2. **Validation:** Checks title matches `<type>: <description>` or `<type>(scope): <description>`
3. **Types:** feat, fix, perf, refactor, docs, chore, ci, test, build, style
4. **Breaking changes:** Allowed via `!` suffix (e.g. `feat!: redesign auth`)

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `pull_request_target` (not `pull_request`) | Works with PRs from forks |
| `requireScope: false` | Scopes are optional but encouraged |
| `GITHUB_TOKEN` sufficient | Read-only PR access, no anti-cascade issue |

### Adapting for Your Repo

The workflow is identical across all repos. No customization needed.

---

## Scheduled Pre-commit Update

**Template file:** `.github/workflow-templates/scheduled-pre-commit-update.yml`

Runs `pre-commit autoupdate` weekly and creates a PR with version bumps.

### How It Works

1. **Trigger:** Every Monday at 06:00 UTC (or manual dispatch)
2. **Update:** Runs `uvx pre-commit autoupdate`
3. **PR Creation:** Creates/updates a PR from `chore/pre-commit-autoupdate` to default branch
4. **CI Trigger:** Uses `INSIGHT_TOKEN` PAT so CI workflows run on the created PR

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `INSIGHT_TOKEN` PAT | `GITHUB_TOKEN` cannot trigger other workflows on PRs it creates (GitHub anti-cascade protection) |
| Monday schedule | Updates land early in the week, leaving time for review |
| Fixed branch name | Reuses the same PR if updates accumulate |
| `chore, ci` labels | Consistent labeling for automated changes |

### Required Secrets

| Secret | Purpose |
|--------|---------|
| `INSIGHT_TOKEN` | PAT with `contents: write` and `pull-requests: write` for PR creation |

### Adapting for Your Repo

The workflow is identical across all repos. No customization needed.

---

## Monorepo Version Manifests

**Template file:** `.github/workflows/monorepo-version-manifests.yml`  
**Reusable backend:** `alpininsight/.github-private/.github/workflows/monorepo-version-manifests-reusable.yml@<org-workflow-sha>`

Generates per-component version artifacts for monorepos that keep projects
under `projects/*`.

### How It Works

1. **Trigger:** Push/PR to `develop` or `main` when project/versioning paths change.
2. **Detect:** Determines affected components from diff or manual dispatch inputs.
3. **Version:** Runs GitVersion and computes SemVer metadata.
4. **Emit:** Uploads artifacts per component:
   - `artifacts/version-manifests/<component>.json`
   - `artifacts/version-manifests/<component>.release.env`

### Manual Inputs (`workflow_dispatch`)

| Input | Description | Default |
|-------|-------------|---------|
| `components` | Comma-separated component list (`hf_models,memadvisor`) | empty (auto-detect) |
| `force_all` | Build manifests for all components under `projects/` | `false` |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Reusable workflow in org `.github` repo | Central logic, less drift across repositories |
| Component detection from `projects/*` directories | No hardcoded component list in template |
| JSON + `.env` artifact output | Supports runtime file ingestion and CI handoffs |
| Run on PR and push | Early validation before merge and post-merge continuity |

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Workflow reports no component changes | Paths outside `projects/*` and no global versioning file changes | Use `workflow_dispatch` with `components` or `force_all=true` |
| Unknown component warning on dispatch | Name does not match a directory under `projects/` | Use exact folder names |
| No artifacts uploaded | `GitVersion.yml` missing or invalid | Add/fix `GitVersion.yml` in repo root |

---

## GitVersion Configuration

**File:** `GitVersion.yml`

All repos use [GitVersion 5.x](https://gitversion.net/) for semantic versioning
based on conventional commits. This is the only supported org release
strategy baseline.

### Standard Configuration

```yaml
# GitVersion 5.x Configuration
mode: ContinuousDelivery
tag-prefix: '[vV]?'
next-version: 0.1.0
assembly-versioning-scheme: MajorMinorPatch
commit-message-incrementing: Enabled
major-version-bump-message: '(\+semver:\s?(breaking|major))|^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\(.+\))?!:|BREAKING CHANGE:'
minor-version-bump-message: '(\+semver:\s?(feature|minor))|^feat(\(.+\))?:'
patch-version-bump-message: '(\+semver:\s?(fix|patch))|^(fix|perf)(\(.+\))?:'
no-bump-message: '(\+semver:\s?(skip|none))|^(chore|docs|style|test|ci|build|revert)(\(.+\))?:'
branches:
  main:
    regex: ^main$
    mode: ContinuousDelivery
    tag: ''
    increment: Patch
    prevent-increment-of-merged-branch-version: false  # CRITICAL
    track-merge-target: false
    is-release-branch: true
    is-mainline: true
  develop:
    regex: ^develop$
    mode: ContinuousDelivery
    tag: alpha
    increment: Patch
    prevent-increment-of-merged-branch-version: false
    track-merge-target: true
    is-release-branch: false
    is-mainline: false
  feature:
    regex: ^(feature|feat)[/-]
    mode: ContinuousDelivery
    tag: alpha.{BranchName}
    increment: Inherit
    source-branches: ['develop', 'main']
  hotfix:
    regex: ^hotfix[/-]
    mode: ContinuousDelivery
    tag: beta
    increment: Patch
    source-branches: ['main']
  release:
    regex: ^release[/-]
    mode: ContinuousDelivery
    tag: rc
    increment: None
    source-branches: ['develop']
  ci:
    regex: ^ci[/-]
    mode: ContinuousDelivery
    tag: ci.{BranchName}
    increment: Inherit
    source-branches: ['develop']
  docs:
    regex: ^docs[/-]
    mode: ContinuousDelivery
    tag: docs.{BranchName}
    increment: Inherit
    source-branches: ['develop']
  fix:
    regex: ^fix[/-]
    mode: ContinuousDelivery
    tag: fix.{BranchName}
    increment: Inherit
    source-branches: ['develop']
```

### Critical Setting: `prevent-increment-of-merged-branch-version`

This setting **must be `false`** on the `main` branch. When set to `true`
(the GitVersion default for mainline branches), it causes `feat:` commits
merged from `develop` to `main` to produce **patch** bumps instead of the
correct **minor** bumps.

**Why this happens:** With `true`, GitVersion ignores the commit message-based
increment calculated on the source branch and falls back to the `increment`
setting on `main` (which is `Patch`). Setting it to `false` lets the
conventional commit prefix (`feat:` = minor, `fix:` = patch) flow through
correctly.

### Develop Alignment

Use `develop` with `tag: alpha` and `increment: Patch` so pre-release builds
stay on the same semantic line as `main`.

If `develop.increment` is set to `Minor`, each feature change can advance the
minor line too early and create drift between `develop` image tags and what is
later released from `main`.

### Version Bump Rules

| Commit Prefix | Version Bump | Example |
|---------------|-------------|---------|
| `feat:` | Minor (0.X.0) | `feat(api): add user endpoint` |
| `fix:`, `perf:` | Patch (0.0.X) | `fix(auth): handle expired tokens` |
| `feat!:`, `BREAKING CHANGE:` | Major (X.0.0) | `feat!: redesign auth flow` |
| `chore:`, `docs:`, `ci:`, `test:`, `build:`, `style:`, `revert:` | None | `chore: update deps` |
| `+semver: minor` | Minor (override) | Any commit with `+semver: minor` in body |

---

## Required Secrets

| Secret | Purpose | Required By |
|--------|---------|-------------|
| `CHANGELOG_BOT_TOKEN` | Fine-grained PAT for changelog PR creation and merge | changelog.yml |
| `INSIGHT_TOKEN` | PAT for automated PR creation that triggers CI | scheduled-pre-commit-update.yml |

The monorepo version-manifest workflow does not require additional secrets.

### Creating the PAT

1. Go to GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens
2. Create a token scoped to the `alpininsight` organization
3. **Permissions:** Contents (read/write), Pull requests (read/write), Metadata (read)
4. **Resource access:** Apply to all repos that use the changelog workflow
5. Add as a repository secret named `CHANGELOG_BOT_TOKEN`

### Rotation

- Set a reasonable expiry (e.g., 1 year)
- Document the expiry date and set a calendar reminder
- When rotating, update the secret in all repos simultaneously

---

## Repository Settings

For the changelog workflow to work optimally with branch protection:

1. **Enable "Allow auto-merge"** in repo Settings > General > Pull Requests
   - This allows `gh pr merge --auto` to queue the PR for merge after checks pass
   - Without this, repos with required checks will need the auto-merge fallback

2. **Branch protection on `develop`** (if applicable):
   - The `CHANGELOG_BOT_TOKEN` PAT must belong to a user/app that satisfies
     the branch protection requirements
   - If reviews are required, consider exempting the bot user or using a
     GitHub App with bypass permissions

---

## Adoption Checklist

When adding these workflows to a new repo:

### Core (all repos)

- [ ] Copy `changelog.yml` to `.github/workflows/`
- [ ] Copy `pr-branch-guard.yml` to `.github/workflows/`
- [ ] Copy `pr-title-lint.yml` to `.github/workflows/`
- [ ] Copy `release.yml` to `.github/workflows/`
- [ ] Copy `GitVersion.yml` to repo root
- [ ] Ensure `cliff.toml` exists (git-cliff configuration)
- [ ] Add `CHANGELOG_BOT_TOKEN` secret to the repo
- [ ] Enable "Allow auto-merge" in repo settings (recommended)
- [ ] Verify `prevent-increment-of-merged-branch-version: false` on `main` branch

### Python repos

- [ ] Copy `feature-ci.yml` to `.github/workflows/` and customize Python matrix
- [ ] Copy `scheduled-pre-commit-update.yml` to `.github/workflows/`
- [ ] Verify `INSIGHT_TOKEN` org secret is accessible

### Optional

- [ ] Call `release-backlog-advisory-reusable.yml` from repo CI if the repo uses `develop -> main` releases
- [ ] For monorepos with `projects/*`: copy `monorepo-version-manifests.yml`
- [ ] For Django repos or notebook-style Python UIs: add a repo-local container build job to CI so image packaging breaks fail before merge
