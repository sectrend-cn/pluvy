"""Own admission and inert-file preparation for default-branch preview publishing.

Every GitHub response is narrowed at ingress. Artifact bytes never provide
identity, currentness, configuration, executable tools, or deployment targets.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import shutil
import tarfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

REPOSITORY = "sectrend-cn/pluvy"
BUILD_PATH = ".github/workflows/preview-website.yml"
WORKFLOW_ID = 415667994
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_ENTRIES = 20000
MAX_PR_FILES = 3000
FILES_PER_PAGE = 100


def _text(value: object) -> str:
    """Require a JSON string at the external boundary."""
    if not isinstance(value, str) or not value:
        raise ValueError("Missing or invalid GitHub string")
    return value


def _positive(value: object) -> int:
    """Require a positive JSON integer, excluding booleans."""
    if type(value) is not int or value < 1:
        raise ValueError("Missing or invalid GitHub integer")
    return value


def _nonnegative(value: object) -> int:
    """Preserve zero file counts while rejecting missing, negative, or coerced values."""
    if type(value) is not int or value < 0:
        raise ValueError("Missing or invalid GitHub file count")
    return value


def _boolean(value: object) -> bool:
    """Require a JSON boolean without truthiness coercion."""
    if not isinstance(value, bool):
        raise ValueError("Missing or invalid GitHub boolean")
    return value


def _mergeable(value: object) -> bool | None:
    """Preserve GitHub's unknown mergeability until the selected PR is checked."""
    return None if value is None else _boolean(value)


def _sha(value: object) -> str:
    """Require a full Git object identity before constructing API paths."""
    text = _text(value)
    if re.fullmatch(r"[0-9a-f]{40}", text) is None:
        raise ValueError("Missing or invalid GitHub SHA")
    return text


@dataclass(frozen=True)
class Repository:
    """GitHub-owned repository identity, including its owner."""

    full_name: str
    owner: str

    @classmethod
    def from_json(cls, value: object) -> Repository:
        """Narrow a repository response at API/event ingress."""
        if not isinstance(value, dict) or not isinstance(value.get("owner"), dict):
            raise ValueError("Missing GitHub repository identity")
        return cls(_text(value.get("full_name")), _text(value["owner"].get("login")))


@dataclass(frozen=True)
class Run:
    """Facts supplied by GitHub about one workflow execution attempt."""

    id: int
    run_attempt: int
    workflow_id: int
    path: str
    repository: Repository
    head_repository: Repository
    head_sha: str
    event: str
    status: str
    conclusion: str

    @classmethod
    def from_json(cls, value: object) -> Run:
        """Reject incomplete runs before they enter admission policy."""
        if not isinstance(value, dict):
            raise ValueError("Missing workflow run")
        return cls(
            _positive(value.get("id")),
            _positive(value.get("run_attempt")),
            _positive(value.get("workflow_id")),
            _text(value.get("path")),
            Repository.from_json(value.get("repository")),
            Repository.from_json(value.get("head_repository")),
            _sha(value.get("head_sha")),
            _text(value.get("event")),
            _text(value.get("status")),
            _text(value.get("conclusion")),
        )


@dataclass(frozen=True)
class Trigger:
    """The trusted runner's workflow_run envelope, never an artifact manifest."""

    repository: Repository
    run: Run

    @classmethod
    def read(cls, path: Path) -> Trigger:
        """Read and narrow the runner-provided event exactly once."""
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("action") != "completed":
            raise ValueError("Expected a completed workflow_run event")
        return cls(
            Repository.from_json(data.get("repository")), Run.from_json(data.get("workflow_run"))
        )


@dataclass(frozen=True)
class PullRequest:
    """Live pull request state, not workflow_run.pull_requests associations."""

    number: int
    state: str
    merged: bool
    head_repository: Repository
    base_repository: Repository
    head_sha: str
    base_ref: str
    mergeable: bool | None
    changed_files: int
    base_sha: str

    @classmethod
    def from_json(cls, value: object) -> PullRequest:
        """Narrow a full pull request API response."""
        if not isinstance(value, dict):
            raise ValueError("Missing pull request")
        head, base = value.get("head"), value.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise ValueError("Missing pull request refs")
        return cls(
            _positive(value.get("number")),
            _text(value.get("state")),
            _boolean(value.get("merged")),
            Repository.from_json(head.get("repo")),
            Repository.from_json(base.get("repo")),
            _sha(head.get("sha")),
            _text(base.get("ref")),
            _mergeable(value.get("mergeable")),
            _nonnegative(value.get("changed_files")),
            _sha(base.get("sha")),
        )


