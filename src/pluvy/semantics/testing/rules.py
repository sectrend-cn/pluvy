"""Shared test-integrity policy for every registered test syntax adapter."""

from dataclasses import dataclass
from typing import Literal

from tree_sitter import Node

from pluvy.analysis.context import TreeContext
from pluvy.analysis.requirements import RuleRequirements
from pluvy.diagnostics import Finding
from pluvy.policy.paths import matches
from pluvy.semantics.testing.contracts import TestAssertion, TestSyntax
from pluvy.semantics.testing.options import TEST_INTEGRITY

_TAUTOLOGY = TEST_INTEGRITY.rule_ids[0]
_VACUOUS = TEST_INTEGRITY.rule_ids[1]


@dataclass(frozen=True)
class TestIntegrityRule:
    """Report tautological and vacuous test assertions from current syntax."""

    syntax: TestSyntax
    name: str = "builtin.testing"
    api_version: int = 2
    requirements: RuleRequirements = RuleRequirements()
    rule_ids: tuple[str, ...] = TEST_INTEGRITY.rule_ids

    def check(self, context: TreeContext) -> tuple[Finding, ...]:
        if not matches(context.source.path, context.policy.checkers.test_integrity.paths):
            return ()
        findings: list[Finding] = []
        for declaration in self.syntax.declarations(context.root):
            assertions = self.syntax.assertions(declaration.node)
            findings.extend(
                self._assertion_finding(context, declaration.name, assertion)
                for assertion in assertions
                if assertion.mirrored or assertion.always_true
            )
            body = self._body_finding(context, declaration.name, declaration.node, assertions)
            if body is not None:
                findings.append(body)
        return tuple(findings)

    def _assertion_finding(
        self, context: TreeContext, test: str, assertion: TestAssertion
    ) -> Finding:
        if assertion.mirrored:
            return self._finding(
                context,
                assertion.node,
                _TAUTOLOGY,
                "error",
                f"Assertion in {test} cannot fail because it restates the same expression "
                "or a literal true. Assert an independently produced value or outcome "
                "instead.",
            )
        return self._finding(
            context,
            assertion.node,
            _VACUOUS,
            "error",
            f"Assertion in {test} uses a matcher that passes without checking behavior. "
            "Assert the produced value, raised error or observable outcome instead.",
        )

    def _body_finding(
        self,
        context: TreeContext,
        test: str,
        declaration: Node,
        assertions: tuple[TestAssertion, ...],
    ) -> Finding | None:
        if not assertions:
            if self.syntax.unrecognized_calls(declaration):
                return None
            return self._finding(
                context,
                declaration,
                _VACUOUS,
                "error",
                f"Test {test} declares no assertion and cannot fail. Add an assertion on "
                "observable behavior, or remove the test.",
            )
        snapshots = tuple(assertion for assertion in assertions if assertion.snapshot)
        if len(snapshots) != len(assertions):
            return None
        return self._finding(
            context,
            snapshots[0].node,
            _VACUOUS,
            "warning",
            f"Test {test} only asserts a snapshot, which can be accepted mechanically "
            "without verifying behavior. Add a behavioral assertion alongside the snapshot.",
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
