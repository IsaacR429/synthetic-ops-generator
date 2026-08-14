from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from synthetic_ops_generator.api.routes.health import (
    router as health_router,
)
from synthetic_ops_generator.api.routes.runs import (
    router as runs_router,
)
from synthetic_ops_generator.api.routes.scenarios import (
    router as scenarios_router,
)
from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)
from synthetic_ops_generator.control.service import (
    ControlService,
    ExecutionPublisherFactory,
)
from synthetic_ops_generator.control.sqlite_run_store import (
    SQLiteRunStore,
)
from synthetic_ops_generator.core.sqlite_identifiers import (
    SQLiteIdFactory,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.history.executor import (
    HistoricalRunExecutor,
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

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CONFIG_ROOT = PROJECT_ROOT / "config"

DEFAULT_DATA_ROOT = (
    PROJECT_ROOT
    / "data"
    / "runs"
)


def create_app(
    *,
    config_root: str | Path = DEFAULT_CONFIG_ROOT,
    data_root: str | Path = DEFAULT_DATA_ROOT,
    event_interval_seconds: float = 5.0,
    execution_publisher_factory: (
        ExecutionPublisherFactory | None
    ) = None,
) -> FastAPI:
    config_root_path = Path(config_root)
    data_root_path = Path(data_root)

    catalogue = ScenarioCatalogue(
        config_root_path / "scenarios"
    )

    generator_factory = GeneratorFactory(
        config_root=config_root_path
    )

    historical_run_executor = (
        HistoricalRunExecutor(
            config_root=config_root_path
        )
    )

    @asynccontextmanager
    async def lifespan(
        app: FastAPI,
    ) -> AsyncIterator[None]:
        store = SQLiteEventStore(
            database_path=(
                data_root_path
                / "events.sqlite3"
            )
        )

        await store.start()

        run_store = SQLiteRunStore(
            database_path=(
                data_root_path
                / "runs.sqlite3"
            )
        )

        await run_store.start()

        ids = SQLiteIdFactory(
            database_path=(
                data_root_path
                / "identifiers.sqlite3"
            )
        )

        replay_publisher = InMemoryPublisher()

        active_run_manager = ActiveRunManager()

        app.state.event_store = store
        app.state.run_store = run_store
        app.state.replay_publisher = (
            replay_publisher
        )
        app.state.active_run_manager = (
            active_run_manager
        )

        control_service = ControlService(
            catalogue=catalogue,
            enterprise_root=(
                config_root_path
                / "enterprises"
            ),
            generator_factory=generator_factory,
            ids=ids,
            store=store,
            run_store=run_store,
            replay_publisher=replay_publisher,
            active_run_manager=active_run_manager,
            execution_publisher_factory=(
                execution_publisher_factory
            ),
            historical_run_executor=(
                historical_run_executor
            ),
            event_interval_seconds=(
                event_interval_seconds
            ),
        )

        await control_service.reconcile_orphaned_runs()

        app.state.control_service = (
            control_service
        )

        try:
            yield
        finally:
            await active_run_manager.shutdown()
            await run_store.stop()
            await store.stop()

    app = FastAPI(
        title=(
            "Synthetic Operational Data Generator "
            "Control API"
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.scenario_catalogue = catalogue

    app.include_router(health_router)
    app.include_router(scenarios_router)
    app.include_router(runs_router)

    return app


app = create_app()