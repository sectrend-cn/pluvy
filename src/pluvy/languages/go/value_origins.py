"""Resolve Go value origins through concrete calls without expanding type constraints."""

import posixpath

from tree_sitter import Node

from pluvy.parsing.treesitter import field, walk
from pluvy.semantics.index import SemanticIndex
from pluvy.semantics.model import Scope, Symbol


class GoValueOrigins:
    """Retain declaration ownership while walking aliases and actual argument bindings."""

    def __init__(self, index: SemanticIndex) -> None:
        self.index = index
        self.indexes = tuple(
            peer
            for peer in index.snapshot_indexes.values()
            if peer.context.source.language == index.context.source.language
        )
        self.imports = {
            peer.context.root.id: peer.syntax.imports(peer.context) for peer in self.indexes
        }

    def owner(self, node: Node) -> SemanticIndex:
        root = node
        while root.parent is not None:
            root = root.parent
        return self.index.snapshot_indexes[root.id]

    def resolve(self, node: Node) -> Symbol | None:
        index = self.owner(node)
        if node.type == "generic_type":
            name = field(node, "type")
            return self.resolve(name) if name is not None else None
        symbol = index.resolve(node)
        if symbol is not None:
            return symbol
        return self._imported(node)

    def _imported(self, node: Node) -> Symbol | None:
        index = self.owner(node)
        receiver, member = index.syntax.member_parts(node)
        if node.type == "qualified_type":
            receiver, member = field(node, "package"), field(node, "name")
        if receiver is None or member is None:
            return None
        binding = index.lookup(index.text(receiver), index.locations.get(receiver.id, 0))
        for entry in self.imports[index.context.root.id]:
            if binding is not None and binding.node.id == entry.node.id:
                return self._package_member(entry.module, index.text(member))
        return None

    def _package_member(self, module: str, name: str) -> Symbol | None:
        candidates = []
        for index in self.indexes:
            directory = posixpath.dirname(index.context.source.path)
            if directory and (module == directory or module.endswith("/" + directory)):
                symbol = index.scopes[0].symbols.get(name)
                if symbol is not None:
                    candidates.append(symbol)
        return candidates[0] if len(candidates) == 1 else None

    def structural_scopes(
        self, node: Node, seen: frozenset[int] = frozenset()
    ) -> tuple[Scope, ...]:
        """Equality reads struct and array contents, but never pointer targets."""
        if node.id in seen:
            return ()
        seen = seen | {node.id}
        index = self.owner(node)
        node = index.syntax.single_value(node)
        if node.type in {"pointer_type", "slice_type", "map_type"}:
            return ()
        if node.type == "unary_expression" and index.text(node).startswith("&"):
            return ()
        callee = index.syntax.call(node)
        if callee is not None and index.text(callee) == "new":
            return ()
        annotation = index.syntax.value_type_node(node)
        if node.type == "array_type":
            annotation = field(node, "element")
        if node.type == "parenthesized_type":
            annotation = next(iter(node.named_children), None)
        if annotation is not None:
            return self.structural_scopes(annotation, seen)
        return self._structural_symbol_scopes(node, seen)

    def _structural_symbol_scopes(self, node: Node, seen: frozenset[int]) -> tuple[Scope, ...]:
        index = self.owner(node)
        callee = index.syntax.call(node)
        if callee is not None:
            if index.text(callee) == "new":
                return ()
            target = self.resolve(callee)
            return tuple(
                scope
                for result in self._results(target)
                for scope in self.structural_scopes(result, seen)
            )
        symbol = self.resolve(node)
        return self._structural_origin(symbol, seen) if symbol is not None else ()

    def _structural_origin(self, symbol: Symbol, seen: frozenset[int]) -> tuple[Scope, ...]:
        if symbol.kind == "class" and symbol.class_scope is not None:
            annotation = field(symbol.class_scope.node, "type")
            if annotation is not None and annotation.type != "struct_type":
                return self.structural_scopes(annotation, seen)
            return (symbol.class_scope,)
        origin = symbol.annotation or symbol.value
        if origin is not None and symbol.kind != "function":
            return self.structural_scopes(origin, seen)
        return ()

    def scopes(self, node: Node, seen: frozenset[int] = frozenset()) -> tuple[Scope, ...]:
        if node.id in seen:
            return ()
        seen = seen | {node.id}
        index = self.owner(node)
        node = index.syntax.single_value(node)
        wrapped = index.syntax.wrapped_value(node)
        if wrapped is not None:
            return self.scopes(wrapped, seen)
        annotation = index.syntax.value_type_node(node) or index.syntax.element_type(node)
        if annotation is not None:
            return self.scopes(annotation, seen)
        return self._resolved_scopes(node, seen)

    def _resolved_scopes(self, node: Node, seen: frozenset[int]) -> tuple[Scope, ...]:
        index = self.owner(node)
        if node.type == "type_identifier":
            scope = index.class_scope(index.text(node))
            if scope is not None:
                return self._class_scopes(scope, seen)
        symbol = self.resolve(node)
        if symbol is not None:
            return self._symbol_scopes(symbol, seen)
        return self._call_scopes(node, seen)

    def _call_scopes(self, node: Node, seen: frozenset[int]) -> tuple[Scope, ...]:
        index = self.owner(node)
        callee = index.syntax.call(node)
        target = self.resolve(callee) if callee is not None else None
        if target is not None:
            return tuple(
                scope for result in self._results(target) for scope in self.scopes(result, seen)
            )
        scope = index.value_scope(node)
        return (scope,) if scope is not None else ()

    def _results(self, target: Symbol | None) -> tuple[Node, ...]:
        if target is None or target.annotation is None:
            return ()
        annotation = target.annotation
        if annotation.type != "parameter_list":
            return (annotation,)
        return tuple(
            result
            for parameter in annotation.named_children
            if (result := field(parameter, "type")) is not None
        )

    def _symbol_scopes(self, symbol: Symbol, seen: frozenset[int]) -> tuple[Scope, ...]:
        if symbol.kind == "parameter" and symbol.class_scope is None:
            return self._parameter_scopes(symbol, seen)
        if symbol.kind == "class" and symbol.class_scope is not None:
            return self._class_scopes(symbol.class_scope, seen)
        if symbol.annotation is not None:
            scopes = self.scopes(symbol.annotation, seen)
            if scopes:
                return scopes
        if symbol.value is not None and symbol.kind != "function":
            return self.scopes(symbol.value, seen)
        return (symbol.class_scope,) if symbol.class_scope is not None else ()

    def _class_scopes(self, scope: Scope, seen: frozenset[int]) -> tuple[Scope, ...]:
        annotation = field(scope.node, "type")
        if annotation is not None and annotation.type != "struct_type":
            return self.scopes(annotation, seen)
        return (scope,)

    def _parameter_scopes(self, symbol: Symbol, seen: frozenset[int]) -> tuple[Scope, ...]:
        if symbol.annotation is not None:
            scopes = self.scopes(symbol.annotation, seen)
            if scopes:
                return scopes
        owner = self.owner(symbol.node)
        function = owner.scopes[symbol.scope].node
        if field(function, "type_parameters") is None:
            return ()
        return tuple(
            scope for value in self.arguments(symbol) for scope in self.scopes(value, seen)
        )

    def arguments(self, parameter: Symbol) -> tuple[Node, ...]:
        index = self.owner(parameter.node)
        function = index.scopes[parameter.scope].node
        parameters = index.syntax.parameters(function)
        positions = [slot for slot, name in enumerate(parameters) if name == parameter.node]
        if not positions:
            return ()
        return tuple(
            argument
            for peer in self.indexes
            for call in walk(peer.context.root)
            if (argument := self._argument(call, function, positions[0])) is not None
        )

    def _argument(self, call: Node, function: Node, position: int) -> Node | None:
        peer = self.owner(call)
        callee = peer.syntax.call(call)
        if call.type == "type_conversion_expression":
            callee = field(call, "type")
        target = self.resolve(callee) if callee is not None else None
        if target is None or target.value != function:
            return None
        if call.type == "type_conversion_expression":
            return field(call, "operand") if position == 0 else None
        arguments = peer.syntax.arguments(call)
        return arguments[position] if position < len(arguments) else None
