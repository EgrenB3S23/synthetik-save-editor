"""Save file edit operations."""

from __future__ import annotations

from pathlib import Path

import savefile
import variables


def apply_edit(save_path: Path, edit_function) -> None:
    """Back up the save, run an edit, then write the result."""
    backup_path = savefile.backup_savefile(save_path)
    print(f"Backup created: {backup_path}")

    lines = savefile.read_lines(save_path)
    updated_lines, summary = edit_function(lines)
    savefile.write_lines(save_path, updated_lines)

    print(summary)


def set_all_perk_daily_module_boosts(lines: list[str], value: str) -> tuple[list[str], str]:
    """Set all 62 normal perk daily module boosts to the given value."""
    target_names = set(variables.main_perk_variable_names())
    formatted_value = savefile.format_display_value(value)
    updated_lines, found = savefile.set_variables(lines, target_names, value)
    missing = sorted(target_names - found)

    summary = (
        f"Updated {len(found)} of {len(target_names)} normal perk boost(s) "
        f"to {formatted_value}."
    )
    if missing:
        summary += "\nNot found in save file:\n  " + "\n  ".join(missing)

    return updated_lines, summary


def show_perk_daily_module_boosts(save_path: Path) -> None:
    """Display how many normal perks currently have each boost value."""
    lines = savefile.read_lines(save_path)
    value_counts, missing_count = savefile.count_main_perk_boost_values(lines)

    print()
    if not value_counts:
        print("No perk daily module boost values found in the save file.")
    else:
        rows: list[tuple[str, int, str]] = []
        for raw_value in sorted(value_counts, key=float):
            display_value = savefile.format_display_value(raw_value)
            count = value_counts[raw_value]
            noun = "perk" if count == 1 else "perks"
            rows.append((display_value, count, noun))

        value_width = max(len(display_value) for display_value, _, _ in rows)
        for display_value, count, noun in rows:
            print(f"{display_value.ljust(value_width)} : {count} {noun}")

    if missing_count:
        noun = "perk" if missing_count == 1 else "perks"
        print(f"\nNot found in save file: {missing_count} {noun}")

    ask_show_all_perks(lines)
    print()


def ask_show_all_perks(lines: list[str]) -> None:
    """Offer to list every perk with its current boost value."""
    options = {
        "1": "1. Yes. Sort by class",
        "2": "2. Yes. Sort by value, then by class",
        "0": "0. No. Back to main menu",
    }

    print()
    print("Show all perks?")
    print()
    for key in ("1", "2", "0"):
        print(options[key])
    print()

    choice = input("Choose an option: ").strip()

    if choice not in options:
        if choice:
            print("Invalid choice. Please enter a number.")
        return

    if choice == "0":
        return

    print()
    print(options[choice])

    if choice == "1":
        print_all_perks_by_class(lines)
    elif choice == "2":
        print_all_perks_by_value_then_class(lines)


def _format_perk_rows(perk_values: dict[str, str | None], perk_ids: list[str]) -> list[tuple[str, str]]:
    """Build display rows for a list of perk IDs."""
    rows: list[tuple[str, str]] = []
    for perk_id in perk_ids:
        raw_value = perk_values.get(perk_id)
        if raw_value is None:
            display_value = "not found"
        else:
            display_value = savefile.format_display_value(raw_value)
        rows.append((perk_id, display_value))
    return rows


def _perk_name_width() -> int:
    """Width of the longest perk ID, so colons align across the full list."""
    return max(len(perk_id) for perk_id in variables.main_perk_ids())


def _print_perk_rows(rows: list[tuple[str, str]], name_width: int) -> None:
    """Print perk rows with aligned colons."""
    if not rows:
        return

    for perk_id, display_value in rows:
        print(f"{perk_id.ljust(name_width)} : {display_value}")


def print_all_perks_by_class(lines: list[str]) -> None:
    """List perks in variables.py order, grouped by class."""
    perk_values = savefile.get_main_perk_values(lines)
    name_width = _perk_name_width()

    print()
    for index, (class_name, perk_ids) in enumerate(variables.PERK_CLASSES):
        if index > 0:
            print()
        print(class_name)
        _print_perk_rows(_format_perk_rows(perk_values, perk_ids), name_width)


def print_all_perks_by_value_then_class(lines: list[str]) -> None:
    """List perks grouped by boost value, then by class within each value."""
    perk_values = savefile.get_main_perk_values(lines)
    raw_values = sorted({value for value in perk_values.values() if value is not None}, key=float)
    name_width = _perk_name_width()

    print()
    for value_index, raw_value in enumerate(raw_values):
        if value_index > 0:
            print()

        print(savefile.format_display_value(raw_value))

        first_class_in_value = True
        for class_name, perk_ids in variables.PERK_CLASSES:
            class_rows = _format_perk_rows(
                perk_values,
                [perk_id for perk_id in perk_ids if perk_values.get(perk_id) == raw_value],
            )
            if not class_rows:
                continue

            if not first_class_in_value:
                print()
            first_class_in_value = False
            print(class_name)
            _print_perk_rows(class_rows, name_width)


def set_data_to_1000(lines: list[str]) -> tuple[list[str], str]:
    """Set the data resource to 1000."""
    updated_lines, found = savefile.set_variable(lines, variables.DATA_VARIABLE, "1000")
    formatted_value = savefile.format_display_value("1000")

    if found:
        summary = f"Set data to {formatted_value}."
    else:
        summary = f"Variable '{variables.DATA_VARIABLE}' was not found in the save file."

    return updated_lines, summary
