"""Project-declared serializers and precise output arguments share boundary analysis."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pluvy.cli import main
from pluvy.diagnostics import Finding, Report
from pluvy.engine import check
from pluvy.policy.models import Policy
from pluvy.source import Language, Source

_POLICY = Policy.model_validate_json("""{
  "checkers": {"type.broad": {"encoding": {
    "encoders": ["codec.encode"],
    "decoders": ["codec.decode"],
    "outputs": [{"call": "transport.publish", "arguments": [1], "keywords": ["body"]}]
  }}}
}""")


def _findings(code: str, language: Language, policy: Policy = _POLICY) -> tuple[Finding, ...]:
    return tuple(
        f
        for f in check(Source("sample", code.encode(), language), policy)
        if f.rule == "type.broad"
    )


def _encoder_policy(entries: tuple[str, ...]) -> Policy:
    encoded = ", ".join(f'"{entry}"' for entry in entries)
    return Policy.model_validate_json(
        '{"checkers":{"type.broad":{"encoding":{"encoders":[' + encoded + "]}}}}"
    )


@pytest.mark.parametrize(
    "entries",
    [
        ("*.dump_json", "*.$emit"),
        ("codec.encode", "*.dump_json"),
    ],
)
def test_restricted_member_encoder_entries_are_accepted(entries: tuple[str, ...]) -> None:
    assert _encoder_policy(entries).checkers.type_broad.encoding.encoders == entries


def test_configured_output_permits_pydantic_member_encoding() -> None:
    policy = Policy.model_validate_json("""{
      "checkers": {"type.broad": {"encoding": {
        "outputs": [{"call": "transport.publish", "arguments": [1]}]
      }}}
    }""")
    code = "import transport\ntransport.publish('out', ADAPTER.dump_json(item))"
    assert _findings(code, Language.PYTHON, policy) == ()
    assert len(_findings(code, Language.PYTHON, Policy())) == 1


def test_typescript_configured_member_encoder_uses_shared_flow() -> None:
    policy = _encoder_policy(("*.serialize",))
    findings = _findings("const body = item.serialize();", Language.TYPESCRIPT, policy)
    assert len(findings) == 1
    assert "serialize" in findings[0].message
    assert _findings("console.log(item.serialize());", Language.TYPESCRIPT, policy) == ()


def test_java_configured_member_encoder_requires_an_explicit_receiver() -> None:
    policy = _encoder_policy(("*.toJson",))
    explicit = (
        "class Codec { void toJson(String value) {} "
        "void run(String item) { this.codec.toJson(item); } }"
    )
    implicit = (
        "class Codec { void toJson(String value) {} void run(String item) { toJson(item); } }"
    )
    findings = _findings(explicit, Language.JAVA, policy)
    assert len(findings) == 1
    assert "toJson" in findings[0].message
    assert _findings(implicit, Language.JAVA, policy) == ()


def test_go_configured_member_encoder_uses_single_result_flow() -> None:
    policy = _encoder_policy(("*.Encode",))
    declaration = 'type Codec struct{}\nfunc (c Codec) Encode(v int) string { return "" }\n'
    internal = (
        "package sample\n"
        + declaration
        + "func run(c Codec) { value := c.Encode(1); consume(value) }"
    )
    permitted = (
        'package sample\nimport "fmt"\n'
        + declaration
        + "func run(c Codec) { fmt.Println(c.Encode(1)) }"
    )
    findings = _findings(internal, Language.GO, policy)
    assert len(findings) == 1
    assert "Encode" in findings[0].message
    assert _findings(permitted, Language.GO, policy) == ()


def test_go_member_encoder_with_bytes_and_error_keeps_the_internal_finding() -> None:
    policy = _encoder_policy(("*.Encode",))
    code = (
        "package sample\ntype Codec struct{}\n"
        "func (c Codec) Encode(v int) ([]byte, error) { return nil, nil }\n"
        "func run(c Codec) { value, _ := c.Encode(1); consume(value) }"
    )
    findings = _findings(code, Language.GO, policy)
    assert len(findings) == 1
    assert "Encode" in findings[0].message


def test_bare_encoder_entry_does_not_match_a_member_call() -> None:
    code = "import codec\nvalue = codec.serialize(item)"
    assert _findings(code, Language.PYTHON, _encoder_policy(("serialize",))) == ()
    assert len(_findings(code, Language.PYTHON, _encoder_policy(("codec.serialize",)))) == 1


@pytest.mark.parametrize(
    "code",
    [
        "import codec\nvalue = codec.encode({'count': 1})",
        "from codec import encode as pack\nvalue = pack({'count': 1})",
        "import codec\npack = codec.encode\ncopy = pack\nvalue = copy({})",
        "import codec\nimport transport\ntransport.publish(codec.encode({}), 'payload')",
        "import codec\nimport transport\ntransport.publish('out', label=codec.encode({}))",
        "import codec\nvalue = codec.decode(codec.encode({}))",
        "import codec\npack = codec.encode\nunpack = codec.decode\nvalue = unpack(pack({}))",
        "import codec\nimport transport\nvalue = codec.encode({})\n"
        "transport.publish('out', value)\nconsume(value)",
        "import codec\nimport transport\ntransport.publish(*items, codec.encode({}))",
        "import codec\nimport transport\ntransport.publish(**{'body': codec.encode({})})",
        "import codec\nimport transport\ntransport.publish('out', {codec.encode({}): 1})",
    ],
)
def test_configured_python_encoding_is_still_erasure(code: str) -> None:
    assert len(_findings(code, Language.PYTHON)) == 1


@pytest.mark.parametrize(
    "code",
    [
        "import codec\nprint(codec.encode({}))",
        "import codec\nimport transport\ntransport.publish('out', codec.encode({}))",
        "import codec\nfrom transport import publish as emit\nemit('out', codec.encode({}))",
        "import codec\nimport transport\ntransport.publish(body=codec.encode({}))",
        "import codec\nimport transport\ntransport.publish('out', body=(codec.encode({})))",
        "import codec\nimport transport\nvalue = codec.encode({})\ncopy = value\n"
        "transport.publish('out', copy)",
        "import codec\nimport transport\ntransport.publish('out', {'body': codec.encode({})})",
        "import codec\nimport transport\ntransport.publish(*items, body=codec.encode({}))",
        "import codec\ndef run(codec: Codec) -> str:\n    return codec.encode({})",
        "import custom as codec\nvalue = codec.encode({})",
    ],
)
def test_python_output_payloads_aliases_and_shadowing(code: str) -> None:
    assert _findings(code, Language.PYTHON) == ()


@pytest.mark.parametrize("language", [Language.JAVASCRIPT, Language.TYPESCRIPT, Language.TSX])
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("const body = codec.encode({});", 1),
        ("const pack = codec.encode; const copy = pack; const body = copy({});", 1),
        ("const unpack = codec.decode; const body = unpack(codec.encode({}));", 1),
        ("transport.publish(codec.encode({}), 'payload');", 1),
        ("transport.publish('out', codec.encode({}));", 0),
        ("const emit = transport.publish; emit('out', codec.encode({}));", 0),
        ("const body = codec.encode({}); const copy = body; transport.publish('out', copy);", 0),
        ("transport.publish('out', {body: codec.encode({})});", 0),
        ("transport.publish(...items, codec.encode({}));", 1),
        ("const body = codec.encode({}); transport.publish('out', body); consume(body);", 1),
        ("function run(transport) { transport.publish('out', codec.encode({})); }", 1),
    ],
)
def test_javascript_configuration_uses_the_same_contract(
    language: Language,
    body: str,
    expected: int,
) -> None:
    code = "import * as codec from 'codec'; import * as transport from 'transport'; " + body
    assert len(_findings(code, language)) == expected


@pytest.mark.parametrize(
    ("language", "code"),
    [
        (Language.PYTHON, "import codec\nimport transport\ntransport.publish(codec.encode({}))"),
        (
            Language.TYPESCRIPT,
            "import * as codec from 'codec'; import * as transport from 'transport'; "
            "transport.publish(codec.encode({}));",
        ),
    ],
)
def test_third_party_input_policy_is_retained(language: Language, code: str) -> None:
    policy = Policy(third_party_modules=("transport",), checkers=_POLICY.checkers)
    assert len(_findings(code, language)) == 1
    assert _findings(code, language, policy) == ()


def test_configured_decoders_override_output_and_library_exemptions() -> None:
    policy = Policy.model_validate_json("""{
      "third_party_modules": ["codec"],
      "checkers": {"type.broad": {"encoding": {
        "encoders": ["codec.encode"], "decoders": ["codec.decode"],
        "outputs": [{"call": "codec.decode", "arguments": [0]}]
      }}}
    }""")
    assert (
        len(_findings("import codec\ncodec.decode(codec.encode({}))", Language.PYTHON, policy)) == 1
    )


def test_builtin_encoder_and_decoder_rules_remain_enabled() -> None:
    python = "import json\nimport codec\nvalue = codec.decode(json.dumps({}))"
    typescript = "import * as codec from 'codec'; const value = JSON.parse(codec.encode({}));"
    assert len(_findings(python, Language.PYTHON)) == 1
    assert len(_findings(typescript, Language.TYPESCRIPT)) == 1
    assert len(_findings("import json\nvalue = json.dumps({})", Language.PYTHON)) == 1


@pytest.mark.parametrize(
    "encoding",
    [
        '{"encoders":"codec.encode"}',
        '{"encoders":[""]}',
        '{"encoders":["*"]}',
        '{"encoders":["*."]}',
        '{"encoders":["*.*"]}',
        '{"encoders":["*.a.b"]}',
        '{"encoders":["a.*"]}',
        '{"encoders":["orjson.*"]}',
        '{"encoders":["*dump"]}',
        '{"encoders":["*.1x"]}',
        '{"decoders":["codec.*"]}',
        '{"decoders":["*.x"]}',
        '{"outputs":["transport.publish"]}',
        '{"outputs":[{"call":"transport.publish"}]}',
        '{"outputs":[{"call":"transport.publish","arguments":[-1]}]}',
        '{"outputs":[{"call":"transport.publish","arguments":[true]}]}',
        '{"outputs":[{"call":"transport.publish","arguments":["1"]}]}',
        '{"outputs":[{"call":"transport.publish","keywords":[""]}]}',
        '{"outputs":[{"call":"transport.publish","keywords":["body*"]}]}',
        '{"outputs":[{"call":"transport.*","arguments":[0]}]}',
        '{"outputs":[{"call":"*.x","arguments":[0]}]}',
        '{"outputs":[{"call":"transport.publish","arguments":[0],"unknown":true}]}',
        '{"enabled":false}',
    ],
)
def test_invalid_encoding_policy_fails_closed(encoding: str) -> None:
    with pytest.raises(ValidationError):
        Policy.model_validate_json('{"checkers":{"type.broad":{"encoding":' + encoding + "}}}")


def test_cli_reads_encoding_policy_without_modifying_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / ".pluvy").mkdir()
    policy = Path(tmp_path / ".pluvy/pluvy.json")
    policy.write_text(_POLICY.model_dump_json(by_alias=True))
    source = tmp_path / "app.py"
    content = "import codec\nvalue = codec.encode({'count': 1})\n"
    source.write_text(content)
    assert main(["--root", str(tmp_path), "--all", "--format", "json"]) == 1
    report = Report.model_validate_json(capsys.readouterr().out)
    assert [(f.rule, f.line) for f in report.findings] == [("type.broad", 2)]
    assert source.read_text() == content


def test_comment_arguments_do_not_shift_payload_positions() -> None:
    code = "import * as codec from 'codec'; import * as transport from 'transport'; "
    code += "transport.publish(/* target */ 'out', /* payload */ codec.encode({}));"
    assert _findings(code, Language.TYPESCRIPT) == ()


def test_decorator_factories_do_not_hide_actual_library_payload_results() -> None:
    source = Source(
        "app.py",
        b"import vendor\n@vendor.decorator()\n"
        b"def run() -> None:\n    pass\n"
        b"raw = vendor.load()\nconsume(raw)\n",
        Language.PYTHON,
    )
    findings = check(source, Policy(third_party_modules=("vendor",)))
    assert {f.line for f in findings if f.rule == "type.boundary"} == {5}
