"""Histogram rendering for promotion distributions. matplotlib is imported
lazily so the rest of the tool has no hard dependency on it."""
from __future__ import annotations


def histogram_png(bins: list[dict], *, path: str, title: str, subtitle: str = "",
                  mean: float | None = None, your_note: float | None = None) -> str:
    """Render histogram_rows as a bar chart PNG at `path`. Dashed line at the
    promotion mean, solid marker at your note. Returns `path`."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless: no display needed
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised via CLI hint
        raise RuntimeError("matplotlib not installed — run: pip install matplotlib") from exc

    fig, ax = plt.subplots(figsize=(9, 5))
    if bins:
        centers = [(b["bin_low"] + b["bin_high"]) / 2 for b in bins]
        widths = [(b["bin_high"] - b["bin_low"]) * 0.9 for b in bins]
        ax.bar(centers, [b["count"] for b in bins], width=widths,
               color="#4C78A8", edgecolor="white")
        ax.set_xlabel("Note / 20")
        ax.set_ylabel("Nombre d'étudiants")
    if mean is not None:
        ax.axvline(mean, color="#F58518", linestyle="--", linewidth=2, label=f"Moyenne {mean:.2f}")
    if your_note is not None:
        ax.axvline(your_note, color="#54A24B", linestyle="-", linewidth=2, label=f"Vous {your_note:.2f}")
    if mean is not None or your_note is not None:
        ax.legend()
    ax.set_title(title if not subtitle else f"{title}\n{subtitle}", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
