"""Grammar-specific nullable and union contract policy for TypeScript."""

from dataclasses import dataclass

from tree_sitter import Node

from pluvy.analysis.context import TreeContext
from pluvy.analysis.requirements import RuleRequirements
from pluvy.diagnostics import Finding
from pluvy.parsing.treesitter import field, walk
from pluvy.policy.type_options import NULLABLE, TYPE_CONTRACT, UNION

_FUNCTION_TYPES = frozenset(
    {
        "arrow_function",
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
        "method_definition",
    }
)
_DECLARATION_TYPES = frozenset({"interface_declaration", "object_type"})
_NULLISH_TYPES = frozenset({"null", "undefined"})
_COMMENT = "comment"


@dataclass(frozen=True)
class TypeScriptContractRule:
    """Report aggregated nullable declarations and oversized TypeScript unions."""

    name: str = "builtin.types.ts_contract"
    api_version: int = 2
    requirements: RuleRequirements = RuleRequirements()
    rule_ids: tuple[str, ...] = TYPE_CONTRACT.rule_ids

    def check(self, context: TreeContext) -> tuple[Finding, ...]:
        options = context.policy.checkers.type_contract
        findings: list[Finding] = []
        findings.extend(self._declaration_findings(context, options.optional_fields))
        findings.extend(self._default_findings(context, options.null_defaults))
        findings.extend(self._union_findings(context, options.max_members))
        return tuple(findings)

    def _declaration_findings(self, context: TreeContext, maximum: int) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for domain in walk(context.root):
            if domain.type not in _DECLARATION_TYPES:
                continue
            members = self._nullable_members(domain)
            if len(members) > maximum:
                findings.append(
                    self._finding(
                        context,
                        members[0],
                        NULLABLE,
                        f"{len(members)} optional or nullable properties exceed the "
                        f"optional_fields limit of {maximum}; keep required fields required "
                        "or split the shape into distinct contracts",
                    )
                )
        return tuple(findings)

    def _nullable_members(self, domain: Node) -> tuple[Node, ...]:
        body = field(domain, "body") if domain.type == "interface_declaration" else domain
        if body is None:
            return ()
        return tuple(
            member
            for member in body.named_children
            if member.type == "property_signature" and self._nullable_member(member)
        )

    def _nullable_member(self, member: Node) -> bool:
        if any(child.type == "?" for child in member.children):
            return True
        annotation = field(member, "type")
        return annotation is not None and self._nullable_annotation(annotation)

    def _nullable_annotation(self, node: Node) -> bool:
        target = self._unwrap_parenthesized(self._annotation_type(node))
        if target.type == "union_type":
            return any(self._is_nullish(member) for member in self._union_members(target))
        return self._is_nullish(target)

    def _annotation_type(self, node: Node) -> Node:
        if node.type != "type_annotation":
            return node
        return next(
            (child for child in node.named_children if child.type != _COMMENT),
            node,
        )

    def _default_findings(self, context: TreeContext, maximum: int) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for function in walk(context.root):
            if function.type not in _FUNCTION_TYPES:
                continue
            body = field(function, "body")
            if body is None:
                continue
            fallbacks = self._nullish_fallbacks(body)
            if len(fallbacks) > maximum:
                findings.append(
                    self._finding(
                        context,
                        fallbacks[0],
                        NULLABLE,
                        f"{len(fallbacks)} bare nullish fallbacks exceed the null_defaults "
                        f"limit of {maximum}; return a concrete value or represent absence "
                        "once at the owning boundary",
                    )
                )
        return tuple(findings)

    def _nullish_fallbacks(self, body: Node) -> tuple[Node, ...]:
        pending = [body]
        found: list[Node] = []
        while pending:
            node = pending.pop()
            if node.type in _FUNCTION_TYPES:
                continue
            if self._is_nullish_fallback(node):
                found.append(node)
            pending.extend(reversed(node.named_children))
        return tuple(found)

    def _is_nullish_fallback(self, node: Node) -> bool:
        if node.type != "binary_expression":
            return False
        operator = field(node, "operator")
        if operator is None or operator.type != "??":
            return False
        right = field(node, "right")
        return right is not None and self._is_nullish(right)

    def _union_findings(self, context: TreeContext, maximum: int) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for union in walk(context.root):
            if union.type != "union_type" or self._is_union_prefix(union):
                continue
            members = tuple(
                member for member in self._union_members(union) if not self._is_nullish(member)
            )
            if len(members) > maximum:
                findings.append(
                    self._finding(
                        context,
                        union,
                        UNION,
                        f"Union has {len(members)} non-nullish members; maximum is "
                        f"{maximum}. Model distinct shapes as discriminated alternatives",
                    )
                )
        return tuple(findings)

    def _is_union_prefix(self, node: Node) -> bool:
        parent = node.parent
        return parent is not None and parent.type == "union_type"

    def _union_members(self, node: Node) -> tuple[Node, ...]:
        members: list[Node] = []
        current = node
        while current.type == "union_type":
            children = tuple(child for child in current.named_children if child.type != _COMMENT)
            if len(children) == 1:
                members.append(self._unwrap_parenthesized(children[0]))
                break
            if len(children) != 2:
                members.extend(self._unwrap_parenthesized(child) for child in children)
                break
            left, right = children
            members.append(self._unwrap_parenthesized(right))
            if left.type != "union_type":
                members.append(self._unwrap_parenthesized(left))
                break
            current = left
        members.reverse()
        return tuple(members)

    def _unwrap_parenthesized(self, node: Node) -> Node:
        if node.type != "parenthesized_type":
            return node
        return next(
            (child for child in node.named_children if child.type != _COMMENT),
            node,
        )

    def _is_nullish(self, node: Node) -> bool:
        return node.type in _NULLISH_TYPES or (
            node.type == "literal_type"
            and any(child.type in _NULLISH_TYPES for child in node.named_children)
        )

    def _finding(self, context: TreeContext, node: Node, rule: str, message: str) -> Finding:
        return Finding(
            path=context.source.path,
            line=node.start_point.row + 1,
            column=node.start_point.column + 1,
            rule=rule,
            message=message,
        )
