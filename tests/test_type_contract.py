"""Behavioral contracts for TypeScript nullable and union type limits."""

import pytest
from pydantic import ValidationError
from tree_sitter import Node

from pluvy.diagnostics import Finding
from pluvy.engine import check
from pluvy.languages.javascript.plugin import JavaScriptLanguage
from pluvy.languages.typescript.plugin import TsxLanguage, TypeScriptLanguage
from pluvy.parsing.treesitter import TreeParser, field, walk
from pluvy.plugins.builtins import builtin_analyzers
from pluvy.policy.models import Policy
from pluvy.source import Language, Source

_CONTRACT_RULES = frozenset({"type.nullable", "type.union"})
_PATHS = {
    Language.JAVASCRIPT: "sample.js",
    Language.TYPESCRIPT: "sample.ts",
    Language.TSX: "sample.tsx",
}
_PARSERS = {
    Language.JAVASCRIPT: JavaScriptLanguage().parser,
    Language.TYPESCRIPT: TypeScriptLanguage().parser,
    Language.TSX: TsxLanguage().parser,
}

_NULL = """type CreateInvoiceInput = {
  id?: string | null | undefined;
  userId?: string | null | undefined;
  amount?: number | null | undefined;
  currency?: string | null | undefined;
  metadata?: {
    source?: string | null | undefined;
    region?: string | null | undefined;
  } | null | undefined;
} | null | undefined;

export function createInvoice(input?: CreateInvoiceInput | null | undefined) {
  return persistInvoice({
    id: input?.id ?? null,
    userId: input?.userId ?? null,
    amount: input?.amount ?? null,
    currency: input?.currency ?? null,
    metadata: input?.metadata ?? null,
  });
}
"""

_UNITED_TYPES = """type MaybePayload =
  | string
  | number
  | boolean
  | null
  | undefined
  | {
      data:
        | string
        | number
        | {
            value?: string | number | unknown | null;
          }
        | unknown
        | null;
      meta?:
        | Record<string, unknown>
        | string
        | number
        | null
        | undefined;
    }
  | unknown;

export function readPayload(input: MaybePayload) {
  if (typeof input === "string") return input;
  if (typeof input === "number") return String(input);
  if (typeof input === "boolean") return String(input);
  if (input && typeof input === "object" && "data" in input) return String(input.data);
  return "";
}
"""

_SIGNALS = """type Payload = A | B | C;
type Declaration = {
  a?: string;
  b?: string;
  c?: string;
};
function run(value) {
  value ?? null;
  value ?? undefined;
  value ?? null;
}
"""

_OVER_LIMITS = """type Payload = A | B | C | D | E;
type Declaration = {
  a?: string;
  b?: string;
  c?: string;
  d?: string;
};
function run(value) {
  value ?? null;
  value ?? undefined;
  value ?? null;
  value ?? undefined;
}
"""


def _source(code: str, language: Language, path: str | None = None) -> Source:
    return Source(path or _PATHS[language], code.encode(), language)


def _findings(
    code: str,
    language: Language = Language.TYPESCRIPT,
    policy: Policy | None = None,
    path: str | None = None,
) -> tuple[Finding, ...]:
    return tuple(check(_source(code, language, path), policy or Policy()))


def _contract_findings(
    code: str,
    language: Language = Language.TYPESCRIPT,
    policy: Policy | None = None,
) -> tuple[Finding, ...]:
    return tuple(
        finding for finding in _findings(code, language, policy) if finding.rule in _CONTRACT_RULES
    )


def _summary(findings: tuple[Finding, ...]) -> list[tuple[str, int, int, str]]:
    return [(finding.rule, finding.line, finding.column, finding.severity) for finding in findings]


def _parser(language: Language) -> TreeParser:
    return _PARSERS[language]


def _root(
    code: str,
    language: Language = Language.TYPESCRIPT,
    path: str | None = None,
) -> Node:
    parser = _parser(language)
    return parser.tree(_source(code, language, path)).root_node


def _nodes(root: Node, *types: str) -> tuple[Node, ...]:
    return tuple(node for node in walk(root) if node.type in types)


