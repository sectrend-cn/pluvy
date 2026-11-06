"""Explicit typed composition of checker-owned policy fragments."""

from pydantic import Field

from pluvy.architecture.options import ArchitectureCheckers
from pluvy.architecture.options import Boundary as Boundary
from pluvy.architecture.options import ImportOptions as ImportOptions
from pluvy.architecture.options import ObjectModelOptions as ObjectModelOptions
from pluvy.architecture.options import Owner as Owner
from pluvy.architecture.options import OwnershipOptions as OwnershipOptions
from pluvy.architecture.options import SourcePlacement as SourcePlacement
from pluvy.architecture.options import StructureOptions as StructureOptions
from pluvy.metrics.options import FunctionSizeOptions as FunctionSizeOptions
from pluvy.metrics.options import MetricCheckers
from pluvy.policy.contracts import CheckerOptions as CheckerOptions
from pluvy.policy.contracts import Contract as Contract
from pluvy.policy.type_options import TypeCheckers
from pluvy.semantics.encoding_options import BroadTypeOptions as BroadTypeOptions
from pluvy.semantics.encoding_options import EncodingCheckers
from pluvy.semantics.encoding_options import EncodingOptions as EncodingOptions
from pluvy.semantics.encoding_options import OutputApi as OutputApi
from pluvy.semantics.failure_options import FailureCheckers
from pluvy.semantics.options import SemanticCheckers
from pluvy.semantics.projection.options import ProjectionCheckers
from pluvy.semantics.testing.options import TestingCheckers


class Checkers(
    MetricCheckers,
    ArchitectureCheckers,
    EncodingCheckers,
    SemanticCheckers,
    TypeCheckers,
    ProjectionCheckers,
    TestingCheckers,
    FailureCheckers,
):
    """Compose supported checker schemas without redeclaring their options or identities."""


class Policy(Contract):
    """Select source files globally and configure each checker independently."""

    version: int = Field(default=2, ge=2, le=2)
    include: tuple[str, ...] = ("**",)
    exclude: tuple[str, ...] = ()
    third_party_modules: tuple[str, ...] = ()
    checkers: Checkers = Checkers()
