from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.domain.enums import Industry


def test_bank_alpha_configuration_loads() -> None:
    enterprise = load_enterprise_configuration("config/enterprises/bank_alpha")

    assert enterprise.enterprise_id == "bank_alpha"
    assert enterprise.industry == Industry.BANKING
    assert len(enterprise.business_streams) == 5
    assert len(enterprise.services) == 5
    assert len(enterprise.components) == 9
    assert len(enterprise.sites) == 2
    assert len(enterprise.service_instances) == 4
    assert len(enterprise.dependencies) == 5


def test_insurer_alpha_configuration_loads() -> None:
    enterprise = load_enterprise_configuration("config/enterprises/insurer_alpha")

    assert enterprise.enterprise_id == "insurer_alpha"
    assert enterprise.industry == Industry.INSURANCE
    assert len(enterprise.business_streams) == 6
    assert len(enterprise.services) == 5
    assert len(enterprise.components) == 6
    assert len(enterprise.sites) == 2
    assert len(enterprise.service_instances) == 4
    assert len(enterprise.dependencies) == 3
