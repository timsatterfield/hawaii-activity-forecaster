"""Explicit local TOML and HAF_ environment loading, without service side effects."""

from collections.abc import Mapping
import os
from pathlib import Path
import tomllib

from pydantic import ValidationError

from .settings import AppConfig


class ConfigurationError(ValueError):
    """Configuration could not be loaded; the message excludes input values."""


# Keep application settings separate from provider/SDK environment variables.
_ENVIRONMENT_FIELDS = {
    "HAF_ENVIRONMENT_MODE": ("environment", "mode"),
    "HAF_LLM_ENABLED": ("llm", "enabled"),
    "HAF_LLM_PROVIDER": ("llm", "provider"),
    "HAF_LLM_MODEL_IDENTIFIER": ("llm", "model_identifier"),
    "HAF_LLM_PROFILE_ID": ("llm", "profile_id"),
    "HAF_LLM_ACTIVATION": ("llm", "activation"),
    "HAF_TRACE_DIRECTORY": ("trace", "directory"),
    "HAF_LANGSMITH_ENABLED": ("langsmith", "enabled"),
}
_BOOLEAN_VARIABLES = {"HAF_LLM_ENABLED", "HAF_LANGSMITH_ENABLED"}


def load_config(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load defaults < explicit TOML < known HAF_ variables, then validate.

    Relative trace directories are anchored to the TOML's containing directory,
    or the current working directory when no file is supplied. No directories,
    trace files, clients, or environment mutations are created here.
    """
    data: dict = {}
    base_directory = Path.cwd()
    if path is not None:
        try:
            config_path = Path(path).resolve()
            base_directory = config_path.parent
            with config_path.open("rb") as stream:
                data = tomllib.load(stream)
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            raise ConfigurationError("Invalid TOML configuration.") from None
        except (OSError, ValueError):
            raise ConfigurationError("Cannot read TOML configuration file.") from None

    environment = os.environ if environ is None else environ
    for variable in environment:
        if variable.startswith("HAF_") and variable not in _ENVIRONMENT_FIELDS:
            raise ConfigurationError("Unknown HAF_ configuration variable.")
    for variable, (section, field) in _ENVIRONMENT_FIELDS.items():
        if variable not in environment:
            continue
        value: object = environment[variable]
        if not isinstance(value, str):
            raise ConfigurationError("Configuration environment values must be strings.")
        if variable in _BOOLEAN_VARIABLES:
            normalized = value.casefold()
            if normalized not in ("true", "false"):
                raise ConfigurationError("Configuration boolean variables require true or false.")
            value = normalized == "true"
        table = data.setdefault(section, {})
        if not isinstance(table, dict):
            raise ConfigurationError("Configuration sections must be TOML tables.")
        table[field] = value

    try:
        config = AppConfig.model_validate(data)
    except ValidationError as error:
        # Do not echo user-supplied values (including misplaced credentials).
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors(include_input=False, include_context=False, include_url=False)
        )
        raise ConfigurationError(f"Invalid application configuration: {problems}") from None

    directory = config.trace.directory
    if not directory.is_absolute():
        directory = base_directory / directory
    # model_copy(update=...) bypasses Pydantic validation, so rebuild the config.
    validated = config.model_dump()
    validated["trace"]["directory"] = directory
    return AppConfig.model_validate(validated)
