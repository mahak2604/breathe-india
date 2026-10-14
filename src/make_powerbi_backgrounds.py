"""
Draws the page backgrounds for the Power BI dashboard (1280 x 720 canvas, rendered at 2x).

Each background has a header band with the page title, space on the right for the
navigation buttons, and a footer with the data credits. Visuals sit on top in Power BI.
Edit PAGES and rerun to change the wording:  python src/make_powerbi_backgrounds.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT = Path("powerbi/backgrounds")
W, H = 1280, 720
HEADER_H, FOOTER_H = 76, 26
NAVY, PALE_BLUE, PAGE, MUTED = "#0D366B", "#9EC5F4", "#F4F3EF", "#898781"
FONT = ["Segoe UI", "DejaVu Sans", "Arial"]

PAGES = [
    ("1_overview", "The air India breathes", "26 cities · 2015 – mid-2020 · CPCB monitoring network"),
    ("2_city_explorer", "City explorer", "Pick a city: its seasons, its stations and its worst days"),
    ("3_lockdown", "What the lockdown really changed", "Actual pollution vs. what the weather alone would have produced"),
    ("4_early_warning", "Can we warn a day ahead?", "Next-day AQI category model vs. a 'same as today' baseline"),
    ("5_data_quality", "How the data was cleaned", "What we found, fixed and flagged before any analysis"),
]
FOOTER = ("Data: Central Pollution Control Board (via Kaggle) · Open-Meteo / Copernicus ERA5 (CC BY 4.0)    "
          "Mahak Wadhawan (L074) · Yash Shah (L056)")


def draw(slug, title, subtitle):
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), W, H, color=PAGE))
    ax.add_patch(Rectangle((0, 0), W, HEADER_H, color=NAVY))
    ax.text(24, 22, "BREATHE  INDIA", color=PALE_BLUE, fontsize=7.5, fontfamily=FONT, fontweight="bold",
            va="center")
    ax.text(24, 47, title, color="white", fontsize=15, fontfamily=FONT, fontweight="semibold", va="center")
    ax.text(24, 66, subtitle, color=PALE_BLUE, fontsize=7.8, fontfamily=FONT, va="center")
    ax.text(24, H - FOOTER_H / 2, FOOTER, color=MUTED, fontsize=6.5, fontfamily=FONT, va="center")
    fig.savefig(OUT / f"{slug}.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        draw(*page)
    print(f"Saved {len(PAGES)} backgrounds to {OUT}")
