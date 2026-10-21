"""
Draws the pipeline overview used as Fig. 1 of the written report.

    python docs/report/make_pipeline_figure.py    -> figures/00_pipeline_overview.png

Drawn at its printed size (16 cm wide) so the text stays readable in the report.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "00_pipeline_overview.png"

NAVY, ORANGE = "#0D366B", "#C4531F"
PALE_BLUE, PALE_ORANGE, PALE_GREY = "#E8EEF7", "#FBEDE6", "#F2F1EC"
INK, MUTED, EDGE_GREY = "#1A1A1A", "#52514E", "#A9A8A0"
FONT = "Segoe UI"
CM = 1 / 2.54
W, H = 16.0, 5.0                      # centimetres


def box(ax, x, y, w, h, title, lines, edge, fill, title_color, step=0.42):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.15",
                                linewidth=0.9, edgecolor=edge, facecolor=fill))
    top = y + h - 0.36
    ax.text(x + w / 2, top, title, ha="center", va="center", fontsize=7.6, fontweight="bold",
            color=title_color, family=FONT)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, top - 0.48 - i * step, line, ha="center", va="center", fontsize=6.8,
                color=INK, family=FONT)


def arrow(ax, start, end, color):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=7, linewidth=0.9,
                                 color=color, shrinkA=0, shrinkB=0))


def label(ax, x, text):
    ax.text(x, H - 0.25, text, ha="center", va="center", fontsize=6.2, fontweight="bold",
            color=MUTED, family=FONT)


def main():
    fig = plt.figure(figsize=(W * CM, H * CM), dpi=400)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    bw, gap, by, bh = 2.2, 0.42, 1.1, 2.45
    xs = [0.1 + i * (bw + gap) for i in range(6)]
    mid = by + bh / 2
    ow = W - 0.1 - xs[5]                       # the output column takes the remaining width

    box(ax, xs[0], by, bw, bh, "4 sources", ["CPCB (Kaggle)", "Weather API", "Geocoding API", "Event calendar"],
        EDGE_GREY, PALE_GREY, INK)
    stages = [("1  Extraction", ["download + APIs", "rate limits", "raw JSON cached"]),
              ("2  Cleaning", ["23 logged steps", "faults removed", "AQI rebuilt"]),
              ("3  Transform", ["star schema", "61-column fact", "lags, reshapes"]),
              ("4  Loading", ["SQLite, 14 tables", "Parquet by year", "read-back checks"])]
    for x, (title, lines) in zip(xs[1:5], stages):
        box(ax, x, by, bw, bh, title, lines, NAVY, PALE_BLUE, NAVY)
    for a, b in zip(xs[:4], xs[1:5]):
        arrow(ax, (a + bw, mid), (b, mid), NAVY)

    # outputs: models feed the dashboard
    ox = xs[5]
    box(ax, ox, 2.5, ow, 2.05, "Machine learning", ["A  classifier", "B  counterfactual", "C  clustering"],
        ORANGE, PALE_ORANGE, ORANGE, step=0.38)
    box(ax, ox, 0.1, ow, 2.05, "Power BI", ["5 pages", "49 measures", "PDF export"], ORANGE, PALE_ORANGE, ORANGE,
        step=0.38)
    arrow(ax, (xs[4] + bw, mid + 0.35), (ox, 3.5), ORANGE)
    arrow(ax, (xs[4] + bw, mid - 0.35), (ox, 1.1), ORANGE)
    arrow(ax, (ox + ow / 2, 2.5), (ox + ow / 2, 2.15), ORANGE)

    label(ax, xs[0] + bw / 2, "INPUT")
    label(ax, (xs[1] + xs[4] + bw) / 2, "DATA WRANGLING PIPELINE  ·  one notebook, about 8 minutes")
    label(ax, ox + ow / 2, "OUTPUTS")

    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=400, facecolor="white")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
