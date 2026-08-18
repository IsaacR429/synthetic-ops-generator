import asyncio
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
    MetricBaseline,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkSource,
    BenchmarkSourceType,
    ResolvedBenchmark,
)
from synthetic_ops_generator.core.clock import (
    ManualSimulationClock,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.generators.metric import MetricGenerator
from synthetic_ops_generator.metrics.models import (
    MetricDefinition,
    MetricDirection,
)
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def build_context(
    *,
    state: OperationalState = OperationalState.NORMAL,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="BANK-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=state,
        simulation_time=datetime(
            2026,
            8,
            11,
            10,
            0,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


def build_behaviour(
    *,
    profile_id: str = "healthy_baseline",
    state: OperationalState = OperationalState.NORMAL,
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.METRIC,
        during_state=state,
        profile_id=profile_id,
    )


def build_definitions() -> dict[str, MetricDefinition]:
    return {
        "request_latency": MetricDefinition(
            metric_definition_id="request_latency",
            name="Request Latency",
            unit="ms",
            evaluation_statistic="p95",
            direction=MetricDirection.LOWER_IS_BETTER,
        ),
        "error_rate": MetricDefinition(
            metric_definition_id="error_rate",
            name="Error Rate",
            unit="percent",
            evaluation_statistic="average",
            direction=MetricDirection.LOWER_IS_BETTER,
        ),
        "availability": MetricDefinition(
            metric_definition_id="availability",
            name="Availability",
            unit="percent",
            evaluation_statistic="average",
            direction=MetricDirection.HIGHER_IS_BETTER,
        ),
    }


def build_baseline_profile(
    *,
    noise: bool = False,
) -> BaselineProfile:
    latency_noise = 15.0 if noise else 0.0
    error_noise = 0.02 if noise else 0.0
    availability_noise = 0.002 if noise else 0.0

    return BaselineProfile(
        profile_id="critical_interactive_nominal",
        name="Critical Interactive Nominal Baseline",
        historical_window_minutes=30,
        sample_interval_seconds=300,
        metrics={
            "request_latency": MetricBaseline(
                metric_definition_id="request_latency",
                center=180,
                noise_stddev=latency_noise,
                lower_bound=100,
                upper_bound=260,
            ),
            "error_rate": MetricBaseline(
                metric_definition_id="error_rate",
                center=0.05,
                noise_stddev=error_noise,
                lower_bound=0.0,
                upper_bound=0.10,
            ),
            "availability": MetricBaseline(
                metric_definition_id="availability",
                center=99.995,
                noise_stddev=availability_noise,
                lower_bound=99.99,
                upper_bound=100.0,
            ),
        },
    )


def build_provenance() -> BenchmarkSource:
    return BenchmarkSource(
        source_id="synthetic_metric_policy_v1",
        source_type=BenchmarkSourceType.SYNTHETIC_REFERENCE,
        source_name="Synthetic Ops Generator Metric Policy",
        source_reference="internal:metric-policy-v1",
        version="1.0",
        rationale="Controlled synthetic test policy.",
    )


def build_benchmarks() -> dict[str, ResolvedBenchmark]:
    provenance = build_provenance()

    return {
        "request_latency": ResolvedBenchmark(
            metric_definition_id="request_latency",
            reference_target=300,
            warning_threshold=500,
            blocking_threshold=1000,
            provenance=provenance,
        ),
        "error_rate": ResolvedBenchmark(
            metric_definition_id="error_rate",
            reference_target=0.10,
            warning_threshold=1.0,
            blocking_threshold=5.0,
            provenance=provenance,
        ),
        "availability": ResolvedBenchmark(
            metric_definition_id="availability",
            reference_target=99.99,
            warning_threshold=99.90,
            blocking_threshold=99.00,
            provenance=provenance,
        ),
    }


def build_generator(
    *,
    behaviour: ScenarioBehaviour | None = None,
    random_seed: int = 42,
    noise: bool = False,
) -> MetricGenerator:
    return MetricGenerator(
        ids=IdFactory(),
        behaviour=(
            behaviour
            if behaviour is not None
            else build_behaviour()
        ),
        definitions=build_definitions(),
        baseline_profile=build_baseline_profile(
            noise=noise
        ),
        benchmarks=build_benchmarks(),
        benchmark_profile_id=(
            "critical_interactive_transaction"
        ),
        random_source=SimulationRandom(
            random_seed
        ),
    )


async def collect_events(
    generator: MetricGenerator,
    context: ScenarioContext,
):
    clock = ManualSimulationClock(
        context.simulation_time
    )

    events = []

    async for event in generator.generate(context):
        events.append(event)

        clock.advance(5)
        context.simulation_time = clock.now()

    return events


def test_healthy_profile_generates_three_metric_events() -> None:
    events = asyncio.run(
        collect_events(
            build_generator(),
            build_context(),
        )
    )

    assert len(events) == 3

    assert {
        event.event_type
        for event in events
    } == {"metric.observed"}


def test_healthy_metrics_are_classified_normal() -> None:
    events = asyncio.run(
        collect_events(
            build_generator(),
            build_context(),
        )
    )

    classifications = {
        event.data["metric"]["classification"]
        for event in events
    }

    assert classifications == {"normal"}


def test_metric_values_come_from_baseline() -> None:
    events = asyncio.run(
        collect_events(
            build_generator(),
            build_context(),
        )
    )

    values = {
        event.data["metric"]["metric_definition_id"]:
        event.data["metric"]["observed_value"]
        for event in events
    }

    assert values == {
        "request_latency": 180.0,
        "error_rate": 0.05,
        "availability": 99.995,
    }


def test_metric_event_preserves_policy_and_baseline() -> None:
    events = asyncio.run(
        collect_events(
            build_generator(),
            build_context(),
        )
    )

    latency = next(
        event.data["metric"]
        for event in events
        if (
            event.data["metric"]["metric_definition_id"]
            == "request_latency"
        )
    )

    assert latency["observed_value"] == 180.0

    assert (
        latency["baseline_profile_id"]
        == "critical_interactive_nominal"
    )

    assert latency["baseline"]["center"] == 180

    assert (
        latency["benchmark_profile_id"]
        == "critical_interactive_transaction"
    )

    benchmark = latency["effective_benchmark"]

    assert benchmark["reference_target"] == 300
    assert benchmark["warning_threshold"] == 500
    assert benchmark["blocking_threshold"] == 1000

    assert (
        benchmark["provenance"]["source_type"]
        == "synthetic_reference"
    )


def test_metric_events_are_service_scoped() -> None:
    events = asyncio.run(
        collect_events(
            build_generator(),
            build_context(),
        )
    )

    assert {
        event.service for event in events
    } == {"payment_service"}

    assert {
        event.source_domain for event in events
    } == {SourceDomain.METRIC}

    assert {
        event.component for event in events
    } == {None}

    assert {
        event.chg_id for event in events
    } == {"CHG0000001"}


def test_metric_sequence_and_time_progress() -> None:
    context = build_context()

    events = asyncio.run(
        collect_events(
            build_generator(),
            context,
        )
    )

    assert [
        event.sequence_number
        for event in events
    ] == [1, 2, 3]

    event_times = [
        event.event_time
        for event in events
    ]

    assert event_times == sorted(event_times)
    assert len(set(event_times)) == 3


def test_healthy_post_change_profile_is_supported() -> None:
    behaviour = build_behaviour(
        profile_id="healthy_post_change",
        state=OperationalState.OBSERVING,
    )

    context = build_context(
        state=OperationalState.OBSERVING,
    )

    events = asyncio.run(
        collect_events(
            build_generator(
                behaviour=behaviour,
            ),
            context,
        )
    )

    assert len(events) == 3

    assert {
        event.data["metric"]["behaviour_profile_id"]
        for event in events
    } == {"healthy_post_change"}


def test_generator_does_not_run_outside_behaviour_state() -> None:
    context = build_context(
        state=OperationalState.OBSERVING,
    )

    events = asyncio.run(
        collect_events(
            build_generator(),
            context,
        )
    )

    assert events == []
    assert context.sequence_number == 0


def test_metric_generation_is_deterministic_for_same_seed() -> None:
    first = asyncio.run(
        collect_events(
            build_generator(
                random_seed=123,
                noise=True,
            ),
            build_context(),
        )
    )

    second = asyncio.run(
        collect_events(
            build_generator(
                random_seed=123,
                noise=True,
            ),
            build_context(),
        )
    )

    first_values = [
        event.data["metric"]["observed_value"]
        for event in first
    ]

    second_values = [
        event.data["metric"]["observed_value"]
        for event in second
    ]

    assert first_values == second_values


def test_generator_rejects_wrong_source_domain() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.NORMAL,
        profile_id="healthy_baseline",
    )

    with pytest.raises(
        ValueError,
        match="requires a Metric behaviour",
    ):
        build_generator(
            behaviour=behaviour,
        )


def test_generator_rejects_missing_definition() -> None:
    definitions = build_definitions()
    definitions.pop("availability")

    with pytest.raises(
        ValueError,
        match="Missing Metric Definition",
    ):
        MetricGenerator(
            ids=IdFactory(),
            behaviour=build_behaviour(),
            definitions=definitions,
            baseline_profile=build_baseline_profile(),
            benchmarks=build_benchmarks(),
            benchmark_profile_id=(
                "critical_interactive_transaction"
            ),
            random_source=SimulationRandom(42),
        )


def test_generator_rejects_unknown_profile() -> None:
    behaviour = build_behaviour(
        profile_id="unknown_metric_profile",
    )

    generator = build_generator(
        behaviour=behaviour,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Metric behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )


def test_degraded_profile_generates_blocking_metrics() -> None:
    behaviour = build_behaviour(
        profile_id="degraded_post_change",
        state=OperationalState.DEGRADED,
    )

    context = build_context(
        state=OperationalState.DEGRADED,
    )

    events = asyncio.run(
        collect_events(
            build_generator(
                behaviour=behaviour,
            ),
            context,
        )
    )

    assert len(events) == 3

    assert {
        event.data["metric"]["classification"]
        for event in events
    } == {"blocking"}

    assert {
        event.data["metric"]["behaviour_profile_id"]
        for event in events
    } == {"degraded_post_change"}

    assert {
        event.data["metric"]["scenario_state"]
        for event in events
    } == {"degraded"}


def test_degraded_values_use_resolved_blocking_thresholds() -> None:
    behaviour = build_behaviour(
        profile_id="degraded_post_change",
        state=OperationalState.DEGRADED,
    )

    events = asyncio.run(
        collect_events(
            build_generator(
                behaviour=behaviour,
            ),
            build_context(
                state=OperationalState.DEGRADED,
            ),
        )
    )

    values = {
        event.data["metric"]["metric_definition_id"]:
        event.data["metric"]["observed_value"]
        for event in events
    }

    assert values == {
        "request_latency": 1000.0,
        "error_rate": 5.0,
        "availability": 99.0,
    }


def test_recovered_profile_generates_normal_metrics() -> None:
    behaviour = build_behaviour(
        profile_id="recovered_post_rollback",
        state=OperationalState.RECOVERY,
    )

    context = build_context(
        state=OperationalState.RECOVERY,
    )

    events = asyncio.run(
        collect_events(
            build_generator(
                behaviour=behaviour,
            ),
            context,
        )
    )

    assert len(events) == 3

    assert {
        event.data["metric"]["classification"]
        for event in events
    } == {"normal"}

    assert {
        event.data["metric"]["behaviour_profile_id"]
        for event in events
    } == {"recovered_post_rollback"}

    assert {
        event.data["metric"]["scenario_state"]
        for event in events
    } == {"recovery"}


def test_recovered_values_use_resolved_reference_targets() -> None:
    behaviour = build_behaviour(
        profile_id="recovered_post_rollback",
        state=OperationalState.RECOVERY,
    )

    events = asyncio.run(
        collect_events(
            build_generator(
                behaviour=behaviour,
            ),
            build_context(
                state=OperationalState.RECOVERY,
            ),
        )
    )

    values = {
        event.data["metric"]["metric_definition_id"]:
        event.data["metric"]["observed_value"]
        for event in events
    }

    assert values == {
        "request_latency": 300.0,
        "error_rate": 0.10,
        "availability": 99.99,
    }