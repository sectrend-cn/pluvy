"""Behavioral coverage for element-derived container type evidence."""

import pytest

from pluvy.diagnostics import Finding
from pluvy.engine import check
from pluvy.policy.models import Policy
from pluvy.source import Language, Source

_PYTHON_RENDER_ITEM = """class Item:
    def render(self) -> None:
        print("item")
"""

_PYTHON_DRAW_ITEM = (
    _PYTHON_RENDER_ITEM
    + """
    def draw(self) -> None:
        print("draw")
"""
)

_PYTHON_RENDER_INT_ITEM = """class Item:
    def render(self) -> int:
        return 1
"""

_PYTHON_RENDER_INT_OTHER = """class Other:
    def render(self) -> int:
        return 2
"""

_PYTHON_RENDER_OTHER = """class Other:
    def render(self) -> None:
        print("other")
"""

_PYTHON_WRITE_OTHER = """class Other:
    def write(self) -> None:
        print("write")

    def render(self) -> None:
        print("other")
"""

_JAVASCRIPT_RENDER_ITEM = """class Item {
  render() { console.log("item"); }
}
"""

_JAVASCRIPT_DRAW_ITEM = """class Item {
  render() { console.log("item"); }
  draw() { console.log("draw"); }
}
"""

_JAVASCRIPT_RENDER_INT_ITEM = """class Item {
  render() { return 1; }
}
"""

_JAVASCRIPT_RENDER_INT_OTHER = """class Other {
  render() { return 2; }
}
"""

_JAVASCRIPT_RENDER_OTHER = """class Other {
  render() { console.log("other"); }
}
"""

_JAVASCRIPT_WRITE_OTHER = """class Other {
  write() { console.log("write"); }
  render() { console.log("other"); }
}
"""

_TYPESCRIPT_RENDER_ITEM = """class Item {
  render(): void { console.log("item"); }
}
"""

_TYPESCRIPT_DRAW_ITEM = """class Item {
  render(): void { console.log("item"); }
  draw(): void { console.log("draw"); }
}
"""

_TYPESCRIPT_RENDER_INT_ITEM = """class Item {
  render(): number { return 1; }
}
"""

_TYPESCRIPT_RENDER_INT_OTHER = """class Other {
  render(): number { return 2; }
}
"""

_TYPESCRIPT_RENDER_OTHER = """class Other {
  render(): void { console.log("other"); }
}
"""

_TYPESCRIPT_WRITE_OTHER = """class Other {
  write(): void { console.log("write"); }
  render(): void { console.log("other"); }
}
"""


def _findings(code: str, language: Language) -> tuple[Finding, ...]:
    return check(Source("sample", code.encode(), language), Policy())


def _source(*parts: str) -> str:
    return "\n".join(part.rstrip("\n") for part in parts) + "\n"


def _unused(name: str) -> str:
    return f"Function {name!r} has no resolved read usage in the audited snapshots"


def _reported(findings: tuple[Finding, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((finding.rule, finding.message) for finding in findings)


def _line_of(code: str, snippet: str) -> int:
    return code[: code.index(snippet)].count("\n") + 1


@pytest.mark.parametrize(
    ("language", "declarations", "statements"),
    [
        (
            Language.PYTHON,
            _PYTHON_RENDER_ITEM + _PYTHON_RENDER_OTHER,
            "items = [Item(), Other()]\nitems[1].render()",
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_RENDER_ITEM + _JAVASCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Other()];\nitems[1].render();",
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_RENDER_ITEM + _TYPESCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Other()];\nitems[1].render();",
        ),
    ],
)
def test_heterogeneous_elements_defer_the_shared_member(
    language: Language, declarations: str, statements: str
) -> None:
    code = _source(declarations, statements)
    assert _findings(code, language) == ()


