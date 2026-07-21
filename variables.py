"""Variable names used in Synthetik 1 save files.

Each normal perk daily module boost uses:
    tpoints_obj_perk_<id>="1.600000"
"""

# In-game "data" resource for alternative modes (Hyper Adrenaline, etc.).
# Save file variable name: currency
DATA_VARIABLE = "currency"

# Shared prefix for the 62 normal class perks.
PERK_VARIABLE_PREFIX = "tpoints_obj_perk_"

# Normal class perks grouped by class. Order within each list is intentional.
PERK_CLASSES: list[tuple[str, list[str]]] = [
    ("Guardian", [
        "iframe",
        "warmup",
        "recovery",
        "closer",
        "aegis",
        "killshield",
        "fortify",
        "enrage",
        "shotgunmaster",
        "shieldoc",
        "lowhpregen",
        "scraparmor",
        "scavengerbits",
        "berserk",
        "return",
        "reloadsurge2",
    ]),
    ("Rogue", [
        "headshotammo",
        "ejectsurge",
        "dodgeboost",
        "backstab",
        "dance",
        "discipline",
        "longrange",
        "perfection",
        "specialized",
        "powertuning",
        "standstill",
        "reactivereload",
        "stealback",
        "diehard",
        "healthy",
    ]),
    ("Commando", [
        "classweapon",
        "reloadstack",
        "powerstep",
        "specializedammo",
        "drone1",
        "fieldration",
        "reloadsurge",
        "edge",
        "wepupgrade",
        "holdbreath",
        "combo",
        "scarred",
        "cover",
        "killer",
        "drill",
    ]),
    ("Specialist", [
        "statusextender",
        "heatup",
        "grenadier",
        "hframe",
        "pistolextender",
        "ammoregen",
        "selfrepair",
        "focus",
        "itemcdvariant",
        "heatrecharge",
        "elementalpower",
        "heatcontrol",
        "transmutate",
        "dodgeheat",
        "sunrise",
        "force",
    ]),
]

# Default perk boost value when the user presses Enter at the prompt.
PERK_DAILY_MODULE_BOOST_VALUE = "1.6"


def main_perk_ids() -> list[str]:
    """Return all 62 normal perk IDs in class order."""
    return [perk_id for _, perk_ids in PERK_CLASSES for perk_id in perk_ids]


def main_perk_variable_names() -> list[str]:
    """Build the full save variable names for all 62 normal perks."""
    return [f"{PERK_VARIABLE_PREFIX}{perk_id}" for perk_id in main_perk_ids()]
