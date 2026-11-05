"""Python wide-capture handlers and their re-throw evidence."""

from tree_sitter import Node

from pluvy.parsing.treesitter import node_text, walk
from pluvy.semantics.failure import FallbackChain, SwallowedHandler

_WIDE_TYPES = frozenset({"BaseException", "Exception"})
_CLAUSE_AUXILIARIES = frozenset({"block", "comment"})


def _capture_type(clause: Node) -> Node | None:
    return next(
        (child for child in clause.named_children if child.type not in _CLAUSE_AUXILIARIES),
        None,
    )


def _declared_type(capture: Node) -> Node:
    if capture.type == "as_pattern" and capture.named_children:
        return capture.named_children[0]
    return capture


def _wide_type(declared: Node) -> Node | None:
    if declared.type == "identifier":
        return declared if node_text(declared) in _WIDE_TYPES else None
    if declared.type == "tuple":
        return next(
            (
                child
                for child in declared.named_children
                if child.type == "identifier" and node_text(child) in _WIDE_TYPES
            ),
            None,
        )
    return None


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
            capture = _capture_type(clause)
            if capture is None:
                handler = "except"
            else:
                declared = _declared_type(capture)
                if _wide_type(declared) is None:
                    continue
                handler = f"except {node_text(declared)}"
            handlers.append(SwallowedHandler(clause, handler))
        return tuple(handlers)

    def fallback_chains(self, _: Node) -> tuple[FallbackChain, ...]:
        return ()