@pytest.mark.parametrize(
    ("language", "declarations", "statements", "unused_line"),
    [
        (
            Language.PYTHON,
            _PYTHON_RENDER_INT_ITEM + _PYTHON_RENDER_INT_OTHER,
            "items = [Item(), Item()]\nitems[0].render()",
            _line_of(_PYTHON_RENDER_INT_ITEM + _PYTHON_RENDER_INT_OTHER, "class Other") + 1,
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_RENDER_INT_ITEM + _JAVASCRIPT_RENDER_INT_OTHER,
            "const items = [new Item(), new Item()];\nitems[0].render();",
            _line_of(_JAVASCRIPT_RENDER_INT_ITEM + _JAVASCRIPT_RENDER_INT_OTHER, "class Other") + 1,
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_RENDER_INT_ITEM + _TYPESCRIPT_RENDER_INT_OTHER,
            "const items = [new Item(), new Item()];\nitems[0].render();",
            _line_of(_TYPESCRIPT_RENDER_INT_ITEM + _TYPESCRIPT_RENDER_INT_OTHER, "class Other") + 1,
        ),
    ],
)
def test_homogeneous_elements_resolve_the_constructed_owner(
    language: Language, declarations: str, statements: str, unused_line: int
) -> None:
    code = _source(declarations, statements)
    findings = _findings(code, language)
    assert _reported(findings) == (
        ("unused.function", _unused("render")),
        ("unused.return", "Return value from 'render' is discarded"),
    )
    assert findings[0].line == unused_line
    assert findings[1].line == _line_of(code, "items[0].render")


@pytest.mark.parametrize(
    ("language", "declarations", "statements", "unused_line"),
    [
        (
            Language.PYTHON,
            _PYTHON_DRAW_ITEM + _PYTHON_RENDER_OTHER,
            "items = [Item(), Item()]\nitems[0].render()",
            _line_of(_PYTHON_DRAW_ITEM, "def draw"),
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_DRAW_ITEM + _JAVASCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Item()];\nitems[0].render();",
            _line_of(_JAVASCRIPT_DRAW_ITEM, "draw()"),
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_DRAW_ITEM + _TYPESCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Item()];\nitems[0].render();",
            _line_of(_TYPESCRIPT_DRAW_ITEM, "draw()"),
        ),
    ],
)
def test_homogeneous_elements_report_unread_sibling_members(
    language: Language, declarations: str, statements: str, unused_line: int
) -> None:
    code = _source(declarations, statements)
    findings = _findings(code, language)
    assert _reported(findings) == (
        ("unused.function", _unused("draw")),
        ("unused.function", _unused("render")),
    )
    assert findings[0].line == unused_line
    assert findings[1].line == _line_of(declarations, "class Other") + 1


@pytest.mark.parametrize(
    ("language", "declarations", "statements"),
    [
        (
            Language.PYTHON,
            _PYTHON_DRAW_ITEM + _PYTHON_RENDER_OTHER,
            "items = [Item(), Other()]\nitems[1].render()",
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_DRAW_ITEM + _JAVASCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Other()];\nitems[1].render();",
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_DRAW_ITEM + _TYPESCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Other()];\nitems[1].render();",
        ),
    ],
)
def test_heterogeneous_elements_report_only_differently_named_members(
    language: Language, declarations: str, statements: str
) -> None:
    code = _source(declarations, statements)
    assert _reported(_findings(code, language)) == (("unused.function", _unused("draw")),)


@pytest.mark.parametrize(
    ("language", "declarations", "statements"),
    [
        (
            Language.PYTHON,
            _PYTHON_RENDER_ITEM + _PYTHON_WRITE_OTHER,
            "items = [Item(), Other()]\nitems[1].render()",
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_RENDER_ITEM + _JAVASCRIPT_WRITE_OTHER,
            "const items = [new Item(), new Other()];\nitems[1].render();",
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_RENDER_ITEM + _TYPESCRIPT_WRITE_OTHER,
            "const items = [new Item(), new Other()];\nitems[1].render();",
        ),
    ],
)
def test_heterogeneous_elements_keep_unrelated_member_reports(
    language: Language, declarations: str, statements: str
) -> None:
    code = _source(declarations, statements)
    assert _reported(_findings(code, language)) == (("unused.function", _unused("write")),)


