"""PythonLanguage identity, discovery and tree-sitter grammar."""

from dataclasses import dataclass, field

import tree_sitter_python
from tree_sitter import Language as Grammar

from pluvy.parsing.treesitter import TreeParser
from pluvy.source import Language, LanguageDefinition


@dataclass(frozen=True)
class PythonLanguage:
    """Own syntax parsing independently of application rule composition."""

    definition: LanguageDefinition = LanguageDefinition(Language.PYTHON, (".py", ".pyi"))
    parser: TreeParser = field(
        default_factory=lambda: TreeParser(Grammar(tree_sitter_python.language()))
    )
