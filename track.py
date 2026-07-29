"""
The one script the scheduler runs. It logs into the official Clash of Clans
API once, then for every account you list it records:

  - a daily village snapshot (progress, completion, rush)
  - remaining upgrade cost and build time, adjusted for your Gold Pass / event
    toggles in config.json
  - live events: Gold Pass season window, Raid Weekend progress, CWL state,
    plus estimated countdowns for the recurring events
  - your war attacks, whenever you're in a war

Credentials come from environment variables so nothing personal lands in a
committed file:

  COC_EMAIL         your login for developer.clashofclans.com
  COC_PASSWORD      the password for that account
  COC_PLAYER_TAGS   your tag(s), comma-separated, main first, e.g. #MAIN,#ALT1

Discount toggles the API can't detect live in config.json (safe to commit).

Output lands under data/accounts/<TAG>/ per account, plus data/summary.json.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import coc

import catalog
import dashboard
import defenses
import events
import guide
import metrics
import store
import upgrades
import wars

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

# Supercell's API throws these on gateway timeouts and maintenance windows --
# transient hiccups a retry almost always clears. One of them must NOT abort the
# whole run: in particular it must not block a village.json edit from rendering,
# since defense data is computed entirely from that file with no API call at all.
_TRANSIENT = (coc.Maintenance, coc.GatewayError, asyncio.TimeoutError)


async def _retry(make_coro, *, attempts: int = 4, base_delay: float = 3.0):
    """Await make_coro(), retrying transient API errors with linear backoff."""
    for i in range(attempts):
        try:
            return await make_coro()
        except _TRANSIENT:
            if i == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (i + 1))


def _repo_slug() -> str | None:
    """"owner/repo" from the git remote, so the dashboard can deep-link to
    'edit this file on GitHub' for village.json. None if it can't be
    determined (no remote, not a git checkout, etc) -- the dashboard just
    skips that link in that case, nothing depends on this."""
    try:
        url = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(\.git)?$", url)
        return m.group(1) if m else None
    except Exception:
        return None


def _repo_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return out if out and out != "HEAD" else "master"
    except Exception:
        return "master"

COST_COLUMNS = [
    "date", "remaining_gold", "remaining_elixir", "remaining_dark_elixir",
    "remaining_ore", "build_days_base", "build_days_adjusted", "gold_pass_boost_pct",
]


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _config() -> tuple[str, str, list[str]]:
    _load_dotenv()
    email = os.environ.get("COC_EMAIL")
    password = os.environ.get("COC_PASSWORD")
    raw = os.environ.get("COC_PLAYER_TAGS") or os.environ.get("COC_PLAYER_TAG") or ""
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    tags = [t if t.startswith("#") else "#" + t for t in tags]
    missing = [n for n, v in (("COC_EMAIL", email), ("COC_PASSWORD", password),
                              ("COC_PLAYER_TAGS", tags)) if not v]
    if missing:
        sys.exit(f"Missing required environment variable(s): {', '.join(missing)}")
    return email, password, tags


def _cost_row(cost_analysis: dict, date_str: str, mods: dict) -> dict:
    cost = cost_analysis["adjusted"]["cost"]
    ore = sum(v for k, v in cost.items() if k.endswith("_ore"))
    return {
        "date": date_str,
        "remaining_gold": cost.get("gold", 0),
        "remaining_elixir": cost.get("elixir", 0),
        "remaining_dark_elixir": cost.get("dark_elixir", 0),
        "remaining_ore": ore,
        "build_days_base": round(cost_analysis["base"]["build_seconds"] / 86400, 1),
        "build_days_adjusted": round(cost_analysis["adjusted"]["build_seconds"] / 86400, 1),
        "gold_pass_boost_pct": mods.get("gold_pass_boost_pct", 0),
    }


def _save_village(acc_dir: Path, analysis: dict, cost_analysis: dict, date_str: str, mods: dict) -> None:
    analysis = dict(analysis)
    analysis["captured_at"] = datetime.now(timezone.utc).isoformat()
    analysis["upgrades"] = cost_analysis
    store.write_json(acc_dir / "village_latest.json", analysis)
    store.write_json(acc_dir / "snapshots" / f"{date_str}.json", analysis)
    store.upsert_csv(acc_dir / "village_history.csv", metrics.CSV_COLUMNS,
                     [metrics.to_csv_row(analysis, date_str)], key_fields=["date"])
    store.upsert_csv(acc_dir / "costs_history.csv", COST_COLUMNS,
                     [_cost_row(cost_analysis, date_str, mods)], key_fields=["date"])


async def _save_wars(client, acc_dir: Path, player, date_str: str) -> str:
    result = await wars.capture(client, player, date_str)
    if result is None:
        return "no active war"
    if result.get("note") == "private war log":
        return "war log private (make it public in-game to capture regular wars)"
    if result["record"]:
        store.write_json(acc_dir / "wars" / f"{store.safe_tag(result['record']['war_id'])}.json", result["record"])
    store.upsert_csv(acc_dir / "wars.csv", wars.WAR_COLUMNS, result["rows"],
                     key_fields=["war_id", "player_tag", "attack_order"])
    if not result["record"]:
        return "in war, no attacks yet"
    return f"{result['record']['war_type']} war, {len(result['rows'])} attack(s) recorded"


def _print(analysis: dict, cost: dict, war_note: str, date_str: str) -> None:
    ident = analysis["identity"]
    rush = analysis["rush_risk"]
    adj = cost["adjusted"]
    print(f"\n{ident['name']}  {ident['tag']}  TH{ident['town_hall']}  ({date_str})")
    print(f"  offense complete : {analysis['offense_completion_pct']}%   rush {rush['score']} ({rush['band']})")
    print(f"  to finish        : {adj['build_time_one_builder']} build (1 builder), cost {adj['cost']}")
    print(f"  war              : {war_note}")


_DEF_CATS = ("defenses", "walls", "traps", "resources")


def _fallback_account(tag, prev_by_tag, mods, dash_accounts, summary) -> bool:
    """API couldn't reach this account this run. Reuse its previous dashboard
    entry (offense) and recompute defenses from the current village.json so a
    village edit still lands. Returns False if there's no prior entry to reuse."""
    entry = prev_by_tag.get(tag) or prev_by_tag.get("#" + tag.lstrip("#"))
    if not entry:
        return False
    acc_dir = DATA_DIR / "accounts" / store.safe_tag(tag)
    village = defenses.load_village(acc_dir)
    th = entry.get("town_hall")
    def_items = catalog.defense_items(village, th)
    off_items = [i for i in (entry.get("items") or []) if i.get("category") not in _DEF_CATS]
    completion = dict(entry.get("completion") or {})
    completion.update(catalog.completion(def_items))
    new_entry = dict(entry)
    new_entry.update({"items": off_items + def_items, "completion": completion,
                      "village_present": bool(village)})
    dash_accounts.append(new_entry)
    summary["accounts"].append({
        "tag": entry.get("tag"), "name": entry.get("name"), "town_hall": th,
        "offense_completion_pct": entry.get("offense_completion_pct"),
        "rush_risk": (entry.get("rush") or {}).get("score"),
        "rush_band": (entry.get("rush") or {}).get("band"),
        "note": "api_unavailable_reused_snapshot",
    })
    return True


