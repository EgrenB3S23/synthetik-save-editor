"""Save file path discovery and remembering the last used path."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_SAVE_NAME = "Save.sav"
CONFIG_DIR_NAME = "synthetik-save-editor"
CONFIG_FILE_NAME = "config.json"


def config_dir() -> Path:
    """Folder for per-user settings (works for script and frozen .exe)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / CONFIG_DIR_NAME
    return Path.home() / f".{CONFIG_DIR_NAME}"


def config_file() -> Path:
    return config_dir() / CONFIG_FILE_NAME


def load_last_save_path() -> Path | None:
    """Return the last successfully used save path, if the file still exists."""
    config_path = config_file()
    if not config_path.is_file():
        return None

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        saved = data.get("last_save_path")
        if not saved:
            return None
        path = Path(saved)
    except (OSError, json.JSONDecodeError, TypeError):
        return None

    return path if path.is_file() else None


def save_last_save_path(save_path: Path) -> None:
    """Remember a save path for the next run."""
    try:
        config_path = config_file()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps({"last_save_path": str(save_path.resolve())}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def local_appdata_dir() -> Path:
    """Best-effort Windows LocalAppData path for the current user."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata)
    return Path.home() / "AppData" / "Local"


def default_save_path_candidates() -> list[Path]:
    """Likely Save.sav locations, most specific first."""
    local_appdata = local_appdata_dir()
    candidates = [
        local_appdata / "Synthetik" / DEFAULT_SAVE_NAME,
        Path.cwd() / DEFAULT_SAVE_NAME,
    ]

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)

    return unique


def best_candidate_save_path() -> Path:
    """Best guess without using a remembered path."""
    for candidate in default_save_path_candidates():
        if candidate.is_file():
            return candidate

    return local_appdata_dir() / "Synthetik" / DEFAULT_SAVE_NAME


def prefilled_save_path() -> str:
    """Path to show pre-filled in the save file prompt."""
    remembered = load_last_save_path()
    if remembered is not None:
        return str(remembered)

    return str(best_candidate_save_path())


def input_prefilled(prompt: str, default: str) -> str | None:
    """Read a line with default text shown in the field.

    Returns the entered text, or None when the user cleared the field (reset).
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _input_prefilled_fallback(prompt, default)

    if sys.platform == "win32":
        try:
            return _input_prefilled_windows(prompt, default)
        except (ImportError, OSError):
            pass

    return _input_prefilled_fallback(prompt, default)


def _input_prefilled_fallback(prompt: str, default: str) -> str | None:
    """Bracket-style prompt when true pre-fill is not available."""
    value = input(f"{prompt}{default}\n> ").strip()
    if not value:
        return default
    return value


def _input_prefilled_windows(prompt: str, default: str) -> str | None:
    import msvcrt

    sys.stdout.write(prompt)
    sys.stdout.write(default)
    sys.stdout.flush()
    buffer = list(default)

    while True:
        char = msvcrt.getwch()
        if char in ("\r", "\n"):
            print()
            if not buffer:
                return None
            return "".join(buffer)
        if char == "\x03":
            raise KeyboardInterrupt
        if char in ("\x08", "\x7f"):
            if buffer:
                buffer.pop()
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue
        if char == "\xe0":
            msvcrt.getwch()
            continue
        if len(char) == 1 and char >= " ":
            buffer.append(char)
            sys.stdout.write(char)
            sys.stdout.flush()


def wait_before_exit() -> None:
    """Keep the window open when double-clicking the script or .exe."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return

    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
