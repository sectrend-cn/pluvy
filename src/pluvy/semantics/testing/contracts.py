"""Narrow current-tree facts for test declarations and their assertions."""

from dataclasses import dataclass
from typing import Literal, Protocol

from tree_sitter import Node


@dataclass(frozen=True)
class TestDeclaration:
    """One test declaration and the original syntax node that anchors it."""

    node: Node
    name: str


@dataclass(frozen=True)
class TestAssertion:
    """One assertion site classified from syntax without runtime evaluation."""

    node: Node
    kind: Literal["assertion", "matcher", "raises", "fatal"]
    always_true: bool = False
    mirrored: bool = False
    snapshot: bool = False


class TestSyntax(Protocol):
    """Language-owned interpretation of test declarations and assertions."""

    def declarations(self, root: Node) -> tuple[TestDeclaration, ...]: ...

    def assertions(self, declaration: Node) -> tuple[TestAssertion, ...]: ...

    def unrecognized_calls(self, declaration: Node) -> tuple[Node, ...]: ...

    def control_statements(self, declaration: Node) -> tuple[Node, ...]: ...
