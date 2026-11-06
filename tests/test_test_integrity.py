"""Behavioral contracts for tautological and vacuous tests across grammars."""

import pytest
from pydantic import ValidationError
from tree_sitter import Node

from pluvy.diagnostics import Finding
from pluvy.engine import check
from pluvy.languages.go.plugin import GoLanguage
from pluvy.languages.go.test_syntax import GoTestSyntax
from pluvy.languages.java.plugin import JavaLanguage
from pluvy.languages.java.test_syntax import JavaTestSyntax
from pluvy.languages.javascript.plugin import JavaScriptLanguage
from pluvy.languages.javascript.test_syntax import JavaScriptTestSyntax
from pluvy.languages.python.plugin import PythonLanguage
from pluvy.languages.python.test_syntax import PythonTestSyntax
from pluvy.parsing.treesitter import TreeParser
from pluvy.policy.models import Policy
from pluvy.semantics.testing.contracts import TestSyntax as Syntax
from pluvy.source import Language, Source

_DEFAULT_PATHS = {
    Language.PYTHON: "tests/test_sample.py",
    Language.JAVASCRIPT: "sample.test.js",
    Language.TYPESCRIPT: "sample.test.ts",
    Language.TSX: "sample.test.tsx",
    Language.GO: "sample_test.go",
    Language.JAVA: "SampleTest.java",
}

_WINNER = """def test_data():
    payload = {"status": "ok"}
    print("test succeed!")
    assert payload["status"] == "ok"
    assert True
    assert 1 == 1


def test_service():
    service = "ready"
    result = service
    assert result == service
"""

_TAXMAN = """describe("formatUserName", () => {
  it("returns the formatted value", () => {
    const input = "Ada";
    const result = formatUserName(input);

    expect(result).toBe(result);
  });

  it("handles basic input", () => {
    expect(formatUserName("Ada")).toBe("Ada");
  });

  it("does not crash", () => {
    expect(() => formatUserName("Ada")).not.toThrow();
  });
});

describe("UserBadge", () => {
  it("renders", () => {
    render(<UserBadge name="Ada" />);
    expect(screen.getByText("Ada")).toBeTruthy();
  });

  it("matches snapshot", () => {
    const { container } = render(<UserBadge name="Ada" />);
    expect(container).toMatchSnapshot();
  });
});
"""


def _findings(
    code: str,
    language: Language,
    policy: Policy | None = None,
    path: str | None = None,
) -> tuple[Finding, ...]:
    source = Source(path or _DEFAULT_PATHS[language], code.encode(), language)
    return tuple(
        finding for finding in check(source, policy or Policy()) if finding.rule.startswith("test.")
    )


def _summary(findings: tuple[Finding, ...]) -> list[tuple[str, int, str]]:
    return [(finding.rule, finding.line, finding.severity) for finding in findings]


def _root(parser: TreeParser, language: Language, path: str, code: str) -> Node:
    return parser.tree(Source(path, code.encode(), language)).root_node


def _assertion_kinds(syntax: Syntax, root: Node) -> tuple[str, ...]:
    (declaration,) = syntax.declarations(root)
    return tuple(assertion.kind for assertion in syntax.assertions(declaration.node))


def _control_types(syntax: Syntax, root: Node) -> tuple[str, ...]:
    (declaration,) = syntax.declarations(root)
    return tuple(node.type for node in syntax.control_statements(declaration.node))


def test_winner_sample_reports_tautologies_without_data_flow() -> None:
    findings = _findings(_WINNER, Language.PYTHON)
    assert _summary(findings) == [
        ("test.tautology", 5, "error"),
        ("test.tautology", 6, "error"),
    ]
    assert all("test_data" in finding.message for finding in findings)


def test_python_assert_message_does_not_hide_a_tautology() -> None:
    code = 'def test_x():\n    assert 1 == 1, "unchanged"\n'
    assert _summary(_findings(code, Language.PYTHON)) == [("test.tautology", 2, "error")]


@pytest.mark.parametrize(
    ("language", "path"),
    [(Language.TYPESCRIPT, "sample.test.ts"), (Language.TSX, "sample.test.tsx")],
)
def test_taxman_sample_reports_only_untrustworthy_assertions(language: Language, path: str) -> None:
    findings = _findings(_TAXMAN, language, path=path)
    assert _summary(findings) == [
        ("test.tautology", 6, "error"),
        ("test.vacuous", 14, "error"),
        ("test.vacuous", 21, "error"),
        ("test.vacuous", 26, "warning"),
    ]


