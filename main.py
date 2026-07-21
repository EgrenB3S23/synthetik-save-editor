"""Synthetik 1 save file editor — simple CLI."""

from __future__ import annotations

from pathlib import Path

import edits


DEFAULT_SAVE_NAME = "Save.sav"


def ask_save_path() -> Path:
    """Ask the user for a save file path, or use the default in the current folder."""
    user_input = input(
        f"Enter the full path to your save file (leave empty for ./{DEFAULT_SAVE_NAME}): "
    ).strip()

    if user_input:
        return Path(user_input)

    return Path.cwd() / DEFAULT_SAVE_NAME


def validate_save_path(save_path: Path) -> bool:
    """Make sure the file exists before we try to edit it."""
    if save_path.is_file():
        return True

    print(f"Save file not found: {save_path}")
    return False


def print_menu(save_path: Path) -> None:
    print()
    print("=== Synthetik 1 Save Editor ===")
    print(f"Save file: {save_path.resolve()}")
    print()
    print("1. Set all perk daily module boosts to 1.6")
    print("2. Set data to 1000")
    print("3. Choose a different save file")
    print("0. Exit")
    print()


def run_menu(save_path: Path) -> Path | None:
    """Show the menu and run the chosen action.

    Returns a new save path if the user picks option 3, or None to exit.
    """
    while True:
        print_menu(save_path)
        choice = input("Choose an option: ").strip()

        if choice == "1":
            edits.apply_edit(save_path, edits.set_all_perk_daily_module_boosts)
        elif choice == "2":
            edits.apply_edit(save_path, edits.set_data_to_1000)
        elif choice == "3":
            new_path = ask_save_path()
            if validate_save_path(new_path):
                return new_path
        elif choice == "0":
            return None
        else:
            print("Invalid choice. Please enter 0, 1, 2, or 3.")


def main() -> None:
    print("Welcome to the Synthetik 1 Save Editor")

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
