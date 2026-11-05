"""Behavioral contracts for swallowed handlers and literal coalescing chains."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from tree_sitter import Node

from pluvy.cli import main
from pluvy.diagnostics import Finding, Report
from pluvy.engine import check
from pluvy.languages.javascript.failure import JavaScriptFailureSyntax
from pluvy.languages.typescript.plugin import TsxLanguage, TypeScriptLanguage
from pluvy.parsing.treesitter import node_text
from pluvy.plugins.builtins import builtin_analyzers
from pluvy.policy.models import Policy
from pluvy.semantics.failure import FallbackChain
from pluvy.semantics.failure_options import FailureHandlingOptions
from pluvy.source import Language, Source

_FLOW_RULES = frozenset({"flow.swallow", "flow.fallback"})
_PATHS = {
    Language.PYTHON: "sample.py",
    Language.JAVASCRIPT: "sample.js",
    Language.TYPESCRIPT: "sample.ts",
    Language.TSX: "sample.tsx",
    Language.JAVA: "Sample.java",
    Language.GO: "sample.go",
}

_DOUZ = """def build_dashboard():
    try:
        try:
            config = load_config()
        except Exception as e:
            print(f"Failed to load config: {e}")
            config = {}

        try:
            users = fetch_users()
        except Exception as e:
            print(f"Failed to fetch users: {e}")
            users = []

        try:
            total = sum(user.get("score", 0) for user in users)
        except Exception as e:
            print(f"Failed to sum users: {e}")
            total = 0

        return {"total": total, "config": config}
    except Exception as e:
        print(f"Failed to build dashboard: {e}")
        return {}
