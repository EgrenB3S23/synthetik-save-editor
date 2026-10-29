"""Snapshot a Save.sav and print every variable that changed.

One in-game change per run, then compare. Snapshot lives in .scratch/
(gitignored) so you can keep this script in the repo.

Usage:
    py research/save_diff.py snapshot [path/to/Save.sav]
    py research/save_diff.py [path/to/Save.sav]
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / ".scratch" / "save_snapshot.json"
DEFAULT_SAVE = Path(os.environ.get("LOCALAPPDATA", "")) / "Synthetik" / "Save.sav"
LINE = re.compile(r'^(\S+?)="(.*)"$')


def read_save(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LINE.match(line.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


def main() -> None:
    args = [arg for arg in sys.argv[1:] if arg != "snapshot"]
    take_snapshot = "snapshot" in sys.argv[1:]
    save_path = Path(args[0]) if args else DEFAULT_SAVE
    if not save_path.is_file():
        sys.exit(f"Save not found: {save_path}")

    current = read_save(save_path)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)

    if take_snapshot:
        SNAPSHOT.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"Snapshot of {len(current)} variables -> {SNAPSHOT}")
        return

    if not SNAPSHOT.is_file():
        sys.exit("No snapshot yet. Run: py research/save_diff.py snapshot")

    previous = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    names = sorted(set(previous) | set(current))
    changes = 0
    for name in names:
        old, new = previous.get(name), current.get(name)
        if old == new:
            continue
        changes += 1
        if old is None:
            print(f"+ {name}={new!r}")
        elif new is None:
            print(f"- {name} (was {old!r})")
        else:
            print(f"* {name}: {old!r} -> {new!r}")

    if changes == 0:
        print("No variables changed.")
    else:
        print(f"\n{changes} variable(s) changed.")


if __name__ == "__main__":
    main()
