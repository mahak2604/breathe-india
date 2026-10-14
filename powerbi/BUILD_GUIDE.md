# Breathe India: Power BI build guide

Everything the dashboard needs is in this folder:

| File | What it is |
|---|---|
| `breathe_india_powerbi.xlsx` | All dashboard tables in one workbook (one sheet per table), created by the notebook |
| `data/*.csv` | The same tables as CSV (plus `fact_pollutant_long`), if you prefer CSV |
| `breathe_india_theme.json` | Colours, fonts and card style |
| `backgrounds/*.png` | One header/footer background per page (1280 × 720) |
| `measures.dax` | Every DAX measure, ready to paste |

Budget about 2–3 hours for the first build. Positions below are **X, Y, width, height** in pixels on a
1280 × 720 page (Format pane → General → Properties → Size and position).

---

## 0. Install

Power BI Desktop is free: Microsoft Store → "Power BI Desktop" (Windows only). Mac users need a Windows PC or VM.

## 1. Load the data (5 min)

1. **Home → Get data → Excel workbook** → `powerbi/breathe_india_powerbi.xlsx`.
2. Tick **all 13 sheets** → **Transform data**.
3. In Power Query, for each table, click the type icon of every *date* column (`Date`, `first_date`, `last_date`,
   `YearMonth`) and set it to **Date** (not Date/Time). Everything else is detected correctly.
4. **Close & Apply.**

## 2. Build the model (15 min)

**Model view.** Delete any relationships Power BI guessed, then create these (all *one-to-many*, *single* direction,
from the dimension on the "1" side):

| From (1 side) | To (many side) |
|---|---|
| `dim_city[City]` | `fact_city_day[City]` |
| `dim_date[Date]` | `fact_city_day[Date]` |
| `dim_aqi_category[category]` | `fact_city_day[AQI_Bucket_clean]` |
| `dim_city[City]` | `dim_station[City]` |
| `dim_city[City]` | `ml_predictions[City]` |
| `dim_date[Date]` | `ml_predictions[Date]` |
| `dim_city[City]` | `ml_counterfactual[City]` |
| `dim_date[Date]` | `ml_counterfactual[Date]` |
| `dim_city[City]` | `ml_lockdown_effect[City]` |

`ml_confusion`, `ml_model_metrics`, `ml_feature_importance`, `cleaning_log` and `data_quality` stay unconnected.

**Housekeeping** (Table view):
* `dim_date` → Table tools → **Mark as date table** → `Date`.
* Sort by column: `dim_date[MonthName]` by `Month`; `dim_date[Season]` by `SeasonOrder`;
  `dim_aqi_category[category]` by `rank`; `ml_confusion[actual]` by `actual_rank`; `ml_confusion[predicted]` by `predicted_rank`.
* `dim_city[latitude]` → Data category **Latitude**; `dim_city[longitude]` → **Longitude**; `dim_city[City]` → **City**.
* Hide the technical columns from report view (right-click → Hide): all `*_flag` columns except `pm_fault_flag`, `doy_sin`,
  `doy_cos`, `wind_u`, `wind_v`, `years_since_2015`, all `*_lag*` columns, `*_rank` columns.

## 3. Theme and measures (15 min)

1. **View → Themes → Browse for themes** → `breathe_india_theme.json`.
2. **Home → Enter data** → name the table `_Measures` → Load.
3. Open `measures.dax`. For each measure: select `_Measures` → **New measure** → paste → Enter. Set the format named
   in the comment above it (Measure tools → Format).
4. Delete the empty `Column1` from `_Measures`. The table becomes a measure folder at the top of the field list.

## 4. Page setup (repeat for each page)

* Format page → **Canvas settings**: Type 16:9 (1280 × 720).
* Format page → **Canvas background** → Image → `backgrounds/<page>.png`, Image fit **Fit**, Transparency **0%**.
* **Navigation:** on page 1 add Insert → Buttons → Navigator → **Page navigator** at **700, 20, 556, 36**.
  Style it: text white, font 10, *Default* fill off, *Selected* fill `#2A78D6`, border off. Copy and paste it onto every page.
  Rename the pages exactly: `Overview`, `City explorer`, `Lockdown`, `Early warning`, `Data quality`.

