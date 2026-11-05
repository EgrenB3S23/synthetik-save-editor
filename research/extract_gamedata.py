"""Extract loadout-related game data into research/gamedata/*.json.

Read-only. Sources:
- Synthetik's data.win (object names + English string table)
- A Save.sav (loadout pool, equipped slots, slot type codes)
- variables.py (the 62 class perks, grouped by class — verified by hand)

Usage:
    py research/extract_gamedata.py [path/to/data.win] [path/to/Save.sav]
"""

from __future__ import annotations

import json
import os
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loadouts  # noqa: E402
import variables  # noqa: E402

OUT = Path(__file__).resolve().parent / "gamedata"
DEFAULT_DATA_WIN = Path(r"E:\Spel\SteamLibrary\steamapps\common\Synthetik\data.win")
DEFAULT_SAVE = Path(os.environ.get("LOCALAPPDATA", "")) / "Synthetik" / "Save.sav"

# The string table holds every language; English comes first and ends before this index.
ENGLISH_STRING_LIMIT = 6580

CLASS_GROUPS = {
    1: "Guardian",
    2: "Rogue",
    3: "Commando",
    4: "Specialist",
}


# ---------------------------------------------------------------- data.win


def read_datawin(path: Path) -> tuple[list[str], list[str], list[str], dict[str, str]]:
    """Return (object names, strings, sprite names, object→sprite) from a GameMaker data.win."""
    with path.open("rb") as f:
        magic, form_size = struct.unpack("<4sI", f.read(8))
        if magic != b"FORM":
            raise ValueError(f"{path} is not a GameMaker data file")

        chunks = {}
        while f.tell() < 8 + form_size:
            name, size = struct.unpack("<4sI", f.read(8))
            chunks[name.decode()] = (f.tell(), size)
            f.seek(size, 1)

        def pointers(offset: int) -> list[int]:
            f.seek(offset)
            (count,) = struct.unpack("<I", f.read(4))
            return list(struct.unpack(f"<{count}I", f.read(4 * count)))

        def string_at(address: int) -> str:
            f.seek(address - 4)
            (length,) = struct.unpack("<I", f.read(4))
            return f.read(length).decode("utf-8", errors="replace")

        strings = []
        for pointer in pointers(chunks["STRG"][0]):
            f.seek(pointer)
            (length,) = struct.unpack("<I", f.read(4))
            strings.append(f.read(length).decode("utf-8", errors="replace"))

        sprites = []
        for pointer in pointers(chunks["SPRT"][0]):
            f.seek(pointer)
            (name_pointer,) = struct.unpack("<I", f.read(4))
            sprites.append(string_at(name_pointer))

        objects = []
        object_sprites = {}
        for pointer in pointers(chunks["OBJT"][0]):
            f.seek(pointer)
            name_pointer, sprite_index = struct.unpack("<Ii", f.read(8))
            name = string_at(name_pointer)
            objects.append(name)
            if 0 <= sprite_index < len(sprites):
                object_sprites[name] = sprites[sprite_index]

    return objects, strings, sprites, object_sprites


# ---------------------------------------------------------------- save


def read_save(path: Path) -> dict[str, str]:
    pattern = re.compile(r'^(.+?)="(.*)"$')
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


# ---------------------------------------------------------------- name guessing


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def english_names(strings: list[str]) -> list[tuple[int, str]]:
    """Upper-case lines from the English part: candidate display names."""
    names = []
    for index, text in enumerate(strings[:ENGLISH_STRING_LIMIT]):
        text = text.strip()
        if (
            2 <= len(text) <= 40
            and text == text.upper()
            and re.search(r"[A-Z]", text)
            and "_" not in text
            and not text.endswith(":")
            and " TO " not in f" {text} "
            and len(text.split()) <= 5
        ):
            names.append((index, text))
    return names


def _is_weapon_code(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9 .\-]{0,5}", text.strip()))


def _is_weapon_name(text: str) -> bool:
    text = text.strip()
    return bool(
        text
        and text == text.upper()
        and 3 <= len(text) <= 30
        and re.search(r"[A-Z]", text)
        and not _is_weapon_code(text)
    )


def weapon_name_pairs(strings: list[str]) -> list[tuple[int, str, str]]:
    """Weapons are listed as FULL NAME + short code, in either order."""
    pairs = []
    used: set[int] = set()
    for index in range(ENGLISH_STRING_LIMIT - 1):
        if index in used:
            continue
        left, right = strings[index].strip(), strings[index + 1].strip()
        if _is_weapon_name(left) and _is_weapon_code(right) and left != right:
            pairs.append((index, left, right))
            used.update((index, index + 1))
        elif _is_weapon_code(left) and _is_weapon_name(right) and left != right:
            pairs.append((index, right, left))
            used.update((index, index + 1))
    return pairs


