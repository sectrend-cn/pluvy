"""Strict configuration owned by the test integrity and deletion checkers."""

from pydantic import Field

from pluvy.policy.contracts import (
    CheckerConfiguration,
    CheckerDefinition,
    CheckerOptions,
    CheckerState,
)

TAUTOLOGY = "test.tautology"
VACUOUS = "test.vacuous"
DELETION = "test.deletion"
TEST_INTEGRITY = CheckerDefinition("test.integrity", (TAUTOLOGY, VACUOUS))
TEST_DELETION = CheckerDefinition(DELETION, (DELETION,))

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


class TestDeletionOptions(CheckerOptions):
    """Select changed test files, snapshot paths and the assertion erosion limit."""

    paths: tuple[str, ...] = _DEFAULT_TEST_PATHS
    snapshot_paths: tuple[str, ...] = ("*.snap", "__snapshots__/*", "*/__snapshots__/*")
    removed_assertions: int = Field(default=3, ge=0)


class TestingCheckers(CheckerConfiguration):
    """Compose the checker schema and its diagnostic switches."""

    test_integrity: TestIntegrityOptions = Field(
        default=TestIntegrityOptions(),
        validation_alias=TEST_INTEGRITY.name,
        serialization_alias=TEST_INTEGRITY.name,
    )
    test_deletion: TestDeletionOptions = Field(
        default=TestDeletionOptions(),
        validation_alias=TEST_DELETION.name,
        serialization_alias=TEST_DELETION.name,
    )

    def checker_states(self) -> tuple[CheckerState, ...]:
        return (
            *super().checker_states(),
            TEST_INTEGRITY.configure(self.test_integrity.enabled),
            TEST_DELETION.configure(self.test_deletion.enabled),
        )