"""

_FALLBACK = """export async function buildRevenuePanel() {
  const raw = await fetch("/api/revenue")
    .then((res) => res.json())
    .catch(() => null);

  const payload =
    (((raw ?? {}) as Record<string, unknown>)?.data ?? {}) as Record<string, unknown>;

  const summary =
    ((((payload ?? {}) as Record<string, unknown>).summary ?? {}) ??
      {}) as Record<string, unknown>;

  return {
    total:
      Number((((summary ?? {}) as Record<string, unknown>).total ?? 0) ?? 0) ?? 0,
    growth:
      Number((((summary ?? {}) as Record<string, unknown>).growth ?? 0) ?? 0) ?? 0,
    trend:
      ((((payload ?? {}) as Record<string, unknown>).trend ?? []) ?? []) as unknown[],
  };
}
"""


def _source(
    code: str,
    language: Language,
    path: str | None = None,
) -> Source:
    return Source(path or _PATHS[language], code.encode(), language)


def _findings(
    code: str,
    language: Language,
    policy: Policy | None = None,
    path: str | None = None,
) -> tuple[Finding, ...]:
    return tuple(check(_source(code, language, path), policy or Policy()))


def _flow_findings(
    code: str,
    language: Language,
    policy: Policy | None = None,
    path: str | None = None,
) -> tuple[Finding, ...]:
    return tuple(
        finding
        for finding in _findings(code, language, policy, path)
        if finding.rule in _FLOW_RULES
    )


def _summary(findings: tuple[Finding, ...]) -> list[tuple[str, int, str]]:
    return [(finding.rule, finding.line, finding.severity) for finding in findings]


def _root(code: str, language: Language = Language.TYPESCRIPT) -> Node:
    parser = {
        Language.TYPESCRIPT: TypeScriptLanguage().parser,
        Language.TSX: TsxLanguage().parser,
    }[language]
    return parser.tree(_source(code, language)).root_node


def _chains(code: str, language: Language = Language.TYPESCRIPT) -> tuple[FallbackChain, ...]:
    return JavaScriptFailureSyntax().fallback_chains(_root(code, language))


def test_douz_sample_reports_every_wide_handler() -> None:
    findings = _flow_findings(_DOUZ, Language.PYTHON)
    assert _summary(findings) == [
        ("flow.swallow", 5, "error"),
        ("flow.swallow", 11, "error"),
        ("flow.swallow", 17, "error"),
        ("flow.swallow", 22, "error"),
    ]
    assert all(finding.message.startswith("The except Exception handler") for finding in findings)


@pytest.mark.parametrize("language", [Language.TYPESCRIPT, Language.TSX])
def test_fallback_sample_reports_two_literal_chains_and_one_swallowed_handler(
    language: Language,
) -> None:
    findings = _flow_findings(_FALLBACK, language)
    assert _summary(findings) == [
        ("flow.swallow", 2, "error"),
        ("flow.fallback", 15, "error"),
        ("flow.fallback", 17, "error"),
    ]
    swallows = tuple(finding for finding in findings if finding.rule == "flow.swallow")
    assert swallows[0].message.startswith("The .catch handler")
    fallbacks = tuple(finding for finding in findings if finding.rule == "flow.fallback")
    assert all(
        finding.message.startswith("The coalescing chain has 4 operators") for finding in fallbacks
    )


def test_total_expression_snapshot_locks_the_chain_definition() -> None:
    code = (
        "const total = Number((((summary ?? {}) as Record<string, unknown>).total "
        "?? 0) ?? 0) ?? 0;\n"
    )
    (chain,) = _chains(code)
    assert chain.operators == 4
    assert node_text(chain.node) == "summary ?? {}"
    assert [default.literal for default in chain.defaults] == [True, True, True, True]
    assert {node_text(default.node) for default in chain.defaults} == {"{}", "0"}


@pytest.mark.parametrize(
    ("expression", "operators"),
    [
        ("((a ?? b)) ?? c", 2),
        ("(a ?? b) as R", 1),
        ("((a ?? b) as R).x ?? c", 2),
        ("(a ?? b)?.x ?? c", 2),
        ("Number((a ?? b)) ?? c", 2),
        ("Number(((a ?? b) ?? c)) ?? d", 3),
        ("(a ?? b).map(f) ?? c", 2),
    ],
)
def test_coalescing_traversal_collects_parenthesized_as_member_and_call_operands(
    expression: str, operators: int
) -> None:
    (chain,) = _chains(f"const value = {expression};\n")
    assert chain.operators == operators


@pytest.mark.parametrize(
    ("expression", "operators"),
    [
        ("x ? (a ?? b) : (c ?? d)", (1, 1)),
        ("x ?? (y = z ?? w)", (1, 1)),
        ("fn(a ?? b) ?? (() => c ?? d)", (2, 1)),
        ("a ?? (b || c)", (1,)),
        ("a + (b ?? c)", (1,)),
    ],
)
def test_other_operators_and_function_bodies_break_the_chain(
    expression: str, operators: tuple[int, ...]
) -> None:
    chains = _chains(f"const value = {expression};\n")
    assert tuple(chain.operators for chain in chains) == operators


def test_arrow_function_body_owns_an_independent_chain() -> None:
    chains = _chains("const value = fn() ?? (() => a ?? b ?? c);\n")
    assert tuple(chain.operators for chain in chains) == (1, 2)
    assert node_text(chains[1].node) == "a ?? b"


@pytest.mark.parametrize(
    ("code", "reported"),
    [
        ("const value = a ?? 0 ?? 0 ?? 0;\n", False),
        ("const value = a ?? 0 ?? 0 ?? 0 ?? 0;\n", True),
        ("const value = a ?? 0 ?? 0 ?? 0 ?? value;\n", False),
        ("const value = a ?? (0 as any) ?? 0 ?? 0 ?? 0;\n", False),
        ("const value = a ?? (0) ?? 0 ?? 0 ?? 0;\n", False),
        ("const value = a ?? null ?? undefined ?? null ?? undefined;\n", False),
        ("const value = a ?? b || c;\n", False),
        ("const value = a || b || c || d;\n", False),
        ("const value = a ? b : c;\n", False),
    ],
)
def test_fallback_requires_a_long_chain_of_bare_literal_defaults(code: str, reported: bool) -> None:
    assert bool(_flow_findings(code, Language.TYPESCRIPT)) is reported


def test_python_or_is_not_a_fallback_chain() -> None:
    assert _flow_findings("value = a or b or c or d\n", Language.PYTHON) == ()


@pytest.mark.parametrize(
    ("code", "reported"),
    [
        ("try:\n    work()\nexcept:\n    pass\n", True),
        ("try:\n    work()\nexcept ValueError:\n    pass\n", False),
        ("try:\n    work()\nexcept Exception:\n    raise\n", False),
        ("try:\n    work()\nexcept Exception as error:\n    raise error\n", False),
        ("try:\n    work()\nexcept Exception as error:\n    raise Other() from error\n", False),
        ("try:\n    work()\nexcept BaseException as error:\n    pass\n", True),
        ("try:\n    work()\nexcept (ValueError, Exception) as error:\n    pass\n", True),
        ("try:\n    work()\nexcept (ValueError, TypeError):\n    pass\n", False),
        (
            "try:\n    work()\nexcept Exception as error:\n"
            "    def retry():\n        raise error\n    retry()\n",
            False,
        ),
    ],
)
def test_python_wide_capture_requires_no_rethrow(code: str, reported: bool) -> None:
    assert bool(_flow_findings(code, Language.PYTHON)) is reported


@pytest.mark.parametrize(
    ("code", "reported"),
    [
        (
            "class A { void run() { try { work(); } catch (Exception e) { log(e); } } }",
            True,
        ),
        (
            "class A { void run() { try { work(); } catch (Throwable e) { log(e); } } }",
            True,
        ),
        (
            "class A { void run() { try { work(); } "
            "catch (RuntimeException | Exception e) { log(e); } } }",
            True,
        ),
        (
            "class A { void run() { try { work(); } "
            "catch (IOException | SQLException e) { log(e); } } }",
            False,
        ),
        (
            "class A { void run() { try { work(); } catch (Exception e) { throw e; } } }",
            False,
        ),
        (
            "class A { void run() { try { work(); } "
            "catch (Exception e) { throw new RuntimeException(e); } } }",
            False,
        ),
    ],
)
def test_java_wide_capture_requires_no_rethrow(code: str, reported: bool) -> None:
    assert bool(_flow_findings(code, Language.JAVA)) is reported


@pytest.mark.parametrize(
    ("code", "reported"),
    [
        ("try { work() } catch (e) { log(e) }", True),
        ("try { work() } catch { log(1) }", True),
        ("try { work() } catch (e) { throw e }", False),
        ("promise.catch(() => null);", True),
        ("promise.catch(e => { log(e) });", True),
        ("promise.catch(unwrap);", False),
        ("promise.catch(e => { throw e });", False),
    ],
)
def test_javascript_capture_requires_no_rethrow(code: str, reported: bool) -> None:
    assert bool(_flow_findings(code, Language.JAVASCRIPT)) is reported


def test_go_registers_no_failure_flow_rules() -> None:
    code = "package sample\n\nfunc run() {\n\tif err := work(); err != nil {\n\t\treturn\n\t}\n}\n"
    assert _flow_findings(code, Language.GO) == ()


def test_each_analyzer_registers_only_the_flow_diagnostics_it_emits() -> None:
    registered = {
        analyzer.name: frozenset(rule for rule in analyzer.rule_ids if rule in _FLOW_RULES)
        for analyzer in builtin_analyzers()
    }
    assert registered == {
        "builtin.python": frozenset({"flow.swallow"}),
        "builtin.go": frozenset(),
        "builtin.javascript": _FLOW_RULES,
        "builtin.typescript": _FLOW_RULES,
        "builtin.tsx": _FLOW_RULES,
        "builtin.java": frozenset({"flow.swallow"}),
    }


def test_call_arguments_connect_coalescing_operators_into_one_chain() -> None:
    findings = _flow_findings("f(a ?? 0, b ?? 0, c ?? 0, d ?? 0);\n", Language.JAVASCRIPT)
    assert _summary(findings) == [("flow.fallback", 1, "error")]
    assert findings[0].message.startswith("The coalescing chain has 4 operators")


def test_object_literal_defaults_stay_out_of_the_surrounding_chain() -> None:
    findings = _flow_findings(
        "f(a ?? 0, { x: b ?? 0, y: c ?? 0, z: d ?? 0 });\n", Language.JAVASCRIPT
    )
    assert findings == ()


def test_tsx_reuses_the_javascript_capture_and_fallback_interpretation() -> None:
    code = "try { work(); } catch { log(1); }\nconst value = a ?? 0 ?? 0 ?? 0 ?? 0;\n"
    assert _summary(_flow_findings(code, Language.TSX)) == [
        ("flow.swallow", 1, "error"),
        ("flow.fallback", 2, "error"),
    ]


def test_python_and_java_have_no_fallback_diagnostic() -> None:
    python = _flow_findings("value = a or b or c or d\n", Language.PYTHON)
    java = _flow_findings("class A { Object value = a == null ? b : c; }", Language.JAVA)
    assert python == ()
    assert java == ()


def test_next_line_suppression_applies_to_swallow() -> None:
    code = (
        "try:\n"
        "    work()\n"
        "# pluvy: ignore-next-line flow.swallow -- Reviewed exception boundary.\n"
        "except Exception as error:\n"
        "    log(error)\n"
    )
    assert _flow_findings(code, Language.PYTHON) == ()


def test_next_line_suppression_applies_to_fallback() -> None:
    code = (
        "// pluvy: ignore-next-line flow.fallback -- Reviewed default chain.\n"
        "const value = a ?? 0 ?? 0 ?? 0 ?? 0;\n"
    )
    assert _flow_findings(code, Language.TYPESCRIPT) == ()


def test_each_diagnostic_has_its_own_suppression_target() -> None:
    code = (
        "// pluvy: ignore-next-line flow.swallow -- Reviewed exception boundary.\n"
        "try { work(); } catch { log(1); }\n"
        "const value = a ?? 0 ?? 0 ?? 0 ?? 0;\n"
    )
    assert _summary(_flow_findings(code, Language.TYPESCRIPT)) == [("flow.fallback", 3, "error")]


def test_configured_max_chain_is_inclusive() -> None:
    policy = Policy.model_validate_json('{"checkers":{"flow.handling":{"max_chain":2}}}')
    assert _flow_findings("const value = a ?? 0 ?? 0;\n", Language.TYPESCRIPT, policy) == ()
    reported = _flow_findings("const value = a ?? 0 ?? 0 ?? 0;\n", Language.TYPESCRIPT, policy)
    assert _summary(reported) == [("flow.fallback", 1, "error")]
    assert reported[0].message.startswith("The coalescing chain has 3 operators")


@pytest.mark.parametrize(
    "options",
    ['{"max_chain":0}', '{"max_chain":-1}', '{"max_chain":true}', '{"unknown":1}'],
)
def test_flow_handling_options_reject_invalid_values(options: str) -> None:
    with pytest.raises(ValidationError):
        Policy.model_validate_json('{"checkers":{"flow.handling":' + options + "}}")


def test_options_constructor_requires_a_positive_bound() -> None:
    with pytest.raises(ValidationError):
        FailureHandlingOptions(max_chain=0)


@pytest.mark.parametrize(
    ("code", "language"),
    [
        (
            "def run():\n    try:\n        work()\n    except Exception as error:\n        pass\n",
            Language.PYTHON,
        ),
        (
            "function run() {\n  try { work(); } catch (error) { log(1); }\n}\n",
            Language.JAVASCRIPT,
        ),
        (
            "class Sample {\n  void run() {\n"
            "    try { work(); } catch (Exception error) { }\n  }\n}\n",
            Language.JAVA,
        ),
    ],
)
def test_capture_bindings_are_not_parameters(code: str, language: Language) -> None:
    findings = tuple(
        finding for finding in _findings(code, language) if finding.rule == "unused.parameter"
    )
    assert findings == ()


def _write_project(root: Path, policy: str, source: str) -> None:
    (root / ".pluvy").mkdir()
    (root / ".pluvy/pluvy.json").write_text(policy)
    (root / "app.ts").write_text(source)


def test_cli_reports_error_severity_and_exit_status_for_a_swallowed_handler(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(
        tmp_path,
        "{}\n",
        "try { work(); } catch { log(1); }\n",
    )
    assert main(["--root", str(tmp_path), "--all", "--format", "json"]) == 1
    report = Report.model_validate_json(capsys.readouterr().out)
    findings = tuple(finding for finding in report.findings if finding.rule == "flow.swallow")
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert (findings[0].path, findings[0].line) == ("app.ts", 1)


def test_disabling_flow_handling_removes_both_diagnostics_and_reports_the_switch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(
        tmp_path,
        '{"checkers":{"flow.handling":{"enabled":false}}}\n',
        "try { work(); } catch { log(1); }\nconst value = a ?? 0 ?? 0 ?? 0 ?? 0;\n",
    )
    assert main(["--root", str(tmp_path), "--all", "--format", "json"]) == 0
    report = Report.model_validate_json(capsys.readouterr().out)
    assert report.findings == ()
    assert report.disabled_checkers == ("flow.handling",)
