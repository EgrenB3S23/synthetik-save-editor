"""Names and lists for loadout slots. Reads research/gamedata JSON when present."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import loadouts
import variables

RANDOM_MODULE_ID = "obj_perk_randomperk"

# Confirmed in-game (screenshots / user). Overrides heuristic name_guess.
CONFIRMED_NAMES = {
    RANDOM_MODULE_ID: "RANDOM MODULE",
    "obj_perk_engineer": "Core: Drone Zeal",
    "obj_item71_sentry": "LMG Sentry Turret",
    "obj_item126_missiledrone": "Missile Drone",
    "obj_item6_reloader": "Field Supply",
    "obj_weapon_REP_11": "57 Fusion Classic",
    "obj_perk_dodgeheat": "Unceasing",
}

CLASS_GROUP_BY_INDEX = {
    1: "Guardian",
    2: "Rogue",
    3: "Commando",
    4: "Specialist",
}


def _gamedata_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base / "research" / "gamedata"


_json_cache: dict[str, dict] = {}


def _load_json(name: str) -> dict:
    if name in _json_cache:
        return _json_cache[name]
    path = _gamedata_dir() / name
    if not path.is_file():
        _json_cache[name] = {}
        return _json_cache[name]
    try:
        _json_cache[name] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _json_cache[name] = {}
    return _json_cache[name]


def _entries(file_name: str, key: str) -> list[dict]:
    data = _load_json(file_name)
    return list(data.get(key) or [])


def display_name(object_id: str | None) -> str:
    if not object_id:
        return "(empty)"
    if object_id in CONFIRMED_NAMES:
        return CONFIRMED_NAMES[object_id]
    for file_name, key in (("perks.json", "perks"), ("items.json", "items"), ("weapons.json", "weapons")):
        for entry in _entries(file_name, key):
            if entry.get("id") == object_id:
                guess = entry.get("name_guess")
                if guess:
                    return str(guess).title() if guess == guess.upper() else str(guess)
                break
    return loadouts.display_slot(object_id)


def class_group_of(object_id: str | None) -> str | None:
    if not object_id or object_id == RANDOM_MODULE_ID:
        return None
    for file_name, key in (("perks.json", "perks"), ("items.json", "items"), ("weapons.json", "weapons")):
        for entry in _entries(file_name, key):
            if entry.get("id") == object_id:
                group = entry.get("class_group")
                if group:
                    return group.replace(" (class core)", "")
                return None
    return None


def entry_search_text(object_id: str) -> str:
    """All text the filter matches against for one object."""
    parts = [object_id, display_name(object_id), class_group_of(object_id) or ""]
    for file_name, key in (("perks.json", "perks"), ("items.json", "items"), ("weapons.json", "weapons")):
        for entry in _entries(file_name, key):
            if entry.get("id") != object_id:
                continue
            for value in entry.values():
                if isinstance(value, str):
                    parts.append(value)
            break
    return " ".join(parts)


def subsequence_match(query: str, text: str) -> bool:
    """True if query characters appear in order in text (*q*u*e*r*y*). Case-insensitive."""
    needle = query.lower()
    haystack = text.lower()
    index = 0
    for char in needle:
        index = haystack.find(char, index)
        if index < 0:
            return False
        index += 1
    return True


def pool_ids(kind: str) -> list[str]:
    """Starter-pool object ids. kind is perks, items, or weapons."""
    file_name = {"perks": "perks.json", "items": "items.json", "weapons": "weapons.json"}[kind]
    key = kind
    ids = []
    for entry in _entries(file_name, key):
        if entry.get("in_loadout_pool") and entry.get("id"):
            ids.append(entry["id"])
    return ids


def class_perk_ids(class_index: int) -> list[str]:
    group = CLASS_GROUP_BY_INDEX[class_index]
    perk_ids = next((ids for name, ids in variables.PERK_CLASSES if name == group), [])
    return [f"obj_perk_{perk_id}" for perk_id in perk_ids]


def class_core_ids() -> set[str]:
    return {
        "obj_perk_riotguard",
        "obj_perk_breacher",
        "obj_perk_marksman",
        "obj_perk_assassin",
        "obj_perk_raider",
        "obj_perk_assaultgunner",
        "obj_perk_engineer",
        "obj_perk_demolisher",
    }
