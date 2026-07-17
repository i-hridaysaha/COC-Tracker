"""
Remaining upgrade cost and build time, per item, with scope-aware boosts.

Every remaining level is summed from the full game tables, so "cost to finish"
is real, not just the next tap. Two honest limits carry over from before: the
API can't see your builders, so build time is reported as one-builder total
(divide by your builder count), and it can't see live events, so boosts come
from config.json, not the game.

Boosts are now targetable. A boost has a kind (time or cost), a scope (all, or
a category, or a resource), and a percent. That's what lets the guide tell a
whole-base event like Hammer Jam apart from a hero-only or dark-elixir-only
one. Gold Pass is a plain build-time boost across everything.
"""

import json
from pathlib import Path

import metrics

_STATIC_CACHE = None
_RESOURCE_KEY = {"Gold": "gold", "Elixir": "elixir", "Dark Elixir": "dark_elixir"}
CATEGORIES = ("heroes", "troops", "spells", "pets", "equipment")


def _static() -> dict:
    global _STATIC_CACHE
    if _STATIC_CACHE is not None:
        return _STATIC_CACHE
    import coc
    raw = json.loads((Path(coc.__file__).parent / "static" / "static_data.json").read_text())
    tables = {c: {} for c in CATEGORIES}
    for section in tables:
        for item in raw.get(section, []):
            if section in ("heroes", "troops") and item.get("village") not in (None, "home"):
                continue
            tables[section].setdefault(item["name"], item)
    _STATIC_CACHE = tables
    return tables


def _add_cost(bucket: dict, resource, cost):
    if isinstance(cost, dict):
        for ore, amount in cost.items():
            if amount:
                bucket[ore] = bucket.get(ore, 0) + int(amount)
    elif cost:
        key = _RESOURCE_KEY.get(resource, (resource or "other").lower().replace(" ", "_"))
        bucket[key] = bucket.get(key, 0) + int(cost)


def _item_remaining(entry: dict, current: int, target: int) -> tuple[dict, int]:
    """Troops/heroes/spells/pets store cost at the source level (X -> X+1),
    so we sum levels [current, target - 1]."""
    cost, seconds = {}, 0
    by_level = {lvl["level"]: lvl for lvl in entry.get("levels", [])}
    for lvl in range(current, target):
        data = by_level.get(lvl)
        if not data:
            continue
        _add_cost(cost, entry.get("upgrade_resource"), data.get("upgrade_cost"))
        seconds += int(data.get("upgrade_time", 0) or 0)
    return cost, seconds


# ---- scope-aware boost application (shared with the defense engine) ----

def _scope_hits_item(scope, category: str, cost: dict) -> bool:
    if scope in ("all", None):
        return True
    if isinstance(scope, dict):
        if "category" in scope:
            return scope["category"] == category
        if "resource" in scope:
            return scope["resource"] in cost
    return False


def apply_boosts(category: str, base_cost: dict, base_seconds: int, mods: dict) -> tuple[dict, int]:
    """Return (adjusted_cost, adjusted_seconds) for one item."""
    events = mods.get("events", []) or []

    # time: gold pass (all) plus any time-kind event whose scope hits this item
    time_factor = 1 - min(mods.get("gold_pass_boost_pct", 0) or 0, 95) / 100
    for e in events:
        if e.get("kind") == "time" and _scope_hits_item(e.get("scope"), category, base_cost):
            time_factor *= 1 - min(e.get("percent", 0) or 0, 95) / 100
    adj_seconds = int(round(base_seconds * max(time_factor, 0.05)))

    # cost: applied per resource, since a resource-scoped event only cuts that one
    adj_cost = {}
    for res, val in base_cost.items():
        factor = 1.0
        for e in events:
            if e.get("kind") != "cost":
                continue
            scope = e.get("scope")
            hits = (scope in ("all", None)
                    or (isinstance(scope, dict) and scope.get("category") == category)
                    or (isinstance(scope, dict) and scope.get("resource") == res))
            if hits:
                factor *= 1 - min(e.get("percent", 0) or 0, 95) / 100
        adj_cost[res] = int(round(val * max(factor, 0.05)))
    return adj_cost, adj_seconds


