from aimbat.lib.common import cli_enable_debug
import click


def _station_print_table() -> None:
    from aimbat.lib.station import station_print_table

    station_print_table()


@click.group("station")
@click.pass_context
def station_cli(ctx: click.Context) -> None:
    """View and manage stations in the AIMBAT project."""
    cli_enable_debug(ctx)


@station_cli.command("list")
def station_cli_list() -> None:
    """Print information on the stations stored in AIMBAT."""
    _station_print_table()


if __name__ == "__main__":
    station_cli(obj={})
