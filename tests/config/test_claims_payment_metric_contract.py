from pathlib import Path

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkCatalogue,
)
from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.metrics.models import (
    MetricCatalogue,
    MetricDirection,
)
from synthetic_ops_generator.metrics.runtime import (
    resolve_metric_runtime_configuration,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


def _claims_payment_service():
    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "insurer_alpha"
    )

    return next(
        service
        for service in enterprise.services
        if (
            service.service_id
            == "claims_payment_service"
        )
    )


def test_queue_depth_is_a_canonical_metric() -> None:
    catalogue = load_yaml_model(
        CONFIG_ROOT
        / "metrics"
        / "definitions.yaml",
        MetricCatalogue,
    )

    definition = catalogue.definitions[
        "queue_depth"
    ]

    assert (
        definition.metric_definition_id
        == "queue_depth"
    )
    assert definition.name == "Queue Depth"
    assert (
        definition.direction
        == MetricDirection.LOWER_IS_BETTER
    )
    assert definition.aggregation_window_seconds > 0


def test_claims_payment_has_its_own_nominal_baseline() -> None:
    baseline = load_baseline_profile(
        "claims_payment_nominal",
        directory=CONFIG_ROOT / "baselines",
    )

    assert baseline.profile_id == (
        "claims_payment_nominal"
    )

    assert {
        "request_latency",
        "error_rate",
        "availability",
        "queue_depth",
    }.issubset(
        baseline.metrics
    )

    queue = baseline.metrics["queue_depth"]

    assert queue.center >= 0
    assert queue.noise_stddev >= 0

    if queue.lower_bound is not None:
        assert queue.lower_bound >= 0

    if queue.upper_bound is not None:
        assert queue.upper_bound >= queue.center


def test_critical_transaction_policy_covers_queue_depth() -> None:
    catalogue = load_yaml_model(
        CONFIG_ROOT
        / "benchmarks"
        / "synthetic_defaults.yaml",
        BenchmarkCatalogue,
    )

    profile = catalogue.profiles[
        "critical_interactive_transaction"
    ]

    policy = profile.metrics[
        "queue_depth"
    ]

    assert (
        policy.metric_definition_id
        == "queue_depth"
    )

    assert (
        policy.reference_target
        < policy.warning_threshold
        < policy.blocking_threshold
    )

    assert (
        policy.provenance.source_type.value
        == "synthetic_reference"
    )


def test_claims_payment_service_selects_claims_payment_baseline() -> None:
    service = _claims_payment_service()

    assert service.baseline_profile_id == (
        "claims_payment_nominal"
    )


def test_claims_payment_metric_runtime_resolves_queue_depth() -> None:
    service = _claims_payment_service()

    runtime = resolve_metric_runtime_configuration(
        service=service,
        config_root=CONFIG_ROOT,
    )

    assert "queue_depth" in runtime.definitions
    assert (
        "queue_depth"
        in runtime.baseline_profile.metrics
    )
    assert (
        "queue_depth"
        in runtime.resolved_benchmarks
    )

    assert (
        runtime.baseline_profile.profile_id
        == "claims_payment_nominal"
    )
    assert (
        runtime.benchmark_profile_id
        == "critical_interactive_transaction"
    )
