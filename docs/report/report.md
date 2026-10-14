# Breathe India: What Really Drives Air Pollution in Indian Cities?

Data Wrangling Group Project · Mahak Wadhawan (L074) · Yash Shah (L056) · 14 October 2026

## 1. Objective

About a third of the PM2.5 drop credited to India's 2020 lockdown was actually favourable weather, and tomorrow's air-quality category can be predicted correctly 75% of the time. Those are the two answers this project gives to one question: how much of a city's daily air quality comes from weather and season, and how much from people?

The 2020 COVID-19 lockdown is our natural experiment. On 25 March 2020 traffic and most industry stopped almost overnight, a change no policy could make on purpose. But the weather also changed that spring, so the headline "pollution fell by 40%" mixes two effects. We separate them with a weather-normalised model.

The project takes five years of government data for 26 cities through the full pipeline: extraction, cleaning, transformation and loading. It then carries the data into three machine-learning tasks and a five-page Power BI dashboard. Everything is reproducible from the repository [mahak2604/breathe-india](https://github.com/mahak2604/breathe-india).

## 2. Dataset

Four sources were joined into one star schema of 28,260 city-days for 26 cities, 1 January 2015 to 1 July 2020. The government air-quality data is the core; weather and city locations come from two public APIs, and an event calendar was typed in from public records.

| Source | How obtained | Rows × columns | Grain | Licence / terms |
| --- | --- | --- | --- | --- |
| [CPCB air quality, city level](https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india) (Central Pollution Control Board, via Kaggle) | HTTP download of a 76 MB zip | 29,531 × 16 | city × day | Published by CPCB; Kaggle page licence |
| CPCB air quality, station level + station register | Same download | 108,035 × 16 and 230 × 5 | station × day | As above |
| [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (Copernicus ERA5) | REST API, 1 call per city, 8 daily variables | 52,234 × 10 | city × day | CC BY 4.0, free non-commercial |
| [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api) | REST API, 1 call per city | 26 × 8 | city | CC BY 4.0 |
| Event calendar | Typed from government lockdown orders and the festival calendar | 6 phases, 5 Diwali dates | date | Public record |

The raw data needed real wrangling, not a tidy-up:

- **Heavy, uneven gaps.** Xylene is 61% empty, PM10 38%, AQI 16%. Mumbai has no PM or AQI data before 2018.
- **An unbalanced panel.** Only 7 cities report AQI from 2015; others start as late as 2020.
- **Impossible values.** AQI reaches 2,049 on a scale that ends at 500, CO and NOx have exact zeros, and PM2.5 exceeds PM10 on 256 days.
- **A corrupted column.** Ahmedabad's carbon monoxide equals its nitric oxide on 94% of days, although the units differ a thousandfold.
- **Names that disagree.** "Amaravati" matches three places in India and "Brajrajnagar" is spelled differently across sources.

## 3. Methodology

The whole pipeline runs end to end in one notebook in about 8 minutes, and every cleaning decision is logged with its reason: 23 entries, stored in the notebook, in `docs/cleaning_log.md` and in the database.

### 3.1 Extraction

- **CPCB data:** Kaggle's public dataset endpoint, which needs no login (the browser button does). Only the three daily files are kept; the 285 MB of hourly files are not needed.
- **Weather:** a 5-year, 8-variable request counts as many API calls, so we hit HTTP 429 (rate limited) after 7 cities. The extractor now pauses 15 s between cities, waits 65 s after a 429 and caches each city's raw JSON, so a rerun fetches only what is missing.
- **Locations:** every geocoder match is checked against the city's state. The geocoder's "Jorapokhar" was a village about 160 km from the monitoring station, so Jharia (Dhanbad), where the station stands, is used instead.

### 3.2 Cleaning: the decisions that mattered

| Issue found | Action | Why | Values |
| --- | --- | --- | --- |
| Ahmedabad CO equals NO (r = 0.999) | CO set to missing; AQI recalculated without it | CO drove 95% of its official "Severe" days | 1,400 CO; 1,576 AQI |
| PM2.5 above PM10, which is physically impossible | Removed whichever reading was further from the city-month norm | Data showed PM2.5 was the faulty one in 94% of cases, overturning our first assumption | 256 |
| Sensor stuck on one value 4+ days | Set to missing | Daily averages never repeat to two decimals for days | 30 |
| Spikes > 3.5 robust SD above the city-month norm | Set to missing, except during Diwali and the crop-burning season | 55% fell in the monsoon, including 918 µg/m³ in Shillong, the cleanest city | 167 removed, 5 kept |
| Exact 0.00 for CO and NOx | Set to missing | A city-wide daily mean of zero is impossible | 3,068 |
| Gaps of 1–3 days | Linear interpolation within the city | Pollution changes smoothly over a few days; longer gaps stay missing | 3,700 |
| Official AQI above 500 | Capped at 500 | 500 is the top of the CPCB scale | 543 |
| AQI missing although pollutants were measured | Filled with our CPCB-breakpoint recalculation, flagged by source | Recalculation matches the official AQI with r = 0.94, within one category 99% of the time | 1,044 |

### 3.3 Transformation

- **Star schema:** a city-day fact table (28,260 rows × 61 columns) with city, date and station dimensions. Every join declares its cardinality, so a duplicated key stops the notebook instead of silently multiplying rows.
- **Engineered features:** day-night temperature range, wind as a vector (so 359° sits next to 1°), seasonal sine and cosine, Diwali and crop-burning flags, lockdown phase, and PM2.5 relative to the same city's median for that month.
- **Time features:** yesterday's and the day before's values joined by calendar date (safe across gaps, unlike a row shift), plus a 7-day rolling mean.
- **Reshapes:** a melt to 165,506 city-day-pollutant rows for the dashboard, a city × month pivot for the seasonal heatmap, region × season and station-level aggregations.

### 3.4 Loading

- **SQLite** (`breathe_india.db`): one table per entity, unique indexes as primary keys, then read-back checks: row counts match, zero orphan keys, and the PM2.5 total agrees to the decimal. An analytical SQL query ranks cities by days over the limit.
- **Parquet** partitioned by year, validated by comparing row counts per partition.
- **Power BI:** the same tables as CSV and a one-file Excel workbook.

## 4. Machine learning

Three tasks, each judged against a simple baseline on data the model never saw, with splits in time order. A random split would leak the future, because tomorrow's pollution closely follows today's. All preprocessing (imputation, scaling, one-hot encoding) sits inside scikit-learn pipelines, so it is fitted on training folds only.

### 4.1 Model A: tomorrow's AQI category (classification)

- **Target:** the next day's official CPCB category, 6 classes. Ahmedabad and every recalculated day are excluded, so the model never learns from our own corrections.
- **Inputs:** today's pollutants, AQI and recent history; today's and tomorrow's weather (a forecast stand-in); calendar; city geography.
- **Split:** train on target days to the end of 2018 (12,315 rows, 17 cities); test on Jan 2019 to 24 Mar 2020 (8,554 rows); a separate lockdown stress test.
- **Selection:** 5-fold time-series cross-validation picked Gradient Boosting, then a small grid tuned it (learning rate 0.03, 31 leaves).

| Model (test, 2019 to Mar 2020) | Accuracy | Macro F1 | Poor-or-worse days caught | Right when the category changed |
| --- | --- | --- | --- | --- |
| Persistence baseline ("same as today") | 0.72 | 0.66 | 80% | 0% |
| Logistic Regression | 0.69 | 0.65 | 93% | 41% |
| Random Forest | 0.76 | 0.70 | 90% | 33% |
| **Gradient Boosting (chosen)** | **0.75** | **0.72** | **92%** | **35%** |

Gradient Boosting has the best macro F1, which weights all six categories equally, and 99.7% of its predictions are right or one category off. Its value is on days the air changes, which the baseline gets wrong by definition. It also fails honestly: in cross-validation on 2015–18 it only matched the baseline (macro F1 0.62 each), and during the lockdown its macro F1 fell to 0.59, below the baseline's 0.65, because the rules it learned stopped applying.

### 4.2 Model B: what the lockdown really changed (regression as a counterfactual)

The model predicts PM2.5 and NO₂ from weather, season, day of week, long-term trend and city only, never from pollution. Fed the real spring-2020 weather, it estimates pollution without a lockdown; the gap to reality is the lockdown effect, cleaned of weather.

| Check | Result |
| --- | --- |
| Placebo: predict spring 2019, when nothing happened | Random Forest R² 0.55, bias −2%; city-month average R² 0.44; Ridge 0.38 |
| Out-of-sample, 1 Jan to 24 Mar 2020 | R² 0.67, bias +4%: it tracked reality up to the lockdown |
| 80% prediction band (quantile Gradient Boosting) | Covered 73% of days: slightly too narrow, read as indicative |
| Lockdown effect on PM2.5, median of 17 cities | −41% naive vs **−28% weather-adjusted** |
| Lockdown effect on NO₂, median of 17 cities | −47% naive vs **−46% weather-adjusted** |

![Figure 1](../../figures/13_counterfactual_cities.png)

*Figure 1. Actual PM2.5 (black) against the weather-based expectation (blue, 80% band), January–June 2020; shading marks the lockdown. Delhi tracks its expectation until 25 March, then falls below it.*

### 4.3 Model C: three kinds of city air (clustering)

K-means on two standardised features per city (typical PM2.5 level and the winter-to-monsoon ratio) gives three groups; k = 3 was chosen by silhouette score (0.41). **High all year:** Delhi, Gurugram, Lucknow, Patna, Brajrajnagar and, after cleaning, Ahmedabad. **Clean monsoon, smoggy winter:** Mumbai, Kolkata, Guwahati, Hyderabad, Talcher, Amaravati, Thiruvananthapuram. **Steady year-round:** Bengaluru, Chennai, Coimbatore, Shillong, Visakhapatnam, Amritsar, Jaipur. Six cities with under a year of data stay unclustered.

## 5. Power BI dashboard

The dashboard (`Breathe_India.pbix`, with a PDF export) answers one question per page for a non-technical reader. Every visual title states its finding, not its field names, and each page ends with a short plain-language note. It reads from the cleaned tables and the model outputs through 13 related tables and 49 DAX measures.

| Page | The question it answers | What is on it | What the reader can do |
| --- | --- | --- | --- |
| Overview | Where and when is the air worst? | Four headline numbers, a map of the cities sized by typical PM2.5 and coloured by cluster, the monthly curve for North, coastal and other cities against the 60 µg/m³ limit, cities ranked by days over the limit | Filter by year and region; hover a city for a custom tooltip page with its own profile |
| City explorer | What is one city's year like? | City × month heatmap, a one-line summary sentence, AQI bands by year in the CPCB colour order, a 7-day PM2.5 line, worst monitoring stations | Click a city in the heatmap or pick it from a dropdown to filter the page |
| Lockdown | What did the lockdown really change? | Naive vs weather-adjusted change, the share due to weather, actual vs expected PM2.5 or NO₂ with an 80% band and a marker on 25 March, naive vs adjusted by city | Choose the city and pollutant (opens on Delhi, PM2.5) |
| Early warning | Can we warn a day ahead? | Model vs baseline accuracy, Poor-or-worse days caught, confusion matrix, top 10 inputs, models compared on macro F1, Delhi predicted vs actual | Switch Test to Lockdown to watch the model fall below the baseline |
| Data quality | Can these numbers be trusted? | Cleaning decisions and sensor faults counted, Ahmedabad's official vs corrected AQI, missing values before vs after, the full cleaning log | Read every decision and its reason |

![Figure 2](../../figures/dashboard_1_overview.png)

*Figure 2. The Overview page: headline numbers, city map, seasonal curve and the cities that break the limit most often.*

The report is generated from code (`src/build_powerbi_project.py`) as a Power BI project, checked with Microsoft's report validator, opened and refreshed in Power BI Desktop, then saved as the `.pbix`. A custom theme, page backgrounds and a colour-blind-checked palette keep the five pages consistent.

## 6. Insights

Five findings, each tested against the cleaned data rather than assumed. The first two would have been wrong without the wrangling.

1. **India's "most polluted city" in this data is a data error.** On official numbers Ahmedabad ranks first, with a median AQI of 384. Its CO column copies its NO column, and CO drove 95% of its AQI-above-400 days. Corrected, its median AQI is 125 and it ranks seventh.
2. **North India's winter air carries 3.3 times the PM2.5 of its monsoon air.** The median November–January day reaches 148 µg/m³, about 2.5 times the national 24-hour limit of 60, against 44 in June–September. Coastal cities swing only 2.2 times. Delhi and Gurugram break the limit on 72% of days.
3. **Rain cleans the air, but a third as much as it seems.** A raw comparison says heavy-rain days have 65% less PM2.5 than dry days. Against the same city in the same month the washout effect is 23%, because heavy rain mostly falls in the already-clean monsoon. Wind matters less: the windiest quarter of days is 10% cleaner than the calmest.
4. **The lockdown cut particles and NO₂, but not ozone, and the weather flattered the particles.** Against spring 2019, PM2.5 fell about 40% and NO₂ about 45% (median city), while ozone barely moved (−2%) and rose in 8 of 18 cities: less traffic NO left more ozone intact. With weather removed (Model B), the real PM2.5 effect is −28%.
5. **Diwali leaves a mark every year.** In North India, PM2.5 on the day after Diwali is about 2.5 times its level in the week before (other cities: 1.9 times). It peaks the day after because daily averages run midnight to midnight and fireworks run late.

![Figure 3](../../figures/04_insight_ranking_error.png)

*Figure 3. Median daily AQI, official (grey) against cleaned (blue). Only Ahmedabad moves materially: from first to seventh.*

## 7. Limitations

The conclusions hold for the monitored parts of 26 cities from 2015 to mid-2020; these are the places where they could be biased.

- **Measurement, not exposure.** A city's value averages a handful of stations (it matches the station average with r = 0.997), so it describes the monitored areas, not every neighbourhood.
- **Uneven coverage.** Only 7 cities report AQI from 2015 and Mumbai has nothing before 2018. Rankings use each city's own period, and late-starting cities are missing from Model A's training years.
- **Our corrections are assumptions.** Ahmedabad's AQI is our recalculation from daily averages; CPCB uses hourly data with 8-hour maxima for CO and ozone. It agrees with the official AQI within one category 99% of the time, not exactly.
- **Removing sensor faults is a judgement.** A 3.5-SD rule with Diwali and crop-burning exceptions could drop a rare real spike outside those windows. Interpolating 1–3 day gaps also smooths some real day-to-day variation.
- **Model A uses tomorrow's actual weather** as a stand-in for a forecast. A deployed system would be somewhat less accurate.
- **Model B assumes 2015–19 "normal" would have continued in 2020.** Anything else that changed that spring, such as fireworks rules or crop burning, lands in the "lockdown effect". Its 80% band covered 73% of days.
- **Weather is reanalysis.** ERA5 is a roughly 25 km grid and smooths local extremes.
- **The data ends on 1 July 2020,** so how fast pollution returned after unlocking is not covered.

## 8. Contribution statement

| Member | Primary responsibility |
| --- | --- |
| Mahak Wadhawan (L074) | Transformation and feature engineering, the three machine-learning models, the Power BI dashboard |
| Yash Shah (L056) | Data extraction (Kaggle download, Open-Meteo APIs), cleaning and the cleaning log, SQLite and Parquet storage |
| Both | Insights, this report and the presentation |

## References

1. Central Pollution Control Board (2014). *National Air Quality Index*. Ministry of Environment, Forest and Climate Change, Government of India.
2. Rao, V. (2020). [Air Quality Data in India (2015–2020)](https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india). Kaggle; data from the Central Pollution Control Board.
3. Zippenfenig, P. (2023). [Open-Meteo.com Weather API](https://open-meteo.com/en/docs/historical-weather-api). Zenodo, doi:10.5281/zenodo.7970649. Licensed CC BY 4.0.
4. Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146, 1999–2049.
5. Ministry of Home Affairs (2020). Order No. 40-3/2020-DM-I(A) of 24 March 2020 and subsequent lockdown extension orders.
6. Central Pollution Control Board (2009). *National Ambient Air Quality Standards* (PM2.5, 24-hour: 60 µg/m³).
7. Pedregosa, F. et al. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.
