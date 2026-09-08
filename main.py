"""Synthetik save file editor — simple CLI."""

from __future__ import annotations

from pathlib import Path

import edits
import savefile
import variables
import sys


DEFAULT_SAVE_NAME = "Save.sav"


def resolve_user_path(user_input: str) -> Path | None:
    """Resolve user input to a save file path.

    Accepts a path to Save.sav, or to the folder containing it.
    Returns None if the input does not point to a usable file or folder.
    """
    path = Path(user_input)

    if path.is_dir():
        return path / DEFAULT_SAVE_NAME

    if path.is_file():
        if path.name != DEFAULT_SAVE_NAME:
            # print(f"Note: This file is not named {DEFAULT_SAVE_NAME}. Proceeding anyway.")
            print(f"WARNING: This tool expects a file named \"{DEFAULT_SAVE_NAME}\". This path points to a file named \"{path.name}\". Proceed anyways?.")
            choice = input("Enter Y or N: ").strip()
            if choice == "Y":
                return path
            else:
                return None

        return path

    return None


def ask_save_path() -> Path:
    """Ask the user for a save file path, or use the default in the current folder."""
    user_input = input(
        "Enter the path to your save file or its folder\n"
        "(leave empty to use Save.sav in the current folder)\n"
    ).strip()

    if not user_input:
        return Path.cwd() / DEFAULT_SAVE_NAME

    save_path = resolve_user_path(user_input)

    if save_path is None:
        print("Invalid path. Enter a path to Save.sav or to the folder containing it.")
        return ask_save_path()

    if save_path.parent.is_dir() and not save_path.is_file():
        print(f"No {DEFAULT_SAVE_NAME} found in: {save_path.parent}")
        return ask_save_path()

    return save_path


def validate_save_path(save_path: Path) -> bool:
    """Make sure the file exists before we try to edit it."""
    if save_path.is_file():
        return True

    print(f"Save file not found: {save_path}")
    return False


def ask_perk_boost_value() -> str | None:
    """Ask for a perk boost value, or return the default when input is empty."""
    default = variables.PERK_DAILY_MODULE_BOOST_VALUE
    formatted_default = savefile.format_display_value(default)
    user_input = input(
        f"Enter perk boost value (leave empty for default {formatted_default}): "
    ).strip()

    if not user_input:
        return default

    try:
        float(user_input)
    except ValueError:
        print("Invalid number. No changes were made.")
        return None

    return user_input


def get_data_current_value(save_path: Path) -> str | None:
    """Read the current data value from the save file."""
    lines = savefile.read_lines(save_path)
    return savefile.get_variable_value(lines, variables.DATA_VARIABLE)


def build_menu_options(save_path: Path) -> dict[str, str]:
    """Build the text for each menu option."""
    default_perk_value = savefile.format_display_value(variables.PERK_DAILY_MODULE_BOOST_VALUE)
    data_value = get_data_current_value(save_path)

    if data_value is not None:
        current_data = savefile.format_display_value(data_value)
        data_option = f"Data: Set to 1000 (current: {current_data})"
    else:
        data_option = "Data: Set to 1000 (current: unknown)"

    return {
        "1": "1. Perks: Set all class perks' daily boost to chosen value",
        "2": "2. Perks: Set single class perk's daily boost to chosen value",
        "3": "3. Perks: Show current class perks' daily boosts",
        "4": f"4. {data_option}",
        "5": "5. Choose a different save file",
        "0": "0. Exit",
    }


def print_menu(save_path: Path) -> dict[str, str]:
    """Print the menu and return the option labels keyed by choice."""
    options = build_menu_options(save_path)

    print()
    print("=== Synthetik Save Editor ===")
    print(f"Save file: {save_path.resolve()}")
    print()
    for key in ("1", "2", "3", "4", "5", "0"):
        print(options[key])
    print()

    return options


def announce_choice(options: dict[str, str], choice: str) -> None:
    """Print the chosen menu option before running it."""
    print()
    print(options[choice])


def run_menu(save_path: Path) -> Path | None:
    """Show the menu and run the chosen action."""
    while True:
        options = print_menu(save_path)
        choice = input("Choose an option: ").strip()

        if choice not in options:
            print("Invalid choice. Please enter a number.")
            continue

        announce_choice(options, choice)

        if choice == "1":
            perk_value = ask_perk_boost_value()
            if perk_value is not None:
                edits.apply_edit(
                    save_path,
                    lambda lines: edits.set_all_perk_daily_module_boosts(lines, perk_value),
                )
        elif choice == "2":
            lines = savefile.read_lines(save_path)
            perk_id = edits.select_single_perk_id(savefile.get_main_perk_values(lines))
            if perk_id is not None:
                perk_value = ask_perk_boost_value()
                if perk_value is not None:
                    edits.apply_edit(
                        save_path,
                        lambda lines: edits.set_single_perk_daily_module_boost(
                            lines, perk_id, perk_value
                        ),
                    )
        elif choice == "3":
            edits.show_perk_daily_module_boosts(save_path)
        elif choice == "4":
            edits.apply_edit(save_path, edits.set_data_to_1000)
        elif choice == "5":
            new_path = ask_save_path()
            if validate_save_path(new_path):
                return new_path
        elif choice == "0":
            return None


def main() -> None:
    print()
    print("Welcome to Egren's Synthetik Save Editor!")
    print()

    if len(sys.argv) > 1:
        save_path = resolve_user_path(sys.argv[1])

        if save_path is None:
            print(f"Invalid save path: {sys.argv[1]}")
            sys.exit(1)
    else:
        save_path = ask_save_path()

    if not validate_save_path(save_path):
        return

    while True:
        result = run_menu(save_path)
        if result is None:
            print("Goodbye!")
            break
        save_path = result

if __name__ == "__main__":
    main()
