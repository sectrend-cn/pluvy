"""Exercise admission with concrete API contracts and adversarial live state."""

from __future__ import annotations

import io
import json
import sys
import tarfile
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preview_publish import (
    BUILD_PATH,
    REPOSITORY,
    WORKFLOW_ID,
    Artifact,
    GitHubApi,
    MergeCommit,
    PullFile,
    PullRequest,
    Repository,
    Run,
    Trigger,
    admit,
    prepare_static_upload,
)

HEAD = "a" * 40
MERGE = "b" * 40
BASE = "c" * 40
REPO = Repository(REPOSITORY, "sectrend-cn")
PR_RESPONSE = (
    '{"number":23,"state":"open","merged":false,"mergeable":true,"changed_files":1,'
    '"head":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"repo":{"full_name":"sectrend-cn/pluvy","owner":{"login":"sectrend-cn"}}},'
    '"base":{"ref":"main","sha":"cccccccccccccccccccccccccccccccccccccccc",'
    '"repo":{"full_name":"sectrend-cn/pluvy","owner":{"login":"sectrend-cn"}}}}'
)


def source_run() -> Run:
    """Declare server-owned run facts independently of any archive."""
    return Run(
        123, 2, WORKFLOW_ID, BUILD_PATH, REPO, REPO, HEAD, "pull_request", "completed", "success"
    )


def write_file_page(root: Path, page: int, files: tuple[PullFile, ...]) -> Path:
    """Write concrete file contracts at the external HTTP-body fixture boundary."""
    path = root / f"files-page-{page}.json"
    path.write_text(
        json.dumps(
            [
                {"filename": file.filename}
                if file.previous_filename is None
                else {"filename": file.filename, "previous_filename": file.previous_filename}
                for file in files
            ]
        ),
        encoding="utf-8",
    )
    return path


class FilesFetcher:
    """Serve numbered response fixtures only when the real API requests their fixed paths."""

    def __init__(self, pages: tuple[Path, ...]) -> None:
        self.pages = pages
        self.requests: list[str] = []

    def __call__(self, path: str) -> str:
        self.requests.append(path)
        for page, fixture in enumerate(self.pages, 1):
            if path == f"/pulls/23/files?per_page=100&page={page}":
                return fixture.read_text(encoding="utf-8")
        raise OSError("Missing or unexpected Files API page")


class FixtureApi:
    """Keep requested build head and current merge-parent evidence independent."""

    def __init__(self) -> None:
        self.identity = (WORKFLOW_ID, BUILD_PATH)
        self.live = source_run()
        self.attempt = self.live
        self.pulls = {23: PullRequest(23, "open", False, REPO, REPO, HEAD, "main", True, 1, BASE)}
        self.files: tuple[PullFile, ...] = (PullFile("website/index.html"),)
        self.files_api: GitHubApi | None = None
        self.after_listing: PullRequest | None = None
        self.pull_requests: list[int] = []
        self.file_requests: list[int] = []
        self.associations: tuple[int, ...] = (23,)
        self.main = BASE
        self.merge_commit = MergeCommit(MERGE, (BASE, HEAD))
        self.uploads: tuple[Artifact, ...] = (Artifact(456, "website-preview-123-2", 123, False),)
        self.run_requests: list[tuple[int, int | None]] = []
        self.artifact_requests: list[int] = []

    def workflow(self) -> tuple[int, str]:
        """Represent the registered workflow API, including its immutable ID."""
        return self.identity

    def run(self, run_id: int, attempt: int | None = None) -> Run:
        """Record which exact run and attempt the policy consults."""
        self.run_requests.append((run_id, attempt))
        return self.live if attempt is None else self.attempt

    def pull_numbers(self, head_sha: str) -> tuple[int, ...]:
        """Reject accidental PR lookup using the merge SHA or untrusted metadata."""
        if head_sha != HEAD:
            raise ValueError("Expected source PR head")
        return self.associations

    def pull(self, number: int) -> PullRequest:
        """Supply current PR state independently of event associations."""
        self.pull_requests.append(number)
        if self.file_requests and self.after_listing is not None:
            return self.after_listing
        return self.pulls[number]

    def pull_files(self, number: int) -> tuple[PullFile, ...]:
        """Record the verified PR number and optionally exercise real API pagination."""
        self.file_requests.append(number)
        if self.files_api is not None:
            return self.files_api.pull_files(number)
        return self.files

    def main_sha(self) -> str:
        """Supply today's base independently of the successful head-tree build."""
        return self.main

    def merge(self, number: int) -> MergeCommit:
        """Require the verified PR number to select the live merge ref."""
        if number != 23:
            raise ValueError("Wrong merge ref")
        return self.merge_commit

    def artifacts(self, run_id: int) -> tuple[Artifact, ...]:
        """Record the run-bound download admission request."""
        self.artifact_requests.append(run_id)
        return self.uploads


