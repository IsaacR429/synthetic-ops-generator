from __future__ import annotations

from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.domain.enums import (
    AssetClass,
    MissionCriticality,
    ServiceClass,
)


ROOT = Path("config/enterprises")


def _load(name: str):
    return load_enterprise_configuration(
        ROOT / name
    )


def _service_map(enterprise):
    return {
        service.service_id: service
        for service in enterprise.services
    }


def _component_map(enterprise):
    return {
        component.component_id: component
        for component in enterprise.components
    }


def test_bank_existing_services_are_classified() -> None:
    enterprise = _load("bank_alpha")
    services = _service_map(enterprise)

    assert (
        services["payment_service"].service_class
        == ServiceClass.BUSINESS_APPLICATION
    )
    assert (
        services["payment_service"].mission_criticality
        == MissionCriticality.MISSION_CRITICAL
    )

    assert (
        services["identity_service"].service_class
        == ServiceClass.BUSINESS_SERVICE
    )

    assert (
        services["account_service"].service_class
        == ServiceClass.BUSINESS_SERVICE
    )

    assert (
        services["mobile_banking_service"].service_class
        == ServiceClass.BUSINESS_APPLICATION
    )

    assert (
        services["loan_service"].service_class
        == ServiceClass.BUSINESS_APPLICATION
    )


def test_insurer_existing_services_are_classified() -> None:
    enterprise = _load("insurer_alpha")
    services = _service_map(enterprise)

    assert (
        services["claims_service"].service_class
        == ServiceClass.BUSINESS_APPLICATION
    )
    assert (
        services["claims_service"].mission_criticality
        == MissionCriticality.MISSION_CRITICAL
    )

    assert (
        services["claims_payment_service"].service_class
        == ServiceClass.BUSINESS_SERVICE
    )

    assert (
        services["broker_portal"].service_class
        == ServiceClass.BUSINESS_APPLICATION
    )

    assert (
        services["policy_service"].service_class
        == ServiceClass.BUSINESS_APPLICATION
    )

    assert (
        services["document_service"].service_class
        == ServiceClass.BUSINESS_SERVICE
    )


def test_existing_database_and_application_components_are_classified() -> None:
    bank = _component_map(
        _load("bank_alpha")
    )
    insurer = _component_map(
        _load("insurer_alpha")
    )

    assert (
        bank["payment_database"].asset_class
        == AssetClass.DATABASE
    )
    assert (
        bank["identity_database"].asset_class
        == AssetClass.DATABASE
    )
    assert (
        bank["account_database"].asset_class
        == AssetClass.DATABASE
    )
    assert (
        insurer["claims_database"].asset_class
        == AssetClass.DATABASE
    )

    for component_id in (
        "payment_api",
        "authentication_api",
        "account_api",
        "mobile_api",
        "loan_api",
    ):
        assert (
            bank[component_id].asset_class
            == AssetClass.APPLICATION
        )

    for component_id in (
        "claims_api",
        "claims_payment_api",
        "broker_web",
        "policy_api",
        "document_worker",
    ):
        assert (
            insurer[component_id].asset_class
            == AssetClass.APPLICATION
        )


def test_both_enterprises_expose_enterprise_infrastructure_stream() -> None:
    for name in (
        "bank_alpha",
        "insurer_alpha",
    ):
        enterprise = _load(name)

        streams = {
            stream.stream_id
            for stream in enterprise.business_streams
        }

        assert (
            "enterprise_infrastructure"
            in streams
        )


def test_bank_exposes_full_infrastructure_asset_taxonomy() -> None:
    enterprise = _load("bank_alpha")
    services = _service_map(enterprise)
    components = _component_map(enterprise)

    infrastructure_services = [
        service
        for service in enterprise.services
        if (
            service.service_class
            == ServiceClass.INFRASTRUCTURE_SERVICE
        )
    ]

    assert infrastructure_services

    for service in infrastructure_services:
        assert (
            service.business_stream_id
            == "enterprise_infrastructure"
        )

    present = {
        component.asset_class
        for component in components.values()
        if component.asset_class is not None
    }

    assert {
        AssetClass.DATABASE,
        AssetClass.MIDDLEWARE,
        AssetClass.LINUX,
        AssetClass.WINDOWS,
        AssetClass.MAINFRAME,
        AssetClass.NETWORK,
        AssetClass.DIGITAL_INFRASTRUCTURE,
        AssetClass.INFORMATION_SECURITY,
    }.issubset(present)


def test_insurer_exposes_full_infrastructure_asset_taxonomy() -> None:
    enterprise = _load("insurer_alpha")
    services = _service_map(enterprise)
    components = _component_map(enterprise)

    infrastructure_services = [
        service
        for service in enterprise.services
        if (
            service.service_class
            == ServiceClass.INFRASTRUCTURE_SERVICE
        )
    ]

    assert infrastructure_services

    for service in infrastructure_services:
        assert (
            service.business_stream_id
            == "enterprise_infrastructure"
        )

    present = {
        component.asset_class
        for component in components.values()
        if component.asset_class is not None
    }

    assert {
        AssetClass.DATABASE,
        AssetClass.MIDDLEWARE,
        AssetClass.LINUX,
        AssetClass.WINDOWS,
        AssetClass.MAINFRAME,
        AssetClass.NETWORK,
        AssetClass.DIGITAL_INFRASTRUCTURE,
        AssetClass.INFORMATION_SECURITY,
    }.issubset(present)


def test_catalogues_have_complete_assurance_classification() -> None:
    for name in (
        "bank_alpha",
        "insurer_alpha",
    ):
        enterprise = _load(name)

        assert enterprise.services
        assert enterprise.components

        for service in enterprise.services:
            assert service.service_class is not None
            assert service.mission_criticality is not None

        for component in enterprise.components:
            assert component.asset_class is not None


def test_business_services_depend_on_shared_infrastructure() -> None:
    for name in (
        "bank_alpha",
        "insurer_alpha",
    ):
        enterprise = _load(name)

        service_by_component = {
            component.component_id: component.service_id
            for component in enterprise.components
        }

        infrastructure_service_ids = {
            service.service_id
            for service in enterprise.services
            if (
                service.service_class
                == ServiceClass.INFRASTRUCTURE_SERVICE
            )
        }

        assert infrastructure_service_ids

        cross_stream_dependencies = []

        for dependency in enterprise.dependencies:
            source_service = (
                dependency.source_id
                if dependency.source_id
                in {
                    service.service_id
                    for service in enterprise.services
                }
                else service_by_component.get(
                    dependency.source_id
                )
            )

            target_service = (
                dependency.target_id
                if dependency.target_id
                in {
                    service.service_id
                    for service in enterprise.services
                }
                else service_by_component.get(
                    dependency.target_id
                )
            )

            if (
                source_service is not None
                and target_service
                in infrastructure_service_ids
                and source_service
                not in infrastructure_service_ids
            ):
                cross_stream_dependencies.append(
                    dependency
                )

        assert cross_stream_dependencies
