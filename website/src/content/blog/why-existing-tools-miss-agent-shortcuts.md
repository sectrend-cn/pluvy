---
title: Why Existing Tools Miss Agent Shortcuts
description: Tests, type checkers and linters all pass a change that deletes a test, widens a signature to Any and swallows the error. Here is why, and what a gate has to do differently.
pubDate: 2026-11-12
authors: [Pluvy team]
tags: [engineering, agents, testing]
draft: false
---

Ask a coding agent to make a failing check pass and it will. The question is how.

Sometimes it fixes the bug. Sometimes it widens a signature to `Any`, wraps the failing call in a broad `except`, adds a `noqa` so the linter stops complaining, deletes the test that kept failing and replaces it with one that cannot. Every check you already run goes green. The task looks done, and nothing in your pipeline says otherwise.

The tools we already had could not be configured to stop it, so we built Pluvy. This post explains why.

## One change, five checks

Start with a small function and its tests, committed and passing:

```python
def parse_order(raw: str) -> Order:
    amount, currency = raw.split(" ")
    return Order(total=Decimal(amount), currency=currency)


def test_parse_order() -> None:
    order = parse_order("12.50 EUR")
    assert order.total == Decimal("12.50")
    assert order.currency == "EUR"


def test_parse_order_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_order("twelve")
```

Now apply the kind of change an agent produces when the goal is "make it pass" rather than "make it correct":

```diff
-def parse_order(raw: str) -> Order:
-    amount, currency = raw.split(" ")
-    return Order(total=Decimal(amount), currency=currency)
+def parse_order(raw: Any) -> Any:
+    try:
+        amount, currency = raw.split(" ")
+        return Order(total=Decimal(amount), currency=currency)
+    except Exception:  # noqa: BLE001
+        return None

 def test_parse_order() -> None:
     order = parse_order("12.50 EUR")
-    assert order.total == Decimal("12.50")
-    assert order.currency == "EUR"
-
-
-def test_parse_order_rejects_garbage() -> None:
-    with pytest.raises(ValueError):
-        parse_order("twelve")
+    assert order is not None or True
+    assert True
```

We ran the usual checks against this change:

| Shortcut | pytest | mypy `--strict` | ruff (defaults) | ruff (opt-in rules) | Pluvy |
|---|---|---|---|---|---|
| Signature widened to `Any` | pass | pass | silent | `ANN401` | `type.broad`, `type.annotation` |
| `except Exception` swallows the failure | pass | pass | silent | silenced by the `noqa` | `flow.swallow` |
| `# noqa` added to silence a rule | — | — | honoured | honoured | `type.suppression` |
| A test deleted | pass | pass | silent | silent | `test.deletion` |
| `assert True` | pass | pass | silent | silent | `test.tautology` |

The tests pass because the remaining test cannot fail. mypy is satisfied because `Any` is a legal type. ruff with its defaults reports one style hint about `or True`. Turning on stricter rules catches the `Any`, but the broad exception rule is silenced by the very comment the agent added, and no rule notices that a test disappeared.

Pluvy, run with `pluvy --base HEAD` against the committed baseline:

```text
src/orders.py:12:22: type.annotation: Preserve a concrete contract instead of Any
src/orders.py:12:22: type.broad: Do not erase contracts with typing.Any
src/orders.py:12:30: type.annotation: Preserve a concrete contract instead of Any
src/orders.py:12:30: type.broad: Do not erase contracts with typing.Any
src/orders.py:16:5: flow.swallow: The except Exception handler swallows failures without re-throwing. Re-throw the original error, or narrow the captured type and handle that specific failure.
src/orders.py:16:24: type.suppression: Fix the contract; do not suppress a checker diagnostic
tests/test_orders.py:1:1: test.deletion: Removed test declarations: 'test_parse_order_rejects_garbage'; Assertion count fell by 1. Restore the removed tests or narrow test.deletion.paths if the reduction is intentional.
tests/test_orders.py:7:5: test.tautology: Assertion in test_parse_order cannot fail because it restates the same expression or a literal true. Assert an independently produced value or outcome instead.
Diagnostic scope: affected_definitions_and_statements.
Usage reference scope: 2 files.
Architecture base: 2 files; 8 findings.
```

Exit code 1. Every shortcut is named.

None of this is a criticism of those tools. They answer the questions they were designed for, and you should keep running them. The gap is that the questions changed.

