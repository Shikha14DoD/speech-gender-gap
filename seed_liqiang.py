"""
Seeds liqiang.csv with a set of manually-identified, verified real
speech URLs -- used because full Wayback-based discovery hit a data
quality dead end on this domain (the general /news/ feed's Wayback
sample is dominated by old re-crawled pages, leaving no room for
genuinely recent content in each year's capped result set).
"""

import pandas as pd

from src.config_loader import load_config, get_leader_config
from src.scraper_liqiang import _fetch_article
from src.text_processing import in_date_range
from src.utils import write_csv

KNOWN_URLS = [
    "https://english.www.gov.cn/news/202410/10/content_WS6707f09dc6d0868f4e8ebab5.html",
    "https://english.www.gov.cn/news/202505/28/content_WS68368211c6d0868f4e8f2ece.html",
    "https://english.www.gov.cn/news/202506/26/content_WS685c7df4c6d0868f4e8f3a49.html",
    "https://english.www.gov.cn/news/202509/27/content_WS68d72520c6d00ca5f9a067aa.html",
    "https://english.www.gov.cn/news/202510/28/content_WS690030cdc6d00ca5f9a071d6.html",
    "https://english.www.gov.cn/news/202406/15/content_WS666c855ec6d0868f4e8e8230.html",
    "https://english.www.gov.cn/news/202403/24/content_WS65ffc1bac6d0868f4e8e566c.html",
    "https://english.www.gov.cn/news/202410/17/content_WS671079b6c6d0868f4e8ebfb4.html",
    "https://english.www.gov.cn/news/202507/07/content_WS686b5e8ac6d0868f4e8f3e85.html",
    "http://english.scio.gov.cn/topnews/2024-01/17/content_116946156.htm",
    "https://english.www.gov.cn/news/202509/24/content_WS68d3a26dc6d00ca5f9a0664e.html",
    "https://english.www.gov.cn/news/202510/28/content_WS6900298dc6d00ca5f9a071d2.html",
    "https://english.www.gov.cn/news/202510/29/content_WS69015a57c6d00ca5f9a0724a.html",
    "http://english.scio.gov.cn/topnews/2026-06/25/content_118566232.html",
    "https://english.www.gov.cn/news/202403/13/content_WS65f0dfccc6d0868f4e8e5079.html",
    "https://english.www.gov.cn/news/202503/12/content_WS67d17f57c6d0868f4e8f0c0d.html",
    "https://english.www.gov.cn/news/202603/13/content_WS69b4b144c6d00ca5f9a09dfd.html",
]


def main():
    config = load_config()
    leader_config = get_leader_config("liqiang", config)
    date_range = leader_config.get("date_range", config["date_range"])

    new_rows = []
    for url in KNOWN_URLS:
        article = _fetch_article(url, leader_config)
        if article is None:
            print(f"  [skip] could not fetch or filter rejected it: {url}")
            continue
        if not in_date_range(article.date, date_range["start"], date_range["end"]):
            print(f"  [skip] outside date range ({article.date}): {url}")
            continue
        new_rows.append(article)
        print(f"  added: {article.title}")

    if new_rows:
        write_csv(new_rows, "data/processed/liqiang.csv")
    print(f"\nDone. Added {len(new_rows)} row(s).")


if __name__ == "__main__":
    main()