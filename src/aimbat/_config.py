"""Global configuration options for the AIMBAT application."""

from aimbat._lib._mixins import EventParametersValidatorMixin
from aimbat.aimbat_types import PydanticNegativeTimedelta, PydanticPositiveTimedelta
from pysmo.tools.iccs._defaults import ICCS_DEFAULTS
from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pathlib import Path
from typing import Literal, Self
import numpy as np


class Settings(EventParametersValidatorMixin, BaseSettings):
    """Global configuration options for the AIMBAT application."""

    model_config = SettingsConfigDict(env_prefix="aimbat_", env_file=".env")

    project: Path = Field(
        default=Path("aimbat.db"),
        description="AIMBAT project file location (ignored if `db_url` is specified).",
    )
    """AIMBAT project file location."""

    db_url: str = Field(
        default="",
        description="AIMBAT database url (default value is derived from `project`).",
    )
    """AIMBAT database url (default is derived from `project`)."""

    logfile: Path = Field(default=Path("aimbat.log"), description="Log file location.")
    """Log file location."""

    log_level: Literal[
        "TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
    ] = Field(
        default="INFO",
        description=(
            "Logging level. "
            "Valid levels (from most to least verbose): "
            "TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL."
        ),
    )
    """Logging level.

    Valid loguru levels, from most to least verbose:

    - ``TRACE``
    - ``DEBUG``
    - ``INFO``
    - ``SUCCESS``
    - ``WARNING``
    - ``ERROR``
    - ``CRITICAL``
    """

    window_pre: PydanticNegativeTimedelta = Field(
        default=ICCS_DEFAULTS.window_pre,
        description="Initial relative begin time of window.",
    )
    """Initial relative begin time of window."""

    window_post: PydanticPositiveTimedelta = Field(
        default=ICCS_DEFAULTS.window_post,
        description="Initial relative end time of window.",
    )
    """Initial relative end time of window."""

    context_width: PydanticPositiveTimedelta = Field(
        default=ICCS_DEFAULTS.context_width,
        description="Context padding to apply before and after the time window.",
    )
    """Context padding to apply before and after the time window."""

    min_ccnorm: float | np.floating = Field(
        default=ICCS_DEFAULTS.min_ccnorm,
        ge=0,
        le=1,
        description="Initial minimum cross correlation coefficient.",
    )
    """Initial minimum cross correlation coefficient."""

    bandpass_apply: bool = Field(
        default=ICCS_DEFAULTS.bandpass_apply,
        description="Whether to apply bandpass filter to seismograms.",
    )
    """Whether to apply bandpass filter to seismograms."""

    bandpass_fmin: float = Field(
        default=ICCS_DEFAULTS.bandpass_fmin,
        ge=0,
        description="Minimum frequency for bandpass filter (ignored if `bandpass_apply` is False).",
    )
    """Minimum frequency for bandpass filter (ignored if `bandpass_apply` is False)."""

    bandpass_fmax: float = Field(
        default=ICCS_DEFAULTS.bandpass_fmax,
        gt=0,
        description="Maximum frequency for bandpass filter (ignored if `bandpass_apply` is False).",
    )
    """Maximum frequency for bandpass filter (ignored if `bandpass_apply` is False)."""

    sac_pick_header: str = Field(
        default="t0", description="SAC header field where initial pick is stored."
    )
    """SAC header field where initial pick is stored."""

    sampledata_src: str = Field(
        default="https://github.com/pysmo/data-example/archive/refs/heads/aimbat_v2.zip",
        description="URL where sample data is downloaded from.",
    )
    """URL where sample data is downloaded from."""

    sampledata_dir: Path = Field(
        default=Path("sample-data"),
        description="Directory to store downloaded sample data.",
    )
    """Directory to store downloaded sample data."""

    min_id_length: int = Field(
        default=2, ge=1, description="Minimum length of ID string."
    )
    """Minimum length of truncated UUID string."""

    @model_validator(mode="after")
    def set_computed_defaults(self) -> Self:
        """Sets defaults that depend on other fields."""
        # 1. Handle db_url dependency on project
        if self.db_url == "":
            self.db_url = f"sqlite+pysqlite:///{self.project}"
        return self


settings = Settings()


def print_settings_table(pretty: bool) -> None:
    """Print a pretty table with AIMBAT configuration options."""
    import json
    from aimbat.utils import TABLE_STYLING
    from aimbat.utils._json import json_to_table

    env_prefix = Settings.model_config.get("env_prefix")
    values: dict[str, str] = json.loads(settings.model_dump_json())

    if not pretty:
        for k, v in values.items():
            env_key = f"{env_prefix.upper()}{k.upper()}" if env_prefix else k
            print(f'{env_key}="{v}"')
        return

    rows = []
    for k, v in values.items():
        field_info = Settings.model_fields.get(k)
        env_var = (
            f"Environment variable: {env_prefix.upper()}{k.upper()}"
            if env_prefix
            else ""
        )
        description = field_info.description if field_info else ""
        description_with_env_var = (f"{description} " if description else "") + env_var
        rows.append(
            {"name": k, "value": str(v), "description": description_with_env_var}
        )

    json_to_table(
        rows,
        title="AIMBAT settings",
        column_kwargs={
            "name": {
                "header": "Name",
                "justify": "left",
                "style": TABLE_STYLING.id,
                "no_wrap": True,
            },
            "value": {
                "header": "Value",
                "justify": "center",
                "style": TABLE_STYLING.mine,
            },
            "description": {
                "header": "Description",
                "justify": "left",
                "style": TABLE_STYLING.linked,
            },
        },
    )


def cli_settings_list(
    *,
    pretty: bool = True,
) -> None:
    """Print a table with default settings currently in use by AIMBAT.

    These defaults control the default behavior of AIMBAT within a project.
    Overriding these defaults can be done on a per-project basis in the
    fllowing ways (in order of precedence):

    - By using environment variables of the form `AIMBAT_{SETTING_NAME}`
      (e.g. `AIMBAT_LOG_LEVEL=DEBUG`).
    - Setting them in a `.env` file in the current working directory
      (e.g. `AIMBAT_LOG_LEVEL=DEBUG` in `.env`).

    Args:
        pretty: Print the table in a pretty format.
    """
    print_settings_table(pretty)


def generate_settings_table_markdown() -> str:
    """Generate a markdown table of all AIMBAT default settings."""
    import json

    class _DefaultsOnly(Settings):
        """Settings subclass that ignores all external sources."""

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return ()

    env_prefix = Settings.model_config.get("env_prefix", "").upper()
    values: dict[str, str] = json.loads(_DefaultsOnly().model_dump_json())

    lines = [
        "| Environment Variable | Default | Description |",
        "|----------------------|---------|-------------|",
    ]

    for name, value in values.items():
        field_info = Settings.model_fields.get(name)
        description = (field_info.description or "" if field_info else "").replace(
            "|", "\\|"
        )
        env_var = f"`{env_prefix}{name.upper()}`"
        formatted = f"`{value}`" if value != "" else '`""`'
        lines.append(f"| {env_var} | {formatted} | {description} |")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(generate_settings_table_markdown(), end="")