def _preview_input(path: str) -> bool:
    """Recognize only canonical, case-sensitive website/docs paths without normalization."""
    parts = path.split("/")
    return (
        "\\" not in path
        and parts[0] in {"website", "docs"}
        and all(part not in {"", ".", ".."} for part in parts)
    )


@dataclass(frozen=True)
class PullFile:
    """One API-owned changed path and its optional pre-rename path."""

    filename: str
    previous_filename: str | None = None

    @classmethod
    def from_json(cls, value: object) -> PullFile:
        """Narrow file metadata at ingress; URLs and patch contents have no authority."""
        if not isinstance(value, dict):
            raise ValueError("Invalid GitHub changed-file entry")
        previous = None
        if "previous_filename" in value:
            previous = _text(value["previous_filename"])
        return cls(_text(value.get("filename")), previous)

    def touches_preview(self) -> bool:
        """Include deletions and renames into or away from a real preview input."""
        return _preview_input(self.filename) or (
            self.previous_filename is not None and _preview_input(self.previous_filename)
        )


@dataclass(frozen=True)
class Artifact:
    """Server-owned artifact identity and association with the source run."""

    id: int
    name: str
    run_id: int
    expired: bool

    @classmethod
    def from_json(cls, value: object) -> Artifact:
        """Reject artifacts lacking a server-owned run association."""
        if not isinstance(value, dict) or not isinstance(value.get("workflow_run"), dict):
            raise ValueError("Missing artifact run association")
        return cls(
            _positive(value.get("id")),
            _text(value.get("name")),
            _positive(value["workflow_run"].get("id")),
            _boolean(value.get("expired")),
        )


@dataclass(frozen=True)
class MergeCommit:
    """Current server-maintained merge relationship, never artifact provenance."""

    sha: str
    parents: tuple[str, ...]

    @classmethod
    def from_json(cls, value: object) -> MergeCommit:
        """Narrow the Git commit API without guessing absent parent evidence."""
        if not isinstance(value, dict) or not isinstance(value.get("parents"), list):
            raise ValueError("Missing Git merge commit parents")
        parents: list[str] = []
        for parent in value["parents"]:
            if not isinstance(parent, dict):
                raise ValueError("Invalid Git merge commit parent")
            parents.append(_sha(parent.get("sha")))
        return cls(_sha(value.get("sha")), tuple(parents))


class PreviewApi(Protocol):
    """Read-only GitHub evidence needed by the admission owner."""

    def workflow(self) -> tuple[int, str]: ...
    def run(self, run_id: int, attempt: int | None = None) -> Run: ...
    def pull_numbers(self, head_sha: str) -> tuple[int, ...]: ...
    def pull(self, number: int) -> PullRequest: ...
    def pull_files(self, number: int) -> tuple[PullFile, ...]: ...
    def main_sha(self) -> str: ...
    def merge(self, number: int) -> MergeCommit: ...
    def artifacts(self, run_id: int) -> tuple[Artifact, ...]: ...


