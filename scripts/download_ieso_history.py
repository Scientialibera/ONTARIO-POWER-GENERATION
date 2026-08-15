from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen


BASE = "https://reports-public.ieso.ca/public/Demand/PUB_Demand_{year}.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official IESO hourly demand history")
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--output-dir", default="data/raw/demand")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for year in range(args.start_year, args.end_year + 1):
        url = BASE.format(year=year)
        output = output_dir / f"PUB_Demand_{year}.csv"
        print(f"Downloading {url}")
        with urlopen(url, timeout=90) as response:
            output.write_bytes(response.read())
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
