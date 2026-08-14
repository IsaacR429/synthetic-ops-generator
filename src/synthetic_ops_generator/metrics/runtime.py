from dataclasses import dataclass
from pathlib import Path

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
)
from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkCatalogue,
    ResolvedBenchmark,
)
from synthetic_ops_generator.benchmarks.resolver import (
    resolve_benchmark,
)
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.domain.enterprise import (
    Service,
)
from synthetic_ops_generator.metrics.models import (
    MetricCatalogue,
    MetricDefinition,
)


@dataclass(frozen=True)
class MetricRuntimeConfiguration:
    definitions: dict[str, MetricDefinition]
    baseline_profile: BaselineProfile
    resolved_benchmarks: dict[str, ResolvedBenchmark]
    benchmark_profile_id: str


def resolve_metric_runtime_configuration(
    *,
    service: Service,
    config_root: str | Path,
) -> MetricRuntimeConfiguration:
    if service.benchmark_profile_id is None:
        raise ValueError(
            f"Service {service.service_id} does not define "
            "a Benchmark profile."
        )

    if service.baseline_profile_id is None:
        raise ValueError(
            f"Service {service.service_id} does not define "
            "a Baseline profile."
        )

    root = Path(config_root)

    metric_catalogue = load_yaml_model(
        root
        / "metrics"
        / "definitions.yaml",
        MetricCatalogue,
    )

    benchmark_catalogue = load_yaml_model(
        root
        / "benchmarks"
        / "synthetic_defaults.yaml",
        BenchmarkCatalogue,
    )

    baseline_profile = load_baseline_profile(
        service.baseline_profile_id,
        directory=root / "baselines",
    )

    benchmark_profile = (
        benchmark_catalogue.profiles.get(
            service.benchmark_profile_id
        )
    )

    if benchmark_profile is None:
        raise ValueError(
            "Configured Benchmark profile was not found: "
            f"{service.benchmark_profile_id}"
        )

    resolved_benchmarks: dict[
        str,
        ResolvedBenchmark,
    ] = {}

    for metric_id in baseline_profile.metrics:
        definition = (
            metric_catalogue.definitions.get(
                metric_id
            )
        )

        if definition is None:
            raise ValueError(
                "Baseline references unknown "
                "Metric Definition: "
                f"{metric_id}"
            )

        base_policy = (
            benchmark_profile.metrics.get(
                metric_id
            )
        )

        if base_policy is None:
            raise ValueError(
                "Benchmark profile does not define Metric: "
                f"{metric_id}"
            )

        resolved_benchmarks[
            metric_id
        ] = resolve_benchmark(
            definition,
            base_policy,
        )

    return MetricRuntimeConfiguration(
        definitions=dict(
            metric_catalogue.definitions
        ),
        baseline_profile=baseline_profile,
        resolved_benchmarks=(
            resolved_benchmarks
        ),
        benchmark_profile_id=(
            benchmark_profile.profile_id
        ),
    )