def test_python_assignment_and_print_body_is_vacuous() -> None:
    findings = _findings(
        "def test_empty():\n    values = [1, 2]\n    print(values)\n", Language.PYTHON
    )
    assert _summary(findings) == [("test.vacuous", 1, "error")]
    assert "test_empty" in findings[0].message


def test_python_unrecognized_call_keeps_body_signal_conservative() -> None:
    code = "def test_empty():\n    values = [1, 2]\n    helper(values)\n"
    assert _findings(code, Language.PYTHON) == ()


def test_javascript_assignment_and_console_body_is_vacuous() -> None:
    code = 'it("empty", () => {\n  const values = [1, 2];\n  console.log(values);\n});\n'
    assert _summary(_findings(code, Language.JAVASCRIPT)) == [("test.vacuous", 1, "error")]


def test_javascript_unrecognized_call_keeps_body_signal_conservative() -> None:
    code = 'it("empty", () => {\n  const values = [1, 2];\n  inspect(values);\n});\n'
    assert _findings(code, Language.JAVASCRIPT) == ()


@pytest.mark.parametrize(
    "body",
    [
        "expect(values).toContain(2);",
        "expect(value).not.toBeTruthy();",
        "expect(value).toMatchSnapshot();\n  expect(values).toContain(2);",
    ],
)
def test_javascript_behavioral_matchers_are_real_assertions(body: str) -> None:
    assert _findings('it("x", () => {\n  ' + body + "\n});\n", Language.JAVASCRIPT) == ()


@pytest.mark.parametrize("statement", ["assert(true);", "assert.equal(value, value);"])
def test_javascript_literal_true_assertions_are_tautologies(statement: str) -> None:
    code = 'it("x", () => {\n  ' + statement + "\n});\n"
    assert _summary(_findings(code, Language.JAVASCRIPT)) == [("test.tautology", 2, "error")]


def test_javascript_negative_and_inequality_assertions_are_not_tautologies() -> None:
    code = (
        'it("x", () => {\n'
        "  assert.notEqual(x, x);\n"
        "  assert.notStrictEqual(x, x);\n"
        "  assertFalse(true);\n"
        "});\n"
    )
    assert _findings(code, Language.JAVASCRIPT) == ()


def test_javascript_positive_equality_assertions_remain_tautologies() -> None:
    code = (
        'it("x", () => {\n'
        "  assert.equal(x, x);\n"
        "  assert.strictEqual(x, x);\n"
        "  assert.deepEqual(x, x);\n"
        "  assert.deepStrictEqual(x, x);\n"
        "  assert(true);\n"
        "  assert.ok(true);\n"
        "});\n"
    )
    assert _summary(_findings(code, Language.JAVASCRIPT)) == [
        ("test.tautology", 2, "error"),
        ("test.tautology", 3, "error"),
        ("test.tautology", 4, "error"),
        ("test.tautology", 5, "error"),
        ("test.tautology", 6, "error"),
        ("test.tautology", 7, "error"),
    ]


def test_javascript_bare_identifier_equality_call_is_not_mirrored() -> None:
    code = 'it("x", () => {\n  assertSame(x, x);\n});\n'
    assert _findings(code, Language.JAVASCRIPT) == ()


def test_python_raises_and_assert_helper_calls_count_as_assertions() -> None:
    raises = "def test_failure():\n    with pytest.raises(ValueError):\n        fail()\n"
    helper = (
        "def _assert_ready(value):\n"
        "    assert value == 'ready'\n\n\n"
        "def test_wrapper():\n"
        "    _assert_ready('ready')\n"
    )
    assert _findings(raises, Language.PYTHON) == ()
    assert _findings(helper, Language.PYTHON) == ()


def test_python_parametrize_decorator_does_not_create_a_finding() -> None:
    code = (
        "import pytest\n\n"
        "@pytest.mark.parametrize('value', [1, 2])\n"
        "def test_value(value):\n"
        "    checked = value + 1\n"
        "    assert checked == 2\n"
    )
    assert _findings(code, Language.PYTHON) == ()


