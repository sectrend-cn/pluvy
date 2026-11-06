"""Application composition for independently registered grammars and rules."""

from dataclasses import dataclass
from functools import lru_cache

from pluvy.analysis.analyzer import TypedAnalyzer
from pluvy.analysis.contracts import RuleBundle
from pluvy.architecture.design import ObjectDesignRule
from pluvy.architecture.design_contracts import DesignSyntax
from pluvy.architecture.imports import (
    ImportExtractor,
    ImportResolver,
    LiteralImportResolver,
)
from pluvy.architecture.options import DISPATCH, IMPORTS, OBJECT_MODEL, OWNERSHIP, STRUCTURE
from pluvy.architecture.rules import ArchitectureRule
from pluvy.diagnostics import AnalysisError
from pluvy.languages import comments
from pluvy.languages.change_scopes import GrammarScopes
from pluvy.languages.design_syntax import GrammarDesignSyntax
from pluvy.languages.go import GoLanguage
from pluvy.languages.go.encoding import GoEncodingSyntax
from pluvy.languages.go.projection import GoProjection
from pluvy.languages.go.rules import GoTypeRule
from pluvy.languages.go.syntax import GoImports, GoMetrics
from pluvy.languages.go.test_syntax import GoTestSyntax
from pluvy.languages.java import JavaLanguage
from pluvy.languages.java.encoding import JavaEncodingSyntax
from pluvy.languages.java.failure import JavaFailureSyntax
from pluvy.languages.java.projection import JavaProjection
from pluvy.languages.java.rules import JavaSuppressions, JavaTypeRule
from pluvy.languages.java.semantic_syntax import JavaSemanticSyntax
from pluvy.languages.java.syntax import JavaDesignSyntax, JavaImports, JavaMetrics
from pluvy.languages.java.test_syntax import JavaTestSyntax
from pluvy.languages.javascript import JavaScriptLanguage
from pluvy.languages.javascript.encoding import JavaScriptEncodingSyntax
from pluvy.languages.javascript.failure import JavaScriptFailureSyntax
from pluvy.languages.javascript.projection import JavaScriptProjection
from pluvy.languages.javascript.syntax import (
    JavaScriptImports,
    JavaScriptMetrics,
    RelativeImportResolver,
)
from pluvy.languages.javascript.test_syntax import JavaScriptTestSyntax
from pluvy.languages.python import PythonLanguage
from pluvy.languages.python.encoding import PythonEncodingSyntax
from pluvy.languages.python.failure import PythonFailureSyntax
from pluvy.languages.python.projection import PythonProjection
from pluvy.languages.python.rules import PythonTypeRule
from pluvy.languages.python.syntax import PythonImports, PythonMetrics, PythonSuppressions
from pluvy.languages.python.test_syntax import PythonTestSyntax
from pluvy.languages.semantic_syntax import (
    GoSemanticSyntax,
    JavaScriptSemanticSyntax,
    PythonSemanticSyntax,
)
from pluvy.languages.typescript import TsxLanguage, TypeScriptLanguage
from pluvy.languages.typescript.contract import TypeScriptContractRule
from pluvy.languages.typescript.rules import TypeScriptTypeRule
from pluvy.languages.typescript.semantic_syntax import TypeScriptSemanticSyntax
from pluvy.languages.typescript.syntax import TypeScriptImports
from pluvy.metrics.contracts import MetricSyntax
from pluvy.metrics.options import FUNCTION_SIZE
from pluvy.metrics.rules import MetricRule
from pluvy.parsing.treesitter import TreeParser
from pluvy.plugins.bundles import BundleRegistry
from pluvy.plugins.languages import LanguagePlugin
from pluvy.plugins.profiles import AnalysisProfile
from pluvy.plugins.registry import AnalyzerRegistry
from pluvy.policy.type_options import (
    ANNOTATION,
    ASSERTION,
    SIGNATURE,
    SUPPRESSION,
    TYPE_CONTRACT,
    WILDCARD,
)
from pluvy.semantics.boundaries import BoundaryRule
from pluvy.semantics.encoding import EncodingRule
from pluvy.semantics.encoding_options import BROAD_TYPE
from pluvy.semantics.failure import FailureFlowRule
from pluvy.semantics.failure_options import FLOW_HANDLING, SWALLOW
from pluvy.semantics.model import SemanticSyntax
from pluvy.semantics.options import BOUNDARY, USAGE_RULES
from pluvy.semantics.projection.contracts import ProjectionSyntax
from pluvy.semantics.projection.options import GUARDED_PROJECTION
from pluvy.semantics.projection.rules import GuardedProjectionRule
from pluvy.semantics.testing.contracts import TestBinding, TestSyntax
from pluvy.semantics.testing.gate import TestDeletionGate
from pluvy.semantics.testing.options import TEST_INTEGRITY
from pluvy.semantics.testing.rules import TestIntegrityRule
from pluvy.semantics.usage import UsageRule
from pluvy.source import Language
from pluvy.suppressions import DirectiveSyntax, SuppressionRule

