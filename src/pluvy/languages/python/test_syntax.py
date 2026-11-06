"""Python test declarations, assertion sites and call families."""

from typing import Literal

from tree_sitter import Node

from pluvy.parsing.treesitter import field, node_text, walk
from pluvy.semantics.testing.contracts import TestAssertion, TestDeclaration

_EQUALITY_OPERATORS = frozenset({"==", "is"})
_EQUALITY_CALLS = frozenset({"assertEqual", "assertEquals", "assertIs"})
_ASSERTION_PREFIXES = ("assert", "_assert")
_RAISES_NAMES = frozenset({"assertRaises", "raises"})
_PRINT_NAME = "print"
_FIXTURE_NAME = "fixture"
_CONTROL_STATEMENTS = frozenset(
    {
        "with_statement",
        "for_statement",
        "while_statement",
        "if_statement",
        "try_statement",
        "match_statement",
        "raise_statement",
    }
)


def _arguments(call: Node) -> tuple[Node, ...]:
    arguments = field(call, "arguments")
    if arguments is None:
        return ()
    return tuple(child for child in arguments.named_children if child.type != "comment")


def _callee_name(call: Node) -> str:
    callee = field(call, "function")
    if callee is None:
        return ""
    if callee.type == "attribute":
        attribute = field(callee, "attribute")
        return node_text(attribute) if attribute is not None else ""
    return node_text(callee)


def _comparison_mirrored(comparison: Node) -> bool:
    operators = comparison.children_by_field_name("operators")
    operands = comparison.named_children
    return (
        len(operators) == 1
        and operators[0].type in _EQUALITY_OPERATORS
        and len(operands) == 2
        and node_text(operands[0]) == node_text(operands[1])
    )


def _assertion_kind(call: Node) -> Literal["assertion", "raises"] | None:
    name = _callee_name(call)
    if name in _RAISES_NAMES:
        return "raises"
    return "assertion" if name.startswith(_ASSERTION_PREFIXES) else None


def _call_mirrored(call: Node) -> bool:
    name = _callee_name(call)
    arguments = _arguments(call)
    if name == "assertTrue" and len(arguments) == 1:
        return arguments[0].type == "true"
    return (
        name in _EQUALITY_CALLS
        and len(arguments) == 2
        and node_text(arguments[0]) == node_text(arguments[1])
    )


def _assert_statement_mirrored(statement: Node) -> bool:
    expressions = statement.named_children
    if not expressions:
        return False
    expression = expressions[0]
    if expression.type == "true":
        return True
    return expression.type == "comparison_operator" and _comparison_mirrored(expression)


def _declared_at_module_or_class(node: Node) -> bool:
    parent = node.parent
    while parent is not None and parent.type == "decorated_definition":
        parent = parent.parent
    if parent is None:
        return False
    if parent.type == "module":
        return True
    return (
        parent.type == "block"
        and parent.parent is not None
        and parent.parent.type == "class_definition"
    )


def _decorator_name(decorator: Node) -> str:
    expression = decorator.named_children[0] if decorator.named_children else None
    if expression is None:
        return ""
    while expression.type == "call":
        function = field(expression, "function")
        if function is None:
            return ""
        expression = function
    if expression.type == "attribute":
        attribute = field(expression, "attribute")
        return node_text(attribute) if attribute is not None else ""
    return node_text(expression) if expression.type == "identifier" else ""


def _fixture_decorated(node: Node) -> bool:
    parent = node.parent
    if parent is None or parent.type != "decorated_definition":
        return False
    return any(
        _decorator_name(child) == _FIXTURE_NAME
        for child in parent.named_children
        if child.type == "decorator"
    )


class PythonTestSyntax:
    """Interpret Python test functions, unittest methods and pytest forms."""

    def declarations(self, root: Node) -> tuple[TestDeclaration, ...]:
        declarations: list[TestDeclaration] = []
        for node in walk(root):
            name = field(node, "name")
            if (
                node.type == "function_definition"
                and name is not None
                and node_text(name).startswith("test_")
                and _declared_at_module_or_class(node)
                and not _fixture_decorated(node)
            ):
                declarations.append(TestDeclaration(node, node_text(name)))
        return tuple(declarations)

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
            elif node.type == "call":
                kind = _assertion_kind(node)
                if kind == "raises":
                    assertions.append(TestAssertion(node, "raises"))
                elif kind == "assertion":
                    assertions.append(
                        TestAssertion(node, "assertion", mirrored=_call_mirrored(node))
                    )
        return tuple(assertions)

    def unrecognized_calls(self, declaration: Node) -> tuple[Node, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        return tuple(
            node
            for node in walk(body)
            if node.type == "call"
            and _assertion_kind(node) is None
            and _callee_name(node) != _PRINT_NAME
        )

    def control_statements(self, declaration: Node) -> tuple[Node, ...]:
        body = field(declaration, "body")
        if body is None:
            return ()
        return tuple(node for node in walk(body) if node.type in _CONTROL_STATEMENTS)