def _required_field(node: Node, name: str) -> Node:
    value = field(node, name)
    assert value is not None
    return value


def test_null_sample_reports_one_declaration_and_one_function_domain() -> None:
    findings = _contract_findings(_NULL)
    assert _summary(findings) == [
        ("type.nullable", 2, 3, "error"),
        ("type.nullable", 14, 9, "error"),
    ]
    assert all(finding.message.startswith("5 ") for finding in findings)


def test_united_types_sample_reports_the_top_level_union_once() -> None:
    findings = _findings(_UNITED_TYPES)
    unions = tuple(finding for finding in findings if finding.rule == "type.union")
    assert _summary(unions) == [("type.union", 2, 3, "error")]
    assert any(finding.rule == "type.broad" for finding in findings)


def test_record_unknown_argument_is_broad_while_record_string_is_not() -> None:
    broad = _findings("type Row = Record<string, unknown>;\n")
    assert _summary(broad) == [("type.broad", 1, 27, "error")]
    assert _contract_findings("type Row = Record<string, unknown>;\n") == ()
    assert _findings("type Row = Record<string, string>;\n") == ()


@pytest.mark.parametrize(("count", "reported"), [(3, False), (4, True)])
def test_optional_member_limit_is_strict(count: int, reported: bool) -> None:
    members = "".join(f"  field{index}?: string;\n" for index in range(count))
    findings = _contract_findings("type Payload = {\n" + members + "};\n")
    assert bool(findings) is reported
    if reported:
        assert findings[0].message.startswith(f"{count} optional")


@pytest.mark.parametrize(("count", "reported"), [(3, False), (4, True)])
def test_explicit_nullable_members_share_the_declaration_limit(count: int, reported: bool) -> None:
    members = "".join(f"  field{index}: string | null;\n" for index in range(count))
    findings = _contract_findings("type Payload = {\n" + members + "};\n")
    assert bool(findings) is reported
    if reported:
        assert findings[0].message.startswith(f"{count} optional")


def test_member_both_optional_and_nullable_counts_once() -> None:
    members = "".join(f"  field{index}?: string | null | undefined;\n" for index in range(4))
    findings = _contract_findings("type Payload = {\n" + members + "};\n")
    assert _summary(findings) == [("type.nullable", 2, 3, "error")]
    assert findings[0].message.startswith("4 ")


@pytest.mark.parametrize("annotation", ["null", "undefined"])
def test_direct_nullish_annotation_counts_as_explicitly_nullable(
    annotation: str,
) -> None:
    members = "".join(f"  field{index}: {annotation};\n" for index in range(4))
    findings = _contract_findings("type Payload = {\n" + members + "};\n")
    assert _summary(findings) == [("type.nullable", 2, 3, "error")]
    assert findings[0].message.startswith("4 ")


def test_interface_declaration_is_an_independent_declaration_domain() -> None:
    code = "interface Payload {\n  a?: string;\n  b?: string;\n  c?: string;\n  d?: string;\n}\n"
    findings = _contract_findings(code)
    assert _summary(findings) == [("type.nullable", 2, 3, "error")]
    assert findings[0].message.startswith("4 ")


def test_nested_object_type_is_an_independent_declaration_domain() -> None:
    code = (
        "type Payload = {\n"
        "  outer?: string;\n"
        "  nested?: {\n"
        "    a?: string;\n"
        "    b?: string;\n"
        "    c?: string;\n"
        "    d?: string;\n"
        "  };\n"
        "};\n"
    )
    findings = _contract_findings(code)
    assert _summary(findings) == [("type.nullable", 4, 5, "error")]
    assert findings[0].message.startswith("4 ")


@pytest.mark.parametrize(("count", "reported"), [(3, False), (4, True)])
def test_nullish_fallback_limit_is_strict(count: int, reported: bool) -> None:
    statements = "".join("  value ?? null;\n" for _ in range(count))
    findings = _contract_findings("function run(value) {\n" + statements + "}\n")
    assert bool(findings) is reported
    if reported:
        assert findings[0].message.startswith(f"{count} bare")


