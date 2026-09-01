import os

import matplotlib
import matplotlib.pyplot as plt
import pytest

matplotlib.use("Agg")


@pytest.fixture(autouse=True)
def _test_environment(monkeypatch):
    """Run each test from the tests directory (cwd-relative data paths) on the Agg backend.

    Several aimbat modules reset ``rcParams['backend']`` to an interactive backend at import
    time, so the backend has to be forced back per test.
    """
    plt.switch_backend("Agg")
    monkeypatch.chdir(os.path.dirname(__file__))
    yield
    plt.close("all")
