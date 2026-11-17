# Approved next-line diagnostic exceptions

Every supported language accepts a standalone line comment on the physical line
immediately before a finding, using that language's line-comment marker (`#` for
Python; `//` for Go, Java, JavaScript, JSX, TypeScript, and TSX):

```ts
// pluvy: ignore-next-line type.broad -- Serialized test input.
const input = JSON.stringify(payload);

// pluvy: ignore-next-line type.broad -- Expected wire response.
assert.equal(result.content, JSON.stringify(expected));
```

```python
# pluvy: ignore-next-line type.annotation -- Legacy adapter boundary.
value: object = read_payload()
```

```go
// pluvy: ignore-next-line type.broad -- Generated wire payload.
type Payload any
```

```java
// pluvy: ignore-next-line type.broad -- Framework callback signature.
void handle(Object value) { consume(value); }
```

## Approval requirements

Use a next-line directive only after obtaining explicit human approval for that
exception. The non-blank reason after `--` records that approval; it does not
prove safety on its own. Revisit the exception whenever the surrounding code or
its callers change.

Foreign linter and type-checker suppression markers remain prohibited across all
supported languages and report `type.suppression`:

- **All languages**: `noqa`, `type: ignore`, `pyright: ignore`, `mypy: ignore`,
  `@ts-ignore` / `@ts-expect-error` / `@ts-nocheck`, `eslint-disable` variants,
  `nolint`, and `lint:ignore`.
- **Java additionally**: `NOSONAR`, `CHECKSTYLE:OFF`, `noinspection`,
  `@SuppressWarnings`, and `@SuppressFBWarnings` (keep those markers out of the
  reason text in Java files as well, since Java's comment check matches them
  independently).

## Selector and placement rules

- **Exact diagnostic ID**: Name one registered diagnostic ID for the file's
  analyzer—for example `size.lines` rather than the `function_size` checker key.
  Unknown IDs, wildcards, comma-separated lists, `type.suppression`, and the
  run-level `test.deletion` diagnostic are rejected as `type.suppression`.
- **Standalone physical line**: Place the directive on its own line immediately
  above the line where the finding starts. Trailing end-of-line comments, block
  comments (`/* ... */`), file-wide directives, missing reasons, and blank or
  comment lines between the directive and its target report `type.suppression`.
- **Exact target coverage**: Every finding on that immediately following line
  matching the named diagnostic ID is omitted; all other rules and lines remain
  active. For example, suppressing `type.broad` on a mixed line covers both
  broad annotations (`any`, `unknown`) and serialization calls on that line—split
  mixed statements first if approval applies to only one part.
- **No unused directives**: A syntactically valid directive whose target line
  emits no matching finding (including when its checker is disabled) reports
  `type.suppression`.

## Snapshot and changed-scope behavior

Pluvy reads suppression comments from the exact immutable source snapshot under
audit: `--staged` reads Git index blobs rather than unstaged working-tree edits.
In `--base` and `--staged` runs, unused-directive checks run only when the
target line falls within the audited change scope, so partial audits do not
flag unrelated files.

Maintainer and implementation details for the suppression parser live in the
skill reference at
[comment-suppressions.md](../.agents/skills/pluvy/references/comment-suppressions.md).
