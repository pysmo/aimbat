from aimbat.lib.common import cli_enable_debug
import click


def _snapshot_create(event_id: int, comment: str | None = None) -> None:
    from aimbat.lib.snapshot import snapshot_create

    snapshot_create(event_id, comment)


def _snapshot_delete(snapshot_id: int) -> None:
    from aimbat.lib.snapshot import snapshot_delete

    snapshot_delete(snapshot_id)


def _snapshot_print_table() -> None:
    from aimbat.lib.snapshot import snapshot_print_table

    snapshot_print_table()


@click.group("snapshot")
@click.pass_context
def snapshot_cli(ctx: click.Context) -> None:
    """View and manage stations in the AIMBAT project."""
    cli_enable_debug(ctx)


@snapshot_cli.command("create")
@click.argument("event_id", nargs=1, type=int, required=True)
@click.option("--comment", "-c", default=None, help="Add a comment to snapshot")
def snapshot_cli_create(event_id: int, comment: str | None = None) -> None:
    """Create new snapshot."""
    _snapshot_create(event_id, comment)


@snapshot_cli.command("delete")
@click.argument("snapshot_id", nargs=1, type=int, required=True)
def snapshot_cli_delete(snapshot_id: int) -> None:
    """Delete existing snapshot."""
    _snapshot_delete(snapshot_id)


@snapshot_cli.command("list")
def snapshot_cli_list() -> None:
    """Print information on the snapshots stored in AIMBAT."""
    _snapshot_print_table()


if __name__ == "__main__":
    snapshot_cli(obj={})