def test_module_level_fallbacks_are_not_counted() -> None:
    code = "".join("const fallback = value ?? null;\n" for _ in range(4))
    assert _contract_findings(code) == ()


@pytest.mark.parametrize(
    "code",
    [
        "const run = (value) => {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "};\n",
        "const run = (value) => value ?? null ?? undefined ?? value ?? null ?? undefined;\n",
        "const run = function (value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "};\n",
        "function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "}\n",
        "function* run(value) {\n"
        "  yield value ?? null;\n"
        "  yield value ?? undefined;\n"
        "  yield value ?? null;\n"
        "  yield value ?? undefined;\n"
        "}\n",
        "const run = function* (value) {\n"
        "  yield value ?? null;\n"
        "  yield value ?? undefined;\n"
        "  yield value ?? null;\n"
        "  yield value ?? undefined;\n"
        "};\n",
        "class Sample {\n"
        "  method(value) {\n"
        "    value ?? null;\n"
        "    value ?? undefined;\n"
        "    value ?? null;\n"
        "    value ?? undefined;\n"
        "  }\n"
        "}\n",
    ],
)
def test_every_function_form_owns_its_nullish_fallback_domain(code: str) -> None:
    findings = _contract_findings(code)
    assert len(findings) == 1
    assert findings[0].rule == "type.nullable"


def test_nested_function_body_is_attributed_to_the_inner_function() -> None:
    code = (
        "function outer(value) {\n"
        "  const inner = () => value ?? null ?? undefined ?? value ?? null ?? undefined;\n"
        "  return inner;\n"
        "}\n"
    )
    findings = _contract_findings(code)
    assert [(finding.rule, finding.line) for finding in findings] == [("type.nullable", 2)]


def test_wrapped_default_values_are_not_bare_nullish_fallbacks() -> None:
    code = (
        "function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? (null);\n"
        "  value ?? (undefined as any);\n"
        "  value ?? getDefault();\n"
        "}\n"
    )
    findings = _findings(code)
    assert _contract_findings(code) == ()
    assert any(finding.rule == "type.assertion" for finding in findings)


def test_four_bare_defaults_report_despite_wrapped_defaults() -> None:
    code = (
        "function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? (null as any);\n"
        "  value ?? getDefault();\n"
        "}\n"
    )
    findings = _contract_findings(code)
    assert _summary(findings) == [("type.nullable", 2, 3, "error")]
    assert findings[0].message.startswith("4 bare")


def test_object_literal_fallback_is_neither_nullish_nor_broad() -> None:
    code = (
        "function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? {};\n"
        "}\n"
    )
    findings = _findings(code)
    assert _contract_findings(code) == ()
    assert [finding for finding in findings if finding.rule == "type.broad"] == []
    root = _root("const fallback = value ?? {};\n")
    assert _nodes(root, "object_type") == ()
    assert len(_nodes(root, "object")) == 1


def test_object_literal_fallback_does_not_count_as_a_nullish_default() -> None:
    code = (
        "function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? {};\n"
        "}\n"
    )
    findings = _contract_findings(code)
    assert _summary(findings) == [("type.nullable", 2, 3, "error")]
    assert all(finding.rule != "type.broad" for finding in _findings(code))


@pytest.mark.parametrize(("count", "reported"), [(4, False), (5, True)])
def test_union_member_limit_is_strict(count: int, reported: bool) -> None:
    members = " | ".join(f"Type{index}" for index in range(count))
    findings = _contract_findings(f"type Payload = {members};\n")
    assert bool(findings) is reported
    if reported:
        assert _summary(findings) == [("type.union", 1, 16, "error")]
        assert findings[0].message.startswith(f"Union has {count} non-nullish")


def test_union_excludes_nullish_members_before_counting() -> None:
    findings = _contract_findings("type Payload = A | B | C | D | E | null | undefined;\n")
    assert _summary(findings) == [("type.union", 1, 16, "error")]
    assert findings[0].message.startswith("Union has 5 non-nullish")


