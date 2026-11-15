# Public CI and release reusables

These reusable workflows are the public implementation for product
repositories that cannot call the private workflow catalog. They run on
GitHub-hosted Ubuntu, pin third-party actions by full commit SHA, and use
the default `GITHUB_TOKEN` only. They do not take repository secrets.

Callers pin each `uses:` line to a reviewed full commit SHA of this
repository. Scripts fetched at runtime are pinned to the same revision plus
a SHA256 digest. Compute a digest with `sha256sum scripts/<file>.py`.

This catalog was introduced for issue #51. The first intended caller is
`alpininsight/insight-ui-webmcp`; a later pull request in that repository
switches its workflows to these reusables after this catalog is merged.

## Repository policy

`alpininsight/.github/.github/workflows/repository-policy.yml`

The calling job must grant `contents: read` and `pull-requests: read`. The
check is intended for `pull_request` and `merge_group` events.

Default routing:

- pull requests into `main` must come from `develop` in the same repository
- pull requests from `main` back into `develop` are rejected
- same-repository heads into `develop` must match an approved prefix
- titles and commit headlines follow Conventional Commits, with documented
  exceptions for generated merge commits and release promotions

Default-off exceptions exist for a narrowly named main realignment branch,
a single named bot into `main`, and a develop history-reconciliation branch.
A misconfigured bot exception fails closed.

Required inputs: `policy_revision`, `policy_sha256`.

This repository itself uses only `main`, so its pull requests are not
expected to satisfy the product default. Policy changes are proven by the
offline unit tests and the pull-request self-test in this workflow.

```sh
python3 -I -B -m unittest discover -s scripts -p test_repository_policy.py -v
```

## Python quality and Gitleaks

`alpininsight/.github/.github/workflows/python-quality.yml`

The calling job must grant `contents: read`. Required input:
`python_versions`, a JSON array such as `'["3.12", "3.13", "3.14"]'`.

Job names are fixed so a caller job named `quality` produces the checks
`quality / Quality (<python>)`, `quality / Gitleaks` and
`quality / Quality Gate`. Additional caller jobs may call the same reusable
with different commands. Set `run_gitleaks: false` when a second call would
otherwise duplicate the secret scan.

Useful optional inputs:

- `uv_sync_args` (default `--locked`), `run_uv_sync`
- `quality_node_version` (empty skips Node setup)
- `run_pre_commit`, `run_gitleaks`
- `gitleaks_version` and `gitleaks_sha256` (default Gitleaks 8.30.1, with the
  official linux_x64 archive digest)
- `pre_commit_command`, `lint_command`, `format_command`,
  `django_check_command`, `test_command` (an empty command skips that step)

When pre-commit and Gitleaks both run, the Gitleaks hook is removed from the
checked-out pre-commit configuration for the matrix so secret scanning stays
in the dedicated job. Gitleaks is installed from the official release,
verified by SHA256, then run as `detect` (the pull request range when base
and head SHAs are present, otherwise full history) and `dir` on the working
tree. The quality-gate job fails closed if the matrix failed, or if Gitleaks
was requested and did not succeed.

## Stable release creation

`alpininsight/.github/.github/workflows/create-release.yml`

This reusable builds on the public [release identity
contract](insight-ui-release-contract.md). It checks out
`scripts/release_version_contract.py` and `scripts/create_github_release.py`
from `alpininsight/.github` at the same reviewed revision, verifies both
digests, and starts Python with `-I` so a module in the source tree cannot
shadow the standard library. The source commit is checked out into a
subdirectory, and the interpreter is started from the runner temp directory.

Required inputs: `release_kind`, `target_version`, `contract_revision`,
`contract_sha256`, `release_sha256`.

Optional inputs: `rc_number` (default `1`), `checkout_ref`, `create`
(default `false`), `generate_release_notes` (default `true`), `require_main`
(default `true`).

Outputs: `release_kind`, `base_version`, `semver`, `python_version`, `tag`,
`is_prerelease`, `source_sha`, `released`.

The calling job must grant `contents: write`, because the reusable declares
a publication job with that permission. `create: false` still does not write
a tag or release. When `checkout_ref` is set, the identity job also reads any
existing tag or release and fails closed if the tag points at another commit,
the release is a draft (drafts are found by listing releases, because
the tag lookup does not return them), the prerelease flag does not match, or a
release exists without a source tag. When `create` is true, `checkout_ref` must be the
40-character lowercase source SHA, and that SHA must be the current commit
of `refs/heads/main` unless `require_main` is false. Creation is refused on
`pull_request` and `merge_group` events.

A stable call (`release_kind: stable`) publishes a GitHub Release whose tag
is `v<version>`, with `draft: false` and `prerelease: false`, on exactly
`checkout_ref`. Annotated tags are peeled to the commit. Tags and releases
are never updated or moved. If the same tag already exists on that commit
and the published release matches the requested prerelease flag, the run
succeeds and `released` is `false`. If the tag points at another commit, or
an existing release is a draft or has a mismatched prerelease flag, the run
fails.

Callers supply `target_version` themselves. This reusable does not calculate
a version from repository history.

```sh
python3 -I -B -m unittest discover -s scripts -p test_create_github_release.py -v
```

A later package publisher can require that this published stable release
exists on the exact source commit before uploading.

## Renovate pre-commit preset

`pre-commit.json` is a shareable Renovate preset that enables the pre-commit
manager. Callers that keep a tracked `.pre-commit-config.yaml` can extend it:

```json
{
  "extends": ["github>alpininsight/.github:pre-commit"]
}
```

This repository's own Renovate configuration does not enable that manager,
because this repository has no pre-commit configuration.

## Starters

Thin caller starters with unusable zero-hash placeholders live under
`workflow-templates/`. Replace every placeholder with the same reviewed
commit SHA and the matching script digest before adoption.