class GitHubApi:
    """Adapt a fetcher into concrete GitHub contracts without trusting URLs in JSON."""

    def __init__(self, fetcher: Callable[[str], str]) -> None:
        self._fetch = fetcher

    def workflow(self) -> tuple[int, str]:
        """Verify the registered workflow rather than relying on its display name."""
        data = json.loads(self._fetch(f"/actions/workflows/{WORKFLOW_ID}"))
        return _positive(data["id"]), _text(data["path"])

    def run(self, run_id: int, attempt: int | None = None) -> Run:
        """Read either the current run or the exact triggering attempt."""
        suffix = "" if attempt is None else f"/attempts/{attempt}"
        return Run.from_json(json.loads(self._fetch(f"/actions/runs/{run_id}{suffix}")))

    def pull_numbers(self, head_sha: str) -> tuple[int, ...]:
        """Resolve PRs from the commit API; never accept truncated associations."""
        data = json.loads(self._fetch(f"/commits/{head_sha}/pulls?per_page=100"))
        if not isinstance(data, list) or len(data) >= 100:
            raise ValueError("Missing or truncated PR associations")
        return tuple(_positive(item["number"]) for item in data)

    def pull(self, number: int) -> PullRequest:
        """Read current PR state after resolving its number from the source SHA."""
        return PullRequest.from_json(json.loads(self._fetch(f"/pulls/{number}")))

    def pull_files(self, number: int) -> tuple[PullFile, ...]:
        """Read complete numbered pages, including an empty page after a full final page."""
        files: list[PullFile] = []
        seen: set[str] = set()
        for page in range(1, MAX_PR_FILES // FILES_PER_PAGE + 2):
            data = json.loads(
                self._fetch(f"/pulls/{number}/files?per_page={FILES_PER_PAGE}&page={page}")
            )
            if not isinstance(data, list) or len(data) > FILES_PER_PAGE:
                raise ValueError("Invalid GitHub Files API page")
            for entry in data:
                file = PullFile.from_json(entry)
                if file.filename in seen:
                    raise ValueError("Duplicate GitHub changed-file entry")
                seen.add(file.filename)
                files.append(file)
            if len(files) > MAX_PR_FILES:
                raise ValueError("GitHub changed-file listing exceeds 3000 files")
            if len(data) < FILES_PER_PAGE:
                return tuple(files)
        raise ValueError("GitHub changed-file pagination did not finish")

    def _commit_ref(self, ref: str) -> str:
        """Resolve only the requested server-owned ref to a commit identity."""
        data = json.loads(self._fetch(f"/git/ref/{ref}"))
        if data["ref"] != f"refs/{ref}" or data["object"]["type"] != "commit":
            raise ValueError("Unexpected Git commit ref")
        return _sha(data["object"]["sha"])

    def main_sha(self) -> str:
        """Read current main independently of any PR-supplied base metadata."""
        return self._commit_ref("heads/main")

    def merge(self, number: int) -> MergeCommit:
        """Read the current merge commit and its parents through fixed Git APIs."""
        sha = self._commit_ref(f"pull/{number}/merge")
        commit = MergeCommit.from_json(json.loads(self._fetch(f"/git/commits/{sha}")))
        if commit.sha != sha:
            raise ValueError("Git merge commit disagrees with requested ref")
        return commit

    def artifacts(self, run_id: int) -> tuple[Artifact, ...]:
        """Require a complete, single-artifact listing for exactly this run."""
        data = json.loads(self._fetch(f"/actions/runs/{run_id}/artifacts?per_page=100"))
        if data["total_count"] != 1 or len(data["artifacts"]) != 1:
            raise ValueError("Missing or unexpected artifact")
        return tuple(Artifact.from_json(item) for item in data["artifacts"])


class GitHubFetcher:
    """Use only the Actions token against a fixed HTTPS origin, without redirects."""

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("GITHUB_TOKEN is required for admission")
        self._token = token

    def __call__(self, path: str) -> str:
        """Bound responses and fail on network, authorization, or decoding errors."""
        connection = http.client.HTTPSConnection("api.github.com", timeout=30)
        try:
            connection.request(
                "GET",
                f"/repos/{REPOSITORY}{path}",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "pluvy-preview-admission",
                },
            )
            response = connection.getresponse()
            content = response.read(2 * 1024 * 1024 + 1)
            if response.status != 200 or len(content) > 2 * 1024 * 1024:
                raise ValueError("GitHub admission API request failed")
            return content.decode("utf-8")
        finally:
            connection.close()


@dataclass(frozen=True)
class Admission:
    """Keep the requested build head separate from current relationship evidence."""

    pr_number: int
    artifact: Artifact
    head_sha: str
    current_merge: MergeCommit


def _repository_matches(repository: Repository, trusted: str) -> bool:
    """Require the exact trusted repository and owner on every relevant object."""
    return repository.full_name == trusted == REPOSITORY and repository.owner == "sectrend-cn"


def _verify_run(run: Run, source: Run, trusted: str) -> None:
    """Bind path, registered ID, event, status, repository, run and attempt."""
    if run.path != BUILD_PATH or run.workflow_id != WORKFLOW_ID:
        raise ValueError("Untrusted workflow path or workflow_id")
    if not all(
        _repository_matches(repo, trusted) for repo in (run.repository, run.head_repository)
    ):
        raise ValueError("Untrusted workflow repository or owner")
    if run.event != "pull_request" or run.conclusion != "success" or run.status != "completed":
        raise ValueError("Expected a successful completed pull_request run")
    if (run.id, run.run_attempt) != (source.id, source.run_attempt):
        raise ValueError("Wrong run id or run attempt")