async def run() -> None:
    email, password, tags = _config()
    mods = upgrades.load_modifiers(ROOT / "config.json")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = {"captured_at": datetime.now(timezone.utc).isoformat(),
               "modifiers": mods, "accounts": []}
    dash_accounts = []
    # Last good dashboard snapshot, so an account the API can't reach this run
    # keeps its previous offense data instead of vanishing (and its defenses
    # still refresh from village.json). Keyed by tag.
    prev_by_tag = {}
    try:
        for a in (json.loads((DATA_DIR / "dashboard_data.json").read_text()).get("accounts") or []):
            prev_by_tag[a.get("tag")] = a
    except Exception:
        pass

    async with coc.Client(load_game_data=coc.LoadGameData(never=True)) as client:
        try:
            await _retry(lambda: client.login(email, password))
        except coc.InvalidCredentials as e:
            sys.exit(f"Login failed. Check COC_EMAIL / COC_PASSWORD. ({e})")
        except _TRANSIENT as e:
            sys.exit(f"API unreachable (login timed out after retries): {e}")

        # Global events, computed once and shared. A transient failure here is
        # not fatal -- the run proceeds without this run's event data.
        try:
            gp = await _retry(lambda: events.gold_pass_window(client))
        except _TRANSIENT:
            gp = None
        scheduled = events.scheduled_calendar(season_end=gp.get("season_end") if gp else None)
        summary["gold_pass_season"] = gp
        summary["scheduled_events"] = scheduled

        for tag in tags:
            try:
                player = await _retry(lambda: client.get_player(tag))
            except coc.NotFound:
                print(f"\n{tag}: not found, skipping.")
                continue
            except _TRANSIENT as e:
                # API down for this account after retries. Don't drop it and
                # don't block the run -- reuse last run's offense data and still
                # refresh defenses from village.json (which needs no API).
                if _fallback_account(tag, prev_by_tag, mods, dash_accounts, summary):
                    print(f"\n{tag}: API timed out ({e}); reused last snapshot, refreshed defenses from village.json.")
                else:
                    print(f"\n{tag}: API timed out ({e}) and no prior snapshot to fall back on; skipping.")
                continue

            try:
                raw_player = await client.http.get_player(player.tag)
            except Exception:
                raw_player = None

            analysis = metrics.analyse(player, raw_player)
            cost_analysis = upgrades.analyse_costs(player, mods, raw_player)
            acc_dir = DATA_DIR / "accounts" / store.safe_tag(tag)
            _save_village(acc_dir, analysis, cost_analysis, date_str, mods)

            clan = getattr(player, "clan", None)
            clan_tag = getattr(clan, "tag", None) if clan else None
            acc_events = {"gold_pass_season": gp, "scheduled": scheduled}
            if clan_tag:
                try:
                    acc_events["raid_weekend"] = await _retry(lambda: events.raid_progress(client, clan_tag, player.tag))
                    acc_events["cwl"] = await _retry(lambda: events.cwl_state(client, clan_tag))
                except _TRANSIENT:
                    pass  # event data is optional; don't let it abort the run
            store.write_json(acc_dir / "events_latest.json", acc_events)

            # dynamic upgrade guide (offense always; defenses if village.json present)
            village = defenses.load_village(acc_dir)
            off_records = upgrades.remaining_records(player, mods, raw_player)
            def_records = defenses.remaining_records(village, analysis["identity"]["town_hall"], mods)
            the_guide = guide.build(off_records, def_records, mods, analysis["identity"]["town_hall"])
            store.write_json(acc_dir / "guide_latest.json", the_guide)
            (acc_dir / "guide.md").write_text(guide.to_markdown(the_guide))

            all_items = catalog.offense_items(player, raw_player) + catalog.defense_items(village, analysis["identity"]["town_hall"])
            merged_completion = dict(analysis.get("completion", {}))
            merged_completion.update(catalog.completion([i for i in all_items if i["category"] in ("defenses", "walls", "traps", "resources")]))
            try:
                war_note = await _retry(lambda: _save_wars(client, acc_dir, player, date_str))
            except _TRANSIENT:
                war_note = "war capture skipped (API timed out)"
            _print(analysis, cost_analysis, war_note, date_str)

            war_rows = []
            wcsv = acc_dir / "wars.csv"
            if wcsv.exists():
                import csv as _csv
                with wcsv.open(newline="") as _f:
                    war_rows = list(_csv.DictReader(_f))
            dash_accounts.append({
                "tag": analysis["identity"]["tag"],
                "name": analysis["identity"]["name"],
                "town_hall": analysis["identity"]["town_hall"],
                "trophies": (analysis.get("ladder") or {}).get("trophies"),
                "best_trophies": (analysis.get("ladder") or {}).get("best_trophies"),
                "war_stars": (analysis.get("ladder") or {}).get("war_stars"),
                "attack_wins": (analysis.get("ladder") or {}).get("attack_wins"),
                "defense_wins": (analysis.get("ladder") or {}).get("defense_wins"),
                "donations": (analysis.get("ladder") or {}).get("donations"),
                "received": (analysis.get("ladder") or {}).get("received"),
                "offense_completion_pct": analysis["offense_completion_pct"],
                "rush": analysis["rush_risk"],
                "completion": merged_completion,
                "items": all_items,
                "ranked": analysis.get("ranked"),
                "village_present": bool(village),
                "events": {"gold_pass_season": gp, "scheduled": scheduled,
                           "raid_weekend": acc_events.get("raid_weekend"),
                           "cwl": acc_events.get("cwl")},
                "wars": war_rows,
            })
            summary["accounts"].append({
                "tag": analysis["identity"]["tag"],
                "name": analysis["identity"]["name"],
                "town_hall": analysis["identity"]["town_hall"],
                "offense_completion_pct": analysis["offense_completion_pct"],
                "rush_risk": analysis["rush_risk"]["score"],
                "rush_band": analysis["rush_risk"]["band"],
                "build_days_to_finish": round(cost_analysis["adjusted"]["build_seconds"] / 86400, 1),
                "trophies": analysis["ladder"]["trophies"],
                "war_stars": analysis["ladder"]["war_stars"],
                "guide_mode": the_guide["mode"],
                "next_up": the_guide["items"][0]["name"] if the_guide["items"] else None,
            })

    store.write_json(DATA_DIR / "summary.json", summary)
    store.write_json(DATA_DIR / "dashboard_data.json",
                     {"captured_at": summary["captured_at"], "modifiers_default": mods,
                      "defense_tables": catalog.defense_tables(),
                      "offense_tables": catalog.offense_level_tables(),
                      "repo": _repo_slug(), "branch": _repo_branch(),
                      "accounts": dash_accounts})
    dashboard.render(DATA_DIR, ROOT / "dashboard.html")


if __name__ == "__main__":
    asyncio.run(run())
