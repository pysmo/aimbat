from pysmo.tools.iccs import ICCS, plotstack as _plotstack


def plot_stack(iccs: ICCS, padded: bool) -> None:
    _plotstack(iccs, padded)
