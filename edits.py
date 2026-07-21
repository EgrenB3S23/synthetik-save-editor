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


def set_all_perk_daily_module_boosts(lines: list[str]) -> tuple[list[str], str]:
    """Set all 62 normal perk daily module boosts to the configured value."""
    target_names = set(variables.main_perk_variable_names())
    updated_lines, found = savefile.set_variables(
        lines,
        target_names,
        variables.PERK_DAILY_MODULE_BOOST_VALUE,
    )
    missing = sorted(target_names - found)

    summary = (
        f"Updated {len(found)} of {len(target_names)} normal perk boost(s) "
        f"to {variables.PERK_DAILY_MODULE_BOOST_VALUE}."
    )
    if missing:
        summary += "\nNot found in save file:\n  " + "\n  ".join(missing)

    return updated_lines, summary


def set_data_to_1000(lines: list[str]) -> tuple[list[str], str]:
    """Set the data resource to 1000."""
    updated_lines, found = savefile.set_variable(lines, variables.DATA_VARIABLE, "1000")

    if found:
        summary = f"Set {variables.DATA_VARIABLE} to 1000."
    else:
        summary = (
            f"Variable '{variables.DATA_VARIABLE}' was not found in the save file. "
            "Check variables.py once you know the exact name."
        )

    return updated_lines, summary
