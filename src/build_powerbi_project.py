"""
Builds the Breathe India Power BI project (PBIP) from code.

    python src/build_powerbi_project.py

Output: powerbi/BreatheIndia/BreatheIndia.pbip
  - BreatheIndia.SemanticModel  tables loaded from powerbi/data/*.csv, relationships, DAX measures
  - BreatheIndia.Report         5 pages + 1 tooltip page in the PBIR format

Open the .pbip in Power BI Desktop, click Refresh to load the data, then
File > Save as > Power BI file (.pbix). If the project folder moves, update the
DataFolder parameter (Transform data > Edit parameters).
"""

import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "powerbi" / "data"
OUT = ROOT / "powerbi" / "BreatheIndia"
NAME = "BreatheIndia"
BASE_THEME_FILE = ROOT / "powerbi" / "base_theme" / "Fluent2-CY26SU09.json"
CUSTOM_THEME_FILE = ROOT / "powerbi" / "breathe_india_theme.json"
BACKGROUNDS = ROOT / "powerbi" / "backgrounds"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"
VISUAL_SCHEMA = SCHEMA + "item/report/definition/visualContainer/2.12.0/schema.json"
PAGE_SCHEMA = SCHEMA + "item/report/definition/page/2.1.0/schema.json"
VERSION_AT_IMPORT = {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}

INK, INK2, MUTED, BLUE, NAVY, PAGE_BG = "#0B0B0B", "#52514E", "#898781", "#2A78D6", "#0D366B", "#F4F3EF"
AQI_ORDER = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
AQI_COLORS = ["#EEA07C", "#E27B52", "#CF5A31", "#AD3F1D", "#832A12", "#561A0B"]


def lid():
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"breathe-india/{next(_counter)}"))


def _count():
    i = 0
    while True:
        i += 1
        yield i


_counter = _count()


# =====================================================================================
# Semantic model (TMSL, model.bim)
# =====================================================================================

TABLES = ["dim_city", "dim_date", "dim_station", "dim_aqi_category", "fact_city_day", "ml_predictions",
          "ml_confusion", "ml_model_metrics", "ml_feature_importance", "ml_counterfactual",
          "ml_lockdown_effect", "cleaning_log", "data_quality"]
DATE_COLUMNS = {"Date", "first_date", "last_date", "YearMonth"}

FACT_VISIBLE = {"City", "Date", "PM25", "PM10", "NO2", "SO2", "CO", "O3", "NH3", "AQI_clean", "AQI_official",
                "AQI_Bucket_clean", "aqi_source", "dominant_pollutant", "temp_mean", "precip_mm", "humidity",
                "wind_max_kmh", "Region", "city_group", "Season", "pm_fault_flag", "episode_flag"}
HIDDEN = {
    "dim_city": {"elevation_m", "pm25_level", "seasonality", "aqi_days"},
    "dim_date": {"DayOfWeekNum", "SeasonOrder", "days_from_diwali"},
    "dim_aqi_category": {"rank", "color"},
    "ml_predictions": {"actual_category_rank", "predicted_category_rank", "baseline_category_rank"},
    "ml_confusion": {"actual_rank", "predicted_rank"},
}
SORT_BY = {("dim_date", "MonthName"): "Month", ("dim_date", "Season"): "SeasonOrder",
           ("dim_date", "DayOfWeek"): "DayOfWeekNum", ("dim_aqi_category", "category"): "rank",
           ("ml_confusion", "actual"): "actual_rank", ("ml_confusion", "predicted"): "predicted_rank"}
CATEGORY = {("dim_city", "latitude"): "Latitude", ("dim_city", "longitude"): "Longitude",
            ("dim_city", "City"): "City", ("dim_city", "State"): "StateOrProvince"}

RELATIONSHIPS = [
    ("fact_city_day", "City", "dim_city", "City"),
    ("fact_city_day", "Date", "dim_date", "Date"),
    ("fact_city_day", "AQI_Bucket_clean", "dim_aqi_category", "category"),
    ("dim_station", "City", "dim_city", "City"),
    ("ml_predictions", "City", "dim_city", "City"),
    ("ml_predictions", "Date", "dim_date", "Date"),
    ("ml_counterfactual", "City", "dim_city", "City"),
    ("ml_counterfactual", "Date", "dim_date", "Date"),
    ("ml_lockdown_effect", "City", "dim_city", "City"),
]

