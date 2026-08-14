from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import (
    ManualSimulationClock,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.history.event_adapter import (
    build_historical_metric_events,
)
from synthetic_ops_generator.history.incident_dataset import (
    build_historical_incident_dataset,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.history.scenario_runtime import (
    build_historical_scenario_runtime,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.runner import (
    ScenarioRunner,
)

CONFIG_ROOT = Path("config")


def build_bank_02_events():
    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-02.yaml"
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    runtime = (
        build_historical_scenario_runtime(
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
        )
    )

    anchor_time = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    dataset = (
        build_historical_incident_dataset(
            runtime=runtime,
            anchor_time=anchor_time,
            curve_spec=(
                PerturbationCurveSpec(
                    degradation_samples=4,
                    plateau_samples=2,
                    recovery_samples=4,
                )
            ),
            random_source=(
                SimulationRandom(
                    seed=42
                )
            ),
        )
    )

    ids = IdFactory()

    runner = ScenarioRunner(
        ids=ids,
        clock=ManualSimulationClock(
            anchor_time
        ),
    )

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    original_time = (
        context.simulation_time
    )

    events = build_historical_metric_events(
        dataset=dataset,
        runtime=runtime,
        context=context,
        ids=ids,
    )

    return (
        dataset,
        context,
        original_time,
        events,
    )


def test_historical_dataset_becomes_metric_observed_events(
) -> None:
    _, _, _, events = (
        build_bank_02_events()
    )

    assert len(events) == 48

    assert all(
        event.event_type
        == "metric.observed"
        for event in events
    )

    assert all(
        event.source_system
        == "synthetic_observability"
        for event in events
    )


def test_historical_events_have_contiguous_sequences(
) -> None:
    _, _, _, events = (
        build_bank_02_events()
    )

    assert tuple(
        event.sequence_number
        for event in events
    ) == tuple(
        range(1, 49)
    )


def test_historical_events_are_emitted_chronologically(
) -> None:
    _, _, _, events = (
        build_bank_02_events()
    )

    timestamps = tuple(
        event.event_time
        for event in events
    )

    assert all(
        current <= following
        for current, following
        in pairwise(timestamps)
    )


def test_historical_events_preserve_run_identity(
) -> None:
    _, context, _, events = (
        build_bank_02_events()
    )

    assert all(
        event.scenario_id
        == context.scenario_id
        for event in events
    )

    assert all(
        event.run_id
        == context.run_id
        for event in events
    )

    assert all(
        event.chg_id
        == context.chg_id
        for event in events
    )

    assert all(
        event.business_stream
        == context.business_stream
        for event in events
    )

    assert all(
        event.service
        == context.service
        for event in events
    )


def test_historical_events_include_historical_context(
) -> None:
    _, _, _, events = (
        build_bank_02_events()
    )

    historical = (
        events[0]
        .data["metric"]["historical"]
    )

    assert set(historical) == {
        "counterfactual_value",
        "perturbation_strength",
        "perturbation_phase",
    }


def test_each_historical_timestamp_contains_all_metrics(
) -> None:
    _, _, _, events = (
        build_bank_02_events()
    )

    timestamps = sorted(
        {
            event.event_time
            for event in events
        }
    )

    assert len(timestamps) == 16

    for timestamp in timestamps:
        timestamp_events = [
            event
            for event in events
            if event.event_time
            == timestamp
        ]

        assert len(
            timestamp_events
        ) == 3

        assert {
            event.data["metric"][
                "metric_definition_id"
            ]
            for event
            in timestamp_events
        } == {
            "request_latency",
            "error_rate",
            "availability",
        }


def test_event_adapter_does_not_mutate_scenario_time(
) -> None:
    (
        dataset,
        context,
        original_time,
        events,
    ) = build_bank_02_events()

    assert (
        events[0].event_time
        < dataset.change_boundary_time
    )

    assert (
        context.simulation_time
        == original_time
    )

    assert (
        context.simulation_time
        == dataset.change_boundary_time
    )


def test_event_adapter_advances_canonical_sequence(
) -> None:
    _, context, _, events = (
        build_bank_02_events()
    )

    assert len(events) == 48
    assert context.sequence_number == 48
