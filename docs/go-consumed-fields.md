# Go implicit field consumption

Go structs are often read through reflection, serialization or structural
comparison rather than explicit `value.Field` expressions. To avoid false
`unused.field` findings while still flagging genuinely unread fields, the Go
semantic adapter contributes recognized implicit reads to shared
`contract_reads`, keeping shared usage analysis independent of concrete language
implementations. `GoConsumedFields` owns recognized consumers and
visibility/tag/custom-marshaler rules; `GoValueOrigins` retains source ownership
while following concrete values, package members, aliases and actual generic
call arguments.

Recognized consumers are imported JSON/XML `Marshal`, `MarshalIndent` and
encoder `Encode`, `reflect.DeepEqual`, Kubernetes
`DefaultUnstructuredConverter.ToUnstructured`, and structural
equality/inequality (`==` / `!=`). Serialization skips private named fields and
exact `-` tags. Custom marshal methods prevent blanket storage-field consumption.
Equality does not traverse pointer targets; `DeepEqual` does. Anonymous struct
embedding permits traversal to exported nested fields.

Behavioral coverage is verified in
[tests/test_go_consumed_fields.py](../tests/test_go_consumed_fields.py) and
[tests/test_go_consumption_regressions.py](../tests/test_go_consumption_regressions.py).
The implementation is a parse-based evidence analysis, not the Go compiler or a
full implementation of `encoding/json` field selection.
`GoSerializationFields` selects fields by wire name and embedding depth, rejects
ambiguous peers, honors JSON tagged dominance, decodes interpreted Go tags and
recognizes uniquely promoted marshal methods.
Exact custom-method signatures, pointer method-set/addressability distinctions,
XML namespace/path/attribute conflict rules and generic stored-parameter
substitution remain unresolved. Package lookup uses
selected snapshot directory suffixes; module replacements and build constraints
are not compiler-resolved. Runtime interface flows and arbitrary returned generic
values are not fully inferred.
