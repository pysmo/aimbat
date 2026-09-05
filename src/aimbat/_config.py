"""Global configuration options for the AIMBAT application."""

from pathlib import Path
from typing import Literal, Self

from pandas import Timedelta
from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from aimbat.types import (
    PydanticNegativeTimedelta,
    PydanticNonNegativeFloat,
    PydanticPositiveTimedelta,
)


class Settings(BaseSettings):
    """Runtime configuration for AIMBAT.

    Values are populated, in order of precedence, from keyword arguments,
    environment variables prefixed with `AIMBAT_`, and an `.env` file in the
    current working directory.
    """

    model_config = SettingsConfigDict(env_prefix="aimbat_", env_file=".env")

    bandpass_apply: bool = Field(
        default=False,
        description="Whether to apply bandpass filter to seismograms.",
    )

    bandpass_fmax: float = Field(
        default=2,
        gt=0,
        description=(
            "Maximum frequency for bandpass filter (ignored if `bandpass_apply` "
            + "is False)."
        ),
    )

    bandpass_fmin: float = Field(
        default=0.05,
        description=(
            "Minimum frequency for bandpass filter (ignored if `bandpass_apply` "
            + "is False)."
        ),
    )

    context_width: PydanticPositiveTimedelta = Field(
        default=Timedelta(seconds=20),
        description="Context padding to apply before and after the time window.",
    )

    corners: int = Field(
        default=2,
        gt=0,
        description=(
            "Number of corners (poles) for the bandpass filter (ignored if "
            + "`bandpass_apply` is False)."
        ),
    )

    db_url: str = Field(
        default="",
        description="AIMBAT database url (default value is derived from `project`).",
    )

    event_duplicate_raise_tolerance: PydanticPositiveTimedelta = Field(
        default=Timedelta(seconds=2),
        description=(
            "Upper bound of the 'ambiguous gap' band. A new event whose origin "
            + "time is further than `event_duplicate_tolerance` but closer than "
            + "this to an existing event's time raises an error unconditionally "
            + "(even during `--dry-run`): the gap is too large for timestamp "
            + "precision noise, too small to be confidently unrelated events. "
            + "Compares origin times only, not location. Ignored when "
            + "`event_duplicate_strict` is True."
        ),
    )

    event_duplicate_strict: bool = Field(
        default=False,
        description=(
            "If True, skip near-duplicate detection entirely: "
            + "`event_duplicate_tolerance` and `event_duplicate_raise_tolerance` "
            + "are both ignored and events merge only on an exact origin-time match"
            + " (itself only microsecond-accurate, so any larger gap silently "
            + "creates a separate event). Use only for source data trusted to be "
            + "free of timing problems at that precision, e.g. a catalogue of "
            + "genuinely close but distinct events such as an aftershock swarm."
        ),
    )

    event_duplicate_tolerance: PydanticPositiveTimedelta = Field(
        default=Timedelta(seconds=0.1),
        description=(
            "Maximum origin-time difference for a new event to be treated as a "
            + "duplicate of an existing one when there is no exact match. A gap "
            + "this small usually reflects upstream precision loss (e.g. SAC's "
            + "32-bit float `o` header) rather than a distinct event, so the "
            + "existing event is reused with a warning, exactly as an exact match "
            + "is (its stored time and location are unchanged). Larger gaps are "
            + "handled by `event_duplicate_raise_tolerance`. Ignored when "
            + "`event_duplicate_strict` is True."
        ),
    )

    log_level: Literal[
        "TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
    ] = Field(
        default="INFO",
        description=(
            "Logging level. Valid levels (from most to least verbose): TRACE, "
            + "DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL."
        ),
    )

    logfile: Path = Field(default=Path("aimbat.log"), description="Log file location.")

    mccc_damp: float = Field(
        default=0.1, ge=0, description="Damping factor for MCCC algorithm."
    )

    mccc_min_cc: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description=(
            "Minimum correlation coefficient required to include a pair in the "
            + "MCCC inversion."
        ),
    )

    min_cc: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description=(
            "Initial minimum cross correlation coefficient threshold for ICCS "
            + "selection."
        ),
    )

    min_id_length: int = Field(
        default=2, ge=1, description="Minimum length of ID string."
    )

    project: Path = Field(
        default=Path("aimbat.db"),
        description="AIMBAT project file location (ignored if `db_url` is specified).",
    )

    sac_pick_header: str = Field(
        default="t0", description="SAC header field where initial pick is stored."
    )

    sampledata_dir: Path = Field(
        default=Path("sample-data"),
        description="Directory to store downloaded sample data.",
    )

    strict_schema_check: bool = Field(
        default=False,
        description=(
            "Raise an error instead of a non-blocking warning when the project "
            + "database schema is out of date. Only affects third-party code using "
            + "aimbat.db.engine directly - AIMBAT's own CLI and TUI always treat a "
            + "stale schema as a hard failure regardless of this setting. Intended "
            + "for scripting: setting PYTHONWARNINGS/-W directly does not reliably "
            + "work for third-party warning categories, since Python resolves them "
            + "very early during interpreter startup, before the AIMBAT package is "
            + "reliably importable."
        ),
    )

    ramp_width: PydanticNonNegativeFloat = Field(
        default=0.1,
        description=(
            "Width of taper ramp as a multiple of the window length. Values "
            + "greater than 1 are valid; the ramp extends outside the window."
        ),
    )

    window_post: PydanticPositiveTimedelta = Field(
        default=Timedelta(seconds=15),
        description="Initial relative end time of window.",
    )

    window_pre: PydanticNegativeTimedelta = Field(
        default=Timedelta(seconds=-15),
        description="Initial relative begin time of window.",
    )

    tui_dark_theme: str = Field(
        default="catppuccin-mocha",
        min_length=1,
        description="TUI dark theme name (from available Textual themes).",
    )
    tui_light_theme: str = Field(
        default="catppuccin-latte",
        min_length=1,
        description="TUI light theme name (from available Textual themes).",
    )

    @model_validator(mode="after")
    def set_computed_defaults(self) -> Self:
        """Derive `db_url` from `project` when not set explicitly.

        A literal `?` in `project` is percent-encoded first: SQLite URL
        parsing otherwise treats it as the start of a query string, silently
        truncating everything from `?` onwards off the path SQLAlchemy
        actually opens.
        """
        if self.db_url == "":
            escaped_project = str(self.project).replace("?", "%3F")
            self.db_url = f"sqlite+pysqlite:///{escaped_project}"
        return self

    @model_validator(mode="after")
    def validate_event_duplicate_tolerances(self) -> Self:
        """Ensure the ambiguous-gap band is non-empty."""
        if self.event_duplicate_raise_tolerance <= self.event_duplicate_tolerance:
            raise ValueError(
                "event_duplicate_raise_tolerance must be greater than "
                + "event_duplicate_tolerance."
            )
        return self


