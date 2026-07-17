"""
Turns a raw coc.py Player object into the derived numbers that actually mean
something: completion per category, rush risk, levels remaining.

The raw API tells you a hero is level 40. That alone is noise. What you care
about is "level 40 out of the 50 this Town Hall allows." Every function here
compares what you have against the max available at YOUR current Town Hall,
which is the honest yardstick. Items your Town Hall hasn't unlocked yet are
not counted against you.

Note the known blind spot: the public API returns your army, heroes, spells,
pets and hero equipment. It does NOT return buildings, defenses, traps or
walls. So these percentages describe your offense and your heroes, not your
base. That is a limit of Supercell's API, not of this code.
"""

from dataclasses import dataclass, field, asdict
from typing import Any


# Which player attributes map to which category. We keep regular home troops
# and siege machines, and deliberately skip super troops (they are temporary
# boosts, not permanent progress).
def _collect(player: Any) -> dict[str, list]:
    heroes = [h for h in getattr(player, "heroes", []) if getattr(h, "is_home_base", True)]
    spells = [s for s in getattr(player, "spells", []) if getattr(s, "is_home_base", True)]
    pets = list(getattr(player, "pets", []) or [])
    equipment = list(getattr(player, "equipment", []) or [])

    home_troops = [t for t in getattr(player, "home_troops", []) if not getattr(t, "is_super_troop", False)]
    sieges = list(getattr(player, "siege_machines", []) or [])
    troops = home_troops + sieges

    return {
        "heroes": heroes,
        "troops": troops,
        "spells": spells,
        "pets": pets,
        "equipment": equipment,
    }


def _max_for_th(item: Any, town_hall: int) -> int:
    """Max level this item can reach at the given Town Hall.

    Falls back to the item's global max if the per-TH lookup is unavailable
    (for example when game data did not load). Returns 0 for anything the
    Town Hall has not unlocked, so it drops out of the calculation.
    """
    try:
        capped = item.get_max_level_for_townhall(town_hall)
    except Exception:
        capped = None
    if capped is None:
        capped = getattr(item, "max_level", None)
    try:
        return int(capped) if capped and capped > 0 else 0
    except (TypeError, ValueError):
        return 0


def _max_for_prev_th(item: Any, town_hall: int) -> int:
    """Max level this item could reach at the PREVIOUS Town Hall.

    This is the yardstick for rush. Returns 0 at TH1 (no previous) or when the
    item did not exist a Town Hall ago.
    """
    if town_hall <= 1:
        return 0
    return _max_for_th(item, town_hall - 1)


@dataclass
class CategoryResult:
    category: str
    items_counted: int
    current_total: int
    max_total: int
    levels_remaining: int
    completion_pct: float
    # names of the items with the most levels still to go, most-behind first
    biggest_gaps: list[dict] = field(default_factory=list)


def _score_category(name: str, items: list, town_hall: int) -> CategoryResult:
    current_total = 0
    max_total = 0
    gaps = []
    counted = 0

    for it in items:
        cap = _max_for_th(it, town_hall)
        if cap <= 0:
            continue
        lvl = int(getattr(it, "level", 0) or 0)
        lvl = min(lvl, cap)  # guard against odd API values above the TH cap
        remaining = max(0, cap - lvl)
        current_total += lvl
        max_total += cap
        counted += 1
        if remaining > 0:
            gaps.append({"name": getattr(it, "name", "?"), "level": lvl, "max": cap, "remaining": remaining})

    gaps.sort(key=lambda g: g["remaining"], reverse=True)
    pct = round(100.0 * current_total / max_total, 1) if max_total else 100.0

    return CategoryResult(
        category=name,
        items_counted=counted,
        current_total=current_total,
        max_total=max_total,
        levels_remaining=max_total - current_total,
        completion_pct=pct,
        biggest_gaps=gaps[:5],
    )