# name: (DAX, format string)
MEASURES = {
    "Days Measured": ("COUNT ( fact_city_day[PM25] )", "#,0"),
    "Cities": ("DISTINCTCOUNT ( fact_city_day[City] )", "0"),
    "Median PM2.5": ("MEDIAN ( fact_city_day[PM25] )", "0"),
    "Median AQI": ("MEDIAN ( fact_city_day[AQI_clean] )", "0"),
    "Median Official AQI": ("MEDIAN ( fact_city_day[AQI_official] )", "0"),
    "% Days Above Standard": (
        "DIVIDE ( CALCULATE ( COUNTROWS ( fact_city_day ), fact_city_day[PM25] > 60 ), [Days Measured] )", "0%"),
    "% Days Poor or Worse": (
        "DIVIDE (\n    CALCULATE ( COUNTROWS ( fact_city_day ), fact_city_day[AQI_clean] > 200 ),\n"
        "    CALCULATE ( COUNTROWS ( fact_city_day ), NOT ISBLANK ( fact_city_day[AQI_clean] ) )\n)", "0%"),
    "Winter vs Monsoon": (
        "DIVIDE (\n    CALCULATE ( [Median PM2.5], dim_date[Month] IN { 11, 12, 1 } ),\n"
        "    CALCULATE ( [Median PM2.5], dim_date[Month] IN { 6, 7, 8, 9 } )\n)", "0.0"),
    "Worst City": (
        "VAR t = ADDCOLUMNS ( VALUES ( dim_city[City] ), \"@share\", [% Days Above Standard] )\n"
        "RETURN MAXX ( TOPN ( 1, FILTER ( t, NOT ISBLANK ( [@share] ) ), [@share], DESC ), dim_city[City] )", None),
    "Worst Month": (
        "VAR t = ADDCOLUMNS ( VALUES ( dim_date[MonthName] ), \"@pm\", [Median PM2.5] )\n"
        "RETURN MAXX ( TOPN ( 1, FILTER ( t, NOT ISBLANK ( [@pm] ) ), [@pm], DESC ), dim_date[MonthName] )", None),
    "Main Pollutant": (
        "VAR t = ADDCOLUMNS (\n    FILTER ( VALUES ( fact_city_day[dominant_pollutant] ), "
        "NOT ISBLANK ( fact_city_day[dominant_pollutant] ) ),\n    \"@n\", CALCULATE ( COUNTROWS ( fact_city_day ) )\n)\n"
        "RETURN MAXX ( TOPN ( 1, t, [@n], DESC ), fact_city_day[dominant_pollutant] )", None),
    "Days": ("COUNTROWS ( fact_city_day )", "#,0"),
    "PM2.5 (7-day avg)": (
        "AVERAGEX ( DATESINPERIOD ( dim_date[Date], MAX ( dim_date[Date] ), -7, DAY ), [Median PM2.5] )", "0"),
    "City Narrative": (
        "VAR c = SELECTEDVALUE ( dim_city[City], \"All 26 cities\" )\nRETURN\n"
        "    c & \": \" & FORMAT ( [% Days Above Standard], \"0%\" ) & \" of days over the PM2.5 limit\"\n"
        "        & \" · worst in \" & [Worst Month]", None),
    "Days in AQI Band": (
        "CALCULATE ( COUNTROWS ( fact_city_day ), KEEPFILTERS ( NOT ISBLANK ( fact_city_day[AQI_Bucket_clean] ) ) )",
        "#,0"),
    "Median AQI Colour": (
        "VAR a = [Median AQI]\nRETURN\n    SWITCH (\n        TRUE (),\n        ISBLANK ( a ), \"#E1E0D9\",\n"
        "        a <= 50, \"#EEA07C\",\n        a <= 100, \"#E27B52\",\n        a <= 200, \"#CF5A31\",\n"
        "        a <= 300, \"#AD3F1D\",\n        a <= 400, \"#832A12\",\n        \"#561A0B\"\n    )", None),
    "Station PM2.5": ("AVERAGE ( dim_station[pm25_mean] )", "0"),
    "Station % Above Standard": ("AVERAGE ( dim_station[share_days_above_naaqs] )", "0%"),
    # lockdown counterfactual
    "Actual": ("AVERAGE ( ml_counterfactual[actual] )", "0"),
    "Expected Without Lockdown": ("AVERAGE ( ml_counterfactual[predicted_bau] )", "0"),
    "Band Low": ("AVERAGE ( ml_counterfactual[band_low] )", "0"),
    "Band High": ("AVERAGE ( ml_counterfactual[band_high] )", "0"),
    "Actual (7-day)": (
        "AVERAGEX ( DATESINPERIOD ( dim_date[Date], MAX ( dim_date[Date] ), -7, DAY ), [Actual] )", "0"),
    "Expected (7-day)": (
        "AVERAGEX ( DATESINPERIOD ( dim_date[Date], MAX ( dim_date[Date] ), -7, DAY ), [Expected Without Lockdown] )",
        "0"),
    "Band Low (7-day)": (
        "AVERAGEX ( DATESINPERIOD ( dim_date[Date], MAX ( dim_date[Date] ), -7, DAY ), [Band Low] )", "0"),
    "Band High (7-day)": (
        "AVERAGEX ( DATESINPERIOD ( dim_date[Date], MAX ( dim_date[Date] ), -7, DAY ), [Band High] )", "0"),
    "Naive Change": ("DIVIDE ( MEDIAN ( ml_lockdown_effect[naive_change_pct] ), 100 )", "0%"),
    "Weather-Adjusted Change": ("DIVIDE ( MEDIAN ( ml_lockdown_effect[weather_adjusted_change_pct] ), 100 )", "0%"),
    "PM2.5 Drop (Naive)": ("CALCULATE ( [Naive Change], ml_lockdown_effect[pollutant] = \"PM25\" )", "0%"),
    "PM2.5 Drop (Weather-Adjusted)": (
        "CALCULATE ( [Weather-Adjusted Change], ml_lockdown_effect[pollutant] = \"PM25\" )", "0%"),
    "NO2 Drop (Weather-Adjusted)": (
        "CALCULATE ( [Weather-Adjusted Change], ml_lockdown_effect[pollutant] = \"NO2\" )", "0%"),
    "Weather Share of PM2.5 Drop": (
        "1 - DIVIDE ( [PM2.5 Drop (Weather-Adjusted)], [PM2.5 Drop (Naive)] )", "0%"),
    # early-warning model
    "Model Accuracy": ("AVERAGE ( ml_predictions[model_correct] )", "0%"),
    "Baseline Accuracy": ("AVERAGE ( ml_predictions[baseline_correct] )", "0%"),
    "Accuracy Gain": ("[Model Accuracy] - [Baseline Accuracy]", "+0.0%;-0.0%"),
    "Poor+ Recall (Model)": (
        "DIVIDE (\n    CALCULATE ( COUNTROWS ( ml_predictions ), ml_predictions[actual_category_rank] >= 4, "
        "ml_predictions[predicted_category_rank] >= 4 ),\n"
        "    CALCULATE ( COUNTROWS ( ml_predictions ), ml_predictions[actual_category_rank] >= 4 )\n)", "0%"),
    "Poor+ Recall (Baseline)": (
        "DIVIDE (\n    CALCULATE ( COUNTROWS ( ml_predictions ), ml_predictions[actual_category_rank] >= 4, "
        "ml_predictions[baseline_category_rank] >= 4 ),\n"
        "    CALCULATE ( COUNTROWS ( ml_predictions ), ml_predictions[actual_category_rank] >= 4 )\n)", "0%"),
    "Accuracy On Change Days": (
        "CALCULATE (\n    [Model Accuracy],\n"
        "    FILTER ( ml_predictions, ml_predictions[actual_category] <> ml_predictions[baseline_category] )\n)", "0%"),
    "Actual Category": ("AVERAGE ( ml_predictions[actual_category_rank] )", "0"),
    "Predicted Category": ("AVERAGE ( ml_predictions[predicted_category_rank] )", "0"),
    "Confusion Days": ("SUM ( ml_confusion[days] )", "#,0"),
    "Confusion Row %": (
        "DIVIDE (\n    [Confusion Days],\n"
        "    CALCULATE ( [Confusion Days], REMOVEFILTERS ( ml_confusion[predicted], ml_confusion[predicted_rank] ) )\n)",
        "0%"),
    "Metric Value": ("AVERAGE ( ml_model_metrics[value] )", "0.00"),
    "Importance": ("SUM ( ml_feature_importance[importance] )", "0.000"),
    # data quality
    "Cleaning Steps": ("COUNTROWS ( cleaning_log )", "0"),
    "AQI Values Rebuilt": (
        "CALCULATE ( COUNTROWS ( fact_city_day ), NOT fact_city_day[aqi_source] IN { \"official\", \"missing\" } )",
        "#,0"),
    "Sensor Faults Removed": ("SUM ( fact_city_day[pm_fault_flag] )", "#,0"),
    "Missing Before %": ("DIVIDE ( AVERAGE ( data_quality[missing_raw_pct] ), 100 )", "0%"),
    "Missing After %": ("DIVIDE ( AVERAGE ( data_quality[missing_clean_pct] ), 100 )", "0%"),
}
TEXT_MEASURES = {"Worst City", "Worst Month", "Main Pollutant", "City Narrative", "Median AQI Colour"}


