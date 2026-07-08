import os
import pytest

matplotlib = pytest.importorskip("matplotlib")  # skip cleanly if not installed
from schoolapp import plots


def test_histogram_png_writes_a_nonempty_file(tmp_path):
    bins = [
        {"bin_low": 0.0, "bin_high": 5.0, "count": 1},
        {"bin_low": 5.0, "bin_high": 10.0, "count": 2},
        {"bin_low": 10.0, "bin_high": 15.0, "count": 2},
        {"bin_low": 15.0, "bin_high": 20.0, "count": 1},
    ]
    out = str(tmp_path / "hist.png")
    result = plots.histogram_png(bins, path=out, title="S1 · MoySem",
                                 subtitle="API-MPT 2024-2025", mean=10.5, your_note=12.5)
    assert result == out
    assert os.path.getsize(out) > 0


def test_histogram_png_empty_bins_still_writes(tmp_path):
    out = str(tmp_path / "empty.png")
    plots.histogram_png([], path=out, title="none")
    assert os.path.exists(out)
