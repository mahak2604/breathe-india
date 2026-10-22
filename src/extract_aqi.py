# Breathe India - data extraction, source 1
#
# Downloads the CPCB air quality data from Kaggle and keeps the three daily files we need.
#
# Dataset: "Air Quality Data in India (2015 - 2020)" by Vijay Rao on Kaggle
#   https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india
# The data itself comes from the Central Pollution Control Board (CPCB), Government of India.
#
# Notes:
# - The download button on the Kaggle website needs a login, but the link below
#   (the one Kaggle shows under "Download via cURL") works without one.
# - The zip file is about 76 MB. It also has two hourly files (285 MB in total)
#   which we don't need, so we only extract the daily files.

import os
import zipfile

import requests

URL = "https://www.kaggle.com/api/v1/datasets/download/rohanrao/air-quality-data-in-india"
RAW_FOLDER = "data/raw"
ZIP_PATH = "data/raw/air_quality_india.zip"
FILES_WE_NEED = ["city_day.csv", "station_day.csv", "stations.csv"]


def main():
    os.makedirs(RAW_FOLDER, exist_ok=True)

    # if all three files are already there, there is nothing to do
    missing = [name for name in FILES_WE_NEED if not os.path.exists(os.path.join(RAW_FOLDER, name))]
    if not missing:
        print("CPCB files already downloaded")
        return

    print("Downloading", URL)
    response = requests.get(URL, timeout=300)
    response.raise_for_status()
    with open(ZIP_PATH, "wb") as f:
        f.write(response.content)
    print("Downloaded", round(len(response.content) / 1_000_000, 1), "MB")

    # take only the daily files out of the zip, then delete the zip
    with zipfile.ZipFile(ZIP_PATH) as z:
        for name in FILES_WE_NEED:
            z.extract(name, RAW_FOLDER)
    os.remove(ZIP_PATH)
    print("Saved", ", ".join(FILES_WE_NEED), "in", RAW_FOLDER)


if __name__ == "__main__":
    main()
