"""Go field consumption retains negative evidence beside actual serialization."""

import pytest

from pluvy.engine import registry
from pluvy.policy.models import Policy
from pluvy.source import Language, Source


def _unused(*files: tuple[str, str]) -> set[str]:
    sources = tuple(Source(path, code.encode(), Language.GO) for path, code in files)
    return {
        "Unused field '" + finding.message.split("'")[1] + "'"
        for finding in registry().analyze_sources(sources, Policy())
        if finding.rule == "unused.field"
    }


@pytest.mark.parametrize("encoding", ["json", "xml"])
@pytest.mark.parametrize(
    "operation", ["Marshal(v)", 'MarshalIndent(v, "", "  ")', "NewEncoder(os.Stdout).Encode(v)"]
)
def test_only_serialized_visible_fields_are_consumed(encoding: str, operation: str) -> None:
    code = f"""package main
import ("encoding/{encoding}"; "os")
type Leaf struct {{ Nested string }}
type Value struct {{
 Visible string; Child map[string][]*Leaf
 Hidden string `{encoding}:"-"`; private string
}}
type Untouched struct {{ Unused string }}
func main() {{ v := Value{{}}; {encoding}.{operation} }}
"""
    assert _unused(("main.go", code)) == {
        "Unused field 'Hidden'",
        "Unused field 'private'",
        "Unused field 'Unused'",
    }


@pytest.mark.parametrize(
    "encoding,method",
    [
        ("json", "MarshalJSON() ([]byte, error) { return nil, nil }"),
        ("xml", "MarshalXML(e *xml.Encoder, start xml.StartElement) error { return nil }"),
    ],
)
def test_custom_marshaler_does_not_consume_its_storage(encoding: str, method: str) -> None:
    code = f"""package main
import "encoding/{encoding}"
type Value struct {{ Hidden string }}
func (v Value) {method}
func main() {{ {encoding}.Marshal(Value{{}}) }}
"""
    assert _unused(("main.go", code)) == {"Unused field 'Hidden'"}


def test_generic_forwarding_uses_actual_call_bindings_across_files() -> None:
    files = (
        (
            "types.go",
            "package main\ntype Used struct { Read string }; type Other struct { Unread string }",
        ),
        (
            "encode.go",
            """package main
import "encoding/json"
func encode[T Used | Other](v T) { json.Marshal(v) }
""",
        ),
        ("main.go", "package main\nfunc main() { encode(Used{}) }"),
    )
    assert _unused(*files) == {"Unused field 'Unread'"}


@pytest.mark.parametrize("operator", ["==", "!="])
def test_equality_reads_values_but_not_pointer_targets(operator: str) -> None:
    code = f"""package main
type Value struct {{ Read string }}
type Pointer struct {{ Unread string }}
func main() {{ a := Value{{}}; b := Pointer{{}}; _ = a {operator} Value{{}}; _ = &b {operator} &b }}
"""
    assert _unused(("main.go", code)) == {"Unused field 'Unread'"}


def test_deep_equal_reads_private_nested_fields() -> None:
    code = """package main
import "reflect"
type Child struct { private string }
type Value struct { Child *Child `json:"-"` }
func main() { reflect.DeepEqual(&Value{}, &Value{}) }
"""
    assert _unused(("main.go", code)) == set()


def test_cross_package_generic_call() -> None:
    files = (
        (
            "helper/encode.go",
            """package helper
import "encoding/json"
func Encode[T any](v T) { json.Marshal(v) }
""",
        ),
        (
            "main.go",
            """package main
import "example/helper"
type Value struct { Read string }; type Other struct { Unread string }
func main() { helper.Encode[Value](Value{}) }
""",
        ),
    )
    assert _unused(*files) == {"Unused field 'Unread'"}


@pytest.mark.parametrize("encoding", ["json", "xml"])
def test_embedded_structs(encoding: str) -> None:
    code = f"""package main
import "encoding/{encoding}"
type embedded struct {{ Read string }}
type Ignored struct {{ Unread string }}
type Value struct {{ *embedded; Ignored `{encoding}:"-"` }}
func main() {{ {encoding}.Marshal(Value{{}}) }}
"""
    assert _unused(("main.go", code)) == {"Unused field 'Unread'"}


def test_unstructured_converter_and_shadowed_serializer() -> None:
    code = """package main
import "k8s.io/apimachinery/pkg/runtime"
type Value struct { Read string; Hidden string `json:"-"` }
func main() { runtime.DefaultUnstructuredConverter.ToUnstructured(&Value{}) }
"""
    assert _unused(("main.go", code)) == {"Unused field 'Hidden'"}


def test_pointer_variables_and_nested_pointer_fields_do_not_read_targets() -> None:
    code = """package main
type Leaf struct { Unread string }
type Value struct { Read *Leaf }
func main() { p := &Leaf{}; _ = p == nil; _ = Value{} == Value{} }
"""
    assert _unused(("main.go", code)) == {"Unused field 'Unread'"}


def test_encoder_alias_and_type_alias() -> None:
    code = """package main
import (wire "encoding/json"; "os")
type Value struct { Read string; Hidden string `json:"-"` }
type Alias = Value
func main() { encoder := wire.NewEncoder(os.Stdout); encoder.Encode(Alias{}) }
"""
    assert _unused(("main.go", code)) == {"Unused field 'Hidden'"}


def test_uncalled_generic_does_not_consume_constraint_fields() -> None:
    code = """package main
import "encoding/json"
type Value struct { Unread string }
func encode[T Value](v T) { json.Marshal(v) }
func main() {}
"""
    assert _unused(("main.go", code)) == {"Unused field 'Unread'"}


def test_type_name_is_not_shadowed_by_receiver_method() -> None:
    code = """package main
import "encoding/xml"
type settings struct { Read string }
type Runner struct {}
func (r Runner) settings() { value := settings{}; xml.Marshal(value) }
func main() { Runner{}.settings() }
"""
    assert _unused(("main.go", code)) == set()


def test_unrelated_marshal_method_is_not_a_consumer() -> None:
    code = """package main
type Value struct { Unread string }
type Encoder struct {}
func (e Encoder) Marshal(v Value) {}
func main() { json := Encoder{}; json.Marshal(Value{}) }
"""
    assert _unused(("main.go", code)) == {"Unused field 'Unread'"}
