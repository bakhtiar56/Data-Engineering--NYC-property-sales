import sys
import argparse
from pathlib import Path
import requests

BASE = "https://www.nyc.gov/assets/finance/downloads/pdf/rolling_sales/annualized-sales/{year}/{year}_{borough}.xlsx"

BOROUGHS = ["manhattan", "bronx", "brooklyn", "queens", "staten_island"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    failures = []
    for b in BOROUGHS:
        url = BASE.format(year=args.year, borough=b)
        out = raw_dir / f"{args.year}_{b}.xlsx"

        if out.exists() and not args.overwrite:
            print(f"SKIP exists: {out}")
            continue

        try:
            print(f"DOWNLOADING: {url}")
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            out.write_bytes(r.content)
            print(f"OK: {out} ({out.stat().st_size} bytes)")
        except Exception as e:
            failures.append((url, str(e)))

    if failures:
        print("\nFAILED downloads:")
        for url, err in failures:
            print(f"- {url} -> {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()