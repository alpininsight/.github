# Public release identity contract

The public workflow validates release names. It contains no private reusable
workflow calls, user-supplied credential references, approval-policy changes,
tag writes or uploads. The PR checkout uses the automatic read-only GitHub token
without persisting it; the calculation job fetches the public script without
credentials.

| Choice | SemVer | Python package version | Git tag |
| --- | --- | --- | --- |
| RC 1 for 2.0.0 | 2.0.0-rc.1 | 2.0.0rc1 | v2.0.0-rc.1 |
| RC 2 for 2.0.0 | 2.0.0-rc.2 | 2.0.0rc2 | v2.0.0-rc.2 |
| Stable 2.0.0 | 2.0.0 | 2.0.0 | v2.0.0 |

Callers pin both the reusable workflow and its script to the same reviewed full
commit SHA, plus the script's SHA256. The script is fetched only from this public
repository without credentials. Invalid or mismatched content stops before execution.

The calling job grants `contents: read` as the maximum permission required by
the workflow's declared PR self-test job. The calculation job explicitly reduces
this to `permissions: {}`. This respects GitHub's rule that a called workflow
cannot elevate caller permissions without relying on an unverified exception
for skipped jobs. The starter declares this read-only ceiling; future private
callers must do the same when separately adopted. No private caller is changed
by this public Source step.

This Source change is based on public `main` at
`3bb8e04b5a03b3b9a3de09105e14388f93289c10`, on the feature branch
`feat/insight-ui-public-release-contract-20261031`. The historical develop branch
is not an implementation base for this change. The new starter stays at the
documented root `workflow-templates/` path; existing starter paths are unchanged.

The starter contains deliberately unusable zero-hash placeholders. Replace them
only after the new public contract commit has been independently reviewed and
merged. Source preparation does not activate the private publisher or change
its registration, environment, credentials or legacy 1.x/TestPyPI behavior.

## Pull request self-test

Pull requests targeting `main` and changing one of these six contract files run
the six pure Python version tests on GitHub-hosted Ubuntu. That job grants only
Contents-read for a SHA-pinned checkout, does not persist its credential and
does not fetch or calculate a release contract. Top-level permissions are empty.
There is no push, schedule, manual-dispatch or privileged PR trigger.

The calculation job runs only for `workflow_call`. GitHub associates a reusable
workflow with its caller's event, so testing `github.event_name == 'workflow_call'`
would incorrectly skip real calls. The two jobs instead distinguish the presence
of the required `target_version` input key. Empty values remain subject to the
validator; they cannot turn an invalid call into the PR self-test. A caller that
is itself a pull request can still calculate a valid release identity.

[GitHub reusable-workflow context](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations)
and [official template layout](https://docs.github.com/en/actions/how-tos/reuse-automations/create-workflow-templates).

The private publisher remains responsible for source CI, artifact verification,
normal-PyPI routing, immutable RC receipts and Matti's release approval. Stable
publication must reference an accepted RC with matching source tree, lockfile and
build inputs; changing the version metadata requires a new verified build. The
public contract alone does not authorize or perform a release.

Run the pure version tests without credentials or network:

```sh
python3 -B -m unittest discover -s scripts -p test_release_version_contract.py -v
```
