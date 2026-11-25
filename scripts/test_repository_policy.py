"""Offline policy tests for branch routing, titles, commits and fail-closed paths."""

from __future__ import annotations

import unittest

from repository_policy import (
    Commit,
    PolicyClient,
    PolicyConfig,
    PolicyEvent,
    config_from_env,
    evaluate,
    event_from_env,
)


REPO = "alpininsight/example"
SHA1 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SHA2 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
SHA3 = "cccccccccccccccccccccccccccccccccccccccc"


def pr(*, title="feat: add cache", head="feat/cache", base="develop", author="alice", number="12", **kwargs) -> PolicyEvent:
    values = dict(
        event_name="pull_request",
        repository=REPO,
        pr_number=number,
        pr_title=title,
        pr_author=author,
        base_ref=base,
        head_ref=head,
        base_repository=REPO,
        head_repository=REPO,
    )
    values.update(kwargs)
    return PolicyEvent(**values)


class FakeClient(PolicyClient):
    def __init__(
        self,
        commits=None,
        parents=None,
        status="ahead",
        fail_list=False,
        fail_parents=False,
        fail_compare=False,
        commit_count=None,
        fail_count=False,
    ):
        self.commits = [Commit(SHA1, 1, "feat: add cache")] if commits is None else list(commits)
        self.parents = parents or {SHA2: [SHA1, SHA3]}
        self.status = status
        self.fail_list = fail_list
        self.fail_parents = fail_parents
        self.fail_compare = fail_compare
        self.commit_count = commit_count
        self.fail_count = fail_count
        self.compares = []

    def list_commits(self, repository, pr_number):
        if self.fail_list:
            raise RuntimeError("boom")
        return list(self.commits)

    def pull_commit_count(self, repository, pr_number):
        if self.fail_count:
            raise RuntimeError("boom")
        if self.commit_count is not None:
            return self.commit_count
        return len(self.commits)

    def commit_parents(self, repository, sha):
        if self.fail_parents:
            raise RuntimeError("boom")
        return list(self.parents[sha])

    def compare_status(self, repository, base, head):
        if self.fail_compare:
            raise RuntimeError("boom")
        self.compares.append((base, head))
        if isinstance(self.status, dict):
            return self.status[(base, head)]
        return self.status


