"""Exercise the shared upload validator without credentials or deployment."""

import io
import os
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preview_publish import prepare_static_upload

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
WORKFLOW = Path(__file__).parents[1] / "workflows" / "preview-website-publish.yml"


def file_member(name: str) -> tarfile.TarInfo:
    """Declare one inert HTML fixture using the canonical archive contract."""
    member = tarfile.TarInfo(name)
    member.size = len(b"<h1>preview</h1>")
    return member


def validate(root: Path, members: list[tarfile.TarInfo]) -> subprocess.CompletedProcess[str]:
    """Run the workflow's validator against an isolated, adversarial tar fixture."""
    incoming = root / "preview-incoming"
    incoming.mkdir()
    with tarfile.open(incoming / "website-preview.tar", "w") as archive:
        for member in members:
            archive.addfile(member, io.BytesIO(b"<h1>preview</h1>"))
    return run_validator(root)


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    """Keep validation subprocesses isolated from the caller's environment."""
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPTS / "preview_publish.py"), "prepare"],
        env={"RUNNER_TEMP": str(root)},
        capture_output=True,
        text=True,
        check=False,
    )


def upload_script() -> str:
    """Exercise the final trusted shell step without invoking a live uploader."""
    upload = WORKFLOW.read_text().split(
        "      - name: Upload only to the dedicated verified PR branch", 1
    )[1]
    return textwrap.dedent(upload.split("        run: |\n", 1)[1])


