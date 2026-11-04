"""Regression evidence for reviewed Go consumption blockers."""

import pytest
from test_go_consumed_fields import _unused


@pytest.mark.parametrize("expression", ["p == nil", "makeLeaf() == nil"])
def test_pointer_alias_and_return_equality(expression: str) -> None:
    code = f"""package main
 type Leaf struct {{ Unread string }}
 type Ptr = *Leaf
 func makeLeaf() *Leaf {{ return nil }}
 func main() {{ var p Ptr; _ = {expression} }}
 """
    assert _unused(("main.go", code)) == {"Unused field 'Unread'"}


@pytest.mark.parametrize("encoding", ["json", "xml"])
def test_wire_name_collision(encoding: str) -> None:
    code = f"""package main
 import "encoding/{encoding}"
 type Value struct {{ A string `{encoding}:"same"`; B string `{encoding}:"same"`; Read string }}
 func main() {{ {encoding}.Marshal(Value{{}}) }}
 """
    assert _unused(("main.go", code)) == {"Unused field 'A'", "Unused field 'B'"}


@pytest.mark.parametrize("encoding", ["json", "xml"])
@pytest.mark.parametrize("right", ["Same", "Different"])
def test_embedded_name_selection(encoding: str, right: str) -> None:
    code = f"""package main
 import "encoding/{encoding}"
 type Left struct {{ Same string }}
 type Right struct {{ {right} string }}
 type Value struct {{ Left; Right; Read string }}
 func main() {{ {encoding}.Marshal(Value{{}}) }}
 """
    expected = {"Unused field 'Same'"} if right == "Same" else set()
    assert _unused(("main.go", code)) == expected


@pytest.mark.parametrize(
    "encoding,method",
    [
        ("json", "MarshalJSON() ([]byte, error) { return nil, nil }"),
        ("xml", "MarshalXML(e *xml.Encoder, s xml.StartElement) error { return nil }"),
    ],
)
def test_promoted_marshaler(encoding: str, method: str) -> None:
    code = f"""package main
 import "encoding/{encoding}"
 type Base struct {{}}
 func (b Base) {method}
 type Value struct {{ Base; Unread string }}
 func main() {{ {encoding}.Marshal(Value{{}}) }}
 """
    assert _unused(("main.go", code)) == {"Unused field 'Unread'"}


@pytest.mark.parametrize("encoding", ["json", "xml"])
def test_interpreted_struct_tags(encoding: str) -> None:
    code = f'''package main
 import "encoding/{encoding}"
 type Value struct {{ Hidden string "{encoding}:\\"-\\""; Read string "{encoding}:\\"read\\"" }}
 func main() {{ {encoding}.Marshal(Value{{}}) }}
 '''
    assert _unused(("main.go", code)) == {"Unused field 'Hidden'"}


@pytest.mark.parametrize("storage", ["Visible string", "Visible string; Child Leaf"])
def test_factory_phantom_type_argument(storage: str) -> None:
    code = """package main
 import "encoding/json"
 type Leaf struct { Unread string }
 type Box[T any] struct { STORAGE }
 func factory() Box[Leaf] { return Box[Leaf]{} }
 func main() { json.Marshal(factory()) }
 """.replace("STORAGE", storage)
    expected = set() if "Child" in storage else {"Unused field 'Unread'"}
    assert _unused(("main.go", code)) == expected


@pytest.mark.parametrize("expression", ["v == Leaf{}", "makeLeaf() == Leaf{}"])
def test_struct_alias_and_return_equality(expression: str) -> None:
    code = f"""package main
 type Leaf struct {{ Read string }}
 type Alias = Leaf
 func makeLeaf() Leaf {{ return Leaf{{}} }}
 func main() {{ var v Alias; _ = {expression} }}
 """
    assert _unused(("main.go", code)) == set()


@pytest.mark.parametrize("encoding", ["json", "xml"])
def test_named_marshaler_does_not_override_outer_fields(encoding: str) -> None:
    method = (
        "MarshalJSON() ([]byte, error) { return nil, nil }"
        if encoding == "json"
        else ("MarshalXML(e *xml.Encoder, s xml.StartElement) error { return nil }")
    )
    code = f"""package main
 import "encoding/{encoding}"
 type Base struct {{ Hidden string }}
 func (b Base) {method}
 type Value struct {{ Child Base; Read string }}
 func main() {{ {encoding}.Marshal(Value{{}}) }}
 """
    assert _unused(("main.go", code)) == {"Unused field 'Hidden'"}