settings = Settings()


def print_settings_table(pretty: bool) -> None:
    """Print the current AIMBAT configuration.

    Args:
        pretty: If True, print a Rich table with name, value, and
            description columns. If False, print each setting as a
            shell-style `AIMBAT_NAME="value"` assignment.
    """
    import json

    from pydantic import BaseModel

    from aimbat._cli.common import json_to_table
    from aimbat.models._format import RichColSpec

    class _SettingsRow(BaseModel):
        name: str = Field(
            title="Name",
            json_schema_extra={"rich": RichColSpec(justify="left", no_wrap=True)},  # type: ignore[dict-item]
        )
        value: str = Field(
            title="Value",
            json_schema_extra={"rich": RichColSpec(justify="left", no_wrap=True)},  # type: ignore[dict-item]
        )
        description: str = Field(
            title="Description",
            json_schema_extra={"rich": RichColSpec(justify="left")},  # type: ignore[dict-item]
        )

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

    json_to_table(rows, model=_SettingsRow, title="AIMBAT settings")


def cli_settings_list(
    *,
    pretty: bool = True,
) -> None:
    """Print the AIMBAT configuration currently in effect.

    These settings control the default behaviour of AIMBAT within a project.
    They can be overridden on a per-project basis, in order of precedence:

    - By using environment variables of the form `AIMBAT_{SETTING_NAME}`
      (e.g. `AIMBAT_LOG_LEVEL=DEBUG`).
    - Setting them in a `.env` file in the current working directory
      (e.g. `AIMBAT_LOG_LEVEL=DEBUG` in `.env`).

    Args:
        pretty: If True, print a Rich table with name, value, and
            description columns. If False, print each setting as a
            shell-style `AIMBAT_NAME="value"` assignment.
    """
    print_settings_table(pretty)


class _DefaultsOnly(Settings):
    """Settings subclass that ignores environment variables and `.env` files.

    Used to read field defaults uninfluenced by the current environment.
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Return no settings sources, so only field defaults apply."""
        return ()


def get_default_settings() -> Settings:
    """Return AIMBAT settings populated from field defaults only.

    Environment variables and `.env` files are ignored, so this reflects
    the true default value of each setting regardless of the current
    environment.
    """
    return _DefaultsOnly()


def generate_settings_table_markdown() -> str:
    """Generate a Markdown table of all AIMBAT default settings.

    Returns:
        Markdown table text, with one row per setting giving its
        environment variable name, default value, and description.
    """
    import json

    env_prefix = Settings.model_config.get("env_prefix", "").upper()
    values: dict[str, str] = json.loads(get_default_settings().model_dump_json())

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