@pytest.mark.parametrize(
    ("language", "declarations", "statements", "unused_line"),
    [
        (
            Language.PYTHON,
            _PYTHON_RENDER_INT_ITEM + _PYTHON_RENDER_INT_OTHER,
            "items = [Item(), Item()]\nitems[0] = Item()\nitems[1].render()",
            _line_of(_PYTHON_RENDER_INT_ITEM + _PYTHON_RENDER_INT_OTHER, "class Other") + 1,
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_RENDER_INT_ITEM + _JAVASCRIPT_RENDER_INT_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = new Item();\nitems[1].render();",
            _line_of(_JAVASCRIPT_RENDER_INT_ITEM + _JAVASCRIPT_RENDER_INT_OTHER, "class Other") + 1,
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_RENDER_INT_ITEM + _TYPESCRIPT_RENDER_INT_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = new Item();\nitems[1].render();",
            _line_of(_TYPESCRIPT_RENDER_INT_ITEM + _TYPESCRIPT_RENDER_INT_OTHER, "class Other") + 1,
        ),
    ],
)
def test_element_write_of_the_same_type_keeps_the_element_owner(
    language: Language, declarations: str, statements: str, unused_line: int
) -> None:
    code = _source(declarations, statements)
    findings = _findings(code, language)
    assert _reported(findings) == (
        ("unused.function", _unused("render")),
        ("unused.return", "Return value from 'render' is discarded"),
    )
    assert findings[0].line == unused_line
    assert findings[1].line == _line_of(code, "items[1].render")


@pytest.mark.parametrize(
    ("language", "declarations", "statements"),
    [
        (
            Language.PYTHON,
            _PYTHON_RENDER_ITEM + _PYTHON_RENDER_OTHER,
            "items = [Item(), Item()]\nitems[0] = Other()\nitems[1].render()",
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_RENDER_ITEM + _JAVASCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = new Other();\nitems[1].render();",
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_RENDER_ITEM + _TYPESCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = new Other();\nitems[1].render();",
        ),
    ],
)
def test_element_write_of_another_type_defers_the_shared_member(
    language: Language, declarations: str, statements: str
) -> None:
    code = _source(declarations, statements)
    assert _findings(code, language) == ()


@pytest.mark.parametrize(
    ("language", "declarations", "statements"),
    [
        (
            Language.PYTHON,
            _PYTHON_RENDER_ITEM + _PYTHON_WRITE_OTHER,
            "items = [Item(), Item()]\nitems[0] = Other()\nitems[1].render()",
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_RENDER_ITEM + _JAVASCRIPT_WRITE_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = new Other();\nitems[1].render();",
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_RENDER_ITEM + _TYPESCRIPT_WRITE_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = new Other();\nitems[1].render();",
        ),
    ],
)
def test_element_write_of_another_type_keeps_other_member_names(
    language: Language, declarations: str, statements: str
) -> None:
    code = _source(declarations, statements)
    assert _reported(_findings(code, language)) == (("unused.function", _unused("write")),)


@pytest.mark.parametrize(
    ("language", "declarations", "statements"),
    [
        (
            Language.PYTHON,
            _PYTHON_RENDER_ITEM + _PYTHON_RENDER_OTHER,
            "items = [Item(), Item()]\nitems[0] = build()\nitems[1].render()",
        ),
        (
            Language.JAVASCRIPT,
            _JAVASCRIPT_RENDER_ITEM + _JAVASCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = build();\nitems[1].render();",
        ),
        (
            Language.TYPESCRIPT,
            _TYPESCRIPT_RENDER_ITEM + _TYPESCRIPT_RENDER_OTHER,
            "const items = [new Item(), new Item()];\nitems[0] = build();\nitems[1].render();",
        ),
    ],
)
def test_unresolvable_element_write_defers_the_shared_member(
    language: Language, declarations: str, statements: str
) -> None:
    code = _source(declarations, statements)
    assert _findings(code, language) == ()


