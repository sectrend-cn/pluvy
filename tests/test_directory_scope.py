"""Verify directory symlinks are rejected only while policy scope may still select them."""

import os
import subprocess
from pathlib import Path

import pytest

from pluvy.cli import main
from pluvy.engine import registry
from pluvy.models import Policy, Report
from pluvy.policy import paths
from pluvy.snapshots import _disk_paths


def _git(root: Path, *arguments: str) -> str:
    """Run one fixture Git command and return its standard output."""
    return subprocess.run(
        ("git", "-C", str(root), *arguments), check=True, capture_output=True, text=True
    ).stdout


def _write(root: Path, relative: str, content: str) -> None:
    """Create one fixture file together with its parent directories."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _link(root: Path, relative: str, target: str) -> None:
    """Create one directory symlink pointing at an absolute fixture path."""
    link = root / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(root / target, target_is_directory=True)


def _policy(root: Path, text: str) -> None:
    """Replace the fixture policy with one JSON document."""
    _write(root, ".pluvy/pluvy.json", f"{text}\n")


def _summary(output: str) -> str:
    """Return the final non-empty line of a text report."""
    return output.strip().splitlines()[-1]


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Provide a committed repository whose policy selects only ``src/*``."""
    assert _git(tmp_path, "init", "-q") == ""
    assert _git(tmp_path, "config", "user.email", "gate@example.invalid") == ""
    assert _git(tmp_path, "config", "user.name", "Gate Test") == ""
    _policy(tmp_path, '{"include": ["src/*"]}')
    _write(tmp_path, "src/app.py", "def run() -> int:\n    return 1\n")
    assert _git(tmp_path, "add", ".pluvy/pluvy.json", "src/app.py") == ""
    assert _git(tmp_path, "commit", "-qm", "fixture") == ""
    return tmp_path


def test_all_mode_skips_symlink_without_selectable_content(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repository, "testdata/other/file.txt", "fixture\n")
    _link(repository, "testdata/fixtures/link", "testdata/other")

    assert main(["--root", str(repository), "--all"]) == 0
    captured = capsys.readouterr()
    assert _summary(captured.out) == "Architecture all: 1 files; 0 findings."
    assert captured.err == ""


def test_base_mode_usage_evidence_skips_out_of_scope_symlink(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repository, "testdata/other/file.txt", "fixture\n")
    _link(repository, "testdata/fixtures/link", "testdata/other")
    _write(repository, "src/app.py", "def run() -> int:\n    return 2\n")

    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    captured = capsys.readouterr()
    assert "Refusing to traverse symlink directory" not in captured.err
    assert Report.model_validate_json(captured.out).files == 1


def test_empty_scope_reports_missing_sources_instead_of_symlinks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(tmp_path, '{"include": ["src/*"]}')
    _write(tmp_path, "testdata/other/file.txt", "fixture\n")
    _link(tmp_path, "testdata/fixtures/link", "testdata/other")

    assert main(["--root", str(tmp_path), "--all"]) == 2
    captured = capsys.readouterr()
    assert "No supported source files selected" in captured.err
    assert "Refusing to traverse symlink directory" not in captured.err


