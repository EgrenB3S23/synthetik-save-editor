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


def read_datawin(path: Path) -> tuple[list[str], list[str]]:
    """Return (object names, strings) from a GameMaker data.win."""
    with path.open("rb") as f:
        magic, form_size = struct.unpack("<4sI", f.read(8))
        if magic != b"FORM":
            raise ValueError(f"{path} is not a GameMaker data file")

        chunks = {}
        while f.tell() < 8 + form_size:
            name, size = struct.unpack("<4sI", f.read(8))
            chunks[name.decode()] = f.tell()
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
        for pointer in pointers(chunks["STRG"]):
            f.seek(pointer)
            (length,) = struct.unpack("<I", f.read(4))
            strings.append(f.read(length).decode("utf-8", errors="replace"))

        objects = []
        for pointer in pointers(chunks["OBJT"]):
            f.seek(pointer)
            (name_pointer,) = struct.unpack("<I", f.read(4))
            objects.append(string_at(name_pointer))

    return objects, strings


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
        ):
            names.append((index, text))
    return names


def weapon_name_pairs(strings: list[str]) -> list[tuple[int, str, str]]:
    """Weapons are listed as FULL NAME followed by a short code (e.g. KAIDA MODEL H / HON)."""
    pairs = []
    for index in range(ENGLISH_STRING_LIMIT - 1):
        name, code = strings[index].strip(), strings[index + 1].strip()
        if (
            re.fullmatch(r"[A-Z0-9][A-Z0-9 .\-]{0,5}", code)
            and name == name.upper()
            and 3 <= len(name) <= 30
            and name != code
        ):
            pairs.append((index, name, code))
    return pairs


def guess_weapon_name(prefix: str, pairs) -> dict:
    """Match the object prefix (HON, PXS, A9...) to a weapon short code or name start."""
    key = normalize(prefix)
    by_code = [(i, n, c) for i, n, c in pairs if normalize(c) == key]
    by_name = [
        (i, n, c)
        for i, n, c in pairs
        if n.upper().startswith(prefix.upper())
        and (len(n) == len(prefix) or not n[len(prefix)].isalpha())
    ]
    matches = by_code or by_name
    names = sorted({n for _, n, _ in matches})
    if len(names) == 1:
        index, name, code = matches[0]
        return {
            "name_guess": name,
            "short_code": code,
            "confidence": "code" if by_code else "name-prefix",
        }
    if names:
        return {"name_guess": None, "confidence": "ambiguous", "candidates": names[:8]}
    return {"name_guess": None, "confidence": "none"}


def description_after(strings: list[str], index: int) -> str | None:
    """First mixed-case line within 3 lines after a name: likely its description."""
    for text in strings[index + 1 : index + 4]:
        if text != text.upper() and len(text) > 20:
            return text.replace("#", " / ")
    return None


def guess_name(object_id: str, short_id: str, names, strings) -> dict:
    """Best-effort display name. Confidence: exact / contains / none."""
    key = normalize(short_id)
    if len(key) < 3:
        return {"name_guess": None, "confidence": "none"}

    exact = [(i, n) for i, n in names if normalize(n) == key]
    if exact:
        index, name = exact[0]
        return {
            "name_guess": name,
            "confidence": "exact",
            "description_guess": description_after(strings, index),
        }

    def close_enough(name: str) -> bool:
        norm = normalize(name)
        if len(key) >= 4 and key in norm:
            return True
        return len(norm) >= 4 and norm in key and len(norm) >= 0.6 * len(key)

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


def build_entries(ids, save, equipped, names, strings, perk_groups=None, weapon_pairs=None) -> list[dict]:
    entries = []
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
        if object_id.startswith("obj_weapon_"):
            entry.update(guess_weapon_name(re.sub(r"_\d+$", "", sid), weapon_pairs or []))
        else:
            entry.update(guess_name(object_id, sid, names, strings))
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

    objects, strings = read_datawin(data_win)
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
        "note": "Generated by research/extract_gamedata.py. name_guess/description_guess are "
        "heuristic matches against the string table and must be verified in-game.",
    }

    write_json("perks.json", {"meta": meta, "perks": build_entries(perks, save, equipped, names, strings, perk_groups)})
    write_json("items.json", {"meta": meta, "items": build_entries(items, save, equipped, names, strings)})
    write_json(
        "weapons.json",
        {
            "meta": meta,
            "weapons": build_entries(weapons, save, equipped, names, strings, weapon_pairs=weapon_name_pairs(strings)),
            "other_weapon_objects": weapon_other,
        },
    )
    write_json(
        "other_pool.json",
        {
            "meta": meta,
            "artefacts": build_entries(artefacts, save, equipped, names, strings),
            "talents_in_pool": build_entries(pool_talents, save, equipped, names, strings),
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

    print(
        f"{len(perks)} perks, {len(items)} items, {len(weapons)} weapons, "
        f"{len(artefacts)} artefacts, {len(pool_talents)} talents in pool"
    )


if __name__ == "__main__":
    main()
