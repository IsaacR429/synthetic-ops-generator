from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)
from synthetic_ops_generator.control.configuration import (
    GenerationLifecycle,
)
from synthetic_ops_generator.control.models import (
    RunStatus,
)
from synthetic_ops_generator.control.service import (
    ControlService,
)
from synthetic_ops_generator.control.sqlite_run_store import (
    SQLiteRunStore,
)
from synthetic_ops_generator.core.sqlite_identifiers import (
    SQLiteIdFactory,
)
from synthetic_ops_generator.domain.enums import (
    SourceDomain,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)
from synthetic_ops_generator.retention.sqlite import (
    SQLiteEventStore,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"

EXPECTED_RESILIENCE_PROFILES = [
    "service_unavailable",
    "replication_observed",
    "failover_initiated",
    "traffic_switch_started",
    "traffic_switch_completed",
    "instance_activated",
    "service_available",
    "instance_serving",
    "service_available",
]


@pytest.mark.parametrize(
    (
        "scenario_id,"
        "primary_site,"
        "secondary_site,"
        "primary_instance,"
        "secondary_instance,"
        "replication_status,"
        "replication_offset_seconds"
    ),
    [
        (
            "BANK-06",
            "bank_primary",
            "bank_secondary",
            "payment_api_primary",
            "payment_api_secondary",
            "stopped",
            60,
        ),
        (
            "INS-06",
            "insurer_primary",
            "insurer_secondary",
            "claims_api_primary",
            "claims_api_secondary",
            "lagging",
            120,
        ),
    ],
)
@pytest.mark.asyncio
async def test_dr_scenarios_share_canonical_factual_runtime_contract(
    tmp_path: Path,
    scenario_id: str,
    primary_site: str,
    secondary_site: str,
    primary_instance: str,
    secondary_instance: str,
    replication_status: str,
    replication_offset_seconds: int,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    service = ControlService(
        catalogue=ScenarioCatalogue(
            CONFIG_ROOT / "scenarios"
        ),
        enterprise_root=(
            CONFIG_ROOT / "enterprises"
        ),
        generator_factory=GeneratorFactory(
            config_root=CONFIG_ROOT
        ),
        ids=SQLiteIdFactory(
            database_path=(
                tmp_path / "identifiers.sqlite3"
            )
        ),
        store=store,
        run_store=run_store,
        replay_publisher=InMemoryPublisher(),
        active_run_manager=ActiveRunManager(),
    )

    started = None

    try:
        started = await service.start_run(
            scenario_id=scenario_id,
            random_seed=42,
            generation_lifecycle=(
                GenerationLifecycle.CONTINUOUS
            ),
        )

        assert started.status == RunStatus.RUNNING

        resilience_events = []
        secondary_continuous_events = []

        for _ in range(40):
            await asyncio.sleep(0.1)

            live_record = await service.get_run(
                started.run_id
            )

            assert live_record is not None
            assert live_record.status != RunStatus.FAILED, (
                live_record.error_message
            )

            events = await store.get_run_events(
                started.run_id
            )

            resilience_events = sorted(
                (
                    event
                    for event in events
                    if (
                        event.source_domain
                        == SourceDomain.RESILIENCE
                    )
                ),
                key=lambda event: event.sequence_number,
            )

            secondary_continuous_events = [
                event
                for event in events
                if (
                    event.source_domain
                    in {
                        SourceDomain.METRIC,
                        SourceDomain.LOG,
                    }
                    and event.site_id
                    == secondary_site
                    and event.service_instance_id
                    == secondary_instance
                )
            ]

            secondary_sources = {
                event.source_domain
                for event in secondary_continuous_events
            }

            if (
                len(resilience_events) == 9
                and secondary_sources
                == {
                    SourceDomain.METRIC,
                    SourceDomain.LOG,
                }
            ):
                break
        else:
            pytest.fail(
                f"{scenario_id} did not produce the canonical "
                "bounded DR evidence and secondary continuous "
                "telemetry."
            )

        assert [
            event.data["behaviour_profile_id"]
            for event in resilience_events
        ] == EXPECTED_RESILIENCE_PROFILES

        primary_unavailable = resilience_events[0]
        replication = resilience_events[1]

        transition_events = resilience_events[2:5]

        secondary_activated = resilience_events[5]
        secondary_available = resilience_events[6]
        secondary_serving = resilience_events[7]

        primary_available_again = resilience_events[8]

        # ------------------------------------------
        # Primary factual availability loss
        # ------------------------------------------

        assert primary_unavailable.site_id == primary_site
        assert (
            primary_unavailable.service_instance_id
            == primary_instance
        )

        unavailable_observation = (
            primary_unavailable.data[
                "service_availability_observation"
            ]
        )

        assert (
            unavailable_observation["availability_state"]
            == "unavailable"
        )
        assert (
            unavailable_observation["site_id"]
            == primary_site
        )
        assert (
            unavailable_observation[
                "service_instance_id"
            ]
            == primary_instance
        )

        # ------------------------------------------
        # Scenario-specific replication fact
        # ------------------------------------------

        assert replication.site_id == primary_site
        assert (
            replication.service_instance_id
            == primary_instance
        )

        replication_observation = replication.data[
            "replication_observation"
        ]

        assert (
            replication_observation["from_site_id"]
            == primary_site
        )
        assert (
            replication_observation[
                "from_service_instance_id"
            ]
            == primary_instance
        )
        assert (
            replication_observation["to_site_id"]
            == secondary_site
        )
        assert (
            replication_observation[
                "to_service_instance_id"
            ]
            == secondary_instance
        )
        assert (
            replication_observation[
                "replication_status"
            ]
            == replication_status
        )

        observed_at = datetime.fromisoformat(
            replication_observation["observed_at"]
        )
        last_successful_at = datetime.fromisoformat(
            replication_observation[
                "last_successful_replication_at"
            ]
        )

        assert (
            observed_at - last_successful_at
            == timedelta(
                seconds=replication_offset_seconds
            )
        )

        # ------------------------------------------
        # Canonical failover transition facts
        # ------------------------------------------

        for event in transition_events:
            assert event.site_id == primary_site
            assert (
                event.service_instance_id
                == primary_instance
            )

            observation = event.data[
                "resilience_observation"
            ]

            assert (
                observation["from_site_id"]
                == primary_site
            )
            assert (
                observation[
                    "from_service_instance_id"
                ]
                == primary_instance
            )
            assert (
                observation["to_site_id"]
                == secondary_site
            )
            assert (
                observation[
                    "to_service_instance_id"
                ]
                == secondary_instance
            )

        # ------------------------------------------
        # Secondary activated + serving facts
        # ------------------------------------------

        for event in (
            secondary_activated,
            secondary_serving,
        ):
            assert event.site_id == secondary_site
            assert (
                event.service_instance_id
                == secondary_instance
            )

            observation = event.data[
                "resilience_observation"
            ]

            assert observation["from_site_id"] is None
            assert (
                observation[
                    "from_service_instance_id"
                ]
                is None
            )
            assert (
                observation["to_site_id"]
                == secondary_site
            )
            assert (
                observation[
                    "to_service_instance_id"
                ]
                == secondary_instance
            )

        # ------------------------------------------
        # Secondary factual availability
        # ------------------------------------------

        assert secondary_available.site_id == secondary_site
        assert (
            secondary_available.service_instance_id
            == secondary_instance
        )

        secondary_availability = secondary_available.data[
            "service_availability_observation"
        ]

        assert (
            secondary_availability[
                "availability_state"
            ]
            == "available"
        )
        assert (
            secondary_availability["site_id"]
            == secondary_site
        )
        assert (
            secondary_availability[
                "service_instance_id"
            ]
            == secondary_instance
        )

        # ------------------------------------------
        # Primary factual recovery availability
        # ------------------------------------------

        assert (
            primary_available_again.site_id
            == primary_site
        )
        assert (
            primary_available_again.service_instance_id
            == primary_instance
        )

        recovered_availability = (
            primary_available_again.data[
                "service_availability_observation"
            ]
        )

        assert (
            recovered_availability[
                "availability_state"
            ]
            == "available"
        )
        assert (
            recovered_availability["site_id"]
            == primary_site
        )
        assert (
            recovered_availability[
                "service_instance_id"
            ]
            == primary_instance
        )

        # ------------------------------------------
        # Continuous telemetry remains secondary
        # ------------------------------------------

        assert {
            event.source_domain
            for event in secondary_continuous_events
        } == {
            SourceDomain.METRIC,
            SourceDomain.LOG,
        }

        assert all(
            event.site_id == secondary_site
            and event.service_instance_id
            == secondary_instance
            for event in secondary_continuous_events
        )

        # ------------------------------------------
        # Resilience facts remain bounded
        # ------------------------------------------

        stopped = await service.stop_run(
            started.run_id
        )

        assert stopped.status == RunStatus.STOPPED

        final_events = await store.get_run_events(
            started.run_id
        )

        final_resilience_events = [
            event
            for event in final_events
            if (
                event.source_domain
                == SourceDomain.RESILIENCE
            )
        ]

        assert len(final_resilience_events) == 9

    finally:
        if started is not None:
            with suppress(Exception):
                await service.stop_run(
                    started.run_id
                )

        await run_store.stop()
        await store.stop()
