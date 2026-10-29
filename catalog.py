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


def labeled(object_id: str | None, multiline: bool = True) -> str:
    """In-game name plus the save value, for the card and picker."""
    if not object_id:
        return "(empty)"
    name = display_name(object_id)
    if name == object_id:
        return object_id
    return f"{name}\n{object_id}" if multiline else f"{name}  ({object_id})"


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


def item_id_for_number(number: int) -> str | None:
    """obj_item id whose number matches a token index, if one exists."""
    for entry in _entries("items.json", "items"):
        if entry.get("item_number") == number and entry.get("id"):
            return str(entry["id"])
    return None


def _suffix_number(object_id: str) -> int | None:
    suffix = object_id.rsplit("_", 1)[-1]
    return int(suffix) if suffix.isdigit() else None


def weapon_id_for_number(number: int) -> str | None:
    """obj_weapon id whose trailing number matches a token index.

    Observed: token 11 is obj_weapon_REP_11, matching spr_weapon11_REP_icon.
    If two objects share a number, prefer one with a name guess.
    """
    matches = [
        entry
        for entry in _entries("weapons.json", "weapons")
        if entry.get("id") and _suffix_number(str(entry["id"])) == number
    ]
    if not matches:
        return None
    matches.sort(key=lambda entry: (not entry.get("name_guess"), not entry.get("in_loadout_pool"), entry["id"]))
    return str(matches[0]["id"])


def slot_kind(slot: int) -> str:
    """Which pool a loadout slot usually holds."""
    if slot == 9:
        return "weapons"
    if slot in (1, 3, 4, 5):
        return "items"
    return "perks"


def options_for_slot(slot: int, class_index: int, restriction: str = "Omniclass") -> list[str]:
    """Candidate object ids for one slot. restriction: Vanilla / Omniclass / Omnislots."""
    if restriction == "Omnislots":
        ids = pool_ids("weapons") + pool_ids("items") + pool_ids("perks")
    elif slot == 0:
        ids = sorted(class_core_ids())
    elif slot_kind(slot) == "weapons":
        ids = pool_ids("weapons")
    elif slot_kind(slot) == "items":
        ids = pool_ids("items")
    else:
        ids = class_perk_ids(class_index)
        if restriction != "Vanilla":
            for perk_id in pool_ids("perks"):
                if perk_id not in class_core_ids() and perk_id not in ids:
                    ids.append(perk_id)

    if slot in (1, 2, 4, 5, 6, 7, 8):
        ids = [RANDOM_MODULE_ID] + ids

    seen: set[str] = set()
    unique_ids = []
    for object_id in ids:
        if object_id and object_id not in seen:
            seen.add(object_id)
            unique_ids.append(object_id)
    return unique_ids


def token_options(family: str) -> list[tuple[int, str]]:
    """(token number, object id) pairs for placing a weapon or item token."""
    rows: list[tuple[int, str]] = []
    if family.startswith("i"):
        for entry in _entries("items.json", "items"):
            number = entry.get("item_number")
            object_id = entry.get("id")
            if number is None or not object_id:
                continue
            rows.append((int(number), str(object_id)))
    else:
        seen: set[int] = set()
        ranked = sorted(
            _entries("weapons.json", "weapons"),
            key=lambda entry: (not entry.get("name_guess"), not entry.get("in_loadout_pool"), entry.get("id") or ""),
        )
        for entry in ranked:
            object_id = entry.get("id")
            if not object_id:
                continue
            number = _suffix_number(str(object_id))
            if number is None or number in seen:
                continue
            seen.add(number)
            rows.append((number, str(object_id)))
    rows.sort(key=lambda row: row[0])
    return rows


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