class PreviewAdmissionTests(unittest.TestCase):
    """Prove that workflow names and artifact metadata convey no authority."""

    def setUp(self) -> None:
        self.trigger = Trigger(REPO, source_run())
        self.api = FixtureApi()

    def reject(self, expected: str) -> None:
        """Require a terminal admission failure, never a successful skip."""
        with self.assertRaisesRegex(ValueError, expected):
            admit(self.trigger, self.api, REPOSITORY, 123)

    def test_accepts_only_bound_current_run_and_exact_artifact(self) -> None:
        result = admit(self.trigger, self.api, REPOSITORY, 123)
        self.assertEqual(result.pr_number, 23)
        self.assertEqual(result.artifact.id, 456)
        self.assertEqual(result.artifact.name, "website-preview-123-2")
        self.assertEqual(result.head_sha, HEAD)
        self.assertEqual(result.current_merge.parents, (BASE, HEAD))
        self.assertNotEqual(result.head_sha, result.current_merge.sha)
        self.assertEqual(self.api.run_requests, [(123, None), (123, 2)])
        self.assertEqual(self.api.artifact_requests, [123])
        self.assertEqual(self.api.file_requests, [23])
        self.assertEqual(self.api.pull_requests, [23, 23])

    def test_accepts_website_or_docs_paths_including_exact_roots(self) -> None:
        for filename in ("website", "website/src/page.astro", "docs", "docs/zh/start.md"):
            with self.subTest(filename=filename):
                self.api.files = (PullFile(filename),)
                self.assertEqual(admit(self.trigger, self.api, REPOSITORY, 123).pr_number, 23)

    def test_accepts_renames_into_or_away_from_website_and_docs(self) -> None:
        for file in (
            PullFile("archive/page.md", "website/page.md"),
            PullFile("archive/page.md", "docs/page.md"),
            PullFile("website/page.md", "other/page.md"),
            PullFile("docs/page.md", "other/page.md"),
        ):
            with self.subTest(file=file):
                self.api.files = (file,)
                self.assertEqual(admit(self.trigger, self.api, REPOSITORY, 123).head_sha, HEAD)

    def test_rejects_rename_that_touches_neither_input_tree(self) -> None:
        self.api.files = (PullFile("other/new.md", "other/old.md"),)
        self.reject("no website or docs input changes")

    def test_rejects_yaml_tests_and_scripts_only(self) -> None:
        for paths in (
            (BUILD_PATH,),
            (".github/tests/test_preview_admission.py",),
            (".github/scripts/preview_publish.py",),
            (
                BUILD_PATH,
                ".github/tests/test_preview_admission.py",
                ".github/scripts/preview_publish.py",
            ),
        ):
            with self.subTest(paths=paths):
                self.api.files = tuple(PullFile(path) for path in paths)
                self.api.pulls[23] = replace(self.api.pulls[23], changed_files=len(paths))
                self.reject("no website or docs input changes")

    def test_rejects_boundary_misses_and_noncanonical_paths_in_both_names(self) -> None:
        for path in (
            "website-evil/index.html",
            "websites/page.md",
            "docsfoo",
            "docs-other/page.md",
            "Website/page.md",
            "Docs/page.md",
            ".website/page.md",
            "foo/website/page.md",
            "../website/page.md",
            "website/../page.md",
            "/website/page.md",
            "./website/page.md",
            "website\\page.md",
            "docs/a\\b.md",
            "docs/../../page.md",
            "docs//page.md",
        ):
            for file in (PullFile(path), PullFile("other/page.md", path)):
                with self.subTest(file=file):
                    self.api.files = (file,)
                    self.reject("no website or docs input changes")

    def test_rejects_zero_changed_files_as_no_preview_inputs(self) -> None:
        self.api.pulls[23] = replace(self.api.pulls[23], changed_files=0)
        self.api.files = ()
        self.reject("no website or docs input changes")
        self.assertEqual(self.api.file_requests, [23])

    def test_rejects_snapshot_changes_during_file_listing(self) -> None:
        before = self.api.pulls[23]
        for after in (
            replace(before, head_sha="d" * 40),
            replace(before, base_sha="d" * 40),
            replace(before, changed_files=2),
            replace(before, number=24),
        ):
            with self.subTest(after=after):
                self.api = FixtureApi()
                self.api.after_listing = after
                self.reject("snapshot changed during file pagination")
                self.assertEqual(self.api.pull_requests, [23, 23])
                self.assertEqual(self.api.file_requests, [23])

    def test_rejects_pr_closed_during_file_listing(self) -> None:
        self.api.after_listing = replace(self.api.pulls[23], state="closed", merged=True)
        self.reject("no longer current and open")

    def test_rejects_cap_overflow_before_listing_a_3000_file_prefix(self) -> None:
        self.api.pulls[23] = replace(self.api.pulls[23], changed_files=3001)
        self.api.files = tuple(PullFile(f"docs/{index}.md") for index in range(3000))
        self.reject("changed_files exceeds.*3000")
        self.assertEqual(self.api.file_requests, [])
        self.assertEqual(self.api.artifact_requests, [])

    def test_every_admit_rechecks_changed_files(self) -> None:
        for _ in range(3):
            self.assertEqual(admit(self.trigger, self.api, REPOSITORY, 123).pr_number, 23)
        self.assertEqual(self.api.file_requests, [23, 23, 23])
        self.assertEqual(self.api.pull_requests, [23, 23, 23, 23, 23, 23])
        self.api.files = (PullFile(BUILD_PATH),)
        self.reject("no website or docs input changes")

    def test_pagination_admits_when_only_page_two_has_a_preview_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch = FilesFetcher(
                (
                    write_file_page(
                        root, 1, tuple(PullFile(f"other/{index}.md") for index in range(100))
                    ),
                    write_file_page(root, 2, (PullFile("docs/start.md"),)),
                )
            )
            self.api.files_api = GitHubApi(fetch)
            self.api.pulls[23] = replace(self.api.pulls[23], changed_files=101)
            self.assertEqual(admit(self.trigger, self.api, REPOSITORY, 123).pr_number, 23)
            self.assertEqual(
                fetch.requests,
                [
                    "/pulls/23/files?per_page=100&page=1",
                    "/pulls/23/files?per_page=100&page=2",
                ],
            )

    def test_full_last_page_requires_an_empty_following_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch = FilesFetcher(
                (
                    write_file_page(
                        root, 1, tuple(PullFile(f"docs/{index}.md") for index in range(100))
                    ),
                    write_file_page(root, 2, ()),
                )
            )
            self.api.files_api = GitHubApi(fetch)
            self.api.pulls[23] = replace(self.api.pulls[23], changed_files=100)
            self.assertEqual(admit(self.trigger, self.api, REPOSITORY, 123).pr_number, 23)
            self.assertEqual(
                fetch.requests,
                [
                    "/pulls/23/files?per_page=100&page=1",
                    "/pulls/23/files?per_page=100&page=2",
                ],
            )
            write_file_page(root, 2, (PullFile("docs/extra.md"),))
            self.reject("Incomplete GitHub changed-file listing")

    def test_complete_3000_files_accepts_and_extra_page_content_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pages: list[Path] = []
            for page in range(1, 31):
                files = tuple(PullFile(f"other/{page}-{index}.md") for index in range(100))
                if page == 30:
                    files = (*files[:-1], PullFile("website/page.astro"))
                pages.append(write_file_page(root, page, files))
            pages.append(write_file_page(root, 31, ()))
            fetch = FilesFetcher(tuple(pages))
            self.api.files_api = GitHubApi(fetch)
            self.api.pulls[23] = replace(self.api.pulls[23], changed_files=3000)
            self.assertEqual(admit(self.trigger, self.api, REPOSITORY, 123).pr_number, 23)
            self.assertEqual(len(fetch.requests), 31)
            self.assertEqual(fetch.requests[-1], "/pulls/23/files?per_page=100&page=31")
            write_file_page(root, 31, (PullFile("docs/overflow.md"),))
            self.reject("listing exceeds 3000")

    def test_rejects_short_truncated_or_wrong_count_pages(self) -> None:
        for actual, expected in ((99, 101), (1, 2), (2, 1), (0, 1)):
            with (
                self.subTest(actual=actual, expected=expected),
                tempfile.TemporaryDirectory() as directory,
            ):
                self.api = FixtureApi()
                page = write_file_page(
                    Path(directory),
                    1,
                    tuple(PullFile(f"docs/{index}.md") for index in range(actual)),
                )
                fetch = FilesFetcher((page,))
                self.api.files_api = GitHubApi(fetch)
                self.api.pulls[23] = replace(self.api.pulls[23], changed_files=expected)
                self.reject("Incomplete GitHub changed-file listing")
                self.assertEqual(fetch.requests, ["/pulls/23/files?per_page=100&page=1"])

    def test_rejects_missing_next_page_after_a_full_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = write_file_page(
                Path(directory), 1, tuple(PullFile(f"docs/{index}.md") for index in range(100))
            )
            fetch = FilesFetcher((page,))
            self.api.files_api = GitHubApi(fetch)
            self.api.pulls[23] = replace(self.api.pulls[23], changed_files=100)
            with self.assertRaisesRegex(OSError, "Missing or unexpected Files API page"):
                admit(self.trigger, self.api, REPOSITORY, 123)
            self.assertEqual(fetch.requests[-1], "/pulls/23/files?per_page=100&page=2")

    def test_rejects_a_repeated_wrong_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = tuple(PullFile(f"docs/{index}.md") for index in range(100))
            root = Path(directory)
            fetch = FilesFetcher((write_file_page(root, 1, files), write_file_page(root, 2, files)))
            self.api.files_api = GitHubApi(fetch)
            self.api.pulls[23] = replace(self.api.pulls[23], changed_files=200)
            self.reject("Duplicate GitHub changed-file entry")
            self.assertEqual(fetch.requests[-1], "/pulls/23/files?per_page=100&page=2")

    def test_file_listing_fetch_failure_never_becomes_success(self) -> None:
        def fetch(path: str) -> str:
            self.assertEqual(path, "/pulls/23/files?per_page=100&page=1")
            raise OSError("Files API unavailable")

        self.api.files_api = GitHubApi(fetch)
        with self.assertRaisesRegex(OSError, "Files API unavailable"):
            admit(self.trigger, self.api, REPOSITORY, 123)
        self.assertEqual(self.api.artifact_requests, [])

    def test_rejects_non_list_and_oversized_files_api_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for response in ("{}", "null", '"not a list"', "1"):
                with self.subTest(response=response):
                    page = root / "invalid-page.json"
                    page.write_text(response, encoding="utf-8")
                    self.api.files_api = GitHubApi(FilesFetcher((page,)))
                    self.reject("Invalid GitHub Files API page")
            page = write_file_page(
                root, 1, tuple(PullFile(f"docs/{index}.md") for index in range(101))
            )
            self.api.files_api = GitHubApi(FilesFetcher((page,)))
            self.reject("Invalid GitHub Files API page")

    def test_rejects_malformed_json_while_listing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "invalid-json.json"
            page.write_text("[", encoding="utf-8")
            self.api.files_api = GitHubApi(FilesFetcher((page,)))
            with self.assertRaises(json.JSONDecodeError):
                admit(self.trigger, self.api, REPOSITORY, 123)

    def test_file_urls_patch_and_link_metadata_cannot_supply_eligibility(self) -> None:
        requests: list[str] = []

        def fetch(path: str) -> str:
            requests.append(path)
            self.assertEqual(path, "/pulls/23/files?per_page=100&page=1")
            return (
                '[{"filename":".github/workflows/preview-website.yml",'
                '"patch":"website/index.html","blob_url":"https://untrusted.invalid/website/a",'
                '"raw_url":"https://untrusted.invalid/docs/a",'
                '"Link":"https://untrusted.invalid/pulls/23/files?page=2"}]'
            )

        self.api.files_api = GitHubApi(fetch)
        self.reject("no website or docs input changes")
        self.assertEqual(requests, ["/pulls/23/files?per_page=100&page=1"])

    def test_rejects_forged_sibling_path_or_workflow_id_in_payload(self) -> None:
        for run in (
            replace(source_run(), path=".github/workflows/forged.yml"),
            replace(source_run(), workflow_id=WORKFLOW_ID + 1),
        ):
            with self.subTest(run=run):
                self.trigger = Trigger(REPO, run)
                self.reject("path or workflow_id")

    def test_rejects_forged_path_or_id_in_live_workflow_registration(self) -> None:
        for identity in ((WORKFLOW_ID, ".github/workflows/sibling.yml"), (1, BUILD_PATH)):
            with self.subTest(identity=identity):
                self.api.identity = identity
                self.reject("Registered workflow")

    def test_rejects_forged_path_or_id_in_live_run(self) -> None:
        for run in (
            replace(source_run(), path=".github/workflows/forged.yml"),
            replace(source_run(), workflow_id=1),
        ):
            with self.subTest(run=run):
                self.api.live = run
                self.reject("path or workflow_id")

    def test_rejects_other_events_in_payload_and_live_responses(self) -> None:
        for event in ("push", "pull_request_target", "workflow_dispatch", "schedule"):
            for location in ("payload", "live", "attempt"):
                with self.subTest(event=event, location=location):
                    self.setUp()
                    run = replace(source_run(), event=event)
                    if location == "payload":
                        self.trigger = Trigger(REPO, run)
                    elif location == "live":
                        self.api.live = run
                    else:
                        self.api.attempt = run
                    self.reject("successful completed pull_request")

    def test_rejects_non_success_or_incomplete_runs(self) -> None:
        for conclusion in ("failure", "cancelled", "timed_out", "skipped", "neutral"):
            with self.subTest(conclusion=conclusion):
                self.trigger = Trigger(REPO, replace(source_run(), conclusion=conclusion))
                self.reject("successful completed pull_request")
        self.trigger = Trigger(REPO, replace(source_run(), status="in_progress"))
        self.reject("successful completed pull_request")

    def test_rejects_repository_or_owner_mismatches(self) -> None:
        for repo in (
            Repository("elsewhere/pluvy", "elsewhere"),
            Repository("sectrend-cn/other", "sectrend-cn"),
            Repository(REPOSITORY, "elsewhere"),
        ):
            with self.subTest(repo=repo):
                self.trigger = Trigger(repo, source_run())
                self.reject("event repository")
                self.trigger = Trigger(REPO, replace(source_run(), repository=repo))
                self.reject("workflow repository")
                self.trigger = Trigger(REPO, replace(source_run(), head_repository=repo))
                self.reject("workflow repository")

    def test_rejects_untrusted_runner_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "event repository"):
            admit(self.trigger, self.api, "elsewhere/pluvy", 123)

    def test_rejects_fork_or_foreign_base(self) -> None:
        foreign = Repository("attacker/pluvy", "attacker")
        for pr in (
            replace(self.api.pulls[23], head_repository=foreign),
            replace(self.api.pulls[23], base_repository=foreign),
        ):
            with self.subTest(pr=pr):
                self.api.pulls[23] = pr
                self.reject("Fork or foreign")

    def test_rejects_closed_or_merged_pr(self) -> None:
        original = self.api.pulls[23]
        for pr in (replace(original, state="closed"), replace(original, merged=True)):
            with self.subTest(pr=pr):
                self.api.pulls[23] = pr
                self.reject("current open PR")

    def test_rejects_stale_head_even_when_event_association_would_match(self) -> None:
        self.api.pulls[23] = replace(self.api.pulls[23], head_sha="c" * 40)
        self.reject("head may be stale")

    def test_rejects_stale_merge_after_base_branch_moves(self) -> None:
        self.api.main = "d" * 40
        self.reject("Stale base or invalid current merge")

    def test_admits_head_api_without_claiming_historical_merge_provenance(self) -> None:
        result = admit(self.trigger, self.api, REPOSITORY, 123)
        self.assertEqual(result.head_sha, self.api.attempt.head_sha)
        self.assertNotEqual(result.head_sha, result.current_merge.sha)
        self.assertEqual(self.api.artifact_requests, [123])

    def test_rejects_head_sha_as_merge_commit(self) -> None:
        self.api.merge_commit = replace(self.api.merge_commit, sha=HEAD)
        self.reject("Stale base or invalid current merge")

    def test_rejects_merge_without_exact_current_base_and_head_parents(self) -> None:
        for parents in ((), (BASE,), (BASE, HEAD, "d" * 40), (HEAD, BASE), (BASE, "d" * 40)):
            with self.subTest(parents=parents):
                self.api.merge_commit = replace(self.api.merge_commit, parents=parents)
                self.reject("Stale base or invalid current merge")

    def test_rejects_current_merge_for_a_different_head(self) -> None:
        self.api.merge_commit = MergeCommit("e" * 40, (BASE, "d" * 40))
        self.reject("Stale base or invalid current merge")

    def test_rejects_unmergeable_or_unknown_pr(self) -> None:
        for mergeable in (False, None):
            with self.subTest(mergeable=mergeable):
                self.api.pulls[23] = replace(self.api.pulls[23], mergeable=mergeable)
                self.reject("not currently mergeable")

    def test_closed_association_with_unknown_mergeability_is_not_selected(self) -> None:
        self.api.pulls[24] = replace(self.api.pulls[23], number=24, state="closed", mergeable=None)
        self.api.associations = (23, 24)
        result = admit(self.trigger, self.api, REPOSITORY, 123)
        self.assertEqual(result.pr_number, 23)
        self.assertEqual(result.head_sha, HEAD)

    def test_moved_current_merge_does_not_relabel_the_head_tree_artifact(self) -> None:
        original = admit(self.trigger, self.api, REPOSITORY, 123)
        self.api.main = "d" * 40
        self.api.merge_commit = MergeCommit("e" * 40, (self.api.main, HEAD))
        current = admit(self.trigger, self.api, REPOSITORY, 123)
        self.assertEqual(current.head_sha, original.head_sha)
        self.assertEqual(current.artifact, original.artifact)
        self.assertNotEqual(current.current_merge, original.current_merge)
        self.assertNotEqual(current.head_sha, current.current_merge.sha)

    def test_rejects_inconsistent_attempt_head(self) -> None:
        self.api.attempt = replace(self.api.attempt, head_sha="c" * 40)
        self.reject("Attempt head SHA disagrees")

    def test_rejects_wrong_run_id_or_attempt(self) -> None:
        with self.assertRaisesRegex(ValueError, "triggering run id"):
            admit(self.trigger, self.api, REPOSITORY, 999)
        for run in (replace(source_run(), id=999), replace(source_run(), run_attempt=1)):
            with self.subTest(run=run):
                self.api.live = run
                self.reject("run id or run attempt")

    def test_rejects_wrong_attempt_identity(self) -> None:
        for run in (replace(self.api.attempt, id=999), replace(self.api.attempt, run_attempt=1)):
            with self.subTest(run=run):
                self.api.attempt = run
                self.reject("run id or run attempt")

    def test_rejects_live_run_head_mismatch(self) -> None:
        self.api.live = replace(self.api.live, head_sha="c" * 40)
        self.reject("Run head SHA disagrees")

    def test_rejects_absent_ambiguous_or_duplicate_pr_associations(self) -> None:
        self.api.pulls[24] = replace(self.api.pulls[23], number=24)
        for numbers in ((), (23, 24), (23, 23)):
            with self.subTest(numbers=numbers):
                self.api.associations = numbers
                self.reject("current open PR|Duplicate PR")

    def test_rejects_non_default_branch_target(self) -> None:
        self.api.pulls[23] = replace(self.api.pulls[23], base_ref="feature")
        self.reject("trusted default branch")

    def test_rejects_wrong_artifact_name_run_or_expiration(self) -> None:
        original = self.api.uploads[0]
        for artifact in (
            replace(original, name="website-preview-123-1"),
            replace(original, name="website-preview-999-2"),
            replace(original, run_id=999),
            replace(original, expired=True),
        ):
            with self.subTest(artifact=artifact):
                self.api.uploads = (artifact,)
                self.reject("Wrong artifact")

    def test_rejects_missing_or_unexpected_artifacts(self) -> None:
        original = self.api.uploads[0]
        for artifacts in ((), (original, replace(original, id=789, name="metadata"))):
            with self.subTest(artifacts=artifacts):
                self.api.uploads = artifacts
                self.reject("Missing or unexpected artifact")

    def test_artifact_metadata_cannot_override_server_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "site.tar"
            forged = (
                b'{"pr_number":23,"head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
                b'"merge_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","workflow_id":415667994,'
                b'"files":["website/index.html"]}'
            )
            with tarfile.open(archive_path, "w") as archive:
                for name, content in (("index.html", b"site"), ("metadata.json", forged)):
                    member = tarfile.TarInfo(name)
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
            prepare_static_upload(archive_path, root / "upload")
            self.assertEqual((root / "upload/metadata.json").read_bytes(), forged)
            self.api.main = "d" * 40
            self.reject("Stale base or invalid current merge")
            self.api.main = BASE
            self.api.pulls[23] = replace(self.api.pulls[23], head_sha="f" * 40)
            self.reject("head may be stale")
            self.api.pulls[23] = replace(self.api.pulls[23], head_sha=HEAD)
            self.api.files = (PullFile(BUILD_PATH),)
            self.reject("no website or docs input changes")


