# Boundaries, usage and serialization

This page covers `third_party_modules` boundary rules, cross-file usage and
discarded-return resolution, and `type.broad` JSON serialization and output
boundaries. For general policy structure and per-checker switches, see
[Checker configuration](checker-configuration.md).

## Third-party boundaries and usage

Declare third-party import specifiers explicitly at policy level:

```json
{
  "third_party_modules": ["vendor.client", "@vendor/sdk", "example.com/vendor/sdk"],
  "checkers": {}
}
```

The default is an empty list. Entries match the actual import module exactly;
import aliases retain that identity. Do not list application modules to bypass
typing. This setting grants a directional boundary exception, not a file or
checker exemption. Internal dictionaries and other broad carriers remain checked.
Disabling `type.boundary` disables its diagnostics but does not alter third-party
classification used by the other type and field checks.

A dictionary, or a directly forwarded dictionary parameter, can erase value
types when every read supplies an argument to a configured library. Python
`**kwargs`, Go maps and TypeScript `Record` annotations are recognized. Type
assertions and suppression directives remain errors. JavaScript receives the
same usage and boundary analysis; it still needs a separate type-aware checker.

For a callback registered as a library argument, its return dictionary is library
input. Its incoming dictionary parameters must be converted at callback ingress.
The check recognizes declared constructors, concrete-return conversion functions
and Python scalar conversions, including extraction of dictionary entries.
A callback also called by application code does not gain a broad return contract.
Library results cannot be returned or passed through application code raw. Values
already constructed with a concrete generic library contract, and explicit `new`
expressions, retain that contract. Type-only schema metadata and fields materialized
by a configured external metaclass are not raw application result carriers.
Mechanical recognition of a conversion does not prove its validator is honest.

In Python, decorator factories supply declaration behavior rather than application
payloads, while ordinary third-party payload results still require ingress
conversion. This does not add a general payload exemption for decorators'
arguments.

Objects passed to configured libraries, including callback return objects, have
all their declared fields treated as consumed. Configured external base classes
also consume their class objects through metaclass construction. This repository
lists `pydantic` for its externally materialized model fields. Field reads resolve
through concrete receivers, annotations, constructors, imports and known bases;
a write, initialization or deletion alone is not a read.

Usage analysis runs automatically for Python, Go, Java, JavaScript/JSX and TypeScript/TSX.
It resolves lexical scopes, closures, literal imports and Go files in the same
package. Public Python module APIs, exported Go/JS/TS functions, non-private,
annotated or overloaded Java methods, recognized runtime entry points and
declaration-only signatures retain their external-use contracts.
Methods linked by resolved inheritance share parameter-use evidence. A read in
any implementation makes the corresponding parameter used throughout its
override family, including base and sibling implementations. Positional arguments
match by position, keyword-only arguments by name, and variadic slots separately.
Extra arguments and parameters unread throughout the family remain findings;
unrelated same-named methods and constructors do not gain this exemption. This
also applies to imported bases and JS/TS `extends` clauses. Structural interface
relationships without resolved inheritance still require review. Python
`self`/`cls`, JS `this`, and blank `_` bindings are not unused-parameter candidates.
TypeScript constructor parameters marked `public`, `protected`, `private` or
`readonly` can declare instance properties, and `unused.parameter` accepts
resolved reads of those properties as usage of the exact constructor parameter
declaration. Initialization and writes alone remain insufficient, and ordinary
parameters or unrelated declarations with the same name remain reportable.

`--all` links all selected snapshots. Changed audits read unchanged reference
files from the same view: working files for `--base`, index blobs for `--staged`.
Only the originally selected files receive findings; JSON `files` retains that
scope and `usage_files` discloses the reference scope. These reads do not modify
source or the index. In-process callers can use `AnalyzerRegistry.analyze_sources`
with the built-in registry to obtain the same cross-file resolution; `engine.check`
checks one snapshot. Custom registries can register a `SemanticParser` explicitly.

Every finding includes `severity`, defaulting to `error`. `unused.return` is
always a `warning`, `test.vacuous` is a `warning` when a test's only assertions
are snapshot matchers, and `test.deletion` reports a changed snapshot path as a
`warning`; text labels them and JSON retains them in `findings`. A known
non-void local or resolved imported function result discarded as a standalone
call, Python/Go `_` assignment, or JS `void` expression produces a warning.
Unknown external return types are not guessed. Warnings alone leave exit status 0.