Every visual gets a title written as a **finding, not a label** (for example "Delhi breaks the limit on 7 days in 10" instead of
"% days by city"). Suggested titles are in quotes below.

---

## Page 1 · Overview, "The air India breathes"

Background: `1_overview.png`

| Visual | Position | Fields & settings |
|---|---|---|
| Card | 24, 88, 244, 92 | `Cities`. Title "Cities monitored" |
| Card | 280, 88, 244, 92 | `Days Measured`. Title "City-days with PM2.5 data" |
| Card | 536, 88, 244, 92 | `Median PM2.5`. Title "Typical PM2.5 (µg/m³)" |
| Card | 792, 88, 244, 92 | `% Days Above Standard`. Title "Days above India's PM2.5 limit" |
| Slicer (dropdown) | 1048, 88, 208, 44 | `dim_date[Year]`, multi-select |
| Slicer (dropdown) | 1048, 136, 208, 44 | `dim_city[Region]` |
| **Azure map** | 24, 192, 404, 494 | Latitude/Longitude from `dim_city`; Size `Median PM2.5`; Legend `dim_city[cluster]`; Tooltips `% Days Above Standard`, `Worst Month`. Bubble layer, min size 6, max 30. Title "Where the air is worst" |
| Line chart | 440, 192, 816, 236 | X `dim_date[MonthName]`; Y `Median PM2.5`; Legend `fact_city_day[city_group]`. Analytics → Y-axis constant line = 60, label "National limit". Markers on. Title "North India's winter air is 3× dirtier than its monsoon air" |
| Bar chart (clustered) | 440, 440, 480, 246 | Y `dim_city[City]`; X `% Days Above Standard`; sort descending; Top N filter = 10. Data colours → fx → Field value `Median AQI Colour`. Title "Delhi and Gurugram break the limit on 7 days in 10" |
| Text box | 932, 440, 324, 246 | Narrative below |

Narrative text (font 11, `#52514E`):

> **What this page says**
> Across 26 cities, PM2.5 broke India's daily limit on **39% of measured days**.
> The worst air is in the north (Delhi, Gurugram, Patna, Lucknow), and it peaks in **November–January**,
> when crop burning, cold still air and festival fireworks combine.
> Right-click any city → **Drill through → City explorer** for its full story.

**Make the map useful as a tooltip host:** Format → Tooltips → Type *Report page* → `City tooltip` (built in step 8).
If your Power BI blocks Azure Maps (organisation setting), use a **Scatter chart** instead: X `longitude`, Y `latitude`,
Size `Median PM2.5`, Legend `cluster`, axes hidden. It reads as a map of India.

## Page 2 · City explorer (drill-through target)

Background: `2_city_explorer.png`. Format page → **Page information → Allow use as drill through**: drag `dim_city[City]`
into the *Drill through* well. Power BI adds a Back button: move it to 640, 26, 40, 24.

| Visual | Position | Fields & settings |
|---|---|---|
| Matrix | 24, 88, 520, 598 | Rows `dim_city[City]`; Columns `dim_date[MonthName]`; Values `Median PM2.5`. Cell elements → **Background colour** on, Gradient: lowest `#CDE2FB`, highest `#0D366B`; font colour rule white above 90. Column subtotals off. Title "Each city's seasonal fingerprint (median PM2.5)". *Clicking a row filters the rest of the page.* |
| Card | 556, 88, 700, 40 | `City Narrative`. Callout font 12, left-aligned, no category label |
| Card | 556, 136, 167, 80 | `Median AQI`; conditional font colour → Field value `Median AQI Colour` |
| Card | 734, 136, 167, 80 | `% Days Poor or Worse` |
| Card | 912, 136, 167, 80 | `Main Pollutant` |
| Card | 1090, 136, 166, 80 | `Worst Month` |
| 100% stacked column | 556, 228, 700, 210 | X `dim_date[Year]`; Y `Days`; Legend `dim_aqi_category[category]`. Colours, Good → Severe: `#EEA07C`, `#E27B52`, `#CF5A31`, `#AD3F1D`, `#832A12`, `#561A0B`. Data labels off, legend top. Title "How many days fell in each AQI band" |
| Line chart | 556, 450, 440, 236 | X `dim_date[Date]` (continuous); Y `PM2.5 (7-day avg)`. Constant line 60. Title "PM2.5, 7-day average" |
| Table | 1008, 450, 248, 236 | `dim_station[station_place]`, `dim_station[pm25_mean]` (data bars on), `dim_station[share_days_above_naaqs]` (as %). Sort by pm25_mean desc. Title "Worst monitoring stations" |

