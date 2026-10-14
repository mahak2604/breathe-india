"""
Data Extraction - Source 2 & 3 (public APIs)
Project: What drives air pollution in Indian cities? (CPCB AQI 2015-2020 + weather)

Source 1 (CPCB air quality) is downloaded manually from Kaggle (login required):
    https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india
    -> put city_day.csv, station_day.csv, stations.csv in data/raw/

This script pulls the other two sources for the 26 cities in city_day.csv:
    1. Open-Meteo Geocoding API      -> latitude, longitude, state, elevation, population
    2. Open-Meteo Historical Weather -> daily weather, 2015-01-01 to 2020-07-01

Access notes (document these in the report, section 4.1):
    - No API key / authentication needed for non-commercial use.
    - Free tier limits: < 600 calls/min, < 5,000/hour, < 10,000/day.
      A request for 5.5 years x 8 variables is weighted as many "calls", so
      fetching cities back to back hits HTTP 429 (rate limited) after ~7 cities.
      Fix: pause 15 s between cities, wait a full minute after a 429, and cache
      each city's raw JSON so a rerun only fetches what is missing.
    - Data licence: CC BY 4.0 (credit Open-Meteo and Copernicus ERA5).
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path("data/raw")
JSON_DIR = RAW_DIR / "weather_json"
START_DATE, END_DATE = "2015-01-01", "2020-07-01"

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_VARS = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
]

# City name exactly as in city_day.csv -> (name to search, state it must be in, note)
# Plain name lookups are ambiguous (e.g. 'Amaravati' also exists in Karnataka and
# Tamil Nadu), so every match is checked against the expected state.
CITIES = {
    "Ahmedabad": ("Ahmedabad", "Gujarat", ""),
    "Aizawl": ("Aizawl", "Mizoram", ""),
    "Amaravati": ("Amaravati", "Andhra Pradesh", "same name exists in KA and TN"),
    "Amritsar": ("Amritsar", "Punjab", ""),
    "Bengaluru": ("Bengaluru", "Karnataka", ""),
    "Bhopal": ("Bhopal", "Madhya Pradesh", ""),
    "Brajrajnagar": ("Brajarajnagar", "Odisha", "GeoNames spells it 'Brajarajnagar'"),
    "Chandigarh": ("Chandigarh", "Chandigarh", ""),
    "Chennai": ("Chennai", "Tamil Nadu", ""),
    "Coimbatore": ("Coimbatore", "Tamil Nadu", ""),
    "Delhi": ("Delhi", "Delhi", "other 'Delhi' villages exist in MP"),
    "Ernakulam": ("Ernakulam", "Kerala", ""),
    "Gurugram": ("Gurugram", "Haryana", ""),
    "Guwahati": ("Guwahati", "Assam", ""),
    "Hyderabad": ("Hyderabad", "Telangana", ""),
    "Jaipur": ("Jaipur", "Rajasthan", ""),
    "Jorapokhar": ("Jharia", "Jharkhand",
                   "the API's 'Jorapokhar' is a different village ~160 km away; "
                   "the CPCB station is at Jorapokhar, Jharia (Dhanbad), so Jharia is used"),
    "Kochi": ("Kochi", "Kerala", ""),
    "Kolkata": ("Kolkata", "West Bengal", ""),
    "Lucknow": ("Lucknow", "Uttar Pradesh", ""),
    "Mumbai": ("Mumbai", "Maharashtra", ""),
    "Patna": ("Patna", "Bihar", ""),
    "Shillong": ("Shillong", "Meghalaya", ""),
    "Talcher": ("Talcher", "Odisha", ""),
    "Thiruvananthapuram": ("Thiruvananthapuram", "Kerala", ""),
    "Visakhapatnam": ("Visakhapatnam", "Andhra Pradesh", ""),
}


def get_json(url, params, pause=1, retries=6):
    """GET with a polite pause, a one-minute wait on rate limits (HTTP 429), and
    exponential back-off on server errors and dropped connections."""
    for attempt in range(retries):
        wait = 2 ** (attempt + 2)
        try:
            resp = requests.get(url, params=params, timeout=60)
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"  {type(e).__name__}, retrying in {wait}s")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            time.sleep(pause)
            return resp.json()
        if resp.status_code == 429:
            print("  HTTP 429 (rate limited), waiting 65s")
            time.sleep(65)
            continue
        if resp.status_code in (500, 502, 503, 504):
            print(f"  HTTP {resp.status_code}, retrying in {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"Gave up on {url} {params}")


def geocode(city, search_name, state, note):
    data = get_json(GEOCODE_URL, {"name": search_name, "count": 10, "language": "en",
                                  "format": "json", "countryCode": "IN"})
    for r in data.get("results", []):
        if state.lower() in (r.get("admin1") or "").lower():
            return {
                "City": city,
                "matched_name": r["name"],
                "State": r.get("admin1"),
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "elevation_m": r.get("elevation"),
                "population": r.get("population"),
                "geo_note": note,
            }
    raise ValueError(f"No match for {city!r} in {state!r}")


def fetch_weather(city, lat, lon):
    cache = JSON_DIR / f"{city}.json"
    if cache.exists():
        print("    (cached)")
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        data = get_json(WEATHER_URL, {"latitude": lat, "longitude": lon,
                                      "start_date": START_DATE, "end_date": END_DATE,
                                      "daily": ",".join(DAILY_VARS), "timezone": "Asia/Kolkata"},
                        pause=15)
        # Keep the untouched API response as the raw record
        cache.write_text(json.dumps(data), encoding="utf-8")
    df = pd.DataFrame(data["daily"]).rename(columns={"time": "Date"})
    df.insert(0, "City", city)
    return df


def main():
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    print("Geocoding cities...")
    coords = pd.DataFrame([geocode(c, *v) for c, v in CITIES.items()])
    coords.to_csv(RAW_DIR / "city_coords.csv", index=False)
    print(coords[["City", "matched_name", "State", "latitude", "longitude"]].to_string(index=False))

    print("\nFetching daily weather...")
    frames = []
    for row in coords.itertuples():
        print(f"  {row.City}")
        frames.append(fetch_weather(row.City, row.latitude, row.longitude))
    weather = pd.concat(frames, ignore_index=True)
    weather.to_csv(RAW_DIR / "weather_daily.csv", index=False)

    print(f"\nSaved {len(coords)} cities -> {RAW_DIR / 'city_coords.csv'}")
    print(f"Saved {weather.shape[0]:,} rows x {weather.shape[1]} cols -> {RAW_DIR / 'weather_daily.csv'}")


if __name__ == "__main__":
    main()
