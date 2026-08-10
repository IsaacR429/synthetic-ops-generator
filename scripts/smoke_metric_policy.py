from synthetic_ops_generator.benchmarks.evaluator import (
    classify_metric,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkCatalogue,
    BenchmarkOverride,
    BenchmarkScope,
)
from synthetic_ops_generator.benchmarks.resolver import (
    resolve_benchmark,
)
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.metrics.models import (
    MetricCatalogue,
)


def main() -> None:
    metrics = load_yaml_model(
        "config/metrics/definitions.yaml",
        MetricCatalogue,
    )

    benchmarks = load_yaml_model(
        "config/benchmarks/synthetic_defaults.yaml",
        BenchmarkCatalogue,
    )

    definition = metrics.definitions["request_latency"]

    profile = benchmarks.profiles[
        "critical_interactive_transaction"
    ]

    base_policy = profile.metrics["request_latency"]

    service_override = BenchmarkOverride(
        scope=BenchmarkScope.SERVICE,
        scope_id="payment_service",
        metric_definition_id="request_latency",
        reference_target=250,
        warning_threshold=400,
        blocking_threshold=700,
        reason="Synthetic Bank Alpha Payment Service policy.",
    )

    resolved = resolve_benchmark(
        definition,
        base_policy,
        [service_override],
    )

    observations = [
        180,
        450,
        920,
    ]

    print("Effective benchmark")
    print(resolved.model_dump_json(indent=2))

    print("\nObserved classifications")

    for observation in observations:
        result = classify_metric(
            definition,
            resolved,
            observation,
        )

        print(
            f"{observation} ms -> {result.value}"
        )


if __name__ == "__main__":
    main()