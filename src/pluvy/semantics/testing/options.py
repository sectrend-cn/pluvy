"""Strict configuration owned by the test integrity checker."""

from pydantic import Field

from pluvy.policy.contracts import (
    CheckerConfiguration,
    CheckerDefinition,
    CheckerOptions,
    CheckerState,
)

TAUTOLOGY = "test.tautology"
VACUOUS = "test.vacuous"
TEST_INTEGRITY = CheckerDefinition("test.integrity", (TAUTOLOGY, VACUOUS))

_DEFAULT_TEST_PATHS: tuple[str, ...] = (
    "test_*.py",
    "*/test_*.py",
    "*_test.py",
    "tests/*",
    "*/tests/*",
    "*.test.js",
    "*.test.jsx",
    "*.test.ts",
    "*.test.tsx",
    "*.test.mjs",
    "*.test.cjs",
    "*.test.mts",
    "*.test.cts",
    "*.spec.js",
    "*.spec.jsx",
    "*.spec.ts",
    "*.spec.tsx",
    "*_test.go",
    "*Test.java",
    "*Tests.java",
)


class TestIntegrityOptions(CheckerOptions):
    """Select test files using the shared case-sensitive shell glob dialect."""

    paths: tuple[str, ...] = _DEFAULT_TEST_PATHS


class TestingCheckers(CheckerConfiguration):
    """Compose the checker schema and its diagnostic switch."""

    test_integrity: TestIntegrityOptions = Field(
        default=TestIntegrityOptions(),
        validation_alias=TEST_INTEGRITY.name,
        serialization_alias=TEST_INTEGRITY.name,
    )

    def checker_states(self) -> tuple[CheckerState, ...]:
        return (
            *super().checker_states(),
            TEST_INTEGRITY.configure(self.test_integrity.enabled),
        )