def test_go_failure_helper_is_an_assertion_and_empty_body_is_vacuous() -> None:
    checked = (
        "package sample\n\n"
        'import "testing"\n\n'
        "func TestChecked(t *testing.T) {\n"
        "    if 1 != 1 {\n"
        '        t.Errorf("bad")\n'
        "    }\n"
        "}\n"
    )
    empty = (
        "package sample\n\n"
        'import "testing"\n\n'
        "func TestEmpty(t *testing.T) {\n"
        "    value := 1\n"
        "    fmt.Println(value)\n"
        "}\n"
    )
    assert _findings(checked, Language.GO) == ()
    assert _summary(_findings(empty, Language.GO)) == [("test.vacuous", 5, "error")]


def test_java_annotation_assertions_are_classified() -> None:
    code = (
        "class SampleTest {\n"
        "  @Test\n"
        "  void checked() {\n"
        "    Assertions.assertEquals(value, 42);\n"
        "  }\n\n"
        "  @Test\n"
        "  void mirrored() {\n"
        "    Assertions.assertEquals(value, value);\n"
        "  }\n\n"
        "  @Test\n"
        "  void empty() {\n"
        '    System.out.println("done");\n'
        "  }\n"
        "}\n"
    )
    assert _summary(_findings(code, Language.JAVA)) == [
        ("test.tautology", 9, "error"),
        ("test.vacuous", 12, "error"),
    ]


def test_java_assert_statements_and_assert_true_literals_are_tautologies() -> None:
    code = (
        "class SampleTest {\n"
        "  @Test\n"
        "  void checked() {\n"
        "    assert true;\n"
        "    assert x == x;\n"
        "    Assertions.assertTrue(true);\n"
        "    Assertions.assertFalse(true);\n"
        "  }\n"
        "}\n"
    )
    assert _summary(_findings(code, Language.JAVA)) == [
        ("test.tautology", 4, "error"),
        ("test.tautology", 5, "error"),
        ("test.tautology", 6, "error"),
    ]


def test_non_test_path_and_disabled_switch_report_nothing() -> None:
    code = "def test_x():\n    assert 1 == 1\n"
    disabled = Policy.model_validate_json('{"checkers":{"test.integrity":{"enabled":false}}}')
    assert _findings(code, Language.PYTHON, path="src/sample.py") == ()
    assert _findings(_WINNER, Language.PYTHON, policy=disabled) == ()


def test_custom_paths_tighten_the_default_scope() -> None:
    code = "def test_x():\n    assert 1 == 1\n"
    policy = Policy.model_validate_json('{"checkers":{"test.integrity":{"paths":["custom/*.py"]}}}')
    assert _findings(code, Language.PYTHON, policy=policy) == ()
    assert _summary(_findings(code, Language.PYTHON, policy=policy, path="custom/test.py")) == [
        ("test.tautology", 2, "error")
    ]


def test_default_paths_and_strict_options() -> None:
    assert len(Policy().checkers.test_integrity.paths) == 20
    with pytest.raises(ValidationError):
        Policy.model_validate_json('{"checkers":{"test.integrity":{"paths":"tests/*"}}}')
    with pytest.raises(ValidationError):
        Policy.model_validate_json('{"checkers":{"test.integrity":{"glob":["tests/*"]}}}')


def test_next_line_suppression_selects_each_diagnostic() -> None:
    tautology = (
        "def test_x():\n"
        "    # pluvy: ignore-next-line test.tautology -- Approved exception.\n"
        "    assert 1 == 1\n"
        "    assert 2 == 2\n"
    )
    vacuous = (
        'it("x", () => {\n'
        "  // pluvy: ignore-next-line test.vacuous -- Approved exception.\n"
        "  expect(callback).not.toThrow();\n"
        "  expect(value).toBeTruthy();\n"
        "});\n"
    )
    assert _summary(_findings(tautology, Language.PYTHON)) == [("test.tautology", 4, "error")]
    assert _summary(_findings(vacuous, Language.JAVASCRIPT)) == [("test.vacuous", 4, "error")]


def test_python_unittest_class_recognizes_assertions_and_raises() -> None:
    code = (
        "class FooTest(TestCase):\n"
        "    def test_checked(self):\n"
        "        self.assertEqual(actual, 42)\n\n"
        "    def test_raises(self):\n"
        "        with self.assertRaises(ValueError):\n"
        "            run()\n\n"
        "    def test_mirrored(self):\n"
        "        self.assertEqual(x, x)\n"
    )
    assert _summary(_findings(code, Language.PYTHON)) == [("test.tautology", 10, "error")]


