from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from datetime import timedelta


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="aimbat_", env_file=".env")

    project: Path = Field(
        default=Path("aimbat.db"), description="AIMBAT project file location."
    )
    db_url: str = Field(
        default_factory=lambda data: r"sqlite+pysqlite:///" + str(data["project"]),
        description="AIMBAT database url.",
    )

    logfile: Path = Field(default=Path("aimbat.log"), description="Log file location.")

    debug: bool = Field(default=False, description="Enable debug logging.")

    window_pre: timedelta = Field(
        default=timedelta(seconds=-15),
        lt=0,
        description="Initial relative begin time of window.",
    )
    window_post: timedelta = Field(
        default=timedelta(seconds=15),
        ge=0,
        description="Initial relative end time of window.",
    )
    window_padding: timedelta = Field(
        default=timedelta(seconds=20), gt=0, description="Padding around time window."
    )
    min_ccnorm: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Initial minimum cross correlation coefficient.",
    )
    sac_pick_header: str = Field(
        default="t0", description="SAC header field where initial pick is stored."
    )
    sampledata_src: str = Field(
        default="https://github.com/pysmo/data-example/archive/refs/heads/aimbat_v2.zip",
        description="URL where sample data is downloaded from.",
    )
    sampledata_dir: Path = Field(
        default=Path("sample-data"),
        description="Directory to store downloaded sample data.",
    )


settings = Settings()


if __name__ == "__main__":
    print(Settings().model_dump())
