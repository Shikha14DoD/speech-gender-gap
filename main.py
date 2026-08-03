"""
Main entry point for the Speech Gender Gap scraper.

Usage:
    python main.py --country denmark --limit 5
    python main.py --country denmark --out data/processed/denmark.csv
"""

import argparse

from src.config_loader import load_config, get_leader_config
from src.scraper_denmark import parse_denmark
from src.scraper_italy import parse_italy
from src.scraper_slovenia import parse_slovenia
from src.scraper_samoa import parse_samoa
from src.scraper_china import parse_china
from src.scraper_liqiang import parse_liqiang
from src.utils import write_csv

# As we add more countries, we register their parser functions here.
PARSERS = {
    "denmark": parse_denmark,
    "italy": parse_italy,
    "slovenia": parse_slovenia,
    "samoa": parse_samoa,
    "china": parse_china,
    "liqiang": parse_liqiang,
}


def main():
    ap = argparse.ArgumentParser(description="Scrape speeches for the Speech Gender Gap project.")
    ap.add_argument("--country", required=True, choices=list(PARSERS.keys()))
    ap.add_argument("--limit", type=int, default=None,
                     help="Stop after N speeches (useful for testing).")
    ap.add_argument("--out", default=None,
                     help="Output CSV path. Defaults to data/processed/<country>.csv")
    args = ap.parse_args()

    config = load_config()
    leader_config = get_leader_config(args.country, config)
    parser_fn = PARSERS[args.country]

    out_path = args.out or f"data/processed/{args.country}.csv"

    # Use a per-country date range if one is set in config.json;
    # otherwise fall back to the project-wide default.
    country_range = leader_config.get("date_range", config["date_range"])

    results = parser_fn(
        leader_config,
        country_range["start"],
        country_range["end"],
        args.limit,
    )
    
    write_csv(results, out_path)
    print(f"\nDone. {len(results)} speeches written to {out_path}")


if __name__ == "__main__":
    main()