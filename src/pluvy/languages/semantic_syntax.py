"""Compatibility exports for language-owned semantic syntax adapters."""

from pluvy.languages.go.semantic_syntax import GoSemanticSyntax
from pluvy.languages.javascript.semantic_syntax import JavaScriptSemanticSyntax
from pluvy.languages.python.semantic_syntax import PythonSemanticSyntax

__all__ = ["GoSemanticSyntax", "JavaScriptSemanticSyntax", "PythonSemanticSyntax"]
