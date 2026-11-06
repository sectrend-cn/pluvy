"""Run-level deletion gate comparing baseline test evidence with changed sources."""

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from pluvy.analysis.context import TreeContext
from pluvy.diagnostics import Finding, SyntaxFailure
from pluvy.policy.models import Policy
from pluvy.policy.paths import matches
from pluvy.semantics.testing.contracts import BaselineParsing, TestBinding, TestSyntax
from pluvy.semantics.testing.options import DELETION, TEST_DELETION
from pluvy.source import Source

_MAX_NAMES = 5


@dataclass(frozen=True)
class TestDeletionGate:
    """Report deleted tests, assertion erosion and changed snapshot paths."""

    bindings: BaselineParsing
    rule_ids: tuple[str, ...] = TEST_DELETION.rule_ids

    def candidates(
        self, current: tuple[Source, ...], changed: tuple[str, ...], policy: Policy
    ) -> tuple[Source, ...]:
        """Select current changed test files whose baseline is worth reading."""
        changed_paths = frozenset(changed)
        paths = policy.checkers.test_deletion.paths
        return tuple(
            source
            for source in current
            if source.path in changed_paths and matches(source.path, paths)
        )

    def evaluate(
        self,
        deleted: tuple[Source, ...],
        baselines: tuple[Source, ...],
        current: tuple[Source, ...],
        changed: tuple[str, ...],
        policy: Policy,
    ) -> tuple[Finding, ...]:
        """Evaluate every deletion signal unless the whole checker is disabled."""
        disabled = policy.checkers.disabled_rules()
        if all(rule in disabled for rule in self.rule_ids):
            return ()
        findings = (
            *self._deleted_findings(deleted, policy),
            *self._erosion_findings(baselines, current, policy),
            *self._snapshot_findings(changed, policy),
        )
        return tuple(sorted(findings, key=_finding_key))

    def _deleted_findings(self, deleted: tuple[Source, ...], policy: Policy) -> tuple[Finding, ...]:
        paths = policy.checkers.test_deletion.paths
        seen: set[str] = set()
        findings: list[Finding] = []
        for source in deleted:
            if source.path in seen or not matches(source.path, paths):
                continue
            seen.add(source.path)
            binding = self.bindings.binding_for(source.language)
            if binding is None:
                continue
            findings.append(
                _file_finding(source.path, "error", self._deleted_message(binding, source, policy))
            )
        return tuple(findings)

    def _deleted_message(self, binding: TestBinding, source: Source, policy: Policy) -> str:
        try:
            context = binding.parser.parse(source, policy)
        except SyntaxFailure:
            return (
                "Deleted test file; baseline test counts are unavailable because the "
                "baseline syntax was rejected. Restore the tests or narrow "
                "test.deletion.paths if the deletion is intentional."
            )
        declarations, assertions = _counts(binding.syntax, context)
        return (
            f"Deleted test file whose baseline contained {declarations} test declaration(s) "
            f"and {assertions} assertion(s). Restore the tests or narrow "
            "test.deletion.paths if the deletion is intentional."
        )

    def _erosion_findings(
        self,
        baselines: tuple[Source, ...],
        current: tuple[Source, ...],
        policy: Policy,
    ) -> tuple[Finding, ...]:
        current_by_path = {source.path: source for source in current}
        paths = policy.checkers.test_deletion.paths
        seen: set[str] = set()
        findings: list[Finding] = []
        for baseline in baselines:
            if baseline.path in seen or not matches(baseline.path, paths):
                continue
            seen.add(baseline.path)
            target = current_by_path.get(baseline.path)
            if target is None or target.language != baseline.language:
                continue
            binding = self.bindings.binding_for(baseline.language)
            if binding is None:
                continue
            try:
                before = binding.parser.parse(baseline, policy)
                after = binding.parser.parse(target, policy)
            except SyntaxFailure:
                continue
            signal = self._erosion_signal(binding.syntax, before, after, policy)
            if signal is not None:
                findings.append(
                    _file_finding(baseline.path, "error", self._erosion_message(*signal))
                )
        return tuple(findings)

    def _erosion_signal(
        self, syntax: TestSyntax, before: TreeContext, after: TreeContext, policy: Policy
    ) -> tuple[tuple[str, ...], int] | None:
        before_declarations = syntax.declarations(before.root)
        after_declarations = syntax.declarations(after.root)
        removed = tuple(
            sorted(
                (
                    Counter(declaration.name for declaration in before_declarations)
                    - Counter(declaration.name for declaration in after_declarations)
                ).elements()
            )
        )
        before_assertions = sum(
            len(syntax.assertions(declaration.node)) for declaration in before_declarations
        )
        after_assertions = sum(
            len(syntax.assertions(declaration.node)) for declaration in after_declarations
        )
        removed_assertions = before_assertions - after_assertions
        if not removed and removed_assertions <= policy.checkers.test_deletion.removed_assertions:
            return None
        return removed, removed_assertions

    def _erosion_message(self, removed: tuple[str, ...], removed_assertions: int) -> str:
        parts: list[str] = []
        if removed:
            parts.append(f"Removed test declarations: {_names(removed)}")
        if removed_assertions > 0:
            parts.append(f"Assertion count fell by {removed_assertions}")
        detail = "; ".join(parts)
        return (
            f"{detail}. Restore the removed tests or narrow test.deletion.paths if the "
            "reduction is intentional."
        )

    def _snapshot_findings(self, changed: tuple[str, ...], policy: Policy) -> tuple[Finding, ...]:
        snapshot_paths = policy.checkers.test_deletion.snapshot_paths
        return tuple(
            _file_finding(
                path,
                "warning",
                "Snapshot file changed; verify the recorded output deliberately. If this "
                "path is not a snapshot store, tighten test.deletion.snapshot_paths.",
            )
            for path in dict.fromkeys(changed)
            if matches(path, snapshot_paths)
        )


def _counts(syntax: TestSyntax, context: TreeContext) -> tuple[int, int]:
    declarations = syntax.declarations(context.root)
    assertions = sum(len(syntax.assertions(declaration.node)) for declaration in declarations)
    return len(declarations), assertions


def _names(removed: tuple[str, ...]) -> str:
    shown = ", ".join(repr(name) for name in removed[:_MAX_NAMES])
    if len(removed) > _MAX_NAMES:
        return f"{shown} and {len(removed) - _MAX_NAMES} more"
    return shown


def _file_finding(path: str, severity: Literal["error", "warning"], message: str) -> Finding:
    return Finding(
        path=path,
        line=1,
        column=1,
        rule=DELETION,
        message=message,
        severity=severity,
        scope="file",
    )


def _finding_key(finding: Finding) -> tuple[str, int, int, str, str]:
    return finding.path, finding.line, finding.column, finding.rule, finding.message
