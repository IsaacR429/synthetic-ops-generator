from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise

from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)


class HistoricalChangeOutcome(StrEnum):
    SUCCESSFUL = "successful"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class HistoricalChangeCase:
    ordinal: int
    scenario_id: str
    run_id: str
    chg_id: str
    change_time: datetime
    outcome: HistoricalChangeOutcome

    def __post_init__(self) -> None:
        if self.ordinal <= 0:
            raise ValueError(
                "Historical Change ordinal "
                "must be greater than zero."
            )

        if not self.scenario_id:
            raise ValueError(
                "Historical Change scenario_id "
                "cannot be empty."
            )

        if not self.run_id:
            raise ValueError(
                "Historical Change run_id "
                "cannot be empty."
            )

        if not self.chg_id:
            raise ValueError(
                "Historical Change chg_id "
                "cannot be empty."
            )

        if (
            self.change_time.tzinfo is None
            or self.change_time.tzinfo.utcoffset(
                self.change_time
            )
            is None
        ):
            raise ValueError(
                "Historical Change time must be "
                "timezone-aware."
            )


@dataclass(frozen=True)
class HistoricalChangeHistory:
    history_id: str
    enterprise_id: str
    business_stream_id: str
    service_id: str
    changes: tuple[HistoricalChangeCase, ...]

    def __post_init__(self) -> None:
        if not self.history_id:
            raise ValueError(
                "Historical history_id "
                "cannot be empty."
            )

        if not self.enterprise_id:
            raise ValueError(
                "Historical enterprise_id "
                "cannot be empty."
            )

        if not self.business_stream_id:
            raise ValueError(
                "Historical business_stream_id "
                "cannot be empty."
            )

        if not self.service_id:
            raise ValueError(
                "Historical service_id "
                "cannot be empty."
            )

        if len(self.changes) < 2:
            raise ValueError(
                "Historical Change history "
                "requires at least two Changes."
            )

        expected_ordinals = tuple(
            range(
                1,
                len(self.changes) + 1,
            )
        )

        actual_ordinals = tuple(
            change.ordinal
            for change in self.changes
        )

        if actual_ordinals != expected_ordinals:
            raise ValueError(
                "Historical Change ordinals "
                "must be contiguous and begin at 1."
            )

        run_ids = [
            change.run_id
            for change in self.changes
        ]

        if len(set(run_ids)) != len(run_ids):
            raise ValueError(
                "Historical Change history "
                "contains duplicate Run IDs."
            )

        change_ids = [
            change.chg_id
            for change in self.changes
        ]

        if (
            len(set(change_ids))
            != len(change_ids)
        ):
            raise ValueError(
                "Historical Change history "
                "contains duplicate CHG IDs."
            )

        change_times = [
            change.change_time
            for change in self.changes
        ]

        for previous, current in pairwise(
            change_times
        ):
            if current <= previous:
                raise ValueError(
                    "Historical Changes must be "
                    "strictly chronological."
                )


@dataclass(frozen=True)
class HistoricalChangePlanEntry:
    """
    Describes one planned Change relative to
    the beginning of a historical period.

    Identity allocation is intentionally
    deferred until the history is built.
    """

    scenario_id: str
    offset: timedelta
    outcome: HistoricalChangeOutcome

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError(
                "Historical Change plan "
                "scenario_id cannot be empty."
            )

        if self.offset < timedelta(0):
            raise ValueError(
                "Historical Change offset "
                "cannot be negative."
            )


def build_historical_change_history(
    *,
    ids: IdFactory,
    enterprise_id: str,
    business_stream_id: str,
    service_id: str,
    start_time: datetime,
    entries: tuple[
        HistoricalChangePlanEntry,
        ...,
    ],
) -> HistoricalChangeHistory:
    if (
        start_time.tzinfo is None
        or start_time.utcoffset() is None
    ):
        raise ValueError(
            "Historical history start time "
            "must be timezone-aware."
        )

    if len(entries) < 2:
        raise ValueError(
            "Historical Change history plan "
            "requires at least two Changes."
        )

    previous_offset: timedelta | None = None

    for entry in entries:
        if (
            previous_offset is not None
            and entry.offset
            <= previous_offset
        ):
            raise ValueError(
                "Historical Change plan offsets "
                "must be strictly increasing."
            )

        previous_offset = entry.offset

    history_id = ids.history_id()

    changes = tuple(
        HistoricalChangeCase(
            ordinal=index,
            scenario_id=entry.scenario_id,
            run_id=ids.run_id(),
            chg_id=ids.change_id(),
            change_time=(
                start_time
                + entry.offset
            ),
            outcome=entry.outcome,
        )
        for index, entry in enumerate(
            entries,
            start=1,
        )
    )

    return HistoricalChangeHistory(
        history_id=history_id,
        enterprise_id=enterprise_id,
        business_stream_id=(
            business_stream_id
        ),
        service_id=service_id,
        changes=changes,
    )
