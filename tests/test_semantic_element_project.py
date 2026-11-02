"""Cross-file coverage for container evidence withdrawn by an element write."""

from collections.abc import Iterable
from pathlib import Path

import pytest

from pluvy.cli import main
from pluvy.languages.javascript.semantic_syntax import JavaScriptSemanticSyntax
from pluvy.languages.python.semantic_syntax import PythonSemanticSyntax
from pluvy.languages.typescript.semantic_syntax import TypeScriptSemanticSyntax
from pluvy.models import Report
from pluvy.plugins.builtins import tree_parser
from pluvy.policy.models import Policy
from pluvy.semantics.index import SemanticIndex
from pluvy.semantics.model import SemanticSyntax, Symbol
from pluvy.semantics.project import ProjectUsage
from pluvy.semantics.usage import UsageRule
from pluvy.source import Language, Source

_PYTHON_DECLARATIONS = """class Item:
    def render(self) -> int:
        return 1

class Other:
    def render(self) -> None:
        print("other")

items = [Item(), Item()]
"""

_PYTHON_WRITES = """from module_name import Other, items

items[0] = Other()
items[0].render()
"""

_JAVASCRIPT_DECLARATIONS = """class Item {
  render() { return 1; }
}

class Other {
  render() { console.log("other"); }
}

export const items = [new Item(), new Item()];
"""

_JAVASCRIPT_WRITES = """import {Other, items} from "./module_name";

items[0] = new Other();
items[0].render();
"""

_TYPESCRIPT_DECLARATIONS = """class Item {
  render(): number { return 1; }
}

class Other {
  render(): void { console.log("other"); }
}

export const items = [new Item(), new Item()];
"""

_TYPESCRIPT_WRITES = """import {Other, items} from "./module_name";

items[0] = new Other();
items[0].render();
"""

_SUFFIXES: dict[Language, str] = {
    Language.PYTHON: ".py",
    Language.JAVASCRIPT: ".js",
    Language.TYPESCRIPT: ".ts",
}

_DECLARATIONS: dict[Language, str] = {
    Language.PYTHON: _PYTHON_DECLARATIONS,
    Language.JAVASCRIPT: _JAVASCRIPT_DECLARATIONS,
    Language.TYPESCRIPT: _TYPESCRIPT_DECLARATIONS,
}

_WRITES: dict[Language, str] = {
    Language.PYTHON: _PYTHON_WRITES,
    Language.JAVASCRIPT: _JAVASCRIPT_WRITES,
    Language.TYPESCRIPT: _TYPESCRIPT_WRITES,
}

_SEMANTIC_SYNTAX: dict[Language, SemanticSyntax] = {
    Language.PYTHON: PythonSemanticSyntax(),
    Language.JAVASCRIPT: JavaScriptSemanticSyntax(),
    Language.TYPESCRIPT: TypeScriptSemanticSyntax(),
}

# The placeholder the write templates keep where the declaring module name belongs.
_MODULE = "module_name"

_ORDERS = (
    pytest.param(Language.PYTHON, "a_declares.py", "b_writes.py", id="python-declaration-first"),
    pytest.param(Language.PYTHON, "b_declares.py", "a_writes.py", id="python-write-first"),
    pytest.param(
        Language.JAVASCRIPT,
        "a_declares.js",
        "b_writes.js",
        id="javascript-declaration-first",
    ),
    pytest.param(Language.JAVASCRIPT, "b_declares.js", "a_writes.js", id="javascript-write-first"),
    pytest.param(
        Language.TYPESCRIPT,
        "a_declares.ts",
        "b_writes.ts",
        id="typescript-declaration-first",
    ),
    pytest.param(Language.TYPESCRIPT, "b_declares.ts", "a_writes.ts", id="typescript-write-first"),
)


def _project(language: Language, declaring: str, writing: str) -> tuple[tuple[str, str], ...]:
    module = declaring.removesuffix(_SUFFIXES[language])
    return (
        (declaring, _DECLARATIONS[language]),
        (writing, _WRITES[language].replace(_MODULE, module)),
    )


def _indexes(files: Iterable[tuple[str, str]], language: Language) -> tuple[SemanticIndex, ...]:
    policy = Policy()
    parser = tree_parser(language)
    syntax = _SEMANTIC_SYNTAX[language]
    return tuple(
        SemanticIndex(parser.parse(Source(path, code.encode(), language), policy), syntax)
        for path, code in sorted(files)
    )


def _prepared(indexes: tuple[SemanticIndex, ...]) -> ProjectUsage:
    project = ProjectUsage(indexes)
    project.prepare()
    return project


def _usage(
    indexes: tuple[SemanticIndex, ...], project: ProjectUsage
) -> tuple[tuple[str, str, str], ...]:
    evidence = project.evidence()
    return tuple(
        (finding.path, finding.rule, finding.message)
        for index in indexes
        for finding in UsageRule().evaluate(index, evidence.unresolved, evidence.contract_reads)
    )


def _container(index: SemanticIndex) -> Symbol:
    return next(symbol for symbol in index.symbols() if symbol.name == "items")


def _of(indexes: tuple[SemanticIndex, ...], path: str) -> SemanticIndex:
    return next(index for index in indexes if index.context.source.path == path)


@pytest.mark.parametrize(("language", "declaring", "writing"), _ORDERS)
def test_cross_file_element_write_withdraws_the_container_evidence(
    language: Language, declaring: str, writing: str
) -> None:
    indexes = _indexes(_project(language, declaring, writing), language)
    assert _usage(indexes, _prepared(indexes)) == ()
    assert _of(indexes, writing).unresolved_reads == {"render"}
    owner = _container(_of(indexes, declaring))
    assert (owner.type_name, owner.class_scope) == ("", None)


@pytest.mark.parametrize(("language", "declaring", "writing"), _ORDERS)
def test_repeated_refresh_keeps_cross_file_element_evidence_withdrawn(
    language: Language, declaring: str, writing: str
) -> None:
    indexes = _indexes(_project(language, declaring, writing), language)
    project = _prepared(indexes)
    for index in indexes:
        index.refresh()
    for index in indexes:
        index.refresh()
    assert _usage(indexes, project) == ()
    assert _container(_of(indexes, declaring)).type_name == ""


def _write_project(root: Path, files: Iterable[tuple[str, str]]) -> None:
    (root / ".pluvy").mkdir(parents=True, exist_ok=True)
    (root / ".pluvy/pluvy.json").write_text("{}\n")
    for path, code in files:
        (root / path).write_text(code)


@pytest.mark.parametrize(("language", "declaring", "writing"), _ORDERS)
def test_full_audit_withdraws_cross_file_element_evidence_in_both_file_orders(
    language: Language,
    declaring: str,
    writing: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_project(tmp_path, _project(language, declaring, writing))
    assert main(["--root", str(tmp_path), "--all", "--format", "json"]) == 0
    report = Report.model_validate_json(capsys.readouterr().out)
    assert (report.files, report.findings) == (2, ())
