# Checker configuration

`.pluvy/pluvy.json` is the policy used when checking a target repository. It does
not modify application behavior or rewrite source. Error findings return exit code 1; warning-only results return 0;
invalid configuration and analysis failures return exit code 2.

Each repository commits its own policy at this default path. Start with
[the example](../examples/.pluvy/pluvy.json) and adapt it to the
repository's architecture. All selection and checker paths are relative to the
repository root, not `.pluvy/`.

Per-checker configuration examples are also bundled in the agent skill under
[the checker index](../.agents/skills/pluvy/references/checkers.md).

`--config` selects the policy path; it stays relative to `--root` in every mode and
must name a path inside the root. There is no automatic fallback to a root-level
policy file. Staged checks read that exact path from the index and reject staged
policy changes pending a full audit and review.

Checker settings belong under `checkers`; top-level checker settings are rejected.

The policy separates global file selection from checker options:

```json
{
  "version": 2,
  "include": ["src/*", "tests/*"],
  "exclude": [],
  "checkers": {
    "function_size": {"lines": 50},
    "architecture.object_model": {
      "enabled": false,
      "paths": ["src/plugins/*"]
    }
  }
}
```

This example checks supported source files under `src/` and `tests/`, enforces a
50-line function limit, and disables non-underscore module-function checking. Other
checkers retain their defaults, including language/rule dispatch checking.

## Options by checker

Every checker supports a strict boolean `enabled`, defaulting to `true`. Omission
of a checker or an option preserves its default. Flags such as `"false"` or `0`
are errors. Unknown checker IDs and options are errors, including when a checker
is disabled. Each entry configures one logical checker. Some checker keys group
related diagnostics: `function_size` owns the five `size.*` IDs,
`test.integrity` owns `test.tautology` and `test.vacuous`, `flow.handling` owns
`flow.swallow` and `flow.fallback`, and `type.contract`
owns `type.nullable` and `type.union`. The run-level `test.deletion` owns its
single diagnostic outside analyzer registration. Every other checker name matches
its diagnostic ID. There is no need to write `enabled: true` or entries that contain
only default options.

| Checker ID | Additional options and defaults | What it checks |
| --- | --- | --- |
| `structure.guarded_projection` | `min_fields: 3` (integer, at least 2) | Repeated guarded field copies in every supported language |
| `function_size` | `lines: 50`, `statements: 50`, `complexity: 10`, `nesting: 3`, `parameters: 5` | All five function metrics |
| `test.integrity` | `paths`: 20 default test-file globs | Tautological assertions and tests without a meaningful assertion |
| `test.deletion` | `paths`: 20 default test-file globs, `snapshot_paths: ["*.snap", "__snapshots__/*", "*/__snapshots__/*"]`, `removed_assertions: 3` (integer, at least 0) | Removed test files, assertion erosion and changed snapshot paths in changed audits |
| `flow.handling` | `max_chain: 3` (positive integer) | Swallowed exception handlers and long `??` chains whose defaults are all bare literals |
| `type.contract` | `max_members: 4`, `optional_fields: 3`, `null_defaults: 3` (positive integers) | Aggregated nullable declarations, bare nullish fallbacks and oversized unions in TypeScript and TSX |
| `type.annotation` | None | Broad or bare Python annotations |
| `type.signature` | None | Missing Python parameter/return annotations |
| `type.broad` | `encoding: {encoders: [], decoders: [], outputs: [], instance_outputs: []}` | Recognized broad type markers and JSON encoding outside proven output or permitted third-party inputs |
| `type.boundary` | None | Unconverted recognized third-party results and callback inputs |
| `unused.parameter` | None | Parameters without read usage |
| `unused.function` | None | Non-exported functions and methods without references |
| `unused.field` | None | Fields without reads, including write-only fields |
| `unused.return` | None | Non-failing warnings for discarded known return values |
| `type.assertion` | None | Unchecked type assertions and casts |
| `type.suppression` | None | Shared foreign suppression directives in every supported language, `NOSONAR`/`CHECKSTYLE:OFF`/`noinspection` only in Java, plus malformed or unused [next-line exceptions](comment-suppressions.md) |
| `imports.wildcard` | None | Python wildcard imports |
| `architecture.owner` | `owners: []` | Exactly one responsibility owner when owners are configured |
| `architecture.structure` | `placements: []` | Selected source paths must match their configured owning locations |
| `architecture.import` | `boundaries: []` | Forbidden source-to-import dependencies |
| `architecture.dispatch` | None | Recognized language/rule identity dispatch |
| `architecture.object_model` | `paths: []` | Non-underscore module-level functions in matching extension files |

