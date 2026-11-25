"""Save and load loadout presets for one subclass (loadout slots + tokens)."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import edits
import savefile

LOADOUTS_DIR_NAME = "loadouts"
PRESET_FORMAT_VERSION = 1
SLOT_COUNT = 10
TOKENS_PER_FAMILY = 4

# (class index, subclass index, name). Class/subclass digits as used in the save.
SUBCLASSES = [
    (1, 0, "Riot Guard"),
    (1, 1, "Breacher"),
    (2, 0, "Sniper"),
    (2, 1, "Assassin"),
    (3, 0, "Raider"),
    (3, 1, "Heavy Gunner"),
    (4, 0, "Engineer"),
    (4, 1, "Demolitions"),
]

# Token family -> (save section, description).
TOKEN_FAMILIES = {
    "wplus": ("[Save3]", "Weapon - more common"),
    "wminus": ("[Save3]", "Weapon - less common"),
    "wbonus": ("[Save3]", "Weapon - more ammo"),
    "iplus": ("[Save2]", "Item - more common"),
    "iminus": ("[Save2]", "Item - less common"),
    "ibonus": ("[Save2]", "Item - more power"),
}


def loadouts_dir() -> Path:
    """The loadouts folder next to the tool (script folder or .exe folder). Created if missing."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent

    folder = base / LOADOUTS_DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def subclass_name(class_index: int, subclass_index: int) -> str:
    for c, s, name in SUBCLASSES:
        if (c, s) == (class_index, subclass_index):
            return name
    return f"Class {class_index}.{subclass_index}"


def slot_variable(class_index: int, subclass_index: int, slot: int) -> str:
    return f"perkslot{slot}class{class_index}{subclass_index}"


def token_variable(family: str, class_index: int, subclass_index: int, number: int) -> str:
    return f"{family}_{class_index}_{subclass_index}__{number}"


def read_loadout(lines: list[str], class_index: int, subclass_index: int) -> dict:
    """Read one subclass's slots and tokens. Unplaced tokens are None."""
    values: dict[str, str] = {}
    for line in lines:
        parts = savefile.split_line(line)
        if parts:
            values[parts[1]] = parts[2]

    slots = [
        values.get(slot_variable(class_index, subclass_index, slot))
        for slot in range(SLOT_COUNT)
    ]
    tokens = {
        family: [
            values.get(token_variable(family, class_index, subclass_index, number))
            for number in range(TOKENS_PER_FAMILY)
        ]
        for family in TOKEN_FAMILIES
    }
    return {"slots": slots, "tokens": tokens}


def build_preset(lines: list[str], class_index: int, subclass_index: int, name: str) -> dict:
    loadout = read_loadout(lines, class_index, subclass_index)
    return {
        "format_version": PRESET_FORMAT_VERSION,
        "name": name,
        "subclass": subclass_name(class_index, subclass_index),
        "class_index": class_index,
        "subclass_index": subclass_index,
        "game_version": savefile.get_variable_value(lines, "version"),
        "created": datetime.now().isoformat(timespec="seconds"),
        "slots": loadout["slots"],
        "tokens": loadout["tokens"],
    }


def validate_preset(preset: dict) -> str | None:
    """Return an error message, or None if the preset looks usable."""
    if not isinstance(preset, dict):
        return "not a preset file"

    key = (preset.get("class_index"), preset.get("subclass_index"))
    if key not in {(c, s) for c, s, _ in SUBCLASSES}:
        return "unknown class/subclass"

    slots = preset.get("slots")
    if not isinstance(slots, list) or len(slots) != SLOT_COUNT:
        return f"expected {SLOT_COUNT} loadout slots"
    if not all(isinstance(slot, str) and slot for slot in slots):
        return "loadout slots must all be filled in"

    tokens = preset.get("tokens")
    if not isinstance(tokens, dict):
        return "missing tokens"
    for family in TOKEN_FAMILIES:
        values = tokens.get(family)
        if not isinstance(values, list) or len(values) != TOKENS_PER_FAMILY:
            return f"expected {TOKENS_PER_FAMILY} '{family}' tokens"
        for value in values:
            if value is None:
                continue
            try:
                float(value)
            except (TypeError, ValueError):
                return f"invalid '{family}' token value: {value!r}"

    return None