def test_union_unknown_member_reports_union_and_broad() -> None:
    findings = _findings("type Payload = A | B | C | D | unknown;\n")
    assert [finding.rule for finding in findings] == ["type.union", "type.broad"]
    assert {finding.line for finding in findings} == {1}


def test_discriminated_union_mapping_and_optional_chain_have_no_contract() -> None:
    code = (
        "type Result =\n"
        '  | { kind: "ok"; value: string }\n'
        '  | { kind: "error"; message: string };\n'
        "type UserRow = { id: string; name: string };\n"
        "type User = { id: string; name: string };\n"
        "function toUser(row: UserRow): User {\n"
        "  return { id: row.id, name: row.name };\n"
        "}\n"
        "function readName(user?: { name: string } | null) {\n"
        "  return user?.name;\n"
        "}\n"
        "function optionalParameter(value?: string) {\n"
        "  return value;\n"
        "}\n"
    )
    assert _contract_findings(code) == ()


def test_tsx_reports_the_same_contract() -> None:
    code = "type Payload = {\n  a?: string;\n  b?: string;\n  c?: string;\n  d?: string;\n};\n"
    assert _summary(_contract_findings(code, Language.TSX)) == [("type.nullable", 2, 3, "error")]


def test_javascript_files_do_not_register_the_contract_checker() -> None:
    code = (
        "function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "}\n"
    )
    assert _contract_findings(code, Language.JAVASCRIPT) == ()
    analyzers = {analyzer.definition.language: analyzer for analyzer in builtin_analyzers()}
    assert _CONTRACT_RULES.isdisjoint(analyzers[Language.JAVASCRIPT].rule_ids)


def test_type_contract_defaults_and_partial_options() -> None:
    options = Policy().checkers.type_contract
    assert (options.max_members, options.optional_fields, options.null_defaults) == (
        4,
        3,
        3,
    )
    partial = Policy.model_validate_json('{"checkers":{"type.contract":{"optional_fields":2}}}')
    assert partial.checkers.type_contract.optional_fields == 2
    assert partial.checkers.type_contract.max_members == 4
    assert partial.checkers.type_contract.null_defaults == 3


def test_defaults_pass_the_signal_boundary() -> None:
    assert _contract_findings(_SIGNALS) == ()


@pytest.mark.parametrize(
    ("options", "rule", "message"),
    [
        ('{"optional_fields":2}', "type.nullable", "optional or nullable properties"),
        ('{"null_defaults":2}', "type.nullable", "bare nullish fallbacks"),
        ('{"max_members":2}', "type.union", "non-nullish members"),
    ],
)
def test_threshold_changes_only_its_signal(options: str, rule: str, message: str) -> None:
    policy = Policy.model_validate_json('{"checkers":{"type.contract":' + options + "}}")
    findings = _contract_findings(_SIGNALS, policy=policy)
    assert len(findings) == 1
    assert findings[0].rule == rule
    assert message in findings[0].message


@pytest.mark.parametrize(
    "options",
    [
        '{"max_members":0}',
        '{"max_members":true}',
        '{"max_members":"4"}',
        '{"optional_fields":0}',
        '{"null_defaults":0}',
        '{"unknown":1}',
        "null",
    ],
)
def test_invalid_type_contract_options_are_rejected(options: str) -> None:
    with pytest.raises(ValidationError):
        Policy.model_validate_json('{"checkers":{"type.contract":' + options + "}}")


def test_invalid_options_are_rejected_even_when_disabled() -> None:
    with pytest.raises(ValidationError):
        Policy.model_validate_json(
            '{"checkers":{"type.contract":{"enabled":false,"max_members":0}}}'
        )


def test_disabling_type_contract_disables_both_diagnostics() -> None:
    policy = Policy.model_validate_json('{"checkers":{"type.contract":{"enabled":false}}}')
    assert policy.checkers.disabled_checkers() == {"type.contract"}
    assert policy.checkers.disabled_rules() == {"type.nullable", "type.union"}
    assert _contract_findings(_OVER_LIMITS, policy=policy) == ()
    assert _contract_findings(_OVER_LIMITS) != ()