def model_column(table, col, dtype):
    if col in DATE_COLUMNS:
        data_type, m_type = "dateTime", "type date"
    elif pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
        data_type, m_type = "int64", "Int64.Type"
    elif pd.api.types.is_float_dtype(dtype):
        data_type, m_type = "double", "type number"
    else:
        data_type, m_type = "string", "type text"
    c = {"name": col, "dataType": data_type, "sourceColumn": col, "summarizeBy": "none", "lineageTag": lid()}
    if data_type == "dateTime":
        c["formatString"] = "mmm yyyy" if col == "YearMonth" else "dd mmm yyyy"
        c["annotations"] = [{"name": "UnderlyingDateTimeDataType", "value": "Date"}]
    if table == "dim_date" and col == "Date":
        c["isKey"] = True
    hidden = HIDDEN.get(table, set())
    if (table == "fact_city_day" and col not in FACT_VISIBLE) or col in hidden:
        c["isHidden"] = True
    if (table, col) in SORT_BY:
        c["sortByColumn"] = SORT_BY[(table, col)]
    if (table, col) in CATEGORY:
        c["dataCategory"] = CATEGORY[(table, col)]
    return c, m_type


def build_table(table):
    df = pd.read_csv(DATA / f"{table}.csv", nrows=2000)
    cols, typed = [], []
    for col in df.columns:
        c, m_type = model_column(table, col, df[col].dtype)
        cols.append(c)
        typed.append(f'{{"{col}", {m_type}}}')
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), '
        '[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        '    Nulls = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, Table.ColumnNames(Promoted)),',
        f'    Typed = Table.TransformColumnTypes(Nulls, {{{", ".join(typed)}}}, "en-US")',
        "in",
        "    Typed",
    ]
    t = {"name": table, "lineageTag": lid(), "columns": cols,
         "partitions": [{"name": table, "mode": "import", "source": {"type": "m", "expression": m}}],
         "annotations": [{"name": "PBI_ResultType", "value": "Table"}]}
    if table == "dim_date":
        t["dataCategory"] = "Time"
    return t


def build_model():
    tables = [build_table(t) for t in TABLES]
    measures = []
    for name, (dax, fmt) in MEASURES.items():
        m = {"name": name, "expression": dax.split("\n") if "\n" in dax else dax, "lineageTag": lid()}
        if fmt:
            m["formatString"] = fmt
        measures.append(m)
    tables.insert(0, {
        "name": "_Measures", "lineageTag": lid(),
        "columns": [{"type": "calculatedTableColumn", "name": "x", "dataType": "int64", "isNameInferred": True,
                     "isDataTypeInferred": True, "isHidden": True, "sourceColumn": "[x]", "summarizeBy": "none",
                     "lineageTag": lid()}],
        "partitions": [{"name": "_Measures", "mode": "import",
                        "source": {"type": "calculated", "expression": 'ROW ( "x", 0 )'}}],
        "measures": measures,
    })
    folder = str(DATA) + "\\"
    return {
        "compatibilityLevel": 1606,
        "model": {
            "culture": "en-IN",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-IN",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "tables": tables,
            "relationships": [{"name": lid(), "fromTable": f, "fromColumn": fc, "toTable": t, "toColumn": tc}
                              for f, fc, t, tc in RELATIONSHIPS],
            "expressions": [{
                "name": "DataFolder", "kind": "m", "lineageTag": lid(),
                "expression": f'"{folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                "annotations": [{"name": "PBI_ResultType", "value": "Text"}],
            }],
            "annotations": [
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                {"name": "PBI_ProTooling", "value": '["DevMode"]'},
                {"name": "PBI_QueryOrder", "value": json.dumps(["DataFolder"] + TABLES)},
            ],
        },
    }


# =====================================================================================
# Report helpers (PBIR)
# =====================================================================================

def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def s(text):
    return lit("'" + str(text).replace("'", "''") + "'")


def n(x):
    return lit(f"{x}D")


def b(flag):
    return lit("true" if flag else "false")


def fill(hex_color):
    return {"solid": {"color": s(hex_color)}}


def M(measure):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": measure}}


def C(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def proj(field, display=None):
    if "Measure" in field:
        ent, prop = "_Measures", field["Measure"]["Property"]
    else:
        ent, prop = field["Column"]["Expression"]["SourceRef"]["Entity"], field["Column"]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


def roles(**kw):
    return {"queryState": {role: {"projections": items} for role, items in kw.items()}}


def title_vco(text, show=True, size=12):
    t = {"show": b(show)}
    if show:
        t.update({"text": s(text), "fontSize": n(size), "fontColor": fill(INK)})
    return {"title": [{"properties": t}], "subTitle": [{"properties": {"show": b(False)}}]}


def categorical_filter(table, column, values, name):
    return {
        "name": name,
        "field": C(table, column),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                "Values": [[{"Literal": {"Value": "'" + v + "'"}}] for v in values]}}}],
        },
        "howCreated": "User",
    }


