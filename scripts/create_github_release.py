"""Create or reuse an immutable GitHub Release on an exact source commit."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from release_version_contract import release_identity

REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
TRUE = {"true", "True", "1"}


class ReleaseError(RuntimeError):
    """A fail-closed release identity or publication error."""


class GitHubReleaseAPI:
    def request(self, repository: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict | None]:
        raise NotImplementedError


class GhReleaseAPI(GitHubReleaseAPI):
    def request(self, repository: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict | None]:
        if not REPO.fullmatch(repository):
            raise ReleaseError("Invalid immutable release source")
        command = ["gh", "api", "--include", "--method", method, f"repos/{repository}/{path}"]
        if payload is not None:
            command += ["--input", "-"]
        result = subprocess.run(
            command,
            input=json.dumps(payload) if payload is not None else None,
            text=True,
            capture_output=True,
            check=False,
            timeout=45,
        )
        headers, separator, body = result.stdout.partition("\n\n")
        status = re.match(r"HTTP/\S+ (\d{3})", headers)
        if not separator or not status:
            raise ReleaseError("Authenticated release API request failed")
        code = int(status.group(1))
        if result.returncode and code < 400:
            raise ReleaseError("Authenticated release API request failed")
        if not body.strip():
            return code, None
        try:
            data = json.loads(body)
        except (ValueError, TypeError) as error:
            raise ReleaseError("Malformed release API response") from error
        return code, data if isinstance(data, dict) else None


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value) in TRUE


def resolve_tag_commit(api: GitHubReleaseAPI, repository: str, tag: str) -> str | None:
    code, data = api.request(repository, "GET", f"git/ref/tags/{quote(tag, safe='')}")
    if code == 404:
        return None
    if code != 200 or not isinstance(data, dict) or data.get("ref") != f"refs/tags/{tag}":
        raise ReleaseError("Release tag lookup failed")
    obj = data.get("object")
    seen: set[str] = set()
    for _ in range(16):
        if not isinstance(obj, dict) or SHA.fullmatch(str(obj.get("sha", ""))) is None:
            raise ReleaseError("Invalid release tag object")
        sha = str(obj["sha"])
        if obj.get("type") == "commit":
            return sha
        if obj.get("type") != "tag" or sha in seen:
            raise ReleaseError("Release tag does not resolve to a commit")
        seen.add(sha)
        code, data = api.request(repository, "GET", f"git/tags/{sha}")
        if code != 200 or not isinstance(data, dict) or data.get("sha") != sha:
            raise ReleaseError("Annotated release tag lookup failed")
        obj = data.get("object")
    raise ReleaseError("Release tag nesting limit exceeded")


def existing_release(api: GitHubReleaseAPI, repository: str, tag: str, prerelease: bool) -> int | None:
    code, data = api.request(repository, "GET", f"releases/tags/{quote(tag, safe='')}")
    if code == 404:
        return None
    if (
        code != 200
        or not isinstance(data, dict)
        or data.get("tag_name") != tag
        or type(data.get("id")) is not int
        or data["id"] <= 0
        or data.get("draft") is not False
        or data.get("prerelease") is not prerelease
        or not data.get("published_at")
    ):
        raise ReleaseError("Existing release identity or state is invalid")
    return data["id"]


def publish(
    api: GitHubReleaseAPI,
    repository: str,
    source: str,
    tag: str,
    name: str,
    generate_notes: bool,
    prerelease: bool,
) -> bool:
    existing = existing_release(api, repository, tag, prerelease)
    current = resolve_tag_commit(api, repository, tag)
    if current is None:
        if existing is not None:
            raise ReleaseError("Existing release has no source tag")
        code, _ = api.request(repository, "POST", "git/refs", {"ref": f"refs/tags/{tag}", "sha": source})
        if code not in (201, 409, 422):
            raise ReleaseError("Cannot create exact source tag")
        current = resolve_tag_commit(api, repository, tag)
    if current != source:
        raise ReleaseError("Release tag belongs to another source commit")
    created = False
    if existing is None:
        code, data = api.request(
            repository,
            "POST",
            "releases",
            {
                "tag_name": tag,
                "target_commitish": source,
                "name": name,
                "generate_release_notes": generate_notes,
                "prerelease": prerelease,
                "draft": False,
            },
        )
        if code == 201 and isinstance(data, dict) and type(data.get("id")) is int:
            existing = data["id"]
            created = True
        elif code in (409, 422):
            existing = existing_release(api, repository, tag, prerelease)
        else:
            raise ReleaseError("Cannot create release; no existing release is modified")
    if existing is None or existing_release(api, repository, tag, prerelease) != existing or resolve_tag_commit(api, repository, tag) != source:
        raise ReleaseError("Release source changed or final readback failed")
    return created


def plan_release(
    kind: str,
    version: str,
    rc_number: str = "1",
    *,
    repository: str,
    source: str = "",
    create: bool = False,
    event_name: str = "",
    require_main: bool = True,
    main_sha: str = "",
    checkout_sha: str | None = None,
    generate_notes: bool = True,
    api: GitHubReleaseAPI | None = None,
) -> dict:
    identity = release_identity(kind, version, rc_number)
    tag = identity["tag"]
    subprocess.run(["git", "check-ref-format", f"refs/tags/{tag}"], check=True, capture_output=True)
    if create:
        if event_name in {"pull_request", "merge_group"}:
            raise ReleaseError("Refusing to create a release from a pull request or merge group")
        if not SHA.fullmatch(source):
            raise ReleaseError("Invalid immutable release source")
        if checkout_sha is not None and checkout_sha != source:
            raise ReleaseError("Release checkout differs from expected source")
        if not REPO.fullmatch(repository):
            raise ReleaseError("Invalid immutable release source")
        if require_main and (not SHA.fullmatch(main_sha) or main_sha != source):
            raise ReleaseError("Release source is not the current commit of main")
        if api is None:
            raise ReleaseError("Release publication requires a GitHub API client")
        released = publish(
            api,
            repository,
            source,
            tag,
            tag,
            generate_notes,
            identity["is_prerelease"],
        )
    else:
        released = False
        if source and not SHA.fullmatch(source):
            raise ReleaseError("Invalid immutable release source")
        if api is not None and source:
            current = resolve_tag_commit(api, repository, tag)
            existing = existing_release(api, repository, tag, identity["is_prerelease"])
            if existing is not None and current is None:
                raise ReleaseError("Existing release has no source tag")
            if current is not None and current != source:
                raise ReleaseError("Release tag belongs to another source commit")
    result = {
        "release_kind": identity["release_kind"],
        "base_version": identity["base_version"],
        "semver": identity["semver"],
        "python_version": identity["python_version"],
        "tag": tag,
        "is_prerelease": identity["is_prerelease"],
        "source_sha": source,
        "released": released,
    }
    return result


def emit(result: dict) -> None:
    printable = dict(result)
    printable["is_prerelease"] = str(result["is_prerelease"]).lower()
    printable["released"] = str(result["released"]).lower()
    print(json.dumps(printable, sort_keys=True))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            for key, value in printable.items():
                handle.write(f"{key}={value}\n")


def main() -> None:
    create = as_bool(os.environ.get("CREATE", "false"))
    source = os.environ.get("SOURCE_REVISION", "")
    checkout = os.environ.get("CHECKOUT_SHA", "")
    result = plan_release(
        os.environ["RELEASE_KIND"],
        os.environ["TARGET_VERSION"],
        os.environ.get("RC_NUMBER", "1"),
        repository=os.environ.get("RELEASE_REPOSITORY", ""),
        source=source,
        create=create,
        event_name=os.environ.get("EVENT_NAME", ""),
        require_main=as_bool(os.environ.get("REQUIRE_MAIN", "true")),
        main_sha=os.environ.get("MAIN_SHA", ""),
        checkout_sha=checkout or None,
        generate_notes=as_bool(os.environ.get("GENERATE_NOTES", "true")),
        api=GhReleaseAPI() if create or as_bool(os.environ.get("VALIDATE_EXISTING", "false")) else None,
    )
    emit(result)


if __name__ == "__main__":
    try:
        main()
    except (ReleaseError, ValueError, subprocess.SubprocessError):
        raise SystemExit("Release source identity could not be verified; no successful release output.") from None