Result classification uses the call expression as well as the declaration.
TypeScript/TSX direct generic results such as `run<R>(work: () => R): R`
substitute explicit type arguments or infer the result from resolved callbacks.
Python supports the corresponding imported `Callable[..., R]` contract with a
PEP 695 parameter or an imported `typing.TypeVar` declaration. JavaScript supports
direct forwarding of an unchanged callback parameter. A callback's declared
contract takes precedence over its body; an unannotated callback with no value
returns supplies no-result evidence. Expression bodies can call resolved local
or imported functions. Each invocation is classified independently.

Promises, coroutines, generators and containers remain value results, even when
their payload is `void` or `None`. Java `Void` and Go empty structs also remain
values; these languages cannot substitute a no-result type for a generic value
parameter. Their existing declaration and overload fallback remains unchanged.

Inference distinguishes no-result, value-result and unresolved evidence.
Unresolved cases retain the declaration-based warning behavior. It does not
implement compiler overload selection, arbitrary type aliases, class-level
generic substitution, generic callback contextual typing or general dataflow.
Overloaded TypeScript callbacks, reassigned callbacks, destructured/rest
parameters, unsupported wrappers and unresolved external callbacks do not prove
`void`. Python keyword argument binding and generic relationships outside direct
callback results retain the fallback. Nested generic calls inside a resolved
callback expression are supported; forwarding through generic parameter
environments is not. There is no compiler runtime dependency.

Cross-file inference reads declarations and callbacks from the same selected
snapshot view as usage resolution. No result is cached on a declaration or across
analysis sessions; staged checks use index content even when worktree signatures
or callback bodies differ. Exact-line suppression is applied after inference,
so a suppression targeting a now-proven void call becomes stale.

These are bounded semantic checks, not compiler or whole-program proofs. Dynamic
imports, arbitrary aliases, reflection, dynamic attributes, complex generic flow,
framework registration and external consumers may require review. An unresolved
member read or protocol dispatch defers same-named member candidates instead of
asserting they are unused. Exported APIs are not automatically declared dead.
Import resolution uses the available policy-selected snapshots; package/build
alias resolution is not a replacement for language tooling. Review remaining
candidates before changing code. The gate never removes or rewrites unused code.

Java evidence is syntax-backed rather than javac type checking. Overload selection,
generic substitution, reflection, annotation processing, generated accessors,
wildcard/static-member project linking, fully qualified expression resolution and
external classpaths are not resolved at compiler level. Nested or anonymous class
ownership, generated members and unresolved external references retain the shared
engine's inference limits.

## Serialization and output boundaries

`type.broad` reports serializer calls that erase concrete internal application
objects into JSON text or bytes unless every observed use reaches a proven
output destination or a permitted outbound library call. Alias resolution and
output forwarding share the same semantic engine across all five supported
languages. Disabling `type.boundary` does not disable serialization checks or
alter their boundary evidence; disabling `type.broad` disables its serialization
findings.

The `third_party_modules` policy above
applies directionally: serialized data may be passed directly to a configured
library (including keyword arguments, inline containers and returns from
callbacks used exclusively by that library), or held in a single-assignment
local whose resolved reads all reach permitted library inputs or proven outputs.
Internal consumers, retained fields, ordinary helper returns, intermediate
transformations, dictionary keys, reassigned carriers and encoder-to-decoder
round trips remain findings—even when the serializer module itself is listed in
`third_party_modules`.

When a receiving library's module is listed in `third_party_modules`, passing a
member-level encoder result directly to one of that library's class methods—such
as `VendorModel.model_validate_json(item.model_dump_json())`—receives the same
directional library-input exemption as `json.dumps`. Declaring that target
method in `decoders` for its resolved identity rejects the round trip.

## Built-in serializers and outputs by language

### Python

- **Recognized encoders and decoders**: `json.dumps` and `json.loads` via module
  imports, renamed imports, `from json import dumps`, and stable
  single-assignment callable or module aliases (`encode = json.dumps`,
  `codec = json`). Python also treats explicit member calls named `dump_json` or
  `model_dump_json` (such as Pydantic `TypeAdapter.dump_json` and
  `BaseModel.model_dump_json`) as encoders without requiring a `pydantic` import
  or resolved receiver type. Name-level identities follow stable aliases and
  parentheses, whereas member-level recognition (built-in Pydantic entry points
  and configured `*.member` entries) matches only the explicit member name at
  the call site—`dump = ADAPTER.dump_json; dump(item)` and
  `(item.model_dump_json)()` are not recognized. Strings containing source
  examples and unrelated methods named `dumps` are ignored.