def test_python_negative_and_inequality_assertions_are_not_tautologies() -> None:
    code = (
        "def test_x():\n"
        "    self.assertNotEqual(x, x)\n"
        "    self.assertIsNot(x, x)\n"
        "    self.assertLess(x, x)\n"
        "    self.assertFalse(True)\n"
    )
    assert _findings(code, Language.PYTHON) == ()


def test_python_positive_equality_assertions_remain_tautologies() -> None:
    code = (
        "def test_x():\n"
        "    self.assertEqual(x, x)\n"
        "    self.assertEquals(x, x)\n"
        "    self.assertIs(x, x)\n"
        "    assert True\n"
        "    assert 1 == 1\n"
    )
    assert _summary(_findings(code, Language.PYTHON)) == [
        ("test.tautology", 2, "error"),
        ("test.tautology", 3, "error"),
        ("test.tautology", 4, "error"),
        ("test.tautology", 5, "error"),
        ("test.tautology", 6, "error"),
    ]


def test_python_assert_true_call_requires_a_literal_true_argument() -> None:
    code = "def test_x():\n    self.assertTrue(True)\n    self.assertTrue(False)\n"
    assert _summary(_findings(code, Language.PYTHON)) == [("test.tautology", 2, "error")]


def test_python_custom_equality_helper_is_an_assertion_without_tautology() -> None:
    code = "def test_x():\n    _assert_same(x, x)\n"
    assert _findings(code, Language.PYTHON) == ()


def test_python_stdout_write_suppresses_empty_body_signal() -> None:
    code = 'import sys\n\n\ndef test_writes() -> None:\n    sys.stdout.write("ok")\n'
    assert _findings(code, Language.PYTHON) == ()


def test_go_error_call_suppresses_empty_body_signal() -> None:
    code = (
        "package sample\n\n"
        'import "testing"\n\n'
        "func TestStatus(t *testing.T) {\n"
        "    var err error\n"
        "    _ = err.Error()\n"
        "}\n"
    )
    assert _findings(code, Language.GO) == ()


def test_default_paths_select_nested_tests_and_ignore_other_sources() -> None:
    code = "def test_x():\n    assert 1 == 1\n"
    assert _summary(_findings(code, Language.PYTHON, path="src/test_x.py")) == [
        ("test.tautology", 2, "error")
    ]
    assert _summary(_findings(code, Language.PYTHON, path="deep/nested/tests/foo.py")) == [
        ("test.tautology", 2, "error")
    ]
    assert _findings(code, Language.PYTHON, path="src/engine.py") == ()
    assert _findings(code, Language.PYTHON, path="plain.py") == ()
    empty = Policy.model_validate_json('{"checkers":{"test.integrity":{"paths":[]}}}')
    assert _findings(code, Language.PYTHON, policy=empty, path="tests/test_x.py") == ()


def test_tsx_snapshot_warning_survives_unrecognized_render_call() -> None:
    code = (
        'it("matches snapshot", () => {\n'
        '  const { container } = render(<Badge name="Ada" />);\n'
        "  expect(container).toMatchSnapshot();\n"
        "});\n"
    )
    assert _summary(_findings(code, Language.TSX)) == [("test.vacuous", 3, "warning")]


@pytest.mark.parametrize(
    ("language", "path"),
    [
        (Language.JAVASCRIPT, "sample.test.js"),
        (Language.TYPESCRIPT, "sample.test.ts"),
        (Language.TSX, "sample.test.tsx"),
    ],
)
def test_javascript_constructor_calls_suppress_empty_body_signal(
    language: Language, path: str
) -> None:
    code = 'it("checked", () => {\n  new Check(42);\n});\n'
    assert _findings(code, language, path=path) == ()


@pytest.mark.parametrize(
    ("language", "path"),
    [
        (Language.JAVASCRIPT, "sample.test.js"),
        (Language.TYPESCRIPT, "sample.test.ts"),
        (Language.TSX, "sample.test.tsx"),
    ],
)
def test_javascript_constructor_calls_with_print_suppress_empty_body_signal(
    language: Language, path: str
) -> None:
    code = 'it("checked", () => {\n  new Check(42);\n  console.log("done");\n});\n'
    assert _findings(code, language, path=path) == ()


