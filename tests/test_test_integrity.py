"""Behavioral contracts for tautological and vacuous tests across grammars."""

import pytest
from pydantic import ValidationError

from pluvy.diagnostics import Finding
from pluvy.engine import check
from pluvy.policy.models import Policy
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
