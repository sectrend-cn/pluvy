"""Verify deletion evidence, run-level activation and baseline assertion erosion."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from pluvy.analysis.context import TreeContext
from pluvy.cli import main
from pluvy.diagnostics import GateError, ParseWarning, Report, SyntaxFailure
from pluvy.languages.javascript.test_syntax import JavaScriptTestSyntax
from pluvy.languages.python.test_syntax import PythonTestSyntax
from pluvy.plugins.builtins import (
    builtin_deletion_gate,
    builtin_languages,
    builtin_registry,
)
from pluvy.policy.models import Policy
from pluvy.semantics.testing.contracts import TestBinding as _TestBinding
from pluvy.semantics.testing.gate import TestDeletionGate as _TestDeletionGate
from pluvy.snapshots import (
    Selection,
    baseline_sources,
    changed_paths,
    deleted_sources,
)
from pluvy.snapshots import (
    git as snapshot_git,
)
from pluvy.source import Language, Source

_TEST_BODY = (
    "def test_alpha() -> None:\n"
    "    assert value(1) == 1\n"
    "\n"
    "def test_beta() -> None:\n"
    "    assert value(2) == 2\n"
    "\n"
    "def value(item: int) -> int:\n"
    "    return item\n"
)


class _RejectingParser:
    """Reject a tree with explicit parser evidence for SyntaxFailure paths."""

    def parse(self, source: Source, policy: Policy) -> TreeContext:
        raise SyntaxFailure(
            (
                ParseWarning(
                    path=source.path,
                    line=1,
                    column=1,
                    message=f"rejected under policy version {policy.version}",
                ),
            )
        )


@dataclass(frozen=True)
class _Bindings:
    """Resolve a test binding in unit probes without application composition."""

    bindings: dict[Language, _TestBinding]

    def binding_for(self, language: Language) -> _TestBinding | None:
        return self.bindings.get(language)


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(("git", "-C", str(root), *arguments), check=True, capture_output=True, text=True)


def _git_output(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(root), *arguments), check=True, capture_output=True, text=True
    ).stdout


def _commit(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message)


def _report(capsys: pytest.CaptureFixture[str]) -> Report:
    return Report.model_validate_json(capsys.readouterr().out)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "gate@example.invalid")
    _git(tmp_path, "config", "user.name", "Gate Test")
    (tmp_path / ".pluvy").mkdir()
    (tmp_path / ".pluvy/pluvy.json").write_text("{}\n")
    (tmp_path / "app.py").write_text("def run() -> int:\n    return 1\n")
    (tmp_path / "test_sample.py").write_text(_TEST_BODY)
    _commit(tmp_path, "fixture")
    return tmp_path


def test_deleted_file_error_reports_baseline_counts(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "test_sample.py").unlink()
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    report = _report(capsys)
    assert [(finding.rule, finding.severity, finding.scope) for finding in report.findings] == [
        ("test.deletion", "error", "file")
    ]
    finding = report.findings[0]
    assert finding.path == "test_sample.py"
    assert (finding.line, finding.column) == (1, 1)
    assert "2 test declaration(s)" in finding.message
    assert "2 assertion(s)" in finding.message
    assert report.files == 0


def test_deleted_non_test_file_is_not_reported(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "app.py").unlink()
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    assert _report(capsys).findings == ()


def test_exact_rename_is_not_reported(repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(repository, "mv", "test_sample.py", "test_renamed.py")
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    report = _report(capsys)
    assert [finding for finding in report.findings if finding.rule == "test.deletion"] == []


def test_partial_rename_still_reports_deletion(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(repository, "mv", "test_sample.py", "test_renamed.py")
    target = repository / "test_renamed.py"
    target.write_text(target.read_text().replace("test_alpha", "test_alpha_renamed"))
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    report = _report(capsys)
    assert [(finding.path, finding.rule) for finding in report.findings] == [
        ("test_sample.py", "test.deletion")
    ]


def test_staged_deletion_uses_head_baseline(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = repository / "test_sample.py"
    source.write_text(_TEST_BODY + "\ndef test_gamma() -> None:\n    assert value(3) == 3\n")
    _commit(repository, "expanded tests")
    source.unlink()
    _git(repository, "add", "-A")
    assert main(["--root", str(repository), "--staged", "--format", "json"]) == 1
    report = _report(capsys)
    message = report.findings[0].message
    assert "3 test declaration(s)" in message
    assert "3 assertion(s)" in message


def test_staged_unmerged_index_is_an_error(repository: Path) -> None:
    blob = _git_output(repository, "rev-parse", "HEAD:test_sample.py").strip()
    entry = "".join(f"100644 {blob} {stage}\ttest_sample.py\n" for stage in (1, 2, 3))
    subprocess.run(
        ("git", "-C", str(repository), "update-index", "--index-info"),
        input=entry,
        text=True,
        check=True,
        capture_output=True,
    )
    assert main(["--root", str(repository), "--staged"]) == 2


def test_all_mode_does_not_run_deletion_gate(repository: Path) -> None:
    _git(repository, "rm", "--cached", "-q", "test_sample.py")
    assert main(["--root", str(repository), "--all"]) == 0
    assert main(["--root", str(repository), "--staged"]) == 1


def test_bad_syntax_baseline_still_reports_deletion(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "test_sample.py").write_text("def test_broken(:\n    assert True\n")
    _commit(repository, "broken baseline")
    (repository / "test_sample.py").unlink()
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    report = _report(capsys)
    assert [(finding.path, finding.rule, finding.scope) for finding in report.findings] == [
        ("test_sample.py", "test.deletion", "file")
    ]
    assert "Deleted test file" in report.findings[0].message


def test_reorder_and_helper_rename_do_not_report(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = (
        "def _helper(item: int) -> int:\n"
        "    return item + 1\n"
        "\n"
        "def test_alpha() -> None:\n"
        "    assert _helper(1) == 2\n"
        "\n"
        "def test_beta() -> None:\n"
        "    assert _helper(2) == 3\n"
    )
    (repository / "test_sample.py").write_text(baseline)
    _commit(repository, "reorder baseline")
    current = (
        "def _assist(item: int) -> int:\n"
        "    return item + 1\n"
        "\n"
        "def test_beta() -> None:\n"
        "    assert _assist(2) == 3\n"
        "\n"
        "def test_alpha() -> None:\n"
        "    assert _assist(1) == 2\n"
    )
    (repository / "test_sample.py").write_text(current)
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    report = _report(capsys)
    assert report.findings == ()


def test_test_declaration_rename_is_reported(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = repository / "test_sample.py"
    source.write_text(source.read_text().replace("test_alpha", "test_gamma"))
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    report = _report(capsys)
    assert [(finding.rule, finding.scope) for finding in report.findings] == [
        ("test.deletion", "file")
    ]
    assert "'test_alpha'" in report.findings[0].message


def test_removed_declaration_is_reported(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = repository / "test_sample.py"
    source.write_text(
        source.read_text().replace("\ndef test_beta() -> None:\n    assert value(2) == 2\n", "")
    )
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    report = _report(capsys)
    assert "'test_beta'" in report.findings[0].message


@pytest.mark.parametrize(
    ("removed", "reported"),
    [(3, False), (4, True)],
)
def test_assertion_threshold_is_strict(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    removed: int,
    reported: bool,
) -> None:
    tail = "def value(item: int) -> int:\n    return item\n"
    baseline = "def test_counts() -> None:\n" + "".join(
        f"    assert value({index}) == {index}\n" for index in range(1, 6)
    )
    (repository / "test_sample.py").write_text(baseline + "\n" + tail)
    _commit(repository, "counts baseline")
    kept = 5 - removed
    current = "def test_counts() -> None:\n" + "".join(
        f"    assert value({index}) == {index}\n" for index in range(1, kept + 1)
    )
    (repository / "test_sample.py").write_text(current + "\n" + tail)
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == int(reported)
    report = _report(capsys)
    assert [finding.rule for finding in report.findings] == (["test.deletion"] if reported else [])


def test_duplicate_declaration_names_use_multiset(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = (
        "def test_dup() -> None:\n"
        "    assert value(1) == 1\n"
        "\n"
        "def test_dup() -> None:\n"
        "    assert value(2) == 2\n"
        "\n"
        "def value(item: int) -> int:\n"
        "    return item\n"
    )
    (repository / "test_dup.py").write_text(baseline)
    _commit(repository, "duplicate baseline")
    reordered = (
        "def test_dup() -> None:\n"
        "    assert value(2) == 2\n"
        "\n"
        "def test_dup() -> None:\n"
        "    assert value(1) == 1\n"
        "\n"
        "def value(item: int) -> int:\n"
        "    return item\n"
    )
    (repository / "test_dup.py").write_text(reordered)
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    assert _report(capsys).findings == ()
    (repository / "test_dup.py").write_text(
        "def test_dup() -> None:\n    assert value(1) == 1\n\n"
        "def value(item: int) -> int:\n    return item\n"
    )
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    report = _report(capsys)
    assert "'test_dup'" in report.findings[0].message


def test_snapshot_change_is_warning_and_coexists_with_deletion(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "widget.snap").write_text("recorded\n")
    _commit(repository, "snapshot baseline")
    (repository / "widget.snap").write_text("changed\n")
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    warning = _report(capsys)
    assert [(finding.path, finding.severity, finding.scope) for finding in warning.findings] == [
        ("widget.snap", "warning", "file")
    ]
    (repository / "test_sample.py").unlink()
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    combined = _report(capsys)
    assert {(finding.path, finding.severity) for finding in combined.findings} == {
        ("widget.snap", "warning"),
        ("test_sample.py", "error"),
    }


@pytest.mark.parametrize("snapshot_paths", ['["tests/snapshots/*"]', "[]"])
def test_snapshot_paths_can_be_narrowed_or_emptied(
    repository: Path, capsys: pytest.CaptureFixture[str], snapshot_paths: str
) -> None:
    (repository / "widget.snap").write_text("recorded\n")
    _commit(repository, "snapshot baseline")
    (repository / "widget.snap").write_text("changed\n")
    policy = '{"checkers":{"test.deletion":{"snapshot_paths":' + snapshot_paths + "}}}"
    (repository / ".pluvy/pluvy.json").write_text(policy + "\n")
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    assert _report(capsys).findings == ()


def test_disabled_checker_skips_deletion_and_is_disclosed(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / ".pluvy/pluvy.json").write_text(
        '{"checkers":{"test.deletion":{"enabled":false}}}\n'
    )
    (repository / "test_sample.py").unlink()
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    report = _report(capsys)
    assert report.findings == ()
    assert report.disabled_checkers == ("test.deletion",)
    assert main(["--root", str(repository), "--base", "HEAD"]) == 0
    assert "Disabled checkers: test.deletion" in capsys.readouterr().out


def test_base_untracked_test_is_not_deleted_and_untracked_snapshot_warns(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "test_new.py").write_text("def test_new() -> None:\n    assert 1 < 2\n")
    (repository / "new.snap").write_text("new\n")
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    report = _report(capsys)
    assert report.files == 1
    assert [(finding.path, finding.severity) for finding in report.findings] == [
        ("new.snap", "warning")
    ]


def test_staged_policy_disable_is_effective(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / ".pluvy/pluvy.json").write_text(
        '{"checkers":{"test.deletion":{"enabled":false}}}\n'
    )
    _commit(repository, "disable deletion")
    (repository / "test_sample.py").unlink()
    _git(repository, "add", "-A")
    assert main(["--root", str(repository), "--staged", "--format", "json"]) == 0
    report = _report(capsys)
    assert report.findings == ()
    assert report.disabled_checkers == ("test.deletion",)


def test_baseline_non_utf8_is_an_error(repository: Path) -> None:
    (repository / "test_sample.py").write_bytes(b"\xff\xfe broken")
    _commit(repository, "binary baseline")
    (repository / "test_sample.py").unlink()
    assert main(["--root", str(repository), "--base", "HEAD"]) == 2


def test_deleted_file_reports_even_when_baseline_parser_rejects() -> None:
    gate = _TestDeletionGate(
        _Bindings({Language.PYTHON: _TestBinding(_RejectingParser(), PythonTestSyntax())})
    )
    deleted = Source("test_sample.py", b"def test_alpha():\n    assert True\n", Language.PYTHON)
    findings = gate.evaluate((deleted,), (), (), (), Policy())
    assert [(finding.path, finding.severity, finding.scope) for finding in findings] == [
        ("test_sample.py", "error", "file")
    ]
    assert "unavailable" in findings[0].message


def test_erosion_skips_file_when_parser_rejects() -> None:
    gate = _TestDeletionGate(
        _Bindings({Language.PYTHON: _TestBinding(_RejectingParser(), PythonTestSyntax())})
    )
    baseline = Source("test_sample.py", b"def test_alpha():\n    assert True\n", Language.PYTHON)
    current = Source("test_sample.py", b"def test_alpha():\n    pass\n", Language.PYTHON)
    assert gate.evaluate((), (baseline,), (current,), ("test_sample.py",), Policy()) == ()


def test_candidates_filter_changed_paths_and_test_globs() -> None:
    gate = builtin_deletion_gate()
    current = (
        Source("test_root.py", b"", Language.PYTHON),
        Source("tests/test_nested.py", b"", Language.PYTHON),
        Source("app.py", b"", Language.PYTHON),
        Source("test_unchanged.py", b"", Language.PYTHON),
    )
    changed = ("test_root.py", "tests/test_nested.py", "app.py")
    candidates = gate.candidates(current, changed, Policy())
    assert [source.path for source in candidates] == ["test_root.py", "tests/test_nested.py"]


def test_duplicate_declaration_multiset_reports_removal() -> None:
    gate = builtin_deletion_gate()
    baseline = Source(
        "test_dup.py",
        (
            b"def test_dup() -> None:\n    assert value(1) == 1\n\n"
            b"def test_dup() -> None:\n    assert value(2) == 2\n\n"
            b"def value(item: int) -> int:\n    return item\n"
        ),
        Language.PYTHON,
    )
    current = Source(
        "test_dup.py",
        (
            b"def test_dup() -> None:\n    assert value(1) == 1\n\n"
            b"def value(item: int) -> int:\n    return item\n"
        ),
        Language.PYTHON,
    )
    findings = gate.evaluate((), (baseline,), (current,), ("test_dup.py",), Policy())
    assert [finding.rule for finding in findings] == ["test.deletion"]
    assert "Assertion count fell by 1" in findings[0].message


def test_builtin_gate_binds_every_language_and_reuses_javascript_syntax() -> None:
    gate = builtin_deletion_gate()
    languages = {plugin.definition.language for plugin in builtin_languages()}
    assert {
        language for language in languages if gate.bindings.binding_for(language) is not None
    } == languages
    assert gate.rule_ids == ("test.deletion",)
    for language in (Language.JAVASCRIPT, Language.TYPESCRIPT, Language.TSX):
        binding = gate.bindings.binding_for(language)
        assert binding is not None
        assert isinstance(binding.syntax, JavaScriptTestSyntax)


def test_gate_disabled_returns_no_findings() -> None:
    gate = builtin_deletion_gate()
    deleted = Source("test_sample.py", b"def test_alpha():\n    assert True\n", Language.PYTHON)
    policy = Policy.model_validate_json('{"checkers":{"test.deletion":{"enabled":false}}}')
    assert gate.evaluate((deleted,), (), (), ("widget.snap",), policy) == ()


def test_findings_are_sorted_by_path() -> None:
    gate = builtin_deletion_gate()
    deleted = (
        Source("z_test.py", b"def test_alpha():\n    assert True\n", Language.PYTHON),
        Source("a_test.py", b"def test_alpha():\n    assert True\n", Language.PYTHON),
    )
    findings = gate.evaluate(deleted, (), (), ("m.snap",), Policy())
    assert [finding.path for finding in findings] == ["a_test.py", "m.snap", "z_test.py"]


def test_changed_paths_excludes_exact_rename_and_includes_untracked(
    repository: Path,
) -> None:
    _git(repository, "mv", "test_sample.py", "test_renamed.py")
    (repository / "new.snap").write_text("new\n")
    assert changed_paths(Selection(repository, "base", "HEAD")) == ("new.snap",)


def test_deleted_sources_selects_only_scoped_language_files(repository: Path) -> None:
    (repository / "notes.txt").write_text("notes\n")
    _commit(repository, "notes")
    (repository / "test_sample.py").unlink()
    (repository / "notes.txt").unlink()
    selection = Selection(repository, "base", "HEAD")
    analyzers = builtin_registry()
    deleted = deleted_sources(selection, Policy(), analyzers)
    assert [source.path for source in deleted] == ["test_sample.py"]
    assert deleted[0].content.startswith(b"def test_alpha")
    excluded = Policy.model_validate_json('{"exclude":["test_sample.py"]}')
    assert deleted_sources(selection, excluded, analyzers) == ()


def test_baseline_sources_skips_missing_and_unregistered_paths(repository: Path) -> None:
    (repository / "new_test.py").write_text("def test_new() -> None:\n    assert 1 < 2\n")
    selection = Selection(repository, "base", "HEAD")
    baselines = baseline_sources(
        selection,
        ("test_sample.py", "new_test.py", "notes.txt"),
        builtin_registry(),
    )
    assert [source.path for source in baselines] == ["test_sample.py"]
    assert baselines[0].content.startswith(b"def test_alpha")


def test_deletion_directive_is_invalid_and_does_not_suppress_gate(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "test_sample.py").write_text(
        "def test_alpha() -> None:\n"
        "    assert value(1) == 1\n"
        "    assert value(2) == 2\n\n"
        "def test_beta() -> None:\n"
        "    assert value(3) == 3\n\n"
        "def value(item: int) -> int:\n"
        "    return item\n"
    )
    _commit(repository, "declaration baseline")
    (repository / "test_sample.py").write_text(
        "def test_alpha() -> None:\n"
        "    # pluvy: ignore-next-line test.deletion -- approved exception\n"
        "    assert value(1) == 1\n"
        "    assert value(2) == 2\n\n"
        "def value(item: int) -> int:\n"
        "    return item\n"
    )
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 1
    findings = {
        (finding.rule, finding.path, finding.line, finding.severity)
        for finding in _report(capsys).findings
    }
    assert ("test.deletion", "test_sample.py", 1, "error") in findings
    assert ("type.suppression", "test_sample.py", 2, "error") in findings


def test_deleted_snapshot_path_is_a_warning(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "widget.snap").write_text("recorded\n")
    _commit(repository, "snapshot baseline")
    (repository / "widget.snap").unlink()
    assert main(["--root", str(repository), "--base", "HEAD", "--format", "json"]) == 0
    assert [
        (finding.path, finding.rule, finding.severity, finding.scope)
        for finding in _report(capsys).findings
    ] == [("widget.snap", "test.deletion", "warning", "file")]


def test_staged_exact_rename_is_silent(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(repository, "mv", "test_sample.py", "test_renamed.py")
    _git(repository, "add", "-A")
    assert main(["--root", str(repository), "--staged", "--format", "json"]) == 0
    assert [
        finding for finding in _report(capsys).findings if finding.rule == "test.deletion"
    ] == []


def test_baseline_sources_surfaces_git_failure(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_git(root: Path, arguments: tuple[str, ...]) -> bytes:
        if arguments[:1] == ("ls-tree",):
            raise GateError("simulated ls-tree failure")
        return snapshot_git(root, arguments)

    monkeypatch.setattr("pluvy.snapshots.git", failing_git)
    selection = Selection(repository, "base", "HEAD")
    with pytest.raises(GateError, match="simulated ls-tree failure"):
        baselines = baseline_sources(selection, ("test_sample.py",), builtin_registry())
        pytest.fail(f"baseline_sources returned {len(baselines)} sources instead of failing")