Slicer tip: add a **Between** date slicer on `dim_date[Date]` hidden behind the narrative card if you want the date range filter
visible during the demo.

## Page 3 · Lockdown, "What the lockdown really changed"

Background: `3_lockdown.png`

| Visual | Position | Fields & settings |
|---|---|---|
| Card | 24, 88, 244, 92 | `PM2.5 Drop (Naive)`. Title "PM2.5 change, 2020 vs 2019" |
| Card | 280, 88, 244, 92 | `PM2.5 Drop (Weather-Adjusted)`. Title "PM2.5 change, weather removed" |
| Card | 536, 88, 244, 92 | `Weather Share of PM2.5 Drop`. Title "Share of the 'drop' that was weather" |
| Card | 792, 88, 244, 92 | `NO2 Drop (Weather-Adjusted)`. Title "NO₂ change, weather removed" |
| Slicer (dropdown, single select) | 1048, 88, 208, 44 | `dim_city[City]`, default **Delhi** |
| Slicer (tiles, single select) | 1048, 136, 208, 44 | `ml_counterfactual[pollutant]`, default **PM25** |
| Line chart | 24, 192, 820, 360 | X `dim_date[Date]` (continuous); Y `Actual (7-day)` (colour `#0B0B0B`) and `Expected (7-day)` (colour `#2A78D6`). Analytics → **Error bars** on `Expected (7-day)`: upper `Band High (7-day)`, lower `Band Low (7-day)`, type *Band*, colour `#CDE2FB`. Analytics → **X-axis constant line** at 25-03-2020, label "Lockdown" (if your version has no X-axis constant line, put a small text box "Lockdown begins 25 Mar ↓" above that date instead). Title "Actual vs. expected without lockdown (shaded = 80% band)" |
| Text box | 24, 564, 820, 122 | Narrative below |
| Bar chart (clustered) | 856, 192, 400, 494 | Y `ml_lockdown_effect[City]`; X `Naive Change` (colour `#898781`) and `Weather-Adjusted Change` (colour `#2A78D6`). Visual filter `ml_lockdown_effect[pollutant]` = PM25. Sort by Weather-Adjusted ascending. **Edit interactions:** make the City slicer *not* filter this chart. Title "Weather made the drop look bigger in most cities" |

Narrative:

> Comparing spring 2020 with spring 2019 says PM2.5 fell **41%**. But spring 2020 also had kinder weather. Our model, trained on
> 2015–2019, predicts what pollution *should* have been given the actual weather. Against that, the real lockdown effect was
> **−28%**: about **a third of the headline drop was weather**. NO₂, which mostly comes from traffic, fell **46%** either way.

## Page 4 · Early warning, "Can we warn a day ahead?"

Background: `4_early_warning.png`. Add a **page-level filter** `ml_predictions[split]` = *Test*, or a tile slicer at
1048, 88, 208, 92 to switch between *Test* and *Lockdown* (a strong demo moment).