def test_excluded_subtree_never_enters_symlink_directories(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(repository, '{"include": ["src/*"], "exclude": ["src/vendor/*"]}')
    _write(repository, "outside/dep.py", "def dep() -> int:\n    return 1\n")
    _link(repository, "src/vendor/link", "outside")
    _link(repository, "src/vendor/deep/link", "outside")

    assert main(["--root", str(repository), "--all"]) == 0
    assert _summary(capsys.readouterr().out) == "Architecture all: 1 files; 0 findings."


def test_pruned_locked_directory_is_never_enumerated(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if os.name == "nt":
        pytest.skip("POSIX directory permissions are unavailable on Windows")
    if os.geteuid() == 0:
        pytest.skip("A privileged user can enumerate permission-denied directories")
    locked = repository / "testdata/fixtures/locked"
    locked.mkdir(parents=True)
    locked.chmod(0o000)
    try:
        assert main(["--root", str(repository), "--all"]) == 0
    finally:
        locked.chmod(0o700)
    assert _summary(capsys.readouterr().out) == "Architecture all: 1 files; 0 findings."


def test_dangling_symlink_outside_scope_is_not_an_error(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _link(repository, "testdata/fixtures/link", "missing")

    assert main(["--root", str(repository), "--all"]) == 0
    assert _summary(capsys.readouterr().out) == "Architecture all: 1 files; 0 findings."


def test_staged_mode_ignores_in_scope_symlink_directory(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/link", "outside")
    _write(repository, "src/app.py", "def run() -> int:\n    return 2\n")
    assert _git(repository, "add", "src/app.py") == ""

    assert main(["--root", str(repository), "--staged"]) == 0
    assert _summary(capsys.readouterr().out) == "Architecture staged: 1 files; 0 findings."


def test_all_mode_still_rejects_symlink_inside_scope(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/link", "outside")

    assert main(["--root", str(repository), "--all"]) == 2
    captured = capsys.readouterr()
    assert "Refusing to traverse symlink directory" in captured.err
    assert "Architecture all:" not in captured.out


def test_base_mode_still_rejects_symlink_inside_scope(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/link", "outside")
    _write(repository, "src/app.py", "def run() -> int:\n    return 2\n")

    assert main(["--root", str(repository), "--base", "HEAD"]) == 2
    captured = capsys.readouterr()
    assert "Refusing to traverse symlink directory" in captured.err
    assert "Architecture base:" not in captured.out


@pytest.mark.parametrize("policy_text", ['{"include": ["*.py"]}', "{}"])
def test_global_include_patterns_still_reject_in_scope_symlinks(
    repository: Path, capsys: pytest.CaptureFixture[str], policy_text: str
) -> None:
    _policy(repository, policy_text)
    _write(repository, "testdata/other/file.txt", "fixture\n")
    _link(repository, "testdata/fixtures/link", "testdata/other")

    assert main(["--root", str(repository), "--all"]) == 2
    captured = capsys.readouterr()
    assert "Refusing to traverse symlink directory" in captured.err
    assert "Architecture all:" not in captured.out


def test_nested_symlink_inside_include_scope_is_rejected(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(repository, '{"include": ["src/*.py"]}')
    _write(repository, "src/sub/x.py", "def x() -> int:\n    return 1\n")
    _write(repository, "outside/y.py", "def y() -> int:\n    return 1\n")
    _link(repository, "src/sub/link", "outside")

    assert main(["--root", str(repository), "--all"]) == 2
    captured = capsys.readouterr()
    assert "Refusing to traverse symlink directory" in captured.err
    assert "Architecture all:" not in captured.out


_WALK_TREE = (
    "src/app.py",
    "src/sub/mod.py",
    "src/notes.txt",
    "tests/test_x.py",
    "tools/script.py",
    "docs/guide.md",
    "node_modules/dep/index.js",
    ".venv/lib/site.py",
    "vendor/lib.py",
)

_WALK_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "{}",
        ("src/app.py", "src/sub/mod.py", "tests/test_x.py", "tools/script.py", "vendor/lib.py"),
    ),
    ('{"include": ["src/*"]}', ("src/app.py", "src/sub/mod.py")),
    (
        '{"include": ["src/*", "tests/*"], "exclude": ["src/sub/*"]}',
        ("src/app.py", "tests/test_x.py"),
    ),
    (
        '{"include": ["*.py"]}',
        ("src/app.py", "src/sub/mod.py", "tests/test_x.py", "tools/script.py", "vendor/lib.py"),
    ),
    ('{"include": ["src/**"]}', ("src/app.py", "src/sub/mod.py")),
)


@pytest.mark.parametrize(("policy_text", "expected"), _WALK_CASES)
def test_directory_pruning_preserves_selected_file_sets(
    tmp_path: Path, policy_text: str, expected: tuple[str, ...]
) -> None:
    for relative in _WALK_TREE:
        _write(tmp_path, relative, "value = 1\n")
    policy = Policy.model_validate_json(policy_text)

    assert _disk_paths(tmp_path, policy, registry()) == expected


_PRUNE_CASES: tuple[tuple[str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("testdata/fixtures", ("src/*",), (), True),
    ("src", ("src/*",), (), False),
    ("src/sub", ("src/*",), (), False),
    ("src/vendor", ("src/*",), ("src/vendor/*",), True),
    ("src/vendor/nested", ("src/*",), ("src/vendor/*",), True),
    ("src/vendor", ("src/*",), ("src/vendor/**",), True),
    ("anywhere", ("**",), (), False),
    ("anywhere", ("*.py",), (), False),
    ("docs", ("src/*.py",), (), True),
    ("src/sub", ("src/*.py",), (), False),
    ("s", ("src/*",), (), True),
    ("srcx", ("src/*",), (), True),
    ("Src", ("src/*",), (), True),
    ("src", ("src",), (), True),
    ("src", ("src/",), (), True),
    ("src", ("src/app.py",), (), False),
    ("vendor", ("src/vendor/x.js",), (), True),
    ("src", (), (), True),
    ("src", ("?rc/*",), (), False),
    ("src/vendor", ("src/*",), ("src/*/*",), False),
    ("docs", ("src/[v]endor/*",), (), True),
    ("src/vendor", ("src/[v]endor/*",), (), False),
    ("src/vendor", ("src/*",), ("src/[v]endor/*",), False),
)


@pytest.mark.parametrize(("directory", "include", "exclude", "expected"), _PRUNE_CASES)
def test_prunable_follows_declared_scope_contract(
    directory: str, include: tuple[str, ...], exclude: tuple[str, ...], expected: bool
) -> None:
    assert paths.prunable(directory, include, exclude) is expected


def test_excluded_symlink_entry_is_pruned_before_rejection(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(repository, '{"include": ["src/*"], "exclude": ["src/vendor/*"]}')
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/vendor", "outside")

    assert main(["--root", str(repository), "--all"]) == 0
    assert _summary(capsys.readouterr().out) == "Architecture all: 1 files; 0 findings."

    _write(repository, "src/app.py", "def run() -> int:\n    return 2\n")
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    report = Report.model_validate_json(capsys.readouterr().out)
    assert report.files == 1
    assert report.usage_files == 1


def test_root_symlink_outside_include_scope_is_pruned(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "vendor", "outside")

    assert main(["--root", str(repository), "--all"]) == 0
    assert _summary(capsys.readouterr().out) == "Architecture all: 1 files; 0 findings."

    _write(repository, "src/app.py", "def run() -> int:\n    return 2\n")
    assert main(["--root", str(repository), "--base", "HEAD"]) == 0
    captured = capsys.readouterr()
    assert _summary(captured.out) == "Architecture base: 1 files; 0 findings."
    assert "Refusing to traverse symlink directory" not in captured.err


def test_environment_named_symlink_stays_skipped(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/node_modules", "outside")

    assert main(["--root", str(repository), "--all"]) == 0
    assert _summary(capsys.readouterr().out) == "Architecture all: 1 files; 0 findings."


def test_exclude_without_covering_prefix_keeps_symlink_rejected(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(repository, '{"include": ["src/*"], "exclude": ["src/vendor"]}')
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/vendor", "outside")

    assert main(["--root", str(repository), "--all"]) == 2
    captured = capsys.readouterr()
    assert "Refusing to traverse symlink directory" in captured.err
    assert "Architecture all:" not in captured.out


def test_global_exclusion_reports_empty_scope_instead_of_symlinks(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(repository, '{"include": ["src/*"], "exclude": ["**"]}')
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/link", "outside")

    assert main(["--root", str(repository), "--all"]) == 2
    captured = capsys.readouterr()
    assert "No supported source files selected" in captured.err
    assert "Refusing to traverse symlink directory" not in captured.err


def test_source_named_symlink_is_pruned_for_walk_but_rejected_on_read(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(repository, '{"include": ["src/*"], "exclude": ["src/link.py/*"]}')
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/link.py", "outside")

    assert main(["--root", str(repository), "--all"]) == 0
    assert _summary(capsys.readouterr().out) == "Architecture all: 1 files; 0 findings."

    _write(repository, "src/app.py", "def run() -> int:\n    return 2\n")
    assert main(["--root", str(repository), "--base", "HEAD"]) == 2
    assert "Refusing source/config symlink" in capsys.readouterr().err


_USAGE_RULES_DISABLED = (
    '{"include": ["src/*"], "checkers": {'
    '"unused.parameter": {"enabled": false}, '
    '"unused.function": {"enabled": false}, '
    '"unused.field": {"enabled": false}, '
    '"unused.return": {"enabled": false}}}'
)


def test_base_skips_usage_walk_when_every_usage_rule_is_disabled(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _policy(repository, _USAGE_RULES_DISABLED)
    _write(repository, "outside/x.py", "def x() -> int:\n    return 1\n")
    _link(repository, "src/link", "outside")
    _write(repository, "src/app.py", "def run() -> int:\n    return 2\n")

    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    report = Report.model_validate_json(capsys.readouterr().out)
    assert report.files == 1
    assert report.usage_files == 0

    assert main(["--root", str(repository), "--all"]) == 2
    assert "Refusing to traverse symlink directory" in capsys.readouterr().err


_SPECIAL_NAME_TREE = (
    "a*b/x.py",
    "a*c/x.py",
    "x?y/x.py",
    "xzy/x.py",
    "[old]/x.py",
    "o/x.py",
    "l/x.py",
    "d/x.py",
    "src/app.py",
)

_SPECIAL_NAME_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('{"include": ["a*c/*"]}', ("a*c/x.py",)),
    ('{"include": ["a*b/*"]}', ("a*b/x.py",)),
    ('{"include": ["x?y/*"]}', ("x?y/x.py", "xzy/x.py")),
    ('{"include": ["[old]/*"]}', ("d/x.py", "l/x.py", "o/x.py")),
    (
        '{"include": ["**"]}',
        (
            "[old]/x.py",
            "a*b/x.py",
            "a*c/x.py",
            "d/x.py",
            "l/x.py",
            "o/x.py",
            "src/app.py",
            "x?y/x.py",
            "xzy/x.py",
        ),
    ),
    ('{"include": ["src/*"]}', ("src/app.py",)),
)


@pytest.mark.parametrize(("policy_text", "expected"), _SPECIAL_NAME_CASES)
def test_fnmatch_special_directory_names_keep_the_selected_set(
    tmp_path: Path, policy_text: str, expected: tuple[str, ...]
) -> None:
    if os.name == "nt":
        pytest.skip("Windows forbids wildcard characters in directory names")
    for relative in _SPECIAL_NAME_TREE:
        _write(tmp_path, relative, "value = 1\n")
    policy = Policy.model_validate_json(policy_text)

    assert _disk_paths(tmp_path, policy, registry()) == expected
