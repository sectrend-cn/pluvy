"""Grammar-specific concrete-type policy."""

from dataclasses import dataclass

from tree_sitter import Node

from pluvy.analysis.context import TreeContext
from pluvy.analysis.requirements import RuleRequirements
from pluvy.diagnostics import Finding
from pluvy.languages.type_checks import TypeMarkers
from pluvy.parsing.treesitter import spelling
from pluvy.semantics.encoding import EncodingRule
from pluvy.semantics.encoding_options import BROAD_TYPE
from pluvy.source import Source


@dataclass(frozen=True)
class GoTypeRule:
    """Reject Go type erasure while preserving capability interfaces."""

    encoding: EncodingRule
    name: str = "builtin.types.go"
    api_version: int = 2
    requirements: RuleRequirements = RuleRequirements(semantic_evidence=True)
    rule_ids: tuple[str, ...] = (BROAD_TYPE.name,)

    def check(self, context: TreeContext) -> tuple[Finding, ...]:
        return (*TypeMarkers(context).check(self), *self.encoding.check(context))

    def issue(self, node: Node, source: Source) -> tuple[str, str] | None:
        text = spelling(node, source)
        if node.type == "type_identifier" and text == "any":
            return BROAD_TYPE.name, "Use a concrete type or a capability interface instead of any"
        if node.type == "interface_type" and all(
            child.type == "comment" for child in node.named_children
        ):
            return BROAD_TYPE.name, "Empty interfaces erase domain contracts"
        return None
