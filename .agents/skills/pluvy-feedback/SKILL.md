---
name: pluvy-feedback
description: Report suspected pluvy false positives to the project issue tracker. Use when a local pluvy scan produces findings the user believes are wrong, when you must prepare a minimal reproducible snippet and a ready-to-paste GitHub issue (diagnostic ID, installation and version, OS, command line, policy, reproduction, scale, reasoning), or guide submission through the GitHub CLI or a manual paste; also covers recommending one approved next-line suppression comment instead of an issue for one-off cases that do not generalize.
---

# Reporting pluvy false positives

When pluvy findings look wrong, the defect belongs upstream in the checker,
not in the scanned project. This skill turns a suspicion into evidence,
decides whether it generalizes, builds a minimal reproduction, and prepares a
GitHub issue for the project repository (https://github.com/sectrend-cn/pluvy).

## When to use this skill

- A local pluvy run (task gate or full audit) reports findings the user
  believes are wrong, or a specific diagnostic ID seems to misreport a common
  construct.
- The user wants a reproducible snippet or an issue draft.

Not for policy changes (thresholds, excludes, owners, boundaries, enable
flags): those are architecture decisions with their own audit and review, and
never a way to make a report disappear.

## Ground rules

1. Treat the scanned project as read-only: collect evidence by re-running the
   gate, never by editing its sources or policy to change the result.
2. One issue carries exactly one diagnostic ID — the `rule` value printed by
   the gate. Two rules mean two issues.
3. Never add suppressions, lower limits or disable checkers to silence the
   report; an approved suppression answers an approved exception, not a
   possible checker defect.
4. Never submit an issue without explicit user consent. You prepare the text
   and the commands; the user decides whether it is filed.
5. Report only observed behavior; state unknown facts (for example the
   installed version) as unknown instead of guessing.

## Step 1 — Collect evidence

Record the exact command line the user ran (mode and every option) and the
exit code. For structured data rerun the gate:

```sh
pluvy --all --format json
```

Use `--root` when the scanned project is not the current directory, and
`--config` when its policy is not at the default `.pluvy/pluvy.json`
(resolved relative to the root):

```sh
pluvy --root <project root> --config <policy path> --all --format json
```

From the JSON report take each finding's `rule` (the diagnostic ID), `path`,
`line`, `column`, `message` and `severity`. Group by `rule`; for the one ID
the user complains about, count the finding total N, the distinct files M,
and keep a short list of sample paths.

In text format each finding is one line of
`path:line:column: rule: message`, with `warning: ` inserted before the rule
for warnings, and the run ends with a summary line such as
`Architecture all: 12 files; 3 findings.` Exit codes: `0` no error-severity
findings, `1` error-severity findings present, `2` configuration, filesystem,
encoding or Git failure.

Also collect the environment facts the issue needs: how pluvy was installed;
the version that installation exposes — `uv tool list`,
`python -m pip show pluvy`, or `git describe --tags` inside a checkout (the
CLI has no version flag; when none of these prints a version, record the
version as unavailable); and the operating system and language/runtime of the
scanned sources.

## Step 2 — Triage universality

Reduce the finding to one minimal self-contained snippet, then ask: is this
construct common, and would another project hit it too?

**No universality** — a project-specific pattern, an intentional exception, a
single odd file. Do not file an issue. Recommend an approved next-line
suppression comment instead, using the language's own line-comment marker:

```python
# pluvy: ignore-next-line type.annotation -- Legacy adapter boundary.
value: object = read_payload()
```

The same directive form with `//` covers Go, Java and the JavaScript family.
The directive is a standalone comment on the physical line immediately before
the finding, naming one exact diagnostic ID and followed by `-- ` and a
nonblank reason.
State these constraints when you recommend it:

- the exception must have been explicitly approved by a human beforehand; the reason
  only records that approval and is not proof of safety;
- metric findings are suppressed by their metric ID (for example
  `size.lines`), not by the checker key;
- block comments, wildcards, lists, a missing reason and a directive with no
  matching finding are all invalid and are themselves reported as
  `type.suppression`;
- `type.suppression` cannot suppress itself.

**Suspected generalizable checker defect** — several independent locations,
or a common construct reported wrongly. Continue with step 3.

## Step 3 — Build a minimal reproduction

Build the reproduction in a system temporary directory, isolated from the
scanned project, and never modify the scanned project to produce it:

```sh
mkdir -p <repro>/.pluvy
```

Layout:

```
<repro>/
  .pluvy/pluvy.json
  sample.py
```

The policy file is mandatory (a missing policy fails with exit code 2); the
minimal valid policy is an empty object, plus only the checker options that
matter for this false positive:

```json
{}
```

Add the smallest source file that still triggers the rule, then run:

```sh
pluvy --root <repro> --all --format json
```

`--all` reads the files on disk and needs no Git repository, which is why the
temporary directory works. Confirm that the same `rule` still appears and
keep the exact output. If the finding disappears, the report is not
reproducible in isolation: say so and do not file an issue. Delete the
temporary directory once the issue text is written.

## Step 4 — Compose the issue

Write the issue body to a file in the workspace, named for the diagnostic ID
(for example `pluvy-false-positive-type.broad.md`), report its actual path,
and show the same body in a fenced block so the user can copy it. Fill every
field from the observations made in steps 1 to 3:

````markdown
## Diagnostic

- Diagnostic ID: `<rule>` (the `rule` field of the report)
- Language / analyzer: <language>
- Severity: <error or warning>

## Environment

- Installation: <how pluvy was installed>
- Version: <version visible from that installation, or "unknown">
- OS: <operating system and version>
- Scanned source language / runtime: <language and runtime version>

## Command line

```sh
pluvy --root <root> --config <policy-path> --all --format text
```

## Policy (`.pluvy/pluvy.json`)

```json
{}
```

## Minimal reproduction

Layout:

```
<repro>/
  .pluvy/pluvy.json
  sample.py
```

Policy `.pluvy/pluvy.json`:

```json
{}
```

`sample.py`:

```python
def add(left, right):
    return left + right
```

Command:

```sh
pluvy --root <repro> --all --format text
```

Expected behavior: <what the correct result is — for a false positive that
usually means no finding is reported here — and why>

Actual output:

```
<paste the full text output of the reproduction run, line for line>
```

## Scale in the original project

- Findings for this diagnostic ID: <N>
- Files involved: <M>
- Sample paths: <path>, <path>, <path>

## Why this looks like a false positive

<the code semantics, what the checker appears to assume, and where the two
diverge>

## Workarounds tried (optional)

<what was attempted and why it is not an acceptable resolution>
````

Replace the example file names and code with the real reproduction. Keep the
actual output verbatim — do not paraphrase or trim lines that change its
meaning.

The repository offers the same fields as a GitHub issue template: the
new-issue page at https://github.com/sectrend-cn/pluvy/issues/new has a
`False positive report` template that pre-fills the suggested title and the
same fields for the manual path in step 5; the `gh issue create --body-file`
command sends the body file prepared here verbatim.

## Step 5 — Guide the submission

The submission decision belongs to the user. Present both paths, then wait.

**Path A — GitHub CLI.** Check that the CLI is authenticated:

```sh
gh auth status
```

If it is available and the user explicitly agrees, create the issue from the
file you wrote:

```sh
gh issue create --repo sectrend-cn/pluvy --title "<title>" --body-file "<body file>"
```

Suggested title: `False positive: <rule> (<language>)`. Report the issue URL
that the command prints. If `gh` is missing or unauthenticated, or the user
declines, use path B.

**Path B — manual paste.** Open
https://github.com/sectrend-cn/pluvy/issues/new and paste the title and the
body from the file or the fenced block above.

Rules for both paths:

- Do not submit, and do not click for the user, without their explicit
  consent.
- Do not attach secrets, credentials or unrelated proprietary source; the
  reproduction should be the minimal snippet only.
- Do not batch-add suppressions or edit the scanned project's policy to make
  the report disappear while waiting for a fix.
