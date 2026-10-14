"""
Data Extraction - Source 1 (Kaggle download over HTTP)
Project: Breathe India - what really drives air pollution in Indian cities?

Dataset : Air Quality Data in India (2015 - 2020), Vijay "Vopani" Rao, Kaggle
Page    : https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india
Origin  : Central Pollution Control Board (CPCB), Government of India
          (continuous ambient air quality monitoring stations), https://cpcb.nic.in

Access notes (document these in the report, section 4.1):
    - The browser download button needs a Kaggle login, but the public dataset
      endpoint below works without credentials (it is the "Download via cURL"
      link Kaggle shows on the dataset page).
    - The archive is ~76 MB. The two hourly files inside it (city_hour 66 MB,
      station_hour 220 MB) are not needed for a daily analysis, so only the three
      daily files are extracted. They are small enough to commit to GitHub.
    - Check the licence shown on the Kaggle page before redistributing the files.
"""

import tempfile
import zipfile
from pathlib import Path

import requests

URL = "https://www.kaggle.com/api/v1/datasets/download/rohanrao/air-quality-data-in-india"
RAW_DIR = Path("data/raw")
NEEDED = ["city_day.csv", "station_day.csv", "stations.csv"]


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if all((RAW_DIR / f).exists() for f in NEEDED):
        print("CPCB files already present - skipping download")
        return

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "air-quality-data-in-india.zip"
        print(f"Downloading {URL}")
        with requests.get(URL, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            with open(archive, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    f.write(chunk)
        print(f"  {archive.stat().st_size / 1e6:.1f} MB downloaded")

        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                print(f"  in archive: {info.filename:18s} {info.file_size / 1e6:6.1f} MB")
            for name in NEEDED:
                z.extract(name, RAW_DIR)
    print(f"Extracted {', '.join(NEEDED)} -> {RAW_DIR}")


if __name__ == "__main__":
    main()