class PreviewApiBoundaryTests(unittest.TestCase):
    """Verify the injectable fetcher and fail-closed response narrowing."""

    def test_fetcher_uses_fixed_workflow_endpoint_and_narrows_identity(self) -> None:
        paths: list[str] = []

        def fetch(path: str) -> str:
            paths.append(path)
            return '{"id":415667994,"path":".github/workflows/preview-website.yml"}'

        self.assertEqual(GitHubApi(fetch).workflow(), (WORKFLOW_ID, BUILD_PATH))
        self.assertEqual(paths, ["/actions/workflows/415667994"])

    def test_file_entry_narrowing_requires_names_and_preserves_rename_absence(self) -> None:
        self.assertEqual(
            PullFile.from_json({"filename": "docs/start.md"}), PullFile("docs/start.md")
        )
        self.assertEqual(
            PullFile.from_json(
                {"filename": "archive/start.md", "previous_filename": "docs/start.md"}
            ),
            PullFile("archive/start.md", "docs/start.md"),
        )
        for response in (
            {},
            {"filename": ""},
            {"filename": 1},
            ["not an entry"],
            {"filename": "docs/start.md", "previous_filename": None},
            {"filename": "docs/start.md", "previous_filename": ""},
            {"filename": "docs/start.md", "previous_filename": 1},
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                PullFile.from_json(response)

    def test_pr_snapshot_ingress_accepts_zero_and_requires_count_and_base_sha(self) -> None:
        def zero_count(path: str) -> str:
            self.assertEqual(path, "/pulls/23")
            return PR_RESPONSE.replace('"changed_files":1', '"changed_files":0')

        pr = GitHubApi(zero_count).pull(23)
        self.assertEqual(pr.changed_files, 0)
        self.assertEqual(pr.base_sha, BASE)
        invalid = (
            PR_RESPONSE.replace('"changed_files":1,', ""),
            PR_RESPONSE.replace('"changed_files":1', '"changed_files":-1'),
            PR_RESPONSE.replace('"changed_files":1', '"changed_files":true'),
            PR_RESPONSE.replace('"changed_files":1', '"changed_files":null'),
            PR_RESPONSE.replace('"changed_files":1', '"changed_files":"1"'),
            PR_RESPONSE.replace('"changed_files":1', '"changed_files":1.5'),
            PR_RESPONSE.replace(f'"sha":"{BASE}",', ""),
            PR_RESPONSE.replace(BASE, "invalid"),
        )
        for response in invalid:
            with self.subTest(response=response):

                def fetch(path: str, response_text: str = response) -> str:
                    self.assertEqual(path, "/pulls/23")
                    return response_text

                with self.assertRaises(ValueError):
                    GitHubApi(fetch).pull(23)

    def test_attempt_api_head_is_not_reinterpreted_as_merge_evidence(self) -> None:
        def fetch(path: str) -> str:
            self.assertEqual(path, "/actions/runs/123/attempts/2")
            return (
                '{"id":123,"run_attempt":2,"workflow_id":415667994,'
                '"path":".github/workflows/preview-website.yml",'
                '"repository":{"full_name":"sectrend-cn/pluvy","owner":{"login":"sectrend-cn"}},'
                '"head_repository":{"full_name":"sectrend-cn/pluvy",'
                '"owner":{"login":"sectrend-cn"}},'
                '"head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
                '"event":"pull_request","status":"completed","conclusion":"success"}'
            )

        attempt = GitHubApi(fetch).run(123, 2)
        self.assertEqual(attempt, source_run())
        self.assertEqual(attempt.head_sha, HEAD)
        self.assertNotEqual(attempt.head_sha, MERGE)

    def test_git_api_resolves_current_base_and_merge_parents_independently(self) -> None:
        responses = {
            "/git/ref/heads/main": (
                '{"ref":"refs/heads/main","object":{"type":"commit",'
                '"sha":"cccccccccccccccccccccccccccccccccccccccc"}}'
            ),
            "/git/ref/pull/23/merge": (
                '{"ref":"refs/pull/23/merge","object":{"type":"commit",'
                '"sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}'
            ),
            f"/git/commits/{MERGE}": (
                '{"sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","parents":['
                '{"sha":"cccccccccccccccccccccccccccccccccccccccc"},'
                '{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}'
            ),
        }
        paths: list[str] = []

        def fetch(path: str) -> str:
            paths.append(path)
            return responses[path]

        api = GitHubApi(fetch)
        self.assertEqual(api.main_sha(), BASE)
        self.assertEqual(api.merge(23), MergeCommit(MERGE, (BASE, HEAD)))
        self.assertEqual(
            paths, ["/git/ref/heads/main", "/git/ref/pull/23/merge", f"/git/commits/{MERGE}"]
        )

    def test_rejects_wrong_ref_or_non_commit_merge_ref(self) -> None:
        for response in (
            '{"ref":"refs/heads/main","object":{"type":"commit","sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}',
            '{"ref":"refs/pull/23/merge","object":{"type":"tree","sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}',
        ):
            with self.subTest(response=response):

                def fetch(path: str, response_text: str = response) -> str:
                    self.assertEqual(path, "/git/ref/pull/23/merge")
                    return response_text

                with self.assertRaisesRegex(ValueError, "Unexpected Git commit ref"):
                    GitHubApi(fetch).merge(23)

    def test_rejects_commit_response_that_does_not_match_merge_ref(self) -> None:
        def fetch(path: str) -> str:
            if path == "/git/ref/pull/23/merge":
                return (
                    '{"ref":"refs/pull/23/merge","object":{"type":"commit",'
                    '"sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}'
                )
            self.assertEqual(path, f"/git/commits/{MERGE}")
            return '{"sha":"dddddddddddddddddddddddddddddddddddddddd","parents":[]}'

        with self.assertRaisesRegex(ValueError, "disagrees with requested ref"):
            GitHubApi(fetch).merge(23)

    def test_rejects_missing_or_malformed_merge_parent_evidence(self) -> None:
        for response in ({}, {"sha": MERGE}, {"sha": MERGE, "parents": [None]}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                MergeCommit.from_json(response)

    def test_missing_merge_ref_is_not_replaced_with_run_head(self) -> None:
        def fetch(path: str) -> str:
            self.assertEqual(path, "/git/ref/pull/23/merge")
            raise FileNotFoundError("Server merge ref unavailable")

        with self.assertRaises(FileNotFoundError):
            GitHubApi(fetch).merge(23)

    def test_api_unknown_mergeability_is_preserved_and_rejected_for_current_pr(self) -> None:
        def fetch(path: str) -> str:
            self.assertEqual(path, "/pulls/23")
            return PR_RESPONSE.replace('"mergeable":true', '"mergeable":null')

        pr = GitHubApi(fetch).pull(23)
        self.assertIsNone(pr.mergeable)
        self.assertEqual(pr.changed_files, 1)
        self.assertEqual(pr.base_sha, BASE)
        api = FixtureApi()
        api.pulls[23] = pr
        with self.assertRaisesRegex(ValueError, "not currently mergeable"):
            admit(Trigger(REPO, source_run()), api, REPOSITORY, 123)

    def test_rejects_missing_artifact_api_metadata(self) -> None:
        for response in (
            '{"total_count":0,"artifacts":[]}',
            '{"total_count":1,"artifacts":[{}]}',
            '{"total_count":2,"artifacts":[{},{}]}',
        ):
            with self.subTest(response=response):

                def fetch(path: str, response_text: str = response) -> str:
                    self.assertEqual(path, "/actions/runs/123/artifacts?per_page=100")
                    return response_text

                with self.assertRaises(ValueError):
                    GitHubApi(fetch).artifacts(123)

    def test_api_failures_never_become_admission_success(self) -> None:
        def fetch(path: str) -> str:
            raise OSError(f"Unavailable API: {path}")

        with self.assertRaises(OSError):
            admit(Trigger(REPO, source_run()), GitHubApi(fetch), REPOSITORY, 123)

    def test_payload_rejects_missing_or_invalid_required_fields(self) -> None:
        for response in ("{}", '{"id":true}', '{"action":"requested"}'):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as directory:
                event = Path(directory) / "event.json"
                event.write_text(response)
                with self.assertRaises(ValueError):
                    Trigger.read(event)


if __name__ == "__main__":
    unittest.main()