def test_java_constructor_calls_suppress_empty_body_signal() -> None:
    code = (
        "class SampleTest {\n"
        "  @Test\n"
        "  void checked() {\n"
        "    new Check(42);\n"
        "  }\n\n"
        "  @Test\n"
        "  void mixed() {\n"
        '    System.out.println("done");\n'
        "    new Check(42);\n"
        "  }\n"
        "}\n"
    )
    assert _findings(code, Language.JAVA) == ()


@pytest.mark.parametrize(
    "decorator",
    ["@pytest.fixture", '@pytest.fixture(scope="module")', "@pytest.fixture()", "@fixture"],
)
def test_python_fixture_decorated_functions_are_not_tests(decorator: str) -> None:
    code = (
        "import pytest\n\n\n"
        f"{decorator}\n"
        "def test_config():\n"
        '    return {"status": "ok"}\n\n\n'
        "def test_uses_config(test_config):\n"
        '    assert test_config["status"] == "ok"\n'
    )
    assert _findings(code, Language.PYTHON) == ()


def test_python_fixture_decorators_are_excluded_from_declarations() -> None:
    code = (
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def test_config():\n"
        "    return {}\n\n"
        '@pytest.fixture(scope="module")\n'
        "def test_scope():\n"
        "    return 1\n\n"
        "@fixture\n"
        "def test_imported():\n"
        "    return 2\n\n"
        "@pytest.mark.parametrize('value', [1])\n"
        "def test_parametrized(value):\n"
        "    assert value == 1\n\n"
        "@pytest.mark.asyncio\n"
        "async def test_asyncio():\n"
        "    assert 1 == 1\n\n"
        "@decorator\n"
        "def test_plain():\n"
        "    assert 1 == 1\n"
    )
    root = _root(PythonLanguage().parser, Language.PYTHON, "tests/test_sample.py", code)
    names = tuple(declaration.name for declaration in PythonTestSyntax().declarations(root))
    assert names == ("test_parametrized", "test_asyncio", "test_plain")


def test_python_async_tests_are_recognized() -> None:
    code = "import pytest\n\n@pytest.mark.asyncio\nasync def test_ready():\n    assert 1 == 1\n"
    assert _summary(_findings(code, Language.PYTHON)) == [("test.tautology", 5, "error")]


def test_python_async_with_fixture_body_is_not_vacuous() -> None:
    code = "async def test_stream(fixture):\n    async with fixture:\n        pass\n"
    assert _findings(code, Language.PYTHON) == ()


def test_python_control_flow_body_is_not_vacuous() -> None:
    code = (
        "def test_flow(values):\n"
        "    for value in values:\n"
        "        pass\n"
        "    if values:\n"
        "        pass\n"
        "    while values:\n"
        "        break\n"
    )
    assert _findings(code, Language.PYTHON) == ()


def test_javascript_control_flow_body_is_not_vacuous() -> None:
    code = (
        'it("flow", () => {\n'
        "  for (const value of values) {\n"
        "    result = value;\n"
        "  }\n"
        "  if (result) {\n"
        "    result = 1;\n"
        "  }\n"
        "  while (result) {\n"
        "    result = 0;\n"
        "  }\n"
        "});\n"
    )
    assert _findings(code, Language.JAVASCRIPT) == ()


@pytest.mark.parametrize(
    ("language", "path", "code"),
    [
        (
            Language.PYTHON,
            "tests/test_sample.py",
            "def test_raised():\n    raise AssertionError\n",
        ),
        (
            Language.JAVASCRIPT,
            "sample.test.js",
            'it("raised", () => {\n  throw error;\n});\n',
        ),
        (
            Language.JAVA,
            "SampleTest.java",
            "class SampleTest {\n  @Test\n  void raised() {\n    throw stale;\n  }\n}\n",
        ),
    ],
)
def test_bare_raise_and_throw_bodies_are_not_vacuous(
    language: Language, path: str, code: str
) -> None:
    assert _findings(code, language, path=path) == ()


@pytest.mark.parametrize(
    ("language", "path", "code"),
    [
        (
            Language.PYTHON,
            "tests/test_sample.py",
            'def test_raised():\n    raise ValueError("x")\n',
        ),
        (
            Language.JAVASCRIPT,
            "sample.test.js",
            'it("raised", () => {\n  throw new Error("x");\n});\n',
        ),
        (
            Language.JAVA,
            "SampleTest.java",
            (
                "class SampleTest {\n"
                "  @Test\n"
                "  void raised() {\n"
                '    throw new IllegalStateException("x");\n'
                "  }\n"
                "}\n"
            ),
        ),
    ],
)
def test_raise_and_throw_calls_keep_the_body_signal_conservative(
    language: Language, path: str, code: str
) -> None:
    assert _findings(code, language, path=path) == ()