def guess_weapon_name(prefix: str, pairs, names=None, strings=None) -> dict:
    """Match the object prefix (HON, PXS, A9...) to a weapon short code or name start."""
    key = normalize(prefix)

    def prefix_hit(label: str) -> bool:
        return label.upper().startswith(prefix.upper()) and (
            len(label) == len(prefix) or not label[len(prefix)].isalpha()
        )

    by_code = [(i, n, c) for i, n, c in pairs if normalize(c) == key]
    by_name = [(i, n, c) for i, n, c in pairs if prefix_hit(n)]
    matches = by_code or by_name
    found = sorted({n for _, n, _ in matches})
    if len(found) == 1:
        index, name, code = matches[0]
        return {
            "name_guess": name,
            "short_code": code,
            "confidence": "code" if by_code else "name-prefix",
        }
    if found:
        return {"name_guess": None, "confidence": "ambiguous", "candidates": found[:8]}
    if names:
        named = [(i, n) for i, n in names if prefix_hit(n)]
        unique = sorted({n for _, n in named})
        if len(unique) == 1:
            index, name = named[0]
            return {
                "name_guess": name,
                "confidence": "name-prefix",
                "description_guess": description_after(strings or [], index),
            }
    return {"name_guess": None, "confidence": "none"}


def description_after(strings: list[str], index: int) -> str | None:
    """First mixed-case line within 3 lines after a name: likely its description."""
    for text in strings[index + 1 : index + 4]:
        if text != text.upper() and len(text) > 20:
            return text.replace("#", " / ")
    return None


def sprite_name_key(sprite_name: str) -> str:
    """spr_item_magicmag → magicmag, used to match MAGIC MAG."""
    text = sprite_name.lower()
    text = re.sub(r"^spr_item_?", "", text)
    text = re.sub(r"^spr_", "", text)
    text = re.sub(r"_n$", "", text)
    return normalize(text)


def guess_name(object_id: str, short_id: str, names, strings, extra_keys: list[str] | None = None) -> dict:
    """Best-effort display name. Confidence: exact / contains / none."""
    keys = [normalize(key) for key in (extra_keys or []) + [short_id] if normalize(key) and len(normalize(key)) >= 3]
    seen: set[str] = set()
    unique_keys = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique_keys.append(key)

    for key in unique_keys:
        exact = [(i, n) for i, n in names if normalize(n) == key]
        if exact:
            index, name = exact[0]
            return {
                "name_guess": name,
                "confidence": "exact",
                "description_guess": description_after(strings, index),
            }

    for key in unique_keys:
        def close_enough(name: str, match_key: str = key) -> bool:
            norm = normalize(name)
            if len(match_key) >= 4 and match_key in norm:
                return True
            return len(norm) >= 4 and norm in match_key and len(norm) >= 0.6 * len(match_key)

        contains = [(i, n) for i, n in names if close_enough(n)]
        if len(contains) == 1:
            index, name = contains[0]
            return {
                "name_guess": name,
                "confidence": "contains",
                "description_guess": description_after(strings, index),
            }
        if contains:
            return {
                "name_guess": None,
                "confidence": "ambiguous",
                "candidates": sorted({n for _, n in contains})[:8],
            }
    return {"name_guess": None, "confidence": "none"}


ITEM_CATALOG_START = "CHAOS POTION"
ITEM_CATALOG_END = "PSY CLOUD GRENADE"


def is_item_title(text: str) -> bool:
    text = text.strip()
    return bool(
        text
        and text == text.upper()
        and re.search(r"[A-Z]", text)
        and "_" not in text
        and "@" not in text
        and not text.endswith(":")
        and not text.startswith("#")
        and 2 <= len(text) <= 40
    )


def is_item_description(text: str) -> bool:
    text = text.strip()
    return len(text) > 20 and text != text.upper()