class RepositoryPolicyTests(unittest.TestCase):
    def test_merge_group_for_main_or_develop_passes(self):
        for base in ("refs/heads/main", "refs/heads/develop"):
            result = evaluate(PolicyEvent("merge_group", REPO, merge_group_base_ref=base), PolicyConfig())
            self.assertTrue(result.ok)

    def test_merge_group_for_another_branch_fails(self):
        result = evaluate(PolicyEvent("merge_group", REPO, merge_group_base_ref="refs/heads/release"), PolicyConfig())
        self.assertFalse(result.ok)

    def test_missing_pull_request_number_fails(self):
        result = evaluate(PolicyEvent("push", REPO), PolicyConfig(), FakeClient())
        self.assertFalse(result.ok)
        self.assertTrue(any("pull_request or merge_group" in item for item in result.failures))

    def test_develop_from_feature_branch_passes(self):
        result = evaluate(pr(), PolicyConfig(), FakeClient())
        self.assertTrue(result.ok, result.failures)

    def test_develop_from_unprefixed_branch_fails(self):
        result = evaluate(pr(head="hotfix-cache"), PolicyConfig(), FakeClient())
        self.assertFalse(result.ok)

    def test_develop_from_a_fork_fails(self):
        result = evaluate(
            pr(head_repository="other/example", base_repository_public=True, head_repository_fork=True),
            PolicyConfig(),
            FakeClient(),
        )
        self.assertFalse(result.ok)

    def test_public_fork_can_contribute_after_opt_in(self):
        result = evaluate(
            pr(head_repository="other/example", base_repository_public=True, head_repository_fork=True),
            PolicyConfig(allow_develop_fork_prs=True),
            FakeClient(),
        )
        self.assertTrue(result.ok, result.failures)
        self.assertFalse(result.allow_develop_sync_merge_headlines)

    def test_fork_opt_in_preserves_routing_and_title_checks(self):
        config = PolicyConfig(allow_develop_fork_prs=True)
        fork = dict(
            head_repository="other/example",
            base_repository_public=True,
            head_repository_fork=True,
        )
        cases = [
            {"base": "main", "head": "develop"},
            {"head": "no-prefix"},
            {"title": "Add cache"},
            {"base_repository_public": False},
            {"head_repository_fork": False},
            {"head_repository": ""},
            {"base_repository": "other/base"},
        ]
        for override in cases:
            with self.subTest(override=override):
                self.assertFalse(evaluate(pr(**(fork | override)), config, FakeClient()).ok)

        client = FakeClient(commits=[Commit(SHA1, 1, "wip")])
        result = evaluate(pr(**fork), config, client)
        self.assertFalse(result.ok)
        self.assertTrue(any("Commit headline" in failure for failure in result.failures))

    def test_fork_payload_requires_explicit_github_booleans(self):
        env = {"ALLOW_DEVELOP_FORK_PRS": "true", "BASE_REPOSITORY_PRIVATE": "false", "HEAD_REPOSITORY_FORK": "true"}
        self.assertTrue(config_from_env(env).allow_develop_fork_prs)
        self.assertFalse(config_from_env({}).allow_develop_fork_prs)
        self.assertTrue(event_from_env(env).base_repository_public)
        self.assertTrue(event_from_env(env).head_repository_fork)
        missing = event_from_env({"BASE_REPOSITORY_PRIVATE": "null", "HEAD_REPOSITORY_FORK": "null"})
        self.assertFalse(missing.base_repository_public)
        self.assertFalse(missing.head_repository_fork)

    def test_main_from_develop_is_a_release_promotion(self):
        result = evaluate(pr(title="chore(release): 2.0.0", head="develop", base="main"), PolicyConfig(), FakeClient())
        self.assertTrue(result.ok, result.failures)
        self.assertTrue(result.is_release_promotion)

    def test_main_from_a_feature_branch_fails(self):
        result = evaluate(pr(head="feat/cache", base="main"), PolicyConfig(), FakeClient())
        self.assertFalse(result.ok)

    def test_main_from_develop_in_another_repository_fails(self):
        result = evaluate(pr(head="develop", base="main", head_repository="other/example"), PolicyConfig(), FakeClient())
        self.assertFalse(result.ok)

    def test_develop_from_main_is_rejected(self):
        result = evaluate(pr(head="main", base="develop"), PolicyConfig(), FakeClient())
        self.assertFalse(result.ok)
        self.assertTrue(any("back into" in item for item in result.failures))

    def test_nonconventional_title_fails(self):
        result = evaluate(pr(title="Add cache"), PolicyConfig(), FakeClient())
        self.assertFalse(result.ok)

    def test_nonconventional_commit_fails(self):
        client = FakeClient(commits=[Commit(SHA1, 1, "wip")])
        result = evaluate(pr(), PolicyConfig(), client)
        self.assertFalse(result.ok)

    def test_generated_merge_commit_with_two_parents_is_skipped(self):
        client = FakeClient(commits=[Commit(SHA1, 2, "Merge branch 'feat/cache' into develop")])
        result = evaluate(pr(), PolicyConfig(), client)
        self.assertTrue(result.ok, result.failures)

    def test_single_parent_merge_headline_is_still_checked(self):
        client = FakeClient(commits=[Commit(SHA1, 1, "Merge branch 'feat/cache' into develop")])
        result = evaluate(pr(), PolicyConfig(), client)
        self.assertFalse(result.ok)

    def test_promotion_allows_github_merge_headlines(self):
        client = FakeClient(
            commits=[Commit(SHA2, 2, "Merge pull request #9 from alpininsight/develop")],
            parents={SHA2: [SHA1, SHA3]},
            status="ahead",
        )
        result = evaluate(pr(title="chore(release): 2.0.0", head="develop", base="main"), PolicyConfig(), client)
        self.assertTrue(result.ok, result.failures)
        self.assertEqual(client.compares, [(SHA3, "develop")])

    def test_develop_sync_merge_requires_two_parents_in_develop(self):
        client = FakeClient(
            commits=[Commit(SHA2, 2, "Merge remote-tracking branch 'origin/develop' into feat/cache")],
            parents={SHA2: [SHA1, SHA3]},
            status="ahead",
        )
        result = evaluate(pr(), PolicyConfig(), client)
        self.assertTrue(result.ok, result.failures)
        self.assertEqual(client.compares, [(SHA3, "develop")])

    def test_develop_sync_merge_rejects_a_second_parent_outside_develop(self):
        client = FakeClient(
            commits=[Commit(SHA2, 2, "Merge remote-tracking branch 'origin/develop' into feat/cache")],
            parents={SHA2: [SHA1, SHA3]},
            status="diverged",
        )
        result = evaluate(pr(), PolicyConfig(), client)
        self.assertFalse(result.ok)

    def test_bot_exception_requires_complete_head_match_and_author(self):
        config = PolicyConfig(allow_main_bot_pr=True, main_bot_author="pin[bot]", main_bot_head_regex=r"^chore/pin-.+$")
        ok = evaluate(
            pr(title="chore: pin image", head="chore/pin-web", base="main", author="pin[bot]"),
            config,
            FakeClient(commits=[Commit(SHA1, 1, "chore: pin image")]),
        )
        self.assertTrue(ok.ok, ok.failures)
        self.assertTrue(ok.is_main_bot_pr)
        self.assertFalse(ok.is_release_promotion)
        denied = evaluate(pr(head="feat/cache", base="main", author="pin[bot]"), config, FakeClient())
        self.assertFalse(denied.ok)

    def test_misconfigured_bot_exception_fails_closed(self):
        result = evaluate(pr(), PolicyConfig(allow_main_bot_pr=True, main_bot_author="", main_bot_head_regex=""), FakeClient())
        self.assertFalse(result.ok)
        self.assertTrue(any("allow_main_bot_pr requires" in item for item in result.failures))

    def test_realignment_exception_marks_a_promotion(self):
        config = PolicyConfig(allow_main_realignment_pr=True)
        result = evaluate(
            pr(title="chore(release): realign main", head="chore/realign-main-with-develop", base="main"),
            config,
            FakeClient(),
        )
        self.assertTrue(result.ok, result.failures)
        self.assertTrue(result.is_main_realignment)
        self.assertTrue(result.is_release_promotion)

    def test_reconciliation_allows_inherited_nonconventional_commits(self):
        config = PolicyConfig(allow_develop_history_reconciliation=True)
        client = FakeClient(
            commits=[Commit(SHA1, 1, "Legacy imported headline")],
            status="identical",
        )
        result = evaluate(pr(head="chore/sync-main-into-develop-20261114"), config, client)
        self.assertTrue(result.ok, result.failures)
        self.assertEqual(client.compares, [(SHA1, "main")])

    def test_reconciliation_rejects_new_nonconventional_commits(self):
        config = PolicyConfig(allow_develop_history_reconciliation=True)
        client = FakeClient(
            commits=[Commit(SHA1, 1, "Legacy imported headline")],
            status="behind",
        )
        result = evaluate(pr(head="chore/sync-main-into-develop-20261114"), config, client)
        self.assertFalse(result.ok)

    def test_commit_listing_errors_fail_closed(self):
        result = evaluate(pr(), PolicyConfig(), FakeClient(fail_list=True))
        self.assertFalse(result.ok)
        self.assertTrue(any("after 5 attempts" in item for item in result.failures))

    def test_empty_commit_listing_fails_closed(self):
        result = evaluate(pr(), PolicyConfig(), FakeClient(commits=[]))
        self.assertFalse(result.ok)
        self.assertTrue(any("no PR commit headlines" in item for item in result.failures))

    def test_single_parent_develop_sync_headline_is_rejected(self):
        client = FakeClient(commits=[Commit(SHA1, 1, "Merge branch 'develop' into feat/cache")])
        result = evaluate(pr(), PolicyConfig(), client)
        self.assertFalse(result.ok)
        self.assertTrue(any("real merge commit" in item for item in result.failures))

    def test_single_parent_develop_sync_pr_headline_is_rejected(self):
        client = FakeClient(
            commits=[Commit(SHA1, 1, "Merge pull request #9 from alpininsight/develop")],
        )
        result = evaluate(pr(), PolicyConfig(), client)
        self.assertFalse(result.ok)
        self.assertTrue(any("real merge commit" in item for item in result.failures))

    def test_single_parent_promotion_github_merge_headline_is_rejected(self):
        client = FakeClient(
            commits=[Commit(SHA1, 1, "Merge pull request #9 from alpininsight/develop")],
        )
        result = evaluate(pr(title="chore(release): 2.0.0", head="develop", base="main"), PolicyConfig(), client)
        self.assertFalse(result.ok)
        self.assertTrue(any("real merge commit" in item for item in result.failures))

    def test_truncated_commit_listing_fails_closed(self):
        listed = [Commit(SHA1, 1, "feat: add cache")]
        result = evaluate(pr(), PolicyConfig(), FakeClient(commits=listed, commit_count=251))
        self.assertFalse(result.ok)
        self.assertTrue(any("incomplete" in item and "251" in item for item in result.failures))

    def test_commit_count_errors_fail_closed(self):
        result = evaluate(pr(), PolicyConfig(), FakeClient(fail_count=True))
        self.assertFalse(result.ok)
        self.assertTrue(any("commit count" in item for item in result.failures))


if __name__ == "__main__":
    unittest.main()
