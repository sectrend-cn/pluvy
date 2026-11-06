"""Type and syntax checker switches shared across language implementations."""

from pydantic import Field

from pluvy.policy.contracts import (
    CheckerConfiguration,
    CheckerDefinition,
    CheckerOptions,
    CheckerState,
)

ANNOTATION = CheckerDefinition("type.annotation")

SIGNATURE = CheckerDefinition("type.signature")

ASSERTION = CheckerDefinition("type.assertion")

SUPPRESSION = CheckerDefinition("type.suppression")

WILDCARD = CheckerDefinition("imports.wildcard")

NULLABLE = "type.nullable"

UNION = "type.union"

TYPE_CONTRACT = CheckerDefinition("type.contract", (NULLABLE, UNION))


class TypeContractOptions(CheckerOptions):
    """Limit nullable declarations, nullish fallbacks and union membership."""

    max_members: int = Field(default=4, ge=1)
    optional_fields: int = Field(default=3, ge=1)
    null_defaults: int = Field(default=3, ge=1)


class TypeCheckers(CheckerConfiguration):
    """Register owned checker fields and project their execution switches."""

    type_annotation: CheckerOptions = Field(
        default=CheckerOptions(),
        validation_alias=ANNOTATION.name,
        serialization_alias=ANNOTATION.name,
    )
    type_signature: CheckerOptions = Field(
        default=CheckerOptions(),
        validation_alias=SIGNATURE.name,
        serialization_alias=SIGNATURE.name,
    )
    type_assertion: CheckerOptions = Field(
        default=CheckerOptions(),
        validation_alias=ASSERTION.name,
        serialization_alias=ASSERTION.name,
    )
    type_suppression: CheckerOptions = Field(
        default=CheckerOptions(),
        validation_alias=SUPPRESSION.name,
        serialization_alias=SUPPRESSION.name,
    )
    imports_wildcard: CheckerOptions = Field(
        default=CheckerOptions(),
        validation_alias=WILDCARD.name,
        serialization_alias=WILDCARD.name,
    )
    type_contract: TypeContractOptions = Field(
        default=TypeContractOptions(),
        validation_alias=TYPE_CONTRACT.name,
        serialization_alias=TYPE_CONTRACT.name,
    )

    def checker_states(self) -> tuple[CheckerState, ...]:
        return (
            *super().checker_states(),
            ANNOTATION.configure(self.type_annotation.enabled),
            SIGNATURE.configure(self.type_signature.enabled),
            ASSERTION.configure(self.type_assertion.enabled),
            SUPPRESSION.configure(self.type_suppression.enabled),
            WILDCARD.configure(self.imports_wildcard.enabled),
            TYPE_CONTRACT.configure(self.type_contract.enabled),
        )
