"""JavaScript-family capture handlers and coalescing-chain interpretation."""

from tree_sitter import Node

from pluvy.parsing.treesitter import field, node_text, walk
from pluvy.semantics.failure import FallbackChain, FallbackDefault, SwallowedHandler

_FUNCTION_BOUNDARIES = frozenset(
    {
        "arrow_function",
        "function",
        "function_declaration",
        "function_expression",
        "generator_function",
        "generator_function_declaration",
        "method_definition",
    }
)
_INLINE_CALLBACKS = frozenset({"arrow_function", "function", "function_expression"})
_LITERAL_DEFAULTS = frozenset(
    {"array", "false", "number", "object", "string", "template_string", "true"}
)
_COMMENT = "comment"


def _contains(node: Node, node_type: str) -> bool:
    return any(child.type == node_type for child in walk(node))


def _catch_callback(call: Node) -> Node | None:
    function = field(call, "function")
    if function is None or function.type != "member_expression":
        return None
    property_name = field(function, "property")
    if property_name is None or node_text(property_name) != "catch":
        return None
    arguments = field(call, "arguments")
    if arguments is None:
        return None
    return next(
        (child for child in arguments.named_children if child.type in _INLINE_CALLBACKS),
        None,
    )


def _callback_swallows(call: Node) -> bool:
    callback = _catch_callback(call)
    if callback is None:
        return False
    body = field(callback, "body")
    return body is not None and not _contains(body, "throw_statement")


def _catch_swallows(clause: Node) -> bool:
    block = next(
        (child for child in clause.named_children if child.type == "statement_block"),
        None,
    )
    return block is not None and not _contains(block, "throw_statement")


def _named_expression(node: Node) -> tuple[Node, ...]:
    return tuple(
        child
        for child in node.named_children
        if child.type != _COMMENT and child.type not in _FUNCTION_BOUNDARIES
    )


def _is_coalescing(node: Node) -> bool:
    if node.type != "binary_expression":
        return False
    operator = field(node, "operator")
    return operator is not None and operator.type == "??"


def _coalescing_children(node: Node) -> tuple[Node, ...]:
    return tuple(
        child for child in (field(node, "left"), field(node, "right")) if child is not None
    )


def _member_children(node: Node) -> tuple[Node, ...]:
    object_node = field(node, "object")
    if object_node is None or object_node.type in _FUNCTION_BOUNDARIES:
        return ()
    return (object_node,)


def _call_children(node: Node) -> tuple[Node, ...]:
    return tuple(
        child
        for child in (field(node, "function"), field(node, "arguments"))
        if child is not None and child.type not in _FUNCTION_BOUNDARIES
    )


def _traversable_children(node: Node) -> tuple[Node, ...]:
    if _is_coalescing(node):
        return _coalescing_children(node)
    if node.type in {"as_expression", "parenthesized_expression"}:
        return _named_expression(node)
    if node.type == "member_expression":
        return _member_children(node)
    if node.type == "call_expression":
        return _call_children(node)
    if node.type == "arguments":
        return _named_expression(node)
    return ()


def _neighbors(node: Node) -> tuple[Node, ...]:
    neighbors = list(_traversable_children(node))
    parent = node.parent
    if parent is not None and node in _traversable_children(parent):
        neighbors.append(parent)
    return tuple(neighbors)


def _component(start: Node) -> tuple[Node, ...]:
    pending = [start]
    seen = {start}
    members: list[Node] = []
    while pending:
        node = pending.pop()
        members.append(node)
        for neighbor in _neighbors(node):
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return tuple(members)


def _depth(node: Node) -> int:
    depth = 0
    current = node.parent
    while current is not None:
        depth += 1
        current = current.parent
    return depth


def _anchor(nodes: tuple[Node, ...]) -> Node:
    return max(nodes, key=lambda node: (_depth(node), -node.start_byte))


def _chain(coalescing: tuple[Node, ...]) -> FallbackChain:
    ordered = tuple(sorted(coalescing, key=lambda item: item.start_byte))
    defaults = tuple(
        FallbackDefault(right, right.type in _LITERAL_DEFAULTS)
        for operator in ordered
        for right in (field(operator, "right"),)
        if right is not None
    )
    return FallbackChain(_anchor(ordered), len(ordered), defaults)


class JavaScriptFailureSyntax:
    """Interpret catch clauses, `.catch` callbacks and `??` expression trees."""

    def swallowed_handlers(self, root: Node) -> tuple[SwallowedHandler, ...]:
        handlers: list[SwallowedHandler] = []
        for node in walk(root):
            if node.type == "catch_clause" and _catch_swallows(node):
                handlers.append(SwallowedHandler(node, "catch"))
            elif node.type == "call_expression" and _callback_swallows(node):
                handlers.append(SwallowedHandler(node, ".catch"))
        return tuple(handlers)

    def fallback_chains(self, root: Node) -> tuple[FallbackChain, ...]:
        chains: list[FallbackChain] = []
        visited: set[Node] = set()
        for node in walk(root):
            if not _is_coalescing(node) or node in visited:
                continue
            component = _component(node)
            visited.update(component)
            coalescing = tuple(item for item in component if _is_coalescing(item))
            chains.append(_chain(coalescing))
        return tuple(chains)
