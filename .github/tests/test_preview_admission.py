"""Exercise admission with concrete API contracts and adversarial live state."""

from __future__ import annotations

import io
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


def source_run() -> Run:
    """Declare server-owned run facts independently of any archive."""
    return Run(
        123, 2, WORKFLOW_ID, BUILD_PATH, REPO, REPO, HEAD, "pull_request", "completed", "success"
    )


class FixtureApi:
    """Keep requested build head and current merge-parent evidence independent."""

    def __init__(self) -> None:
        self.identity = (WORKFLOW_ID, BUILD_PATH)
        self.live = source_run()
        self.attempt = self.live
        self.pulls = {23: PullRequest(23, "open", False, REPO, REPO, HEAD, "main", True)}
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
        return self.pulls[number]

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
                b'"merge_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","workflow_id":415667994}'
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


class PreviewApiBoundaryTests(unittest.TestCase):
    """Verify the injectable fetcher and fail-closed response narrowing."""

    def test_fetcher_uses_fixed_workflow_endpoint_and_narrows_identity(self) -> None:
        paths: list[str] = []

        def fetch(path: str) -> str:
            paths.append(path)
            return '{"id":415667994,"path":".github/workflows/preview-website.yml"}'

        self.assertEqual(GitHubApi(fetch).workflow(), (WORKFLOW_ID, BUILD_PATH))
        self.assertEqual(paths, ["/actions/workflows/415667994"])

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
            return (
                '{"number":23,"state":"open","merged":false,"mergeable":null,'
                '"head":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
                '"repo":{"full_name":"sectrend-cn/pluvy","owner":{"login":"sectrend-cn"}}},'
                '"base":{"ref":"main","repo":{"full_name":"sectrend-cn/pluvy",'
                '"owner":{"login":"sectrend-cn"}}}}'
            )

        pr = GitHubApi(fetch).pull(23)
        self.assertIsNone(pr.mergeable)
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
