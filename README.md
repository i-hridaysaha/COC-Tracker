# CoC Personal Tracker

> This material is unofficial and is not endorsed by Supercell. For more
> information see Supercell's Fan Content Policy:
> [www.supercell.com/fan-content-policy](https://www.supercell.com/fan-content-policy).

A tracker for your own Clash of Clans accounts that runs itself on GitHub and
builds a history of your progress over time. No server, no daily effort. Once
a day it wakes up, pulls each village from the official Supercell API, works
out what it means, records any war attacks, and writes it all down. The
dashboard is published live via GitHub Pages, so you just open the URL --
nothing to download or re-download.

It borrows the good ideas from trackers like ClashOS (completion percentages,
rush read, upgrade priorities) and adds the one thing those tools can't do:
**memory**. Every run is saved, so you watch the trend, not just today.

## What it tracks

For every account you list, each day:

- completion percent for heroes, troops, spells, pets and hero equipment,
  measured against the max for that account's current Town Hall
- an overall offense completion percent
- a **rush read** using the real definition: how far your offense sits below
  the *previous* Town Hall's max. Max the last TH before moving up and you
  read "not rushed", even on a brand-new Town Hall. That's correct.
- total levels remaining, and which items have the biggest gaps
- ladder stats: trophies, war stars, donations, attack/defense wins
- **your war attacks**, whenever you're in a war (regular or CWL), including
  stars, destruction, defender and Town Hall matchup

The honest limit: the public API returns your army and heroes, **not** your
buildings, defenses, traps, resource buildings or walls. So progress numbers
describe your offense, not your base. That's a Supercell API limit, not a bug
here.


## Events, costs and boosts

Each run also records, per account:

- **Upgrade cost and build time to finish.** Every remaining level summed from
  the full game tables, bucketed by resource (gold, elixir, dark elixir, ores)
  with total build time. Build time assumes one builder, so divide by your
  builder count for real elapsed time.
- **Gold Pass and event boosts.** The API can't see whether a pass or event
  discount is live, so you declare it in `config.json`. Gold Pass build-time
  boost is a tier: 10, 15 or 20. Event cost and time discounts are separate
  fields for the weeks Supercell runs one. The cost and time numbers above are
  then shown adjusted.
- **Live events.** The Gold Pass season window (days left), Raid Weekend state
  and your own raid progress (loot, attacks used), and CWL state.
- **Event countdowns.** Estimated time-to-next for Clan Games, season reset,
  CWL and Raid Weekend, from Supercell's fixed cadences. These are labelled
  `estimate` because the API publishes no events calendar. Season reset is
  anchored to the real Gold Pass end when available. One-off special events
  can't be predicted and aren't included.

### Dynamic upgrade guide

Every run writes a ranked guide per account: `guide.md` (readable) and
`guide_latest.json` (structured). What it ranks by shifts with what's live:

- **No event:** longest builds first. With parallel builders the long poles
  decide when you finish, so starting them first is the real path to max in the
  least time. Walls carry no build time, so they sit at the bottom.
- **Event live:** ranked by what the event saves. A cost event floats your
  priciest upgrades up; a time event floats your longest builds up. Each line
  says what it saves and which event it's riding.

Because events are targetable (below), the guide tells a whole-base Hammer Jam
apart from a hero-only or dark-elixir-only event, and reorders accordingly.

### Defenses (two ways)

**Easiest: paste it in the dashboard.** On the Overview page there's a "Paste
village JSON" button. Paste your current defense, wall and trap levels there and
your defense score, health bars, Tracker tabs and Planner priorities light up
instantly. It's saved in your browser, per account, and needs no repo file and
no run. Update it the same way whenever you upgrade.

**Or commit a file**, if you want the daily-committed data and guide.md to
include defenses too: drop the same JSON at
`data/accounts/<YOURTAG>/village.json` using `village.example.json` as the
template. Either way works; the paste is the low-effort one.

### village.json format

The API can't see buildings, so defenses and walls only join the guide if you
provide them. Copy `village.example.json` to
`data/accounts/<YOURTAG>/village.json` and fill in your current defense and wall
levels. Update it occasionally after you upgrade. This is the one manual step
in the whole tracker, and it's why you chose the fuller guide. Without the file,
the guide is offense-only and says so.

### config.json

Committed and safe to share (no secrets).

    "gold_pass_boost_pct": 0, 10, 15 or 20     Gold Pass build-time boost tier

    "events": [ ... ]     one entry per live event boost, each shaped:
        { "name": "Hammer Jam", "kind": "time", "scope": "all", "percent": 20 }
      kind    "time" or "cost"
      scope   "all", or {"category": "heroes|troops|spells|pets|equipment|defenses|walls|traps|resources"},
              or {"resource": "gold|elixir|dark_elixir"}
      percent the discount

When Hammer Jam starts you add one event line and every cost/time number and
the guide reflect it on the next run. When it ends, remove the line.

### A word on freshness

Costs, times and max levels come from the game tables bundled with the coc.py
library. When Supercell ships new content or a new Town Hall, refresh them with:

    pip install -U coc.py

On GitHub that happens on its own, since the workflow installs the latest each
run.

## Dashboard (three pages)

Every run builds `dashboard.html` at the repo root: one self-contained, dark
page tuned to GitHub's palette. It's now a small app with three pages and all
controls built in. No file editing, ever.

**Overview** — town hall completion, village health per category (heroes,
troops, spells, pets, equipment, defenses, walls, traps, resource buildings), a
defense score, your **Ranked** (Legend league) season trophies and rank (the
public API only exposes season-level aggregates, never a per-attack log, so
that's what's shown — no fabricated hit-by-hit feed), and a **War Log** of
your recent clan war / CWL attacks.

**Tracker** — every item as a card with an icon, its level, its max, a fill
bar, and a MAX badge when it's done. Tabs across the categories, including
buildings, traps and resource buildings once you've pasted `village.json`.

**Planner** — priority upgrade lists (top defenses, heroes, lab, pets,
equipment, resources) with cost and time. Tapping "+ queue" opens a picker: for
builder-lane items (defenses, walls, traps, resources) you choose which
builder queues it; for single-slot lanes (Laboratory, Pet House, Blacksmith)
it confirms into that queue. Auto-fill can also fill the plan for you, with a
projected finish date per lane. Your plan is saved in the browser.

### Toggles live in the UI now

The Planner has the boosts as on-page controls: Gold Pass tier (10/15/20),
event cost and time discounts, your builder count, and goblin builder /
researcher switches. Change one and every cost, time and queue recomputes
instantly. Settings and plans are remembered per account in your browser
(localStorage). `config.json` still seeds the defaults for the committed data
files, but you never have to touch it for day-to-day use.

The dashboard is published at **https://i-hridaysaha.github.io/COC-Tracker/**
via GitHub Pages, rebuilt automatically after every run -- just open the URL,
no download or re-download needed. Note this makes the repo (and everything
in `data/`: village levels, trophies, war history) publicly visible; that's a
deliberate tradeoff for not needing a paid GitHub plan for private Pages. If
you'd rather keep it private, drop back to the offline model instead: skip
Pages, and just download `dashboard.html` from the repo whenever you want a
fresh copy -- it's fully self-contained and works with no internet connection
once downloaded. Defenses, traps, resource buildings and walls on the
Overview and Planner come from your `village.json`. Item icons are a small
original SVG set built for this project (there's no offline, license-free
source of real game art), color-coded by category.

## Output

Everything lands under `data/`:

    data/
      (dashboard.html at repo root)    dark, self-contained dashboard, rebuilt each run
      summary.json                     every account's headline + gold pass + countdowns
      accounts/<TAG>/
        village_history.csv            daily progress trend
        costs_history.csv              daily "grind left": cost + build days
        village_latest.json            full detail of the most recent run (incl. upgrades)
        events_latest.json             gold pass, raid, CWL, countdowns
        guide.md / guide_latest.json   ranked upgrade guide (shifts with events)
        village.json                   YOUR defense + resource-building + trap + wall levels (you provide this)
        snapshots/<date>.json          full snapshot kept per day (never lost)
        wars.csv                       one row per war attack you make
        wars/<war_id>.json             full record of each war

Open any CSV in anything, or plot it.

## Setup (about 5 minutes, once)

1. **Developer account.** Sign up at
   [developer.clashofclans.com](https://developer.clashofclans.com). Free, and
   separate from your game login. You only need its email and password.

2. **Create the repo.** Push this folder to a GitHub repository. Private keeps
   everything (village levels, trophies, war history) visible only to you;
   public is what lets you use free GitHub Pages (see step 5) without a paid
   plan. Private repos need GitHub Pro or higher for Pages to work.

3. **Add three secrets.** Repo Settings → Secrets and variables → Actions → New
   repository secret:
   - `COC_EMAIL` — your developer.clashofclans.com email
   - `COC_PASSWORD` — that account's password
   - `COC_PLAYER_TAGS` — your tag(s), comma-separated, main first,
     e.g. `#MAIN123,#ALT456`

   The library logs in with these and generates an API key for whatever IP the
   GitHub runner has that day, so you never touch IP allow-lists. That's the
   part that makes it survive on GitHub.

4. **Run it once by hand.** Actions tab → "Track village" → Run workflow. Check
   the log. On success it commits your first snapshot (and `index.html`).

5. **(Optional) Turn on GitHub Pages.** Repo Settings → Pages → Source:
   "Deploy from a branch" → Branch: `master` / `/ (root)` → Save. Your
   dashboard is then live at `https://<you>.github.io/<repo>/`, rebuilt
   automatically every run. Skip this if you'd rather keep using the
   download-`dashboard.html` model.

Done. After this it runs on its own, daily.

## A note on war capture

Supercell has no "war history" endpoint. This works by checking, each run,
whether you're in a war right now and recording your attacks then. Do that
daily and the history assembles itself. Two things to know:

- **CWL wars** are captured automatically.
- **Regular wars** need your clan's war log set to public in-game. If it's
  private, the run says so and simply skips war capture for that account.

## Run locally instead (optional)

    pip install -r requirements.txt
    cp .env.example .env      # then edit .env with your details
    python track.py

`.env` is gitignored, so credentials stay off GitHub.

## Sharing this project

Safe to share as-is. Credentials live in GitHub secrets, never in the files.
Your `data/` history is the only personal thing here, so before handing the
repo to someone, clear that folder or point them at a fresh copy. `config.json`
is safe to share (just your boost toggles). They add their own three secrets
and it's their tracker.

## Change the schedule

Edit the `cron` line in `.github/workflows/track.yml`. It's in UTC.

## Not affiliated with Supercell

This material is unofficial and is not endorsed by Supercell. For more
information see Supercell's Fan Content Policy:
[www.supercell.com/fan-content-policy](https://www.supercell.com/fan-content-policy).
