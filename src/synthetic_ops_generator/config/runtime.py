from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioFrequencyOverride,
)


class RuntimeMode(StrEnum):
    REAL_TIME = "real_time"
    ACCELERATED = "accelerated"


class RuntimeTimingConfiguration(BaseModel):
    mode: RuntimeMode
    speed_multiplier: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_mode(
        self,
    ) -> "RuntimeTimingConfiguration":
        if (
            self.mode == RuntimeMode.REAL_TIME
            and self.speed_multiplier != 1.0
        ):
            raise ValueError(
                "Real-time runtime requires "
                "speed_multiplier=1.0."
            )

        return self

    def wall_clock_seconds(
        self,
        simulated_seconds: float,
    ) -> float:
        if simulated_seconds < 0:
            raise ValueError(
                "Simulated duration cannot be negative."
            )

        return (
            simulated_seconds
            / self.speed_multiplier
        )


class IntervalFrequencyConfiguration(BaseModel):
    interval_seconds: float = Field(gt=0)


class LogFrequencyConfiguration(BaseModel):
    normal_per_second: float = Field(gt=0)
    warning_per_second: float = Field(gt=0)
    failure_per_second: float = Field(gt=0)


class SourceFrequencyConfiguration(BaseModel):
    metrics: IntervalFrequencyConfiguration
    logs: LogFrequencyConfiguration
    infrastructure_tests: (
        IntervalFrequencyConfiguration
    )


class GeneratorRuntimeConfiguration(BaseModel):
    runtime: RuntimeTimingConfiguration
    frequency: SourceFrequencyConfiguration


def load_generator_runtime_configuration(
    *,
    config_root: str | Path,
) -> GeneratorRuntimeConfiguration:
    root = Path(config_root)

    return load_yaml_model(
        root / "global" / "defaults.yaml",
        GeneratorRuntimeConfiguration,
    )


def resolve_source_frequency_configuration(
    *,
    defaults: SourceFrequencyConfiguration,
    override: ScenarioFrequencyOverride | None = None,
) -> SourceFrequencyConfiguration:
    if override is None:
        return SourceFrequencyConfiguration(
            metrics=IntervalFrequencyConfiguration(
                interval_seconds=(
                    defaults.metrics.interval_seconds
                )
            ),
            logs=LogFrequencyConfiguration(
                normal_per_second=(
                    defaults.logs.normal_per_second
                ),
                warning_per_second=(
                    defaults.logs.warning_per_second
                ),
                failure_per_second=(
                    defaults.logs.failure_per_second
                ),
            ),
            infrastructure_tests=(
                IntervalFrequencyConfiguration(
                    interval_seconds=(
                        defaults.infrastructure_tests
                        .interval_seconds
                    )
                )
            ),
        )

    metrics_interval_seconds = (
        defaults.metrics.interval_seconds
    )

    if (
        override.metrics is not None
        and override.metrics.interval_seconds is not None
    ):
        metrics_interval_seconds = (
            override.metrics.interval_seconds
        )

    normal_logs_per_second = (
        defaults.logs.normal_per_second
    )
    warning_logs_per_second = (
        defaults.logs.warning_per_second
    )
    failure_logs_per_second = (
        defaults.logs.failure_per_second
    )

    if override.logs is not None:
        if (
            override.logs.normal_per_second
            is not None
        ):
            normal_logs_per_second = (
                override.logs.normal_per_second
            )

        if (
            override.logs.warning_per_second
            is not None
        ):
            warning_logs_per_second = (
                override.logs.warning_per_second
            )

        if (
            override.logs.failure_per_second
            is not None
        ):
            failure_logs_per_second = (
                override.logs.failure_per_second
            )

    infrastructure_test_interval_seconds = (
        defaults.infrastructure_tests
        .interval_seconds
    )

    if (
        override.infrastructure_tests
        is not None
        and override.infrastructure_tests
        .interval_seconds is not None
    ):
        infrastructure_test_interval_seconds = (
            override.infrastructure_tests
            .interval_seconds
        )

    return SourceFrequencyConfiguration(
        metrics=IntervalFrequencyConfiguration(
            interval_seconds=(
                metrics_interval_seconds
            )
        ),
        logs=LogFrequencyConfiguration(
            normal_per_second=(
                normal_logs_per_second
            ),
            warning_per_second=(
                warning_logs_per_second
            ),
            failure_per_second=(
                failure_logs_per_second
            ),
        ),
        infrastructure_tests=(
            IntervalFrequencyConfiguration(
                interval_seconds=(
                    infrastructure_test_interval_seconds
                )
            )
        ),
    )
