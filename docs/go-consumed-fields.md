# Go implicit field consumption

The Go semantic adapter contributes declaration IDs to shared `contract_reads`.
Shared usage analysis remains independent of concrete language implementations.
`GoConsumedFields` owns recognized consumers and visibility/tag/custom-marshaler
rules; `GoValueOrigins` retains source ownership while following concrete values,
package members, aliases and actual generic call arguments. Policy is unchanged.

Recognized consumers are imported JSON/XML Marshal, MarshalIndent and encoder
Encode, reflect.DeepEqual, Kubernetes DefaultUnstructuredConverter.ToUnstructured,
and structural equality/inequality. Serialization skips private named fields and
exact `-` tags. Custom marshal methods prevent blanket storage-field consumption.
Equality does not traverse pointer targets; DeepEqual does. Anonymous struct
embedding permits traversal to exported nested fields.

Behavioral evidence is in tests/test_go_consumed_fields.py: visible versus skipped
and unrelated fields; nested map/slice/pointer values; custom JSON/XML marshaling;
actual generic calls across files and packages, including explicit type arguments;
uncalled generic constraints; pointer identity versus struct equality; DeepEqual;
anonymous embedding; encoder/import/type aliases; Kubernetes conversion; unrelated
Marshal methods. The implementation is a parse-based evidence analysis, not the Go
compiler or a full implementation of encoding/json field selection.
`GoSerializationFields` selects fields by wire name and embedding depth, rejects
ambiguous peers, honors JSON tagged dominance, decodes interpreted Go tags and
recognizes uniquely promoted marshal methods. Additional positive/negative
regressions in tests/test_go_consumption_regressions.py cover pointer alias and
pointer-return comparisons, struct value comparisons, JSON/XML duplicate wire
names and embedded names, promoted versus named-child marshalers, interpreted
skip tags, and phantom versus concretely stored factory type arguments.
Exact custom-method signatures, pointer method-set/addressability distinctions,
XML namespace/path/attribute conflict rules and generic stored-parameter
substitution remain unresolved. Package lookup uses
selected snapshot directory suffixes; module replacements and build constraints
are not compiler-resolved. Runtime interface flows and arbitrary returned generic
values are not fully inferred.

Final repair validation (all commands prefixed by `rtk proxy mise exec --`):

- `uv run --directory /tmp/sast-pluvy-migration --no-sync pytest -q`: 2117 passed.
- Same runner with `mypy src tests`: success, 175 source files.
- Same runner with `ruff check src tests`: passed.
- Same runner with `ruff format --check src tests`: 176 files formatted.
- Same runner with `pluvy --all`: exit 0, 176 files, 0 errors / 56 existing
  unused.return warnings in review infrastructure and tests; not zero findings.
- Same runner with `pluvy --base 0d69ef3`: exit 0, 9 files, 0 errors / 0 warnings.
  Includes inherited uncommitted migration edits; no changes were filtered out.
- Same runner with `pluvy --root /home/guo/Projects/sast-workflow --all`:
  exit 0, 318 files, 0 errors / 0 warnings.

No policy, business-project code or suppression is changed, and no commit is created.

Branch coverage could not be measured: coverage is not installed, and requesting
it through uv --with coverage failed fetching PyPI with TLS handshake EOF.
This is a delivery limitation; passing behavioral tests is not a coverage claim.
