from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)


class EnterpriseCatalogue:
    """
    Read-only catalogue of configured Enterprises.

    Enterprise configuration remains owned by
    the config/enterprises directory and the
    canonical Enterprise loader.
    """

    def __init__(
        self,
        root: str | Path,
    ) -> None:
        self._root = Path(root)

    def list_enterprises(
        self,
    ) -> tuple[Enterprise, ...]:
        if not self._root.exists():
            return ()

        enterprises = tuple(
            load_enterprise_configuration(
                directory
            )
            for directory in sorted(
                (
                    path
                    for path in self._root.iterdir()
                    if (
                        path.is_dir()
                        and (
                            path
                            / "enterprise.yaml"
                        ).exists()
                    )
                ),
                key=lambda path: path.name,
            )
        )

        return tuple(
            sorted(
                enterprises,
                key=lambda enterprise: (
                    enterprise.enterprise_id
                ),
            )
        )

    def get_enterprise(
        self,
        enterprise_id: str,
    ) -> Enterprise | None:
        for enterprise in (
            self.list_enterprises()
        ):
            if (
                enterprise.enterprise_id
                == enterprise_id
            ):
                return enterprise

        return None