def visual(name, pos, vtype, query=None, objects=None, vco=None, filters=None, z=1000):
    x, y, w, h = pos
    v = {"visualType": vtype}
    if query:
        v["query"] = query
    if objects:
        v["objects"] = objects
    if vco:
        v["visualContainerObjects"] = vco
    v["drillFilterOtherVisuals"] = True
    out = {"$schema": VISUAL_SCHEMA, "name": name,
           "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": v}
    if filters:
        out["filterConfig"] = {"filters": filters}
    return out


def textbox(name, pos, paragraphs):
    paras = []
    for p in paragraphs:
        runs = []
        for text, style in p:
            ts = {"fontFamily": "Segoe UI", "fontSize": "11pt", "color": INK2}
            ts.update(style)
            runs.append({"value": text, "textStyle": ts})
        paras.append({"textRuns": runs, "horizontalTextAlignment": "left"})
    return visual(name, pos, "textbox", objects={"general": [{"properties": {"paragraphs": paras}}]},
                  vco={"background": [{"properties": {"show": b(False)}}],
                       "border": [{"properties": {"show": b(False)}}]})


def kpi_cards(name, pos, items, value_size=24):
    """items: list of (measure, label)"""
    return visual(name, pos, "cardVisual",
                  query=roles(Data=[proj(M(m), label) for m, label in items]),
                  objects={"value": [{"properties": {"fontSize": n(value_size), "fontColor": fill(INK)},
                                      "selector": {"id": "default"}}],
                           "label": [{"properties": {"fontSize": n(10), "fontColor": fill(INK2)},
                                      "selector": {"id": "default"}}]},
                  vco=title_vco("", show=False))


def text_card(name, pos, measure, size=12):
    return visual(name, pos, "cardVisual", query=roles(Data=[proj(M(measure))]),
                  objects={"value": [{"properties": {"fontSize": n(size), "fontColor": fill(INK), "textWrap": b(True),
                                                     "horizontalAlignment": s("left")},
                                      "selector": {"id": "default"}}],
                           "label": [{"properties": {"show": b(False)}, "selector": {"id": "default"}}]},
                  vco=title_vco("", show=False))


def slicer(name, pos, table, column, header, single=False, default=None):
    objects = {"data": [{"properties": {"mode": s("Dropdown")}}],
               "header": [{"properties": {"show": b(True), "text": s(header)}}]}
    if single:
        objects["selection"] = [{"properties": {"singleSelect": b(True)}}]
    if default:
        objects["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2, "From": [{"Name": "s", "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": column}}],
                "Values": [[{"Literal": {"Value": f"'{default}'"}}]]}}}]}}}}]
    return visual(name, pos, "slicer", query=roles(Values=[proj(C(table, column))]), objects=objects,
                  vco={"padding": [{"properties": {k: n(8) for k in ("top", "bottom", "left", "right")}}]})


def navigator(name):
    # Wide enough that the bold label of the current page ("City explorer") is not cut off.
    return visual(name, (600, 22, 656, 34), "pageNavigator",
                  objects={
                      "text": [{"properties": {"fontColor": fill("#FFFFFF"), "fontSize": n(10)},
                                "selector": {"id": "default"}},
                               {"properties": {"fontColor": fill("#FFFFFF"), "fontSize": n(10), "bold": b(True)},
                                "selector": {"id": "selected"}}],
                      "fill": [{"properties": {"show": b(True), "fillColor": fill("#FFFFFF"), "transparency": n(90)},
                                "selector": {"id": "default"}},
                               {"properties": {"show": b(True), "fillColor": fill(BLUE), "transparency": n(0)},
                                "selector": {"id": "selected"}}],
                      "outline": [{"properties": {"show": b(False)}, "selector": {"id": "default"}}],
                      "pages": [{"properties": {"showHiddenPages": b(False), "showTooltipPages": b(False)}}],
                  },
                  vco={"background": [{"properties": {"show": b(False)}}],
                       "border": [{"properties": {"show": b(False)}}],
                       "title": [{"properties": {"show": b(False)}}]}, z=5000)


def series_colors(measure_colors):
    """Per-measure colors for charts with several measures in Y."""
    return [{"properties": {"fill": fill(color)}, "selector": {"metadata": f"_Measures.{m}"}}
            for m, color in measure_colors]


def category_colors(table, column, value_colors):
    return [{"properties": {"fill": fill(color)},
             "selector": {"data": [{"scopeId": {"Comparison": {
                 "ComparisonKind": 0, "Left": C(table, column), "Right": {"Literal": {"Value": f"'{v}'"}}}}}]}}
            for v, color in value_colors]


