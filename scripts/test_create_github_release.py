"""Offline tests for dry-run identity, idempotent reuse, and fail-closed publication."""

from __future__ import annotations

import unittest

from create_github_release import GitHubReleaseAPI, ReleaseError, plan_release, publish

SOURCE = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
REPO = "alpininsight/example"


class FakeAPI(GitHubReleaseAPI):
    def __init__(self, tag_sha=None, tag_type="commit", release=None, create_tag_code=201, create_release_code=201):
        self.tag_sha = tag_sha
        self.tag_type = tag_type
        self.release = dict(release) if release else None
        self.create_tag_code = create_tag_code
        self.create_release_code = create_release_code
        self.writes = []
        self.annotated = {}

    def request(self, repository, method, path, payload=None):
        if method != "GET":
            self.writes.append((method, path, payload))
        if path.startswith("git/ref/tags/"):
            if self.tag_sha is None:
                return 404, {"message": "Not Found"}
            return 200, {"ref": f"refs/tags/{path.rsplit('/', 1)[-1]}", "object": {"type": self.tag_type, "sha": self.tag_sha}}
        if path.startswith("git/tags/"):
            sha = path.rsplit("/", 1)[-1]
            obj = self.annotated.get(sha)
            if not obj:
                return 404, {}
            return 200, {"sha": sha, "object": obj}
        if path.startswith("releases/tags/"):
            if self.release is None:
                return 404, {"message": "Not Found"}
            return 200, self.release
        if method == "POST" and path == "git/refs":
            if self.create_tag_code in (201, 409, 422) and self.create_tag_code == 201:
                self.tag_sha = payload["sha"]
                self.tag_type = "commit"
            return self.create_tag_code, {}
        if method == "POST" and path == "releases":
            if self.create_release_code == 201:
                self.release = {
                    "id": 7,
                    "tag_name": payload["tag_name"],
                    "draft": False,
                    "prerelease": payload["prerelease"],
                    "published_at": "2026-11-14T13:00:00Z",
                }
                return 201, self.release
            return self.create_release_code, {}
        raise AssertionError(f"unexpected {method} {path}")


class CreateReleaseTests(unittest.TestCase):
    def test_dry_run_stable_identity_does_not_write(self):
        api = FakeAPI()
        result = plan_release(
            "stable", "2.0.0", repository=REPO, source=SOURCE, create=False, api=api
        )
        self.assertEqual(result["tag"], "v2.0.0")
        self.assertEqual(result["semver"], "2.0.0")
        self.assertFalse(result["is_prerelease"])
        self.assertFalse(result["released"])
        self.assertEqual(api.writes, [])

    def test_dry_run_rc_identity(self):
        result = plan_release("rc", "2.0.0", "1", repository=REPO, create=False)
        self.assertEqual(result["tag"], "v2.0.0-rc.1")
        self.assertEqual(result["python_version"], "2.0.0rc1")
        self.assertTrue(result["is_prerelease"])
        self.assertFalse(result["released"])

    def test_create_is_rejected_on_pull_request_events(self):
        with self.assertRaisesRegex(ReleaseError, "pull request"):
            plan_release(
                "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
                event_name="pull_request", require_main=False, api=FakeAPI(),
            )

    def test_create_requires_main_tip_when_requested(self):
        with self.assertRaisesRegex(ReleaseError, "current commit of main"):
            plan_release(
                "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
                event_name="workflow_dispatch", require_main=True, main_sha=OTHER, api=FakeAPI(),
            )

    def test_create_stable_release_on_exact_source(self):
        api = FakeAPI()
        result = plan_release(
            "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
            event_name="workflow_dispatch", require_main=True, main_sha=SOURCE, checkout_sha=SOURCE, api=api,
        )
        self.assertTrue(result["released"])
        self.assertEqual(result["tag"], "v2.0.0")
        self.assertEqual([item[0] for item in api.writes], ["POST", "POST"])
        self.assertEqual(api.writes[0][1], "git/refs")
        self.assertEqual(api.writes[0][2]["sha"], SOURCE)
        self.assertFalse(api.writes[1][2]["draft"])
        self.assertFalse(api.writes[1][2]["prerelease"])

    def test_idempotent_reuse_same_sha_does_not_rewrite(self):
        api = FakeAPI(
            tag_sha=SOURCE,
            release={"id": 3, "tag_name": "v2.0.0", "draft": False, "prerelease": False, "published_at": "2026-11-01T00:00:00Z"},
        )
        result = plan_release(
            "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
            event_name="workflow_dispatch", require_main=False, api=api,
        )
        self.assertFalse(result["released"])
        self.assertEqual(api.writes, [])

    def test_wrong_sha_fails_closed(self):
        api = FakeAPI(
            tag_sha=OTHER,
            release={"id": 3, "tag_name": "v2.0.0", "draft": False, "prerelease": False, "published_at": "2026-11-01T00:00:00Z"},
        )
        with self.assertRaisesRegex(ReleaseError, "another source commit"):
            plan_release(
                "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
                event_name="workflow_dispatch", require_main=False, api=api,
            )

    def test_draft_release_fails_closed(self):
        api = FakeAPI(
            tag_sha=SOURCE,
            release={"id": 3, "tag_name": "v2.0.0", "draft": True, "prerelease": False, "published_at": None},
        )
        with self.assertRaisesRegex(ReleaseError, "identity or state is invalid"):
            plan_release(
                "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
                event_name="workflow_dispatch", require_main=False, api=api,
            )

    def test_prerelease_mismatch_fails_closed(self):
        api = FakeAPI(
            tag_sha=SOURCE,
            release={"id": 3, "tag_name": "v2.0.0", "draft": False, "prerelease": True, "published_at": "2026-11-01T00:00:00Z"},
        )
        with self.assertRaisesRegex(ReleaseError, "identity or state is invalid"):
            plan_release(
                "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
                event_name="workflow_dispatch", require_main=False, api=api,
            )

    def test_dry_run_detects_conflicting_existing_tag(self):
        api = FakeAPI(tag_sha=OTHER)
        with self.assertRaisesRegex(ReleaseError, "another source commit"):
            plan_release("stable", "2.0.0", repository=REPO, source=SOURCE, create=False, api=api)

    def test_checkout_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ReleaseError, "checkout differs"):
            plan_release(
                "stable", "2.0.0", repository=REPO, source=SOURCE, create=True,
                event_name="workflow_dispatch", require_main=False, checkout_sha=OTHER, api=FakeAPI(),
            )

    def test_peels_annotated_tag_to_commit(self):
        api = FakeAPI(tag_sha="cccccccccccccccccccccccccccccccccccccccc", tag_type="tag")
        api.annotated["cccccccccccccccccccccccccccccccccccccccc"] = {"type": "commit", "sha": SOURCE}
        api.release = {"id": 3, "tag_name": "v2.0.0", "draft": False, "prerelease": False, "published_at": "2026-11-01T00:00:00Z"}
        released = publish(api, REPO, SOURCE, "v2.0.0", "v2.0.0", True, False)
        self.assertFalse(released)


if __name__ == "__main__":
    unittest.main()
