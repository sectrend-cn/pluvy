# Pluvy

[![PyPI](https://img.shields.io/pypi/v/pluvy)](https://pypi.org/project/pluvy/)
[![Python](https://img.shields.io/pypi/pyversions/pluvy)](https://pypi.org/project/pluvy/)
[![License](https://img.shields.io/pypi/l/pluvy)](LICENSE)

**An engineering policy gate for code written by people and coding agents.**
Pluvy parses Python, Go, Java, JavaScript/JSX and TypeScript/TSX with
tree-sitter and fails the build when a change erases type contracts, swallows
errors, weakens or deletes tests, or crosses the architecture boundaries your
repository declares.

Website: [sectrend-cn.github.io/pluvy](https://sectrend-cn.github.io/pluvy/)

```text
$ pluvy --all
src/orders.py:4:25: type.broad: Do not erase contracts with typing.Any
tests/test_orders.py:5:5: test.tautology: Assertion in test_load cannot fail because it restates the same expression or a literal true. Assert an independently produced value or outcome instead.
tests/test_orders.py:6:5: warning: unused.return: Return value from 'load' is discarded
Diagnostic scope: full_files.
Usage reference scope: 2 files.
Architecture all: 2 files; 3 findings.
```

## Why Pluvy

- **One policy, five languages.** A single committed `.pluvy/pluvy.json`
  drives the same checkers across every supported language.
- **Architecture as data.** Declare owners, placements and forbidden import
  directions; the gate enforces them on every change.
- **Built for agent-written code.** It catches shortcuts that keep CI green
  without doing the work: tautological or assertion-free tests, deleted tests
  and eroded assertions, swallowed exceptions, literal fallback chains, casts
  and `Any`.
- **Change-aware.** `--base` and `--staged` report only the definitions and
  statements a change touches, so existing debt does not block new work.
- **Read-only.** No mode modifies, stages, stashes, restores or deletes source
  files, and none changes Git configuration. It is safe to run in CI, in hooks
  and inside agent sessions.

## What it checks

22 checkers, all enabled by default:

| Area | Checkers |
| --- | --- |
| Type contracts | `type.broad`, `type.annotation`, `type.signature`, `type.boundary`, `type.assertion`, `type.contract` |
| Test integrity | `test.integrity` (tautological and vacuous tests), `test.deletion` (removed tests, assertion erosion, changed snapshots) |
| Error handling | `flow.handling` (swallowed handlers, long `??` literal fallbacks) |
| Architecture | `architecture.owner`, `architecture.structure`, `architecture.import`, `architecture.dispatch`, `architecture.object_model` |
| Dead code | `unused.parameter`, `unused.function`, `unused.field`, `unused.return` |
| Structure and size | `function_size`, `structure.guarded_projection`, `imports.wildcard` |
| Suppression hygiene | `type.suppression` (foreign and malformed suppression directives) |

Options, defaults, per-language coverage and known limits are listed in
[Checker configuration](docs/checker-configuration.md).

## Quick start

Python 3.12 or newer is required. Install the published command line from
[PyPI](https://pypi.org/project/pluvy/):

```sh
uv tool install pluvy
```

Without uv, use `python -m pip install pluvy`. To try it once without
installing, run `uvx pluvy --all`.

Add a policy to the repository you want to check and commit it:

```sh
mkdir -p .pluvy
echo '{"version": 2, "include": ["src/*", "tests/*"], "checkers": {}}' > .pluvy/pluvy.json
```

Then run one of the three modes:

```sh
pluvy --all                 # audit every selected file, including existing debt
pluvy --base origin/main    # audit only what changed since a commit
pluvy --staged              # audit the Git index before committing
```

Add `--root /path/to/project` to run from another directory and
`--format json` for machine-readable output.

| Exit code | Meaning |
| --- | --- |
| `0` | No error findings; warnings may be present |
| `1` | At least one error finding |
| `2` | Configuration, encoding, filesystem or Git failure |

[Getting started](docs/getting-started.md) covers installation options, building
up a policy, triaging the first audit of an existing repository and per-task
gating. A [Chinese translation](docs/zh/getting-started.md) is available.

## Adopting on an existing repository

The first `--all` on an existing codebase usually exits `1`: that is the
baseline reading, not a failure of the tool. Gate pull requests with `--base`
so new changes are held to the policy, work through the `--all` findings over
time fixing the code first, and treat threshold, exclusion and owner changes as
architecture decisions, each with its own full audit and review before the
change is committed; `--staged` refuses to run while a policy change is staged.
Exceptions use an approved next-line
suppression that names one rule and a reason; see
[comment suppressions](docs/comment-suppressions.md).

## Policy

Each target repository owns `.pluvy/pluvy.json`; paths inside it are relative to
the repository root. Start from [the example policy](examples/.pluvy/pluvy.json),
which declares owners, an import boundary and size limits. Specify
`"enabled": false` only to turn a checker off; omitted checkers and options keep
their defaults.

## Integration

### Coding agents

The bundled skill in `.agents/skills/pluvy/` tells an agent when the gate
applies, which mode to run after a task and how to report the result. The PyPI
package contains the tool only, so copy the skill from this repository into the
consuming project's skills directory, or point to it from `AGENTS.md`. See
[Agent integration](docs/getting-started.md#agent-integration).

### CI

Any CI system that can install a Python package can run the same commands.
This repository gates itself in
[GitHub Actions](.github/workflows/engineering.yml).

### Pre-commit

Once the policy is committed, a pre-commit hook can run `pluvy --staged`.
The hook blocks commits that change the policy; see
[Discipline for changing the policy](docs/getting-started.md#discipline-for-changing-the-policy).
Install hooks yourself; Pluvy never changes Git configuration.

## Extending

Language plugins own suffixes and grammar interpretation; rules implement
`RuleBundle` over a shared `TreeContext`. See
[Plugin architecture](docs/plugin-architecture.md).

## Development

Set up a development environment from this checkout:

```sh
python -m pip install --no-cache-dir uv==0.8.22
uv sync --locked --group dev
. .venv/bin/activate
```

The required checks are listed in `AGENTS.md` and run in
[the engineering workflow](.github/workflows/engineering.yml). Shared code
policy lives in [Engineering standards](docs/engineering-standards.md).

## License

[MIT](LICENSE)
