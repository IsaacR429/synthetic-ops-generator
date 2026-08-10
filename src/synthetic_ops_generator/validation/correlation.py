from synthetic_ops_generator.events.envelope import GeneratedEvent


class CorrelationValidationError(ValueError):
    pass


def validate_run_correlation(
    events: list[GeneratedEvent],
) -> None:
    if not events:
        return

    expected_scenario = events[0].scenario_id
    expected_run = events[0].run_id

    for event in events:
        if event.scenario_id != expected_scenario:
            raise CorrelationValidationError(
                f"Scenario mismatch in event {event.event_id}"
            )

        if event.run_id != expected_run:
            raise CorrelationValidationError(
                f"Run mismatch in event {event.event_id}"
            )


def validate_change_correlation(
    events: list[GeneratedEvent],
    expected_chg_id: str,
) -> None:
    for event in events:
        if event.chg_id is not None and event.chg_id != expected_chg_id:
            raise CorrelationValidationError(
                f"CHG mismatch in event {event.event_id}: "
                f"{event.chg_id} != {expected_chg_id}"
            )