- **Recognized outputs**: unshadowed `print` / `builtins.print`, imported
  `sys.stdout.write` and `sys.stderr.write`, `write_text` on a recognized
  `pathlib.Path` construction or stable local alias, and `write` or
  `print(..., file=...)` targeting an enclosing writable text `open` /
  `builtins.open` / `io.open` context or standard stream. `StringIO`, shadowed
  names and arbitrary `write` or `send` methods do not establish egress.

```python
import json
import vendor

vendor.send(body=json.dumps({"count": 1}))  # permitted when vendor is in third_party_modules
print(json.dumps({"count": 1}))             # permitted terminal output
```

### JavaScript, TypeScript and TSX

- **Recognized encoders and decoders**: native `JSON.stringify` and `JSON.parse`,
  including stable callable and module aliases (`const encode = JSON.stringify`,
  `const codec = JSON`).
- **Recognized outputs**: unshadowed `console.log`/`info`/`warn`/`error`/`debug`,
  standard `process.stdout.write` and `process.stderr.write`, and imported
  `fs` / `node:fs` (including `fs/promises` and `node:fs/promises`) file write
  and append payload arguments (serialized filenames do not count). Computed
  members, destructured aliases and shadowed globals do not establish egress.

```javascript
const encode = JSON.stringify;
console.log(encode({ count: 1 }));
const body = encode({ count: 1 });
consume(body); // reported by type.broad
```

### Go

- **Recognized encoders and decoders**: imported `encoding/json.Marshal` and
  `encoding/json.MarshalIndent` (encoders) and `encoding/json.Unmarshal`
  (decoder), preserving import and stable callable aliases. In
  `data, err := json.Marshal(value)`, only `data` is tracked as the serialized
  carrier; checking `err` stays independent. Predeclared or reassigned carriers,
  aggregate tuple forwarding, byte/string conversions and streaming encoders
  remain outside this proof.
- **Recognized outputs**: imported `fmt.Print` / `fmt.Println`,
  `os.Stdout.Write` / `os.Stderr.Write` (argument `0`), and `os.WriteFile`
  (payload argument `1`). Arbitrary `io.Writer` methods and memory buffers do
  not establish egress by name alone.

### Java

- **Recognized encoders and decoders**: one-argument `Gson.toJson` and Jackson
  `ObjectMapper.writeValueAsString` / `writeValueAsBytes` on imported,
  explicitly typed locals, parameters, fields or direct constructors;
  `Gson.fromJson` and `ObjectMapper.readValue` / `readTree` reject round-trip
  reconstruction. Multi-argument streaming overloads, `var` inference and
  unqualified `toJson` methods without receiver proof are not classified
  automatically. A configured `*.toJson` encoder entry enables receiver-agnostic
  recognition for explicit-receiver calls (including streaming overloads such as
  `gson.toJson(item, writer)` that the built-in adapter excludes), while
  implicit-receiver calls remain unproved.
- **Recognized outputs**: unshadowed `System.out` and `System.err` `print` /
  `println` (argument `0`).

Across all languages, conditional result branches (`cond ? encode(x) : text`)
retain all-consumer flow, while using an encoded value as a condition or passing
it across functions without configured contracts remains a finding.

## Configuring encoding APIs

Extend `type.broad` in `.pluvy/pluvy.json` to recognize project-specific or
third-party serializers and approved output APIs. These lists add to built-in
recognition; empty or omitted lists keep all built-in checks active.

```json
{
  "checkers": {
    "type.broad": {
      "encoding": {
        "encoders": ["orjson.dumps", "@vendor/codec.encode", "*.to_wire"],
        "decoders": ["orjson.loads", "@vendor/codec.decode"],
        "outputs": [
          {"call": "transport.publish", "arguments": [1], "keywords": ["body"]}
        ]
      }
    }
  }
}
```

The [example policy](../examples/.pluvy/pluvy.json) contains a compact version
of this configuration. Choose API names from the target project:

- `encoders`: exact qualified functions returning serialized data, or the
  restricted receiver-agnostic member form `*.member` (a `*.` prefix followed by
  one ASCII identifier; a bare method name remains an exact qualified identity).
  Their results must still flow exclusively to permitted outputs; registration
  is not an exemption.
