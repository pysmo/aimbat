"""Processing of data.

This command launches various processing tools.
"""

from aimbat.cli.common import CommonParameters
from cyclopts import App


def _processing_plot_stack(db_url: str | None) -> None:
    from aimbat.lib.processing import plot_stack
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        plot_stack(session)


def _processing_run_iccs(db_url: str | None) -> None:
    from aimbat.lib.processing import run_iccs
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        run_iccs(session)


def _processing_stack_pick(db_url: str | None) -> None:
    from aimbat.lib.processing import stack_pick
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        stack_pick(session)


app = App(name="processing", help=__doc__, help_format="markdown")


@app.command(name="plotstack")
def processing_plot_stack(*, common: CommonParameters | None = None) -> None:
    """Plot iccs stack."""

    common = common or CommonParameters()

    _processing_plot_stack(common.db_url)


@app.command(name="iccs")
def processing_iccs(*, common: CommonParameters | None = None) -> None:
    """Run ICCS."""

    common = common or CommonParameters()

    _processing_run_iccs(common.db_url)


@app.command(name="pick")
def processing_cli_pick(*, common: CommonParameters | None = None) -> None:
    """Pick arrival time in stack."""

    common = common or CommonParameters()

    _processing_stack_pick(common.db_url)


if __name__ == "__main__":
    app()
