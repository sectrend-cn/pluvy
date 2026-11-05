"""Independent regression coverage for type.contract parse and suppression edges."""

from pluvy.engine import check
from pluvy.policy.models import Policy
from pluvy.source import Language, Source

_CONTRACT = frozenset({"type.nullable", "type.union"})
_PATHS = {Language.TYPESCRIPT: "sample.ts", Language.TSX: "sample.tsx"}


def _contract_findings(code: str, language: Language) -> list[tuple[str, int, int, str]]:
    path = _PATHS[language]
    return [
        (finding.rule, finding.line, finding.column, finding.severity)
        for finding in check(Source(path, code.encode(), language), Policy())
        if finding.rule in _CONTRACT
    ]


def test_leading_pipe_union_reports_once_at_the_union_node() -> None:
    code = "type Payload =\n  | A\n  | B\n  | C\n  | D\n  | E;\n"
    findings = _contract_findings(code, Language.TYPESCRIPT)
    assert findings == [("type.union", 2, 3, "error")]


def test_tsx_function_domain_and_union_both_report() -> None:
    code = (
        "type Payload = A | B | C | D | E;\n"
        "export function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "}\n"
    )
    assert _contract_findings(code, Language.TSX) == [
        ("type.union", 1, 16, "error"),
        ("type.nullable", 3, 3, "error"),
    ]


def test_declaration_next_line_suppression_matches_the_first_member_anchor() -> None:
    members = "  a?: string;\n  b?: string;\n  c?: string;\n  d?: string;\n"
    unsuppressed = "type Payload = {\n" + members + "};\n"
    assert _contract_findings(unsuppressed, Language.TYPESCRIPT) == [
        ("type.nullable", 2, 3, "error")
    ]
    code = (
        "type Payload = {\n"
        "  // pluvy: ignore-next-line type.nullable -- Approved shape.\n" + members + "};\n"
    )
    assert _contract_findings(code, Language.TYPESCRIPT) == []


def test_tsx_unused_nullable_directive_is_reported_by_suppression() -> None:
    code = "// pluvy: ignore-next-line type.nullable -- Stale directive.\nexport const value = 1;\n"
    findings = [
        (finding.rule, finding.line, finding.column, finding.severity)
        for finding in check(Source("sample.tsx", code.encode(), Language.TSX), Policy())
    ]
    assert ("type.suppression", 1, 1, "error") in findings
