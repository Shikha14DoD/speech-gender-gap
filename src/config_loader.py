"""
Loads config.json (project root) into a simple Python object,
so scraper code never hardcodes URLs, leader names, or dates directly.
"""

import json
import os

# config.json lives at the project root, one level up from src/
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_leader_config(country: str, config: dict) -> dict:
    """Look up a single leader's config entry by country name (case-insensitive)."""
    for entry in config["leaders"]:
        if entry["country"].lower() == country.lower():
            return entry
    raise ValueError(f"No config entry found for country: {country}")