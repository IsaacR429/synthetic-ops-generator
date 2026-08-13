import json

from synthetic_ops_generator.events.envelope import GeneratedEvent


def serialize_generated_event(
    event: GeneratedEvent,
) -> bytes:
    """
    Serialize a GeneratedEvent into deterministic UTF-8 JSON bytes.

    The canonical GeneratedEvent model remains the source of truth.
    Serialization does not add, remove, or reinterpret event fields.
    """

    payload = event.model_dump(
        mode="json",
    )

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def deserialize_generated_event(
    payload: bytes,
) -> GeneratedEvent:
    """
    Deserialize UTF-8 JSON bytes into a validated GeneratedEvent.
    """

    data = json.loads(
        payload.decode("utf-8")
    )

    return GeneratedEvent.model_validate(data)