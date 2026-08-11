from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.operational_log import (
    LogSeverity,
    OperationalLog,
)


def build_log() -> OperationalLog:
    return OperationalLog(
        log_id="LOG0000001",
        chg_id="CHG0000001",
        log_type="request_completed",
        severity=LogSeverity.INFO,
        message="Payment request completed successfully.",
        service="payment_service",
        component="payment_api",
        timestamp=datetime(
            2026,
            8,
            11,
            12,
            0,
            tzinfo=UTC,
        ),
        attributes={
            "http_status": 200,
        },
    )


def test_operational_log_accepts_valid_data() -> None:
    log = build_log()

    assert log.log_id == "LOG0000001"
    assert log.chg_id == "CHG0000001"
    assert log.severity == LogSeverity.INFO


def test_operational_log_supports_component_scope() -> None:
    log = build_log()

    assert log.service == "payment_service"
    assert log.component == "payment_api"


def test_operational_log_supports_structured_attributes() -> None:
    log = build_log()

    assert log.attributes["http_status"] == 200


def test_operational_log_supports_optional_error_code() -> None:
    log = OperationalLog(
        log_id="LOG0000002",
        chg_id="CHG0000001",
        log_type="dependency_timeout",
        severity=LogSeverity.ERROR,
        message="Database dependency timed out.",
        service="payment_service",
        component="payment_api",
        timestamp=datetime(
            2026,
            8,
            11,
            12,
            0,
            tzinfo=UTC,
        ),
        error_code="DB_TIMEOUT",
    )

    assert log.error_code == "DB_TIMEOUT"


def test_operational_log_rejects_naive_timestamp() -> None:
    naive_timestamp = datetime(
        2026,
        8,
        11,
        12,
        0,
        tzinfo=UTC,
    ).replace(tzinfo=None)

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        OperationalLog(
            log_id="LOG0000001",
            chg_id="CHG0000001",
            log_type="request_completed",
            severity=LogSeverity.INFO,
            message="Request completed.",
            service="payment_service",
            timestamp=naive_timestamp,
        )


def test_operational_log_allows_service_level_log() -> None:
    log = OperationalLog(
        log_id="LOG0000001",
        chg_id="CHG0000001",
        log_type="service_health",
        severity=LogSeverity.INFO,
        message="Service operating normally.",
        service="payment_service",
        component=None,
        timestamp=datetime(
            2026,
            8,
            11,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    assert log.component is None