def test_raise_and_throw_bodies_still_report_tautologies() -> None:
    python = "def test_raised():\n    raise AssertionError\n    assert 1 == 1\n"
    javascript = 'it("raised", () => {\n  throw error;\n  expect(x).toBe(x);\n});\n'
    java = (
        "class SampleTest {\n"
        "  @Test\n"
        "  void raised() {\n"
        "    throw stale;\n"
        "    Assertions.assertTrue(true);\n"
        "  }\n"
        "}\n"
    )
    assert _summary(_findings(python, Language.PYTHON)) == [("test.tautology", 3, "error")]
    assert _summary(_findings(javascript, Language.JAVASCRIPT)) == [("test.tautology", 3, "error")]
    assert _summary(_findings(java, Language.JAVA)) == [("test.tautology", 5, "error")]


def test_javascript_parameter_comments_do_not_change_argument_counts() -> None:
    code = 'it("x", () => {\n  assert(/* rationale */ true);\n});\n'
    assert _summary(_findings(code, Language.JAVASCRIPT)) == [("test.tautology", 2, "error")]


def test_java_parameter_comments_do_not_change_argument_counts() -> None:
    code = (
        "class SampleTest {\n"
        "  @Test\n"
        "  void checked() {\n"
        "    Assertions.assertTrue(/* rationale */ true);\n"
        "  }\n"
        "}\n"
    )
    assert _summary(_findings(code, Language.JAVA)) == [("test.tautology", 4, "error")]


def test_javascript_nested_function_bodies_count_for_the_outer_test() -> None:
    with_assertion = (
        'it("outer", () => {\n  const inner = () => {\n    expect(x).toBe(x);\n  };\n});\n'
    )
    with_call = 'it("outer", () => {\n  const inner = () => {\n    helper();\n  };\n});\n'
    assert _summary(_findings(with_assertion, Language.JAVASCRIPT)) == [
        ("test.tautology", 3, "error")
    ]
    assert _findings(with_call, Language.JAVASCRIPT) == ()


def test_python_nested_function_bodies_count_for_the_outer_test() -> None:
    with_assertion = "def test_outer():\n    def inner():\n        assert 1 == 1\n"
    with_call = "def test_outer():\n    def inner():\n        helper()\n"
    assert _summary(_findings(with_assertion, Language.PYTHON)) == [("test.tautology", 3, "error")]
    assert _findings(with_call, Language.PYTHON) == ()


@pytest.mark.parametrize(
    "statement",
    ["assertNote(true, y);", "_assert_notice(true, y);", "assertAllFalse(true, y);"],
)
def test_javascript_negated_names_still_count_as_assertions(statement: str) -> None:
    code = 'it("x", () => {\n  ' + statement + "\n});\n"
    assert _findings(code, Language.JAVASCRIPT) == ()
    root = _root(JavaScriptLanguage().parser, Language.JAVASCRIPT, "sample.test.js", code)
    (declaration,) = JavaScriptTestSyntax().declarations(root)
    (assertion,) = JavaScriptTestSyntax().assertions(declaration.node)
    assert assertion.kind == "assertion"
    assert assertion.mirrored is False
    assert assertion.always_true is False


def test_python_assertion_kinds_are_anchored() -> None:
    code = (
        "def test_sample():\n"
        "    assert value == 1\n"
        "    with pytest.raises(ValueError):\n"
        "        run()\n"
    )
    root = _root(PythonLanguage().parser, Language.PYTHON, "tests/test_sample.py", code)
    assert _assertion_kinds(PythonTestSyntax(), root) == ("assertion", "raises")


def test_javascript_assertion_kinds_are_anchored() -> None:
    code = (
        'it("x", () => {\n'
        "  expect(value).toBe(1);\n"
        "  expect(value).toContain(1);\n"
        "  assert(value);\n"
        "});\n"
    )
    root = _root(JavaScriptLanguage().parser, Language.JAVASCRIPT, "sample.test.js", code)
    assert _assertion_kinds(JavaScriptTestSyntax(), root) == ("matcher", "matcher", "assertion")


