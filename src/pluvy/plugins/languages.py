"""Language discovery contracts independent of rule selection."""

from pathlib import PurePosixPath
from typing import Protocol

from pluvy.diagnostics import AnalysisError
from pluvy.parsing.treesitter import TreeParser
from pluvy.source import Language, LanguageDefinition


def _is_single_suffix(suffix: str) -> bool:
    """Accept one dot followed by a non-empty name without separators or further dots.

    The rule is spelled out instead of delegated to ``PurePosixPath.suffix``, whose
    treatment of a trailing dot differs between Python releases.
    """
    name = suffix.removeprefix(".")
    return suffix.startswith(".") and bool(name) and "." not in name and "/" not in name


class LanguagePlugin(Protocol):
    """Own an identity, its suffixes and its tree-sitter parser."""

    @property
    def definition(self) -> LanguageDefinition: ...

    @property
    def parser(self) -> TreeParser: ...


class LanguageRegistry:
    """Own atomic grammar identity and suffix discovery independently of rules."""

    def __init__(self) -> None:
        self._definitions: dict[Language, LanguageDefinition] = {}
        self._suffixes: dict[str, Language] = {}

    def validate(self, definition: LanguageDefinition) -> None:
        """Check discovery ambiguity before publishing registration state."""
        if definition.language in self._definitions:
            raise AnalysisError(f"Duplicate analyzer for language: {definition.language}")
        suffixes = definition.suffixes
        if not suffixes or len(set(suffixes)) != len(suffixes):
            raise AnalysisError(f"Invalid suffix declarations for language: {definition.language}")
        for suffix in suffixes:
            if not _is_single_suffix(suffix):
                raise AnalysisError(f"Invalid language suffix: {suffix}")
            if suffix in self._suffixes:
                raise AnalysisError(f"Conflicting language suffix: {suffix}")

    def register(self, definition: LanguageDefinition) -> None:
        """Register a grammar's discovery contract without requiring a rule set."""
        self.validate(definition)
        self._definitions[definition.language] = definition
        self._suffixes.update((suffix, definition.language) for suffix in definition.suffixes)

    def language_for(self, path: str) -> Language | None:
        """Resolve source suffixes through explicit language registrations."""
        return self._suffixes.get(PurePosixPath(path).suffix)
