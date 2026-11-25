# Pluvy getting started

This guide is for developers adopting Pluvy. It covers installing the CLI,
configuring a policy for a target repository, running day-to-day checks,
triaging existing findings, and running the gate after every code task.

Pluvy is a read-only, parser-backed engineering policy gate: no run mode modifies, stages,
restores, deletes or rewrites source files, and none of them changes Git configuration.

## Quick start

From the root of the Git repository you want to check:

```sh
uv tool install pluvy
mkdir -p .pluvy
echo '{"version": 2, "include": ["src/*", "tests/*"], "checkers": {}}' > .pluvy/pluvy.json
pluvy --all
```

The output lists one finding per line, then a summary. For a `src/app.py` that declares
`def load(value: Any) -> Any` and a test that calls `load(1)` and then asserts `True`:

```text
src/app.py:4:17: type.annotation: Preserve a concrete contract instead of Any
src/app.py:4:17: type.broad: Do not erase contracts with typing.Any
src/app.py:4:25: type.annotation: Preserve a concrete contract instead of Any
src/app.py:4:25: type.broad: Do not erase contracts with typing.Any
tests/test_app.py:5:5: warning: unused.return: Return value from 'load' is discarded
tests/test_app.py:6:5: test.tautology: Assertion in test_load cannot fail because it restates the same expression or a literal true. Assert an independently produced value or outcome instead.
Diagnostic scope: full_files.
Usage reference scope: 2 files.
Architecture all: 2 files; 6 findings.
```

