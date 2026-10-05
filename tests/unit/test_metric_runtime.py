from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.metrics.runtime import (
    resolve_metric_runtime_configuration,
)

CONFIG_ROOT = Path("config")


@pytest.mark.parametrize(
    (
        "enterprise_path",
        "service_id",
        "expected_baseline",
        "expected_benchmark",
    ),
    [
        (
            Path("config/enterprises/bank_alpha"),
            "payment_service",
            "payment_processing_nominal",
            "critical_interactive_transaction",
        ),
        (
            Path("config/enterprises/insurer_alpha"),
            "claims_service",
            "business_workflow_nominal",
            "business_critical_interactive",
        ),
    ],
)
def test_resolves_metric_runtime_configuration(
    enterprise_path: Path,
    service_id: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    enterprise = load_enterprise_configuration(
        enterprise_path
    )

    service = next(
        s for s in enterprise.services if s.service_id == service_id
    )

    runtime = (
        resolve_metric_runtime_configuration(
            service=service,
            config_root=CONFIG_ROOT,
        )
    )

    assert (
        runtime.baseline_profile.profile_id
        == expected_baseline
    )

    assert (
        runtime.benchmark_profile_id
        == expected_benchmark
    )

    assert set(
        runtime.resolved_benchmarks
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert set(
        runtime.resolved_benchmarks
    ).issubset(
        runtime.definitions
    )


def test_metric_runtime_requires_baseline_profile(
) -> None:
    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/bank_alpha"
        )
    )

    service = enterprise.services[0].model_copy(
        update={
            "baseline_profile_id": None
        }
    )

    with pytest.raises(
        ValueError,
        match="does not define a Baseline profile",
    ):
        resolve_metric_runtime_configuration(
            service=service,
            config_root=CONFIG_ROOT,
        )


def test_metric_runtime_requires_benchmark_profile(
) -> None:
    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/bank_alpha"
        )
    )

    service = enterprise.services[0].model_copy(
        update={
            "benchmark_profile_id": None
        }
    )

    with pytest.raises(
        ValueError,
        match="does not define a Benchmark profile",
    ):
        resolve_metric_runtime_configuration(
            service=service,
            config_root=CONFIG_ROOT,
        )


def test_runtime_allows_context_metric_without_benchmark(
    tmp_path: Path,
) -> None:
    metrics_directory = tmp_path / "metrics"
    metrics_directory.mkdir()
    (metrics_directory / "definitions.yaml").write_text(
        """
definitions:
  request_latency:
    metric_definition_id: request_latency
    name: Request Latency
    unit: ms
    evaluation_statistic: p95
    direction: lower_is_better
  throughput:
    metric_definition_id: throughput
    name: Throughput
    unit: requests_per_second
    evaluation_statistic: rate
    direction: context_dependent
""".strip(),
        encoding="utf-8",
    )

    baselines_directory = tmp_path / "baselines"
    baselines_directory.mkdir()
    (baselines_directory / "capacity_test.yaml").write_text(
        """
profile_id: capacity_test
name: Capacity Test Baseline
historical_window_minutes: 60
sample_interval_seconds: 60
metrics:
  request_latency:
    metric_definition_id: request_latency
    center: 180.0
    noise_stddev: 10.0
  throughput:
    metric_definition_id: throughput
    center: 800.0
    noise_stddev: 25.0
""".strip(),
        encoding="utf-8",
    )

    benchmarks_directory = tmp_path / "benchmarks"
    benchmarks_directory.mkdir()
    (
        benchmarks_directory
        / "synthetic_defaults.yaml"
    ).write_text(
        """
profiles:
  capacity_benchmark:
    profile_id: capacity_benchmark
    name: Capacity Benchmark
    workload_class: interactive_transactional
    criticality: critical
    metrics:
      request_latency:
        metric_definition_id: request_latency
        reference_target: 300
        warning_threshold: 500
        blocking_threshold: 1000
        provenance:
          source_id: test
          source_type: synthetic_reference
          source_name: Test
          version: "1.0"
          rationale: Test.
""".strip(),
        encoding="utf-8",
    )

    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )

    payment_service = next(
        service
        for service in enterprise.services
        if service.service_id == "payment_service"
    )

    service = payment_service.model_copy(
        update={
            "baseline_profile_id": "capacity_test",
            "benchmark_profile_id": "capacity_benchmark",
        }
    )

    runtime = resolve_metric_runtime_configuration(
        service=service,
        config_root=tmp_path,
    )

    assert set(runtime.definitions) == {
        "request_latency",
        "throughput",
    }
    assert set(runtime.baseline_profile.metrics) == {
        "request_latency",
        "throughput",
    }
    assert set(runtime.resolved_benchmarks) == {
        "request_latency",
    }
    assert "throughput" not in runtime.resolved_benchmarks


def test_runtime_rejects_directional_metric_without_benchmark(
    tmp_path: Path,
) -> None:
    metrics_directory = tmp_path / "metrics"
    metrics_directory.mkdir(exist_ok=True)
    (metrics_directory / "definitions.yaml").write_text(
        """
definitions:
  request_latency:
    metric_definition_id: request_latency
    name: Request Latency
    unit: ms
    evaluation_statistic: p95
    direction: lower_is_better
""".strip(),
        encoding="utf-8",
    )

    baselines_directory = tmp_path / "baselines"
    baselines_directory.mkdir(exist_ok=True)
    (baselines_directory / "directional_test.yaml").write_text(
        """
profile_id: directional_test
name: Directional Test Baseline
historical_window_minutes: 60
sample_interval_seconds: 60
metrics:
  request_latency:
    metric_definition_id: request_latency
    center: 180
    noise_stddev: 15
""".strip(),
        encoding="utf-8",
    )

    benchmarks_directory = tmp_path / "benchmarks"
    benchmarks_directory.mkdir(exist_ok=True)
    (
        benchmarks_directory
        / "synthetic_defaults.yaml"
    ).write_text(
        """
profiles:
  empty_benchmark:
    profile_id: empty_benchmark
    name: Empty Benchmark
    workload_class: interactive_transactional
    criticality: critical
    metrics: {}
""".strip(),
        encoding="utf-8",
    )

    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )

    payment_service = next(
        service
        for service in enterprise.services
        if service.service_id == "payment_service"
    )

    service = payment_service.model_copy(
        update={
            "baseline_profile_id": "directional_test",
            "benchmark_profile_id": "empty_benchmark",
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "Benchmark profile does not define Metric: "
            "request_latency"
        ),
    ):
        resolve_metric_runtime_configuration(
            service=service,
            config_root=tmp_path,
        )
