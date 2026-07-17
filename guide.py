"""
The dynamic upgrade guide.

It takes every remaining upgrade, offense from the API and defenses/walls from
your pasted village.json, and ranks them. The ranking changes with what's
live:

  - No event: sorted by build time, longest first. That's the honest answer to
    "what gets me to max fastest", because with parallel builders the long
    poles decide when you finish, so you start them first. Walls carry no build
    time, so they sit at the bottom as pure resource sinks.

  - Event live: sorted by what the event saves you. During a cost event the
    biggest-cost upgrades float up (do them cheap). During a time event the
    longest builds float up (bank the saved days). Each line says what it saves
    and which event it's riding.

Defenses only appear if you've provided village.json. Without it the guide is
offense-only and says so.
"""

from datetime import timedelta


def _fmt(seconds: int) -> str:
    if not seconds:
        return "no build time"
    return str(timedelta(seconds=int(seconds))).replace(", 0:00:00", "")


def _human_cost(cost: dict) -> str:
    order = ["gold", "elixir", "dark_elixir", "shiny_ore", "glowy_ore", "starry_ore"]
    labels = {"gold": "gold", "elixir": "elixir", "dark_elixir": "DE",
              "shiny_ore": "shiny", "glowy_ore": "glowy", "starry_ore": "starry"}
    parts = [f"{cost[k]:,} {labels.get(k, k)}" for k in order if cost.get(k)]
    parts += [f"{v:,} {k}" for k, v in cost.items() if k not in order and v]
    return ", ".join(parts) or "free"


def build(offense_records, defense_records, mods, town_hall) -> dict:
    events = mods.get("events", []) or []
    have_defenses = bool(defense_records)
    recs = list(offense_records) + list(defense_records)

    if events:
        mode = "event"
        event_names = ", ".join(e.get("name", "event") for e in events)
        recs.sort(key=lambda r: (r["cost_saved"], r["time_saved"]), reverse=True)
    else:
        mode = "time_to_max"
        event_names = None
        recs.sort(key=lambda r: (r["adj_seconds"], sum(r["adj_cost"].values())), reverse=True)

    ranked = []
    for i, r in enumerate(recs, 1):
        if mode == "event":
            bits = []
            if r["cost_saved"] > 0:
                bits.append(f"saves {r['cost_saved']:,} in resources")
            if r["time_saved"] > 0:
                bits.append(f"saves {_fmt(r['time_saved'])} build time")
            reason = (" and ".join(bits) + f" while {event_names} is live") if bits else "not affected by the active event"
        else:
            if r["adj_seconds"] == 0:
                reason = "no build time, a pure resource sink, slot in when a builder is free"
            else:
                reason = f"one of your longest builds at {_fmt(r['adj_seconds'])}, start early to reach max sooner"
        ranked.append({
            "rank": i, "category": r["category"], "name": r["name"],
            "from_level": r["level"], "to_level": r["target"],
            "cost": r["adj_cost"], "cost_text": _human_cost(r["adj_cost"]),
            "build_time": _fmt(r["adj_seconds"]), "build_seconds": r["adj_seconds"],
            "reason": reason,
        })

    total_seconds = sum(r["adj_seconds"] for r in recs)
    total_cost = {}
    for r in recs:
        for k, v in r["adj_cost"].items():
            total_cost[k] = total_cost.get(k, 0) + v

    return {
        "town_hall": town_hall, "mode": mode, "active_events": event_names,
        "includes_defenses": have_defenses,
        "total_build_time_one_builder": _fmt(total_seconds),
        "total_cost": total_cost, "total_cost_text": _human_cost(total_cost),
        "items": ranked,
    }


def to_markdown(guide: dict) -> str:
    lines = [f"# Upgrade guide — TH{guide['town_hall']}", ""]
    if guide["mode"] == "event":
        lines.append(f"**Event live: {guide['active_events']}.** Ranked by what the event saves you.")
    else:
        lines.append("**No event live.** Ranked to reach max in the least time: longest builds first.")
    if not guide["includes_defenses"]:
        lines.append("")
        lines.append("_Offense only. Add `village.json` to include defenses and walls._")
    lines += ["", f"Total remaining: {guide['total_build_time_one_builder']} of build time (one builder), "
              f"{guide['total_cost_text']}.", ""]
    for it in guide["items"]:
        lines.append(f"{it['rank']}. **{it['name']}** ({it['category']}) "
                     f"{it['from_level']} → {it['to_level']} — {it['cost_text']}, {it['build_time']}")
        lines.append(f"   _{it['reason']}_")
    return "\n".join(lines) + "\n"