_BASE_RULES = (
    *USAGE_RULES,
    *BOUNDARY.rule_ids,
    *SUPPRESSION.rule_ids,
    *FUNCTION_SIZE.rule_ids,
    *TEST_INTEGRITY.rule_ids,
    OWNERSHIP.name,
    STRUCTURE.name,
    IMPORTS.name,
    DISPATCH.name,
    OBJECT_MODEL.name,
    GUARDED_PROJECTION.name,
)


@dataclass(frozen=True)
class _Capabilities:
    """Bind consumer-owned syntax interfaces without a heterogeneous registry."""

    metrics: MetricSyntax
    imports: ImportExtractor
    resolver: ImportResolver
    semantics: SemanticSyntax
    design: DesignSyntax
    projection: ProjectionSyntax
    testing: TestSyntax


@lru_cache(maxsize=1)
def builtin_languages() -> tuple[LanguagePlugin, ...]:
    """Register only grammar identity and discovery at this seam."""
    return (
        PythonLanguage(),
        GoLanguage(),
        JavaScriptLanguage(),
        TypeScriptLanguage(),
        TsxLanguage(),
        JavaLanguage(),
    )


@dataclass(frozen=True)
class _DeletionBindings:
    """Resolve the test capability that owns each registered language."""

    bindings: dict[Language, TestBinding]

    def binding_for(self, language: Language) -> TestBinding | None:
        return self.bindings.get(language)


def builtin_deletion_gate() -> TestDeletionGate:
    """Compose baseline test parsing for every registered grammar."""
    syntaxes: dict[Language, TestSyntax] = {
        Language.PYTHON: PythonTestSyntax(),
        Language.GO: GoTestSyntax(),
        Language.JAVASCRIPT: JavaScriptTestSyntax(),
        Language.TYPESCRIPT: JavaScriptTestSyntax(),
        Language.TSX: JavaScriptTestSyntax(),
        Language.JAVA: JavaTestSyntax(),
    }
    bindings: dict[Language, TestBinding] = {}
    for plugin in builtin_languages():
        language = plugin.definition.language
        syntax = syntaxes.get(language)
        if syntax is None:
            raise AnalysisError(f"No test syntax registered for {language}")
        bindings[language] = TestBinding(plugin.parser, syntax)
    return TestDeletionGate(_DeletionBindings(bindings))


def _compose(
    plugin: LanguagePlugin,
    syntax: _Capabilities,
    rules: tuple[RuleBundle, ...],
    required: tuple[str, ...],
    directives: DirectiveSyntax | None = None,
) -> TypedAnalyzer:
    bundles = BundleRegistry()
    for rule in rules:
        bundles.register(rule)
    shared_rules: tuple[RuleBundle, ...] = (
        UsageRule(),
        BoundaryRule(),
        MetricRule(syntax.metrics),
        ArchitectureRule(syntax.imports, syntax.resolver),
        ObjectDesignRule(syntax.design),
        GuardedProjectionRule(syntax.projection),
        TestIntegrityRule(syntax.testing),
    )
    for shared in shared_rules:
        bundles.register(shared)
    return TypedAnalyzer(
        f"builtin.{plugin.definition.language.value}",
        plugin.definition,
        plugin.parser,
        bundles,
        AnalysisProfile((*_BASE_RULES, *required)),
        syntax.semantics,
        scopes=GrammarScopes(syntax.semantics),
        directives=directives,
    )


def _python_analyzer(plugin: LanguagePlugin) -> TypedAnalyzer:
    syntax = _Capabilities(
        PythonMetrics(),
        PythonImports(),
        LiteralImportResolver(),
        PythonSemanticSyntax(),
        GrammarDesignSyntax(),
        PythonProjection(),
        PythonTestSyntax(),
    )
    required = (
        ANNOTATION.name,
        SIGNATURE.name,
        ASSERTION.name,
        BROAD_TYPE.name,
        WILDCARD.name,
        SWALLOW,
    )
    directives = comments.DirectiveSyntax(frozenset({"comment"}), "#")
    rules = (
        PythonTypeRule(EncodingRule(PythonEncodingSyntax())),
        SuppressionRule(PythonSuppressions(), directives=directives),
        FailureFlowRule(PythonFailureSyntax(), rule_ids=(SWALLOW,)),
    )
    return _compose(plugin, syntax, rules, required, directives)


