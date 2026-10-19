from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path

import pytest

from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)
from synthetic_ops_generator.control.configuration import (
    GenerationLifecycle,
)
from synthetic_ops_generator.control.models import (
    RunStatus,
)
from synthetic_ops_generator.control.service import (
    ControlService,
)
from synthetic_ops_generator.control.sqlite_run_store import (
    SQLiteRunStore,
)
from synthetic_ops_generator.core.sqlite_identifiers import (
    SQLiteIdFactory,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)
from synthetic_ops_generator.domain.resilience import (
    ReplicationObservation,
    ResilienceObservation,
    ResilienceObservationType,
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)
from synthetic_ops_generator.resilience.assessment import (
    RecoveryObjectiveAssessmentContext,
    RecoveryObjectiveAssessmentStatus,
    assess_rpo_objective,
    assess_rto_objective,
)
from synthetic_ops_generator.resilience.catalogue import (
    load_recovery_objective_configuration,
    resolve_recovery_objective,
)
from synthetic_ops_generator.resilience.exposure import (
    ReplicationExposureMeasurementStatus,
    ReplicationExposureScope,
    measure_replication_exposure,
)
from synthetic_ops_generator.resilience.recovery import (
    RecoveryMeasurementScope,
    RecoveryMeasurementStatus,
    measure_service_recovery,
)
from synthetic_ops_generator.retention.sqlite import (
    SQLiteEventStore,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"

RECOVERY_OBJECTIVES_PATH = (
    CONFIG_ROOT
    / "resilience"
    / "recovery_objectives.yaml"
)


def test_cross_industry_recovery_objective_configuration_loads() -> None:
    configuration = (
        load_recovery_objective_configuration(
            RECOVERY_OBJECTIVES_PATH
        )
    )

    assert set(configuration.sources) == {
        "bank_dr_standard",
        "insurer_dr_standard",
    }

    assert set(configuration.objectives) == {
        "RO-BANK-PAYMENTS-PROD",
        "RO-INS-CLAIMS-PROD",
    }


@pytest.mark.parametrize(
    (
        "objective_id,"
        "enterprise_id,"
        "service,"
        "component,"
        "expected_rto,"
        "expected_rpo,"
        "expected_source_id"
    ),
    [
        (
            "RO-BANK-PAYMENTS-PROD",
            "bank_alpha",
            "payment_service",
            "payment_api",
            300.0,
            120.0,
            "bank_dr_standard",
        ),
        (
            "RO-INS-CLAIMS-PROD",
            "insurer_alpha",
            "claims_service",
            "claims_api",
            600.0,
            300.0,
            "insurer_dr_standard",
        ),
    ],
)
def test_cross_industry_recovery_objectives_resolve(
    objective_id: str,
    enterprise_id: str,
    service: str,
    component: str,
    expected_rto: float,
    expected_rpo: float,
    expected_source_id: str,
) -> None:
    configuration = (
        load_recovery_objective_configuration(
            RECOVERY_OBJECTIVES_PATH
        )
    )

    objective = resolve_recovery_objective(
        configuration=configuration,
        objective_id=objective_id,
    )

    assert objective.objective_id == objective_id

    assert (
        objective.scope.enterprise_id
        == enterprise_id
    )
    assert objective.scope.service == service
    assert objective.scope.component == component
    assert (
        objective.scope.environment
        == Environment.PRODUCTION
    )

    assert (
        objective.rto_target_seconds
        == expected_rto
    )
    assert (
        objective.rpo_target_seconds
        == expected_rpo
    )

    assert (
        objective.provenance.source_id
        == expected_source_id
    )


async def _collect_dr_resilience_events(
    *,
    tmp_path: Path,
    scenario_id: str,
):
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    service = ControlService(
        catalogue=ScenarioCatalogue(
            CONFIG_ROOT / "scenarios"
        ),
        enterprise_root=(
            CONFIG_ROOT / "enterprises"
        ),
        generator_factory=GeneratorFactory(
            config_root=CONFIG_ROOT
        ),
        ids=SQLiteIdFactory(
            database_path=(
                tmp_path / "identifiers.sqlite3"
            )
        ),
        store=store,
        run_store=run_store,
        replay_publisher=InMemoryPublisher(),
        active_run_manager=ActiveRunManager(),
    )

    started = None

    try:
        started = await service.start_run(
            scenario_id=scenario_id,
            random_seed=42,
            generation_lifecycle=(
                GenerationLifecycle.CONTINUOUS
            ),
        )

        assert started.status == RunStatus.RUNNING

        resilience_events = []

        for _ in range(40):
            await asyncio.sleep(0.1)

            live_record = await service.get_run(
                started.run_id
            )

            assert live_record is not None

            assert (
                live_record.status
                != RunStatus.FAILED
            ), live_record.error_message

            events = await store.get_run_events(
                started.run_id
            )

            resilience_events = sorted(
                (
                    event
                    for event in events
                    if (
                        event.source_domain
                        == SourceDomain.RESILIENCE
                    )
                ),
                key=lambda event: (
                    event.sequence_number
                ),
            )

            if len(resilience_events) == 9:
                break

        else:
            pytest.fail(
                f"{scenario_id} did not produce "
                "nine bounded resilience facts."
            )

        stopped = await service.stop_run(
            started.run_id
        )

        assert stopped.status == RunStatus.STOPPED

        return resilience_events

    finally:
        if started is not None:
            with suppress(Exception):
                await service.stop_run(
                    started.run_id
                )

        await run_store.stop()
        await store.stop()


@pytest.mark.parametrize(
    (
        "scenario_id,"
        "objective_id,"
        "enterprise_id,"
        "expected_service,"
        "expected_component"
    ),
    [
        (
            "BANK-06",
            "RO-BANK-PAYMENTS-PROD",
            "bank_alpha",
            "payment_service",
            "payment_api",
        ),
        (
            "INS-06",
            "RO-INS-CLAIMS-PROD",
            "insurer_alpha",
            "claims_service",
            "claims_api",
        ),
    ],
)
@pytest.mark.asyncio
async def test_dr_runtime_evidence_measures_and_assesses_configured_objectives(
    tmp_path: Path,
    scenario_id: str,
    objective_id: str,
    enterprise_id: str,
    expected_service: str,
    expected_component: str,
) -> None:
    events = await _collect_dr_resilience_events(
        tmp_path=tmp_path,
        scenario_id=scenario_id,
    )

    assert len(events) == 9

    primary_unavailable_event = events[0]
    replication_event = events[1]
    secondary_serving_event = events[7]

    unavailable = (
        ServiceAvailabilityObservation.model_validate(
            primary_unavailable_event.data[
                "service_availability_observation"
            ]
        )
    )

    replication = ReplicationObservation.model_validate(
        replication_event.data[
            "replication_observation"
        ]
    )

    serving = ResilienceObservation.model_validate(
        secondary_serving_event.data[
            "resilience_observation"
        ]
    )

    assert (
        unavailable.availability_state
        == ServiceAvailabilityState.UNAVAILABLE
    )

    assert (
        serving.observation_type
        == ResilienceObservationType.INSTANCE_SERVING
    )

    assert unavailable.service == expected_service
    assert unavailable.component == expected_component

    assert replication.service == expected_service
    assert replication.component == expected_component

    assert serving.service == expected_service
    assert serving.component == expected_component

    recovery = measure_service_recovery(
        scope=RecoveryMeasurementScope(
            service=unavailable.service,
            component=unavailable.component,
            failed_site_id=unavailable.site_id,
            failed_service_instance_id=(
                unavailable.service_instance_id
            ),
            restored_site_id=serving.to_site_id,
            restored_service_instance_id=(
                serving.to_service_instance_id
            ),
        ),
        outage_observation=unavailable,
        restoration_observation=serving,
    )

    assert (
        recovery.status
        == RecoveryMeasurementStatus.MEASURED
    )

    assert (
        recovery.recovery_duration_seconds
        is not None
    )
    assert recovery.recovery_duration_seconds >= 0

    exposure = measure_replication_exposure(
        scope=ReplicationExposureScope(
            service=replication.service,
            component=replication.component,
            source_site_id=(
                replication.from_site_id
            ),
            source_service_instance_id=(
                replication.from_service_instance_id
            ),
            target_site_id=(
                replication.to_site_id
            ),
            target_service_instance_id=(
                replication.to_service_instance_id
            ),
        ),
        outage_observation=unavailable,
        replication_observation=replication,
    )

    assert (
        exposure.status
        == ReplicationExposureMeasurementStatus.MEASURED
    )

    assert (
        exposure.exposure_interval_seconds
        is not None
    )
    assert exposure.exposure_interval_seconds >= 0

    configuration = (
        load_recovery_objective_configuration(
            RECOVERY_OBJECTIVES_PATH
        )
    )

    objective = resolve_recovery_objective(
        configuration=configuration,
        objective_id=objective_id,
    )

    context = RecoveryObjectiveAssessmentContext(
        enterprise_id=enterprise_id,
        environment=Environment.PRODUCTION,
        evaluated_on=unavailable.observed_at.date(),
    )

    rto = assess_rto_objective(
        objective=objective,
        measurement=recovery,
        context=context,
    )

    rpo = assess_rpo_objective(
        objective=objective,
        measurement=exposure,
        context=context,
    )

    assert (
        rto.status
        == RecoveryObjectiveAssessmentStatus.MET
    )

    assert (
        rpo.status
        == RecoveryObjectiveAssessmentStatus.MET
    )

    assert (
        rto.actual_seconds
        == recovery.recovery_duration_seconds
    )

    assert (
        rpo.actual_seconds
        == exposure.exposure_interval_seconds
    )

    assert (
        rto.target_seconds
        == objective.rto_target_seconds
    )

    assert (
        rpo.target_seconds
        == objective.rpo_target_seconds
    )

    assert (
        rto.provenance_source_id
        == objective.provenance.source_id
    )

    assert (
        rpo.provenance_source_id
        == objective.provenance.source_id
    )


def test_configured_objectives_do_not_embed_scenario_identity() -> None:
    configuration = (
        load_recovery_objective_configuration(
            RECOVERY_OBJECTIVES_PATH
        )
    )

    for objective_id in configuration.objectives:
        objective = resolve_recovery_objective(
            configuration=configuration,
            objective_id=objective_id,
        )

        dumped = objective.model_dump()

        assert "scenario_id" not in dumped
        assert "dr_success" not in dumped
        assert "actual_data_loss" not in dumped
        assert "data_loss" not in dumped