def _verify_pull(pr: PullRequest, numbers: tuple[int, ...], trusted: str) -> None:
    """Authorize the selected PR's identity, repository, base, and mergeability."""
    if pr.number not in numbers or pr.number < 1:
        raise ValueError("Wrong PR identity")
    if not all(
        _repository_matches(repo, trusted) for repo in (pr.head_repository, pr.base_repository)
    ):
        raise ValueError("Fork or foreign PR repository")
    if pr.base_ref != "main":
        raise ValueError("Preview PR must target the trusted default branch")
    if pr.mergeable is not True:
        raise ValueError("PR is not currently mergeable")


def _current_pull(source: Run, api: PreviewApi, trusted: str) -> PullRequest:
    """Resolve only the sole current open PR from the server-owned source head."""
    numbers = api.pull_numbers(source.head_sha)
    if len(set(numbers)) != len(numbers):
        raise ValueError("Duplicate PR associations")
    pulls = tuple(api.pull(number) for number in numbers)
    current = tuple(
        pr
        for pr in pulls
        if pr.state == "open" and not pr.merged and pr.head_sha == source.head_sha
    )
    if len(current) != 1:
        raise ValueError("Expected exactly one current open PR; head may be stale")
    pr = current[0]
    _verify_pull(pr, numbers, trusted)
    return pr


def _current_merge(pr: PullRequest, api: PreviewApi) -> MergeCommit:
    """Verify only today's two-parent relationship; never infer a build merge SHA."""
    main = api.main_sha()
    merge = api.merge(pr.number)
    if merge.parents != (main, pr.head_sha) or merge.sha in {main, pr.head_sha}:
        raise ValueError("Stale base or invalid current merge relationship")
    return merge


def _verify_preview_inputs(pr: PullRequest, head_sha: str, api: PreviewApi, trusted: str) -> None:
    """Bind complete API file evidence to one unchanged, authorized PR snapshot."""
    if pr.changed_files > MAX_PR_FILES:
        raise ValueError("PR changed_files exceeds GitHub's 3000-file limit")
    snapshot = (pr.number, pr.head_sha, pr.base_sha, pr.changed_files)
    files = api.pull_files(pr.number)
    current = api.pull(pr.number)
    if snapshot != (current.number, current.head_sha, current.base_sha, current.changed_files):
        raise ValueError("PR snapshot changed during file pagination")
    if current.head_sha != head_sha or current.state != "open" or current.merged:
        raise ValueError("PR is no longer current and open after file pagination")
    _verify_pull(current, (pr.number,), trusted)
    if len(files) != pr.changed_files:
        raise ValueError("Incomplete GitHub changed-file listing")
    if not any(file.touches_preview() for file in files):
        raise ValueError("PR has no website or docs input changes")


def admit(trigger: Trigger, api: PreviewApi, trusted: str, expected_run_id: int) -> Admission:
    """Fail closed unless the event and live API jointly prove every invariant.

    The build explicitly requests the immutable PR head. API head identities
    prove currentness, not artifact bytes or historical merge provenance. Today's
    merge relationship may move independently of the requested build head.
    """
    source = trigger.run
    if not _repository_matches(trigger.repository, trusted) or source.id != expected_run_id:
        raise ValueError("Wrong event repository or triggering run id")
    _verify_run(source, source, trusted)
    if api.workflow() != (WORKFLOW_ID, BUILD_PATH):
        raise ValueError("Registered workflow identity changed")
    live = api.run(source.id)
    _verify_run(live, source, trusted)
    if live.head_sha != source.head_sha:
        raise ValueError("Run head SHA disagrees with event")
    pr = _current_pull(source, api, trusted)
    _verify_preview_inputs(pr, source.head_sha, api, trusted)
    attempt = api.run(source.id, source.run_attempt)
    _verify_run(attempt, source, trusted)
    if attempt.head_sha != source.head_sha:
        raise ValueError("Attempt head SHA disagrees with event")
    merge = _current_merge(pr, api)
    artifacts = api.artifacts(source.id)
    if len(artifacts) != 1:
        raise ValueError("Missing or unexpected artifact")
    artifact = artifacts[0]
    expected_name = f"website-preview-{source.id}-{source.run_attempt}"
    if artifact.name != expected_name or artifact.run_id != source.id or artifact.expired:
        raise ValueError("Wrong artifact name, run id, or expired artifact")
    return Admission(pr.number, artifact, source.head_sha, merge)