def parse_item_catalog(strings: list[str]) -> list[dict]:
    """English loadout-item labels from the string table: name, subtitle, description.

    They run in item-number order from CHAOS POTION through PSY CLOUD GRENADE.
    """
    try:
        index = strings.index(ITEM_CATALOG_START)
        end = strings.index(ITEM_CATALOG_END)
    except ValueError:
        return []

    entries: list[dict] = []
    while index <= end:
        if not is_item_title(strings[index]):
            index += 1
            continue
        name = strings[index].strip()
        index += 1
        subtitle = None
        if index < len(strings) and is_item_title(strings[index]):
            nxt = strings[index + 1] if index + 1 < len(strings) else ""
            nxt2 = strings[index + 2] if index + 2 < len(strings) else ""
            if is_item_description(nxt):
                subtitle = strings[index].strip()
                index += 1
            elif is_item_title(nxt) and is_item_description(nxt2):
                pass
            else:
                subtitle = strings[index].strip()
                index += 1
        description = None
        if index < len(strings) and is_item_description(strings[index]):
            description = strings[index].replace("#", " / ")
            index += 1
            while index < len(strings) and is_item_description(strings[index]):
                index += 1
        entries.append({"name": name, "subtitle": subtitle, "description": description})
        if name == ITEM_CATALOG_END:
            break
    return entries


def _longest_overlap(left: str, right: str) -> int:
    if not left or not right:
        return 0
    limit = min(len(left), len(right))
    for length in range(limit, 4, -1):
        for start in range(len(left) - length + 1):
            if left[start : start + length] in right:
                return length
    return 0


def _catalog_match_score(object_id: str, sprite_name: str, entry: dict) -> int:
    suffix = normalize(short_id(object_id))
    sprite = sprite_name_key(sprite_name)
    name = normalize(entry.get("name") or "")
    subtitle = normalize(entry.get("subtitle") or "")
    haystack = name + subtitle
    score = 0
    if suffix and suffix == name:
        score += 100
    if sprite and sprite == name:
        score += 100
    if suffix and name and len(suffix) >= 6 and sorted(suffix) == sorted(name):
        score += 90
    if suffix and len(suffix) >= 4 and suffix in haystack:
        score += 40
    if sprite and len(sprite) >= 4 and sprite in haystack:
        score += 40
    overlap = max(_longest_overlap(suffix, haystack), _longest_overlap(sprite, haystack))
    if overlap >= 5:
        score += overlap * 2
    return score


def assign_item_catalog(
    item_ids: list[str], catalog: list[dict], object_sprites: dict[str, str]
) -> dict[str, dict]:
    """Map official catalog labels onto obj_item ids.

    Strong suffix/sprite matches first (so MAGIC MAG follows spr_item_magicmag even
    when the object is named ministim). Remaining labels fill by item number.
    """
    by_number: dict[int, list[str]] = {}
    for object_id in item_ids:
        match = re.match(r"obj_item(\d+)_", object_id)
        if match:
            by_number.setdefault(int(match.group(1)), []).append(object_id)

    assigned: dict[str, dict] = {}
    used_ids: set[str] = set()
    used_entries: set[int] = set()

    def apply(object_id: str, entry: dict, catalog_index: int) -> None:
        assigned[object_id] = {
            "name_guess": entry["name"],
            "subtitle": entry.get("subtitle"),
            "confidence": "catalog",
            "description_guess": entry.get("description"),
        }
        used_ids.add(object_id)
        used_entries.add(catalog_index)

    pairs: list[tuple[int, str, int]] = []
    for object_id in item_ids:
        sprite = object_sprites.get(object_id, "")
        for catalog_index, entry in enumerate(catalog):
            score = _catalog_match_score(object_id, sprite, entry)
            if score >= 40:
                pairs.append((score, object_id, catalog_index))
    pairs.sort(key=lambda row: (-row[0], row[2], row[1]))
    for _, object_id, catalog_index in pairs:
        if object_id in used_ids or catalog_index in used_entries:
            continue
        apply(object_id, catalog[catalog_index], catalog_index)

    for catalog_index, entry in enumerate(catalog):
        if catalog_index in used_entries:
            continue
        candidates = [object_id for object_id in by_number.get(catalog_index + 1, []) if object_id not in used_ids]
        if not candidates:
            continue
        scored = [
            (_catalog_match_score(object_id, object_sprites.get(object_id, ""), entry), object_id)
            for object_id in candidates
        ]
        best = max(score for score, _ in scored)
        stems = {re.sub(r"\d+$", "", short_id(object_id)) for object_id in candidates}
        if best == 0 and (len(candidates) == 1 or len(stems) == 1):
            winners = candidates
        elif best == 0:
            continue
        else:
            winners = [object_id for score, object_id in scored if score == best]
        for object_id in winners:
            apply(object_id, entry, catalog_index)
    return assigned


