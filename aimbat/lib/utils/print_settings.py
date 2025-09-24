from aimbat.logger import logger
from aimbat.lib.misc.rich_utils import make_table
from rich.console import Console
from aimbat.config import settings, Settings


def print_settings_table() -> None:
    """Print a pretty table with AIMBAT configuration options."""

    logger.info("Printing AIMBAT settings table.")

    env_prefix = None
    try:
        env_prefix = Settings.model_config["env_prefix"]
    except KeyError:
        pass

    table = make_table(title="AIMBAT settings")
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Value", justify="center", style="magenta")
    table.add_column("Description", justify="left", style="green")

    for k, v in Settings.model_fields.items():
        description = f"{v.description}" if v.description else ""
        if env_prefix:
            env_var = f" Environment variable: {env_prefix.upper()}{str(k).upper()}"
            description += env_var
        description = description
        table.add_row(k, str(getattr(settings, k)), description)

    console = Console()
    console.print(table)