def _go_analyzer(plugin: LanguagePlugin) -> TypedAnalyzer:
    syntax = _Capabilities(
        GoMetrics(),
        GoImports(),
        LiteralImportResolver(),
        GoSemanticSyntax(),
        GrammarDesignSyntax(),
        GoProjection(),
        GoTestSyntax(),
    )
    directives = comments.DirectiveSyntax(frozenset({"comment"}), "//")
    return _compose(
        plugin,
        syntax,
        (
            GoTypeRule(EncodingRule(GoEncodingSyntax())),
            SuppressionRule(comments.GrammarComments(), directives=directives),
        ),
        (BROAD_TYPE.name,),
        directives,
    )


def _java_analyzer(plugin: LanguagePlugin) -> TypedAnalyzer:
    syntax = _Capabilities(
        JavaMetrics(),
        JavaImports(),
        LiteralImportResolver(),
        JavaSemanticSyntax(),
        JavaDesignSyntax(),
        JavaProjection(),
        JavaTestSyntax(),
    )
    directives = comments.DirectiveSyntax(frozenset({"line_comment", "block_comment"}), "//")
    rules = (
        JavaTypeRule(EncodingRule(JavaEncodingSyntax())),
        SuppressionRule(JavaSuppressions(), directives=directives),
        FailureFlowRule(JavaFailureSyntax(), rule_ids=(SWALLOW,)),
    )
    return _compose(
        plugin,
        syntax,
        rules,
        (BROAD_TYPE.name, ASSERTION.name, SWALLOW),
        directives,
    )


def _javascript_analyzer(plugin: LanguagePlugin) -> TypedAnalyzer:
    syntax = _Capabilities(
        JavaScriptMetrics(),
        JavaScriptImports(),
        RelativeImportResolver(),
        JavaScriptSemanticSyntax(),
        GrammarDesignSyntax(),
        JavaScriptProjection(),
        JavaScriptTestSyntax(),
    )
    directives = comments.DirectiveSyntax(frozenset({"comment"}), "//")
    rules = (
        EncodingRule(JavaScriptEncodingSyntax()),
        SuppressionRule(comments.GrammarComments(), directives=directives),
        FailureFlowRule(JavaScriptFailureSyntax()),
    )
    return _compose(plugin, syntax, rules, (BROAD_TYPE.name, *FLOW_HANDLING.rule_ids), directives)


def _typescript_analyzer(plugin: LanguagePlugin) -> TypedAnalyzer:
    syntax = _Capabilities(
        JavaScriptMetrics(),
        TypeScriptImports(),
        RelativeImportResolver(),
        TypeScriptSemanticSyntax(),
        GrammarDesignSyntax(),
        JavaScriptProjection(),
        JavaScriptTestSyntax(),
    )
    directives = comments.DirectiveSyntax(frozenset({"comment"}), "//")
    rules = (
        TypeScriptTypeRule(EncodingRule(JavaScriptEncodingSyntax())),
        TypeScriptContractRule(),
        SuppressionRule(comments.GrammarComments(), directives=directives),
        FailureFlowRule(JavaScriptFailureSyntax()),
    )
    return _compose(
        plugin,
        syntax,
        rules,
        (ASSERTION.name, BROAD_TYPE.name, *TYPE_CONTRACT.rule_ids, *FLOW_HANDLING.rule_ids),
        directives,
    )


def builtin_analyzers() -> tuple[TypedAnalyzer, ...]:
    """Bind grammar capabilities to independent shared and exceptional rule policies."""
    python, go, javascript, typescript, tsx, java = builtin_languages()
    return (
        _python_analyzer(python),
        _go_analyzer(go),
        _javascript_analyzer(javascript),
        _typescript_analyzer(typescript),
        _typescript_analyzer(tsx),
        _java_analyzer(java),
    )


def tree_parser(language: Language) -> TreeParser:
    """Resolve the compatibility parser facade through language registration."""
    parsers = {plugin.definition.language: plugin.parser for plugin in builtin_languages()}
    try:
        return parsers[language]
    except KeyError as error:
        raise AnalysisError(f"No tree parser registered for {language}") from error


def builtin_registry() -> AnalyzerRegistry:
    """Compose isolated analyzer registrations and their typed session capabilities."""
    registry = AnalyzerRegistry()
    for analyzer in builtin_analyzers():
        registry.register(analyzer)
    return registry