Each finding reads `path:line:column: rule: message`. A `warning:` prefix before the rule marks a
warning, which never changes the exit code. Python `typing.Any` triggers both `type.annotation` and
`type.broad`, so each position appears twice. The final line summarizes the run mode, audited file
count and total findings. Because error-level findings are present, this run exits `1`—the normal
initial baseline on an existing codebase; see
[First full audit of an existing repository](#first-full-audit-of-an-existing-repository).

If your sources live outside `src/` and `tests/`, update `include`: `--all` exits `2` when `include`
matches no supported source files. After reviewing the initial audit, commit `.pluvy/pluvy.json` and
gate new changes against a base commit such as `pluvy --base origin/main`. The sections below cover
each step in detail.

## Installation

### Prerequisites

- Python 3.12 or later.
- `uv` is recommended for managing an isolated tool environment; see the
  [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### Installation from PyPI

Install the CLI from [PyPI](https://pypi.org/project/pluvy/):

```sh
uv tool install pluvy
```

Without `uv`, install with `pip`:

```sh
python -m pip install pluvy
```

To run once without installing, use `uvx pluvy --all`.

`uv tool install` places `pluvy` in uv's executable directory (`uv tool dir --bin`, typically
`~/.local/bin`); run `uv tool update-shell` if that directory is not yet on your `PATH`. `pip`
installs `pluvy` into the target Python environment's scripts directory. Pass `--force` to
`uv tool install` when replacing an existing uv tool installation of the same name.

### Obtaining the source

The PyPI package ships the CLI only. Sample policies under `examples/` and the agent skill under
`.agents/skills/pluvy/` live in the [GitHub repository](https://github.com/sectrend-cn/pluvy); clone
it when you need them. Below, `/path/to/pluvy` refers to that local checkout. Replace `pluvy` with
`/path/to/pluvy` in either install command to install unreleased changes from source.

### Verification

```sh
pluvy --help
pluvy --root /path/to/project --all
```

`pluvy --help` confirms the installation and lists the supported flags: `--root` (default `.`),
`--config` (default `.pluvy/pluvy.json`), `--format` (`text` or `json`), and one required mode from
`--all`, `--staged` or `--base`. The second command audits `/path/to/project`. If that repository
does not have a policy file yet, the command exits `2` and reports the missing file—create the
policy as shown in [Configuration](#configuration) and run the check again.

### Obtaining the skill

Copy `.agents/skills/pluvy/` from a repository checkout into the target project's skills directory.
See [Agent integration](#agent-integration) for supported layouts.

## Configuration

### Establishing a repository policy

Every target repository commits its own `.pluvy/pluvy.json` (resolved relative to `--root` in all
modes). Pluvy has no subcommand that generates or initializes a policy; write and commit the file
directly. The CLI defines only `--all`, `--staged`, `--base`, `--root`, `--config` and `--format`,
plus `-h, --help`.

You can start either by copying the [sample policy](../examples/.pluvy/pluvy.json) to
`.pluvy/pluvy.json` and adapting its paths, or by writing a minimal policy where an empty (or
omitted) `checkers` object leaves all 22 checkers enabled with their defaults:

```json
{"version": 2, "include": ["src/*", "tests/*"], "exclude": [], "checkers": {}}
```

Common settings to layer in as needed:

- `include` / `exclude`: select which files participate in all checks (case-sensitive, `*` spans
  `/`, paths relative to the repository root).
- `owners` under `architecture.owner`: assign a single accountable owner to every selected file.
- `boundaries` under `architecture.import`: forbid specific cross-layer dependency directions.
- `function_size`: set maxima for function lines, statements, complexity, nesting and parameters.

When building up from a minimal policy, apply one step at a time and inspect the output before
moving on:

1. Set `include` and `exclude` to match the repository's source and test directories.
2. Run `pluvy --all` to establish a baseline. Existing repositories usually exit `1` (see
   [First full audit of an existing repository](#first-full-audit-of-an-existing-repository)); if no
   supported source files match, `--all` exits `2` so you can fix `include` first.
3. Declare `owners` under `architecture.owner` for all selected files.
4. Add `boundaries` under `architecture.import`.
5. Tune `function_size` limits or declare project serializers under `type.broad.encoding` where
   justified.

Threshold, exclusion, owner and boundary edits are policy changes: review each one with a full
`--all` audit as described next rather than using it to silence findings.

### Discipline for changing the policy

Changing thresholds, exclusions, owners, boundaries or checker `enabled` flags is an architecture
decision, not a way to clear findings. Both the initial policy and every later revision require a
full `--all` audit and human review before commit. While `.pluvy/pluvy.json` has staged changes in
the Git index, `--staged` exits `2` rather than checking staged code against an unreviewed policy.
Once committed, the revised policy takes effect immediately. If a pre-commit hook runs
`pluvy --staged`, commit the reviewed policy change in its own commit and bypass the hook for that
commit only (for example with `git commit --no-verify`).

See [Checker configuration](checker-configuration.md) for all options, per-language coverage and
analysis limits.

## Running

Pass exactly one of the three mutually exclusive modes (`--all`, `--staged` or `--base <commit>`):

- `--all`: audits every working-tree file matched by the policy, **including** Git-ignored files,
  exposing all existing debt.
- `--base <commit>`: compares `<commit>` against the working tree, **including** untracked files
  (new files are audited in full).
- `--staged`: reads only staged index blobs and the staged policy, ignoring unstaged working-tree
  edits.

Canonical commands:

```sh
pluvy --all
pluvy --staged
pluvy --base <commit>
pluvy --root /path/to/project --all
pluvy --all --format json
```

`--root` defaults to the current directory (and must be the repository root in Git modes);
`--config` defaults to `.pluvy/pluvy.json`. They combine as
`pluvy --root /path/to/project --config .pluvy/pluvy.json --all`.

Exit codes:

| Exit code | Meaning |
|---|---|
| `0` | No error-level findings; warnings do not change the exit code |
| `1` | At least one error-level finding |
| `2` | Configuration, encoding, filesystem or Git failure (including `--staged` while a policy change is staged) |

Change modes (`--base` and `--staged`) parse full file snapshots for cross-reference resolution,
then filter reported findings to **affected definitions and module statements**: editing inside a
function selects the entire function (including decorators and signature), editing a class header
selects the class, editing a module statement selects that statement, pure deletions keep a nearby
line anchor, and untracked files are audited in full. File ownership and placement rules still apply
to every changed file. Reports distinguish `full_files` from `affected_definitions_and_statements`
via `scope`.

Additional runtime rules:

- An empty `--all` run fails as a configuration error (exit `2`), whereas an empty change run
  reports `0` files and exits `0`.
- Syntax errors emit a warning on `stderr` without changing the exit code; enabled rules continue on
  the recovered tree, so results on broken syntax may be incomplete.
- `--format json` outputs `mode`, `scope`, `files`, `usage_files`, `disabled_checkers` and
  `findings` (each with `severity`). Treat the JSON fields as implementation-defined across minor
  upgrades rather than a frozen external schema.

### Troubleshooting

| Output | Cause | What to do |
|---|---|---|
| `Architecture gate error: [Errno 2] No such file or directory: '.../.pluvy/pluvy.json'` | No policy under `--root`, or the command ran from a subdirectory | Add the policy, run from the repository root, or pass `--root` |
| `Architecture gate error: fatal: Needed a single revision` | The `--base` commit does not exist (for example `--base HEAD` before the first commit) | Create an initial commit first, or run `--all` |
| `Architecture gate error: Policy changed in index; review it and run --all before adoption` | `--staged` ran with a staged policy edit | Commit the reviewed policy separately per [Discipline for changing the policy](#discipline-for-changing-the-policy) |
| `Architecture base: 0 files; 0 findings.` with exit `0` | No diff against the chosen base (for example `--base HEAD` after committing task changes) | Not a valid pass: rerun against the parent of the task's first commit |

## Triage

### The three disposition paths

1. **Fix the code first**: a finding indicates a broken contract or boundary, so repairing the code
   is the default response.
2. **Approved next-line suppression (all supported languages)**: Python (`#`) and Go, Java and the
   JavaScript/TypeScript family (`//`) accept a standalone next-line directive naming one exact
   diagnostic ID and a reason. Use this only when **explicit human approval was granted beforehand**:
   the reason records that approval rather than proving safety, and reviewers must revisit it if the
   code's role changes. Block comments, wildcards, rule lists and missing reasons fail with
   `type.suppression`. Full syntax and rules:
   [Approved next-line diagnostic exceptions](comment-suppressions.md).
3. **Policy revision**: changing thresholds, exclusions or owners requires a standalone `--all`
   audit and architecture review; never weaken the policy to manufacture a passing run.

### Debt semantics

`--all` surfaces repository-wide debt, while `--base` scopes findings to definitions and statements
touched by a change; one mode cannot substitute for the other:

- `0`: no error-level findings in this run's scope; warnings may be present.
- `1`: at least one error-level finding in this run's scope; address each finding before completing the task.
- `2`: the gate could not complete (configuration, encoding, filesystem or Git failure); fix the
  configuration or environment error first, then rerun the gate.

### First full audit of an existing repository

On an existing codebase, the first `pluvy --all` run after creating a policy normally exits `1`.
Treat that output as your baseline inventory rather than a tool error:

1. Inspect the findings and fix genuine contract or test defects first.
2. Where findings reflect accepted legacy debt or default limits that do not fit the codebase,
   adjust thresholds, exclusions or owners deliberately, then rerun `--all` and review.
3. Record which findings were fixed, which were accepted via policy configuration, and the review
   decision.

## Per-task gating

Run Pluvy once at the end of every code task—before reporting the work complete—and report the mode,
exit code, error/warning counts and key findings truthfully; the same standard applies to human and
agent changes. The command-selection table (uncommitted edits, task commits, unknown start commit,
and `--staged` scope), binding gate rules, post-run checks and report format are defined in the
[pluvy skill](../.agents/skills/pluvy/SKILL.md). Always check the file count on the summary line
(`Architecture base: N files; M findings.`): `0 files` when code actually changed means the `--base`
commit was chosen too late and does not count as a pass.

## Agent integration

The skill bundle lives under `.agents/skills/pluvy/` in a repository checkout (`SKILL.md` plus
`references/`). Three integration options are supported:

1. **Standard skills directory**: copy `.agents/skills/pluvy/` into the target project's or user's
   skills directory so compatible agents discover and load it automatically.
2. **Agent-specific directory adaptation**: when an agent reads instructions only from its own
   directory, choose copy versus symlink based on where that directory lives:
   - **Inside the repository (`--root`)**: apart from built-in infrastructure directories such as
     `node_modules` or `.venv`, which are always skipped, a directory symlink is tolerated during
     directory enumeration only if the policy proves no selected file can exist below its path or
     an ancestor. Either no `include` pattern reaches below it or an `exclude` pattern covers every
     descendant (`include: ["src/*", "tests/*"]` or `exclude: [".claude/*"]`). Pluvy never resolves
     the symlink target when deciding scope. Otherwise, including under the default
     `include: ["**"]`, copy the directory and re-copy it when its source updates. Out-of-scope
     directory symlinks never affect `--all` or `--base` enumeration and emit no warning. An
     in-scope directory symlink fails with exit code `2` (`Refusing to traverse symlink directory`)
     and is never skipped or downgraded to a warning. Pruning does not cover direct reads, so
     `--base` still refuses a symlink that Git lists as a selected changed or untracked source.
     Neither `--all` nor `--base` usage traversal consults `.gitignore` ([Running](#running)), so a
     Git-ignored in-scope directory symlink still fails with exit code `2`; `--staged` never walks
     the disk. `--base` walks the disk for usage evidence only when at least one selected changed
     or untracked current source is present (deletions alone do not count) and an `unused.*`
     checker is enabled; a `0 files` run skips that walk, and an exit-`0` `0 files` report does not
     validate expected changes ([Per-task gating](#per-task-gating)). See the agent integration
     notes for exact pruning rules.
   - **Outside `--root`** (such as a user-level skills directory): a symlink works cleanly and keeps
     a single source of truth.
3. **AGENTS.md pointer snippet**: for agents that read `AGENTS.md`, paste the snippet below into
   that file manually (never auto-rewrite a user's `AGENTS.md`):

```markdown
<!-- pluvy skill pointer -->
When adopting, configuring, or running pluvy, or triaging its findings,
first read `.agents/skills/pluvy/SKILL.md` and follow it.
```

For the general integration paths and limits, see
[agent integration notes](../.agents/skills/pluvy/references/agent-integration.md). Agents reading
the published documentation over HTTP can fetch `/llms.txt` for a structured index, `/llms-full.txt`
for the single-file plain-text corpus, or append `.md` to any documentation URL (for example
`/docs/getting-started.md`).