def preset_filename(preset: dict) -> str:
    """Build a file name like heavy-gunner_hyper-adrenaline-220.json."""

    def slug(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

    name_slug = slug(preset["name"]) or "preset"
    return f"{slug(preset['subclass'])}_{name_slug}.json"


def write_preset(preset: dict, path: Path) -> None:
    path.write_text(json.dumps(preset, indent=2) + "\n", encoding="utf-8")


def load_presets() -> list[tuple[Path, dict | None, str | None]]:
    """Load every preset file. Each entry is (path, preset or None, error or None)."""
    results = []
    for path in sorted(loadouts_dir().glob("*.json")):
        try:
            preset = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            results.append((path, None, f"could not read file ({error})"))
            continue

        problem = validate_preset(preset)
        results.append((path, None if problem else preset, problem))

    return results


def _line_ending(lines: list[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\n"


def _insert_index(lines: list[str], section: str, class_index: int, subclass_index: int) -> int | None:
    """Where to add a new token line: after this subclass's last token line in the section,
    or at the end of the section. None if the section does not exist."""
    token_pattern = re.compile(rf"^[wi](plus|minus|bonus)_{class_index}_{subclass_index}__\d+$")
    in_section = False
    section_end = None
    last_token = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section:
                section_end = index
                break
            in_section = stripped == section
            continue

        if in_section:
            parts = savefile.split_line(line)
            if parts and token_pattern.match(parts[1]):
                last_token = index

    if not in_section and section_end is None:
        return None
    if last_token is not None:
        return last_token + 1
    return section_end if section_end is not None else len(lines)


def apply_preset(lines: list[str], preset: dict) -> tuple[list[str], str]:
    """Write a preset's slots and tokens into the save. Only this subclass is changed."""
    class_index = preset["class_index"]
    subclass_index = preset["subclass_index"]

    slot_targets = {
        slot_variable(class_index, subclass_index, slot): value
        for slot, value in enumerate(preset["slots"])
    }
    token_targets: dict[str, str | None] = {}
    for family in TOKEN_FAMILIES:
        for number, value in enumerate(preset["tokens"][family]):
            token_targets[token_variable(family, class_index, subclass_index, number)] = (
                None if value is None else str(value)
            )

    found: set[str] = set()
    removed = 0
    new_lines: list[str] = []

    for line in lines:
        parts = savefile.split_line(line)
        name = parts[1] if parts else None

        if name in slot_targets:
            new_lines.append(savefile.build_line(*parts[:2], slot_targets[name], parts[3]))
            found.add(name)
        elif name in token_targets:
            found.add(name)
            value = token_targets[name]
            if value is None:
                removed += 1
                continue
            new_lines.append(savefile.build_line(*parts[:2], value, parts[3]))
        else:
            new_lines.append(line)

    line_ending = _line_ending(lines)
    added = 0
    not_added: list[str] = []
    for family, (section, _) in TOKEN_FAMILIES.items():
        for number in range(TOKENS_PER_FAMILY):
            name = token_variable(family, class_index, subclass_index, number)
            value = token_targets[name]
            if value is None or name in found:
                continue

            index = _insert_index(new_lines, section, class_index, subclass_index)
            if index is None:
                not_added.append(name)
                continue
            new_lines.insert(index, savefile.build_line("", name, value, line_ending))
            added += 1

    missing_slots = sorted(set(slot_targets) - found)

    summary = (
        f"Loaded preset '{preset['name']}' into {preset['subclass']}.\n"
        f"Updated {len(slot_targets) - len(missing_slots)} of {SLOT_COUNT} loadout slots. "
        f"Tokens: {added} added, {removed} removed, the rest updated in place."
    )
    if missing_slots:
        summary += "\nLoadout slots not found in save file:\n  " + "\n  ".join(missing_slots)
    if not_added:
        summary += "\nCould not add tokens (section missing):\n  " + "\n  ".join(not_added)

    return new_lines, summary


def display_slot(value: str | None) -> str:
    """obj_item81_tanto -> tanto, obj_weapon_HON_34 -> HON_34."""
    if value is None:
        return "(not found)"
    for prefix in (r"obj_perk_", r"obj_item\d+_", r"obj_weapon_"):
        match = re.match(prefix, value)
        if match:
            return value[match.end():]
    return value


def token_object_id(family: str, value: str | None) -> str | None:
    """Object id a token index refers to, if the index matches an item or weapon."""
    if value is None:
        return None
    try:
        number = int(float(value))
    except ValueError:
        return None
    import catalog

    if family.startswith("i"):
        return catalog.item_id_for_number(number)
    if family.startswith("w"):
        return catalog.weapon_id_for_number(number)
    return None


def display_token_value(family: str, value: str | None) -> str:
    """Token index plus a name when the index matches obj_itemN or obj_weapon_*_N."""
    if value is None:
        return "(none)"
    shown = savefile.format_display_value(value)
    object_id = token_object_id(family, value)
    if not object_id:
        return shown
    import catalog

    name = catalog.display_name(object_id)
    return f"{shown} {name}"


def display_tokens(values: list[str | None], family: str | None = None) -> str:
    placed = []
    for value in values:
        if value is None:
            continue
        placed.append(display_token_value(family or "", value) if family else savefile.format_display_value(value))
    return ", ".join(placed) if placed else "(none)"


def print_comparison(current: dict, preset: dict) -> int:
    """Print current vs preset values. Returns how many rows would change."""
    rows: list[tuple[str, str, str]] = []
    for slot in range(SLOT_COUNT):
        rows.append(
            (f"Slot {slot}", display_slot(current["slots"][slot]), display_slot(preset["slots"][slot]))
        )
    for family, (_, description) in TOKEN_FAMILIES.items():
        rows.append(
            (
                description,
                display_tokens(current["tokens"][family], family),
                display_tokens(preset["tokens"][family], family),
            )
        )

    label_width = max(len(label) for label, _, _ in rows)
    current_width = max(len("Current"), *(len(old) for _, old, _ in rows))
    changes = 0

    print(f"{'':{label_width}}   {'Current':{current_width}}   Preset")
    for label, old, new in rows:
        marker = "*" if old != new else " "
        if old != new:
            changes += 1
        print(f"{label:{label_width}} {marker} {old:{current_width}}   {new}")

    print()
    print("Token numbers are the weapon/item each token is placed on. * = will change.")
    print("Item tokens also show the matching obj_itemN name when known.")
    return changes


def print_loadout(loadout: dict, class_index: int | None = None, subclass_index: int = 0) -> None:
    """Print one loadout with the raw save values, so they can be matched to in-game choices."""
    import catalog

    if class_index is not None:
        level = catalog.loadout_cheat_level(
            loadout["slots"], class_index, subclass_index=subclass_index
        )
        print(f"Legal in {level}  {catalog.cheat_square_text(level)}")
        print()
    slot_width = max(len(f"Slot {slot}") for slot in range(SLOT_COUNT))
    for slot, value in enumerate(loadout["slots"]):
        mark = ""
        if class_index is not None:
            slot_level = catalog.minimum_cheat_level(
                value, slot, class_index, subclass_index=subclass_index
            )
            mark = f"  {catalog.cheat_square_text(slot_level)}"
        print(f"{f'Slot {slot}':{slot_width}} : {value if value is not None else '(not found)'}{mark}")

    print()
    family_width = max(len(description) for _, description in TOKEN_FAMILIES.values())
    for family, (_, description) in TOKEN_FAMILIES.items():
        print(f"{description:{family_width}} : {display_tokens(loadout['tokens'][family], family)}")
    print()
    print("Token numbers are the weapon/item each token is placed on.")
    print("Names come from obj_itemN / obj_weapon_*_N when that number is unique enough.")


def select_subclass(lines: list[str], allow_all: bool = False) -> tuple[int, int] | str | None:
    """Let the user pick one of the 8 subclasses. With allow_all, "all" is also an option."""
    options: dict[str, tuple[int, int] | str] = {
        str(index): (c, s) for index, (c, s, _) in enumerate(SUBCLASSES, start=1)
    }
    name_width = max(len(name) for _, _, name in SUBCLASSES)

    print()
    print("Select a subclass:")
    print()
    for key, (c, s) in list(options.items()):
        loadout = read_loadout(lines, c, s)
        weapon = display_slot(loadout["slots"][SLOT_COUNT - 1])
        print(f"{key}. {subclass_name(c, s).ljust(name_width)} (weapon: {weapon})")
    if allow_all:
        options["9"] = "all"
        print("9. All subclasses")
    print("0. Cancel")
    print()

    choice = input("Choose a subclass: ").strip()
    return options.get(choice)


def ask_yes_no(prompt: str) -> bool:
    return input(f"{prompt} (Y/N): ").strip().upper() == "Y"


def save_preset_flow(save_path: Path) -> None:
    lines = savefile.read_lines(save_path)
    selection = select_subclass(lines)
    if selection is None:
        return

    class_index, subclass_index = selection
    name = input("Name this preset (e.g. Hyper Adrenaline 220%): ").strip()
    if not name:
        print("No name entered. Nothing was saved.")
        return

    preset = build_preset(lines, class_index, subclass_index, name)
    problem = validate_preset(preset)
    if problem:
        print(f"Could not read a complete loadout from the save file: {problem}")
        return

    path = loadouts_dir() / preset_filename(preset)
    if path.exists() and not ask_yes_no(f"{path.name} already exists. Overwrite?"):
        print("Nothing was saved.")
        return

    write_preset(preset, path)
    print(f"Saved preset: {path}")


def choose_preset() -> tuple[Path, dict] | None:
    presets = load_presets()
    usable = [(path, preset) for path, preset, _ in presets if preset is not None]
    broken = [(path, problem) for path, preset, problem in presets if preset is None]

    print()
    print(f"Presets folder: {loadouts_dir()}")
    if broken:
        print()
        print("Skipped (invalid files):")
        for path, problem in broken:
            print(f"  {path.name}: {problem}")

    if not usable:
        print()
        print("No presets found. Save one first.")
        return None

    subclass_width = max(len(preset["subclass"]) for _, preset in usable)
    options = {str(index): entry for index, entry in enumerate(usable, start=1)}

    print()
    for key, (_, preset) in options.items():
        print(f"{key}. {preset['subclass'].ljust(subclass_width)} : {preset['name']}")
    print("0. Cancel")
    print()

    choice = input("Choose a preset: ").strip()
    return options.get(choice)


def load_preset_flow(save_path: Path) -> None:
    chosen = choose_preset()
    if chosen is None:
        return

    _, preset = chosen
    lines = savefile.read_lines(save_path)
    current = read_loadout(lines, preset["class_index"], preset["subclass_index"])

    print()
    print(f"{preset['subclass']}: '{preset['name']}'")
    save_version = savefile.get_variable_value(lines, "version")
    if preset.get("game_version") and save_version and preset["game_version"] != save_version:
        print(
            f"Note: preset was made with game version {preset['game_version']}, "
            f"your save is version {save_version}."
        )
    print()
    changes = print_comparison(current, preset)

    if changes == 0:
        print("\nThe save already matches this preset. Nothing to do.")
        return

    print()
    print(f"Only {preset['subclass']} will be changed. Make sure Synthetik is closed.")
    if not ask_yes_no("Load this preset?"):
        print("No changes were made.")
        return

    edits.apply_edit(save_path, lambda lines: apply_preset(lines, preset))


def list_presets_flow() -> None:
    presets = load_presets()
    print()
    print(f"Presets folder: {loadouts_dir()}")
    print()
    if not presets:
        print("No presets found.")
        return

    for path, preset, problem in presets:
        if preset is None:
            print(f"{path.name}: invalid ({problem})")
        else:
            weapon = display_slot(preset["slots"][SLOT_COUNT - 1])
            print(f"{preset['subclass']} : {preset['name']}  (weapon: {weapon}, file: {path.name})")


SLOT_EDIT_MATCH_LIMIT = 40


def cheat_level_flow() -> None:
    """Pick the loadout freedom / cheat tier used by slot editing."""
    import catalog
    import save_paths

    current = save_paths.load_cheat_level()
    print()
    print(f"Current cheat level: {current}")
    print(catalog.cheat_blurb(current))
    print()
    for index, (name, blurb) in enumerate(catalog.CHEAT_LEVELS, start=1):
        mark = "*" if name == current else " "
        print(f"{index}. {mark} {name}")
        print(f"      {blurb}")
    print("0. Cancel")
    print()
    choice = input("Choose a cheat level: ").strip()
    if choice == "0" or not choice.isdigit() or int(choice) not in range(1, len(catalog.CHEAT_LEVELS) + 1):
        print("Cheat level unchanged.")
        return
    name = catalog.CHEAT_LEVELS[int(choice) - 1][0]
    save_paths.save_cheat_level(name)
    print(f"Cheat level is now {name}. This is not stored in presets.")


def edit_slot_flow(save_path: Path) -> None:
    """Change one loadout slot from a filtered list at the current cheat level."""
    import catalog

    lines = savefile.read_lines(save_path)
    selection = select_subclass(lines)
    if selection is None:
        return
    class_index, subclass_index = selection
    loadout = read_loadout(lines, class_index, subclass_index)
    print()
    print_loadout(loadout, class_index, subclass_index)

    slot_text = input("Slot number to edit (0-9): ").strip()
    try:
        slot = int(slot_text)
    except ValueError:
        print("Not a number. Nothing was changed.")
        return
    if slot not in range(SLOT_COUNT):
        print("Slot must be 0-9. Nothing was changed.")
        return

    current = loadout["slots"][slot]
    current_level = catalog.minimum_cheat_level(
        current, slot, class_index, subclass_index=subclass_index
    )
    print()
    print(f"Current slot {slot}: {catalog.labeled(current, multiline=False)}")
    print(f"  {catalog.cheat_square_text(current_level)}  Legal in {current_level}")
    print()
    print(f"Cheat level for this pick (Enter = {current_level}, this slot's current level):")
    for index, (name, blurb) in enumerate(catalog.CHEAT_LEVELS):
        print(f"  {index}. {name} — {blurb}")
    choice = input("Cheat level: ").strip()
    if not choice:
        level = current_level
    elif choice.isdigit() and int(choice) in range(len(catalog.CHEAT_LEVELS)):
        level = catalog.CHEAT_LEVELS[int(choice)][0]
    else:
        print(f"Unknown filter. Using {current_level}.")
        level = current_level
    print(f"Using {level}.")
    query = input("Filter (empty lists the first matches): ").strip()
    options = catalog.options_for_slot(
        slot,
        class_index,
        level,
        subclass_index=subclass_index,
    )
    shown: list[str] = []
    for object_id in options:
        if query and not catalog.filter_match(query, catalog.entry_search_text(object_id)):
            continue
        shown.append(object_id)
    shown.sort(
        key=lambda object_id: (
            object_id != current,
            -catalog.cheat_rank(
                catalog.minimum_cheat_level(object_id, slot, class_index, subclass_index=subclass_index)
            ),
            catalog.display_name(object_id).lower(),
        )
    )
    truncated = len(shown) > SLOT_EDIT_MATCH_LIMIT
    shown = shown[:SLOT_EDIT_MATCH_LIMIT]

    if not shown:
        print("No matches. Nothing was changed.")
        return

    print()
    for index, object_id in enumerate(shown, start=1):
        mark = "*" if object_id == current else " "
        needed = catalog.minimum_cheat_level(
            object_id, slot, class_index, subclass_index=subclass_index
        )
        print(
            f"{index:2}. {mark} {catalog.cheat_square_text(needed)}  {catalog.labeled(object_id, multiline=False)}"
        )
    if truncated:
        print(f"Showing first {SLOT_EDIT_MATCH_LIMIT} matches, keep typing to narrow down.")
    print(" 0. Cancel")
    print()
    choice = input("Choose a value: ").strip()
    if choice == "0" or not choice.isdigit() or int(choice) not in range(1, len(shown) + 1):
        print("Nothing was changed.")
        return

    new_value = shown[int(choice) - 1]
    if new_value == current:
        print("Already that value. Nothing to do.")
        return

    name = subclass_name(class_index, subclass_index)
    print()
    print(f"{name} slot {slot}: {catalog.labeled(current, multiline=False)}")
    print(f"                 -> {catalog.labeled(new_value, multiline=False)}")
    print("Make sure Synthetik is closed.")
    if not ask_yes_no("Write this change"):
        print("No changes were made.")
        return

    preset = build_preset(lines, class_index, subclass_index, "slot-edit")
    preset["slots"] = list(loadout["slots"])
    preset["slots"][slot] = new_value
    problem = validate_preset(preset)
    if problem:
        print(f"Could not write: {problem}")
        return
    edits.apply_edit(save_path, lambda lines: apply_preset(lines, preset))


def view_save_loadout_flow(save_path: Path) -> None:
    lines = savefile.read_lines(save_path)
    selection = select_subclass(lines, allow_all=True)
    if selection is None:
        return

    targets = [(c, s) for c, s, _ in SUBCLASSES] if selection == "all" else [selection]
    for class_index, subclass_index in targets:
        print()
        print(f"--- {subclass_name(class_index, subclass_index)} (in save file) ---")
        print_loadout(read_loadout(lines, class_index, subclass_index), class_index, subclass_index)


def view_preset_flow() -> None:
    chosen = choose_preset()
    if chosen is None:
        return

    path, preset = chosen
    print()
    print(f"--- {preset['subclass']}: '{preset['name']}' ---")
    print(f"File: {path.name}")
    if preset.get("game_version"):
        print(f"Game version: {preset['game_version']}")
    if preset.get("created"):
        print(f"Created: {preset['created']}")
    print()
    print_loadout(preset, preset.get("class_index"), preset.get("subclass_index") or 0)


def delete_preset_flow() -> None:
    chosen = choose_preset()
    if chosen is None:
        return

    path, preset = chosen
    print()
    print(f"Delete '{preset['name']}' ({path.name})?")
    if not ask_yes_no("Delete this preset file"):
        print("Nothing was deleted.")
        return
    path.unlink()
    print(f"Deleted {path.name}")


def rename_preset(path: Path, preset: dict, new_name: str) -> Path:
    """Change a preset's display name and move the file if the slug changes."""
    preset = dict(preset)
    preset["name"] = new_name
    problem = validate_preset(preset)
    if problem:
        raise ValueError(problem)

    new_path = path.with_name(preset_filename(preset))
    if new_path != path and new_path.exists():
        raise FileExistsError(new_path.name)
    write_preset(preset, new_path)
    if new_path != path:
        path.unlink()
    return new_path


def rename_preset_flow() -> None:
    chosen = choose_preset()
    if chosen is None:
        return

    path, preset = chosen
    new_name = input(f"New name for '{preset['name']}': ").strip()
    if not new_name:
        print("No name entered. Nothing was renamed.")
        return
    try:
        new_path = rename_preset(path, preset, new_name)
    except FileExistsError as error:
        print(f"A preset file already uses that name: {error}")
        return
    except ValueError as error:
        print(f"Could not rename: {error}")
        return
    print(f"Renamed to {new_path.name}")


def run_loadout_menu(save_path: Path) -> None:
    options = {
        "1": "1. Save a subclass loadout to a preset",
        "2": "2. Load a preset into the save",
        "3": "3. List saved presets",
        "4": "4. View a loadout in the save file",
        "5": "5. View a preset file",
        "6": "6. Rename a preset",
        "7": "7. Delete a preset",
        "8": "8. Edit a single loadout slot",
        "0": "0. Back to main menu",
    }

    while True:
        print()
        print("=== Loadouts ===")
        print()
        for key in ("1", "2", "3", "4", "5", "6", "7", "8", "0"):
            print(options[key])
        print()

        choice = input("Choose an option: ").strip()
        if choice not in options:
            print("Invalid choice. Please enter a number.")
            continue

        print()
        print(options[choice])

        if choice == "1":
            save_preset_flow(save_path)
        elif choice == "2":
            load_preset_flow(save_path)
        elif choice == "3":
            list_presets_flow()
        elif choice == "4":
            view_save_loadout_flow(save_path)
        elif choice == "5":
            view_preset_flow()
        elif choice == "6":
            rename_preset_flow()
        elif choice == "7":
            delete_preset_flow()
        elif choice == "8":
            edit_slot_flow(save_path)
        elif choice == "0":
            return