def test_go_assertion_kinds_are_anchored() -> None:
    code = (
        "package sample\n\n"
        'import "testing"\n\n'
        "func TestChecked(t *testing.T) {\n"
        '    t.Errorf("bad")\n'
        "}\n"
    )
    root = _root(GoLanguage().parser, Language.GO, "sample_test.go", code)
    assert _assertion_kinds(GoTestSyntax(), root) == ("fatal",)


def test_java_assertion_kinds_are_anchored() -> None:
    code = (
        "class SampleTest {\n"
        "  @Test\n"
        "  void checked() {\n"
        "    assert value == 1;\n"
        "    Assertions.assertTrue(value);\n"
        "  }\n"
        "}\n"
    )
    root = _root(JavaLanguage().parser, Language.JAVA, "SampleTest.java", code)
    assert _assertion_kinds(JavaTestSyntax(), root) == ("assertion", "assertion")


def test_python_control_statement_kinds_are_anchored() -> None:
    code = (
        "def test_flow(values, handle):\n"
        "    with handle:\n"
        "        pass\n"
        "    for value in values:\n"
        "        pass\n"
        "    while values:\n"
        "        break\n"
        "    if values:\n"
        "        pass\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError:\n"
        "        pass\n"
        "    match values:\n"
        "        case 1:\n"
        "            pass\n"
        "    raise AssertionError\n"
    )
    root = _root(PythonLanguage().parser, Language.PYTHON, "tests/test_sample.py", code)
    assert _control_types(PythonTestSyntax(), root) == (
        "with_statement",
        "for_statement",
        "while_statement",
        "if_statement",
        "try_statement",
        "match_statement",
        "raise_statement",
    )


def test_javascript_control_statement_kinds_are_anchored() -> None:
    code = (
        'it("flow", () => {\n'
        "  if (x) { y(); }\n"
        "  for (let i = 0; i < 1; i++) { y(); }\n"
        "  for (const key in object) { y(); }\n"
        "  for (const value of values) { y(); }\n"
        "  while (x) { y(); }\n"
        "  do { y(); } while (x);\n"
        "  try { y(); } catch (error) { y(); }\n"
        "  switch (x) { case 1: y(); }\n"
        "  with (object) { y(); }\n"
        "  throw error;\n"
        "});\n"
    )
    root = _root(JavaScriptLanguage().parser, Language.JAVASCRIPT, "sample.test.js", code)
    assert _control_types(JavaScriptTestSyntax(), root) == (
        "if_statement",
        "for_statement",
        "for_in_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "switch_statement",
        "with_statement",
        "throw_statement",
    )


def test_go_control_statement_kinds_are_anchored() -> None:
    code = (
        "package sample\n\n"
        'import "testing"\n\n'
        "func TestFlow(t *testing.T) {\n"
        '    if x { t.Error("x") }\n'
        '    for i := 0; i < 1; i++ { t.Error("x") }\n'
        '    switch x { case 1: t.Error("x") }\n'
        "    switch value := x.(type) { case int: _ = value }\n"
        "    select { case <-ch: }\n"
        "}\n"
    )
    root = _root(GoLanguage().parser, Language.GO, "sample_test.go", code)
    assert _control_types(GoTestSyntax(), root) == (
        "if_statement",
        "for_statement",
        "expression_switch_statement",
        "type_switch_statement",
        "select_statement",
    )


def test_java_control_statement_kinds_are_anchored() -> None:
    code = (
        "class SampleTest {\n"
        "  @Test\n"
        "  void flow() {\n"
        "    if (x) { y(); }\n"
        "    for (int i = 0; i < 1; i++) { y(); }\n"
        "    for (String value : values) { y(); }\n"
        "    while (x) { y(); }\n"
        "    do { y(); } while (x);\n"
        "    try { y(); } catch (Exception error) { y(); }\n"
        "    try (var reader = open()) { y(); }\n"
        "    switch (x) { case 1: y(); }\n"
        "    synchronized (lock) { y(); }\n"
        "    throw stale;\n"
        "  }\n"
        "}\n"
    )
    root = _root(JavaLanguage().parser, Language.JAVA, "SampleTest.java", code)
    assert _control_types(JavaTestSyntax(), root) == (
        "if_statement",
        "for_statement",
        "enhanced_for_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "try_with_resources_statement",
        "switch_expression",
        "synchronized_statement",
        "throw_statement",
    )