class PreviewArtifactTests(unittest.TestCase):
    """Prove that untrusted output stays static and cannot supply Pages configuration."""

    def test_static_files_and_trusted_noindex_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_root = tarfile.TarInfo("./")
            archive_root.type = tarfile.DIRTYPE
            assets = tarfile.TarInfo("./_astro/")
            assets.type = tarfile.DIRTYPE
            result = validate(
                root,
                [
                    archive_root,
                    assets,
                    file_member("./index.html"),
                    file_member("./_astro/client.js"),
                    tarfile.TarInfo("./.nojekyll"),
                ],
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (root / "preview-upload/_astro/client.js").read_bytes(), b"<h1>preview</h1>"
            )
            self.assertEqual(
                (root / "preview-upload/_headers").read_text(),
                "/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n",
            )
            self.assertFalse((root / "preview-upload/.nojekyll").exists())

    def test_rejects_traversal_and_pages_execution_inputs(self) -> None:
        names = [
            "../escape.html",
            "/absolute.html",
            "a/../../escape.html",
            "a//b.html",
            "a/./b.html",
            "a\\b.html",
            "caf\u00e9.html",
            "a\nb.html",
            "_worker.js",
            "_worker.js/index.js",
            "_routes.json",
            "_headers",
            "_redirects",
            "functions/api.js",
            "a/functions/api.js",
            "_FUNCTIONS/api.js",
            "_WORKER.JS",
            ".env",
            ".nojekyll",
            "a/.nojekyll",
            "a" * 1025,
            ".wrangler/state",
            "a/.npmrc",
            "wrangler.toml",
            "wrangler.json",
            "wrangler.jsonc",
            "package.json",
            "node_modules/a.js",
            "a;touch pwned.html",
            "$(touch pwned).html",
        ]
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                result = validate(root, [file_member("index.html"), file_member(name)])
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "preview-upload/_headers").exists())
                self.assertFalse((root / "escape.html").exists())

    def test_rejects_links_and_special_files(self) -> None:
        for kind in (
            tarfile.SYMTYPE,
            tarfile.LNKTYPE,
            tarfile.FIFOTYPE,
            tarfile.CHRTYPE,
            tarfile.BLKTYPE,
            tarfile.CONTTYPE,
            tarfile.GNUTYPE_SPARSE,
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                member = tarfile.TarInfo("asset")
                member.type = kind
                member.linkname = "/etc/passwd"
                result = validate(Path(directory), [file_member("index.html"), member])
                self.assertNotEqual(result.returncode, 0)

    def test_rejects_duplicate_case_collisions_and_missing_index(self) -> None:
        fixtures = [
            [file_member("index.html"), file_member("index.html")],
            [file_member("index.html"), file_member("INDEX.HTML")],
            [file_member("other.html")],
        ]
        for members in fixtures:
            with (
                self.subTest(names=[member.name for member in members]),
                tempfile.TemporaryDirectory() as directory,
            ):
                result = validate(Path(directory), members)
                self.assertNotEqual(result.returncode, 0)

    def test_rejects_an_oversized_member_before_reading_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "preview-incoming"
            incoming.mkdir()
            member = file_member("index.html")
            member.size = 25 * 1024 * 1024 + 1
            (incoming / "website-preview.tar").write_bytes(member.tobuf() + bytes(1024))
            result = run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("size limit exceeded", result.stderr)

    def test_rejects_missing_linked_and_oversized_archives(self) -> None:
        for kind in ("missing", "symlink", "directory", "oversized"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                incoming = root / "preview-incoming"
                incoming.mkdir()
                archive = incoming / "website-preview.tar"
                if kind == "symlink":
                    archive.symlink_to(root / "absent")
                elif kind == "directory":
                    archive.mkdir()
                elif kind == "oversized":
                    with archive.open("wb") as output:
                        output.truncate(256 * 1024 * 1024 + 1)
                result = run_validator(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "preview-upload").exists())

    def test_shared_validator_requires_a_fresh_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = validate(root, [file_member("index.html")])
            self.assertEqual(result.returncode, 0, result.stderr)
            with self.assertRaises(FileExistsError):
                prepare_static_upload(
                    root / "preview-incoming/website-preview.tar", root / "preview-upload"
                )

    def test_rejects_duplicate_inert_markers_and_malformed_directories(self) -> None:
        root_member = tarfile.TarInfo("./")
        root_member.type = tarfile.DIRTYPE
        malformed = tarfile.TarInfo("assets//nested/")
        malformed.type = tarfile.DIRTYPE
        for members in (
            [root_member, root_member],
            [tarfile.TarInfo(".nojekyll"), tarfile.TarInfo("./.nojekyll")],
            [malformed],
        ):
            with self.subTest(members=members), tempfile.TemporaryDirectory() as directory:
                result = validate(Path(directory), [file_member("index.html"), *members])
                self.assertNotEqual(result.returncode, 0)

    def test_rejects_excessive_entry_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            members = [file_member("index.html")]
            for number in range(20000):
                member = tarfile.TarInfo(f"directory-{number}")
                member.type = tarfile.DIRTYPE
                members.append(member)
            result = validate(Path(directory), members)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Too many entries", result.stderr)

    def test_rejects_unexpected_outer_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = validate(root, [file_member("index.html")])
            self.assertEqual(result.returncode, 0, result.stderr)
            (root / "preview-incoming/metadata.json").write_text('{"pr_number":999}')
            result = run_validator(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unexpected incoming artifact files", result.stderr)

    def test_rejects_compressed_or_corrupt_archives(self) -> None:
        for kind in ("gzip", "corrupt"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                incoming = root / "preview-incoming"
                incoming.mkdir()
                archive_path = incoming / "website-preview.tar"
                if kind == "gzip":
                    with tarfile.open(archive_path, "w:gz") as archive:
                        archive.addfile(file_member("index.html"), io.BytesIO(b"<h1>preview</h1>"))
                else:
                    archive_path.write_bytes(b"corrupt tar")
                result = run_validator(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "preview-upload/_headers").exists())

    def test_upload_rejects_missing_credentials_without_starting_wrangler(self) -> None:
        for token, account in (("", ""), ("test-only", ""), ("", "test-only")):
            with self.subTest(token_missing=not token, account_missing=not account):
                result = subprocess.run(
                    ["/bin/bash", "-c", upload_script()],
                    env={
                        "PATH": os.defpath,
                        "CLOUDFLARE_API_TOKEN": token,
                        "CLOUDFLARE_ACCOUNT_ID": account,
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("credentials are unavailable", result.stdout)
                self.assertEqual(result.stderr, "")

    def test_upload_branch_guard_and_fixed_project_with_inert_node_stand_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            node = root / "node"
            node.write_text('#!/bin/sh\nprintf "%s " "$@"\nprintf "\\n"\n', encoding="utf-8")
            node.chmod(0o755)
            environment = {
                "PATH": f"{root}:{os.defpath}",
                "RUNNER_TEMP": str(root),
                "CLOUDFLARE_API_TOKEN": "test-only",
                "CLOUDFLARE_ACCOUNT_ID": "test-only",
            }
            for number in ("", "0", "-1", "01", "main", "23;exit 0", "23\n", "23"):
                with self.subTest(number=number):
                    result = subprocess.run(
                        ["/bin/bash", "-c", upload_script()],
                        env={**environment, "PR_NUMBER": number},
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.stderr, "")
                    if number == "23":
                        self.assertEqual(result.returncode, 0)
                        self.assertIn("--project-name pluvy-preview --branch pr-23", result.stdout)
                        self.assertIn(f"pages deploy {root}/preview-upload", result.stdout)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