## Why the existing tools cannot close the gap

### They examine one snapshot, and a deletion leaves nothing to examine

A linter or type checker looks at the code as it is now. A deleted test is not in the code as it is now, so there is nothing to flag. Coverage tools have the same blind spot: delete the test and the code it covered, and the percentage can even go up.

Catching erosion requires comparing two snapshots: which test declarations existed at the base commit, how many assertions they had, and what survived. That comparison is a different kind of analysis, not a missing rule. Pluvy's `--base` and `--staged` modes resolve both snapshots from Git and report removed tests and dropped assertions directly.

### The code under review can switch the reviewer off

Every mainstream linter accepts inline directives: `noqa`, `type: ignore`, `eslint-disable`, `@ts-ignore`, `nolint`, `@SuppressWarnings`. That was a reasonable design when the author and the reader of the code were the same careful human. It is a poor design when the author is optimizing for a green check, because the cheapest way to satisfy a rule is to tell it to stop looking.

Pluvy treats those directives as findings in their own right. It recognizes the foreign directives of every supported language and reports them as `type.suppression`. The one exception it accepts is a standalone next-line comment that names exactly one diagnostic and gives a reason, and the reason records an approval a human already gave; it is not a way for the agent to grant itself one.

### The rules that matter are opt-in, and the switch is in the same diff

Several of the checks above exist somewhere: ruff has `ANN401` and `BLE001`, ESLint can forbid `any`. But they are off by default, spread across tools and configured differently for each language. An agent that is allowed to edit the code is usually allowed to edit `pyproject.toml` or `.eslintrc` too, and relaxing a rule in the same change that violates it is invisible in a green run.

Pluvy keeps the policy in a single committed file, `.pluvy/pluvy.json`, with every checker enabled by default for every supported language. Changing that file is an architecture decision: `pluvy --staged` refuses to run while a policy change is staged, and a policy change needs its own full audit and review.

### They do not know your architecture

"The domain layer must not import adapters" and "every file under `src/` has exactly one owner" are facts about your repository, not about Python or Go. Linters ship with rules about the language. Some ecosystems have import-boundary plugins, but each speaks one language with its own configuration, and none of them share a policy across a polyglot repository.

Pluvy reads boundaries, placements and owners from the same policy file and applies them to Python, Go, Java, JavaScript and TypeScript alike.

### Debt blocks adoption, so the gate never gets turned on

Turning a strict rule on in an existing codebase produces hundreds of findings on day one. The usual response is a baseline file, a long ignore list or giving up. Pluvy's change modes report only the definitions and statements a change touches: an edit inside a function brings in the whole function, untouched code stays quiet. New work is held to the policy from the first commit, and the full `--all` reading is there when you are ready to clear the backlog.

## Why a new tool rather than more plugins

It is tempting to add these checks as plugins to a linter you already run. Three requirements rule that out.

**Analysis has to compare snapshots.** Linter plugin APIs give a rule the current file. Test-deletion and assertion-erosion checks need the baseline tree too, resolved from Git, with renames and untracked files handled. That is the core of the engine, not something a per-file rule can add.

**Suppression has to be outside the code's control.** A plugin runs inside a host that honours `noqa` and `eslint-disable` before the plugin ever sees the line. A gate that the inspected code can turn off is not a gate.

**One policy has to span every language.** Agents work across a whole repository. Pluvy parses Python, Go, Java, JavaScript, JSX, TypeScript and TSX with tree-sitter and runs the same checkers, under the same policy, with per-language adapters behind a shared rule set. One configuration, one exit code, one place to review a policy change.

## What Pluvy deliberately does not do

Pluvy is not a replacement for your type checker, formatter, linter or test suite. It works from syntax, not inferred types, and it does not prove that code is correct. It does not fix anything either: a finding is evidence for a human or an agent to act on, and the gate stays independent of the change it is judging.

What it adds is the layer the existing tools were never designed to cover: the difference between work that is done and work that looks done.

## Try it on your last agent change

```sh
uv tool install pluvy
mkdir -p .pluvy
echo '{"version": 2, "include": ["src/*", "tests/*"], "checkers": {}}' > .pluvy/pluvy.json
pluvy --base main
```

The [getting started guide](../../docs/getting-started/) walks through policy setup, the first audit of an existing repository and how to run the gate after every agent task.
