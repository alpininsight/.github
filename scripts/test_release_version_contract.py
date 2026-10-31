"""Offline behavior tests for release identities, including ambiguous and injected values."""

import unittest

from release_version_contract import release_identity


class ReleaseIdentityTests(unittest.TestCase):
    def test_first_rc_has_all_three_version_forms(self):
        self.assertEqual(release_identity("rc", "2.0.0", "1"), {
            "release_kind": "rc", "base_version": "2.0.0", "semver": "2.0.0-rc.1",
            "python_version": "2.0.0rc1", "tag": "v2.0.0-rc.1", "is_prerelease": True,
        })

    def test_second_rc_is_distinct_from_first(self):
        self.assertEqual(release_identity("rc", "2.0.0", "2")["python_version"], "2.0.0rc2")

    def test_stable_has_no_prerelease_marker(self):
        result = release_identity("stable", "2.0.0")
        self.assertEqual(result["python_version"], "2.0.0")
        self.assertEqual(result["tag"], "v2.0.0")
        self.assertFalse(result["is_prerelease"])

    def test_invalid_release_kind_is_rejected(self):
        for kind in ("prod", "preview", "", "rc\nstable", "stable;echo unsafe"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "Release kind"):
                release_identity(kind, "2.0.0")

    def test_noncanonical_base_is_rejected(self):
        for version in ("v2.0.0", "02.0.0", "2.0", "2.0.0rc1", "2.0.0+local", "2.0.0\n", "2.0.0;echo unsafe", None):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "Target version"):
                release_identity("rc", version)

    def test_rc_number_cannot_be_ambiguous_or_injected(self):
        for number in ("0", "-1", "01", "1.5", "1\n", "1000000", "1;echo unsafe", 1, True):
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, "RC number"):
                release_identity("rc", "2.0.0", number)


if __name__ == "__main__":
    unittest.main()
