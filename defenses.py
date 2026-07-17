"""
Defenses, walls, traps and resource buildings, from the village JSON you paste in.

The public API can't see buildings, so this half runs on a file you provide:
data/accounts/<TAG>/village.json. It's the only manual step in the whole
tracker, and it's why defenses are "occasional paste" rather than automatic.
Update it when you've upgraded a few buildings and want the guide to know.

Schema (levels are current in-game levels):

    {
      "town_hall": 16,
      "buildings": [
        {"name": "Cannon", "level": 21},
        {"name": "Cannon", "level": 20},
        {"name": "Inferno Tower", "level": 9}
      ],
      "resources": [
        {"name": "Gold Mine", "level": 16},
        {"name": "Gold Storage", "level": 16}
      ],
      "traps": [
        {"name": "Bomb", "level": 12}
      ],
      "walls": [
        {"level": 16, "count": 250},
        {"level": 15, "count": 25}
      ]
    }

List a building once per copy you own. "buildings" is defensive structures
(cannons, towers, etc), "resources" is Gold Mine / Elixir Collector / Dark
Elixir Drill and their storages -- both are looked up in the same bundled
buildings table, just kept in separate lists so the dashboard can score them
separately. Walls are grouped by level with a count. Costs and times come
from the same bundled game tables as everything else, so they're as fresh as
the library.
"""

import json
from pathlib import Path

import upgrades

_BUILDINGS_CACHE = None


def _buildings() -> dict:
    """Home-village buildings, indexed by name. Buildings store cost at the
    destination level (X means the cost to reach X), the opposite of troops."""
    global _BUILDINGS_CACHE
    if _BUILDINGS_CACHE is not None:
        return _BUILDINGS_CACHE
    import coc
    raw = json.loads((Path(coc.__file__).parent / "static" / "static_data.json").read_text())
    out = {}
    for b in raw.get("buildings", []):
        if b.get("village") not in (None, "home"):
            continue
        out.setdefault(b["name"], b)
    _BUILDINGS_CACHE = out
    return out


_TRAPS_CACHE = None


def _traps() -> dict:
    """Home-village traps, indexed by name. Same destination-level cost
    convention as buildings."""
    global _TRAPS_CACHE
    if _TRAPS_CACHE is not None:
        return _TRAPS_CACHE
    import coc
    raw = json.loads((Path(coc.__file__).parent / "static" / "static_data.json").read_text())
    out = {}
    for t in raw.get("traps", []):
        if t.get("village") not in (None, "home"):
            continue
        out.setdefault(t["name"], t)
    _TRAPS_CACHE = out
    return out


def _max_level_for_th(entry: dict, town_hall: int) -> int:
    levels = [lvl["level"] for lvl in entry.get("levels", [])
              if lvl.get("required_townhall", 99) <= town_hall]
    return max(levels) if levels else 0


def _building_remaining(entry: dict, current: int, target: int) -> tuple[dict, int]:
    """Sum build_cost / build_time for levels (current, target], destination
    convention."""
    cost, seconds = {}, 0
    resource = entry.get("upgrade_resource") or "Gold"
    key = upgrades._RESOURCE_KEY.get(resource, resource.lower())
    by_level = {lvl["level"]: lvl for lvl in entry.get("levels", [])}
    for lvl in range(current + 1, target + 1):
        data = by_level.get(lvl)
        if not data:
            continue
        c = data.get("build_cost")
        if c:
            cost[key] = cost.get(key, 0) + int(c)
        seconds += int(data.get("build_time", 0) or 0)
    return cost, seconds


def load_village(acc_dir: Path):
    path = acc_dir / "village.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def remaining_records(village: dict, town_hall_fallback: int, mods: dict) -> list[dict]:
    if not village:
        return []
    town_hall = int(village.get("town_hall") or town_hall_fallback or 0)
    tables = _buildings()
    records = []

    for b in village.get("buildings", []):
        name = b.get("name")
        entry = tables.get(name)
        if not entry:
            continue
        target = _max_level_for_th(entry, town_hall)
        level = int(b.get("level", 0) or 0)
        if not target or level >= target:
            continue
        base_cost, base_seconds = _building_remaining(entry, level, target)
        if not base_cost and base_seconds == 0:
            continue
        adj_cost, adj_seconds = upgrades.apply_boosts("defenses", base_cost, base_seconds, mods)
        records.append({
            "category": "defenses", "name": name, "level": level, "target": target,
            "base_cost": base_cost, "base_seconds": base_seconds,
            "adj_cost": adj_cost, "adj_seconds": adj_seconds,
            "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
            "time_saved": base_seconds - adj_seconds,
        })

    for r in village.get("resources", []):
        name = r.get("name")
        entry = tables.get(name)
        if not entry:
            continue
        target = _max_level_for_th(entry, town_hall)
        level = int(r.get("level", 0) or 0)
        if not target or level >= target:
            continue
        base_cost, base_seconds = _building_remaining(entry, level, target)
        if not base_cost and base_seconds == 0:
            continue
        adj_cost, adj_seconds = upgrades.apply_boosts("resources", base_cost, base_seconds, mods)
        records.append({
            "category": "resources", "name": name, "level": level, "target": target,
            "base_cost": base_cost, "base_seconds": base_seconds,
            "adj_cost": adj_cost, "adj_seconds": adj_seconds,
            "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
            "time_saved": base_seconds - adj_seconds,
        })

    traps_table = _traps()
    for t in village.get("traps", []):
        name = t.get("name")
        entry = traps_table.get(name)
        if not entry:
            continue
        target = _max_level_for_th(entry, town_hall)
        level = int(t.get("level", 0) or 0)
        if not target or level >= target:
            continue
        base_cost, base_seconds = _building_remaining(entry, level, target)
        if not base_cost and base_seconds == 0:
            continue
        adj_cost, adj_seconds = upgrades.apply_boosts("traps", base_cost, base_seconds, mods)
        records.append({
            "category": "traps", "name": name, "level": level, "target": target,
            "base_cost": base_cost, "base_seconds": base_seconds,
            "adj_cost": adj_cost, "adj_seconds": adj_seconds,
            "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
            "time_saved": base_seconds - adj_seconds,
        })

    wall = tables.get("Wall")
    if wall and village.get("walls"):
        target = _max_level_for_th(wall, town_hall)
        for grp in village["walls"]:
            level = int(grp.get("level", 0) or 0)
            count = int(grp.get("count", 0) or 0)
            if not target or level >= target or count <= 0:
                continue
            per_wall, _ = _building_remaining(wall, level, target)  # walls have 0 build time
            base_cost = {k: v * count for k, v in per_wall.items()}
            if not base_cost:
                continue
            adj_cost, _ = upgrades.apply_boosts("walls", base_cost, 0, mods)
            records.append({
                "category": "walls", "name": f"Wall lvl {level}->{target} x{count}",
                "level": level, "target": target,
                "base_cost": base_cost, "base_seconds": 0,
                "adj_cost": adj_cost, "adj_seconds": 0,
                "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
                "time_saved": 0,
            })
    return records