def gradient_values(measure, lo="#F2F7FD", hi="#5598E7"):
    return [{"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {
        "Input": M(measure),
        "FillRule": {"linearGradient2": {"min": {"color": {"Literal": {"Value": f"'{lo}'"}}},
                                         "max": {"color": {"Literal": {"Value": f"'{hi}'"}}},
                                         "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}}}}},
             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"_Measures.{measure}"}}]


def tooltip_page_vco(page="citytip"):
    return {"visualTooltip": [{"properties": {"show": b(True), "type": s("Canvas"), "section": s(page)}}]}


def ref_line(value, label, color=MUTED, axis="y1AxisReferenceLine"):
    return {axis: [{"properties": {"show": b(True), "displayName": s(label), "value": n(value),
                                   "lineColor": fill(color), "style": s("dashed"), "transparency": n(0),
                                   "dataLabelShow": b(True), "dataLabelColor": fill(INK2),
                                   "dataLabelText": s("Name"), "dataLabelHorizontalPosition": s("left")},
                    "selector": {"id": "1"}}]}


# =====================================================================================
# Pages
# =====================================================================================

def page_overview():
    vs = [navigator("ov_nav"),
          kpi_cards("ov_kpis", (24, 88, 840, 96), [
              ("Cities", "Cities monitored"), ("Days Measured", "City-days with PM2.5 data"),
              ("Median PM2.5", "Typical PM2.5 (µg/m³)"), ("% Days Above Standard", "Days above PM2.5 limit")]),
          slicer("ov_year", (876, 88, 184, 96), "dim_date", "Year", "Year"),
          slicer("ov_region", (1072, 88, 184, 96), "dim_city", "Region", "Region")]
    def avg(table, column, label):
        return {"field": {"Aggregation": {"Expression": C(table, column), "Function": 1}},
                "queryRef": f"Avg({table}.{column})", "nativeQueryRef": f"Average of {column}", "displayName": label}

    m = visual("ov_map", (24, 196, 404, 490), "scatterChart",
               query=roles(Category=[proj(C("dim_city", "City"))],
                           X=[avg("dim_city", "longitude", "Longitude")],
                           Y=[avg("dim_city", "latitude", "Latitude")],
                           Size=[proj(M("Median PM2.5"))],
                           Series=[proj(C("dim_city", "cluster"), "Air type")],
                           Tooltips=[proj(M("% Days Above Standard")), proj(M("Worst Month"))]),
               objects={"categoryAxis": [{"properties": {"show": b(False), "showAxisTitle": b(False),
                                                          "gridlineShow": b(False)}}],
                        "valueAxis": [{"properties": {"show": b(False), "showAxisTitle": b(False),
                                                       "gridlineShow": b(False)}}],
                        "bubbles": [{"properties": {"bubbleSize": lit("-12L")}}],
                        "categoryLabels": [{"properties": {"show": b(True), "fontSize": n(8), "color": fill(INK2)}}],
                        "legend": [{"properties": {"show": b(True), "position": s("Bottom"), "fontSize": n(8)}}],
                        "dataPoint": category_colors("dim_city", "cluster", [
                            ("High all year", BLUE), ("Clean monsoon, smoggy winter", "#EB6834"),
                            ("Steady year-round", "#1BAF7A"), ("Not enough data", "#C3C2B7")])},
               vco={**title_vco("Where the air is worst (bubble = typical PM2.5)"),
                    **tooltip_page_vco()})
    line = visual("ov_season", (440, 196, 816, 236), "lineChart",
                  query=roles(Category=[proj(C("dim_date", "MonthName"), "Month")],
                              Y=[proj(M("Median PM2.5"))],
                              Series=[proj(C("fact_city_day", "city_group"), "City group")]),
                  objects={**ref_line(60, "National limit (60)"),
                           "legend": [{"properties": {"show": b(True), "position": s("Top")}}],
                           "lineStyles": [{"properties": {"strokeWidth": lit("2L"), "showMarker": b(True)}}],
                           "dataPoint": category_colors("fact_city_day", "city_group", [
                               ("North India", BLUE), ("Other cities", "#EB6834"), ("Coastal cities", "#1BAF7A")])},
                  vco=title_vco("North India's winter air is about 3x dirtier than its monsoon air"))
    bar = visual("ov_rank", (440, 444, 480, 242), "clusteredBarChart",
                 query={**roles(Category=[proj(C("dim_city", "City"))], Y=[proj(M("% Days Above Standard"))]),
                        "sortDefinition": {"sort": [{"field": M("% Days Above Standard"), "direction": "Descending"}],
                                           "isDefaultSort": False}},
                 objects={"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": M("Median AQI Colour")}}}},
                                         "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                          "labels": [{"properties": {"show": b(True), "fontSize": n(9)}}]},
                 vco={**title_vco("Delhi and Gurugram break the limit on 7 days in 10"), **tooltip_page_vco()})
    note = textbox("ov_note", (932, 444, 324, 242), [
        [("What this page says", {"fontFamily": "Segoe UI Semibold", "fontSize": "12pt", "color": INK})],
        [("Across 26 cities, PM2.5 broke India's daily limit on ", {}), ("39% of measured days.", {"fontWeight": "bold"})],
        [("The worst air is in the north (Delhi, Gurugram, Patna, Lucknow) and it peaks in ", {}),
         ("November–January", {"fontWeight": "bold"}),
         (", when crop burning, cold still air and festival fireworks combine.", {})],
        [("Hover a city for its profile. Use City explorer for the detail.", {"color": MUTED, "fontSize": "10pt"})],
    ])
    return vs + [m, line, bar, note]


def page_cities():
    vs = [navigator("ct_nav")]
    matrix = visual("ct_matrix", (24, 88, 544, 598), "pivotTable",
                    query=roles(Rows=[proj(C("dim_city", "City"))], Columns=[proj(C("dim_date", "MonthName"), "Month")],
                                Values=[proj(M("Median PM2.5"))]),
                    objects={"values": gradient_values("Median PM2.5") + [
                                 {"properties": {"fontSize": n(8), "fontColor": fill(INK)}}],
                             "columnHeaders": [{"properties": {"fontSize": n(8)}}],
                             "rowHeaders": [{"properties": {"fontSize": n(8)}}],
                             "subTotals": [{"properties": {"rowSubtotals": b(False), "columnSubtotals": b(False)}}]},
                    vco=title_vco("Each city's seasonal fingerprint (median PM2.5) · click a city to filter"))
    city = slicer("ct_city", (580, 88, 176, 80), "dim_city", "City", "City")
    narrative = text_card("ct_narrative", (768, 88, 488, 80), "City Narrative", size=11)
    kpis = kpi_cards("ct_kpis", (580, 180, 676, 84), [
        ("Median AQI", "Typical AQI"), ("% Days Poor or Worse", "Days Poor or worse"),
        ("Main Pollutant", "Usually sets the AQI"), ("Worst Month", "Worst month")], value_size=20)
    stacked = visual("ct_bands", (580, 276, 676, 176), "hundredPercentStackedColumnChart",
                     query=roles(Category=[proj(C("dim_date", "Year"))], Y=[proj(M("Days in AQI Band"), "Days")],
                                 Series=[proj(C("dim_aqi_category", "category"), "AQI category")]),
                     objects={"dataPoint": category_colors("dim_aqi_category", "category",
                                                           list(zip(AQI_ORDER, AQI_COLORS))),
                              "legend": [{"properties": {"show": b(True), "position": s("Top")}}]},
                     vco=title_vco("How many days fell in each AQI band, by year"))
    daily = visual("ct_daily", (580, 464, 400, 222), "lineChart",
                   query=roles(Category=[proj(C("dim_date", "Date"))], Y=[proj(M("PM2.5 (7-day avg)"))]),
                   objects={**ref_line(60, "Limit"),
                            "dataPoint": series_colors([("PM2.5 (7-day avg)", BLUE)]),
                            "categoryAxis": [{"properties": {"axisType": s("Scalar")}}]},
                   vco=title_vco("PM2.5, 7-day average"))
    stations = visual("ct_stations", (992, 464, 264, 222), "tableEx",
                      query={**roles(Values=[proj(C("dim_station", "station_place"), "Station"),
                                             proj(M("Station PM2.5"), "PM2.5")]),
                             "sortDefinition": {"sort": [{"field": M("Station PM2.5"), "direction": "Descending"}],
                                                "isDefaultSort": False}},
                      objects={"columnHeaders": [{"properties": {"autoSizeColumnWidth": b(False),
                                                                 "columnAdjustment": s("fixedWidth"),
                                                                 "fontSize": n(9)}}],
                               "columnWidth": [
                                   {"properties": {"value": n(178)}, "selector": {"metadata": "dim_station.station_place"}},
                                   {"properties": {"value": n(48)}, "selector": {"metadata": "_Measures.Station PM2.5"}}],
                               "values": [{"properties": {"fontSize": n(9), "wordWrap": b(True)}}],
                               "total": [{"properties": {"totals": b(False)}}]},
                      vco=title_vco("Worst monitoring stations (mean PM2.5)"))
    return vs + [matrix, city, narrative, kpis, stacked, daily, stations]