PERK_CATALOG_START = "CORE: UNYIELDING"
PERK_CATALOG_END = "SUN RISING"

# Loadout-visible English labels that the suffix/sprite heuristic cannot reach.
PERK_CORE_LABELS = {
    "obj_perk_riotguard": "CORE: UNYIELDING",
    "obj_perk_breacher": "CORE: CHARGE",
    "obj_perk_marksman": "CORE: STEADY AIM",
    "obj_perk_assassin": "CORE: PROFESSIONAL",
    "obj_perk_raider": "CORE: RANK UP",
    "obj_perk_assaultgunner": "CORE: ENGAGE",
    "obj_perk_engineer": "CORE: DRONE ZEAL",
    "obj_perk_demolisher": "CORE: PULVERIZE",
    "obj_perk_morph": "CORE: MORPH",
    "obj_perk_calm": "CORE: CALM",
    "obj_perk_randomperk": "RANDOM MODULE",
}

PERK_ALIASES = {
    "headshotammo": "HEAD HUNTER",
    "ejectsurge": "SWITCH POSITION",
    "dodgeboost": "EVASIVE MANEUVERS",
    "dance": "SPOTTER",
    "longrange": "KEEPING DISTANCE",
    "specialized": "DMR CONVERSION",
    "powertuning": "KEEPING COOL",
    "healthy": "AGAINST THE ODDS",
    "stealback": "BLOOD BORNE",
    "pistolextender": "WEAPONS DEAL",
    "classweapon": "CLASS WEAPON",
    "reloadstack": "ROUTINE",
    "powerstep": "CHARGE",
    "fieldration": "FIELD RATIONS",
    "reloadsurge": "PRESS THE ATTACK",
    "wepupgrade": "PACK A PUNCH",
    "holdbreath": "HOLD BREATH",
    "combo": "MADNESS",
    "drill": "DEXTERITY",
    "hframe": "CHROMATIC ALLOY",
    "selfrepair": "INNER FIRE",
    "itemcdvariant": "OVERDRIVE",
    "heatcontrol": "CALCULATED",
    "force": "UNSTOPPABLE FORCE",
    "sunrise": "SUN RISING",
    "dodgeheat": "UNCEASING",
}


def parse_perk_catalog(strings: list[str]) -> list[dict]:
    """English class-module labels: CORE: UNYIELDING through SUN RISING."""
    try:
        index = strings.index(PERK_CATALOG_START)
        end = strings.index(PERK_CATALOG_END)
    except ValueError:
        return []

    entries: list[dict] = []
    while index <= end:
        if not is_item_title(strings[index]):
            index += 1
            continue
        name = strings[index].strip()
        index += 1
        description = None
        if index < len(strings) and is_item_description(strings[index]):
            description = strings[index].replace("#", " / ")
            index += 1
        entries.append({"name": name, "subtitle": None, "description": description})
        if name == PERK_CATALOG_END:
            break
    return entries


def parse_extra_core_labels(strings: list[str]) -> list[dict]:
    """Later CORE: titles (Charge, Drone Zeal, Pulverize, …) with their descriptions."""
    entries = []
    seen = set()
    for index, text in enumerate(strings[:ENGLISH_STRING_LIMIT]):
        name = text.strip()
        if not name.startswith("CORE:") or name in seen:
            continue
        seen.add(name)
        description = None
        if index + 1 < len(strings) and is_item_description(strings[index + 1]):
            description = strings[index + 1].replace("#", " / ")
        entries.append({"name": name, "subtitle": None, "description": description})
    return entries


