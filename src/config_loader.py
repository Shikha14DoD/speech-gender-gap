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
    Look up a single leader's config entry, matching by an explicit
    'key' field first (needed since some people/countries now have
    multiple distinct config entries -- e.g. Xi Jinping has both an
    English SCIO source and a Chinese People's Daily source), then
    falling back to country name, then leader name.
    """
    for entry in config["leaders"]:
        if entry.get("key", "").lower() == lookup_key.lower():
            return entry
    for entry in config["leaders"]:
        if entry["country"].lower() == lookup_key.lower():
            return entry
    for entry in config["leaders"]:
        normalized_lookup = lookup_key.lower().replace(" ", "")
        normalized_leader = entry["leader"].lower().replace(" ", "")
        if normalized_lookup in normalized_leader:
            return entry
    raise ValueError(f"No config entry found for: {lookup_key}")