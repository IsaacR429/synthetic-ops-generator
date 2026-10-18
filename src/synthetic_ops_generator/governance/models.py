from datetime import date
from enum import StrEnum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from synthetic_ops_generator.checks.requirements import (
    CheckRequirement,
)
from synthetic_ops_generator.domain.enums import (
    AssetClass,
    Environment,
    MissionCriticality,
    RiskLevel,
    ServiceClass,
)


class GovernanceAuthorityType(StrEnum):
    """
    Nature of the authority from which governance requirements derive.

    P3A introduces only the authority type required by the current
    enterprise governance contract. Additional authority classes should
    be added when a real use case requires them.
    """

    ENTERPRISE_STANDARD = "enterprise_standard"


class GovernanceAuthority(BaseModel):
    """
    Identifies the authority behind one or more policy documents.

    This represents governance provenance, not an observed approval
    event and not a runtime decision maker.
    """

    authority_id: str = Field(min_length=1)
    authority_type: GovernanceAuthorityType

    name: str = Field(min_length=1)

    source_reference: str | None = Field(
        default=None,
        min_length=1,
    )


class PolicyDocument(BaseModel):
    """
    Versioned enterprise policy or standard issued under a governance
    authority.

    Effective dates describe static policy validity. Runtime scheduling,
    validation windows, and release cycles remain outside P3A.
    """

    policy_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: str = Field(min_length=1)

    owner: str = Field(min_length=1)
    authority_id: str = Field(min_length=1)

    effective_from: date
    effective_to: date | None = None

    description: str | None = None

    @model_validator(mode="after")
    def validate_effective_period(
        self,
    ) -> "PolicyDocument":
        if (
            self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError(
                "Policy effective_to cannot precede "
                "effective_from."
            )

        return self


class PolicyApplicability(BaseModel):
    """
    Static enterprise selectors describing where a control is intended
    to apply.

    Values inside one populated selector dimension use OR semantics.
    Populated selector dimensions are intended to combine with AND
    semantics during P3B policy activation.

    Empty dimensions are unconstrained.

    P3A declares these selectors only. It does not yet resolve them
    against topology or Change context.
    """

    environments: set[Environment] = Field(
        default_factory=set
    )

    service_classes: set[ServiceClass] = Field(
        default_factory=set
    )

    mission_criticalities: set[
        MissionCriticality
    ] = Field(
        default_factory=set
    )

    asset_classes: set[AssetClass] = Field(
        default_factory=set
    )

    change_risks: set[RiskLevel] = Field(
        default_factory=set
    )


class PolicyControl(BaseModel):
    """
    One control objective contained in a PolicyDocument.

    A control references CheckRequirement identities rather than
    duplicating check-definition, evidence-acceptance, threshold, or
    execution semantics.
    """

    control_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)

    control_reference: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)

    applicability: PolicyApplicability = Field(
        default_factory=PolicyApplicability
    )

    requirement_ids: tuple[str, ...] = Field(
        min_length=1
    )

    @field_validator("requirement_ids")
    @classmethod
    def validate_requirement_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(
            not requirement_id.strip()
            for requirement_id in value
        ):
            raise ValueError(
                "Policy Control requirement references "
                "cannot be empty."
            )

        if len(value) != len(set(value)):
            raise ValueError(
                "Policy Control requirement references "
                "cannot contain duplicates."
            )

        return value


class PolicyCatalogue(BaseModel):
    """
    Referentially consistent static enterprise governance catalogue.

    P3A validates identity relationships only. It does not activate
    controls, assess evidence, resolve exceptions, or make readiness
    decisions.
    """

    authorities: dict[
        str,
        GovernanceAuthority,
    ] = Field(
        default_factory=dict
    )

    policies: dict[
        str,
        PolicyDocument,
    ] = Field(
        default_factory=dict
    )

    controls: dict[
        str,
        PolicyControl,
    ] = Field(
        default_factory=dict
    )

    requirements: dict[
        str,
        CheckRequirement,
    ] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_references(
        self,
    ) -> "PolicyCatalogue":
        for key, authority in self.authorities.items():
            if key != authority.authority_id:
                raise ValueError(
                    "Governance Authority catalogue key "
                    "does not match authority_id: "
                    f"{key}"
                )

        for key, policy in self.policies.items():
            if key != policy.policy_id:
                raise ValueError(
                    "Policy catalogue key does not match "
                    f"policy_id: {key}"
                )

            if (
                policy.authority_id
                not in self.authorities
            ):
                raise ValueError(
                    "Policy references unknown governance "
                    f"authority: {policy.authority_id}"
                )

        for key, requirement in self.requirements.items():
            if key != requirement.requirement_id:
                raise ValueError(
                    "Requirement catalogue key does not "
                    "match requirement_id: "
                    f"{key}"
                )

        for key, control in self.controls.items():
            if key != control.control_id:
                raise ValueError(
                    "Control catalogue key does not match "
                    f"control_id: {key}"
                )

            if control.policy_id not in self.policies:
                raise ValueError(
                    "Control references unknown policy: "
                    f"{control.policy_id}"
                )

            for requirement_id in control.requirement_ids:
                if (
                    requirement_id
                    not in self.requirements
                ):
                    raise ValueError(
                        "Control references unknown "
                        "requirement: "
                        f"{requirement_id}"
                    )

        return self