def _rush_risk(groups: dict[str, list], town_hall: int) -> dict:
    """The real definition of rush, not a made-up percentage.

    A base is rushed when you moved up a Town Hall without finishing the last
    one. So this measures how far your offense sits below the PREVIOUS Town
    Hall's max. If you maxed the previous TH before upgrading, this is zero,
    even if your current TH is barely started. That is correct: a fresh, fully
    caught-up TH16 is not rushed.

    Heroes, troops and spells count. Deficit is levels still missing versus the
    previous TH cap. The score is that deficit as a share of what the previous
    TH allowed. Higher means more rushed.
    """
    deficit = 0
    prev_max = 0
    worst = []
    for name in ("heroes", "troops", "spells"):
        for it in groups.get(name, []):
            cap = _max_for_prev_th(it, town_hall)
            if cap <= 0:
                continue
            lvl = min(int(getattr(it, "level", 0) or 0), cap)
            gap = max(0, cap - lvl)
            deficit += gap
            prev_max += cap
            if gap > 0:
                worst.append({"name": getattr(it, "name", "?"), "level": lvl,
                              "prev_th_max": cap, "behind": gap, "category": name})

    score = round(100.0 * deficit / prev_max, 1) if prev_max else 0.0
    if score < 5:
        band = "not rushed"
    elif score < 15:
        band = "slightly rushed"
    elif score < 30:
        band = "rushed"
    else:
        band = "heavily rushed"
    worst.sort(key=lambda w: w["behind"], reverse=True)
    return {"score": score, "band": band, "levels_behind_prev_th": deficit,
            "worst_offenders": worst[:5]}


def analyse(player: Any) -> dict:
    """Full analysis. Returns a nested dict ready to serialise to JSON."""
    town_hall = int(getattr(player, "town_hall", 0) or 0)
    groups = _collect(player)
    cats = {name: _score_category(name, items, town_hall) for name, items in groups.items()}

    offense_cur = sum(cats[c].current_total for c in ("heroes", "troops", "spells"))
    offense_max = sum(cats[c].max_total for c in ("heroes", "troops", "spells"))
    offense_pct = round(100.0 * offense_cur / offense_max, 1) if offense_max else 100.0

    total_remaining = sum(c.levels_remaining for c in cats.values())
    rush = _rush_risk(groups, town_hall)

    clan = getattr(player, "clan", None)

    return {
        "identity": {
            "name": getattr(player, "name", "?"),
            "tag": getattr(player, "tag", "?"),
            "town_hall": town_hall,
            "town_hall_weapon": getattr(player, "town_hall_weapon", None),
            "exp_level": getattr(player, "exp_level", None),
            "clan_name": getattr(clan, "name", None) if clan else None,
            "clan_tag": getattr(clan, "tag", None) if clan else None,
            "role": str(getattr(player, "role", "") or "") or None,
        },
        "ladder": {
            "trophies": getattr(player, "trophies", None),
            "best_trophies": getattr(player, "best_trophies", None),
            "war_stars": getattr(player, "war_stars", None),
            "attack_wins": getattr(player, "attack_wins", None),
            "defense_wins": getattr(player, "defense_wins", None),
            "donations": getattr(player, "donations", None),
            "received": getattr(player, "received", None),
        },
        "completion": {name: round(c.completion_pct, 1) for name, c in cats.items()},
        "offense_completion_pct": offense_pct,
        "total_levels_remaining": total_remaining,
        "rush_risk": rush,
        "categories": {name: asdict(c) for name, c in cats.items()},
    }


# Flat row for the time-series CSV. One row per run. This is the trend backbone.
CSV_COLUMNS = [
    "date", "name", "town_hall", "trophies", "best_trophies", "war_stars",
    "attack_wins", "defense_wins", "donations", "received", "exp_level",
    "heroes_pct", "troops_pct", "spells_pct", "pets_pct", "equipment_pct",
    "offense_pct", "rush_risk", "total_levels_remaining", "clan_name", "clan_tag",
]


def to_csv_row(analysis: dict, date_str: str) -> dict:
    ident = analysis["identity"]
    lad = analysis["ladder"]
    comp = analysis["completion"]
    return {
        "date": date_str,
        "name": ident["name"],
        "town_hall": ident["town_hall"],
        "trophies": lad["trophies"],
        "best_trophies": lad["best_trophies"],
        "war_stars": lad["war_stars"],
        "attack_wins": lad["attack_wins"],
        "defense_wins": lad["defense_wins"],
        "donations": lad["donations"],
        "received": lad["received"],
        "exp_level": ident["exp_level"],
        "heroes_pct": comp.get("heroes"),
        "troops_pct": comp.get("troops"),
        "spells_pct": comp.get("spells"),
        "pets_pct": comp.get("pets"),
        "equipment_pct": comp.get("equipment"),
        "offense_pct": analysis["offense_completion_pct"],
        "rush_risk": analysis["rush_risk"]["score"],
        "total_levels_remaining": analysis["total_levels_remaining"],
        "clan_name": ident["clan_name"],
        "clan_tag": ident["clan_tag"],
    }


def group_items(player):
    """Public accessor for the per-category item groups, used by the
    upgrade-cost engine so it can reuse the exact same category rules."""
    return _collect(player)
