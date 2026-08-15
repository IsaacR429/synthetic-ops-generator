from pathlib import Path

import pytest

from synthetic_ops_generator.config.loader import (
    ConfigurationError,
)
from synthetic_ops_generator.config.runtime import (
    RuntimeMode,
    RuntimeTimingConfiguration,
    load_generator_runtime_configuration,
    resolve_source_frequency_configuration,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioFrequencyOverride,
    ScenarioIntervalFrequencyOverride,
    ScenarioLogFrequencyOverride,
)


def write_defaults(
    directory: Path,
    content: str,
) -> Path:
    global_dir = directory / "global"
    global_dir.mkdir(parents=True, exist_ok=True)
    defaults_file = global_dir / "defaults.yaml"
    defaults_file.write_text(content.strip(), encoding="utf-8")
    return defaults_file


def test_load_generator_runtime_configuration(
    tmp_path: Path,
) -> None:
    write_defaults(
        tmp_path,
        """
runtime:
  mode: accelerated
  speed_multiplier: 12.0

frequency:
  metrics:
    interval_seconds: 5

  logs:
    normal_per_second: 2
    warning_per_second: 8
    failure_per_second: 25

  infrastructure_tests:
    interval_seconds: 60
""",
    )

    config = load_generator_runtime_configuration(
        config_root=tmp_path
    )

    assert config.runtime.mode == RuntimeMode.ACCELERATED
    assert config.runtime.speed_multiplier == 12.0
    assert config.frequency.metrics.interval_seconds == 5
    assert config.frequency.logs.normal_per_second == 2
    assert config.frequency.logs.warning_per_second == 8
    assert config.frequency.logs.failure_per_second == 25
    assert config.frequency.infrastructure_tests.interval_seconds == 60


def test_accelerated_runtime_converts_wall_clock_seconds() -> None:
    runtime = RuntimeTimingConfiguration(
        mode=RuntimeMode.ACCELERATED,
        speed_multiplier=12.0,
    )

    assert runtime.wall_clock_seconds(
        60
    ) == pytest.approx(5.0)

    assert runtime.wall_clock_seconds(
        5
    ) == pytest.approx(
        5 / 12
    )


def test_real_time_runtime_preserves_duration() -> None:
    runtime = RuntimeTimingConfiguration(
        mode=RuntimeMode.REAL_TIME,
        speed_multiplier=1.0,
    )

    assert runtime.wall_clock_seconds(
        5
    ) == pytest.approx(5.0)


def test_real_time_runtime_rejects_acceleration() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Real-time runtime requires "
            "speed_multiplier=1.0"
        ),
    ):
        RuntimeTimingConfiguration(
            mode=RuntimeMode.REAL_TIME,
            speed_multiplier=2.0,
        )


@pytest.mark.parametrize(
    "simulated_seconds",
    [
        -1.0,
        -0.1,
    ],
)
def test_runtime_rejects_negative_simulated_duration(
    simulated_seconds: float,
) -> None:
    runtime = RuntimeTimingConfiguration(
        mode=RuntimeMode.ACCELERATED,
        speed_multiplier=12.0,
    )

    with pytest.raises(
        ValueError,
        match=(
            "Simulated duration cannot be negative"
        ),
    ):
        runtime.wall_clock_seconds(
            simulated_seconds
        )


def test_runtime_configuration_rejects_invalid_frequency(
    tmp_path: Path,
) -> None:
    write_defaults(
        tmp_path,
        """
runtime:
  mode: accelerated
  speed_multiplier: 12.0

frequency:
  metrics:
    interval_seconds: 0

  logs:
    normal_per_second: 2
    warning_per_second: 8
    failure_per_second: 25

  infrastructure_tests:
    interval_seconds: 60
""",
    )

    with pytest.raises(
        ConfigurationError,
        match="Configuration validation failed",
    ):
        load_generator_runtime_configuration(
            config_root=tmp_path
        )


def test_scenario_frequency_override_supports_partial_fields() -> None:
    overridden = ScenarioFrequencyOverride(
        metrics=ScenarioIntervalFrequencyOverride(
            interval_seconds=2
        ),
        logs=ScenarioLogFrequencyOverride(
            warning_per_second=12
        ),
    )

    assert (
        overridden.metrics.interval_seconds
        == 2
    )

    assert (
        overridden.logs.warning_per_second
        == 12
    )

    assert (
        overridden.logs.normal_per_second
        is None
    )


def test_scenario_frequency_override_rejects_non_positive_values() -> None:
    with pytest.raises(ValueError):
        ScenarioIntervalFrequencyOverride(
            interval_seconds=0
        )

    with pytest.raises(ValueError):
        ScenarioLogFrequencyOverride(
            warning_per_second=-1
        )


def test_resolve_source_frequency_without_override_copies_defaults() -> None:
    configuration = (
        load_generator_runtime_configuration(
            config_root="config"
        )
    )

    resolved = (
        resolve_source_frequency_configuration(
            defaults=configuration.frequency,
            override=None,
        )
    )

    assert resolved == configuration.frequency
    assert resolved is not configuration.frequency


def test_resolve_source_frequency_applies_partial_scenario_override() -> None:
    configuration = (
        load_generator_runtime_configuration(
            config_root="config"
        )
    )

    override = ScenarioFrequencyOverride(
        metrics=(
            ScenarioIntervalFrequencyOverride(
                interval_seconds=2
            )
        ),
        logs=(
            ScenarioLogFrequencyOverride(
                warning_per_second=12
            )
        ),
    )

    resolved = (
        resolve_source_frequency_configuration(
            defaults=configuration.frequency,
            override=override,
        )
    )

    assert (
        resolved.metrics.interval_seconds
        == 2
    )

    assert (
        resolved.logs.normal_per_second
        == 2
    )

    assert (
        resolved.logs.warning_per_second
        == 12
    )

    assert (
        resolved.logs.failure_per_second
        == 25
    )

    assert (
        resolved.infrastructure_tests
        .interval_seconds
        == 60
    )
