"""Canonical extraction contracts and module identity resolution."""

from typing import Protocol

from pluvy.analysis.context import TreeContext
from pluvy.architecture.models import Import
from pluvy.source import Source


class ImportResolver(Protocol):
    """Map a literal dependency to the names its language considers equivalent."""

    def names(self, dependency: Import, source: Source) -> tuple[str, ...]: ...


class LiteralImportResolver(ImportResolver):
    """Python and Go import specifiers are already module identities."""

    def names(self, dependency: Import, source: Source) -> tuple[str, ...]:
        """Keep the resolver signature; literal identities need no source path."""
        return (dependency.module,)


class ImportExtractor(Protocol):
    """Extract dependency evidence from one concrete parser context."""

    def extract(self, context: TreeContext) -> tuple[Import, ...]: ...
