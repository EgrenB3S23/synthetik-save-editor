"""Variable names used in Synthetik 1 save files.

Each normal perk daily module boost uses:
    tpoints_obj_perk_<id>="1.600000"
"""

# In-game "data" resource for alternative modes (Hyper Adrenaline, etc.).
# Save file variable name: currency
DATA_VARIABLE = "currency"

# Shared prefix for the 62 normal class perks.
PERK_VARIABLE_PREFIX = "tpoints_obj_perk_"

# Perk IDs only — the part after the prefix above.
PERKS = {
    "main": [
        # Guardian (16)
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
        # Rogue (15)
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
        # Commando (15)
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
        # Specialist (16)
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
    ],
}

# Default perk boost value when the user presses Enter at the prompt.
PERK_DAILY_MODULE_BOOST_VALUE = "1.6"


def main_perk_variable_names() -> list[str]:
    """Build the full save variable names for all 62 normal perks."""
    return [f"{PERK_VARIABLE_PREFIX}{perk_id}" for perk_id in PERKS["main"]]
