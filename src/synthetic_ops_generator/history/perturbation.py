from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from synthetic_ops_generator.benchmarks.evaluator import (
    MetricEvaluationError,
    classify_metric,
)
from synthetic_ops_generator.benchmarks.models import (
    ResolvedBenchmark,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
    MetricDirection,
)


class PerturbationPhase(str, Enum):
    DEGRADATION = "degradation"
    PLATEAU = "plateau"
    RECOVERY = "recovery"


@dataclass(frozen=True)
class PerturbationCurveSpec:
    degradation_samples: int
    plateau_samples: int = 0
    recovery_samples: int = 0

    def __post_init__(self) -> None:
        if self.degradation_samples <= 0:
            raise ValueError(
                "degradation_samples must be "
                "greater than zero."
            )

        if self.plateau_samples < 0:
            raise ValueError(
                "plateau_samples cannot be negative."
            )

        if self.recovery_samples < 0:
            raise ValueError(
                "recovery_samples cannot be negative."
            )


@dataclass(frozen=True)
class PerturbationPoint:
    sample_index: int
    phase: PerturbationPhase
    strength: float


@dataclass(frozen=True)
class PerturbationCurve:
    points: tuple[PerturbationPoint, ...]


@dataclass(frozen=True)
class TimestampedPerturbationPoint:
    sample_index: int
    timestamp: datetime

    phase: PerturbationPhase
    strength: float


@dataclass(frozen=True)
class TimestampedPerturbationCurve:
    anchor_time: datetime
    sample_interval_seconds: int

    points: tuple[
        TimestampedPerturbationPoint,
        ...,
    ]


@dataclass(frozen=True)
class MetricPerturbationPoint:
    sample_index: int
    phase: PerturbationPhase
    strength: float

    healthy_value: float
    perturbed_value: float

    classification: MetricClassification


@dataclass(frozen=True)
class MetricPerturbationSeries:
    metric_definition_id: str

    points: tuple[
        MetricPerturbationPoint,
        ...,
    ]


def build_perturbation_curve(
    *,
    spec: PerturbationCurveSpec,
) -> PerturbationCurve:
    points: list[PerturbationPoint] = []

    for degradation_index in range(
        1,
        spec.degradation_samples + 1,
    ):
        strength = (
            degradation_index
            / spec.degradation_samples
        )

        points.append(
            PerturbationPoint(
                sample_index=len(points),
                phase=(
                    PerturbationPhase.DEGRADATION
                ),
                strength=float(strength),
            )
        )

    for _ in range(
        spec.plateau_samples
    ):
        points.append(
            PerturbationPoint(
                sample_index=len(points),
                phase=PerturbationPhase.PLATEAU,
                strength=1.0,
            )
        )

    if spec.recovery_samples > 0:
        for recovery_index in range(
            1,
            spec.recovery_samples + 1,
        ):
            strength = (
                1.0
                - (
                    recovery_index
                    / spec.recovery_samples
                )
            )

            points.append(
                PerturbationPoint(
                    sample_index=len(points),
                    phase=(
                        PerturbationPhase.RECOVERY
                    ),
                    strength=float(strength),
                )
            )

    return PerturbationCurve(
        points=tuple(points)
    )


def anchor_perturbation_curve(
    *,
    curve: PerturbationCurve,
    anchor_time: datetime,
    sample_interval_seconds: int,
) -> TimestampedPerturbationCurve:
    if (
        anchor_time.tzinfo is None
        or anchor_time.utcoffset() is None
    ):
        raise ValueError(
            "Perturbation anchor time must be "
            "timezone-aware."
        )

    if sample_interval_seconds <= 0:
        raise ValueError(
            "Perturbation sample interval must "
            "be greater than zero."
        )

    points = tuple(
        TimestampedPerturbationPoint(
            sample_index=point.sample_index,
            timestamp=(
                anchor_time
                + timedelta(
                    seconds=(
                        (
                            point.sample_index
                            + 1
                        )
                        * sample_interval_seconds
                    )
                )
            ),
            phase=point.phase,
            strength=point.strength,
        )
        for point in curve.points
    )

    return TimestampedPerturbationCurve(
        anchor_time=anchor_time,
        sample_interval_seconds=(
            sample_interval_seconds
        ),
        points=points,
    )


def perturb_metric_value(
    *,
    healthy_value: float,
    incident_target: float,
    strength: float,
) -> float:
    if not 0.0 <= strength <= 1.0:
        raise ValueError(
            "Perturbation strength must be "
            "between zero and one."
        )

    return float(
        healthy_value
        + strength
        * (
            incident_target
            - healthy_value
        )
    )


def validate_metric_perturbation_target(
    *,
    definition: MetricDefinition,
    benchmark: ResolvedBenchmark,
    healthy_value: float,
) -> None:
    if (
        definition.metric_definition_id
        != benchmark.metric_definition_id
    ):
        raise ValueError(
            "Metric Definition and resolved "
            "Benchmark must reference the "
            "same metric."
        )

    if (
        definition.direction
        == MetricDirection.CONTEXT_DEPENDENT
    ):
        raise MetricEvaluationError(
            "Context-dependent metrics cannot "
            "use standard historical "
            "perturbation evaluation."
        )

    healthy_classification = classify_metric(
        definition,
        benchmark,
        healthy_value,
    )

    if (
        healthy_classification
        != MetricClassification.NORMAL
    ):
        raise ValueError(
            "Historical perturbation must "
            "start from a normal healthy value."
        )

    target_classification = classify_metric(
        definition,
        benchmark,
        benchmark.blocking_threshold,
    )

    if (
        target_classification
        != MetricClassification.BLOCKING
    ):
        raise ValueError(
            "Historical perturbation incident "
            "target must classify as blocking."
        )


def build_metric_perturbation_series(
    *,
    definition: MetricDefinition,
    benchmark: ResolvedBenchmark,
    healthy_value: float,
    curve: PerturbationCurve,
) -> MetricPerturbationSeries:
    validate_metric_perturbation_target(
        definition=definition,
        benchmark=benchmark,
        healthy_value=healthy_value,
    )

    points: list[
        MetricPerturbationPoint
    ] = []

    for curve_point in curve.points:
        perturbed_value = perturb_metric_value(
            healthy_value=healthy_value,
            incident_target=(
                benchmark.blocking_threshold
            ),
            strength=curve_point.strength,
        )

        classification = classify_metric(
            definition,
            benchmark,
            perturbed_value,
        )

        points.append(
            MetricPerturbationPoint(
                sample_index=(
                    curve_point.sample_index
                ),
                phase=curve_point.phase,
                strength=curve_point.strength,
                healthy_value=healthy_value,
                perturbed_value=(
                    perturbed_value
                ),
                classification=classification,
            )
        )

    return MetricPerturbationSeries(
        metric_definition_id=(
            definition.metric_definition_id
        ),
        points=tuple(points),
    )
