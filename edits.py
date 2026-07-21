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
            display_value = savefile.format_perk_boost_summary_value(raw_value)
            count = value_counts[raw_value]
            noun = "perk" if count == 1 else "perks"
            rows.append((display_value, count, noun))

        value_width = max(len(display_value) for display_value, _, _ in rows)
        for display_value, count, noun in rows:
            print(f"{display_value.ljust(value_width)} : {count} {noun}")

    if missing_count:
        noun = "perk" if missing_count == 1 else "perks"
        print(f"\nNot found in save file: {missing_count} {noun}")
    print()


def set_data_to_1000(lines: list[str]) -> tuple[list[str], str]:
    """Set the data resource to 1000."""
    updated_lines, found = savefile.set_variable(lines, variables.DATA_VARIABLE, "1000")
    formatted_value = savefile.format_display_value("1000")

    if found:
        summary = f"Set data to {formatted_value}."
    else:
        summary = f"Variable '{variables.DATA_VARIABLE}' was not found in the save file."

    return updated_lines, summary