def page_lockdown():
    vs = [navigator("lk_nav"),
          kpi_cards("lk_kpis", (24, 88, 840, 96), [
              ("PM2.5 Drop (Naive)", "PM2.5 vs 2019"),
              ("PM2.5 Drop (Weather-Adjusted)", "PM2.5, weather removed"),
              ("Weather Share of PM2.5 Drop", "Drop due to weather"),
              ("NO2 Drop (Weather-Adjusted)", "NO₂, weather removed")]),
          slicer("lk_city", (876, 88, 184, 96), "dim_city", "City", "City", single=True, default="Delhi"),
          slicer("lk_pollutant", (1072, 88, 184, 96), "ml_counterfactual", "pollutant", "Pollutant", single=True,
                 default="PM25")]
    line = visual("lk_line", (24, 196, 820, 360), "lineChart",
                  query=roles(Category=[proj(C("dim_date", "Date"))],
                              Y=[proj(M("Actual (7-day)"), "Actual"),
                                 proj(M("Expected (7-day)"), "Expected without lockdown"),
                                 proj(M("Band High (7-day)"), "80% band (upper)"),
                                 proj(M("Band Low (7-day)"), "80% band (lower)")]),
                  objects={"dataPoint": series_colors([("Actual (7-day)", INK), ("Expected (7-day)", BLUE),
                                                       ("Band High (7-day)", "#9EC5F4"),
                                                       ("Band Low (7-day)", "#9EC5F4")]),
                           "lineStyles": [{"properties": {"strokeWidth": n(1), "lineStyle": s("dashed")},
                                           "selector": {"metadata": f"_Measures.{m}"}}
                                          for m in ("Band High (7-day)", "Band Low (7-day)")],
                           "xAxisReferenceLine": [{"properties": {
                               "show": b(True), "displayName": s("Lockdown begins"),
                               "value": lit("datetime'2020-03-25T00:00:00'"), "lineColor": fill(MUTED),
                               "style": s("dashed"), "dataLabelShow": b(True), "dataLabelColor": fill(INK2)},
                               "selector": {"id": "1"}}],
                           "categoryAxis": [{"properties": {"axisType": s("Scalar")}}],
                           "legend": [{"properties": {"show": b(True), "position": s("Top")}}]},
                  vco=title_vco("Actual vs expected without lockdown, 2020 (pick a city and pollutant)"),
                  filters=[{"name": "lk_year", "field": C("dim_date", "Year"), "type": "Categorical",
                            "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
                                       "Where": [{"Condition": {"In": {
                                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                                       "Property": "Year"}}],
                                           "Values": [[{"Literal": {"Value": "2020L"}}]]}}}]},
                            "howCreated": "User"}])
    note = textbox("lk_note", (24, 568, 820, 118), [
        [("Comparing spring 2020 with spring 2019 says PM2.5 fell ", {}), ("41%", {"fontWeight": "bold"}),
         (". But spring 2020 also had kinder weather. Our model, trained on 2015–2019, predicts what pollution "
          "should have been given the actual weather. Against that, the real lockdown effect was ", {}),
         ("−28%", {"fontWeight": "bold"}), (": about ", {}), ("a third of the headline drop was weather", {"fontWeight": "bold"}),
         (". NO₂, mostly from traffic, fell ", {}), ("46%", {"fontWeight": "bold"}), (" either way.", {})],
    ])
    bar = visual("lk_bar", (856, 196, 400, 490), "clusteredBarChart",
                 query={**roles(Category=[proj(C("ml_lockdown_effect", "City"))],
                                Y=[proj(M("Naive Change"), "Naive (2020 vs 2019)"),
                                   proj(M("Weather-Adjusted Change"), "Weather-adjusted")]),
                        "sortDefinition": {"sort": [{"field": M("Weather-Adjusted Change"), "direction": "Ascending"}],
                                           "isDefaultSort": False}},
                 objects={"dataPoint": series_colors([("Naive Change", MUTED), ("Weather-Adjusted Change", BLUE)]),
                          "legend": [{"properties": {"show": b(True), "position": s("Top")}}]},
                 vco=title_vco("PM2.5 change by city: weather made most drops look bigger"),
                 filters=[categorical_filter("ml_lockdown_effect", "pollutant", ["PM25"], "lk_pm25only")])
    return vs + [line, note, bar]


