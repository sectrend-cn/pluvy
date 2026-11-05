"""Java wide-capture handlers and their re-throw evidence."""

from tree_sitter import Node

from pluvy.parsing.treesitter import node_text, walk
from pluvy.semantics.failure import FallbackChain, SwallowedHandler

_WIDE_TYPES = frozenset({"Exception", "Throwable"})


def _child(node: Node, node_type: str) -> Node | None:
    return next((child for child in node.named_children if child.type == node_type), None)


def _catch_type(clause: Node) -> Node | None:
    parameter = _child(clause, "catch_formal_parameter")
    if parameter is None:
        return None
    return _child(parameter, "catch_type")


def _alternatives(catch_type: Node) -> tuple[Node, ...]:
    return tuple(child for child in catch_type.named_children if child.type == "type_identifier")


def _has_throw(block: Node) -> bool:
    return any(node.type == "throw_statement" for node in walk(block))


class JavaFailureSyntax:
    """Interpret single and multi-alternative `catch` clauses from current syntax."""

    def swallowed_handlers(self, root: Node) -> tuple[SwallowedHandler, ...]:
        handlers: list[SwallowedHandler] = []
        for clause in walk(root):
            if clause.type != "catch_clause":
                continue
            block = _child(clause, "block")
            catch_type = _catch_type(clause)
            if block is None or catch_type is None or _has_throw(block):
                continue
            alternatives = _alternatives(catch_type)
            if not any(node_text(alternative) in _WIDE_TYPES for alternative in alternatives):
                continue
            handlers.append(SwallowedHandler(clause, f"catch {node_text(catch_type)}"))
        return tuple(handlers)

    def fallback_chains(self, _: Node) -> tuple[FallbackChain, ...]:
        return ()