- `decoders`: exact qualified reconstruction functions. Passing an encoding into
  these (directly, via aliases or through forwarded locals) reports `type.broad`.
- `outputs`: exact `call` identities with payload selectors. `arguments` lists
  zero-based positional indexes; `keywords` lists Python keyword names. At least
  one selector is required; an empty list never matches all arguments.

With the configuration above, `publish("topic", encoded)` and
`publish(body=encoded)` pass, whereas `publish(encoded, "payload")` reports
`encoded`. Positional offsets after `*args` or `...args` cannot prove a
configured slot, though explicit Python keyword arguments after `*args` still
can; `**kwargs` is not expanded into named slots.

Exact API names match resolved import identities rather than local aliases:
Python `from orjson import dumps as pack` matches `orjson.dumps`, and
`import { encode as pack } from "@vendor/codec"` matches `@vendor/codec.encode`.
A `*.member` entry matches explicit-receiver member calls by member name (bare
calls, Java implicit-receiver calls, aliases and parenthesized callees do not
match). Names are exact and case-sensitive; blank strings, whitespace, general
wildcards (such as `orjson.*`), non-integer indexes and unknown fields fail
configuration validation even when `type.broad` is disabled.

This configuration applies uniformly across Python, Go, Java, JavaScript, JSX,
TypeScript and TSX. Exact qualified API names do not resolve arbitrary instance
methods, computed members or dynamic imports without import evidence. Decoder
rejection always takes precedence over both `outputs` declarations and
`third_party_modules` input exemptions, and encoding settings never exempt
broad annotations (`Any`, `any`), casts or unconverted library return values.

### Source-owned instance output callbacks

Approve a specific class-owned method or callback property (or a named struct
receiver in Go) without exempting every same-named method in the codebase:

```json
{
  "checkers": {
    "type.broad": {
      "encoding": {
        "instance_outputs": [
          {
            "path": "src/analysis/command.ts",
            "class_name": "Cli",
            "member": "out",
            "arguments": [0]
          }
        ]
      }
    }
  }
}
```

This permits `this.out(JSON.stringify(entry))` inside `Cli` in that exact file.
`instance_outputs` is an explicit policy trust boundary: the analyzer does not
trace dependency injection sites to verify every runtime implementation of
`out`, so review the injection contract before adding an entry and revisit it
when implementations change.

Selector rules shared by all languages:

- `path`: exact, case-sensitive, normalized repository-relative POSIX path (no
  leading `/`, backslashes, wildcards, `.` or `..`).
- `class_name` and `member`: exact ASCII identifiers (including `$` and `_`),
  each resolving to a single unambiguous declaration in the snapshot; unmatched
  or duplicate declarations remain inert so shared policies work during
  partial audits. Parser-recovered snapshots fail closed.
- `arguments`: non-empty list of zero-based non-negative integer payload
  positions.

Per-language receiver rules:

- **JavaScript, TypeScript and TSX**: recognizes direct `this.member(...)` calls
  inside instance methods, field initializers and nested arrow functions.
  Ordinary nested functions, explicit `this` parameters, object literals, static
  members, getters/setters, decorated or computed members, inherited-only
  members, receiver aliases and extracted callbacks are not approved.
- **Python**: recognizes `self.out(...)` (using the method's actual first
  positional parameter name, including closures capturing it) on fields declared
  on the class or initialized in `__init__`. Decorated methods (`@staticmethod`,
  `@classmethod`, `@property`), variadic or reassigned receivers, inherited-only
  members and keyword argument calls (`self.out(line=encoded)`) are not
  approved.
- **Go**: `class_name` names the struct receiver type and `member` names its
  direct method or function-valued field in that same file (for example,
  `c.out(data)` inside `func (c *Cli) run(...)`), supporting value/pointer
  receivers and closures capturing the unchanged receiver. Embedded fields and
  reassigned receivers remain checked.
- **Java**: recognizes direct `this.out(encoded)` on a single non-overloaded
  instance method, or `this.out.accept(encoded)` when `out` is a field typed as
  explicitly imported `java.util.function.Consumer` (where `arguments` indexes
  into `accept`). Lambdas preserve the enclosing `this`; static contexts,
  anonymous classes, overloads and implicit `out(...)` calls without `this.` are
  not approved.
