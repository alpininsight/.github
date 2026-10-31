"""Credential-free release identity shared by public callers and private publishers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

BASE = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
RC = re.compile(r"[1-9][0-9]{0,5}")


def release_identity(kind: str, version: str, rc_number: str = "1") -> dict:
    """Return consistent SemVer, PEP 440 and Git-tag identities without publishing."""
    if kind not in {"rc", "stable"}:
        raise ValueError("Release kind must be rc or stable")
    if not isinstance(version, str) or len(version) > 64 or BASE.fullmatch(version) is None:
        raise ValueError("Target version must be a canonical X.Y.Z version")
    if kind == "rc":
        if not isinstance(rc_number, str) or RC.fullmatch(rc_number) is None:
            raise ValueError("RC number must be an integer from 1 to 999999 without leading zeros")
        semver = f"{version}-rc.{rc_number}"
        python_version = f"{version}rc{rc_number}"
    else:
        semver = python_version = version
    return {
        "release_kind": kind,
        "base_version": version,
        "semver": semver,
        "python_version": python_version,
        "tag": f"v{semver}",
        "is_prerelease": kind == "rc",
    }


def main() -> None:
    """Emit validated workflow outputs; this command has no network or publication code."""
    identity = release_identity(os.environ["RELEASE_KIND"], os.environ["TARGET_VERSION"], os.environ.get("RC_NUMBER", "1"))
    print(json.dumps(identity, sort_keys=True))
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            for key, value in identity.items():
                rendered = str(value).lower() if isinstance(value, bool) else str(value)
                output.write(f"{key}={rendered}\n")


if __name__ == "__main__":
    main()
