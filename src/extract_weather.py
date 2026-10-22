# Breathe India - data extraction, sources 2 and 3
#
# Uses two free Open-Meteo APIs for the 26 cities in the CPCB data:
#   1. Geocoding API          -> latitude, longitude, state, elevation, population of each city
#   2. Historical weather API -> daily weather from 2015-01-01 to 2020-07-01 (ERA5 reanalysis data)
#
# Notes:
# - No API key is needed. The data is licensed CC BY 4.0 (we credit Open-Meteo and Copernicus ERA5).
# - The free API has a rate limit. A 5.5-year request counts as many calls, so after about
#   7 cities we got "HTTP 429 - too many requests". To fix this the script waits 15 seconds
#   between cities, waits a full minute after a 429, and saves every city's answer as a JSON file.
#   If the script is run again, cities that are already saved are not downloaded again.

import json
import os
import time

import pandas as pd
import requests

RAW_FOLDER = "data/raw"
JSON_FOLDER = "data/raw/weather_json"
START_DATE = "2015-01-01"
END_DATE = "2020-07-01"

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"

WEATHER_VARIABLES = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
]

# City name as in city_day.csv: (name we search for, state it must be in, note)
# Many place names exist more than once in India (for example there is also an Amaravati
# in Karnataka and in Tamil Nadu), so we only accept a match in the right state.
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
    # the API's "Jorapokhar" is a different village about 160 km away;
    # the CPCB station is at Jorapokhar, Jharia (Dhanbad), so we search for Jharia
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


def get_json(url, params):
    # ask the API, and try again if it fails (at most 6 times)
    for attempt in range(6):
        try:
            response = requests.get(url, params=params, timeout=60)
        except requests.RequestException:
            print("  connection problem, trying again in 10 seconds")
            time.sleep(10)
            continue

        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            print("  too many requests (HTTP 429), waiting 65 seconds")
            time.sleep(65)
        else:
            print("  HTTP error", response.status_code, "- trying again in 10 seconds")
            time.sleep(10)

    raise RuntimeError("Could not get data from " + url)


def find_city(city, search_name, state, note):
    # look the city up and return the first match that is in the right state
    data = get_json(GEOCODE_URL, {"name": search_name, "count": 10, "language": "en",
                                  "format": "json", "countryCode": "IN"})
    time.sleep(1)
    for place in data.get("results", []):
        place_state = place.get("admin1") or ""
        if state.lower() in place_state.lower():
            return {
                "City": city,
                "matched_name": place["name"],
                "State": place.get("admin1"),
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "elevation_m": place.get("elevation"),
                "population": place.get("population"),
                "geo_note": note,
            }
    raise ValueError("No match for " + city + " in " + state)


def get_weather(city, latitude, longitude):
    json_file = os.path.join(JSON_FOLDER, city + ".json")

    if os.path.exists(json_file):
        # we already downloaded this city
        print("    (already saved)")
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        params = {"latitude": latitude, "longitude": longitude,
                  "start_date": START_DATE, "end_date": END_DATE,
                  "daily": ",".join(WEATHER_VARIABLES), "timezone": "Asia/Kolkata"}
        data = get_json(WEATHER_URL, params)
        # save the API answer exactly as we got it, this is our raw data
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        time.sleep(15)   # be polite to the free API

    weather = pd.DataFrame(data["daily"])
    weather = weather.rename(columns={"time": "Date"})
    weather.insert(0, "City", city)
    return weather


def main():
    os.makedirs(JSON_FOLDER, exist_ok=True)

    print("Finding the location of each city...")
    rows = []
    for city, (search_name, state, note) in CITIES.items():
        rows.append(find_city(city, search_name, state, note))
    coords = pd.DataFrame(rows)
    coords.to_csv(os.path.join(RAW_FOLDER, "city_coords.csv"), index=False)
    print(coords[["City", "State", "latitude", "longitude"]].to_string(index=False))

    print("\nDownloading daily weather...")
    all_weather = []
    for i in range(len(coords)):
        city = coords.loc[i, "City"]
        print(" ", city)
        all_weather.append(get_weather(city, coords.loc[i, "latitude"], coords.loc[i, "longitude"]))
    weather = pd.concat(all_weather, ignore_index=True)
    weather.to_csv(os.path.join(RAW_FOLDER, "weather_daily.csv"), index=False)

    print("\nSaved", len(coords), "cities to city_coords.csv")
    print("Saved", len(weather), "rows to weather_daily.csv")


if __name__ == "__main__":
    main()
