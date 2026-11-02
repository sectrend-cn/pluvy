"""Shared function measurements and policy contracts."""

from typing import TYPE_CHECKING

from pluvy.metrics.contracts import Metrics, MetricSyntax

__all__ = ["MetricRule", "Metrics", "MetricSyntax"]

if TYPE_CHECKING:
    from pluvy.metrics.rules import MetricRule


def __getattr__(name: str) -> type["MetricRule"]:
    """Load the public rule class without coupling option imports to execution."""
    if name != "MetricRule":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from pluvy.metrics.rules import MetricRule

    return MetricRule