Metric maxima must be positive integers and are inclusive. Owners contain `name`
and `paths`. Boundaries contain `name`, `sources`, and `forbidden_imports`.
Ownership does not infer dependency permissions. All matching boundaries apply.
An empty owner list, boundary list, or object-model path list provides no
project-specific facts for that check to enforce.

The three `type.contract` maxima are also positive integers and inclusive: a
count equal to its limit passes, and only a greater count is reported.
`optional_fields` applies per object type or interface declaration,
`null_defaults` per innermost function body, and `max_members` per union
expression after `null` and `undefined` members are removed.

`flow.handling.max_chain` is also a positive integer and uses the same strict
`>`: a `??` chain with as many operators as the limit passes, and only a longer
chain is reported. A chain is reported only when every direct default is a bare
non-nullish literal; parenthesized, asserted and called defaults are not
literals, and a mixed chain stays silent.

`test.deletion.removed_assertions` is a non-negative integer using the same strict
`>`: an assertion count fall equal to the limit passes, and only a larger fall is
reported. Whole-file deletion is not subject to this threshold.

`include` and `exclude` are global and cannot be placed inside a checker. They use
case-sensitive shell matching of root-relative paths, with `*` spanning `/`.
Architecture-specific paths select where that one architecture check applies;
they do not remove files from other checkers.

`test.integrity.paths` selects which files the test-integrity checker analyzes.
`test.deletion.paths` shares the same default and dialect for changed test files.
The default is `["test_*.py", "*/test_*.py", "*_test.py", "tests/*", "*/tests/*",
"*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx", "*.test.mjs", "*.test.cjs",
"*.test.mts", "*.test.cts", "*.spec.js", "*.spec.jsx", "*.spec.ts", "*.spec.tsx",
"*_test.go", "*Test.java", "*Tests.java"]`. The same `fnmatchcase` semantics
apply: matching is case-sensitive, `*` spans `/`, and `**` or brace alternation
have no special meaning. An empty list selects no files.

The schema covers 22 logical checkers, which produce 29 built-in diagnostic IDs.
Language syntax, region boundaries and a configuration example are documented in
[the guarded projection checker reference](../.agents/skills/pluvy/references/checkers/structure.guarded_projection.md).
Custom plugin settings continue
to belong to their typed plugin constructors; arbitrary custom checker names in
this JSON are rejected.

## Language coverage

