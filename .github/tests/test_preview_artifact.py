"""Exercise the actual inline upload validator without credentials or deployment."""

import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / "workflows" / "preview-website.yml"
MATCH = re.search(r"          python3 -I - <<'PY'\n(.*?)          PY\n", WORKFLOW.read_text(), re.S)
if MATCH is None:
    raise RuntimeError("The workflow must contain its inline static upload validator")
VALIDATOR = textwrap.dedent(MATCH.group(1))


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
        [sys.executable, "-I", "-c", VALIDATOR],
        env={"RUNNER_TEMP": str(root)},
        capture_output=True,
        text=True,
        check=False,
    )


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

    def test_upload_skips_missing_credentials_without_starting_wrangler(self) -> None:
        workflow = WORKFLOW.read_text()
        upload = workflow.split("      - name: Upload only to the dedicated PR branch", 1)[1]
        script = textwrap.dedent(upload.split("        run: |\n", 1)[1])
        result = subprocess.run(
            ["/bin/bash", "-c", script],
            env={"PATH": os.defpath, "CLOUDFLARE_API_TOKEN": "", "CLOUDFLARE_ACCOUNT_ID": ""},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipping upload", result.stdout)


if __name__ == "__main__":
    unittest.main()
