from datetime import date

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.benchmarks.models import (
    BenchmarkSource,
    BenchmarkSourceType,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
)
from synthetic_ops_generator.resilience.objectives import (
    RecoveryObjective,
    RecoveryObjectiveScope,
)


def enterprise_source() -> BenchmarkSource:
    return BenchmarkSource(
        source_id="bank_dr_standard",
        source_type=(
            BenchmarkSourceType.ENTERPRISE_SLO
        ),
        source_name="Bank Alpha DR Standard",
        source_reference=(
            "enterprise://bank_alpha/dr-standard"
        ),
        version="2026.1",
        rationale=(
            "Defines approved recovery objectives for "
            "critical payment services."
        ),
    )


def scope() -> RecoveryObjectiveScope:
    return RecoveryObjectiveScope(
        enterprise_id="bank_alpha",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
    )


def test_recovery_objective_supports_rto_and_rpo() -> None:
    objective = RecoveryObjective(
        objective_id="RO-BANK-PAYMENTS-001",
        scope=scope(),
        rto_target_seconds=300.0,
        rpo_target_seconds=60.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
        description=(
            "Production payment API recovery objectives."
        ),
    )

    assert objective.rto_target_seconds == 300.0
    assert objective.rpo_target_seconds == 60.0

    assert (
        objective.provenance.source_type
        == BenchmarkSourceType.ENTERPRISE_SLO
    )

    assert objective.effective_from == date(
        2026,
        1,
        1,
    )
    assert objective.effective_to is None


def test_recovery_objective_can_define_rto_only() -> None:
    objective = RecoveryObjective(
        objective_id="RO-RTO-ONLY",
        scope=scope(),
        rto_target_seconds=120.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
    )

    assert objective.rto_target_seconds == 120.0
    assert objective.rpo_target_seconds is None


def test_recovery_objective_can_define_rpo_only() -> None:
    objective = RecoveryObjective(
        objective_id="RO-RPO-ONLY",
        scope=scope(),
        rpo_target_seconds=30.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
    )

    assert objective.rto_target_seconds is None
    assert objective.rpo_target_seconds == 30.0


def test_recovery_objective_requires_at_least_one_target() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Recovery objective requires at least one "
            "of RTO or RPO"
        ),
    ):
        RecoveryObjective(
            objective_id="RO-NO-TARGET",
            scope=scope(),
            provenance=enterprise_source(),
            effective_from=date(2026, 1, 1),
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "rto_target_seconds",
        "rpo_target_seconds",
    ],
)
def test_recovery_targets_cannot_be_negative(
    field_name: str,
) -> None:
    values = {
        "objective_id": "RO-NEGATIVE",
        "scope": scope(),
        "provenance": enterprise_source(),
        "effective_from": date(2026, 1, 1),
        field_name: -1.0,
    }

    with pytest.raises(ValidationError):
        RecoveryObjective(**values)


def test_zero_second_recovery_target_is_valid() -> None:
    objective = RecoveryObjective(
        objective_id="RO-ZERO",
        scope=scope(),
        rto_target_seconds=0.0,
        rpo_target_seconds=0.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
    )

    assert objective.rto_target_seconds == 0.0
    assert objective.rpo_target_seconds == 0.0


def test_effective_to_may_equal_effective_from() -> None:
    objective = RecoveryObjective(
        objective_id="RO-SINGLE-DAY",
        scope=scope(),
        rto_target_seconds=300.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 1, 1),
    )

    assert objective.effective_to == date(
        2026,
        1,
        1,
    )


def test_effective_to_cannot_precede_effective_from() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Recovery objective effective_to cannot "
            "precede effective_from"
        ),
    ):
        RecoveryObjective(
            objective_id="RO-BAD-DATES",
            scope=scope(),
            rto_target_seconds=300.0,
            provenance=enterprise_source(),
            effective_from=date(2026, 2, 1),
            effective_to=date(2026, 1, 31),
        )


def test_component_scope_is_optional() -> None:
    service_scope = RecoveryObjectiveScope(
        enterprise_id="bank_alpha",
        service="payment_service",
        environment=Environment.PRODUCTION,
    )

    objective = RecoveryObjective(
        objective_id="RO-SERVICE",
        scope=service_scope,
        rto_target_seconds=300.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
    )

    assert objective.scope.component is None


def test_recovery_objective_preserves_provenance() -> None:
    source = enterprise_source()

    objective = RecoveryObjective(
        objective_id="RO-PROVENANCE",
        scope=scope(),
        rto_target_seconds=300.0,
        rpo_target_seconds=60.0,
        provenance=source,
        effective_from=date(2026, 1, 1),
    )

    assert objective.provenance.source_id == (
        "bank_dr_standard"
    )
    assert objective.provenance.version == "2026.1"
    assert objective.provenance.source_reference == (
        "enterprise://bank_alpha/dr-standard"
    )


def test_recovery_objective_is_immutable() -> None:
    objective = RecoveryObjective(
        objective_id="RO-FROZEN",
        scope=scope(),
        rto_target_seconds=300.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
    )

    with pytest.raises(ValidationError):
        objective.rto_target_seconds = 999.0


def test_recovery_objective_contains_no_observed_or_verdict_fields() -> None:
    objective = RecoveryObjective(
        objective_id="RO-BOUNDARY",
        scope=scope(),
        rto_target_seconds=300.0,
        rpo_target_seconds=60.0,
        provenance=enterprise_source(),
        effective_from=date(2026, 1, 1),
    )

    dumped = objective.model_dump()

    forbidden = {
        "scenario_id",
        "recovery_duration_seconds",
        "exposure_interval_seconds",
        "rto_met",
        "rto_breached",
        "rpo_met",
        "rpo_breached",
        "dr_success",
        "actual_data_loss",
        "data_loss",
    }

    assert forbidden.isdisjoint(dumped)
