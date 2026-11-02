"""Semantic rule evaluation and validation of agent evidence."""

from dataclasses import dataclass

from pluvy.analysis.context import TreeContext
from pluvy.analysis.requirements import RuleRequirements
from pluvy.diagnostics import AnalysisError, Finding
from pluvy.review.contracts import ReviewAgent, ReviewGuideline, ReviewRequest
from pluvy.review.submission_models import ReviewScope


@dataclass(frozen=True)
class PromptReviewRule:
    """Own one guideline and accept only complete findings about this snapshot."""

    name: str
    guideline: ReviewGuideline
    agent: ReviewAgent
    api_version: int = 2
    requirements: RuleRequirements = RuleRequirements()

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return (self.guideline.rule_id,)

    def check(self, context: TreeContext) -> tuple[Finding, ...]:
        result = self.agent.review(ReviewRequest(context.source, self.guideline))
        if result.status != "complete" or not result.summary.strip():
            raise AnalysisError(f"Agent review did not complete: {result.summary}")
        scope = ReviewScope.from_request(ReviewRequest(context.source, self.guideline))
        for finding in result.findings:
            scope.validate_finding(finding)
        return result.findings
