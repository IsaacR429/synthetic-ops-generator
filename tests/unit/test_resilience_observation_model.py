from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.domain.resilience import (
    ResilienceObservation,
    ResilienceObservationType,
)
from synthetic_ops_generator.scenarios.continuous_contract import (
    supports_continuous_execution,
)


OBSERVED_AT = datetime(
    2026,
    10,
    11,
    10,
    30,
    tzinfo=UTC,
)


def make_transition(
    observation_type: ResilienceObservationType,
) -> ResilienceObservation:
    return ResilienceObservation(
        observation_id="RSO0000001",
        observation_type=observation_type,
        service="payment_service",
        component="payment_api",
        from_site_id="bank_primary",
        from_service_instance_id="payment_api_primary",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=OBSERVED_AT,
    )


def make_target_observation(
    observation_type: ResilienceObservationType,
) -> ResilienceObservation:
    return ResilienceObservation(
        observation_id="RSO0000001",
        observation_type=observation_type,
        service="payment_service",
        component="payment_api",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=OBSERVED_AT,
    )


def test_resilience_is_first_class_source_domain() -> None:
    assert SourceDomain.RESILIENCE.value == "resilience"


def test_resilience_source_is_not_continuous_schedulable() -> None:
    assert (
        supports_continuous_execution(
            SourceDomain.RESILIENCE
        )
        is False
    )


@pytest.mark.parametrize(
    "observation_type",
    [
        ResilienceObservationType.FAILOVER_INITIATED,
        ResilienceObservationType.TRAFFIC_SWITCH_STARTED,
        ResilienceObservationType.TRAFFIC_SWITCH_COMPLETED,
    ],
)
def test_transition_observation_requires_distinct_source_and_target(
    observation_type: ResilienceObservationType,
) -> None:
    observation = make_transition(
        observation_type
    )

    assert (
        observation.from_service_instance_id
        == "payment_api_primary"
    )
    assert (
        observation.to_service_instance_id
        == "payment_api_secondary"
    )


@pytest.mark.parametrize(
    "observation_type",
    [
        ResilienceObservationType.INSTANCE_ACTIVATED,
        ResilienceObservationType.INSTANCE_SERVING,
    ],
)
def test_instance_state_observation_uses_target_endpoint_only(
    observation_type: ResilienceObservationType,
) -> None:
    observation = make_target_observation(
        observation_type
    )

    assert observation.from_site_id is None
    assert observation.from_service_instance_id is None
    assert observation.to_site_id == "bank_secondary"
    assert (
        observation.to_service_instance_id
        == "payment_api_secondary"
    )


def test_transition_observation_requires_source_endpoint() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Resilience transition observations require "
            "both source and destination endpoints"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.FAILOVER_INITIATED
            ),
            service="payment_service",
            to_site_id="bank_secondary",
            to_service_instance_id="payment_api_secondary",
            observed_at=OBSERVED_AT,
        )


def test_transition_observation_requires_destination_endpoint() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Resilience transition observations require "
            "both source and destination endpoints"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.TRAFFIC_SWITCH_STARTED
            ),
            service="payment_service",
            from_site_id="bank_primary",
            from_service_instance_id="payment_api_primary",
            observed_at=OBSERVED_AT,
        )


def test_transition_rejects_same_service_instance() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Resilience transition source and destination "
            "instances must differ"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.TRAFFIC_SWITCH_COMPLETED
            ),
            service="payment_service",
            from_site_id="bank_primary",
            from_service_instance_id="payment_api_primary",
            to_site_id="bank_primary",
            to_service_instance_id="payment_api_primary",
            observed_at=OBSERVED_AT,
        )


def test_source_endpoint_requires_site_and_instance() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Source resilience endpoint requires both "
            "site and service instance"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.FAILOVER_INITIATED
            ),
            service="payment_service",
            from_site_id="bank_primary",
            to_site_id="bank_secondary",
            to_service_instance_id="payment_api_secondary",
            observed_at=OBSERVED_AT,
        )


def test_destination_endpoint_requires_site_and_instance() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Destination resilience endpoint requires both "
            "site and service instance"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.INSTANCE_SERVING
            ),
            service="payment_service",
            to_service_instance_id="payment_api_secondary",
            observed_at=OBSERVED_AT,
        )


def test_instance_state_observation_rejects_source_endpoint() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Instance-state resilience observations "
            "cannot define a source endpoint"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.INSTANCE_ACTIVATED
            ),
            service="payment_service",
            from_site_id="bank_primary",
            from_service_instance_id="payment_api_primary",
            to_site_id="bank_secondary",
            to_service_instance_id="payment_api_secondary",
            observed_at=OBSERVED_AT,
        )


def test_resilience_observation_supports_service_level_scope() -> None:
    observation = ResilienceObservation(
        observation_id="RSO0000001",
        observation_type=(
            ResilienceObservationType.INSTANCE_SERVING
        ),
        service="payment_service",
        to_site_id="bank_secondary",
        to_service_instance_id="payment_api_secondary",
        observed_at=OBSERVED_AT,
    )

    assert observation.component is None


def test_resilience_observation_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Resilience observation timestamps "
            "must be timezone-aware"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.INSTANCE_SERVING
            ),
            service="payment_service",
            to_site_id="bank_secondary",
            to_service_instance_id="payment_api_secondary",
            observed_at=datetime(
                2026,
                10,
                11,
                10,
                30,
            ),
        )


def test_instance_state_observation_requires_destination_endpoint() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Instance-state resilience observations "
            "require a destination endpoint"
        ),
    ):
        ResilienceObservation(
            observation_id="RSO0000001",
            observation_type=(
                ResilienceObservationType.INSTANCE_ACTIVATED
            ),
            service="payment_service",
            observed_at=OBSERVED_AT,
        )


def test_transition_allows_same_site_with_distinct_instances() -> None:
    observation = ResilienceObservation(
        observation_id="RSO0000001",
        observation_type=(
            ResilienceObservationType.TRAFFIC_SWITCH_COMPLETED
        ),
        service="payment_service",
        from_site_id="bank_primary",
        from_service_instance_id="payment_api_a",
        to_site_id="bank_primary",
        to_service_instance_id="payment_api_b",
        observed_at=OBSERVED_AT,
    )

    assert (
        observation.from_service_instance_id
        != observation.to_service_instance_id
    )
    assert observation.from_site_id == observation.to_site_id
