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
    "obj_item107_ministim": "Magic Mag",
    "obj_weapon_REP_11": "57 Fusion Classic",
    "obj_perk_dodgeheat": "Unceasing",
}

CLASS_GROUP_BY_INDEX = {
    1: "Guardian",
    2: "Rogue",
    3: "Commando",
    4: "Specialist",
}

# Higher index = more loadout freedom. Not stored in presets.
CHEAT_LEVELS: list[tuple[str, str]] = [
    ("Vanilla", "This class group's usual choices only. Cores stay locked."),
    ("Omniclass", "Any starter-pool object of this slot's type, any class. Cores locked."),
    ("Uber Omniclass", "Omniclass, plus swapping class cores (memory module and class item)."),
    ("Omnislots", "Any starter-pool object in any slot."),
    ("Unlimited", "Any item, weapon, perk, or artefact in the game data, any slot."),
]
DEFAULT_CHEAT_LEVEL = "Vanilla"
CHEAT_SQUARE_COUNT = 4  # black squares = rank; Vanilla is 0 filled squares
_SKIP_IDS = {"obj_perk_parent", "obj_item_parent", "obj_weapon_parent"}

SUBCLASS_CORES = {
    (1, 0): "obj_perk_riotguard",
    (1, 1): "obj_perk_breacher",
    (2, 0): "obj_perk_marksman",
    (2, 1): "obj_perk_assassin",
    (3, 0): "obj_perk_raider",
    (3, 1): "obj_perk_assaultgunner",
    (4, 0): "obj_perk_engineer",
    (4, 1): "obj_perk_demolisher",
}

# Starter items seen on each class group. Incomplete vs the full in-game picker.
VANILLA_ITEMS_BY_CLASS = {
    1: ["obj_item99_battlecry", "obj_item36_grenade_stun", "obj_item100_breachingcharge"],
    2: ["obj_item122_targetcpu", "obj_item83_grenade_smoke", "obj_item115_decoy", "obj_item94_dagger"],
    3: ["obj_item81_tanto", "obj_item55_stim", "obj_item86_commandoflare", "obj_item124_gunner"],
    4: [
        "obj_item71_sentry",
        "obj_item130_riotguard",
        "obj_item126_missiledrone",
        "obj_item6_reloader",
        "obj_item101_resonator",
    ],
}

VANILLA_PISTOLS_BY_CLASS = {
    1: ["obj_weapon_CP_38"],
    2: ["obj_weapon_DE_94", "obj_weapon_REP_11"],
    3: ["obj_weapon_HON_34", "obj_weapon_REP_11"],
    4: [
        "obj_weapon_PTL_6",
        "obj_weapon_REV_9",
        "obj_weapon_LSP_21",
        "obj_weapon_PXS_10",
        "obj_weapon_REP_11",
        "obj_weapon_A9_55",
        "obj_weapon_DE_61",
        "obj_weapon_HLP_64",
        "obj_weapon_TEC_84",
    ],
}


def cheat_rank(level: str) -> int:
    names = [name for name, _ in CHEAT_LEVELS]
    try:
        return names.index(level)
    except ValueError:
        return names.index(DEFAULT_CHEAT_LEVEL)


def normalize_cheat_level(level: str | None) -> str:
    names = {name for name, _ in CHEAT_LEVELS}
    if level in names:
        return level
    return DEFAULT_CHEAT_LEVEL


def cheat_blurb(level: str) -> str:
    level = normalize_cheat_level(level)
    for name, blurb in CHEAT_LEVELS:
        if name == level:
            return blurb
    return ""


def slot_editable(slot: int, cheat_level: str, vanilla_editable: bool) -> bool:
    """Every slot is clickable; cheat level is a picker filter, not a lock."""
    return True


def minimum_cheat_level(
    object_id: str | None,
    slot: int,
    class_index: int,
    class_equipped: list[str] | None = None,
    subclass_index: int = 0,
) -> str:
    """Lowest cheat level at which this object is legal in this slot."""
    if not object_id:
        return "Vanilla"
    for name, _ in CHEAT_LEVELS:
        options = options_for_slot(
            slot, class_index, name, class_equipped, subclass_index=subclass_index
        )
        if object_id in options:
            return name
    return "Unlimited"


def loadout_cheat_level(
    slots: list[str | None],
    class_index: int,
    class_equipped: list[str] | None = None,
    subclass_index: int = 0,
) -> str:
    """Highest slot requirement — one non-Vanilla pick raises the whole loadout."""
    rank = 0
    name = "Vanilla"
    for slot, object_id in enumerate(slots):
        level = minimum_cheat_level(object_id, slot, class_index, class_equipped, subclass_index)
        this_rank = cheat_rank(level)
        if this_rank > rank:
            rank = this_rank
            name = level
    return name


def cheat_square_text(level: str) -> str:
    """■ x rank, □ filling out to 4, then the rank number. Vanilla is 0."""
    rank = cheat_rank(level)
    squares = ("■" * rank) + ("□" * (CHEAT_SQUARE_COUNT - rank))
    return f"{squares} {rank}"


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


