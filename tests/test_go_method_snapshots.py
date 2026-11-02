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


def _git(root: Path, *arguments: str) -> None:
    result = subprocess.run(
        ("git", "-C", str(root), *arguments), capture_output=True, text=True, check=True
    )
    assert result.returncode == 0


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "gate@example.invalid")
    _git(tmp_path, "config", "user.name", "Gate Test")
    (tmp_path / ".pluvy").mkdir()
    (tmp_path / ".pluvy/pluvy.json").write_text("{}\n")
    (tmp_path / "types.go").write_text(_TYPES)
    (tmp_path / "methods.go").write_text("package main\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "initial Go package")
    return tmp_path


def _revise(root: Path, types: str) -> None:
    (root / "types.go").write_text(types)
    (root / "methods.go").write_text(_METHOD)
    _git(root, "add", "types.go", "methods.go")


@pytest.mark.parametrize("mode", [("--all",), ("--base", "HEAD"), ("--staged",)])
def test_called_method_usage_across_files_in_every_snapshot_mode(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    mode: tuple[str, ...],
) -> None:
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
