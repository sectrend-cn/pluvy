"""Python wide-capture handlers and their re-throw evidence."""

from tree_sitter import Node

from pluvy.parsing.treesitter import node_text, walk
from pluvy.semantics.failure import FallbackChain, SwallowedHandler

_WIDE_TYPES = frozenset({"BaseException", "Exception"})
_TYPE_NODES = frozenset({"identifier", "tuple"})


def _declared_type(clause: Node) -> Node | None:
    for child in clause.named_children:
        if child.type == "as_pattern":
            return child.named_children[0] if child.named_children else None
        if child.type in _TYPE_NODES:
            return child
    return None


def _alternatives(declared: Node | None) -> tuple[Node, ...]:
    if declared is None:
        return ()
    if declared.type == "identifier":
        return (declared,)
    return tuple(child for child in declared.named_children if child.type == "identifier")


def _handler_block(clause: Node) -> Node | None:
    return next((child for child in clause.named_children if child.type == "block"), None)


def _has_raise(block: Node) -> bool:
    return any(node.type == "raise_statement" for node in walk(block))


class PythonFailureSyntax:
    """Interpret bare and typed `except` clauses without runtime evaluation."""

    def swallowed_handlers(self, root: Node) -> tuple[SwallowedHandler, ...]:
        handlers: list[SwallowedHandler] = []
        for clause in walk(root):
            if clause.type != "except_clause":
                continue
            block = _handler_block(clause)
            if block is None or _has_raise(block):
                continue
            declared = _declared_type(clause)
            if declared is not None and not any(
                node_text(alternative) in _WIDE_TYPES for alternative in _alternatives(declared)
            ):
                continue
            handler = "except" if declared is None else f"except {node_text(declared)}"
            handlers.append(SwallowedHandler(clause, handler))
        return tuple(handlers)

    def fallback_chains(self, _: Node) -> tuple[FallbackChain, ...]:
        return ()
