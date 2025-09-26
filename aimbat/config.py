"""Global configuration options for the AIMBAT application."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from datetime import timedelta


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="aimbat_", env_file=".env")

    project: Path = Field(
        default=Path("aimbat.db"),
        description="AIMBAT project file location (ignored if `db_url` is specified).",
    )
    """AIMBAT project file location."""

    db_url: str = Field(
        default_factory=lambda data: r"sqlite+pysqlite:///" + str(data["project"]),
        description="AIMBAT database url (default value is derived from `project`.)",
    )
    """AIMBAT database url."""

    logfile: Path = Field(default=Path("aimbat.log"), description="Log file location.")
    """Log file location."""

    debug: bool = Field(default=False, description="Enable debug logging.")
    """Enable debug logging."""

    window_pre: timedelta = Field(
        default=timedelta(seconds=-15),
        lt=0,
        description="Initial relative begin time of window.",
    )
    """Initial relative begin time of window."""

    window_post: timedelta = Field(
        default=timedelta(seconds=15),
        ge=0,
        description="Initial relative end time of window.",
    )
    """Initial relative end time of window."""

    window_padding: timedelta = Field(
        default=timedelta(seconds=20), gt=0, description="Padding around time window."
    )
    """Padding around time window."""

    min_ccnorm: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Initial minimum cross correlation coefficient.",
    )
    """Initial minimum cross correlation coefficient."""

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


settings = Settings()


def print_settings_table(pretty: bool) -> None:
    """Print a pretty table with AIMBAT configuration options."""
    from aimbat.cli.styling import make_table, TABLE_COLOURS
    from rich.console import Console

    env_prefix = ""
    try:
        env_prefix = Settings.model_config["env_prefix"]
    except KeyError:
        pass

    if not pretty:
        for k in Settings.model_fields:
            print(
                f'{(env_prefix + k).upper() if env_prefix else k}="{getattr(settings, k)}"'
            )
        return

    table = make_table(title="AIMBAT settings")
    table.add_column("Name", justify="left", style=TABLE_COLOURS.id, no_wrap=True)
    table.add_column("Value", justify="center", style=TABLE_COLOURS.mine)
    table.add_column("Description", justify="left", style=TABLE_COLOURS.linked)

    for k, v in Settings.model_fields.items():
        description = f"{v.description}" if v.description else ""
        if env_prefix:
            env_var = f" Environment variable: {env_prefix.upper()}{str(k).upper()}"
            description += env_var
        description = description
        table.add_row(k, str(getattr(settings, k)), description)

    console = Console()
    console.print(table)


if __name__ == "__main__":
    print(Settings().model_dump())