Six built-in analyzers cover five languages (including JSX and TSX syntax): Python (`.py`, `.pyi`), Go
(`.go`), Java (`.java`), JavaScript and JSX (`.js`, `.jsx`, `.mjs`, `.cjs`),
TypeScript (`.ts`, `.mts`, `.cts`) and TSX (`.tsx`). Every checker is enabled by
default for each selected file. `enabled: false` disables that checker for every
selected file: there is no `enabled` option scoped to one language or one file,
and `include` / `exclude` drop files from all checkers at once, except that
changed snapshot paths reported by the run-level `test.deletion` gate follow the
changed set instead (see [Run-level deletion gate](#run-level-deletion-gate)).
Architecture `placements`, `boundaries` and `paths` select where that one
architecture check applies rather than enabling or disabling it. `owners` is not a scope selector:
when it is configured and the checker is enabled, every selected file must match
exactly one owner. Both are described in [Options by checker](#options-by-checker).
Coverage differences therefore come only from the diagnostics an analyzer registers.

Java analysis uses the locked `tree-sitter-java` grammar and needs no JDK or build
step.

Every analyzer registers the same base set of 19 diagnostic IDs:

- Usage: `unused.parameter`, `unused.function`, `unused.field` and
  `unused.return`, which is always a warning and never fails the gate.
- Boundaries and directives: `type.boundary` and `type.suppression`.
- Function metrics: `size.lines`, `size.statements`, `size.complexity`,
  `size.nesting` and `size.parameters`, all configured through the single
  `function_size` checker.
- Architecture: `architecture.owner`, `architecture.structure`,
  `architecture.import`, `architecture.dispatch` and
  `architecture.object_model`.
- Structure: `structure.guarded_projection`.
- Testing: `test.tautology` and `test.vacuous`, both configured through the
  single `test.integrity` checker.

`test.deletion` is not part of that per-language set: no analyzer registers it,
and it is produced by the run-level deletion gate in `--base` and `--staged` mode.

The remaining nine diagnostic IDs are registered per language:

| Analyzer | Additional diagnostic IDs |
| --- | --- |
| Python | `type.annotation`, `type.signature`, `type.assertion`, `type.broad`, `imports.wildcard`, `flow.swallow` |
| Go | `type.broad` |
| Java | `type.assertion`, `type.broad`, `flow.swallow` |
| JavaScript and JSX | `type.broad`, `flow.swallow`, `flow.fallback` |
| TypeScript and TSX | `type.assertion`, `type.broad`, `type.nullable`, `type.union`, `flow.swallow`, `flow.fallback` |

A registered diagnostic can only report for the analyzer that registered it:
`type.annotation`, `type.signature` and `imports.wildcard` appear in Python files
only, and `type.assertion` covers Python, Java, TypeScript and TSX but not Go or
JavaScript.

`type.broad` recognizes different markers in each language, in addition to the
JSON encoding forms described in
[Serialization boundaries](serialization-boundaries.md):

| Language | `type.broad` markers |
| --- | --- |
| Python | `typing.Any`, `typing_extensions.Any` and `pydantic.JsonValue` references, plus internal `json.dumps`, `dump_json` and `model_dump_json` results |
| Go | `any` and empty interfaces, plus imported `encoding/json` `Marshal`/`MarshalIndent` results |
| Java | `java.lang.Object`, unbounded wildcards and recognized raw collections, plus recognized Gson/Jackson results |
| JavaScript and JSX | `JSON.stringify` results only; JavaScript has no type annotations to check |
| TypeScript and TSX | `any`, `unknown`, `object` and empty object types, plus `JSON.stringify` results |

Python broad annotation markers such as `Any` or `object` are reported by
`type.annotation`, and a `typing.Any` reference additionally triggers
`type.broad`, so one annotation can produce a finding from each checker.
Coverage of a diagnostic does not promise complete evidence for every construct:
resolution limits are described in
[Third-party boundaries and usage](serialization-boundaries.md#third-party-boundaries-and-usage) and
[Configuring encoding APIs](serialization-boundaries.md#configuring-encoding-apis).

## Run-level deletion gate

`test.deletion` is a run-level gate, not an analyzer registration. It activates
only for `--base` and `--staged`; `--all` does not run it. A deleted test file
reports one error with its baseline declaration and assertion counts. A surviving
changed test file is compared with its baseline: a missing declaration name in
the multiset or an assertion count fall greater than `removed_assertions` reports
one error per file. A changed path matching `snapshot_paths` reports one warning
per path. Snapshot warnings are path signals over the changed set; global
`include`/`exclude` do not filter them, so tighten `snapshot_paths` or disable the
checker instead. Exact 100% renames are excluded from both the deletion and
changed-path sets, so a partial rename still appears as a deletion.

Next-line suppression is unavailable. A deleted file has no current snapshot, and
an erosion finding has no corresponding current defect node, so
`pluvy: ignore-next-line test.deletion` in a surviving file is an invalid
directive and produces `type.suppression`. Disable the checker with
`enabled: false` or tighten its globs when a reduction is intentional.

Deleted files are not analyzed inputs: `files` in a text or JSON report counts
only the current selected sources, while deletion findings are added from
baseline evidence. Every `test.deletion` finding is anchored at line 1, column 1
with `scope: "file"`. An unmerged `--staged` index and a baseline blob that is not
valid UTF-8 fail closed with exit code 2.

## Disabling and shared execution

Set `enabled: false` to disable one checker across selected files. Text reports
list disabled checker names, and JSON reports include a `disabled_checkers` array.
For example, `"function_size": {"enabled": false}` disables all five function
metrics and is reported as `function_size`. Findings still use `size.lines`,
`size.statements`, `size.complexity`, `size.nesting`, and `size.parameters`.
The same source may still violate a different enabled checker. For example,
Python `typing.Any` can trigger both `type.annotation` and `type.broad`.

Fully disabled rule bundles are skipped. A bundle with enabled diagnostics may
still share traversal work across its checks; disabled diagnostics are filtered
individually. Errors and undeclared output from an executing bundle still fail
analysis. Disabling a checker does not permit broken plugin registration.

Parsing constructs the context used by enabled checks. Invalid syntax emits
warnings on stderr, including when `--format json` is selected, and checks
continue on the recovered tree. Parser warnings are recorded apart from findings
and never change defect counts or the exit status; they disclose that results may
be inaccurate. Every language uses a tree-sitter context. Rules consume the
available recovered syntax, while analyses requiring complete evidence may be
unavailable. For Java, recovered syntax produces warnings and still permits syntax
checks, while usage and boundary diagnostics require a complete parse. Parser
infrastructure and semantic preparation failures return exit 2. When every
diagnostic provided by an analyzer is disabled, parsing and bundle execution are
skipped.

`syntax.invalid` has been removed from the checker schema and rule declarations.
Remove any `checkers["syntax.invalid"]` entry from existing policies; it is now
rejected as an unknown checker. Parser warnings have no enable/disable option.

Changing enable flags is a policy change subject to the same full-audit and review
requirements as changing thresholds or boundaries. Staged-policy changes remain
blocked by the staged gate; unstaged options do not alter index-based checks.

## Source structure

`architecture.structure` enforces declared source-placement conventions. A file
matching a placement's `paths` must also match at least one of its
`allowed_paths`. Each matching placement is enforced independently; an unrelated
placement does not affect the file. Patterns use the existing case-sensitive
shell matching, where `*` can span directory separators. Paths are repository
relative and pass through the same global include/exclude selection as other
checks. The checker defaults to enabled with an empty `placements` list.

For example, this repository requires language rule modules — `*_rules.py`
modules and each language's `rules.py` — to live with the language plugins:

```json
"architecture.structure": {
  "placements": [{
    "name": "language rule modules belong with language plugins",
    "paths": ["src/pluvy/*_rules.py", "src/pluvy/languages/*/rules.py"],
    "allowed_paths": ["src/pluvy/languages/*"]
  }]
}
```

`src/pluvy/python_rules.py` fails this constraint even if another policy
assigns it a valid owner. `src/pluvy/languages/python/rules.py` passes:
the `src/pluvy/languages/*/rules.py` pattern covers that path. Application
composition in `plugins/builtins.py` imports `PythonTypeRule` from this module:
the language owner covers that path, and existing dependency restrictions and
object-model checks apply to it.

Placement, ownership and import restrictions have independent enable flags.
Placement diagnostics report the source path at line 1, name the constraint and
list the allowed locations. All built-in languages use the same structural
check. Changed modes apply it only to selected source files; staged checks use
index paths and index policy, including when the working tree has moved a file.
The gate never moves files itself.

This is explicit convention enforcement. It does not infer a file's domain from
its name, detect every misplaced class, or prove that a shared abstraction has
real consumers. Those remain source-structure review obligations. The configured
`*_rules.py` convention covers this project's language rule modules; other
projects should declare their own domain-specific placements.

Third-party boundary declarations (`third_party_modules`), cross-file usage
resolution, built-in serializer rules and `checkers["type.broad"].encoding`
options (`encoders`, `decoders`, `outputs` and `instance_outputs`) are
documented in [Boundaries, usage and serialization](serialization-boundaries.md).
