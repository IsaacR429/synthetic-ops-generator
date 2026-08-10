from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

ModelT = TypeVar(
    "ModelT",
    bound=BaseModel,
)


class ConfigurationError(ValueError):
    pass


def load_yaml_model(
    path: str | Path,
    model_type: type[ModelT],
) -> ModelT:
    config_path = Path(path)

    if not config_path.exists():
        raise ConfigurationError(
            f"Configuration file not found: {config_path}"
        )

    try:
        with config_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            content = yaml.safe_load(file) or {}

        return model_type.model_validate(content)

    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Invalid YAML in {config_path}"
        ) from exc

    except ValidationError as exc:
        raise ConfigurationError(
            f"Configuration validation failed for {config_path}"
        ) from exc