def assign_perk_catalog(
    perk_ids: list[str], catalog: list[dict], extra_cores: list[dict], object_sprites: dict[str, str]
) -> dict[str, dict]:
    """Map official module labels onto obj_perk ids."""
    by_name = {entry["name"]: entry for entry in extra_cores}
    by_name.update({entry["name"]: entry for entry in catalog})
    assigned: dict[str, dict] = {}
    used_ids: set[str] = set()
    used_names: set[str] = set()

    def apply(object_id: str, label: str) -> None:
        entry = by_name.get(label) or {"name": label, "subtitle": None, "description": None}
        assigned[object_id] = {
            "name_guess": entry["name"],
            "subtitle": entry.get("subtitle"),
            "confidence": "catalog",
            "description_guess": entry.get("description"),
        }
        used_ids.add(object_id)
        used_names.add(entry["name"])

    for object_id, label in PERK_CORE_LABELS.items():
        if object_id in perk_ids:
            apply(object_id, label)

    guardian = next((ids for group, ids in variables.PERK_CLASSES if group == "Guardian"), [])
    start = next((i for i, entry in enumerate(catalog) if entry["name"] == "CORE: UNYIELDING"), None)
    if start is not None:
        names = [
            entry["name"]
            for entry in catalog[start + 1 :]
            if entry.get("description") and not entry["name"].startswith("CORE:")
        ][: len(guardian)]
        if len(names) == len(guardian):
            for perk_id, label in zip(guardian, names):
                object_id = f"obj_perk_{perk_id}"
                if object_id not in used_ids:
                    apply(object_id, label)

    for suffix, label in PERK_ALIASES.items():
        object_id = f"obj_perk_{suffix}"
        if object_id in perk_ids and object_id not in used_ids:
            apply(object_id, label)

    remaining_catalog = [entry for entry in catalog if entry["name"] not in used_names]
    remaining_ids = [object_id for object_id in perk_ids if object_id not in used_ids]
    pairs: list[tuple[int, str, int]] = []
    for object_id in remaining_ids:
        sprite = object_sprites.get(object_id, "")
        for index, entry in enumerate(remaining_catalog):
            score = _catalog_match_score(object_id, sprite, entry)
            if score >= 40:
                pairs.append((score, object_id, index))
    pairs.sort(key=lambda row: (-row[0], row[2], row[1]))
    taken_entries: set[int] = set()
    for _, object_id, index in pairs:
        if object_id in used_ids or index in taken_entries:
            continue
        apply(object_id, remaining_catalog[index]["name"])
        taken_entries.add(index)
    return assigned


# ---------------------------------------------------------------- build


def equipped_map(save: dict[str, str]) -> dict[str, list[dict]]:
    """object id -> where it is currently equipped in this save."""
    equipped: dict[str, list[dict]] = {}
    for class_index, subclass_index, name in loadouts.SUBCLASSES:
        for slot in range(loadouts.SLOT_COUNT):
            value = save.get(loadouts.slot_variable(class_index, subclass_index, slot))
            if value:
                equipped.setdefault(value, []).append({"subclass": name, "slot": slot})
    return equipped


def short_id(object_id: str) -> str:
    for prefix in (r"obj_perk_", r"obj_item\d+_", r"obj_weapon_", r"obj_artefact_", r"T_"):
        match = re.match(prefix, object_id)
        if match:
            return object_id[match.end():]
    return object_id


def build_entries(
    ids,
    save,
    equipped,
    names,
    strings,
    perk_groups=None,
    weapon_pairs=None,
    object_sprites=None,
    official_names=None,
) -> list[dict]:
    entries = []
    object_sprites = object_sprites or {}
    official_names = official_names or {}
    for object_id in ids:
        unlock = save.get(f"tunlock_{object_id}")
        entry = {
            "id": object_id,
            "in_loadout_pool": unlock is not None,
            "tunlock_value": None if unlock is None else unlock,
            "daily_boost": save.get(f"tpoints_{object_id}"),
            "class_group": (perk_groups or {}).get(object_id),
            "equipped_in_this_save": equipped.get(object_id, []),
        }
        if object_id.startswith("obj_item"):
            match = re.match(r"obj_item(\d+)_", object_id)
            entry["item_number"] = int(match.group(1)) if match else None

        sid = short_id(object_id)
        if object_id in official_names:
            entry.update(official_names[object_id])
        elif object_id.startswith("obj_weapon_"):
            entry.update(
                guess_weapon_name(
                    re.sub(r"_\d+$", "", sid), weapon_pairs or [], names=names, strings=strings
                )
            )
        else:
            extra = []
            sprite = object_sprites.get(object_id)
            if sprite:
                extra.append(sprite_name_key(sprite))
            entry.update(guess_name(object_id, sid, names, strings, extra_keys=extra))
        entries.append(entry)
    return entries


