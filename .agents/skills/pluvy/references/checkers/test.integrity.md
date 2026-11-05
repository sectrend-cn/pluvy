# `test.integrity`

[Back to the checker index](../checkers.md)

Reports assertions that cannot fail (`test.tautology`) and tests without a
meaningful assertion (`test.vacuous`). Only the current syntax tree is inspected:
the checker does not execute tests, follow data flow or compare snapshot content.

**Severity**: error for `test.tautology` and for `test.vacuous`, except that a
test whose only assertions are snapshot matchers reports `test.vacuous` as a
warning.

**Languages**: every analyzer; recognized test declarations and assertions
differ:

| Language | Test declarations and recognized assertions |
| --- | --- |
| Python | Module-level and class-level `def test_*` functions; `assert` statements and `assert*`/`_assert*` calls, with `pytest.raises` and `assertRaises` counted as assertions. |
| JavaScript, TypeScript, TSX | `it(...)` and `test(...)` callbacks; `expect(...).matcher(...)` chains and `assert*`/`_assert*` calls. |
| Go | `func Test*` functions; `t.Error*`, `t.Fatal*` and `t.Fail*` calls. |
| Java | `@Test` methods; `Assertions.assert*` and inherited `assert*` calls plus `assert` statements. |

A test is reported by default only when its path matches one of the default test
globs. The checker classifies recognized assertions one site at a time. An
assertion whose two operands have the same source spelling, a literal-true
assertion or literal-true `assertTrue`, and an equality assertion such as
`assertEquals(x, x)` are tautologies. The always-true matchers are
`.not.toThrow()`, `toBeTruthy()` and `toBeDefined()`. `toBe`, `toEqual` and
`toStrictEqual` are compared structurally, and `assertEquals`/`assertSame` do the
same in Java; Go does not claim mirrored or always-true forms. Each assertion
site produces at most one diagnostic, and a test containing both kinds reports
each defective site separately.

A test with no recognized assertion is vacuous only when its body also has no
unrecognized call. Calls to the language print family are exempt from that
conservative check: Python `print`, JavaScript-family `console.*`, Go
`fmt.Print*`/`log.Print*` and Java `System.out.print*`/`System.err.print*`. Any
other unrecognized call can be a custom assertion helper, so the missing-assertion
signal stays silent rather than guessing that the helper cannot fail. The
snapshot signal is independent: a test whose recognized assertions are all
`toMatchSnapshot()` or `toMatchInlineSnapshot()` reports one warning at the first
snapshot assertion, because setup calls do not change the fact that the test
verifies no behavior.

A finding can be suppressed on the next line by naming `test.tautology` or
`test.vacuous` in an approved directive with a reason; the directive applies to
both diagnostics independently. A missing-assertion or snapshot finding can also
be avoided by removing the test from the configured test paths. Disabling
`test.integrity` disables both diagnostics, and text reports list the switch name
rather than the diagnostic IDs.

**Options**: `enabled` (boolean, default `true`); `paths` (tuple of strings,
default `("test_*.py", "*/test_*.py", "*_test.py", "tests/*", "*/tests/*",
"*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "*.test.mjs", "*.test.cjs",
"*.test.mts", "*.test.cts", "*.spec.js", "*.spec.jsx", "*.spec.ts",
"*.spec.tsx", "*_test.go", "*Test.java", "*Tests.java")`). Paths use the shared
case-sensitive `fnmatchcase` dialect: `*` spans `/`, and `**` or brace
alternation have no special meaning. An empty tuple selects no files.

Correct — restrict the checker to two test layouts:

```json
{
  "checkers": {
    "test.integrity": {"paths": ["tests/*", "*.spec.ts"]}
  }
}
```

Incorrect — `globs` is not an option and unknown options are rejected:

```json
{
  "checkers": {
    "test.integrity": {"globs": ["tests/*"]}
  }
}
```

Known limits are deliberate. A custom assertion helper is recognized only when
its name starts with `assert` or `_assert`; other helpers suppress the
missing-assertion signal but are never proven to assert. Identical spelling is
not data flow, so `assert result == service` is not a tautology even when both
names refer to the same value, and a call versus a literal is not a tautology.
Snapshot-only tests receive a warning rather than an error. The path globs can
include non-test files with test-like names, so tighten `paths` when the default
set does not describe a repository.
