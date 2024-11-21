from aimbat.lib.common import cli_enable_debug
import click


def _utils_plotseis(event_id: int, use_qt: bool = False) -> None:
    from aimbat.lib.utils import utils_plotseis
    import pyqtgraph as pg  # type: ignore

    if use_qt:
        pg.mkQApp()

    utils_plotseis(event_id, use_qt)

    if use_qt:
        pg.exec()


@click.group("utils")
@click.pass_context
def utils_cli(ctx: click.Context) -> None:
    """Usefull extra tools to use with AIMBAT projects."""
    cli_enable_debug(ctx)


@utils_cli.command("plotseis")
@click.argument("event_id", nargs=1, type=int, required=True)
@click.pass_context
def utils_cli_plotseis(ctx: click.Context, event_id: int) -> None:
    """Plot seismograms in project."""

    use_qt: bool = ctx.obj.get("USE_QT", False)
    _utils_plotseis(event_id, use_qt)


if __name__ == "__main__":
    utils_cli(obj={})
