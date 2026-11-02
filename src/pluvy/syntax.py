"""Compatibility exports for the tree-sitter parsing boundary."""

from tree_sitter import Node, Tree

from pluvy.languages.metric_syntax import FUNCTIONS
from pluvy.parsing.treesitter import field, spelling, walk
from pluvy.plugins.builtins import tree_parser
from pluvy.source import Source


def parse(source: Source) -> Tree:
    """Parse a source snapshot with its declared grammar."""
    return tree_parser(source.language).tree(source)


__all__ = ["FUNCTIONS", "Node", "Tree", "field", "parse", "spelling", "walk"]
