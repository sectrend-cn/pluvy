# Agent integration notes — pluvy skill

How a consuming repository connects an agent to this skill, and the limits
that apply. Anchors in these notes point inside the skill directory; bare file
names such as `README.md` name files of the pluvy source repository for
reference only, not resolvable anchors; no network location is assumed.

## Generic statement (any agent)

This skill is a plain directory with a `SKILL.md` in Agent Skills format. Any
agent that implements the Agent Skills directory convention can discover it
under `.agents/skills/` (project level, found from the working directory up
through its ancestors) or `~/.agents/skills/` (user level). Any agent that can
read files and run shell commands can also use it without a discovery
mechanism: read `.agents/skills/pluvy/SKILL.md` from the consuming
repository and follow it, for example through the AGENTS.md pointer snippet in
SKILL.md. Nothing here promises that a specific tool will discover or load the
skill on its own; the concrete integration steps are up to each agent.

## Repository adoption and automatic runs

Skill discovery is separate from repository adoption. Installing this skill at
user level makes it available across repositories; it does not require every
repository to run the gate. Follow [the applicability decision](../SKILL.md#decide-whether-the-gate-applies)
before automatic execution or reporting. A pointer to this skill is a reading
instruction, not a project requirement to run the gate.

| Repository or task context | Expected agent behavior |
|---|---|
| Global executable or skill only; no project policy, requirement or explicit run request | No gate command and no gate notice in the task report |
| Default project policy exists | Run the post-task gate and report its actual result |
| Project instructions, scripts or CI explicitly require the gate via a custom `--config` | Use the declared root and config, even without the default policy |
| Project requires the gate but its policy is missing | Report the configuration failure; do not treat it as non-adoption |
| Policy is malformed or unreadable | Report the failure; preserve exit code 2 |
| User explicitly requests a run without a policy | Attempt the requested run and report the configuration failure |
| User asks about capabilities before adoption | Answer the question without automatically running the gate or creating a policy |

Do not create a policy to silence a post-task warning. Adoption is a separate
requested task. Repository tests, linting and type checks retain their own
requirements regardless of whether this gate applies.

## Adapting agent-specific skill directories

Some agents load skills only from their own directory. Where that directory
lives decides the form:

- Outside the audited repository root (`--root`), for example a user-level or
  agent-specific skills directory, a symlink keeps a single source of truth:

```sh
ln -s /absolute/path/to/repo/.agents/skills/pluvy <agent-skills-dir>/pluvy
```

- Inside the repository root (`--root`), apart from built-in infrastructure
  directories such as `node_modules`, `.venv` or `__pycache__`, which are
  always skipped regardless of policy, a directory symlink is allowed during
  directory enumeration only when the policy proves no selected file can exist
  below the symlink's own path or an ancestor directory; Pluvy never resolves
  the symlink target when deciding scope. That holds when no `include` pattern
  can reach below that path (for example `include: ["src/*", "tests/*"]`) or
  when an `exclude` pattern covers every descendant below it (for example
  `exclude: [".claude/*"]`, which prunes `.claude` even though the pattern
  matches descendants rather than `.claude` itself). Otherwise — including
  under the default policy (`include: ["**"]`, `exclude: []`) — copy the
  directory instead.

  During disk traversal, Pluvy checks whether a directory can contain selected
  files before refusing symlinks (prune first, then check directory symlinks).
  `include` and `exclude` use case-sensitive shell matching (`fnmatchcase`)
  where `*` spans `/` and `**` has no special meaning. Pruning is conservative:
  a directory is pruned only when it is proved that no selected file can exist
  below it, and any directory that cannot be proved stays in scope. Each
  pattern's head is compared character by character against the start of the
  directory prefix (`<directory>/`), with `?` matching one character, stopping
  at `*`, `[` or the end of the directory prefix:

  - **`include` pruning**: a pattern can reach below the directory whenever its
    head matches the start of the directory prefix and its remaining tail is
    non-empty (so `src/*/` keeps `src`, `src/*` and `src/**` reach only `src`
    and its descendants, leading-star patterns such as `**` and `*.py` reach
    every directory, and stopping at `[` prevents character classes from
    proving a directory unreachable). Under `include` alone, a directory is
    pruned only when no `include` pattern can reach below it.
  - **`exclude` pruning**: a pattern covers every path below the directory only
    when its head matches the start of the directory prefix (allowing `?`, such
    as `src/?endor/*`) and its remaining tail is non-empty and consists purely
    of stars (such as `src/vendor/*`, `src/vendor/**`, `.claude/*` or `**`).
    Patterns containing `[` and structured patterns such as `src/*.py` or
    `src/*/*` never prune directories.

  Pruned directories are never entered, so directory symlinks and unreadable
  directories at or inside pruned directories (as well as dangling symlinks
  inside them) do not affect `--all` or `--base` directory enumeration and emit
  no warning. Any directory symlink that stays in scope is rejected with exit
  code 2
  (`Architecture gate error: Refusing to traverse symlink directory: ...`),
  never skipped or downgraded to a warning. Neither `--all` nor `--base` usage
  traversal consults `.gitignore`, so a Git-ignored directory symlink that
  stays in scope fails with exit code 2 unless `exclude` proves no selected
  file can exist below its path.

  Pruning applies only to directory enumeration, not direct source reads: with
  `include: ["src/*"]`, if Git reports a selected changed or untracked path
  whose own entry is a symlink (for example a directory symlink named
  `src/link.py`), `--base` rejects reading that source with exit code 2
  (`Architecture gate error: Refusing source/config symlink: ...`) even when
  `exclude: ["src/link.py/*"]` covers every descendant; `--all` prunes that
  directory entry only because such an `exclude` covers its descendants, and
  without that `exclude` `--all` also exits 2 with
  `Refusing to traverse symlink directory`. For `--base <commit>`, changed and
  untracked paths come from Git, and disk traversal for usage evidence runs
  only when at least one selected current source is present (changed or
  untracked; deletions alone do not count) and at least one of the four
  `unused.*` checkers (`unused.parameter`, `unused.function`, `unused.field`,
  `unused.return`) is enabled. With no selected current sources (`0 files`, for
  example `pluvy --base HEAD` on an unchanged tree), `--base` still reads the
  policy and, when `test.deletion` is enabled, checks Git deletions (which can
  exit 1), but skips the usage directory walk, so it does not surface an
  in-scope directory symlink. If current source changes were expected, an
  exit-0 `0 files` report does not validate them (see
  [post-run checks](../SKILL.md#post-run-checks)). Disabling all four
  `unused.*` checkers skips only the usage directory walk (JSON output reports
  `usage_files` as `0`; text output omits the usage reference line); it does
  not prevent the direct source-read refusal described above. `--staged` never
  walks the disk.

  When using a copy, treat it as a drifting duplicate: re-copy after every
  update of the source, otherwise the two locations diverge silently. Windows
  systems without usable symlinks use the copy form everywhere.

## Team / CI usage

Any CI system that can install the `pluvy` package from PyPI integrates with
the same commands used locally. The pluvy repository itself runs the same
engineering checks in GitHub Actions (`.github/workflows/engineering.yml`).
A pre-commit hook can run `pluvy --staged` once the
policy file is committed; the hook must be installed explicitly, because the
tool never changes Git configuration. The `README.md` integration section
carries the background.
