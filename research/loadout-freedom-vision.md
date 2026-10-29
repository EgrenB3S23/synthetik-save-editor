# Loadout freedom — vision

Status: **idea / research**. Nothing here is implemented. This document captures the goal and the
open questions so we can investigate together before writing code.

## The idea

Today, each class can only equip modules from its own class group. The loadout preset system
(already built) saves and restores a subclass's slots and tokens. The next step is to let the
editor put **anything** into **any** loadout slot, as far as the game mechanically supports it.

Example: put a Commando starter item (Raider / Heavy Gunner) into an Engineer slot.

Each "restriction level" below is effectively a new metagame: same game, different rules for
what a loadout may contain.

## Restriction levels

| Level | Name | What changes |
|---|---|---|
| 0 | **Vanilla** | Current game. Only a class group's own items, pistols and perks. |
| 1 | **Omniclass** | Class no longer matters, slot type still does. A Rogue can take an Engineer pistol, but a weapon can't go in an item slot. |
| 2 | **Uber Omniclass** | Level 1, plus swapping the class core module (slot 0). If the save allows it, also swapping the level 5/10/15/20/25, prestige and insanity class bonuses for another class's bonuses. |
| 3 | **Omnislots** | Level 2, plus slots no longer have types. Any slot can hold any item, weapon, perk or class bonus. |
| 4 | **Unlimited** | Level 3, plus any item or weapon in the game, not just starter items and starter weapons. |

Class groups (from the game's own text): **Guardian** (Riot Guard, Breacher), **Rogue** (Sniper,
Assassin), **Commando** (Raider, Heavy Gunner; called `SOLDIER` internally), **Specialist**
(Engineer, Demolitions). The game also has a `GENERIC` group.

## What we know so far

See [`save-format-notes.md`](save-format-notes.md) for the save variables, and
[`gamedata/`](gamedata/) for the extracted lists.

- Every loadout slot is a plain text value in the save, e.g. `perkslot9class30="obj_weapon_HON_34"`.
  Writing a different object id there is trivial for the editor. The question is only what the
  game does with it.
- The save has a per-slot type code (`slot<slot>perkgroup<class>`). It's identical for all four
  classes, so it looks like a slot *type*, not a class restriction:

  | Slot | Type code | Seen in this save |
  |---|---|---|
  | 0 | 4 | Class core perk (`obj_perk_raider`, `obj_perk_engineer`, …) |
  | 1 | 5 | Random perk, or an item (Breacher has Breaching Charge here) |
  | 2 | 5 | Random perk |
  | 3 | 9 | Class signature item (Tanto, Battlecry, Sentry, …) |
  | 4 | 0 | Item (Stim, Smoke grenade, Decoy, Riot Guard shield, …) |
  | 5 | 0 | Item, or random perk |
  | 6 | 1 | Perk |
  | 7 | 1 | Perk, or random perk |
  | 8 | 1 | Often `randomperk`; not on the Engineer class card |
  | 9 | 2 | Starting pistol |

  Confirmed: `obj_perk_randomperk` means **empty item or perk loadout slot** (right-click in-game
  → extra random perk). Never used for tokens (unused token = missing line), pistols, or cores.
  See [`gui-layout-notes.md`](gui-layout-notes.md).
- Cross-class already happens in vanilla data: Engineer has `obj_item130_riotguard` in slot 4.
- The **loadout pool** (everything that has a `tunlock_`/`tpoints_`/`tactive_` entry in the save)
  is 168 entries: 73 perks (incl. 8 class cores), 40 items, 15 starting pistols, 19 artefacts,
  21 talents. That pool is the natural value set for levels 1–3. Level 4 would open up all
  117 perks, 158 items and 110 weapon objects found in the game data.
- The game's text marks some restrictions explicitly, e.g. `#Rogue exclusive`,
  `#Commando Exclusive`, `#Specialist Exclusive` on pistols.

## Open questions (need in-game testing)

Ordered roughly by how much they decide what's possible:

1. **Does the game accept a foreign object in a slot?** Put another class group's starter item in
   a slot by hand, start a run, and check: does it show in the loadout screen, does it spawn,
   does the game reset it, or does it crash? This one test decides whether level 1 is possible.
2. **Is the restriction enforced on load, on run start, or only in the loadout UI?** If only the
   UI enforces it, the editor can bypass it freely. If the game "repairs" the slot on load, we
   need another approach.
3. **What do the slot type codes mean exactly?** Is 5 "class or generic module", 9 "class item",
   0 "item", 1 "perk", 2 "weapon", 4 "core"? What happens with the wrong type in a slot (level 3)?
4. **Class core swap (level 2):** does an Engineer with `obj_perk_raider` in slot 0 play like a
   Raider core on an Engineer? Is the core tied to the class's own weapon proficiency?
5. **Class level bonuses (level 2):** where are the lvl 5/10/15/20/25/prestige/insanity bonus
   choices stored? Candidates: `scl`, `sma`, `sta`, `sad`, `ski` per subclass (5 values per
   subclass) and `pst`/`subclasspst` (prestige). Change one in-game and diff the save.
6. **Non-pool items and weapons (level 4):** does a slot accept an item or weapon that has no
   `tunlock_` entry? Does the token system need a matching entry?
7. **Slot 8 and the slot-5 "random perk":** what unlocks slot 8, and can we fill it?
8. **Do the class core / talent unlock values (`tunlock_` = 0, 1, 2, -66, -7001) gate anything?**

## How we'll investigate

- `.scratch/save_diff.py` (local, not committed) snapshots the save and lists every changed
  variable after an in-game change. One change per test.
- `research/extract_gamedata.py` regenerates `research/gamedata/*.json` from the game files and a
  save. Name guesses are heuristic; confirmed names should be filled in by hand as we verify them.
- Keep test results in this file, under a "Findings" section, so the restriction levels can be
  updated with what's actually possible.

## Findings

(none yet)
