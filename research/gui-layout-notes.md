# GUI layout notes (from in-game screenshots)

Captured 2026-10-29. Engineer (Specialist, orange) on the hub screen. Not implemented yet.

## Hub layout

- Center: mission / 3D world (out of scope).
- Bottom bar: Multiplayer, **Classes [Tab]**, Difficulty, Research, **Items**, **Weapons**.
- Right: class loadout card (always visible on this screen).
- Left: token list when Items or Weapons is selected.

## Class card (top to bottom)

Specialist color: orange/red, as on the Engineer card.

| In-game | Editable in vanilla | Likely save slot | Engineer example |
|---|---|---|---|
| Class memory module | No (class core) | 0 | Core: Drone Zeal (`obj_perk_engineer`) |
| Pistol | Yes (click → picker) | 9 | 57 Fusion Classic (likely `obj_weapon_REP_11`) |
| Class core item | No | 3 | LMG Sentry Turret (`obj_item71_sentry`) |
| Starting item 1 | Yes (right-click empties) | 4 | Missile Drone |
| Starting item 2 | Yes (right-click empties) | 5 | Field Supply (`obj_item6_reloader`?) |
| Class perk 1 (Overdrive *slot*) | Yes (right-click empties) | 6 | Unceasing + always **+25%** |
| Class perk 2 | Yes (right-click empties) | 7 | Overdrive (the *perk*) |

Then the **class bonus track** (not the 10 loadout slots): Baseline, Level 5, 10, 15, 20, 25, Prestige, Challenge. Uber Omniclass later.

**Name collision:** "Overdrive" is both (a) the +25% that always sits on class perk 1, and (b) a Specialist perk. In the editor, label the slot "Overdrive slot" / "Class perk 1" and keep the perk id `overdrive` as the item name.

## Empty item/perk slots = `obj_perk_randomperk`

Confirmed: `randomperk` is **not** its own slot type. Right-clicking any of the **2 item slots** or **2 perk slots** empties it. An empty slot stores `obj_perk_randomperk`. You can skip starting items to roll extra random perks instead.

So the chooser for those four slots should include **RANDOM MODULE** as the empty option (`obj_perk_randomperk`). Label it the way the game does.

**Tokens never use `randomperk`.** Tokens are a separate system (marks on the Items/Weapons lists). An unused token is *no save line at all* (`null` in a preset), not `obj_perk_randomperk`.

**All 8 subclasses edit the same five slots:** pistol, 2 starting items, 2 class perks. Confirmed. Cores (memory module + class core item) are class-specific and locked in vanilla.

**GUI write confirmed in-game (2026-10-29):** Riot Guard items + perks set to RANDOM MODULE via the tkinter prototype and Write to save. Game showed four RANDOM MODULE rows.

**Cannot be emptied to random perk:** pistol (slot 9) and class memory module (slot 0). They can be *changed* (pistol yes in vanilla; core not in vanilla), but not cleared. Class core item (slot 3, e.g. LMG Sentry Turret) is locked in vanilla.

In-game empty state on the card: the four editable rows all show **RANDOM MODULE** (dice icon). Perk 1 still shows **+25%**.

**Unconfirmed:** how save slots 1, 2, and 8 relate to this card. They often store `randomperk` even when 4–7 are filled, and this emptied Engineer card still shows only the four RANDOM MODULE rows. They might be hidden extras, unlocks, or something else — do not treat "off this card" as confirmed.

Slots 1, 2, and 8 still exist in the save and are often `randomperk` even when 4–7 are filled. **How they map to the class card is unknown.** Breacher can store an item in slot 1 (Breaching Charge), so those variables are real. Don't assume they are unused.

## Click a slot → picker list

Same for pistol, items, and perks: the chosen slot highlights, a vertical list of allowed options appears, click one to equip. Current choice has a cyan outline.

Vanilla Engineer pistols in the picker: P33 Compact, Last Breath, Kaida Laser Pistol, PPQ-H Laser Pistol, 57 Fusion Classic, Auto-9/45, Titanium Eagle, P25 Overdrive, TEC-9. (9 of 15 pool pistols — class-filtered = GUI tier 1.)

GUI tiers 2–3 grow that same list (other classes, then other slot types). Filter box on top when the list is long.

## Token panel (Items / Weapons tabs)

Same control for items and weapons. Full game list, **sorted by rarity**. Row color = rarity:

- Blue: starting / common
- Purple: epic
- (Legendary likely red; not in the crops)

Marks on the row (up to 4 of each type per subclass):

| Mark | Meaning | Save family |
|---|---|---|
| White up-arrow | + supply (more common) | `wplus` / `iplus` |
| Black down-arrow | − supply (less common) | `wminus` / `iminus` |
| White lightning hex | power (weapon ammo / +20% item power) | `wbonus` / `ibonus` |

Starting items (e.g. Field Supply) appear both in the loadout and in the item token list.

## GUI should resemble

1. Right (or similar): class card with the rows above. Click a row to edit (cores greyed out at vanilla).
2. Click → chooser list (tiered + filter), like the pistol picker.
3. Separate Items / Weapons views for tokens, or a split panel: list + three token types as marks you can place/remove (4 each).
4. Class switcher (Classes tab) — no screenshot yet; 8 subclasses.
