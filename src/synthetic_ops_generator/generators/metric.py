from collections.abc import AsyncIterator, Mapping
from typing import ClassVar

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
    MetricBaseline,
)
from synthetic_ops_generator.benchmarks.evaluator import (
    classify_metric,
)
from synthetic_ops_generator.benchmarks.models import (
    ResolvedBenchmark,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.metrics.models import MetricDefinition
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


class MetricGenerator(SourceGenerator):
    """
    Generates synthetic operational Metric observations.

    Metric semantics, Baselines and effective Benchmark/SLO policy
    are supplied to the generator. The generator does not define
    or modify operational policy.
    """

    source_system = "synthetic_observability"

    _SUPPORTED_PROFILES: ClassVar[frozenset[str]] = frozenset(
        {
            "healthy_baseline",
            "healthy_post_change",
        }
    )

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        definitions: Mapping[str, MetricDefinition],
        baseline_profile: BaselineProfile,
        benchmarks: Mapping[str, ResolvedBenchmark],
        benchmark_profile_id: str,
        random_source: SimulationRandom,
        metric_ids: tuple[str, ...] | None = None,
    ) -> None:
        if behaviour.source != SourceDomain.METRIC:
            raise ValueError(
                "MetricGenerator requires a Metric behaviour."
            )

        if not benchmark_profile_id:
            raise ValueError(
                "MetricGenerator requires a Benchmark profile ID."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._definitions = dict(definitions)
        self._baseline_profile = baseline_profile
        self._benchmarks = dict(benchmarks)
        self._benchmark_profile_id = benchmark_profile_id
        self._random = random_source

        self._metric_ids = (
            metric_ids
            if metric_ids is not None
            else tuple(baseline_profile.metrics)
        )

        if not self._metric_ids:
            raise ValueError(
                "MetricGenerator requires at least one Metric."
            )

        self._validate_configuration()

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        if (
            self._behaviour.profile_id
            not in self._SUPPORTED_PROFILES
        ):
            raise ValueError(
                "Unsupported Metric behaviour profile: "
                f"{self._behaviour.profile_id}"
            )

        for metric_id in self._metric_ids:
            definition = self._definitions[metric_id]
            baseline = self._baseline_profile.metrics[metric_id]
            benchmark = self._benchmarks[metric_id]

            observed_value = self._sample_observation(
                baseline
            )

            classification = classify_metric(
                definition,
                benchmark,
                observed_value,
            )

            yield GeneratedEvent(
                event_id=self._ids.event_id(),
                event_type="metric.observed",
                event_time=context.simulation_time,
                source_system=self.source_system,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                business_stream=context.business_stream,
                service=context.service,
                component=None,
                environment=context.environment,
                sequence_number=context.next_sequence(),
                data={
                    "metric": {
                        "metric_definition_id": (
                            definition.metric_definition_id
                        ),
                        "name": definition.name,
                        "observed_value": observed_value,
                        "unit": definition.unit,
                        "evaluation_statistic": (
                            definition.evaluation_statistic
                        ),
                        "direction": definition.direction.value,
                        "classification": classification.value,
                        "baseline_profile_id": (
                            self._baseline_profile.profile_id
                        ),
                        "baseline": baseline.model_dump(
                            mode="json"
                        ),
                        "benchmark_profile_id": (
                            self._benchmark_profile_id
                        ),
                        "effective_benchmark": (
                            benchmark.model_dump(
                                mode="json"
                            )
                        ),
                        "behaviour_profile_id": (
                            self._behaviour.profile_id
                        ),
                        "scenario_state": (
                            context.scenario_state.value
                        ),
                    }
                },
            )

    def _sample_observation(
        self,
        baseline: MetricBaseline,
    ) -> float:
        value = self._random.normal(
            baseline.center,
            baseline.noise_stddev,
        )

        if baseline.lower_bound is not None:
            value = max(
                value,
                baseline.lower_bound,
            )

        if baseline.upper_bound is not None:
            value = min(
                value,
                baseline.upper_bound,
            )

        return float(value)

    def _validate_configuration(self) -> None:
        for metric_id in self._metric_ids:
            definition = self._definitions.get(
                metric_id
            )

            if definition is None:
                raise ValueError(
                    "Missing Metric Definition: "
                    f"{metric_id}"
                )

            baseline = self._baseline_profile.metrics.get(
                metric_id
            )

            if baseline is None:
                raise ValueError(
                    "Missing Metric Baseline: "
                    f"{metric_id}"
                )

            if (
                baseline.metric_definition_id
                != metric_id
            ):
                raise ValueError(
                    "Metric Baseline ID does not match "
                    f"its configuration key: {metric_id}"
                )

            benchmark = self._benchmarks.get(
                metric_id
            )

            if benchmark is None:
                raise ValueError(
                    "Missing resolved Benchmark: "
                    f"{metric_id}"
                )

            if (
                benchmark.metric_definition_id
                != metric_id
            ):
                raise ValueError(
                    "Resolved Benchmark ID does not match "
                    f"Metric Definition: {metric_id}"
                )