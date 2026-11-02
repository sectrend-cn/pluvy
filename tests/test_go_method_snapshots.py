"""Go method usage is rebuilt from the selected full, changed or index snapshots."""

import subprocess
from pathlib import Path

import pytest

from pluvy.cli import main
from pluvy.diagnostics import Report

_TYPES = (
    "package main\n\n"
    "func main() { _ = makeItems() }\n\n"
    "type item struct{}\n\n"
    "func makeItems() []item { return []item{{}} }\n"
)
_CALLED = _TYPES.replace("_ = makeItems()", "makeItems()[0].render()")
_UNUSED = _TYPES.replace("_ = makeItems()", "_ = makeItems()[0]")
_METHOD = "package main\n\nfunc (value item) render() { println(&value) }\n"
_SAME_NAME_TYPES = (
    "package main\n\n"
    "type alpha struct{}\n\ntype beta struct{}\n\n"
    "func main() {\n\t_ = alpha{}\n\t_ = beta{}\n}\n"
)
_SAME_NAME_METHODS = (
    "package main\n\n"
    "func (a alpha) render() { println(&a) }\n\n"
    "func (b beta) render() { println(&b) }\n"
)


def _git(root: Path, *arguments: str) -> None:
    result = subprocess.run(
        ("git", "-C", str(root), *arguments), capture_output=True, text=True, check=True
    )
    assert result.returncode == 0


def _repository(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a git repository whose initial commit holds the given Go files."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "gate@example.invalid")
    _git(tmp_path, "config", "user.name", "Gate Test")
    (tmp_path / ".pluvy").mkdir()
    (tmp_path / ".pluvy/pluvy.json").write_text("{}\n")
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "initial Go package")
    return tmp_path


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    return _repository(tmp_path, {"types.go": _TYPES, "methods.go": "package main\n"})


@pytest.fixture
def same_name_repository(tmp_path: Path) -> Path:
    return _repository(tmp_path, {"types.go": _SAME_NAME_TYPES, "methods.go": "package main\n"})


def _revise(root: Path, types: str) -> None:
    (root / "types.go").write_text(types)
    (root / "methods.go").write_text(_METHOD)
    _git(root, "add", "types.go", "methods.go")


@pytest.mark.parametrize("mode", [("--all",), ("--base", "HEAD"), ("--staged",)])
def test_chained_method_call_is_not_reported_in_every_snapshot_mode(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    mode: tuple[str, ...],
) -> None:
    """A chained call keeps its method unreported through name-based conservative suppression."""
    _revise(repository, _CALLED)
    assert main(["--root", str(repository), *mode, "--format", "json"]) == 0
    assert Report.model_validate_json(capsys.readouterr().out).findings == ()


@pytest.mark.parametrize("mode", [("--all",), ("--base", "HEAD"), ("--staged",)])
def test_unused_method_across_files_is_reported_once_in_every_snapshot_mode(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    mode: tuple[str, ...],
) -> None:
    _revise(repository, _UNUSED)
    assert main(["--root", str(repository), *mode, "--format", "json"]) == 1
    report = Report.model_validate_json(capsys.readouterr().out)
    assert [(f.path, f.line, f.column, f.rule) for f in report.findings] == [
        ("methods.go", 3, 19, "unused.function")
    ]


@pytest.mark.parametrize("mode", [("--all",), ("--base", "HEAD"), ("--staged",)])
def test_same_name_methods_report_each_declaration_in_every_snapshot_mode(
    same_name_repository: Path,
    capsys: pytest.CaptureFixture[str],
    mode: tuple[str, ...],
) -> None:
    (same_name_repository / "methods.go").write_text(_SAME_NAME_METHODS)
    _git(same_name_repository, "add", "methods.go")
    assert main(["--root", str(same_name_repository), *mode, "--format", "json"]) == 1
    report = Report.model_validate_json(capsys.readouterr().out)
    assert [(f.path, f.line, f.column, f.rule) for f in report.findings] == [
        ("methods.go", 3, 16, "unused.function"),
        ("methods.go", 5, 15, "unused.function"),
    ]
