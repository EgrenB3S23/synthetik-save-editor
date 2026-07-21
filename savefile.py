"""Reading, writing, and backing up Synthetik save files."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

import variables

# Matches lines like:  tpoints_obj_perk_force="1.600000"
# The variable name is everything before the = sign.
SAVE_LINE_PATTERN = re.compile(r'^(\s*)(.+?)\s*=\s*"(.*)"\s*$')


def backup_savefile(save_path: Path) -> Path:
    """Copy the save file before editing it.

    Creates a file like: Save.backup.20260721_191530.sav
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = save_path.with_name(
        f"{save_path.stem}.backup.{timestamp}{save_path.suffix}"
    )
    shutil.copy2(save_path, backup_path)
    return backup_path


def read_lines(save_path: Path) -> list[str]:
    """Read the save file and return one string per line (including line endings)."""
    return save_path.read_text(encoding="utf-8").splitlines(keepends=True)


def write_lines(save_path: Path, lines: list[str]) -> None:
    """Write lines back to the save file."""
    save_path.write_text("".join(lines), encoding="utf-8")


def format_save_value(value: str) -> str:
    """Format numbers the way Synthetik stores them, e.g. 1.6 -> 1.600000."""
    try:
        return f"{float(value):.6f}"
    except ValueError:
        return value


def format_display_value(value: str) -> str:
    """Format a value for display, e.g. 6.000000 -> 6 and 1.250000 -> 1.25."""
    try:
        number = float(value)
        if number == int(number):
            return str(int(number))
        return f"{number:.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return value


def split_line(line: str) -> tuple[str, str, str, str] | None:
    """Split one save line into whitespace, variable name, value, and line ending."""
    line_body = line.rstrip("\r\n")
    match = SAVE_LINE_PATTERN.match(line_body)
    if not match:
        return None

    line_ending = line[len(line_body) :]
    whitespace, variable_name, _old_value = match.groups()
    return whitespace, variable_name, _old_value, line_ending


def build_line(whitespace: str, variable_name: str, value: str, line_ending: str) -> str:
    """Rebuild one save line from its parts."""
    formatted_value = format_save_value(value)
    return f'{whitespace}{variable_name}="{formatted_value}"{line_ending}'


def get_variable_value(lines: list[str], variable_name: str) -> str | None:
    """Return the current value of one variable, or None if it is not in the file."""
    for line in lines:
        parts = split_line(line)
        if parts and parts[1] == variable_name:
            return parts[2]

    return None


def set_variable(lines: list[str], variable_name: str, new_value: str) -> tuple[list[str], bool]:
    """Find one exact variable name and replace its value.

    Example match:  currency="6.000000"
    """
    updated = False
    new_lines: list[str] = []

    for line in lines:
        parts = split_line(line)
        if parts and parts[1] == variable_name:
            new_lines.append(build_line(*parts[:2], new_value, parts[3]))
            updated = True
        else:
            new_lines.append(line)

    return new_lines, updated


def set_variables(lines: list[str], variable_names: set[str], new_value: str) -> tuple[list[str], set[str]]:
    """Update several exact variable names in one pass through the file.

    Returns the updated lines and the set of variable names that were found.
    """
    found: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        parts = split_line(line)
        if parts and parts[1] in variable_names:
            new_lines.append(build_line(*parts[:2], new_value, parts[3]))
            found.add(parts[1])
        else:
            new_lines.append(line)

    return new_lines, found


def count_main_perk_boost_values(lines: list[str]) -> tuple[dict[str, int], int]:
    """Count how many normal perks have each boost value.

    Returns value counts and how many of the 62 perk variables were missing.
    """
    target_names = set(variables.main_perk_variable_names())
    counts: dict[str, int] = {}
    found = 0

    for line in lines:
        parts = split_line(line)
        if parts and parts[1] in target_names:
            value = parts[2]
            counts[value] = counts.get(value, 0) + 1
            found += 1

    missing_count = len(target_names) - found
    return counts, missing_count


def get_main_perk_values(lines: list[str]) -> dict[str, str | None]:
    """Map each normal perk ID to its current save value, or None if missing."""
    perk_values = {perk_id: None for perk_id in variables.main_perk_ids()}
    variable_to_perk_id = {
        f"{variables.PERK_VARIABLE_PREFIX}{perk_id}": perk_id for perk_id in perk_values
    }

    for line in lines:
        parts = split_line(line)
        if parts and parts[1] in variable_to_perk_id:
            perk_values[variable_to_perk_id[parts[1]]] = parts[2]

    return perk_values
