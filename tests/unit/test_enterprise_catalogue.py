from pathlib import Path

from synthetic_ops_generator.config.enterprise_catalogue import (
    EnterpriseCatalogue,
)

CONFIG_ROOT = Path("config")


def test_enterprise_catalogue_lists_configured_enterprises() -> None:
    catalogue = EnterpriseCatalogue(
        CONFIG_ROOT / "enterprises"
    )

    enterprises = (
        catalogue.list_enterprises()
    )

    assert tuple(
        enterprise.enterprise_id
        for enterprise in enterprises
    ) == (
        "bank_alpha",
        "insurer_alpha",
    )


def test_enterprise_catalogue_loads_enterprise_domain() -> None:
    catalogue = EnterpriseCatalogue(
        CONFIG_ROOT / "enterprises"
    )

    enterprise = (
        catalogue.get_enterprise(
            "bank_alpha"
        )
    )

    assert enterprise is not None
    assert (
        enterprise.enterprise_id
        == "bank_alpha"
    )

    assert enterprise.business_streams
    assert enterprise.services
    assert enterprise.components


def test_enterprise_catalogue_returns_none_for_unknown_enterprise() -> None:
    catalogue = EnterpriseCatalogue(
        CONFIG_ROOT / "enterprises"
    )

    assert (
        catalogue.get_enterprise(
            "unknown"
        )
        is None
    )