def _fmt_time(seconds: int) -> str:
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m and not d:
        parts.append(f"{m}m")
    return " ".join(parts) or "0m"


def load_modifiers(config_path: Path) -> dict:
    default = {"gold_pass_boost_pct": 0, "events": []}
    if not config_path.exists():
        return default
    try:
        data = json.loads(config_path.read_text())
    except Exception:
        return default
    mods = data.get("modifiers", {})
    out = dict(default)
    gp = mods.get("gold_pass_boost_pct", 0)
    out["gold_pass_boost_pct"] = gp if gp in (0, 10, 15, 20) else 0
    evs = mods.get("events", [])
    clean = []
    for e in evs if isinstance(evs, list) else []:
        if not isinstance(e, dict) or not e.get("percent"):
            continue
        if e.get("kind") not in ("time", "cost"):
            continue
        clean.append({"name": e.get("name", "event"), "kind": e["kind"],
                      "scope": e.get("scope", "all"), "percent": e["percent"]})
    out["events"] = clean
    return out


def remaining_records(player, mods: dict) -> list[dict]:
    """One record per offense item that still has levels to go."""
    town_hall = int(getattr(player, "town_hall", 0) or 0)
    tables = _static()
    groups = metrics.group_items(player)
    records = []
    for cat, items in groups.items():
        for it in items:
            entry = tables.get(cat, {}).get(getattr(it, "name", None))
            if not entry:
                continue
            try:
                target = it.get_max_level_for_townhall(town_hall)
            except Exception:
                target = getattr(it, "max_level", None)
            if not target:
                continue
            level = min(int(getattr(it, "level", 0) or 0), int(target))
            if level >= target:
                continue
            base_cost, base_seconds = _item_remaining(entry, level, int(target))
            if not base_cost and base_seconds == 0:
                continue
            adj_cost, adj_seconds = apply_boosts(cat, base_cost, base_seconds, mods)
            records.append({
                "category": cat, "name": getattr(it, "name", "?"),
                "level": level, "target": int(target),
                "base_cost": base_cost, "base_seconds": base_seconds,
                "adj_cost": adj_cost, "adj_seconds": adj_seconds,
                "cost_saved": sum(base_cost.values()) - sum(adj_cost.values()),
                "time_saved": base_seconds - adj_seconds,
            })
    return records


def _aggregate(records: list[dict]) -> dict:
    base_cost, adj_cost, base_s, adj_s = {}, {}, 0, 0
    for r in records:
        for k, v in r["base_cost"].items():
            base_cost[k] = base_cost.get(k, 0) + v
        for k, v in r["adj_cost"].items():
            adj_cost[k] = adj_cost.get(k, 0) + v
        base_s += r["base_seconds"]
        adj_s += r["adj_seconds"]
    return {
        "base": {"cost": base_cost, "build_seconds": base_s, "build_time_one_builder": _fmt_time(base_s)},
        "adjusted": {"cost": adj_cost, "build_seconds": adj_s, "build_time_one_builder": _fmt_time(adj_s)},
    }


def analyse_costs(player, mods: dict) -> dict:
    records = remaining_records(player, mods)
    agg = _aggregate(records)
    by_cat = {}
    for r in records:
        c = by_cat.setdefault(r["category"], {"cost": {}, "build_seconds": 0})
        for k, v in r["adj_cost"].items():
            c["cost"][k] = c["cost"].get(k, 0) + v
        c["build_seconds"] += r["adj_seconds"]
    for c in by_cat.values():
        c["build_time"] = _fmt_time(c["build_seconds"])
    return {
        "modifiers_applied": mods, **agg, "by_category": by_cat,
        "note": "Build time assumes one builder. Divide by your builder count for real elapsed time.",
    }
