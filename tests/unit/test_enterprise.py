from synthetic_ops_generator.domain.enterprise import Enterprise, Service
from synthetic_ops_generator.domain.enums import Criticality, Industry


def test_enterprise_collections_are_independent() -> None:
    first = Enterprise(
        enterprise_id="ENT001",
        name="Bank Alpha",
        industry=Industry.BANKING,
    )

    second = Enterprise(
        enterprise_id="ENT002",
        name="Insurer Alpha",
        industry=Industry.INSURANCE,
    )

    first.services.append(
        Service(
            service_id="SVC001",
            name="Payment Service",
            business_stream_id="payments",
            owner="Payments Team",
            criticality=Criticality.CRITICAL,
        )
    )

    assert len(first.services) == 1
    assert len(second.services) == 0