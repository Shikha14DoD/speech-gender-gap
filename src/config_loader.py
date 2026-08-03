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


def get_leader_config(lookup_key: str, config: dict) -> dict:
    """
    Look up a single leader's config entry, matching by country name
    OR leader name (case-insensitive). Needed since some countries now
    have more than one leader tracked (e.g. China: Xi Jinping AND Li
    Qiang) -- country name alone isn't unique in that case.
    """
    for entry in config["leaders"]:
        if entry["country"].lower() == lookup_key.lower():
            return entry
    for entry in config["leaders"]:
        # Compare with spaces stripped from both sides, so "liqiang"
        # matches a leader name like "Li Qiang".
        normalized_lookup = lookup_key.lower().replace(" ", "")
        normalized_leader = entry["leader"].lower().replace(" ", "")
        if normalized_lookup in normalized_leader:
            return entry
    raise ValueError(f"No config entry found for: {lookup_key}")