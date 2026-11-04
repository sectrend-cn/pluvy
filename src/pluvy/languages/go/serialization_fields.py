"""Go serializer field dominance and promoted marshaler evidence."""

import re
from dataclasses import dataclass
from typing import Literal

from tree_sitter import Node

from pluvy.languages.go.value_origins import GoValueOrigins
from pluvy.parsing.treesitter import field
from pluvy.semantics.model import Scope


@dataclass(frozen=True)
class SerializedField:
    """A concrete field candidate with its embedding depth and wire name."""

    node: Node
    annotation: Node | None
    name: str
    depth: int
    tagged: bool


class GoSerializationFields:
    """Select visible fields before recursively consuming their stored values."""

    def __init__(self, origins: GoValueOrigins, mode: Literal["json", "xml"]) -> None:
        self.origins = origins
        self.mode = mode

    def selected(self, scope: Scope) -> tuple[SerializedField, ...]:
        candidates = self._candidates(scope, 0, frozenset())
        groups: dict[str, list[SerializedField]] = {}
        for candidate in candidates:
            groups.setdefault(candidate.name, []).append(candidate)
        return tuple(
            selected for group in groups.values() if (selected := self._dominant(group)) is not None
        )

    def _dominant(self, group: list[SerializedField]) -> SerializedField | None:
        depth = min(candidate.depth for candidate in group)
        peers = [candidate for candidate in group if candidate.depth == depth]
        tagged = [candidate for candidate in peers if candidate.tagged]
        if self.mode == "json" and tagged:
            peers = tagged
        return peers[0] if len(peers) == 1 else None

    def custom(self, scope: Scope) -> bool:
        names = (
            ("MarshalJSON", "MarshalText") if self.mode == "json" else ("MarshalXML", "MarshalText")
        )
        return any(self._unique_method(scope, name) for name in names)

    def _unique_method(self, scope: Scope, name: str) -> bool:
        depths = self._method_depths(scope, name, frozenset())
        return bool(depths) and depths.count(min(depths)) == 1

    def _method_depths(self, scope: Scope, name: str, seen: frozenset[int]) -> tuple[int, ...]:
        if scope.node.id in seen:
            return ()
        if name in scope.symbols:
            return (0,) if scope.symbols[name].kind == "function" else ()
        seen = seen | {scope.node.id}
        return tuple(
            depth + 1
            for declaration in self._declarations(scope)
            if not declaration.children_by_field_name("name")
            for nested in self._embedded_scopes(declaration)
            for depth in self._method_depths(nested, name, seen)
        )

    def _declarations(self, scope: Scope) -> tuple[Node, ...]:
        body = field(scope.node, "type")
        if body is None:
            return ()
        declarations = next(
            (node for node in body.named_children if node.type == "field_declaration_list"), None
        )
        return tuple(declarations.named_children) if declarations is not None else ()

    def _embedded_scopes(self, declaration: Node) -> tuple[Scope, ...]:
        annotation = field(declaration, "type")
        return self.origins.scopes(annotation) if annotation is not None else ()

    def _candidates(
        self, scope: Scope, depth: int, seen: frozenset[int]
    ) -> tuple[SerializedField, ...]:
        if scope.node.id in seen:
            return ()
        seen = seen | {scope.node.id}
        result: list[SerializedField] = []
        for declaration in self._declarations(scope):
            tag = self._tag(declaration)
            if tag == "-":
                continue
            names = declaration.children_by_field_name("name")
            if names:
                result.extend(self._named(declaration, depth, tag))
            else:
                result.extend(self._embedded(declaration, depth, seen, tag))
        return tuple(result)

    def _named(self, declaration: Node, depth: int, tag: str) -> tuple[SerializedField, ...]:
        owner = self.origins.owner(declaration)
        wire_name = tag.split(",", 1)[0]
        return tuple(
            SerializedField(
                node,
                field(declaration, "type"),
                wire_name or owner.text(node),
                depth,
                bool(wire_name),
            )
            for node in declaration.children_by_field_name("name")
            if owner.text(node)[:1].isupper()
        )

    def _embedded(
        self, declaration: Node, depth: int, seen: frozenset[int], tag: str
    ) -> tuple[SerializedField, ...]:
        scopes = self._embedded_scopes(declaration)
        wire_name = tag.split(",", 1)[0]
        if wire_name and self.mode == "json":
            return (
                SerializedField(declaration, field(declaration, "type"), wire_name, depth, True),
            )
        return tuple(
            candidate for scope in scopes for candidate in self._candidates(scope, depth + 1, seen)
        )

    def _tag(self, declaration: Node) -> str:
        tag = field(declaration, "tag")
        if tag is None:
            return ""
        text = self.origins.owner(tag).text(tag)
        text = text[1:-1] if text.startswith("`") else self._unquote(text)
        match = re.search(rf'(?:^|\s){self.mode}:"([^"\\]*(?:\\.[^"\\]*)*)"', text)
        return self._unquote('"' + match.group(1) + '"') if match is not None else ""

    def _unquote(self, text: str) -> str:
        return re.sub(
            r"\\(U[0-9a-fA-F]{8}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[0-7]{3}|.)",
            self._escape,
            text[1:-1],
        )

    def _escape(self, match: re.Match[str]) -> str:
        escape = match.group(1)
        if escape[0] in "Uux":
            return chr(int(escape[1:], 16))
        if len(escape) == 3 and escape.isdigit():
            return chr(int(escape, 8))
        return {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}.get(
            escape, escape
        )