@pytest.mark.parametrize("key", ["type.nullable", "type.union"])
def test_single_diagnostics_are_not_checker_keys(key: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Policy.model_validate_json('{"checkers":{"' + key + '":{}}}')


def test_next_line_suppression_uses_the_nullable_diagnostic_id() -> None:
    code = (
        "function run(value) {\n"
        "  // pluvy: ignore-next-line type.nullable -- Approved fallback.\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "  value ?? null;\n"
        "  value ?? undefined;\n"
        "}\n"
    )
    assert _contract_findings(code) == ()


def test_next_line_suppression_uses_the_union_diagnostic_id() -> None:
    code = (
        "// pluvy: ignore-next-line type.union -- Approved union.\n"
        "type Payload = A | B | C | D | E;\n"
    )
    assert _contract_findings(code) == ()


def test_union_parse_shape_flattens_left_nesting_and_stops_at_parentheses() -> None:
    code = (
        "type Direct = A | B | C;\ntype Grouped = (A | B | C) | D;\ntype Leading =\n  | A\n  | B;\n"
    )
    root = _root(code)
    unions = _nodes(root, "union_type")
    grouped = next(node for node in unions if node.start_point.row == 1)
    assert [child.type for child in grouped.named_children] == [
        "parenthesized_type",
        "type_identifier",
    ]
    assert grouped.named_children[0].named_children[0].type == "union_type"
    leading = next(node for node in unions if node.start_point.row == 3)
    assert [child.type for child in leading.named_children] == [
        "union_type",
        "type_identifier",
    ]
    assert len(leading.named_children[0].named_children) == 1


def test_property_signature_optional_marker_and_nullable_annotation_shape() -> None:
    code = (
        "type Payload = {\n"
        "  optional?: string;\n"
        "  nullable: string | null;\n"
        "  both?: number | undefined;\n"
        "};\n"
        "interface Contract {\n"
        "  required: string;\n"
        "}\n"
    )
    root = _root(code)
    properties = _nodes(root, "property_signature")
    assert len(properties) == 4
    assert any(child.type == "?" for child in properties[0].children)
    assert _required_field(properties[0], "type").type == "type_annotation"
    annotation = _required_field(properties[1], "type").named_children[0]
    assert annotation.type == "union_type"
    assert [child.type for child in annotation.named_children] == [
        "predefined_type",
        "literal_type",
    ]
    interface = _nodes(root, "interface_declaration")[0]
    assert _required_field(interface, "body").type == "interface_body"
    assert [child.type for child in _required_field(interface, "body").named_children] == [
        "property_signature"
    ]


def test_nullish_fallback_nodes_are_binary_expressions_with_bare_right_operands() -> None:
    code = (
        "function run(value) {\n"
        "  value ?? null;\n"
        "  value ?? (null);\n"
        "  value ?? (null as any);\n"
        "}\n"
    )
    root = _root(code)
    expressions = _nodes(root, "binary_expression")
    assert [_required_field(node, "operator").type for node in expressions] == ["??", "??", "??"]
    assert [_required_field(node, "right").type for node in expressions] == [
        "null",
        "parenthesized_expression",
        "parenthesized_expression",
    ]


def test_function_body_fields_cover_generator_and_arrow_forms() -> None:
    code = (
        "const arrowExpression = (value) => value;\n"
        "const arrowBlock = (value) => { return value; };\n"
        "function declared(value) { return value; }\n"
        "const expression = function (value) { return value; };\n"
        "function* generatorDeclaration(value) { yield value; }\n"
        "const generatorExpression = function* (value) { yield value; };\n"
        "class Sample { method(value) { return value; } *iterator(value) { yield value; } }\n"
    )
    root = _root(code)
    functions = _nodes(
        root,
        "arrow_function",
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
        "method_definition",
    )
    assert {node.type for node in functions} == {
        "arrow_function",
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
        "method_definition",
    }
    assert all(field(node, "body") is not None for node in functions)
    assert {_required_field(node, "body").type for node in functions} == {
        "identifier",
        "statement_block",
    }