| Visual | Position | Fields & settings |
|---|---|---|
| Card | 24, 88, 244, 92 | `Model Accuracy`. Title "Model: exact category" |
| Card | 280, 88, 244, 92 | `Baseline Accuracy`. Title "Baseline ('same as today')" |
| Card | 536, 88, 244, 92 | `Poor+ Recall (Model)`. Title "Poor-or-worse days caught" |
| Card | 792, 88, 244, 92 | `Accuracy On Change Days`. Title "Right when the category changes" |
| Matrix | 24, 192, 420, 300 | Rows `ml_confusion[actual]`; Columns `ml_confusion[predicted]`; Values `Confusion Row %`. Background colour gradient `#CDE2FB` → `#0D366B`. Title "Where predictions land (row %)" |
| Bar chart | 456, 192, 380, 300 | Y `ml_feature_importance[feature]`; X `ml_feature_importance[importance]`; Top N = 10 by importance. Title "What the model relies on" |
| Clustered bar | 848, 192, 408, 300 | Y `ml_model_metrics[model]`; X `Metric Value`. Visual filters: `task` = A: next-day AQI category, `evaluation` = Test (2019 - Mar 2020), `metric` = Macro F1. Title "Gradient Boosting beats the baseline on unseen data" |
| Line chart | 24, 504, 820, 182 | X `dim_date[Date]`; Y Max of `ml_predictions[actual_category_rank]` and Max of `ml_predictions[predicted_category_rank]`. City slicer or visual filter = Delhi. Y axis 1–6. Title "Delhi: predicted vs actual AQI category (1 = Good … 6 = Severe)" |
| Text box | 856, 504, 400, 182 | Narrative below |

Narrative:

> The model gets **75%** of next-day categories exactly right (baseline 72%) and catches **92% of Poor-or-worse days**
> (baseline 80%). Its real value is on days the air *changes*. Honest caveat: during the lockdown it did **worse** than the
> baseline, because the rules it learned stopped applying.

## Page 5 · Data quality, "How the data was cleaned"

Background: `5_data_quality.png`

| Visual | Position | Fields & settings |
|---|---|---|
| Card | 24, 88, 244, 92 | `Values Fixed or Flagged` |
| Card | 280, 88, 244, 92 | `Sensor Faults Removed` |
| Card | 536, 88, 500, 92 | Text: insert a **Text box** "Ahmedabad: #1 most polluted → #7 after cleaning" (font 18 semibold) |
| Line chart | 24, 192, 600, 250 | X `dim_date[YearMonth]`; Y `Median Official AQI` (colour `#898781`) and `Median AQI` (colour `#2A78D6`); visual filter `dim_city[City]` = Ahmedabad. Title "Ahmedabad: official AQI vs. corrected (CO sensor copied NO)" |
| Clustered bar | 636, 192, 620, 250 | Y `data_quality[pollutant]`; X `Missing Before %` and `Missing After %`. Title "Missing values before vs. after cleaning (%)" |
| Table | 24, 454, 1232, 232 | `cleaning_log`: step, table, issue, action, reason, rows_affected. Word wrap on, font 9. Title "Cleaning log: every decision and why" |

## 5. Tooltip page (the hover polish)

New page `City tooltip` → Format page → Page information → **Allow use as tooltip** on; Canvas settings Type **Tooltip**
(320 × 240). Add: card `Median PM2.5` (title = City via `SELECTEDVALUE`, or leave default), card `% Days Above Standard`, card
`Worst Month`, and a small line chart `dim_date[MonthName]` × `Median PM2.5`. Hide the page (right-click → Hide page).
Point the map and the bar chart on page 1 at it.

## 6. Final checks before the viva

* Every visual has a sentence-style title and no "Sum of …" labels (rename fields in the visual: double-click the field name).
* Click through every slicer. Nothing should go blank.
* View → **Performance analyzer** → refresh visuals: everything under 1 s.
* File → **Export → PDF** (the fallback the guidelines ask for) and save as `Breathe_India_dashboard.pdf`.
* Save as `Breathe_India.pbix` in this folder.

## 7. Two-minute demo script

1. **Overview:** "39% of days broke the limit." Point at the map, then the winter peak line.
2. Right-click **Delhi** on the bar chart → **Drill through → City explorer**. Read the narrative card. Show the AQI-band
   columns turning dark every winter, and the worst station (Anand Vihar).
3. **Lockdown:** switch the city slicer Delhi → Mumbai. "Mumbai barely changed once weather is removed." Point at the two
   bar colours: "weather made the drop look bigger."
4. **Early warning:** flip the split slicer Test → Lockdown and watch accuracy fall below the baseline. That is the honesty slide.
5. **Data quality:** "Without cleaning, Ahmedabad would be India's most polluted city." End on the cleaning log.
