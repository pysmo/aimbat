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

    _blah: int = 4


settings = Settings()


def print_settings_table(pretty: bool) -> None:
    """Print a pretty table with AIMBAT configuration options."""
    from aimbat.lib.common import make_table, TABLE_STYLING
    from rich.console import Console

    env_prefix = Settings.model_config.get("env_prefix")

    if not pretty:
        for k in Settings.model_fields:
            print(
                f'{(env_prefix + k).upper() if env_prefix else k}="{getattr(settings, k)}"'
            )
        return

    table = make_table(title="AIMBAT settings")
    table.add_column("Name", justify="left", style=TABLE_STYLING.id, no_wrap=True)
    table.add_column("Value", justify="center", style=TABLE_STYLING.mine)
    table.add_column("Description", justify="left", style=TABLE_STYLING.linked)

    for k, v in Settings.model_fields.items():
        env_var = (
            f"Environment variable: {env_prefix.upper()}{str(k).upper()}"
            if env_prefix
            else ""
        )
        description_with_env_var = (
            f"{v.description} " if v.description else ""
        ) + env_var
        table.add_row(k, str(getattr(settings, k)), description_with_env_var)

    console = Console()
    console.print(table)


def cli_settings_list(
    *,
    pretty: bool = True,
) -> None:
    """Print a table with default settings used in AIMBAT.

    These defaults control the default behavior of AIMBAT within a project.
    They can be changed using environment variables of the same name, or by
    adding a `.env` file to the current working directory.

    Parameters:
        pretty: Print the table in a pretty format.
    """
    print_settings_table(pretty)


if __name__ == "__main__":
    print(Settings().model_dump())