def page_forecast():
    vs = [navigator("fc_nav"),
          kpi_cards("fc_kpis", (24, 88, 1012, 96), [
              ("Model Accuracy", "Model: exact category"), ("Baseline Accuracy", "Baseline ('same as today')"),
              ("Poor+ Recall (Model)", "Poor-or-worse days caught"),
              ("Accuracy On Change Days", "Right when the category changes")]),
          slicer("fc_split", (1048, 88, 208, 96), "ml_predictions", "split", "Evaluation period", single=True,
                 default="Test")]
    cm = visual("fc_confusion", (24, 196, 420, 300), "pivotTable",
                query=roles(Rows=[proj(C("ml_confusion", "actual"), "Actual")],
                            Columns=[proj(C("ml_confusion", "predicted"), "Predicted")],
                            Values=[proj(M("Confusion Row %"), "Share of days")]),
                objects={"values": gradient_values("Confusion Row %") + [
                    {"properties": {"fontSize": n(9), "fontColor": fill(INK)}}],
                         "columnHeaders": [{"properties": {"fontSize": n(9)}}],
                         "rowHeaders": [{"properties": {"fontSize": n(9)}}],
                         "subTotals": [{"properties": {"rowSubtotals": b(False), "columnSubtotals": b(False)}}]},
                vco=title_vco("Where predictions land (row % of actual days, test period)"))
    imp = visual("fc_importance", (456, 196, 380, 300), "clusteredBarChart",
                 query={**roles(Category=[proj(C("ml_feature_importance", "label"), "Feature")],
                                Y=[proj(M("Importance"))]),
                        "sortDefinition": {"sort": [{"field": M("Importance"), "direction": "Descending"}],
                                           "isDefaultSort": False}},
                 objects={"dataPoint": series_colors([("Importance", BLUE)])},
                 vco=title_vco("What the model relies on (top 10 inputs)"),
                 filters=[{"name": "fc_top10", "field": C("ml_feature_importance", "label"), "type": "TopN",
                           "filter": {"Version": 2, "From": [
                               {"Name": "subquery", "Type": 2, "Expression": {"Subquery": {"Query": {
                                   "Version": 2, "From": [{"Name": "f", "Entity": "ml_feature_importance", "Type": 0}],
                                   "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}},
                                                          "Property": "label"}, "Name": "field"}],
                                   "OrderBy": [{"Direction": 2, "Expression": {"Aggregation": {
                                       "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "f"}},
                                                                 "Property": "importance"}}, "Function": 0}}}],
                                   "Top": 10}}}},
                               {"Name": "f", "Entity": "ml_feature_importance", "Type": 0}],
                               "Where": [{"Condition": {"In": {
                                   "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}},
                                                               "Property": "label"}}],
                                   "Table": {"SourceRef": {"Source": "subquery"}}}}}]},
                           "howCreated": "User"}])
    comp = visual("fc_models", (848, 196, 408, 300), "clusteredBarChart",
                  query={**roles(Category=[proj(C("ml_model_metrics", "model"), "Model")], Y=[proj(M("Metric Value"), "Macro F1")]),
                         "sortDefinition": {"sort": [{"field": M("Metric Value"), "direction": "Descending"}],
                                            "isDefaultSort": False}},
                  objects={"dataPoint": series_colors([("Metric Value", BLUE)]),
                           "labels": [{"properties": {"show": b(True), "fontSize": n(9)}}]},
                  vco=title_vco("Macro F1 on unseen 2019–20 data: Gradient Boosting beats the baseline"),
                  filters=[categorical_filter("ml_model_metrics", "metric", ["Macro F1"], "fc_f1"),
                           categorical_filter("ml_model_metrics", "evaluation", ["Test (2019 - Mar 2020)"], "fc_eval"),
                           categorical_filter("ml_model_metrics", "task", ["A: next-day AQI category"], "fc_task")])
    track = visual("fc_track", (24, 508, 820, 178), "lineChart",
                   query=roles(Category=[proj(C("dim_date", "Date"))],
                               Y=[proj(M("Actual Category"), "Actual"), proj(M("Predicted Category"), "Predicted")]),
                   objects={"dataPoint": series_colors([("Actual Category", INK), ("Predicted Category", BLUE)]),
                            "categoryAxis": [{"properties": {"axisType": s("Scalar")}}],
                            "legend": [{"properties": {"show": b(True), "position": s("Top")}}]},
                   vco=title_vco("Delhi: predicted vs actual AQI category (1 = Good … 6 = Severe)"),
                   filters=[categorical_filter("dim_city", "City", ["Delhi"], "fc_delhi")])
    note = textbox("fc_note", (856, 508, 400, 178), [
        [("The model gets ", {}), ("75%", {"fontWeight": "bold"}), (" of next-day categories exactly right (baseline 72%) and "
          "catches ", {}), ("92% of Poor-or-worse days", {"fontWeight": "bold"}), (" (baseline 80%).", {})],
        [("Honest caveat: switch the period to Lockdown and it does worse than the baseline, because the rules it "
          "learned stopped applying.", {"color": MUTED, "fontSize": "10pt"})],
    ])
    return vs + [cm, imp, comp, track, note]


def page_quality():
    vs = [navigator("dq_nav"),
          kpi_cards("dq_kpis", (24, 88, 600, 96), [
              ("Cleaning Steps", "Cleaning decisions logged"), ("Sensor Faults Removed", "Days with bad PM data"),
              ("AQI Values Rebuilt", "AQI values rebuilt")]),
          textbox("dq_headline", (636, 88, 620, 96), [
              [("Ahmedabad: #1 most polluted → #7 after cleaning", {"fontFamily": "Segoe UI Semibold",
                                                                     "fontSize": "16pt", "color": INK})],
              [("Its CO sensor column was a copy of NO (identical on 94% of days).", {"fontSize": "10pt"})]])]
    ahd = visual("dq_ahmedabad", (24, 196, 600, 250), "lineChart",
                 query=roles(Category=[proj(C("dim_date", "YearMonth"), "Month")],
                             Y=[proj(M("Median Official AQI"), "Official AQI"), proj(M("Median AQI"), "Corrected AQI")]),
                 objects={"dataPoint": series_colors([("Median Official AQI", MUTED), ("Median AQI", BLUE)]),
                          "legend": [{"properties": {"show": b(True), "position": s("Top")}}]},
                 vco=title_vco("Ahmedabad: official AQI vs corrected (monthly median)"),
                 filters=[categorical_filter("dim_city", "City", ["Ahmedabad"], "dq_ahd")])
    missing = visual("dq_missing", (636, 196, 620, 250), "clusteredBarChart",
                     query={**roles(Category=[proj(C("data_quality", "pollutant"), "Pollutant")],
                                    Y=[proj(M("Missing Before %"), "Before cleaning"),
                                       proj(M("Missing After %"), "After cleaning")]),
                            "sortDefinition": {"sort": [{"field": M("Missing Before %"), "direction": "Descending"}],
                                               "isDefaultSort": False}},
                     objects={"dataPoint": series_colors([("Missing Before %", MUTED), ("Missing After %", BLUE)]),
                              "legend": [{"properties": {"show": b(True), "position": s("Top")}}]},
                     vco=title_vco("Missing values before vs after cleaning"))
    log = visual("dq_log", (24, 458, 1232, 228), "tableEx",
                 query=roles(Values=[proj(C("cleaning_log", c), d) for c, d in [
                     ("step", "#"), ("table", "Table"), ("issue", "Issue found"), ("action", "Action"),
                     ("reason", "Reason"), ("rows_affected", "Rows")]]),
                 objects={"columnHeaders": [{"properties": {"autoSizeColumnWidth": b(True),
                                                            "columnAdjustment": s("growToFit"), "fontSize": n(9)}}],
                          "values": [{"properties": {"fontSize": n(8), "wordWrap": b(True)}}]},
                 vco=title_vco("Cleaning log: every decision and why"))
    return vs + [ahd, missing, log]


