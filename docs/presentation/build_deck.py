"""
Builds the viva deck: docs/presentation/Breathe_India_viva.pptx

    python docs/presentation/build_deck.py

10 slides, 16:9, native (editable) PowerPoint charts drawn from the project's output tables,
two notebook figures and one dashboard screenshot, and speaker notes on every slide.
"""

from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
DATA, FIG = ROOT / "powerbi" / "data", ROOT / "figures"
OUT = Path(__file__).resolve().parent / "Breathe_India_viva.pptx"

NAVY, BLUE, ORANGE = RGBColor(0x0D, 0x36, 0x6B), RGBColor(0x2A, 0x78, 0xD6), RGBColor(0xEB, 0x68, 0x34)
GREEN, INK, INK2 = RGBColor(0x1B, 0xAF, 0x7A), RGBColor(0x1A, 0x1A, 0x1A), RGBColor(0x52, 0x51, 0x4E)
MUTED, GRID, TINT, WHITE = RGBColor(0x89, 0x87, 0x81), RGBColor(0xE1, 0xE0, 0xD9), RGBColor(0xEE, 0xF3, 0xFA), RGBColor(0xFF, 0xFF, 0xFF)
PALE = RGBColor(0x9E, 0xC5, 0xF4)
FONT = "Calibri"
W, H = 13.333, 7.5

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]


