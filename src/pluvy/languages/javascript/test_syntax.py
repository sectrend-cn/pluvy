"""JavaScript, TypeScript and TSX test declarations and assertion sites."""

from tree_sitter import Node

from pluvy.parsing.treesitter import field, walk
from pluvy.semantics.testing.contracts import TestAssertion, TestDeclaration

_DECLARATIONS = frozenset({"it", "test"})
_ASSERT_ROOTS = frozenset({"assert", "_assert"})
_EQUALITY_MATCHERS = frozenset({"toBe", "toStrictEqual", "toEqual"})
_EQUALITY_ASSERT_MEMBERS = frozenset({"equal", "strictEqual", "deepEqual", "deepStrictEqual"})
_ALWAYS_TRUE_MATCHERS = frozenset({"toBeDefined", "toBeTruthy"})
_SNAPSHOT_MATCHERS = frozenset({"toMatchInlineSnapshot", "toMatchSnapshot"})
_PRINT_ROOT = "console"
_CALLBACKS = frozenset({"arrow_function", "function", "function_expression"})
_ASSERTION_PREFIXES = ("assert", "_assert")
_CONTROL_STATEMENTS = frozenset(
    {
        "if_statement",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "switch_statement",
        "with_statement",
    }
)


def _spelling(node: Node) -> str:
    """Return the exact parsed spelling without decoding escapes."""
    return (node.text or b"").decode("utf-8")


def _arguments(call: Node) -> tuple[Node, ...]:
    arguments = field(call, "arguments")
    if arguments is None:
        return ()
    return tuple(child for child in arguments.named_children if child.type != "comment")


def _callee(call: Node) -> Node | None:
    return field(call, "function")


def _root_name(node: Node) -> str:
    current = node
    while current.type == "member_expression":
        owner = field(current, "object")
        if owner is None:
            return ""
        current = owner
    if current.type == "call_expression":
        callee = _callee(current)
        return _spelling(callee) if callee is not None and callee.type == "identifier" else ""
    return _spelling(current) if current.type == "identifier" else ""


def _expect_call(node: Node) -> Node | None:
    current = node
    while current.type == "member_expression":
        owner = field(current, "object")
        if owner is None:
            return None
        current = owner
    callee = _callee(current) if current.type == "call_expression" else None
    if callee is not None and callee.type == "identifier" and _spelling(callee) == "expect":
        return current
    return None


def _chain_has_not(function: Node) -> bool:
    current = field(function, "object")
    while current is not None and current.type == "member_expression":
        property_name = field(current, "property")
        if property_name is not None and _spelling(property_name) == "not":
            return True
        current = field(current, "object")
    return False


def _pair_mirrored(call: Node) -> bool:
    arguments = _arguments(call)
    return len(arguments) == 2 and _spelling(arguments[0]) == _spelling(arguments[1])


def _negated(function: Node, name: str) -> bool:
    lowered = name.lower()
    return _chain_has_not(function) or "not" in lowered or lowered.endswith("false")


def _assertion_mirrored(call: Node, function: Node, name: str) -> bool:
    if _negated(function, name):
        return False
    arguments = _arguments(call)
    if len(arguments) == 1:
        return arguments[0].type == "true"
    return (
        function.type == "member_expression"
        and name in _EQUALITY_ASSERT_MEMBERS
        and _pair_mirrored(call)
    )


def _equality_mirrored(call: Node, function: Node) -> bool:
    receiver = field(function, "object")
    if receiver is None or receiver.type != "call_expression":
        return False
    callee = _callee(receiver)
    expected = _arguments(receiver)
    actual = _arguments(call)
    return (
        callee is not None
        and callee.type == "identifier"
        and _spelling(callee) == "expect"
        and len(expected) == 1
        and len(actual) == 1
        and _spelling(expected[0]) == _spelling(actual[0])
    )


def _assertion(function: Node) -> bool:
    if function.type == "identifier":
        return _spelling(function).startswith(_ASSERTION_PREFIXES)
    return _root_name(function) in _ASSERT_ROOTS