def page_tooltip():
    return [
        kpi_cards("tt_kpis", (8, 8, 304, 80), [("Median PM2.5", "PM2.5"), ("% Days Above Standard", "Days > limit"),
                                              ("Worst Month", "Worst")], value_size=16),
        visual("tt_line", (8, 96, 304, 136), "lineChart",
               query=roles(Category=[proj(C("dim_date", "MonthName"), "Month")], Y=[proj(M("Median PM2.5"))]),
               objects={"dataPoint": series_colors([("Median PM2.5", BLUE)])},
               vco=title_vco("Median PM2.5 by month", size=10)),
    ]


PAGES = [
    ("overview", "Overview", "1_overview.png", page_overview),
    ("cities", "City explorer", "2_city_explorer.png", page_cities),
    ("lockdown", "Lockdown", "3_lockdown.png", page_lockdown),
    ("forecast", "Early warning", "4_early_warning.png", page_forecast),
    ("quality", "Data quality", "5_data_quality.png", page_quality),
]


def page_json(name, display, background=None, tooltip=False, interactions=None):
    p = {"$schema": PAGE_SCHEMA, "name": name, "displayName": display}
    if tooltip:
        p.update({"displayOption": "ActualSize", "height": 240, "width": 320, "type": "Tooltip",
                  "visibility": "HiddenInViewMode"})
        return p
    p.update({"displayOption": "FitToPage", "height": 720, "width": 1280})
    objects = {"outspace": [{"properties": {"color": fill(PAGE_BG), "transparency": n(0)}}]}
    if background:
        objects["background"] = [{"properties": {
            "image": {"image": {"name": s(background),
                                "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources",
                                                                         "PackageType": 1, "ItemName": background}}},
                                "scaling": s("Fit")}},
            "color": fill(PAGE_BG), "transparency": n(0)}}]
    p["objects"] = objects
    if interactions:
        p["visualInteractions"] = interactions
    return p


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def build(report_only=False):
    sm, rp = OUT / f"{NAME}.SemanticModel", OUT / f"{NAME}.Report"
    if report_only:
        shutil.rmtree(rp / "definition" / "pages", ignore_errors=True)
        build_report(rp)
        print(f"Rebuilt report pages in {rp}")
        return
    if OUT.exists():
        shutil.rmtree(OUT)

    # ---- project + semantic model
    write_json(OUT / f"{NAME}.pbip", {
        "$schema": SCHEMA + "pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    write_json(sm / "definition.pbism", {
        "$schema": SCHEMA + "item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}})
    write_json(sm / "model.bim", build_model())
    for folder, kind in [(sm, "SemanticModel"), (rp, "Report")]:
        write_json(folder / ".platform", {
            "$schema": SCHEMA + "gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": kind, "displayName": "Breathe India"},
            "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"breathe-india/{kind}"))}})

    build_report(rp)
    (OUT / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    print(f"Built {OUT / (NAME + '.pbip')}")


def build_report(rp):
    write_json(rp / "definition.pbir", {
        "$schema": SCHEMA + "item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    d = rp / "definition"
    write_json(d / "version.json", {
        "$schema": SCHEMA + "item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    shared = rp / "StaticResources" / "SharedResources" / "BaseThemes"
    shared.mkdir(parents=True, exist_ok=True)
    shutil.copy(BASE_THEME_FILE, shared / BASE_THEME_FILE.name)
    reg = rp / "StaticResources" / "RegisteredResources"
    reg.mkdir(parents=True, exist_ok=True)
    theme = json.loads(CUSTOM_THEME_FILE.read_text(encoding="utf-8"))
    theme["name"] = CUSTOM_THEME_FILE.name      # must equal customTheme.name in report.json
    write_json(reg / CUSTOM_THEME_FILE.name, theme)
    items = [{"name": CUSTOM_THEME_FILE.name, "path": CUSTOM_THEME_FILE.name, "type": "CustomTheme"}]
    for _, _, bg, _ in PAGES:
        shutil.copy(BACKGROUNDS / bg, reg / bg)
        items.append({"name": bg, "path": bg, "type": "Image"})
    base = BASE_THEME_FILE.stem
    write_json(d / "report.json", {
        "$schema": SCHEMA + "item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": base, "reportVersionAtImport": VERSION_AT_IMPORT, "type": "SharedResources"},
            "customTheme": {"name": CUSTOM_THEME_FILE.name, "reportVersionAtImport": VERSION_AT_IMPORT,
                            "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": s("Top")}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": base, "path": f"BaseThemes/{base}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources", "items": items}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})

    # ---- pages
    order = []
    for name, display, bg, builder in PAGES:
        visuals = builder()
        interactions = None
        if name == "lockdown":   # the city/pollutant slicers drive the line, not the all-city comparison bar
            interactions = [{"source": "lk_city", "target": "lk_bar", "type": "NoFilter"},
                            {"source": "lk_pollutant", "target": "lk_bar", "type": "NoFilter"}]
        write_json(d / "pages" / name / "page.json", page_json(name, display, bg, interactions=interactions))
        for v in visuals:
            write_json(d / "pages" / name / "visuals" / v["name"] / "visual.json", v)
        order.append(name)
    write_json(d / "pages" / "citytip" / "page.json", page_json("citytip", "City tooltip", tooltip=True))
    for v in page_tooltip():
        write_json(d / "pages" / "citytip" / "visuals" / v["name"] / "visual.json", v)
    order.append("citytip")
    write_json(d / "pages" / "pages.json", {
        "$schema": SCHEMA + "item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": order, "activePageName": "overview"})



if __name__ == "__main__":
    import sys
    build(report_only="--report-only" in sys.argv)