# ----------------------------------------------------------------------------- helpers
def text(slide, x, y, w, h, runs, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         line_spacing=1.1, space_after=6):
    """runs: a string, or a list of paragraphs; each paragraph a string or a list of (text, {opts})."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paragraphs = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        for piece, opts in ([(para, {})] if isinstance(para, str) else para):
            r = p.add_run()
            r.text = piece
            f = r.font
            f.name, f.size = FONT, Pt(opts.get("size", size))
            f.bold = opts.get("bold", bold)
            f.italic = opts.get("italic", False)
            f.color.rgb = opts.get("color", color)
    return box


def title(slide, words, kicker=None, dark=False):
    if kicker:
        text(slide, 0.6, 0.38, 12, 0.3, kicker.upper(), size=12, bold=True, color=PALE if dark else BLUE)
    text(slide, 0.6, 0.66, 12.1, 0.9, words, size=30, bold=True, color=WHITE if dark else NAVY,
         line_spacing=1.0)


def background(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def card(slide, x, y, w, h, fill=TINT):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.06
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def badge(slide, x, y, label, fill=NAVY, size=0.46):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(size), Inches(size))
    c.fill.solid()
    c.fill.fore_color.rgb = fill
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(14), True, WHITE
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE


def stat(slide, x, y, w, value, label, color=NAVY, value_size=40, label_size=13):
    text(slide, x, y, w, 0.75, value, size=value_size, bold=True, color=color, line_spacing=1.0)
    text(slide, x, y + 0.8, w, 0.8, label, size=label_size, color=INK2, line_spacing=1.05)


def footer(slide, n, dark=False):
    text(slide, 0.6, 7.0, 9, 0.3, "Breathe India · Mahak Wadhawan (L074) · Yash Shah (L056)", size=10,
         color=PALE if dark else MUTED)
    text(slide, 11.73, 7.0, 1.0, 0.3, str(n), size=10, color=PALE if dark else MUTED, align=PP_ALIGN.RIGHT)


def notes(slide, words):
    slide.notes_slide.notes_text_frame.text = words


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                    Inches(w) if w else None, Inches(h) if h else None)


def style_chart(chart, legend=True, size=12):
    chart.font.name, chart.font.size = FONT, Pt(size)
    chart.font.color.rgb = INK2
    chart.has_title = False
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)


def quiet_axes(chart, value_format=None, gridlines=True, show_value_axis=True):
    va, ca = chart.value_axis, chart.category_axis
    va.has_major_gridlines = gridlines
    if gridlines:
        va.major_gridlines.format.line.color.rgb = GRID
        va.major_gridlines.format.line.width = Pt(0.75)
    va.format.line.fill.background()
    va.visible = show_value_axis
    if value_format:
        va.tick_labels.number_format, va.tick_labels.number_format_is_linked = value_format, False
    ca.format.line.color.rgb = GRID
    ca.has_major_gridlines = False


# ----------------------------------------------------------------------------- data
raw = pd.read_csv(ROOT / "data" / "raw" / "city_day.csv")
fact = pd.read_csv(DATA / "fact_city_day.csv")
metrics = pd.read_csv(DATA / "ml_model_metrics.csv")
effect = pd.read_csv(DATA / "ml_lockdown_effect.csv")

rank = (pd.DataFrame({"official": raw.groupby("City")["AQI"].median(),
                      "cleaned": fact.groupby("City")["AQI_clean"].median()})
        .dropna().sort_values("official", ascending=False).head(7))
season = fact.groupby(["city_group", "Month"])["PM25"].median().unstack(0)
test = metrics[metrics["evaluation"].eq("Test (2019 - Mar 2020)")]
mtab = test.pivot_table(index="model", columns="metric", values="value")
order = ["Persistence baseline", "Logistic Regression", "Random Forest", "Gradient Boosting"]
mtab = mtab.reindex(order)
pm = effect[effect["pollutant"].eq("PM25")].sort_values("weather_adjusted_change_pct")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ----------------------------------------------------------------------------- 1 title
s = prs.slides.add_slide(BLANK)
background(s, NAVY)
text(s, 0.8, 1.2, 9, 0.4, "DATA WRANGLING GROUP PROJECT", size=14, bold=True, color=PALE)
text(s, 0.8, 1.75, 11.5, 1.2, "Breathe India", size=60, bold=True, color=WHITE, line_spacing=1.0)
text(s, 0.8, 2.95, 11, 1.0, "What really drives air pollution in Indian cities?", size=28, color=WHITE,
     line_spacing=1.0)
for i, (v, lab) in enumerate([("26", "cities"), ("5½ years", "of daily data, 2015 to 2020"),
                              ("4", "sources joined"), ("3", "machine-learning models")]):
    stat(s, 0.8 + i * 3.05, 4.35, 2.8, v, lab, color=WHITE, value_size=34, label_size=13)
    s.shapes[-1].text_frame.paragraphs[0].runs[0].font.color.rgb = PALE
text(s, 0.8, 6.35, 11, 0.4, "Mahak Wadhawan (L074)  ·  Yash Shah (L056)", size=16, color=WHITE)
notes(s, "Good morning. We are Mahak and Yash. Our project asks one question: how much of a city's daily air "
         "pollution comes from weather and season, and how much from people? We used five and a half years of "
         "government data for 26 Indian cities, joined it with weather from a public API, and used the 2020 "
         "lockdown as a natural experiment.")

# ----------------------------------------------------------------------------- 2 answer first
s = prs.slides.add_slide(BLANK)
title(s, "A third of the lockdown's “clean air” was actually the weather", "The answer, up front")
stats = [("−41%", "PM2.5 change in spring 2020 vs 2019: the headline everyone quoted", MUTED),
         ("−28%", "the real lockdown effect once our model removes the weather", BLUE),
         ("75%", "of next-day air-quality categories predicted exactly (baseline 72%)", NAVY)]
for i, (v, lab, col) in enumerate(stats):
    card(s, 0.6 + i * 4.1, 2.0, 3.8, 3.1)
    stat(s, 0.95 + i * 4.1, 2.35, 3.2, v, lab, color=col, value_size=60, label_size=16)
    s.shapes[-1].top = Inches(3.45)
text(s, 0.6, 5.55, 12, 1.1, [[("Also: ", {"bold": True, "color": NAVY}),
                             ("cleaning changed the story. Officially, Ahmedabad is India's most polluted city. "
                              "It isn't: a sensor column was copied.", {})]], size=17)
footer(s, 2)
notes(s, "Our three headline answers. First, pollution did fall in the 2020 lockdown, 41 percent for fine "
         "particles compared with 2019. But spring 2020 also had kinder weather. Once our model takes the "
         "weather out, the real lockdown effect is 28 percent, so about a third of the headline drop was "
         "weather. Second, tomorrow's air-quality category is predictable 75 percent of the time. Third, "
         "the wrangling itself changed the story, which we'll show next.")

# ----------------------------------------------------------------------------- 3 data + pipeline
s = prs.slides.add_slide(BLANK)
title(s, "Four sources, one star schema, three storage formats", "Data and pipeline")
sources = [("CPCB air quality", "Kaggle download · 29,531 city-days, 108,035 station-days"),
           ("Open-Meteo weather API", "52,234 days of ERA5 weather · rate-limited, cached"),
           ("Open-Meteo geocoding API", "26 cities located · names checked by state"),
           ("Event calendar", "Lockdown phases and Diwali dates")]
for i, (name, sub) in enumerate(sources):
    y = 1.95 + i * 1.12
    card(s, 0.6, y, 4.3, 0.92)
    text(s, 0.85, y + 0.12, 3.9, 0.35, name, size=16, bold=True, color=NAVY)
    text(s, 0.85, y + 0.48, 3.9, 0.4, sub, size=12, color=INK2)
    arrow = s.shapes.add_connector(1, Inches(4.95), Inches(y + 0.46), Inches(5.55), Inches(4.1))
    arrow.line.color.rgb = MUTED
    arrow.line.width = Pt(1.25)
mid = card(s, 5.6, 2.9, 3.0, 2.4, fill=NAVY)
text(s, 5.85, 3.15, 2.5, 0.4, "Clean fact table", size=18, bold=True, color=WHITE)
text(s, 5.85, 3.6, 2.6, 1.6, ["28,260 city-days × 62 columns", "23 logged cleaning decisions",
                              "Validated joins, lags, rolling means"], size=13, color=WHITE, space_after=4)
outs = [("SQLite", "keys + read-back checks"), ("Parquet", "partitioned by year"),
        ("Power BI", "5-page dashboard"), ("Models A, B, C", "scikit-learn")]
for i, (name, sub) in enumerate(outs):
    y = 1.95 + i * 1.12
    card(s, 9.25, y, 3.45, 0.92)
    text(s, 9.5, y + 0.12, 3.0, 0.35, name, size=16, bold=True, color=NAVY)
    text(s, 9.5, y + 0.48, 3.0, 0.4, sub, size=12, color=INK2)
    arrow = s.shapes.add_connector(1, Inches(8.6), Inches(4.1), Inches(9.2), Inches(y + 0.46))
    arrow.line.color.rgb = MUTED
    arrow.line.width = Pt(1.25)
text(s, 0.6, 6.45, 12, 0.4, "Everything reruns end to end in about 8 minutes from one notebook: github.com/mahak2604/breathe-india",
     size=13, color=INK2)
footer(s, 3)
notes(s, "We used four sources. The core is the Central Pollution Control Board's daily data, downloaded from "
         "Kaggle. Weather came from the Open-Meteo API. It rate-limited us after seven cities, so we added "
         "pauses, back-off and a cache. City locations came from a geocoding API, where we had to check every "
         "match by state, because 'Amaravati' exists three times in India. Everything lands in one clean fact "
         "table, then goes into SQLite with key checks, year-partitioned Parquet, the dashboard and the models.")

# ----------------------------------------------------------------------------- 4 wrangling: the data lied
s = prs.slides.add_slide(BLANK)
title(s, "The raw data was wrong in ways a quick look would miss", "Cleaning")
issues = [("1", "A copied column", "Ahmedabad's CO equals its NO on 94% of days, although the units differ "
                                   "1000×. It drove 95% of the city's “Severe” days."),
          ("2", "Impossible pairs", "PM2.5 above PM10 on 256 days. We assumed PM10 was wrong; the data showed "
                                    "PM2.5 was the faulty one 94% of the time."),
          ("3", "Broken sensors", "A sensor stuck at 11.00 for 8 days, and 917 µg/m³ in Shillong, the cleanest "
                                  "city. 197 readings removed, with Diwali spikes kept."),
          ("4", "Gaps and limits", "AQI up to 2,049 on a 0–500 scale, exact zeros, 61% of one column empty. "
                                   "Short gaps interpolated, the rest left honest.")]
for i, (n, head, body) in enumerate(issues):
    x, y = 0.6 + (i % 2) * 6.15, 1.95 + (i // 2) * 2.35
    card(s, x, y, 5.95, 2.1)
    badge(s, x + 0.3, y + 0.3, n, fill=BLUE)
    text(s, x + 0.95, y + 0.32, 4.7, 0.45, head, size=19, bold=True, color=NAVY)
    text(s, x + 0.95, y + 0.85, 4.75, 1.2, body, size=14, color=INK)
footer(s, 4)
notes(s, "These are the four ways the raw data misled us. One: Ahmedabad's carbon monoxide column is a copy of "
         "its nitric oxide column, identical on 94 percent of days. Two: on 256 days fine particles exceeded "
         "coarse particles, which is physically impossible. We first assumed the PM10 sensor was wrong; the "
         "data told us it was PM2.5, so we changed our rule. Three: broken sensors, including Shillong "
         "'reading' 917. Four: impossible AQI values and big gaps. Every decision, 23 in all, is in our "
         "cleaning log with its reason.")

# ----------------------------------------------------------------------------- 5 insight: ranking error
s = prs.slides.add_slide(BLANK)
title(s, "Cleaning moved Ahmedabad from India's most polluted city to 7th", "Insight 1")
cd = CategoryChartData()
cd.categories = list(rank.index[::-1])
cd.add_series("Official CPCB AQI", [round(v) for v in rank["official"][::-1]])
cd.add_series("After cleaning", [round(v) for v in rank["cleaned"][::-1]])
ch = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.75), Inches(8.0), Inches(4.75), cd).chart
style_chart(ch)
quiet_axes(ch, gridlines=False, show_value_axis=False)
plot = ch.plots[0]
plot.gap_width, plot.overlap = 60, -10
plot.has_data_labels = True
plot.data_labels.font.size, plot.data_labels.font.color.rgb = Pt(12), INK2
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
for ser, col in zip(plot.series, (MUTED, BLUE)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
stat(s, 9.0, 2.0, 3.7, "384 → 125", "Ahmedabad's median AQI, official vs cleaned", color=NAVY, value_size=40)
text(s, 9.0, 3.85, 3.7, 2.6, ["Every other city barely moves.",
                              "Without this one fix, any ranking, map or model would have named the wrong city."],
     size=16, color=INK, space_after=10)
text(s, 0.6, 6.55, 8, 0.25, "Median daily AQI, 2015–2020, top 7 cities on official numbers", size=11, color=MUTED)
footer(s, 5)
notes(s, "This chart is the result of that first cleaning step. Grey is the official ranking: Ahmedabad is far "
         "ahead of everyone, at a median AQI of 384. Blue is after cleaning: 125, seventh place. Every other "
         "city barely moves. This is why we spent so much effort on wrangling: one copied column would have "
         "named the wrong city in every chart and model.")

# ----------------------------------------------------------------------------- 6 insight: seasons + weather
s = prs.slides.add_slide(BLANK)
title(s, "North India's winter air carries 3.3× the PM2.5 of its monsoon air", "Insights 2 and 3")
cd = CategoryChartData()
cd.categories = MONTHS
for grp in ("North India", "Other cities", "Coastal cities"):
    cd.add_series(grp, [round(v) for v in season[grp]])
ch = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(0.6), Inches(1.75), Inches(8.0), Inches(4.9), cd).chart
style_chart(ch)
quiet_axes(ch)
for ser, col in zip(ch.plots[0].series, (BLUE, ORANGE, GREEN)):
    ser.format.line.color.rgb = col
    ser.format.line.width = Pt(2.5)
    ser.smooth = False
    ser.marker.style = XL_MARKER_STYLE.CIRCLE
    ser.marker.size = 6
    ser.marker.format.fill.solid()
    ser.marker.format.fill.fore_color.rgb = col
    ser.marker.format.line.color.rgb = col
text(s, 0.6, 6.7, 8, 0.25, "Median PM2.5 (µg/m³) by month, 2015–2020 · India's 24-hour limit is 60", size=11,
     color=MUTED)
stat(s, 9.0, 1.95, 3.7, "148 vs 44", "µg/m³: North India in Nov–Jan vs Jun–Sep. Coastal cities swing only 2.2×.",
     value_size=36)
stat(s, 9.0, 4.0, 3.7, "23%, not 65%", "how much cleaner a heavy-rain day really is, once we compare the same "
                                      "city in the same month", color=BLUE, value_size=36)
footer(s, 6)
notes(s, "Season sets the baseline. In North India the typical winter day has about 148 micrograms of fine "
         "particles, two and a half times the national limit, against 44 in the monsoon. Coastal cities swing "
         "much less. And a non-obvious one: a raw comparison says heavy-rain days are 65 percent cleaner. "
         "But heavy rain mostly falls in the monsoon, which is clean anyway. Comparing the same city in the "
         "same month, the real washout effect is 23 percent. Always control for season before crediting the weather.")

# ----------------------------------------------------------------------------- 7 model A
s = prs.slides.add_slide(BLANK)
title(s, "Model A warns a day ahead and catches 92% of Poor-or-worse days", "Machine learning · classification")
cd = CategoryChartData()
cd.categories = ["Accuracy", "Macro F1", "Poor-or-worse days caught"]
for model in order:
    cd.add_series(model, [round(mtab.loc[model, m], 2) for m in ("Accuracy", "Macro F1", "Poor-or-worse recall")])
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.75), Inches(8.0), Inches(4.9), cd).chart
style_chart(ch)
quiet_axes(ch, value_format="0%", gridlines=False, show_value_axis=False)
plot = ch.plots[0]
plot.gap_width, plot.overlap = 70, -5
plot.has_data_labels = True
plot.data_labels.number_format, plot.data_labels.number_format_is_linked = "0%", False
plot.data_labels.font.size, plot.data_labels.font.color.rgb = Pt(11), INK2
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
for ser, col in zip(plot.series, (MUTED, PALE, RGBColor(0x6D, 0xA7, 0xEC), NAVY)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
text(s, 0.6, 6.7, 8, 0.25, "Unseen test period Jan 2019 – Mar 2020 · time-ordered split, time-series cross-validation",
     size=11, color=MUTED)
card(s, 9.0, 1.95, 3.7, 2.15)
text(s, 9.25, 2.15, 3.3, 1.9, [[("Gradient Boosting ", {"bold": True, "color": NAVY}), ("beats “same as today” on "
                                "accuracy (75% vs 72%) and is right 35% of the time when the category changes, "
                                "where the baseline is always wrong.", {})]], size=14)
card(s, 9.0, 4.3, 3.7, 2.15)
text(s, 9.25, 4.5, 3.3, 1.9, [[("Honest caveat: ", {"bold": True, "color": ORANGE}), ("in the lockdown its macro F1 "
                               "fell to 0.59, below the baseline's 0.65. The rules it learned stopped applying.", {})]],
     size=14)
footer(s, 7)
notes(s, "Model A predicts tomorrow's AQI category, six classes, as an early warning. The baseline is 'tomorrow "
         "will be like today', which is hard to beat because air quality is persistent. We split by time, never "
         "randomly, because a random split leaks the future. Gradient Boosting wins on macro F1 and catches 92 "
         "percent of Poor-or-worse days. Its real value is on the days the category changes. And honestly: "
         "during the lockdown it did worse than the baseline, which shows its limits under a sudden shock.")

# ----------------------------------------------------------------------------- 8 model B
s = prs.slides.add_slide(BLANK)
title(s, "Weather removed, the lockdown cut PM2.5 by 28%, not 41%", "Machine learning · Model B counterfactual")
picture(s, FIG / "13_counterfactual_cities.png", 0.6, 1.75, w=12.1)
ys = 5.55
for i, (v, lab, col) in enumerate([("−41% → −28%", "PM2.5: naive vs weather-adjusted, median of 17 cities", BLUE),
                                   ("−47% → −46%", "NO₂ (mostly traffic): a real drop either way", NAVY),
                                   ("R² 0.55", "placebo test on spring 2019, when nothing happened", MUTED)]):
    text(s, 0.6 + i * 4.1, ys, 3.9, 0.55, v, size=28, bold=True, color=col)
    text(s, 0.6 + i * 4.1, ys + 0.6, 3.9, 0.5, lab, size=13, color=INK2)
footer(s, 8)
notes(s, "Model B is our most original part. It predicts pollution from weather, season, day of week, trend "
         "and city only, never from pollution itself. Fed the real spring-2020 weather, it tells us what "
         "pollution should have been without a lockdown. The black line is reality, blue is the expectation. "
         "Delhi tracks the expectation until 25 March, then falls below it. We trusted it because it passed a "
         "placebo test on spring 2019. Result: PM2.5 fell 28 percent because of the lockdown, not 41. NO2, "
         "which comes from traffic, fell about 46 percent either way.")

# ----------------------------------------------------------------------------- 9 dashboard
s = prs.slides.add_slide(BLANK)
title(s, "The dashboard turns this into five questions a non-expert can explore", "Power BI")
pic = picture(s, FIG / "dashboard_1_overview.png", 0.6, 1.75, w=7.9)
pic.line.color.rgb = GRID
pages = [("Overview", "where and when the air is worst"), ("City explorer", "one city's year, stations, AQI bands"),
         ("Lockdown", "actual vs expected, pick any city"), ("Early warning", "model vs baseline, switch periods"),
         ("Data quality", "every cleaning decision and why")]
for i, (name, sub) in enumerate(pages):
    y = 1.8 + i * 0.93
    badge(s, 8.85, y + 0.05, str(i + 1), fill=BLUE, size=0.42)
    text(s, 9.45, y, 3.4, 0.35, name, size=16, bold=True, color=NAVY)
    text(s, 9.45, y + 0.36, 3.4, 0.4, sub, size=13, color=INK2)
text(s, 0.6, 6.45, 12, 0.35, "Live demo: Breathe_India.pbix · hover a city, drill into Delhi, switch Test → Lockdown",
     size=13, bold=True, color=BLUE)
footer(s, 9)
notes(s, "Now the live demo. On the Overview, 39 percent of days broke the limit; hover a city for its own "
         "profile. On City explorer, pick Delhi: its winters turn dark every year, and Anand Vihar is the worst "
         "station. On Lockdown, switch Delhi to Mumbai: Mumbai barely changed once weather is removed. On Early "
         "warning, switch Test to Lockdown and watch the model fall below the baseline. And the Data quality page "
         "shows every cleaning decision.")

# ----------------------------------------------------------------------------- 10 limits + close
s = prs.slides.add_slide(BLANK)
background(s, NAVY)
title(s, "What we can say, and what we can't", "Limitations and conclusion", dark=True)
text(s, 0.6, 1.9, 5.9, 0.4, "Limitations", size=18, bold=True, color=PALE)
text(s, 0.6, 2.4, 5.9, 3.6, ["Monitors cover parts of 26 cities, not everyone's exposure",
                             "Our AQI corrections are recalculations, not CPCB's own",
                             "Model A uses actual weather as a forecast stand-in",
                             "Model B assumes 2015–19 “normal” would have held in 2020",
                             "Data ends 1 July 2020"], size=15, color=WHITE, space_after=9)
text(s, 7.0, 1.9, 5.7, 0.4, "Takeaways", size=18, bold=True, color=PALE)
text(s, 7.0, 2.4, 5.7, 3.0, ["Season sets the baseline: winter is the problem in the north",
                             "People still matter: −28% PM2.5 and −46% NO₂ without traffic",
                             "Wrangling changed the answer: check the data before trusting a ranking"],
     size=15, color=WHITE, space_after=9)
text(s, 7.0, 4.9, 5.7, 1.1, [[("Contribution: ", {"bold": True, "color": PALE}),
                              ("Mahak led extraction, cleaning and storage; Yash led transformation, the models and "
                               "the dashboard; insights, report and deck together.", {})]], size=13, color=WHITE)
text(s, 0.6, 6.2, 12, 0.6, "Thank you. Questions?", size=26, bold=True, color=WHITE)
footer(s, 10, dark=True)
notes(s, "To close: our data covers monitored parts of 26 cities and ends in mid-2020, and our corrections are "
         "assumptions we documented. Three takeaways: season sets the baseline; people still matter, the lockdown "
         "really cut particles by 28 percent and NO2 by 46; and wrangling changed the answer. Thank you, we're "
         "happy to take questions.")

prs.core_properties.title = "Breathe India: what really drives air pollution in Indian cities?"
prs.core_properties.author = "Mahak Wadhawan, Yash Shah"
prs.save(OUT)
print(f"Saved {OUT} ({len(prs.slides)} slides)")
