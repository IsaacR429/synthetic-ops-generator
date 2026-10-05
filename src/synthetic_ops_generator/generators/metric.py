from collections.abc import AsyncIterator, Mapping

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
    MetricBaseline,
)
from synthetic_ops_generator.benchmarks.evaluator import (
    evaluate_metric,
)

from synthetic_ops_generator.benchmarks.models import (
    ResolvedBenchmark,
)
from synthetic_ops_generator.capacity.evaluator import (
    classify_capacity,
)
from synthetic_ops_generator.capacity.models import (
    CapacityProfile,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.metrics.event_payload import (
    METRIC_EVENT_TYPE,
    METRIC_SOURCE_SYSTEM,
    MetricCapacityContext,
    build_metric_event_data,
)
from synthetic_ops_generator.metrics.models import (
    MetricDefinition,
    MetricDirection,
)

from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    CAPACITY_PRESSURE,
    CAPACITY_RECOVERY,
    CAPACITY_SATURATION,
    DEGRADED_POST_CHANGE,
    OPERATIONAL_DEGRADATION,
    OPERATIONAL_RECOVERY,
    OPERATIONAL_WARNING,
    RECOVERED_POST_ROLLBACK,
    SUPPORTED_PROFILES_BY_SOURCE,
)


class MetricGenerator(SourceGenerator):
    """
    Generates synthetic operational Metric observations.

    Metric semantics, Baselines and effective Benchmark/SLO policy
    are supplied to the generator. The generator does not define
    or modify operational policy.
    """

    source_system = METRIC_SOURCE_SYSTEM

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
        capacity_profile: CapacityProfile | None = None,
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
        self._capacity_profile = capacity_profile

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
            not in SUPPORTED_PROFILES_BY_SOURCE[
                SourceDomain.METRIC
            ]
        ):
            raise ValueError(
                "Unsupported Metric behaviour profile: "
                f"{self._behaviour.profile_id}"
            )

        for metric_id in self._metric_ids:
            definition = self._definitions[metric_id]
            baseline = self._baseline_profile.metrics[metric_id]
            benchmark = self._benchmarks.get(metric_id)


            observed_value = self._generate_observation(
                baseline=baseline,
                benchmark=benchmark,
            )

            evaluation = evaluate_metric(
                definition=definition,
                benchmark=benchmark,
                observed_value=observed_value,
            )

            classification = evaluation.classification

            capacity_context: MetricCapacityContext | None = None
            if self._behaviour.profile_id in {
                CAPACITY_PRESSURE,
                CAPACITY_SATURATION,
                CAPACITY_RECOVERY,
            }:
                if self._capacity_profile is None:
                    raise ValueError(
                        "Capacity pressure behaviour requires "
                        "a Capacity profile."
                    )
                envelope = self._capacity_profile.metrics.get(
                    metric_id
                )
                if envelope is None:
                    raise ValueError(
                        "Capacity profile does not define Metric: "
                        f"{metric_id}"
                    )
                capacity_context = MetricCapacityContext(
                    capacity_profile_id=(
                        self._capacity_profile.profile_id
                    ),
                    classification=classify_capacity(
                        envelope,
                        observed_value=observed_value,
                    ),
                    direction=envelope.direction,
                    pressure_threshold=(
                        envelope.pressure_threshold
                    ),
                    saturation_threshold=(
                        envelope.saturation_threshold
                    ),
                )

            if (
                self._behaviour.profile_id
                == OPERATIONAL_WARNING
                and classification.value != "warning"
            ):
                raise ValueError(
                    "Operational warning Metric behaviour "
                    f"must produce a warning observation for {metric_id}."
                )

            if (
                self._behaviour.profile_id
                in {
                    DEGRADED_POST_CHANGE,
                    OPERATIONAL_DEGRADATION,
                }
                and classification.value != "blocking"
            ):
                raise ValueError(
                    "Degraded Metric behaviour must produce "
                    f"a blocking observation for {metric_id}."
                )

            if (
                self._behaviour.profile_id
                in {
                    RECOVERED_POST_ROLLBACK,
                    OPERATIONAL_RECOVERY,
                }
                and classification.value != "normal"
            ):
                raise ValueError(
                    "Recovered Metric behaviour requires "
                    f"a normal reference target for {metric_id}."
                )

            yield GeneratedEvent(
                event_id=self._ids.event_id(),
                event_type=METRIC_EVENT_TYPE,
                event_time=context.simulation_time,
                source_system=self.source_system,
                source_domain=self._behaviour.source,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                business_stream=context.business_stream,
                service=context.service,
                component=None,
                environment=context.environment,
                sequence_number=context.next_sequence(),
                data=build_metric_event_data(
                    definition=definition,
                    baseline=baseline,
                    benchmark=benchmark,
                    baseline_profile_id=(
                        self._baseline_profile.profile_id
                    ),
                    benchmark_profile_id=(
                        self._benchmark_profile_id
                    ),
                    behaviour_profile_id=(
                        self._behaviour.profile_id
                    ),
                    scenario_state=(
                        context.scenario_state
                    ),
                    observed_value=observed_value,
                    classification=classification,
                    evaluation_status=evaluation.status,
                    capacity_context=capacity_context,
                ),
            )

    def _generate_observation(
        self,
        *,
        baseline: MetricBaseline,
        benchmark: ResolvedBenchmark | None,
    ) -> float:
        if self._behaviour.profile_id in {
            CAPACITY_PRESSURE,
            CAPACITY_SATURATION,
        }:
            if self._capacity_profile is None:
                if (
                    self._behaviour.profile_id
                    == CAPACITY_PRESSURE
                ):
                    raise ValueError(
                        "Capacity pressure behaviour requires "
                        "a Capacity profile."
                    )
                raise ValueError(
                    "Capacity saturation behaviour requires "
                    "a Capacity profile."
                )
            envelope = self._capacity_profile.metrics.get(
                baseline.metric_definition_id
            )
            if envelope is None:
                raise ValueError(
                    "Capacity profile does not define Metric: "
                    f"{baseline.metric_definition_id}"
                )
            if (
                self._behaviour.profile_id
                == CAPACITY_PRESSURE
            ):
                return float(
                    envelope.pressure_threshold
                )
            return float(
                envelope.saturation_threshold
            )

        if (
            self._behaviour.profile_id
            == OPERATIONAL_WARNING
        ):
            return float(
                benchmark.warning_threshold
            )

        if (
            self._behaviour.profile_id
            in {
                DEGRADED_POST_CHANGE,
                OPERATIONAL_DEGRADATION,
            }
        ):
            return float(
                benchmark.blocking_threshold
            )

        if (
            self._behaviour.profile_id
            in {
                RECOVERED_POST_ROLLBACK,
                OPERATIONAL_RECOVERY,
            }
        ):
            return float(
                benchmark.reference_target
            )

        return self._sample_observation(
            baseline
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
        if (
            self._behaviour.profile_id
            == CAPACITY_PRESSURE
            and self._capacity_profile is None
        ):
            raise ValueError(
                "Capacity pressure behaviour requires "
                "a Capacity profile."
            )

        if (
            self._behaviour.profile_id
            == CAPACITY_SATURATION
            and self._capacity_profile is None
        ):
            raise ValueError(
                "Capacity saturation behaviour requires "
                "a Capacity profile."
            )

        if (
            self._behaviour.profile_id
            == CAPACITY_RECOVERY
            and self._capacity_profile is None
        ):
            raise ValueError(
                "Capacity recovery behaviour requires "
                "a Capacity profile."
            )

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

            if (
                self._behaviour.profile_id
                in {
                    CAPACITY_PRESSURE,
                    CAPACITY_SATURATION,
                    CAPACITY_RECOVERY,
                }
                and self._capacity_profile is not None
                and metric_id
                not in self._capacity_profile.metrics
            ):
                raise ValueError(
                    "Capacity profile does not define Metric: "
                    f"{metric_id}"
                )

            if (
                definition.direction
                == MetricDirection.CONTEXT_DEPENDENT
                and self._behaviour.profile_id
                in {
                    OPERATIONAL_WARNING,
                    OPERATIONAL_DEGRADATION,
                    DEGRADED_POST_CHANGE,
                    OPERATIONAL_RECOVERY,
                    RECOVERED_POST_ROLLBACK,
                }
            ):
                raise ValueError(
                    "Context-dependent Metric cannot use "
                    "threshold-driven behaviour."
                )

            benchmark = self._benchmarks.get(
                metric_id
            )


            if benchmark is None:
                if (
                    definition.direction
                    == MetricDirection.CONTEXT_DEPENDENT
                ):
                    continue
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