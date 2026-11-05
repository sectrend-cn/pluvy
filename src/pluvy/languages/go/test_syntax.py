"""Go test declarations, fatal assertion calls and print families."""

from tree_sitter import Node

from pluvy.parsing.treesitter import field, node_text, walk
from pluvy.semantics.testing.contracts import TestAssertion, TestDeclaration

_ASSERTION_NAMES = frozenset({"Error", "Errorf", "Fail", "FailNow", "Fatal", "Fatalf"})
_ASSERTION_PREFIX = "Fail"
_PRINT_RECEIVERS = frozenset({"fmt", "log"})
_PRINT_PREFIX = "Print"
_TEST_PREFIX = "Test"
_CONTROL_STATEMENTS = frozenset(
    {
        "if_statement",
        "for_statement",
        "expression_switch_statement",
        "type_switch_statement",
        "select_statement",
    }
)


def _selector_parts(call: Node) -> tuple[str, str]:
    selector = field(call, "function")
    if selector is None or selector.type != "selector_expression":
        return "", ""
    receiver = field(selector, "operand")
    member = field(selector, "field")
    return (
        node_text(receiver) if receiver is not None else "",
        node_text(member) if member is not None else "",
    )


def _is_assertion(call: Node) -> bool:
    _, member = _selector_parts(call)
    return member in _ASSERTION_NAMES or member.startswith(_ASSERTION_PREFIX)


def _is_print(call: Node) -> bool:
    receiver, member = _selector_parts(call)
    return receiver in _PRINT_RECEIVERS and member.startswith(_PRINT_PREFIX)


class GoTestSyntax:
    """Interpret Go Test functions and testing.T failure helpers."""

    def declarations(self, root: Node) -> tuple[TestDeclaration, ...]:
        return tuple(
            TestDeclaration(node, node_text(name))
            for node in walk(root)
            if node.type == "function_declaration"
            for name in (field(node, "name"),)
            if name is not None and node_text(name).startswith(_TEST_PREFIX)
        )

    def assertions(self, declaration: Node) -> tuple[TestAssertion, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        return tuple(
            TestAssertion(node, "fatal")
            for node in walk(body)
            if node.type == "call_expression" and _is_assertion(node)
        )

    def unrecognized_calls(self, declaration: Node) -> tuple[Node, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        return tuple(
            node
            for node in walk(body)
            if node.type == "call_expression" and not _is_assertion(node) and not _is_print(node)
        )

    def control_statements(self, declaration: Node) -> tuple[Node, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        return tuple(node for node in walk(body) if node.type in _CONTROL_STATEMENTS)