_NAME_SOURCES = (
    ("perks.json", "perks"),
    ("items.json", "items"),
    ("weapons.json", "weapons"),
    ("other_pool.json", "artefacts"),
)


def display_name(object_id: str | None) -> str:
    """Player-facing in-game label when we have one, otherwise the object suffix."""
    if not object_id:
        return "(empty)"
    if object_id in CONFIRMED_NAMES:
        return CONFIRMED_NAMES[object_id]
    for file_name, key in _NAME_SOURCES:
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
    for file_name, key in _NAME_SOURCES:
        for entry in _entries(file_name, key):
            if entry.get("id") == object_id:
                group = entry.get("class_group")
                if group:
                    return group.replace(" (class core)", "")
                return None
    return None


def entry_search_text(object_id: str) -> str:
    """All text the filter matches against for one object.

    The in-game label is first so queries like "magic mag" hit the official name.
    """
    parts = [display_name(object_id), object_id, class_group_of(object_id) or ""]
    for file_name, key in _NAME_SOURCES:
        for entry in _entries(file_name, key):
            if entry.get("id") != object_id:
                continue
            for field in ("name_guess", "subtitle", "description_guess"):
                value = entry.get(field)
                if isinstance(value, str):
                    parts.append(value)
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


def _unique_ids(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_ids = []
    for object_id in ids:
        if object_id and object_id not in seen and object_id not in _SKIP_IDS:
            seen.add(object_id)
            unique_ids.append(object_id)
    return unique_ids


def equipped_on_class(lines: list[str], class_index: int) -> list[str]:
    """Object ids currently in either subclass loadout for this class."""
    ids: list[str] = []
    for subclass_index in (0, 1):
        loadout = loadouts.read_loadout(lines, class_index, subclass_index)
        ids.extend(value for value in loadout["slots"] if value)
    return ids


def _typed(ids: list[str], kind: str) -> list[str]:
    prefixes = {
        "weapons": "obj_weapon",
        "items": "obj_item",
        "perks": "obj_perk",
        "artefacts": "obj_artefact",
    }
    prefix = prefixes[kind]
    return [object_id for object_id in ids if object_id.startswith(prefix)]


def options_for_slot(
    slot: int,
    class_index: int,
    restriction: str = DEFAULT_CHEAT_LEVEL,
    class_equipped: list[str] | None = None,
    subclass_index: int = 0,
) -> list[str]:
    """Candidate object ids for one slot at a cheat level."""
    level = normalize_cheat_level(restriction)
    rank = cheat_rank(level)
    kind = slot_kind(slot)
    equipped = class_equipped or []

    if rank >= 4:
        ids = all_ids("weapons") + all_ids("items") + all_ids("perks") + all_ids("artefacts")
    elif rank >= 3:
        ids = pool_ids("weapons") + pool_ids("items") + pool_ids("perks")
    elif slot == 0:
        own_core = SUBCLASS_CORES.get((class_index, subclass_index))
        if rank < 2:
            ids = [own_core] if own_core else sorted(class_core_ids())
        else:
            ids = sorted(class_core_ids())
    elif kind == "weapons":
        if rank == 0:
            ids = vanilla_pistols(class_index, equipped)
        else:
            ids = pool_ids("weapons")
    elif kind == "items":
        if rank == 0:
            ids = list(VANILLA_ITEMS_BY_CLASS.get(class_index, []))
        else:
            ids = pool_ids("items")
    else:
        ids = class_perk_ids(class_index)
        if rank >= 1:
            for perk_id in pool_ids("perks"):
                if perk_id not in class_core_ids() and perk_id not in ids:
                    ids.append(perk_id)

    if slot in (1, 2, 4, 5, 6, 7, 8):
        ids = [RANDOM_MODULE_ID] + ids
    return _unique_ids(ids)


def vanilla_pistols(class_index: int, equipped: list[str] | None = None) -> list[str]:
    """Starter pistols this class can pick in-game.

    Specialist list is from the Engineer screenshot. Other groups are the
    pistols seen on that class in the extracted save — still incomplete.
    `equipped` is ignored so a cheated pistol cannot launder itself as Vanilla.
    """
    del equipped
    pool = set(pool_ids("weapons"))
    return [object_id for object_id in VANILLA_PISTOLS_BY_CLASS.get(class_index, []) if object_id in pool]


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
    return [
        str(entry["id"])
        for entry in _kind_entries(kind)
        if entry.get("in_loadout_pool") and entry.get("id")
    ]


def all_ids(kind: str) -> list[str]:
    """Every extracted object id of this kind, including non-starter gear."""
    return [str(entry["id"]) for entry in _kind_entries(kind) if entry.get("id")]


def _kind_entries(kind: str) -> list[dict]:
    files = {
        "perks": ("perks.json", "perks"),
        "items": ("items.json", "items"),
        "weapons": ("weapons.json", "weapons"),
        "artefacts": ("other_pool.json", "artefacts"),
    }
    file_name, key = files[kind]
    return _entries(file_name, key)


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