def _static_path(member: tarfile.TarInfo, root: Path) -> Path:
    """Allow only static asset paths with no Pages execution or configuration."""
    name = member.name.removeprefix("./")
    parts = name.removesuffix("/").split("/") if member.isdir() else name.split("/")
    forbidden = {
        "functions",
        "node_modules",
        "package.json",
        "package-lock.json",
        "npm-shrinkwrap.json",
        "wrangler.toml",
        "wrangler.json",
        "wrangler.jsonc",
    }
    for part in parts:
        if not re.fullmatch(r"[\w@()+,.-]+", part, re.ASCII) or part.startswith("."):
            raise ValueError("Unsafe static asset path")
        if part.casefold() in forbidden or (part.startswith("_") and part != "_astro"):
            raise ValueError("Executable or configurable Pages input is forbidden")
    if len(name) > 1024:
        raise ValueError("Static asset path is too long")
    return root.joinpath(*parts)


def _copy_member(archive: tarfile.TarFile, member: tarfile.TarInfo, target: Path) -> None:
    """Copy regular bytes with exclusive creation, without extracting metadata."""
    if member.isdir():
        target.mkdir(parents=True, exist_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    source = archive.extractfile(member)
    if source is None:
        raise ValueError("Missing regular-file content")
    with source, target.open("xb") as destination:
        shutil.copyfileobj(source, destination)


def _inert_marker(member: tarfile.TarInfo, seen: set[str]) -> bool:
    """Omit only unique, inert tar-root and GitHub Pages marker entries."""
    name = member.name.removeprefix("./")
    root = member.name in {".", "./"} and member.isdir()
    marker = name == ".nojekyll" and member.isfile() and member.size == 0
    if not (root or marker):
        return False
    identity = "." if root else name
    if identity in seen:
        raise ValueError("Duplicate archive marker")
    seen.add(identity)
    return True


def prepare_static_upload(archive_path: Path, root: Path) -> None:
    """Copy validated regular files to a fresh directory and add trusted noindex."""
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError("Expected a regular archive")
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Static archive is too large")
    root.mkdir()
    seen: set[str] = set()
    total = 0
    with tarfile.open(archive_path, "r:") as archive:
        for index, member in enumerate(archive):
            if (
                index >= MAX_ENTRIES
                or member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}
                or member.sparse is not None
                or (member.isdir() and member.size != 0)
            ):
                raise ValueError("Too many entries or a link/special file")
            if _inert_marker(member, seen):
                continue
            target = _static_path(member, root)
            identity = target.relative_to(root).as_posix().casefold()
            total += member.size
            if (
                identity in seen
                or not 0 <= member.size <= MAX_FILE_BYTES
                or total > MAX_ARCHIVE_BYTES
            ):
                raise ValueError("Duplicate asset or static upload size limit exceeded")
            seen.add(identity)
            _copy_member(archive, member, target)
    if not (root / "index.html").is_file():
        raise ValueError("Static index.html is required")
    (root / "_headers").write_text(
        "/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n", encoding="utf-8"
    )


def main() -> None:
    """Expose admission outputs and static preparation to trusted Actions only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("admit", "prepare"))
    args = parser.parse_args()
    if args.operation == "prepare":
        temporary = Path(os.environ["RUNNER_TEMP"])
        incoming = temporary / "preview-incoming"
        if incoming.is_symlink() or set(incoming.iterdir()) != {incoming / "website-preview.tar"}:
            raise ValueError("Unexpected incoming artifact files")
        prepare_static_upload(incoming / "website-preview.tar", temporary / "preview-upload")
        return
    if os.environ["GITHUB_EVENT_NAME"] != "workflow_run":
        raise ValueError("Publisher must run from workflow_run")
    admission = admit(
        Trigger.read(Path(os.environ["GITHUB_EVENT_PATH"])),
        GitHubApi(GitHubFetcher(os.environ["GITHUB_TOKEN"])),
        os.environ["GITHUB_REPOSITORY"],
        _positive(int(os.environ["SOURCE_RUN_ID"])),
    )
    if "EXPECTED_PR_NUMBER" in os.environ:
        expected = (os.environ["EXPECTED_PR_NUMBER"], os.environ["EXPECTED_ARTIFACT_ID"])
        if expected != (str(admission.pr_number), str(admission.artifact.id)):
            raise ValueError("Admission changed while the publisher was queued")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"pr-number={admission.pr_number}\nartifact-id={admission.artifact.id}\n")
    print(
        f"Verified PR head {admission.head_sha}; current merge {admission.current_merge.sha} "
        "is relationship evidence only, not the artifact tree."
    )


if __name__ == "__main__":
    main()
