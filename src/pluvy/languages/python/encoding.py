"""Python JSON identity and output APIs for the shared serialization rule."""

from tree_sitter import Node

from pluvy.languages.encoding_syntax import GrammarEncoding
from pluvy.languages.python.encoding_members import PythonInstanceOutputs
from pluvy.languages.python.outputs import PythonOutputs
from pluvy.languages.python.qualified_names import PythonNameSyntax
from pluvy.semantics.aliases import QualifiedNames
from pluvy.semantics.index import SemanticIndex


class PythonEncodingSyntax(GrammarEncoding):
    """Recognize JSON encoding and decoding without embedding flow analysis."""

    names = PythonNameSyntax()
    encoders = frozenset({"json.dumps"})
    decoders = frozenset({"json.loads"})

    def instance_owner(self, callee: Node, index: SemanticIndex) -> Node | None:
        return PythonInstanceOutputs(index).owner(callee)

    def terminal(self, callee: Node, value: Node, names: QualifiedNames) -> bool:
        return PythonOutputs(names).terminal(callee, value)