@pytest.mark.parametrize(
    ("language", "code"),
    [
        (
            Language.PYTHON,
            _source(
                _PYTHON_RENDER_INT_ITEM,
                "item2 = Item()\nitems = [Item(), item2]\nitems[1].render()",
            ),
        ),
        (
            Language.PYTHON,
            _source(
                _PYTHON_RENDER_INT_ITEM,
                "rest = [Item()]\nitems = [Item(), *rest]\nitems[1].render()",
            ),
        ),
        (
            Language.PYTHON,
            _source(
                _PYTHON_RENDER_INT_ITEM,
                "items = [Item(), 1]\nitems[0].render()",
            ),
        ),
        (
            Language.PYTHON,
            _source(
                _PYTHON_RENDER_INT_ITEM,
                "items = [\n# element\nItem(), 1]\nitems[0].render()",
            ),
        ),
        (
            Language.JAVASCRIPT,
            _source(
                _JAVASCRIPT_RENDER_INT_ITEM,
                "const item2 = new Item();\nconst items = [new Item(), item2];\nitems[1].render();",
            ),
        ),
        (
            Language.JAVASCRIPT,
            _source(
                _JAVASCRIPT_RENDER_INT_ITEM,
                "const rest = [new Item()];\n"
                "const items = [new Item(), ...rest];\nitems[1].render();",
            ),
        ),
        (
            Language.JAVASCRIPT,
            _source(
                _JAVASCRIPT_RENDER_INT_ITEM,
                "const items = [new Item(), 1];\nitems[0].render();",
            ),
        ),
        (
            Language.JAVASCRIPT,
            _source(
                _JAVASCRIPT_RENDER_INT_ITEM,
                "const items = [/* element */ new Item(), 1];\nitems[0].render();",
            ),
        ),
        (
            Language.JAVASCRIPT,
            _source(
                _JAVASCRIPT_RENDER_INT_ITEM,
                "const items = [new Item(), ,];\nitems[0].render();",
            ),
        ),
        (
            Language.TYPESCRIPT,
            _source(
                _TYPESCRIPT_RENDER_INT_ITEM,
                "const item2 = new Item();\nconst items = [new Item(), item2];\nitems[1].render();",
            ),
        ),
        (
            Language.TYPESCRIPT,
            _source(
                _TYPESCRIPT_RENDER_INT_ITEM,
                "const rest = [new Item()];\n"
                "const items = [new Item(), ...rest];\nitems[1].render();",
            ),
        ),
        (
            Language.TYPESCRIPT,
            _source(
                _TYPESCRIPT_RENDER_INT_ITEM,
                "const items = [new Item(), 1];\nitems[0].render();",
            ),
        ),
        (
            Language.TYPESCRIPT,
            _source(
                _TYPESCRIPT_RENDER_INT_ITEM,
                "const items = [/* element */ new Item(), 1];\nitems[0].render();",
            ),
        ),
        (
            Language.TYPESCRIPT,
            _source(
                _TYPESCRIPT_RENDER_INT_ITEM,
                "const items = [new Item(), ,];\nitems[0].render();",
            ),
        ),
    ],
)
def test_incomplete_element_evidence_defers_the_shared_member(
    language: Language, code: str
) -> None:
    assert _findings(code, language) == ()


@pytest.mark.parametrize(
    ("language", "code", "unused_line"),
    [
        (
            Language.PYTHON,
            _source(
                _PYTHON_RENDER_ITEM + _PYTHON_RENDER_OTHER,
                "items: list[Item] = [Item(), Other()]\nitems[1].render()",
            ),
            _line_of(_PYTHON_RENDER_ITEM + _PYTHON_RENDER_OTHER, "class Other") + 1,
        ),
        (
            Language.TYPESCRIPT,
            _source(
                _TYPESCRIPT_RENDER_ITEM + _TYPESCRIPT_RENDER_OTHER,
                "const items: Item[] = [new Item(), new Other()];\nitems[1].render();",
            ),
            _line_of(_TYPESCRIPT_RENDER_ITEM + _TYPESCRIPT_RENDER_OTHER, "class Other") + 1,
        ),
    ],
)
def test_annotated_container_keeps_its_declared_element_type(
    language: Language, code: str, unused_line: int
) -> None:
    findings = _findings(code, language)
    assert _reported(findings) == (("unused.function", _unused("render")),)
    assert findings[0].line == unused_line


_GO_COMPOSITE_ELEMENT_WRITE = """package main

type Item struct{}

type Other struct{}

func (i Item) render() int { return 1 }

func (o Other) render() int { return 2 }

func main() {
	b := []Item{{}}
	b[0] = Other{}
	b[1].render()
}
"""


def test_go_composite_literal_element_write_keeps_the_spelled_owner() -> None:
    assert _reported(_findings(_GO_COMPOSITE_ELEMENT_WRITE, Language.GO)) == (
        ("unused.function", _unused("render")),
        ("unused.return", "Return value from 'render' is discarded"),
    )


_JAVA_ARRAY_CREATION_ELEMENT_WRITE = """class Sample {
    static class Item {
        int render() { return 1; }
    }

    static class Other {
        int render() { return 2; }
    }

    void run() {
        Item[] b = new Item[]{new Item()};
        b[0] = new Other();
        b[1].render();
    }
}
"""


def test_java_array_creation_element_write_keeps_the_spelled_owner() -> None:
    findings = _findings(_JAVA_ARRAY_CREATION_ELEMENT_WRITE, Language.JAVA)
    assert [(finding.rule, finding.line) for finding in findings] == [("unused.return", 13)]
