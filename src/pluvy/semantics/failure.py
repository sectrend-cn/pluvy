"""Shared failure-flow policy for swallowed handlers and literal fallback chains."""

from dataclasses import dataclass
from typing import Literal, Protocol

from tree_sitter import Node

from pluvy.analysis.context import TreeContext
from pluvy.analysis.requirements import RuleRequirements
from pluvy.diagnostics import Finding
from pluvy.semantics.failure_options import FALLBACK, FLOW_HANDLING, SWALLOW


@dataclass(frozen=True)
class SwallowedHandler:
    """One wide capture whose handler subtree contains no re-throw."""

    node: Node
    handler: str


@dataclass(frozen=True)
class FallbackDefault:
    """One coalescing default with its bare-literal classification."""

    node: Node
    literal: bool


@dataclass(frozen=True)
class FallbackChain:
    """One maximal coalescing chain and the default written for each operator."""

    node: Node
    operators: int
    defaults: tuple[FallbackDefault, ...]


class FailureSyntax(Protocol):
    """Language-owned interpretation of capture handlers and coalescing chains."""

    def swallowed_handlers(self, root: Node) -> tuple[SwallowedHandler, ...]: ...

    def fallback_chains(self, root: Node) -> tuple[FallbackChain, ...]: ...


@dataclass(frozen=True)
class FailureFlowRule:
    """Report wide captures without re-throws and over-long literal coalescing."""

    syntax: FailureSyntax
    name: str = "builtin.failure"
    api_version: int = 2
    requirements: RuleRequirements = RuleRequirements()
    rule_ids: tuple[str, ...] = FLOW_HANDLING.rule_ids

    def check(self, context: TreeContext) -> tuple[Finding, ...]:
        findings = tuple(
            self._swallow_finding(context, handler)
            for handler in self.syntax.swallowed_handlers(context.root)
        )
        maximum = context.policy.checkers.flow_handling.max_chain
        fallbacks = tuple(
            self._fallback_finding(context, chain, maximum)
            for chain in self.syntax.fallback_chains(context.root)
            if self._over_limit(chain, maximum)
        )
        return findings + fallbacks

    def _over_limit(self, chain: FallbackChain, maximum: int) -> bool:
        return (
            chain.operators > maximum
            and bool(chain.defaults)
            and all(default.literal for default in chain.defaults)
        )

    def _swallow_finding(self, context: TreeContext, handler: SwallowedHandler) -> Finding:
        return self._finding(
            context,
            handler.node,
            SWALLOW,
            "error",
            f"The {handler.handler} handler swallows failures without re-throwing. "
            "Re-throw the original error, or narrow the captured type and handle that "
            "specific failure.",
        )

    def _fallback_finding(
        self, context: TreeContext, chain: FallbackChain, maximum: int
    ) -> Finding:
        return self._finding(
            context,
            chain.node,
            FALLBACK,
            "error",
            f"The coalescing chain has {chain.operators} operators and literal defaults; "
            f"maximum is {maximum}. Return a concrete value or surface the missing data "
            "instead of substituting constants.",
        )

    def _finding(
        self,
        context: TreeContext,
        node: Node,
        rule: str,
        severity: Literal["error", "warning"],
        message: str,
    ) -> Finding:
        return Finding(
            path=context.source.path,
            line=node.start_point.row + 1,
            column=node.start_point.column + 1,
            rule=rule,
            message=message,
            severity=severity,
        )