def _classification(call: Node) -> TestAssertion | None:
    function = _callee(call)
    if function is None:
        return None
    if function.type == "identifier":
        return _identifier(call, function)
    if function.type != "member_expression":
        return None
    return _member(call, function)


def _identifier(call: Node, function: Node) -> TestAssertion | None:
    if not _assertion(function):
        return None
    return TestAssertion(
        call,
        "assertion",
        mirrored=_assertion_mirrored(call, function, _spelling(function)),
    )


def _member(call: Node, function: Node) -> TestAssertion | None:
    property_name = field(function, "property")
    matcher = _spelling(property_name) if property_name is not None else ""
    if _expect_call(function) is not None:
        return _expect_matcher(call, function, matcher)
    return _assert_member(call, function, matcher)


def _expect_matcher(call: Node, function: Node, matcher: str) -> TestAssertion:
    inverted = _chain_has_not(function)
    always_true = (matcher in _ALWAYS_TRUE_MATCHERS and not inverted) or (
        matcher == "toThrow" and inverted and not _arguments(call)
    )
    return TestAssertion(
        call,
        "matcher",
        always_true=always_true,
        mirrored=matcher in _EQUALITY_MATCHERS and _equality_mirrored(call, function),
        snapshot=matcher in _SNAPSHOT_MATCHERS,
    )


def _assert_member(call: Node, function: Node, name: str) -> TestAssertion | None:
    if not _assertion(function):
        return None
    return TestAssertion(
        call,
        "assertion",
        mirrored=_assertion_mirrored(call, function, name),
    )


def _is_print(call: Node) -> bool:
    function = _callee(call)
    return function is not None and _root_name(function) == _PRINT_ROOT


def _callback(call: Node) -> Node | None:
    for argument in reversed(_arguments(call)):
        if argument.type in _CALLBACKS:
            return argument
    return None


def _name(argument: Node) -> str:
    if argument.type == "string":
        fragments = [
            _spelling(child) for child in argument.named_children if child.type == "string_fragment"
        ]
        return "".join(fragments)
    return " ".join(_spelling(argument).split())[:80]


def _test_name(call: Node, callback: Node) -> str:
    for argument in _arguments(call):
        if argument != callback:
            return _name(argument)
    return "unnamed test"


class JavaScriptTestSyntax:
    """Interpret Jasmine/Jest/Vitest-style declarations in the JS grammar family."""

    def declarations(self, root: Node) -> tuple[TestDeclaration, ...]:
        declarations: list[TestDeclaration] = []
        for node in walk(root):
            if node.type != "call_expression":
                continue
            function = _callee(node)
            if function is None or function.type != "identifier":
                continue
            if _spelling(function) not in _DECLARATIONS:
                continue
            callback = _callback(node)
            if callback is not None:
                declarations.append(TestDeclaration(node, _test_name(node, callback)))
        return tuple(declarations)

    def assertions(self, declaration: Node) -> tuple[TestAssertion, ...]:
        callback = _callback(declaration)
        body = field(callback, "body") if callback is not None else None
        if body is None:
            return ()
        return tuple(
            assertion
            for node in walk(body)
            if node.type == "call_expression"
            for assertion in (_classification(node),)
            if assertion is not None
        )

    def unrecognized_calls(self, declaration: Node) -> tuple[Node, ...]:
        callback = _callback(declaration)
        body = field(callback, "body") if callback is not None else None
        if body is None:
            return ()
        return tuple(
            node
            for node in walk(body)
            if node.type == "new_expression"
            or (
                node.type == "call_expression"
                and _classification(node) is None
                and not _is_print(node)
            )
        )

    def control_statements(self, declaration: Node) -> tuple[Node, ...]:
        callback = _callback(declaration)
        body = field(callback, "body") if callback is not None else None
        if body is None:
            return ()
        return tuple(node for node in walk(body) if node.type in _CONTROL_STATEMENTS)
