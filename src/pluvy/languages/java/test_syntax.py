"""Java JUnit test declarations, assertion sites and print calls."""

from tree_sitter import Node

from pluvy.parsing.treesitter import field, walk
from pluvy.semantics.testing.contracts import TestAssertion, TestDeclaration

_TEST_ANNOTATION = "Test"
_ASSERTION_PREFIX = "assert"
_EQUALITY_ASSERTIONS = frozenset({"assertEquals", "assertSame"})
_PRINT_RECEIVERS = frozenset({"System.err", "System.out"})
_PRINT_PREFIX = "print"
_ANNOTATIONS = frozenset({"annotation", "marker_annotation"})
_COMMENTS = frozenset({"block_comment", "line_comment"})
_CONTROL_STATEMENTS = frozenset(
    {
        "if_statement",
        "for_statement",
        "enhanced_for_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "try_with_resources_statement",
        "switch_expression",
        "synchronized_statement",
    }
)


def _spelling(node: Node) -> str:
    """Return the exact parsed spelling without decoding escapes."""
    return (node.text or b"").decode("utf-8")


def _arguments(call: Node) -> tuple[Node, ...]:
    arguments = field(call, "arguments")
    if arguments is None:
        return ()
    return tuple(child for child in arguments.named_children if child.type not in _COMMENTS)


def _call_name(call: Node) -> str:
    name = field(call, "name")
    return _spelling(name) if name is not None else ""


def _has_test_annotation(method: Node) -> bool:
    modifiers = next((child for child in method.named_children if child.type == "modifiers"), None)
    if modifiers is None:
        return False
    return any(
        node.type in _ANNOTATIONS
        and any(
            child.type == "identifier" and _spelling(child) == _TEST_ANNOTATION
            for child in walk(node)
        )
        for node in walk(modifiers)
    )


def _pair_mirrored(call: Node) -> bool:
    arguments = _arguments(call)
    return len(arguments) == 2 and _spelling(arguments[0]) == _spelling(arguments[1])


def _assert_statement_mirrored(statement: Node) -> bool:
    expressions = statement.named_children
    if not expressions:
        return False
    expression = expressions[0]
    if expression.type == "true":
        return True
    if expression.type != "binary_expression":
        return False
    operator = expression.child_by_field_name("operator")
    left = expression.child_by_field_name("left")
    right = expression.child_by_field_name("right")
    return (
        operator is not None
        and operator.type == "=="
        and left is not None
        and right is not None
        and _spelling(left) == _spelling(right)
    )


def _call_mirrored(call: Node) -> bool:
    name = _call_name(call)
    arguments = _arguments(call)
    if name == "assertTrue" and len(arguments) == 1 and arguments[0].type == "true":
        return True
    return name in _EQUALITY_ASSERTIONS and _pair_mirrored(call)


def _is_assertion(call: Node) -> bool:
    return _call_name(call).startswith(_ASSERTION_PREFIX)


def _is_print(call: Node) -> bool:
    name = _call_name(call)
    receiver = field(call, "object")
    return (
        name.startswith(_PRINT_PREFIX)
        and receiver is not None
        and receiver.type == "field_access"
        and _spelling(receiver) in _PRINT_RECEIVERS
    )


class JavaTestSyntax:
    """Interpret JUnit 5 annotations, assertion calls and console output."""

    def declarations(self, root: Node) -> tuple[TestDeclaration, ...]:
        return tuple(
            TestDeclaration(node, _spelling(name))
            for node in walk(root)
            if node.type == "method_declaration"
            for name in (field(node, "name"),)
            if name is not None and _has_test_annotation(node)
        )

    def assertions(self, declaration: Node) -> tuple[TestAssertion, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        assertions: list[TestAssertion] = []
        for node in walk(body):
            if node.type == "assert_statement":
                assertions.append(
                    TestAssertion(node, "assertion", mirrored=_assert_statement_mirrored(node))
                )
            elif node.type == "method_invocation" and _is_assertion(node):
                assertions.append(TestAssertion(node, "assertion", mirrored=_call_mirrored(node)))
        return tuple(assertions)

    def unrecognized_calls(self, declaration: Node) -> tuple[Node, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        return tuple(
            node
            for node in walk(body)
            if node.type == "object_creation_expression"
            or (
                node.type == "method_invocation" and not _is_assertion(node) and not _is_print(node)
            )
        )

    def control_statements(self, declaration: Node) -> tuple[Node, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        return tuple(node for node in walk(body) if node.type in _CONTROL_STATEMENTS)