def write_json(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    data_win = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA_WIN
    save_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SAVE

    objects, strings, sprites, object_sprites = read_datawin(data_win)
    save = read_save(save_path)
    equipped = equipped_map(save)
    names = english_names(strings)

    perk_groups = {
        f"obj_perk_{perk_id}": group
        for group, perk_ids in variables.PERK_CLASSES
        for perk_id in perk_ids
    }
    for class_index, subclass_index, _ in loadouts.SUBCLASSES:
        core = save.get(loadouts.slot_variable(class_index, subclass_index, 0))
        if core:
            perk_groups[core] = f"{CLASS_GROUPS[class_index]} (class core)"

    skip = {"obj_perk_parent", "obj_item_parent", "obj_weapon_parent"}

    def pick(pattern: str) -> list[str]:
        return sorted(o for o in objects if re.match(pattern, o) and o not in skip)

    perks = pick(r"^obj_perk_")
    items = sorted(pick(r"^obj_item\d+_"), key=lambda o: int(re.match(r"obj_item(\d+)_", o).group(1)))
    weapons = pick(r"^obj_weapon_[A-Za-z0-9]+_\d+$")
    weapon_other = sorted(set(pick(r"^obj_weapon_")) - set(weapons))
    artefacts = pick(r"^obj_artefact_")
    pool_talents = sorted(k[len("tunlock_"):] for k in save if k.startswith("tunlock_T_"))

    meta = {
        "source_data_win": data_win.name,
        "source_save": save_path.name,
        "game_version": save.get("version"),
        "note": "Generated by research/extract_gamedata.py. name_guess values with "
        "confidence 'catalog' are English in-game labels. Other name_guess/"
        "description_guess fields are heuristic matches and must be verified in-game.",
    }

    official_names = {}
    official_names.update(assign_item_catalog(items, parse_item_catalog(strings), object_sprites))
    official_names.update(
        assign_perk_catalog(
            perks, parse_perk_catalog(strings), parse_extra_core_labels(strings), object_sprites
        )
    )
    write_json(
        "perks.json",
        {
            "meta": meta,
            "perks": build_entries(
                perks,
                save,
                equipped,
                names,
                strings,
                perk_groups,
                object_sprites=object_sprites,
                official_names=official_names,
            ),
        },
    )
    write_json(
        "items.json",
        {
            "meta": meta,
            "items": build_entries(
                items,
                save,
                equipped,
                names,
                strings,
                object_sprites=object_sprites,
                official_names=official_names,
            ),
        },
    )
    write_json(
        "weapons.json",
        {
            "meta": meta,
            "weapons": build_entries(
                weapons,
                save,
                equipped,
                names,
                strings,
                weapon_pairs=weapon_name_pairs(strings),
                object_sprites=object_sprites,
            ),
            "other_weapon_objects": weapon_other,
        },
    )
    write_json(
        "other_pool.json",
        {
            "meta": meta,
            "artefacts": build_entries(
                artefacts, save, equipped, names, strings, object_sprites=object_sprites
            ),
            "talents_in_pool": build_entries(
                pool_talents, save, equipped, names, strings, object_sprites=object_sprites
            ),
        },
    )

    slot_groups = {}
    for class_index in range(5):
        slot_groups[str(class_index)] = [save.get(f"slot{slot}perkgroup{class_index}") for slot in range(10)]
    current = {
        name: [save.get(loadouts.slot_variable(c, s, slot)) for slot in range(10)]
        for c, s, name in loadouts.SUBCLASSES
    }
    write_json(
        "slots_observed.json",
        {
            "meta": meta,
            "slot_variable_pattern": "perkslot<slot>class<class><subclass>",
            "slot_perkgroup_by_class_index": slot_groups,
            "current_loadouts": current,
        },
    )

    classes = {
        "meta": meta,
        "class_groups_in_string_table": ["GENERIC", "GUARDIAN", "ROGUE", "SOLDIER", "SPECIALIST"],
        "classes": [
            {
                "class_index": c,
                "subclass_index": s,
                "name": name,
                "class_group": CLASS_GROUPS[c],
                "save_prefix": f"class{c}{s}",
                "token_prefix": f"_{c}_{s}__",
            }
            for c, s, name in loadouts.SUBCLASSES
        ],
    }
    write_json("classes.json", classes)

    relevant = [
        name
        for name in sprites
        if re.search(r"(item|weapon|perk|pistol|module)", name, re.I)
    ]
    write_json(
        "sprites.json",
        {
            "meta": {
                **meta,
                "note": "Sprite *names* from the SPRT chunk. Pixel data lives in TXTR "
                "(~400MB) and is not exported. Icons for the GUI would need a texture-page decoder.",
                "sprite_count": len(sprites),
            },
            "names_matching_item_weapon_perk": relevant,
        },
    )

    print(
        f"{len(perks)} perks, {len(items)} items, {len(weapons)} weapons, "
        f"{len(artefacts)} artefacts, {len(pool_talents)} talents in pool, "
        f"{len(sprites)} sprites ({len(relevant)} name-matched)"
    )


if __name__ == "__main__":
    main()
