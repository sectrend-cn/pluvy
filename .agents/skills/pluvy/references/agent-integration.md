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
  directories such as `node_modules` or `.venv`, which are always skipped
  regardless of policy, a directory symlink is allowed during directory
  enumeration only if the policy proves no selected file can exist below its
  path or an ancestor. Either no `include` pattern reaches below it or an
  `exclude` pattern covers all descendants (`include: ["src/*", "tests/*"]` or
  `exclude: [".claude/*"]`). Pluvy never resolves symlink targets when deciding
  scope. Otherwise, including under the default `include: ["**"]`, copy the
  directory as a drifting duplicate and re-copy it after every update. Windows
  systems without usable symlinks use the copy form everywhere. Patterns are
  case-sensitive `fnmatchcase` (`*` spans `/`; `**` is not special), and pruning
  is conservative and happens before the symlink check:

  - **Head/tail**: Each pattern's head is compared character by character with
    the start of `<directory>/`, where `?` matches one character. It stops at
    `*`, `[` or the prefix end, and the rest is the tail.
  - **`include`**: A pattern reaches below a directory if its head matches with
    a non-empty tail. `src/*/` keeps `src`; `src/*` and `src/**` reach `src` and
    its descendants; leading stars (`**`, `*.py`) reach all directories.
    Stopping at `[` means a character class can never prove a directory
    unreachable. Under `include` alone, a directory is pruned only if no include
    pattern reaches below it.
  - **`exclude`**: A pattern covers all paths below a directory only if its head
    matches (`?` is allowed, as in `src/?endor/*`) and its tail is one or more
    stars. Examples are `src/vendor/*`, `src/vendor/**`, `.claude/*` and `**`.
    Patterns with `[` or structured tails (`src/*.py`, `src/*/*`) never prune.

  Pruned directories are never entered, so directory symlinks and unreadable
  directories at or inside them, and dangling symlinks inside them, never
  affect `--all` or `--base` directory enumeration and emit no warning. Neither
  walk consults `.gitignore`, so a Git-ignored directory symlink is treated
  like any other. Any directory symlink that stays in scope fails with exit
  code `2` (`Architecture gate error: Refusing to traverse symlink directory:
  ...`) and is never skipped or downgraded to a warning.

  Pruning covers enumeration, not direct reads. With `include: ["src/*"]`, Git
  can report a selected changed or untracked path whose entry is a symlink,
  such as the directory symlink `src/link.py`. `--base` exits `2`
  (`Architecture gate error: Refusing source/config symlink: ...`) even if
  `exclude: ["src/link.py/*"]` covers all descendants. `--all` prunes it only
  with that `exclude`, and otherwise exits `2` (`Refusing to traverse symlink
  directory`).

  In `--base <commit>`, changed and untracked paths come from Git; usage
  traversal runs only when at least one selected current source is present
  (changed or untracked; deletions alone do not count) and at least one
  `unused.*` checker is enabled. With `0 files` (for example `pluvy --base
  HEAD` on an unchanged tree), `--base` still reads the policy and checks Git
  deletions if `test.deletion` is enabled. That deletion check can exit `1`;
  because the usage walk is skipped, an in-scope directory symlink is not
  surfaced. If current source changes were expected, an exit-`0` `0 files`
  report does not validate them ([post-run
  checks](../SKILL.md#post-run-checks)). Disabling all four `unused.*`
  checkers skips only that walk; it does not prevent the direct source-read
  refusal. `--staged` never walks the disk.

## Team / CI usage

Any CI system that can install the `pluvy` package from PyPI integrates with
the same commands used locally. The pluvy repository itself runs the same
engineering checks in GitHub Actions (`.github/workflows/engineering.yml`).
A pre-commit hook can run `pluvy --staged` once the
policy file is committed; the hook must be installed explicitly, because the
tool never changes Git configuration. The `README.md` integration section
carries the background.
