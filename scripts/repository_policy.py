"""Credential-free repository policy for public develop/main callers."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

CONVENTIONAL = re.compile(
    r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([A-Za-z0-9_.-]+\))?!?: .+"
)
GITHUB_MERGE = re.compile(r"^Merge pull request #[0-9]+ from .+")
MERGE_HEADLINE = re.compile(r"^Merge ")
SHA = re.compile(r"[0-9a-f]{40}")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TRUE = {"true", "True", "1"}


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value) in TRUE


@dataclass
class Commit:
    sha: str
    parent_count: int
    headline: str


@dataclass
class PolicyEvent:
    event_name: str
    repository: str
    merge_group_base_ref: str = ""
    pr_number: str = ""
    pr_title: str = ""
    pr_author: str = ""
    base_ref: str = ""
    head_ref: str = ""
    base_repository: str = ""
    head_repository: str = ""


@dataclass
class PolicyConfig:
    main_branch: str = "main"
    develop_branch: str = "develop"
    enforce_develop_source_branch_prefixes: bool = True
    develop_source_branch_prefix_regex: str = (
        r"^(build|chore|ci|dependabot|docs|feat|feature|fix|perf|refactor|renovate|revert|style|test)/.+$"
    )
    allow_develop_history_reconciliation: bool = False
    develop_history_reconciliation_head_regex: str = r"^chore/sync-main-into-develop-[0-9]{8}$"
    require_conventional_title: bool = True
    require_conventional_commits: bool = True
    allow_main_realignment_pr: bool = False
    main_realignment_head_regex: str = r"^chore/realign-main-with-.+$"
    allow_main_bot_pr: bool = False
    main_bot_author: str = ""
    main_bot_head_regex: str = ""


@dataclass
class PolicyResult:
    ok: bool
    failures: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    is_release_promotion: bool = False
    is_main_realignment: bool = False
    is_develop_history_reconciliation: bool = False
    allow_develop_sync_merge_headlines: bool = False
    is_main_bot_pr: bool = False


class PolicyClient:
    def list_commits(self, repository: str, pr_number: str) -> list[Commit]:
        raise NotImplementedError

    def pull_commit_count(self, repository: str, pr_number: str) -> int:
        raise NotImplementedError

    def commit_parents(self, repository: str, sha: str) -> list[str]:
        raise NotImplementedError

    def compare_status(self, repository: str, base: str, head: str) -> str:
        raise NotImplementedError


def verify_develop_source_merge(
    commit: Commit,
    client: PolicyClient,
    repository: str,
    develop_branch: str,
) -> str | None:
    """Return a failure message, or None if this is a real two-parent merge from develop."""
    if not isinstance(commit.parent_count, int) or commit.parent_count <= 1:
        return (
            f"Synchronization or promotion merge '{commit.headline}' ({commit.sha}) "
            f"must be a real merge commit; found {commit.parent_count} parent(s)."
        )
    try:
        parents = client.commit_parents(repository, commit.sha)
    except (RuntimeError, ValueError, OSError):
        return (
            f"Unable to verify parents for develop synchronization merge "
            f"'{commit.headline}' ({commit.sha}); failing closed."
        )
    if len(parents) != 2:
        return (
            f"Develop synchronization merge '{commit.headline}' ({commit.sha}) "
            f"must have exactly two parents; found {len(parents)}."
        )
    try:
        status = client.compare_status(repository, parents[1], develop_branch)
    except (RuntimeError, ValueError, OSError):
        return (
            f"Unable to verify that develop synchronization merge '{commit.headline}' "
            f"({commit.sha}) uses '{develop_branch}' history; failing closed."
        )
    if status not in {"ahead", "identical"}:
        return (
            f"Develop synchronization merge '{commit.headline}' ({commit.sha}) second "
            f"parent is not in '{develop_branch}' history (compare status: '{status}')."
        )
    return None


def compile_regex(pattern: str, label: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as error:
        raise ValueError(f"{label} is not a valid regular expression: {pattern!r}.") from error


def fullmatch(pattern: re.Pattern[str], value: str) -> bool:
    matched = pattern.search(value)
    return matched is not None and matched.group(0) == value


def evaluate(event: PolicyEvent, config: PolicyConfig, client: PolicyClient | None = None) -> PolicyResult:
    failures: list[str] = []
    is_release_promotion = False
    is_main_realignment = False
    is_develop_history_reconciliation = False
    allow_develop_sync_merge_headlines = False
    is_main_bot_pr = False

    if event.event_name == "merge_group":
        expected = (f"refs/heads/{config.main_branch}", f"refs/heads/{config.develop_branch}")
        if event.merge_group_base_ref not in expected:
            return PolicyResult(
                False,
                [
                    f"Merge group base {event.merge_group_base_ref!r} is neither "
                    f"'refs/heads/{config.main_branch}' nor 'refs/heads/{config.develop_branch}'."
                ],
            )
        return PolicyResult(
            True,
            summary=[
                "## Repository Policy",
                "- Event: `merge_group`",
                f"- Merge group base: `{event.merge_group_base_ref}`",
                "- Route, title and commit checks: enforced on each pull request before it entered the queue",
            ],
        )

    if not event.pr_number:
        failures.append("Repository Policy must run on pull_request or merge_group events.")

    bot_pattern: re.Pattern[str] | None = None
    if config.allow_main_bot_pr:
        if not config.main_bot_author or not config.main_bot_head_regex:
            failures.append("allow_main_bot_pr requires a non-empty main_bot_author and main_bot_head_regex.")
        else:
            try:
                bot_pattern = compile_regex(config.main_bot_head_regex, "main_bot_head_regex")
            except ValueError as error:
                failures.append(str(error))

    def main_bot_pr_matches() -> bool:
        if not config.allow_main_bot_pr or not config.main_bot_author or bot_pattern is None:
            return False
        if event.head_repository != event.base_repository or event.pr_author != config.main_bot_author:
            return False
        return fullmatch(bot_pattern, event.head_ref)

    if event.base_ref == config.main_branch:
        if event.head_ref != config.develop_branch or event.head_repository != event.base_repository:
            realign_ok = False
            if (
                config.allow_main_realignment_pr
                and event.head_repository == event.base_repository
                and config.main_realignment_head_regex
            ):
                try:
                    realign_pattern = compile_regex(
                        config.main_realignment_head_regex, "main_realignment_head_regex"
                    )
                except ValueError as error:
                    failures.append(str(error))
                else:
                    realign_ok = realign_pattern.search(event.head_ref) is not None
            if realign_ok:
                is_release_promotion = True
                is_main_realignment = True
            elif main_bot_pr_matches():
                is_main_bot_pr = True
            else:
                failures.append(
                    f"PRs into '{config.main_branch}' must come from '{config.develop_branch}' "
                    f"in the same repository. Current source is '{event.head_repository}:{event.head_ref}'."
                )
                if config.allow_main_bot_pr:
                    failures.append(
                        f"The bot exception admits only same-repository PRs by '{config.main_bot_author}' "
                        f"whose complete head branch matches '{config.main_bot_head_regex}'; "
                        f"this PR is by '{event.pr_author}'."
                    )
        else:
            is_release_promotion = True

    if (
        event.base_ref == config.develop_branch
        and event.head_ref == config.main_branch
        and event.head_repository == event.base_repository
    ):
        failures.append(f"PRs from '{config.main_branch}' back into '{config.develop_branch}' are not allowed.")
    elif event.base_ref == config.develop_branch and config.enforce_develop_source_branch_prefixes:
        prefix_ok = False
        if event.head_repository == event.base_repository and config.develop_source_branch_prefix_regex:
            try:
                prefix_pattern = compile_regex(
                    config.develop_source_branch_prefix_regex, "develop_source_branch_prefix_regex"
                )
            except ValueError as error:
                failures.append(str(error))
            else:
                prefix_ok = prefix_pattern.search(event.head_ref) is not None
        if event.head_repository != event.base_repository:
            failures.append(
                f"PRs into '{config.develop_branch}' must come from a same-repository branch with an "
                f"approved prefix. Current source is '{event.head_repository}:{event.head_ref}'."
            )
        elif not prefix_ok:
            failures.append(
                f"PR head into '{config.develop_branch}' must match "
                f"'{config.develop_source_branch_prefix_regex}'. Current source branch is '{event.head_ref}'."
            )

    if (
        event.base_ref == config.develop_branch
        and config.allow_develop_history_reconciliation
        and event.head_repository == event.base_repository
        and config.develop_history_reconciliation_head_regex
    ):
        try:
            recon_pattern = compile_regex(
                config.develop_history_reconciliation_head_regex,
                "develop_history_reconciliation_head_regex",
            )
        except ValueError as error:
            failures.append(str(error))
        else:
            is_develop_history_reconciliation = recon_pattern.search(event.head_ref) is not None

    if event.head_repository == event.base_repository and (
        event.base_ref == config.develop_branch or is_release_promotion
    ):
        allow_develop_sync_merge_headlines = True

    if config.require_conventional_title and not CONVENTIONAL.search(event.pr_title or ""):
        if is_release_promotion:
            failures.append(
                "Release-promotion PR titles must follow Conventional Commits; "
                f"use 'chore(release): <lowercase subject>'. Current title: '{event.pr_title}'."
            )
        else:
            failures.append(
                "PR title must follow Conventional Commits, for example 'feat: add API cache'. "
                f"Current title: '{event.pr_title}'."
            )

    if config.require_conventional_commits and event.pr_number:
        if client is None:
            failures.append("Commit headline checks require a GitHub client.")
        else:
            fetch_failed = False
            try:
                commits = client.list_commits(event.repository, event.pr_number)
            except (RuntimeError, ValueError, OSError):
                failures.append("Unable to fetch PR commit headlines from GitHub after 5 attempts; failing closed.")
                commits = []
                fetch_failed = True
            if not fetch_failed and not commits:
                failures.append("GitHub returned no PR commit headlines; failing closed.")
            if not fetch_failed:
                try:
                    expected = client.pull_commit_count(event.repository, event.pr_number)
                except (RuntimeError, ValueError, OSError, TypeError):
                    failures.append(
                        "Unable to verify the PR commit count from GitHub; failing closed."
                    )
                else:
                    if not isinstance(expected, int) or expected < 1:
                        failures.append(
                            "GitHub returned an invalid PR commit count; failing closed."
                        )
                    elif len(commits) != expected:
                        failures.append(
                            f"PR commit listing is incomplete ({len(commits)} headlines, "
                            f"{expected} commits declared); failing closed."
                        )

            owner = event.head_repository.split("/", 1)[0] if event.head_repository else ""
            develop_sync = re.compile(rf"^Merge branch '{re.escape(config.develop_branch)}' into .+")
            develop_remote_sync = re.compile(
                rf"^Merge remote-tracking branch 'origin/{re.escape(config.develop_branch)}' into .+"
            )
            develop_sync_pr = re.compile(
                rf"^Merge pull request #[0-9]+ from {re.escape(owner)}/{re.escape(config.develop_branch)}$"
            )

            for commit in commits:
                if is_main_realignment:
                    continue
                develop_sync_headline = bool(
                    (is_release_promotion and GITHUB_MERGE.search(commit.headline))
                    or (
                        allow_develop_sync_merge_headlines
                        and (
                            develop_sync.search(commit.headline)
                            or develop_remote_sync.search(commit.headline)
                            or develop_sync_pr.search(commit.headline)
                        )
                    )
                )
                if develop_sync_headline:
                    error = verify_develop_source_merge(
                        commit, client, event.repository, config.develop_branch
                    )
                    if error:
                        failures.append(error)
                    continue
                if commit.parent_count > 1 and MERGE_HEADLINE.search(commit.headline):
                    continue
                if not CONVENTIONAL.search(commit.headline):
                    if is_develop_history_reconciliation:
                        try:
                            status = client.compare_status(
                                event.repository, commit.sha, config.main_branch
                            )
                        except (RuntimeError, ValueError, OSError):
                            failures.append(
                                f"Unable to verify whether non-Conventional commit '{commit.headline}' "
                                f"({commit.sha}) is inherited from '{config.main_branch}'; failing closed."
                            )
                            continue
                        if status not in {"ahead", "identical"}:
                            failures.append(
                                "Commit headline must follow Conventional Commits unless it is inherited "
                                f"from '{config.main_branch}' by the audited reconciliation: '{commit.headline}'."
                            )
                    else:
                        failures.append(f"Commit headline must follow Conventional Commits: '{commit.headline}'.")

    summary = [
        "## Repository Policy",
        f"- Event: `{event.event_name}`",
        f"- Base branch: `{event.base_ref}`",
        f"- Head branch: `{event.head_ref}`",
        f"- Base repository: `{event.base_repository}`",
        f"- Head repository: `{event.head_repository}`",
        f"- Enforce develop source branch prefixes: `{str(config.enforce_develop_source_branch_prefixes).lower()}`",
        f"- Develop source branch prefix regex: `{config.develop_source_branch_prefix_regex}`",
        f"- Develop history reconciliation: `{str(is_develop_history_reconciliation).lower()}`",
        f"- Conventional PR title: `{str(config.require_conventional_title).lower()}`",
        f"- Conventional commit headlines: `{str(config.require_conventional_commits).lower()}`",
        f"- Release promotion PR: `{str(is_release_promotion).lower()}`",
        f"- Develop sync merge headline exception: `{str(allow_develop_sync_merge_headlines).lower()}`",
        f"- Main realignment PR: `{str(is_main_realignment).lower()}`",
        f"- Main bot PR: `{str(is_main_bot_pr).lower()}`",
    ]
    return PolicyResult(
        ok=not failures,
        failures=failures,
        summary=summary,
        is_release_promotion=is_release_promotion,
        is_main_realignment=is_main_realignment,
        is_develop_history_reconciliation=is_develop_history_reconciliation,
        allow_develop_sync_merge_headlines=allow_develop_sync_merge_headlines,
        is_main_bot_pr=is_main_bot_pr,
    )


class GhPolicyClient(PolicyClient):
    def __init__(self, run: Callable[..., subprocess.CompletedProcess[str]] | None = None) -> None:
        self._run = run or subprocess.run

    def _api(self, path: str, query: str) -> str:
        last_error = ""
        for attempt in range(1, 6):
            result = self._run(
                ["gh", "api", "--paginate", path, "--jq", query],
                text=True,
                capture_output=True,
                check=False,
                timeout=45,
            )
            if result.returncode == 0:
                return result.stdout
            last_error = result.stderr.strip() or result.stdout.strip() or "GitHub API request failed"
            if attempt < 5:
                time.sleep(attempt * 10)
        raise RuntimeError(last_error)

    def list_commits(self, repository: str, pr_number: str) -> list[Commit]:
        if not REPO.fullmatch(repository) or not re.fullmatch(r"[0-9]+", pr_number):
            raise ValueError("Invalid repository or pull request number")
        raw = self._api(
            f"repos/{repository}/pulls/{pr_number}/commits",
            ".[] | [.sha, (.parents | length), (.commit.message | split(\"\\n\")[0])] | @tsv",
        )
        commits: list[Commit] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            sha, parent_count, headline = line.split("\t", 2)
            if SHA.fullmatch(sha) is None:
                raise RuntimeError("Invalid commit SHA in pull request listing")
            commits.append(Commit(sha=sha, parent_count=int(parent_count), headline=headline))
        return commits

    def pull_commit_count(self, repository: str, pr_number: str) -> int:
        if not REPO.fullmatch(repository) or not re.fullmatch(r"[0-9]+", pr_number):
            raise ValueError("Invalid repository or pull request number")
        raw = self._api(f"repos/{repository}/pulls/{pr_number}", ".commits")
        try:
            count = int(raw.strip())
        except ValueError as error:
            raise RuntimeError("Invalid pull request commit count") from error
        if count < 1:
            raise RuntimeError("Invalid pull request commit count")
        return count

    def commit_parents(self, repository: str, sha: str) -> list[str]:
        if not REPO.fullmatch(repository) or SHA.fullmatch(sha) is None:
            raise ValueError("Invalid repository or commit")
        raw = self._api(f"repos/{repository}/commits/{sha}", "[.parents[].sha] | @tsv")
        return [item for item in raw.strip().split("\t") if item]

    def compare_status(self, repository: str, base: str, head: str) -> str:
        if not REPO.fullmatch(repository):
            raise ValueError("Invalid repository")
        raw = self._api(f"repos/{repository}/compare/{base}...{head}", ".status")
        return raw.strip()


def event_from_env(env: dict[str, str]) -> PolicyEvent:
    return PolicyEvent(
        event_name=env.get("EVENT_NAME", ""),
        repository=env.get("REPOSITORY", ""),
        merge_group_base_ref=env.get("MERGE_GROUP_BASE_REF", ""),
        pr_number=env.get("PR_NUMBER", ""),
        pr_title=env.get("PR_TITLE", ""),
        pr_author=env.get("PR_AUTHOR", ""),
        base_ref=env.get("BASE_REF", ""),
        head_ref=env.get("HEAD_REF", ""),
        base_repository=env.get("BASE_REPOSITORY", ""),
        head_repository=env.get("HEAD_REPOSITORY", ""),
    )


def config_from_env(env: dict[str, str]) -> PolicyConfig:
    return PolicyConfig(
        main_branch=env.get("MAIN_BRANCH", "main"),
        develop_branch=env.get("DEVELOP_BRANCH", "develop"),
        enforce_develop_source_branch_prefixes=as_bool(
            env.get("ENFORCE_DEVELOP_SOURCE_BRANCH_PREFIXES", "true")
        ),
        develop_source_branch_prefix_regex=env.get(
            "DEVELOP_SOURCE_BRANCH_PREFIX_REGEX", PolicyConfig.develop_source_branch_prefix_regex
        ),
        allow_develop_history_reconciliation=as_bool(
            env.get("ALLOW_DEVELOP_HISTORY_RECONCILIATION", "false")
        ),
        develop_history_reconciliation_head_regex=env.get(
            "DEVELOP_HISTORY_RECONCILIATION_HEAD_REGEX",
            PolicyConfig.develop_history_reconciliation_head_regex,
        ),
        require_conventional_title=as_bool(env.get("REQUIRE_CONVENTIONAL_TITLE", "true")),
        require_conventional_commits=as_bool(env.get("REQUIRE_CONVENTIONAL_COMMITS", "true")),
        allow_main_realignment_pr=as_bool(env.get("ALLOW_MAIN_REALIGNMENT_PR", "false")),
        main_realignment_head_regex=env.get(
            "MAIN_REALIGNMENT_HEAD_REGEX", PolicyConfig.main_realignment_head_regex
        ),
        allow_main_bot_pr=as_bool(env.get("ALLOW_MAIN_BOT_PR", "false")),
        main_bot_author=env.get("MAIN_BOT_AUTHOR", ""),
        main_bot_head_regex=env.get("MAIN_BOT_HEAD_REGEX", ""),
    )


def main() -> None:
    result = evaluate(event_from_env(dict(os.environ)), config_from_env(dict(os.environ)), GhPolicyClient())
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(result.summary) + "\n")
    if not result.ok:
        sys.stderr.write("Repository policy failed:\n")
        for item in result.failures:
            sys.stderr.write(f"- {item}\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
