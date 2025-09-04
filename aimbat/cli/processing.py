"""Processing tools.

This command launches various processing tools.
"""

from aimbat.cli.common import CommonParameters
from cyclopts import App


def _processing_run_iccs(db_url: str | None) -> None:
    from aimbat.lib.processing import create_iccs_instance, run_iccs
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        run_iccs(session, iccs)


def _processing_stack_pick(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.processing import create_iccs_instance, stack_pick
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        stack_pick(session, iccs, padded)


def _processing_stack_tw_pick(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.processing import create_iccs_instance, stack_tw_pick
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        stack_tw_pick(session, iccs, padded)


app = App(name="processing", help=__doc__, help_format="markdown")


@app.command(name="iccs")
def processing_iccs(*, common: CommonParameters | None = None) -> None:
    """Run ICCS."""

    common = common or CommonParameters()

    _processing_run_iccs(common.db_url)


@app.command(name="pick")
def processing_cli_pick(
    *, padded: bool = True, common: CommonParameters | None = None
) -> None:
    """Pick arrival time in stack.

    Parameters:
        padded: Pad the time window for plotting.
    """

    common = common or CommonParameters()

    _processing_stack_pick(common.db_url, padded)


@app.command(name="tw")
def processing_cli_tw_pick(
    *, padded: bool = True, common: CommonParameters | None = None
) -> None:
    """Pick time window in stack.

    Parameters:
        padded: Pad the time window for plotting.
    """

    common = common or CommonParameters()

    _processing_stack_tw_pick(common.db_url, padded)


if __name__ == "__main__":
    app()
