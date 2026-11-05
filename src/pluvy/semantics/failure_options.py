"""Strict configuration owned by the failure-flow checker."""

from pydantic import Field

from pluvy.policy.contracts import (
    CheckerConfiguration,
    CheckerDefinition,
    CheckerOptions,
    CheckerState,
)

SWALLOW = "flow.swallow"
FALLBACK = "flow.fallback"
FLOW_HANDLING = CheckerDefinition("flow.handling", (SWALLOW, FALLBACK))


class FailureHandlingOptions(CheckerOptions):
    """Limit coalescing chains judged to hide failures behind literal defaults."""

    max_chain: int = Field(default=3, ge=1)


class FailureCheckers(CheckerConfiguration):
    """Compose the failure-flow schema and its diagnostic switch."""

    flow_handling: FailureHandlingOptions = Field(
        default=FailureHandlingOptions(),
        validation_alias=FLOW_HANDLING.name,
        serialization_alias=FLOW_HANDLING.name,
    )

    def checker_states(self) -> tuple[CheckerState, ...]:
        return (
            *super().checker_states(),
            FLOW_HANDLING.configure(self.flow_handling.enabled),
        )
