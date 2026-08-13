import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    deserialize_generated_event,
    serialize_generated_event,
)


def make_event() -> GeneratedEvent:
    return GeneratedEvent(
        event_id="EVT0000001",
        event_type="metric.observed",
        event_time=datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        ),
        source_system="synthetic_observability",
        scenario_id="BANK-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=1,
        data={
            "metric": {
                "metric_id": "request_latency",
                "value": 180.5,
                "unit": "ms",
                "message": "Nominal opération",
            }
        },
    )


def test_serializes_generated_event_to_utf8_json_bytes() -> None:
    event = make_event()

    payload = serialize_generated_event(event)

    assert isinstance(payload, bytes)

    decoded = json.loads(
        payload.decode("utf-8")
    )

    assert decoded["event_id"] == "EVT0000001"
    assert decoded["event_type"] == "metric.observed"
    assert decoded["schema_version"] == "1.0"
    assert decoded["environment"] == "production"
    assert decoded["sequence_number"] == 1
    assert decoded["synthetic"] is True

    assert (
        decoded["data"]["metric"]["message"]
        == "Nominal opération"
    )


def test_serialization_is_deterministic() -> None:
    event = make_event()

    first = serialize_generated_event(event)
    second = serialize_generated_event(event)

    assert first == second


def test_serialization_uses_compact_canonical_json() -> None:
    event = make_event()

    payload = serialize_generated_event(event)

    decoded = payload.decode("utf-8")

    assert ": " not in decoded
    assert ", " not in decoded

    parsed = json.loads(decoded)

    assert parsed == event.model_dump(
        mode="json"
    )


def test_serialization_round_trip_preserves_event() -> None:
    original = make_event()

    payload = serialize_generated_event(original)

    restored = deserialize_generated_event(
        payload
    )

    assert restored == original


def test_deserialization_validates_event_contract() -> None:
    invalid_payload = json.dumps(
        {
            "event_id": "",
            "event_type": "test.event",
            "event_time": "2026-08-13T10:00:00+00:00",
            "source_system": "synthetic_test",
            "scenario_id": "TEST-01",
            "run_id": "RUN0000001",
            "sequence_number": 1,
        }
    ).encode("utf-8")

    with pytest.raises(ValidationError):
        deserialize_generated_event(
            invalid_payload
        )