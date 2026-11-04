"""Field reads proven by Go serialization and structural comparison operations."""

from typing import Literal

from tree_sitter import Node

from pluvy.languages.go.encoding import GoEncodingNames
from pluvy.languages.go.serialization_fields import GoSerializationFields
from pluvy.languages.go.value_origins import GoValueOrigins
from pluvy.parsing.treesitter import field, walk
from pluvy.semantics.aliases import QualifiedNames
from pluvy.semantics.index import SemanticIndex
from pluvy.semantics.model import Scope

type Consumption = Literal["json", "xml", "deep", "equal"]


class GoConsumedFields:
    """Apply library field contracts only to values reaching proven consumers."""

    def __init__(self, index: SemanticIndex) -> None:
        self.index = index
        self.names = QualifiedNames(index, GoEncodingNames())
        self.origins = GoValueOrigins(index)
        self.reads: set[int] = set()
        self.visited: set[tuple[int, Consumption]] = set()

    def used_declarations(self) -> frozenset[int]:
        for node in walk(self.index.context.root):
            self._consume(node)
        return frozenset(self.reads)

    def _consume(self, node: Node) -> None:
        if node.type == "binary_expression":
            operator = field(node, "operator")
            if operator is not None and self.index.text(operator) in {"==", "!="}:
                for value in node.named_children:
                    self._value(value, "equal")
            return
        callee = self.index.syntax.call(node)
        if callee is None:
            return
        mode = self._mode(callee)
        if mode is not None:
            arguments = self.index.syntax.arguments(node)
            for value in arguments if mode == "deep" else arguments[:1]:
                self._value(value, mode)

    def _mode(self, callee: Node) -> Consumption | None:
        name = self.names.qualified(callee)
        if name in {"encoding/json.Marshal", "encoding/json.MarshalIndent"}:
            return "json"
        if name in {"encoding/xml.Marshal", "encoding/xml.MarshalIndent"}:
            return "xml"
        if name == "reflect.DeepEqual":
            return "deep"
        if name == "k8s.io/apimachinery/pkg/runtime.DefaultUnstructuredConverter.ToUnstructured":
            return "json"
        return self._encoder_mode(callee)

    def _encoder_mode(self, callee: Node) -> Consumption | None:
        receiver, member = self.index.syntax.member_parts(callee)
        if receiver is None or member is None or self.index.text(member) != "Encode":
            return None
        value = self.names.value(receiver)
        constructor = self.index.syntax.call(value) if value is not None else None
        name = self.names.qualified(constructor) if constructor is not None else ""
        if name == "encoding/json.NewEncoder":
            return "json"
        return "xml" if name == "encoding/xml.NewEncoder" else None

    def _value(self, value: Node, mode: Consumption) -> None:
        scopes = (
            self.origins.structural_scopes(value) if mode == "equal" else self.origins.scopes(value)
        )
        for scope in scopes:
            self._scope(scope, mode)

    def _scope(self, scope: Scope, mode: Consumption) -> None:
        key = scope.node.id, mode
        if key in self.visited:
            return
        self.visited.add(key)
        if mode == "json" or mode == "xml":
            self._serialized(scope, mode)
            return
        for symbol in scope.symbols.values():
            if symbol.kind != "field" or symbol.node.parent is None:
                continue
            if symbol.name != "_":
                self.reads.add(symbol.node.id)
                if symbol.annotation is not None:
                    self._nested(symbol.annotation, mode)
        body = field(scope.node, "type")
        if body is not None:
            self._embedded(body, mode)

    def _serialized(self, scope: Scope, mode: Literal["json", "xml"]) -> None:
        selection = GoSerializationFields(self.origins, mode)
        if selection.custom(scope):
            return
        for candidate in selection.selected(scope):
            self.reads.add(candidate.node.id)
            if candidate.annotation is not None:
                self._nested(candidate.annotation, mode)

    def _nested(self, annotation: Node, mode: Consumption) -> None:
        if mode == "equal" and annotation.type in {"pointer_type", "slice_type", "map_type"}:
            return
        self._value(annotation, mode)

    def _embedded(self, body: Node, mode: Consumption) -> None:
        declarations = next(
            (n for n in body.named_children if n.type == "field_declaration_list"), None
        )
        if declarations is None:
            return
        for declaration in declarations.named_children:
            if declaration.type != "field_declaration" or declaration.children_by_field_name(
                "name"
            ):
                continue
            annotation = field(declaration, "type")
            if annotation is not None:
                self._nested(annotation, mode)
