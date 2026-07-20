"""
Builds dashboard.html: a single self-contained, three-page app.

This is the shift you asked for. The old dashboard was a static picture rendered
by Python. This one embeds the full per-item catalog plus your data, and does
the boost math and planning in the browser. That's what lets every toggle live
in the UI: Gold Pass tier, event discounts, builder count, goblin builder and
researcher are controls on the page, not lines in a file. Change one and costs,
times and queues recompute instantly. Nothing to edit, no run to wait for. Your
settings and plan are remembered in the browser (localStorage), per account.

Still one file, still offline, still private. It reads data/dashboard_data.json
at build time and bakes it in.

Pages: Overview (completion ring, village health, defense score, battle log),
Tracker (every item as a card with level/max and a fill bar), Planner (priority
lists with live cost/time and builder / lab / pet / blacksmith queues).

Honest limits from the API: it never exposes whether a boost is live, how many
builders you have, or their status, so those are your inputs here. Defenses,
walls and traps come from village.json.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


STYLE = r"""
:root{color-scheme:dark;
--canvas:#0d1117;--surface:#161b22;--raised:#1c2128;--border:#30363d;--soft:#21262d;
--text:#e6edf3;--muted:#8b949e;--faint:#6e7681;
--blue:#58a6ff;--green:#3fb950;--amber:#e3b341;--gold:#d9a520;--orange:#f0883e;--purple:#bc8cff;--red:#f85149;--bronze:#db6d28;}
*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--text);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
.wrap{max-width:1120px;margin:0 auto;padding:20px 18px 80px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
h1{font-size:16px;font-weight:600;margin:0;letter-spacing:.2px}
.sub{color:var(--muted);font-size:12px}
.nav{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:5px;margin-bottom:16px}
.navbtn{background:transparent;border:0;color:var(--muted);padding:9px;border-radius:7px;cursor:pointer;font-size:14px;font-weight:600;display:flex;align-items:center;justify-content:center;gap:7px}
.navbtn.active{background:var(--raised);color:var(--gold);box-shadow:inset 0 -2px 0 var(--gold)}
.accts{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.acct{background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:6px 14px;border-radius:20px;cursor:pointer;font-size:13px}
.acct.active{color:var(--text);border-color:#58a6ff66;background:var(--raised)}
.page{display:none}.page.active{display:block}
.card{background:var(--surface);border:1px solid var(--soft);border-radius:10px;padding:16px}
.card+.card{margin-top:14px}
h3{margin:0 0 12px;font-size:12px;font-weight:700;color:var(--gold);text-transform:uppercase;letter-spacing:.7px}
.muted{color:var(--muted)}.faint{color:var(--faint)}
.ovtop{display:grid;grid-template-columns:180px 1fr;gap:20px;align-items:center}
.ring{position:relative;width:160px;height:160px;margin:0 auto}
.ringpct{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.ringpct b{font-size:34px;font-weight:700;font-family:ui-monospace,monospace}
.ringpct span{font-size:12px;color:var(--muted)}
.ovstats .line{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--soft)}
.ovstats .line:last-child{border-bottom:0}
.ovstats .k{color:var(--muted)}.ovstats .v{font-family:ui-monospace,monospace;font-weight:600}
.badge{display:inline-flex;align-items:center;gap:6px;border-radius:20px;padding:6px 14px;font-size:12px;font-weight:600;border:1px solid}
.badge.ok{color:var(--green);border-color:#3fb95055;background:#3fb9500f}
.badge.warn{color:var(--amber);border-color:#e3b34155;background:#e3b3410f}
.health .hrow{display:grid;grid-template-columns:110px 1fr 46px;align-items:center;gap:10px;margin-bottom:9px}
.hlabel{color:var(--muted);text-transform:capitalize}
.htrack{display:block;height:9px;background:var(--soft);border-radius:5px;overflow:hidden}
.hfill{display:block;height:100%;border-radius:5px}
.hpct{font-family:ui-monospace,monospace;text-align:right;font-size:13px}
.cards6{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.stat{background:var(--raised);border:1px solid var(--soft);border-radius:8px;padding:12px}
.stat b{font-size:19px;font-family:ui-monospace,monospace;display:block}
.stat span{color:var(--muted);font-size:11px}
.log .lrow{display:grid;grid-template-columns:78px 52px 1fr auto;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--soft);font-size:13px}
.log .lrow:last-child{border-bottom:0}
.stars{color:var(--amber);letter-spacing:1px}
.leaguetag{font-size:10px;color:var(--faint);border:1px solid var(--soft);border-radius:4px;padding:1px 6px;text-transform:uppercase}
.pills{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.pill{background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:8px 16px;border-radius:22px;cursor:pointer;font-size:13px;font-weight:600}
.pill.active{background:var(--gold);color:#1a1200;border-color:var(--gold)}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
.tile{background:var(--surface);border:1px solid var(--soft);border-radius:12px;padding:12px;text-align:center;position:relative}
.tile.max{border-color:#3fb95055;background:#3fb9500a}
.ic{width:56px;height:56px;border-radius:12px;margin:0 auto 8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px;font-family:ui-monospace,monospace}
.tname{font-size:12px;color:var(--muted);min-height:30px;display:flex;align-items:center;justify-content:center}
.tlv{font-family:ui-monospace,monospace;font-weight:600;color:var(--gold);margin:2px 0 8px}
.tbar{height:6px;background:var(--soft);border-radius:4px;overflow:hidden}
.tfill{height:100%;border-radius:4px}
.maxbadge{position:absolute;top:8px;right:8px;background:var(--green);color:#04240f;font-size:10px;font-weight:700;border-radius:5px;padding:1px 6px}
.settings{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.field{display:flex;flex-direction:column;gap:6px}
.field label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.seg{display:flex;gap:4px}
.seg button{flex:1;background:var(--raised);border:1px solid var(--border);color:var(--muted);padding:7px;border-radius:6px;cursor:pointer;font-family:ui-monospace,monospace;font-size:12px}
.seg button.on{background:var(--gold);color:#1a1200;border-color:var(--gold)}
input[type=number]{background:var(--raised);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:8px;font-family:ui-monospace,monospace;width:100%}
.toggle{display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
.toggle .sw{width:38px;height:22px;border-radius:12px;background:var(--soft);position:relative;transition:.15s;flex:none}
.toggle .sw::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:var(--faint);transition:.15s}
.toggle.on .sw{background:#3fb95055}.toggle.on .sw::after{left:18px;background:var(--green)}
.pcols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.prio h4{margin:0 0 8px;font-size:13px;color:var(--text)}
.pitem{display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid var(--soft)}
.pitem:last-child{border-bottom:0}
.pi-name{font-size:13px;min-width:0}
.pi-name .lv{color:var(--muted);font-family:ui-monospace,monospace;font-size:11px}
.pi-meta{font-family:ui-monospace,monospace;font-size:11px;color:var(--muted);text-align:right;white-space:nowrap}
.addbtn{background:var(--raised);border:1px solid var(--border);color:var(--blue);border-radius:6px;padding:4px 8px;font-size:11px;cursor:pointer}
.addbtn:hover{border-color:var(--blue)}
.autofill{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.af{background:var(--raised);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:9px 14px;font-size:13px;cursor:pointer;font-weight:600;text-decoration:none;display:inline-block}
.af:hover{border-color:var(--gold)}.af.clear{color:var(--red)}
.lanes{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.lane{background:var(--raised);border:1px solid var(--soft);border-radius:10px;padding:12px}
.lane h5{margin:0 0 4px;font-size:13px;display:flex;justify-content:space-between}
.lane .sum{color:var(--muted);font-size:11px;font-family:ui-monospace,monospace;margin-bottom:8px}
.qitem{display:flex;justify-content:space-between;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--soft);border-radius:6px;padding:6px 8px;margin-bottom:6px;font-size:12px}
.qitem .x{color:var(--faint);cursor:pointer;font-weight:700}
.qitem .x:hover{color:var(--red)}
.empty{color:var(--faint);font-size:12px;border:1px dashed var(--border);border-radius:6px;padding:14px;text-align:center}
.note{color:var(--faint);font-size:11px;margin-top:6px}
@media(max-width:900px){.ovtop{grid-template-columns:1fr}.grid{grid-template-columns:repeat(4,1fr)}.pcols{grid-template-columns:1fr}.lanes{grid-template-columns:1fr}.settings{grid-template-columns:1fr 1fr}.cards6{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){.grid{grid-template-columns:repeat(3,1fr)}}
.modal{display:none;position:fixed;inset:0;background:rgba(1,4,9,.72);z-index:50;align-items:center;justify-content:center;padding:20px}
.modalbox{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;max-width:640px;width:100%;max-height:86vh;overflow:auto}
.modalbox textarea{width:100%;height:300px;background:var(--canvas);border:1px solid var(--border);border-radius:8px;color:var(--text);font-family:ui-monospace,monospace;font-size:12px;padding:12px;resize:vertical;margin-top:10px}
.modalbtns{display:flex;gap:8px;margin-top:12px}
.verr{color:var(--red);font-size:12px;min-height:16px;margin-top:6px}
.ico{width:1em;height:1em;display:inline-block;vertical-align:-.15em}
.ico-img{width:100%;height:100%;object-fit:contain;display:block}
.ico-placeholder{display:inline-flex;align-items:center;justify-content:center;width:1em;height:1em;background:var(--soft);border-radius:4px}
.ic .ico{width:30px;height:30px;display:flex;align-items:center;justify-content:center}
.ic .ico-img{max-width:100%;max-height:100%}
.pi-name{display:flex;align-items:center;gap:7px}
.pi-ic{width:16px;height:16px;flex:none;opacity:.9;display:flex;align-items:center;justify-content:center}
.pi-ic .ico-img{max-width:100%;max-height:100%}
.qpick{display:flex;justify-content:space-between;align-items:center;gap:10px;background:var(--raised);border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:8px;cursor:pointer;font-size:13px}
.qpick:hover{border-color:var(--gold)}
.qpick .meta{color:var(--muted);font-size:11px;font-family:ui-monospace,monospace;white-space:nowrap}
.qsub{color:var(--muted);font-size:12px;margin:4px 0 12px}
.lane{transition:box-shadow .3s,border-color .3s}
.lane.flash{border-color:var(--gold);box-shadow:0 0 0 3px #d9a52033}
.rk .rline{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--soft);font-size:13px}
.rk .rline:last-child{border-bottom:0}
"""

APP_JS = r"""
const CAT_COLOR={heroes:'#bc8cff',troops:'#f0883e',spells:'#58a6ff',pets:'#3fb950',equipment:'#e3b341',defenses:'#db6d28',walls:'#8b949e',traps:'#f85149',resources:'#d9a520'};
const DEFENSE=['defenses','walls','traps'];
const BUILDER_CATS=['defenses','walls','traps','resources','heroes'];
const LANE_OF={defenses:'builders',walls:'builders',traps:'builders',resources:'builders',heroes:'builders',troops:'lab',spells:'lab',pets:'pet',equipment:'smith'};
const LANE_LABEL={lab:'Laboratory',pet:'Pet House',smith:'Blacksmith'};

/* Real game icons from COC ICON PACK, organized by category. */
const ICON_MAP={troops:{'Barbarian':'Avatar_Barbarian.webp','Archer':'Avatar_Archer.webp','Giant':'Avatar_Giant.webp','Goblin':'Avatar_Goblin.webp','Wall Breaker':'Avatar_Wall_Breaker.webp','Balloon':'Avatar_Balloon.webp','Wizard':'Avatar_Wizard.webp','Healer':'Avatar_Healer.webp','Dragon':'Avatar_Dragon.webp','P.E.K.K.A':'Avatar_P.E.K.K.A.webp','Baby Dragon':'Avatar_Baby_Dragon.webp','Miner':'Avatar_Miner.webp','Electro Dragon':'Avatar_Electro_Dragon.webp','Yeti':'Avatar_Yeti.webp','Dragon Rider':'Avatar_Dragon_Rider.webp','Electro Titan':'Avatar_Electro_Titan.webp','Root Rider':'Avatar_Root_Rider.webp','Druid':'Avatar_Druid.webp','Minion':'Avatar_Minion.webp','Hog Rider':'Avatar_Hog_Rider.webp','Valkyrie':'Avatar_Valkyrie.webp','Golem':'Avatar_Golem.webp','Witch':'Avatar_Witch.webp','Lava Hound':'Avatar_Lava_Hound.webp','Bowler':'Avatar_Bowler.webp','Ice Golem':'Avatar_Ice_Golem.webp','Headhunter':'Avatar_Headhunter.webp','Apprentice Warden':'Avatar_Apprentice_Warden.webp','Ruin Witch':'Avatar_Ruin_Witch.webp','Wall Wrecker':'Avatar_Wall_Wrecker.webp','Battle Blimp':'Avatar_Battle_Blimp.webp','Stone Slammer':'Avatar_Stone_Slammer.webp','Siege Barracks':'Avatar_Siege_Barracks.webp','Log Launcher':'Avatar_Log_Launcher.webp','Flame Flinger':'Avatar_Flame_Flinger.webp','Battle Drill':'Avatar_Battle_Drill.webp','Sky Wagon':'Avatar_Sky_Wagon.webp','Thrower':'Avatar_Thrower.webp','Furnace':'Avatar_Furnace.webp','Troop Launcher':'Avatar_Troop_Launcher.webp','Meteor Golem':'Avatar_Meteor_Golem.webp'},heroes:{'Barbarian King':'Avatar_Hero_Barbarian_King.webp','Archer Queen':'Avatar_Hero_Archer_Queen.webp','Grand Warden':'Avatar_Hero_Grand_Warden.webp','Royal Champion':'Avatar_Hero_Royal_Champion.webp','Minion Prince':'Avatar_Hero_Minion_Prince.webp','Dragon Duke':'Avatar_Hero_Dragon_Duke.webp'},pets:{'L.A.S.S.I':'Avatar_L.A.S.S.I.webp','Electro Owl':'Avatar_Electro_Owl.webp','Mighty Yak':'Avatar_Mighty_Yak.webp','Unicorn':'Avatar_Unicorn.webp','Frosty':'Avatar_Frosty.webp','Diggy':'Avatar_Diggy.webp','Poison Lizard':'Avatar_Poison_Lizard.webp','Phoenix':'Avatar_Phoenix.webp','Spirit Fox':'Avatar_Spirit_Fox.webp','Angry Jelly':'Avatar_Angry_Jelly.webp','Sneezy':'Avatar_Sneezy.webp','Greedy Raven':'Avatar_Greedy_Raven.webp'},defenses:{'Cannon':'Cannon21B.webp','Archer Tower':'Archer_Tower21.webp','Mortar':'Mortar18B.webp','Air Defense':'Air_Defense16.webp','Wizard Tower':'Wizard_Tower17.webp','Air Sweeper':'Air_Sweeper7.webp','Hidden Tesla':'Hidden_Tesla17.webp','Bomb Tower':'Bomb_Tower13.webp','X-Bow':'X-Bow13_Ground.webp','Inferno Tower':'Inferno_Tower12_Single.webp','Eagle Artillery':'Eagle_Artillery7.webp','Scattershot':'Scattershot7.webp','Spell Tower':'Spell_Tower4_Rage.webp','Monolith':'Monolith5.webp','Ricochet Cannon':'Ricochet_Cannon4.webp','Multi-Archer Tower':'Multi-Archer_Tower4.webp','Firespitter':'Firespitter3.webp','Revenge Tower':'Revenge_Tower2_Stage3.webp','Multi-Gear Tower':'Multi-Gear_Tower3_LongRange.webp'},traps:{'Bomb':'Bomb13.webp','Spring Trap':'Spring_Trap13.webp','Giant Bomb':'Giant_Bomb11.webp','Air Bomb':'Air_Bomb13.webp','Seeking Air Mine':'Seeking_Air_Mine7.webp','Skeleton Trap':'SkeletonTrap5.webp','Tornado Trap':'Tornado_Trap2.webp','Giga Bomb':'Giga_Bomb4.webp'},walls:{'Walls':'Wall19.webp','Wall lvl 1':'Wall19.webp','Wall lvl 2':'Wall19.webp','Wall lvl 3':'Wall19.webp','Wall lvl 4':'Wall19.webp','Wall lvl 5':'Wall19.webp','Wall lvl 6':'Wall19.webp','Wall lvl 7':'Wall19.webp','Wall lvl 8':'Wall19.webp','Wall lvl 9':'Wall19.webp','Wall lvl 10':'Wall19.webp','Wall lvl 11':'Wall19.webp','Wall lvl 12':'Wall19.webp','Wall lvl 13':'Wall19.webp','Wall lvl 14':'Wall19.webp','Wall lvl 15':'Wall19.webp','Wall lvl 16':'Wall19.webp','Wall lvl 17':'Wall17.webp','Wall lvl 18':'Wall18.webp','Wall lvl 19':'Wall19.webp'},resources:{'Gold Mine':'Gold_Mine17.webp','Elixir Collector':'Elixir_Collector17.webp','Dark Elixir Drill':'Dark_Elixir_Drill11.webp','Gold Storage':'Gold_Storage19.webp','Elixir Storage':'Elixir_Storage19.webp','Dark Elixir Storage':'Dark_Elixir_Storage13.webp'},spells:{'Lightning Spell':'Lightning_Spell_info.webp','Healing Spell':'Healing_Spell_info.webp','Rage Spell':'Rage_Spell_info.webp','Jump Spell':'Jump_Spell_info.webp','Freeze Spell':'Freeze_Spell_info.webp','Clone Spell':'Clone_Spell_info.webp','Recall Spell':'Recall_Spell_info.webp','Revive Spell':'Revive_Spell_info.webp','Poison Spell':'Poison_Spell_info.webp','Earthquake Spell':'Earthquake_Spell_info.webp','Haste Spell':'Haste_Spell_info.webp','Skeleton Spell':'Skeleton_Spell_info.webp','Bat Spell':'Bat_Spell_info.webp','Overgrowth Spell':'Overgrowth_Spell_info.webp','Angry Spell':'Angry_Spell_info.webp','Invisibility Spell':'Invisibility_Spell_info.webp','Totem Spell':'Totem_Spell_info.webp','Ice Block Spell':'Ice_Block_Spell_info.webp'},equipment:{'Barbarian Puppet':'Barbarian_Puppet.webp','Archer Puppet':'Archer_Puppet.webp','Giant Gauntlets':'Giant_Gauntlet.webp','Rage Gem':'Rage_Gem.webp','Heal Tome':'Healing_Tome.webp','Hog Rider Gauntlets':'Hog_Rider_Puppet.webp','Tornado Boots':'Earthquake_Boots.webp','Fireball Gloves':'Fireball_Equipment.webp','Electro Boots':'Electro_Boots.webp','Ice Arrows':'Frozen_Arrow.webp','Healing Tome':'Eternal_Tome.webp','Frost Helm':'Frost_Flake.webp','Phoenix Feather':'Fire_Heart.webp','Eternal Token':'Eternal_Tome.webp','Vampire Bat':'Invisibility_Vial.webp','Royal Gem':'Royal_Gem.webp','Monolith Arrow':'Monolith_Arrow.webp','Flame Blower':'Flame_Blower.webp','Stun Blaster':'Stun_Blaster.webp','Rage Vial':'Rage_Vial.webp','Invisibility Vial':'Invisibility_Vial.webp','Life Gem':'Life_Gem.webp','Seeking Shield':'Seeking_Shield.webp','Earthquake Boots':'Earthquake_Boots.webp','Electro Fangs':'Electro_Fangs.webp','Haste Vial':'Haste_Vial.webp','Action Figure':'Action_Figure.webp','Dark Crown':'Dark_Crown.webp','Dark Orb':'Dark_Orb.webp','Heroic Torch':'Heroic_Torch.webp','Magic Mirror':'Magic_Mirror.webp','Metal Pants':'Metal_Pants.webp','Meteor Staff':'Meteor_Staff.webp','Noble Iron':'Noble_Iron.webp','Rocket Backpack':'Rocket_Backpack.webp','Rocket Spear':'Rocket_Spear.webp','Snake Bracelet':'Snake_Bracelet.webp','Spiky Ball':'Spiky_Ball.webp','Stick Horse':'Stick_Horse.webp','Vampstache':'Vampstache.webp','Fire Heart':'Fire_Heart.webp','Eternal Tome':'Eternal_Tome.webp','Hog Rider Puppet':'Hog_Rider_Puppet.webp','Giant Gauntlet':'Giant_Gauntlet.webp','Frozen Arrow':'Frozen_Arrow.webp','Giant Arrow':'Giant_Arrow.webp','Healer Puppet':'Healer_Puppet.webp','Fireball':'Fireball_Equipment.webp','Lavaloon Puppet':'Lavaloon_Puppet.webp','Henchmen Puppet':'Henchmen_Puppet.webp','Frost Flake':'Frost_Flake.webp'}};
const MAX_LEVELS_CSV={"Barbarian":{1:1,2:2,3:2,4:2,5:3,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:12,17:13,18:14},"Archer":{1:1,2:2,3:2,4:2,5:3,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:12,17:13,18:14},"Giant":{2:1,3:2,4:2,5:2,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:12,17:13,18:14},"Goblin":{2:1,3:2,4:2,5:3,6:3,7:4,8:5,9:6,10:7,11:8,12:8,13:9,14:10,15:11,16:11,17:12,18:13},"Wall Breaker":{3:2,4:2,5:3,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:12,17:13,18:14},"Balloon":{3:2,4:2,5:3,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:12,17:13,18:14},"Wizard":{5:2,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:12,17:13,18:14},"Healer":{6:2,7:3,8:4,9:4,10:5,11:5,12:6,13:7,14:8,15:9,16:9,17:10,18:11},"Dragon":{7:2,8:3,9:4,10:5,11:6,12:7,13:8,14:9,15:10,16:11,17:12,18:13},"P.E.K.K.A":{8:3,9:5,10:6,11:7,12:8,13:9,14:10,15:11,16:12,17:13,18:14},"Baby Dragon":{9:2,10:4,11:5,12:6,13:7,14:8,15:9,16:10,17:11,18:12},"Miner":{10:3,11:5,12:6,13:7,14:8,15:9,16:10,17:11,18:12},"Electro Dragon":{11:2,12:3,13:4,14:5,15:6,16:7,17:8,18:9},"Yeti":{12:2,13:3,14:4,15:5,16:6,17:7,18:8},"Dragon Rider":{13:2,14:3,15:4,16:5,17:6,18:7},"Electro Titan":{14:2,15:3,16:4,17:5,18:6},"Root Rider":{15:2,16:3,17:4,18:5},"Druid":{16:2,17:3,18:4},"Meteor Golem":{14:1,15:1,16:1,17:2,18:2},"Minion":{7:2,8:4,9:5,10:6,11:7,12:8,13:9,14:10,15:11,16:12,17:13,18:14},"Hog Rider":{7:2,8:4,9:5,10:6,11:7,12:9,13:10,14:11,15:12,16:13,17:14,18:15},"Valkyrie":{8:2,9:4,10:5,11:6,12:7,13:8,14:9,15:10,16:11,17:12,18:13},"Golem":{8:2,9:4,10:5,11:7,12:9,13:10,14:11,15:12,16:13,17:14,18:15},"Witch":{9:2,10:3,11:4,12:5,13:5,14:6,15:6,16:7,17:8,18:9},"Lava Hound":{9:2,10:3,11:4,12:5,13:6,14:6,15:6,16:7,17:8,18:9},"Bowler":{10:2,11:3,12:4,13:5,14:6,15:7,16:8,17:9,18:10},"Ice Golem":{11:2,12:3,13:4,14:5,15:6,16:7,17:8,18:9},"Headhunter":{12:2,13:3,14:3,15:3,16:4,17:5,18:6},"Apprentice Warden":{13:2,14:3,15:4,16:4,17:5,18:6},"Ruin Witch":{16:2,17:3,18:4},"Wall Wrecker":{12:3,13:4,14:4,15:5,16:5,17:6,18:7},"Battle Blimp":{12:3,13:4,14:4,15:5,16:5,17:6,18:7},"Stone Slammer":{12:3,13:4,14:4,15:5,16:5,17:6,18:7},"Siege Barracks":{13:4,14:4,15:5,16:5,17:6,18:7},"Log Launcher":{13:4,14:4,15:5,16:5,17:6,18:7},"Flame Flinger":{14:4,15:5,16:5,17:6,18:7},"Battle Drill":{15:4,16:5,17:6,18:7},"Sky Wagon":{17:3,18:4},"Barbarian King":{4:10,5:10,6:10,7:10,8:20,9:30,10:40,11:50,12:65,13:75,14:85,15:90,16:95,17:100,18:110},"Archer Queen":{8:10,9:30,10:40,11:50,12:65,13:75,14:85,15:90,16:95,17:100,18:110},"Grand Warden":{11:20,12:40,13:50,14:60,15:65,16:70,17:75,18:85},"Royal Champion":{13:25,14:30,15:40,16:45,17:50,18:55},"Minion Prince":{9:10,10:20,11:30,12:40,13:50,14:60,15:70,16:80,17:90,18:95},"Dragon Duke":{15:10,16:15,17:20,18:25},"L.A.S.S.I":{14:10,15:10,16:10,17:10,18:10},"Electro Owl":{14:10,15:10,16:10,17:10,18:10},"Mighty Yak":{14:10,15:10,16:10,17:10,18:10},"Unicorn":{14:10,15:10,16:10,17:10,18:10},"Frosty":{15:10,16:10,17:10,18:10},"Diggy":{15:10,16:10,17:10,18:10},"Poison Lizard":{15:10,16:10,17:10,18:10},"Phoenix":{15:10,16:10,17:10,18:10},"Spirit Fox":{16:10,17:10,18:10},"Angry Jelly":{16:10,17:10,18:10},"Sneezy":{17:10,18:10},"Greedy Raven":{18:10},"Cannon":{1:1,2:3,3:5,4:7,5:8,6:9,7:10,8:11,9:11,10:13,11:15,12:17,13:19,14:20,15:21},"Archer Tower":{2:2,3:4,4:6,5:7,6:8,7:9,8:10,9:11,10:13,11:15,12:17,13:19,14:20,15:21},"Mortar":{3:1,4:2,5:3,6:4,7:5,8:6,9:7,10:8,11:9,12:11,13:13,14:14,15:15,16:16,17:17,18:18},"Air Defense":{4:1,5:2,6:3,7:5,8:6,9:7,10:8,11:9,12:10,13:11,14:12,15:13,16:14,17:15,18:16},"Wizard Tower":{5:2,6:3,7:4,8:6,9:7,10:8,11:9,12:11,13:13,14:14,15:15,16:16,17:17,18:18},"Air Sweeper":{6:2,7:4,8:5,9:6,10:6,11:7,12:7,13:7,14:7,15:7,16:8,17:8,18:9},"Hidden Tesla":{7:3,8:6,9:7,10:8,11:9,12:10,13:12,14:13,15:14,16:15,17:16,18:17},"Bomb Tower":{8:2,9:3,10:4,11:5,12:7,13:8,14:9,15:10,16:11,17:12,18:13},"X-Bow":{9:3,10:4,11:5,12:6,13:7,14:8,15:9,16:10,17:11,18:12},"Inferno Tower":{10:3,11:5,12:6,13:7,14:8,15:9,16:10,17:11,18:12},"Eagle Artillery":{11:2,12:3,13:4,14:5,15:6,16:7,17:8,18:9},"Scattershot":{13:2,14:3,15:4,16:5,17:6,18:7},"Spell Tower":{15:3,16:3,17:4,18:5},"Monolith":{15:2,16:3,17:4,18:5},"Ricochet Cannon":{16:2,17:3,18:4},"Multi-Archer Tower":{16:2,17:3,18:4},"Firespitter":{17:2,18:3},"Revenge Tower":{18:2},"Bomb":{3:2,4:2,5:3,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:11,16:12,17:12,18:13},"Spring Trap":{4:1,5:2,6:3,7:4,8:5,9:5,10:5,11:5,12:5,13:5,14:5,15:5,16:5,17:5,18:5},"Giant Bomb":{6:2,7:3,8:4,9:5,10:5,11:6,12:7,13:8,14:9,15:10,16:11,17:12,18:13},"Air Bomb":{5:2,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:13,17:14,18:15},"Seeking Air Mine":{7:1,8:2,9:3,10:4,11:5,12:6,13:7,14:8,15:9,16:10,17:11,18:12},"Skeleton Trap":{8:2,9:3,10:4,11:4,12:4,13:4,14:4,15:4,16:4,17:5,18:5},"Tornado Trap":{11:2,12:3,13:3,14:3,15:3,16:3,17:3,18:3},"Giga Bomb":{13:2,14:3,15:4,16:5,17:6,18:7},"Walls":{1:1,2:2,3:3,4:4,5:5,6:6,7:7,8:8,9:9,10:10,11:11,12:12,13:13,14:14,15:15,16:16,17:17,18:18},"Gold Mine":{1:1,2:2,3:4,4:6,5:8,6:10,7:11,8:12,9:12,10:12,11:13,12:14,13:14,14:15,15:15,16:16,17:16,18:17},"Elixir Collector":{1:1,2:2,3:4,4:6,5:8,6:10,7:11,8:12,9:12,10:12,11:13,12:14,13:14,14:15,15:15,16:16,17:16,18:17},"Dark Elixir Drill":{7:3,8:6,9:6,10:6,11:7,12:8,13:8,14:9,15:9,16:10,17:10,18:11},"Gold Storage":{1:1,2:2,3:3,4:4,5:5,6:6,7:7,8:8,9:9,10:11,11:12,12:13,13:14,14:15,15:16,16:17,17:18,18:19},"Elixir Storage":{1:1,2:2,3:3,4:4,5:5,6:6,7:7,8:8,9:9,10:11,11:12,12:13,13:14,14:15,15:16,16:17,17:18,18:19},"Dark Elixir Storage":{7:3,8:4,9:6,10:6,11:7,12:8,13:9,14:10,15:11,16:12,17:13,18:14},"Lightning Spell":{5:4,6:4,7:4,8:5,9:6,10:7,11:7,12:7,13:8,14:9,15:10,16:10,17:11,18:12},"Healing Spell":{6:3,7:4,8:5,9:6,10:7,11:7,12:7,13:8,14:9,15:10,16:10,17:11,18:12},"Rage Spell":{7:4,8:5,9:5,10:6,11:6,12:6,13:6,14:6,15:6,16:6,17:7,18:8},"Jump Spell":{9:2,10:3,11:3,12:3,13:4,14:4,15:5,16:5,17:6,18:6},"Freeze Spell":{10:5,11:7,12:7,13:7,14:7,15:7,16:7,17:8,18:9},"Clone Spell":{11:4,12:5,13:6,14:7,15:8,16:8,17:9,18:10},"Recall Spell":{15:3,16:4,17:5,18:6},"Revive Spell":{16:2,17:3,18:4},"Poison Spell":{8:2,9:3,10:4,11:5,12:6,13:7,14:8,15:9,16:9,17:10,18:11},"Earthquake Spell":{8:2,9:3,10:4,11:5,12:5,13:5,14:5,15:5,16:5,17:6,18:7},"Haste Spell":{9:2,10:4,11:5,12:5,13:5,14:5,15:5,16:5,17:6,18:7},"Skeleton Spell":{10:3,11:4,12:5,13:6,14:7,15:8,16:8,17:9,18:10},"Bat Spell":{11:3,12:5,13:5,14:5,15:6,16:6,17:7,18:8},"Overgrowth Spell":{12:2,13:3,14:4,15:4,16:4,17:5,18:6},"Angry Spell":{16:2,17:3,18:4}};
function getMaxLevel(name,th){const m=MAX_LEVELS_CSV[name];return m&&m[th]?m[th]:null;}
const ITEM_ORDER={};for(const cat in ICON_MAP){ITEM_ORDER[cat]=Object.keys(ICON_MAP[cat]);}
function itemSortIndex(cat,name){const order=ITEM_ORDER[cat]||[];return order.indexOf(name)>=0?order.indexOf(name):999;}
function sortByGameOrder(items){return items.slice().sort((a,b)=>itemSortIndex(a.category,a.name)-itemSortIndex(b.category,b.name));}
function iconImg(cat,name){const cats=ICON_MAP[cat]||{};let lookupName=name;if(cat==='walls'){const match=name.match(/^Wall lvl (\d+)/);if(match)lookupName='Wall lvl '+match[1];}let img=cats[lookupName];if(!img)return '<span class="ico ico-placeholder"></span>';let folder='';if(cat==='troops')folder='Troops';else if(cat==='heroes')folder='Heroes';else if(cat==='pets')folder='Pets';else if(cat==='defenses')folder='Defense';else if(cat==='traps')folder='Traps';else if(cat==='walls')folder='Walls';else if(cat==='resources')folder='Resources';else if(cat==='spells')folder='Spells';else if(cat==='equipment')folder='Equipments';const path=encodeURI(`COC ICON PACK/${folder}/${img}`);return '<img src="'+path+'" alt="'+esc(name)+'" class="ico-img"/>';}
function iconSVG(cat,name){return iconImg(cat,name);}
let state=load();
function load(){try{return JSON.parse(localStorage.getItem('coc-dash'))||{}}catch(e){return {}}}
function save(){try{localStorage.setItem('coc-dash',JSON.stringify(state))}catch(e){}}
function acctKey(){return (DATA.accounts[state.acc||0]||{}).tag||'x'}
function settings(){if(!state.settings)state.settings={goldPass:(DATA.modifiers_default||{}).gold_pass_boost_pct||0,eventCost:0,eventTime:0,builders:6,goblinB:false,goblinR:false};return state.settings;}
function plan(){state.plans=state.plans||{};const k=acctKey();if(!state.plans[k])state.plans[k]={builders:{},lab:[],pet:[],smith:[]};return state.plans[k];}
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function fmtNum(n){return n==null?'—':Number(n).toLocaleString()}
function fmtTime(sec){sec=Math.round(sec);if(sec<=0)return '—';let d=Math.floor(sec/86400),h=Math.floor(sec%86400/3600),m=Math.floor(sec%3600/60);if(d>=1)return h?d+'d '+h+'h':d+'d';if(h>=1)return m?h+'h '+m+'m':h+'h';return m+'m';}
function fmtDate(sec){let d=new Date(Date.now()+sec*1000);return d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}
function rampColor(pct,isMax){if(pct>=90)return '#2ea043';if(pct>=75)return '#57ab5a';if(pct>=61)return '#d4c14e';if(pct>=50)return '#e0912f';return '#e5534b';}
function adj(item){const s=settings();const timeCut=Math.min((s.goldPass||0)+(s.eventTime||0),95)/100;const costCut=Math.min(s.eventCost||0,95)/100;const seconds=Math.round((item.seconds||0)*(1-timeCut));const cost={};for(const k in (item.cost||{})){cost[k]=Math.round(item.cost[k]*(1-costCut));}return {seconds,cost,unknown:!!item.unknown_cost};}
function costText(cost){const order=['gold','elixir','dark_elixir','shiny_ore','glowy_ore','starry_ore'];const lab={gold:'gold',elixir:'elixir',dark_elixir:'DE',shiny_ore:'shiny',glowy_ore:'glowy',starry_ore:'starry'};let parts=[];for(const k of order)if(cost[k])parts.push(fmtNum(cost[k])+' '+lab[k]);for(const k in cost)if(!order.includes(k)&&cost[k])parts.push(fmtNum(cost[k])+' '+k);return parts.join(' · ')||'free';}
function acc(){return DATA.accounts[state.acc||0]}
function pastedVillage(){state.village=state.village||{};return state.village[acctKey()]||null;}
function defenseItemsFromVillage(v){
  if(!v||!DATA.defense_tables)return null;
  const T=DATA.defense_tables,th=+(v.town_hall||acc().town_hall||0),out=[];
  let total=0,matched=0;const misses=[];
  const norm=s=>String(s||'').trim().toLowerCase();
  const idx=table=>{const m={};for(const k in table)m[norm(k)]=table[k];return m;};
  const bIdx=idx(T.buildings),tIdx=idx(T.traps);
  const allBuildingIds=new Set(T.known_building_ids||[]);
  const maxTh=e=>{let m=0;for(const l of e.l)if(l[3]<=th&&l[0]>m)m=l[0];return m;};
  // Next level only: a builder/lab slot performs one level-up at a time, not
  // the whole remaining climb to the Town Hall cap.
  const remain=(e,cur,target)=>{if(cur>=target)return[0,0,e.r];const by={};for(const l of e.l)by[l[0]]=l;const d=by[cur+1];return d?[d[1],d[2],e.r]:[0,0,e.r];};
  const pushItem=(cat,name,lvl,lookup)=>{
    const e=lookup[norm(name)];
    if(!e){misses.push(name+' -- name not recognized');return false;}
    const target=maxTh(e);
    if(!target){misses.push(name+' -- not unlocked at Town Hall '+th+' in the bundled data (check your "town_hall" field, or this is very new content the library doesn\'t know yet)');return false;}
    const level=Math.min(+lvl||0,target);const[c,s,r]=remain(e,level,target);
    out.push({category:cat,name,level,max:target,is_max:level>=target,cost:c?{[r]:c}:{},seconds:s});
    return true;
  };
  const wallGroups={}; // level -> count, merged from an explicit v.walls array and any id-based wall entries
  const addWall=(level,count)=>{if(count>0)wallGroups[level]=(wallGroups[level]||0)+count;};

  // --- our own {name, level} schema, used as-is ---
  (v.buildings||v.defenses||[]).forEach(b=>{if(b.name==null)return;total++;if(pushItem('defenses',b.name,b.level,bIdx))matched++;});
  (v.resources||[]).forEach(b=>{if(b.name==null)return;total++;if(pushItem('resources',b.name,b.level,bIdx))matched++;});
  (v.traps||[]).forEach(t=>{if(t.name==null)return;total++;if(pushItem('traps',t.name,t.level,tIdx))matched++;});
  (v.walls||[]).forEach(g=>addWall(+g.level||0,+g.count||0));

  // --- an id-based export, e.g. {"data": 1000008, "lvl": 21, "cnt": 2} --
  // the shape some base-analysis / game-data-dump tools produce. "data" is
  // the exact internal id from the same bundled tables everything else
  // here reads from, so it translates directly with no name typing.
  (v.buildings||v.defenses||[]).forEach(b=>{
    if(b.data==null||b.name!=null)return;
    if(T.wall_id!=null&&b.data===T.wall_id){addWall(+b.lvl||0,Math.max(0,+b.cnt||1));return;}
    if(T.town_hall_id!=null&&b.data===T.town_hall_id)return; // Town Hall itself: not tracked, not a miss
    const info=(T.building_ids||{})[b.data];
    if(!info){
      // a real building we just don't track (Army Camp, Laboratory, Clan Castle, ...): not counted at all,
      // as opposed to an id we've genuinely never heard of, which is worth flagging
      if(!allBuildingIds.has(b.data)){total++;misses.push('building id '+b.data+' -- not recognized');}
      return;
    }
    total++;
    const count=Math.max(1,+b.cnt||1);let ok=0;
    for(let i=0;i<count;i++)if(pushItem(info.c,info.n,b.lvl,bIdx))ok++;
    if(ok>0)matched++;
  });
  (v.traps||[]).forEach(t=>{
    if(t.data==null||t.name!=null)return;
    total++;
    const name=(T.trap_ids||{})[t.data];
    if(!name){misses.push('trap id '+t.data+' -- not recognized');return;}
    const count=Math.max(1,+t.cnt||1);let ok=0;
    for(let i=0;i<count;i++)if(pushItem('traps',name,t.lvl,tIdx))ok++;
    if(ok>0)matched++;
  });

  const we=T.wall;
  Object.entries(wallGroups).forEach(([levelStr,count])=>{
    const level=+levelStr;total++;
    const target=we?maxTh(we):0;
    if(!we||!we.l.length||!target){misses.push('Wall lvl '+level+' -- not unlocked at Town Hall '+th);return;}
    matched++;const[c]=remain(we,level,target);
    out.push({category:'walls',name:'Wall lvl '+level+' x'+count,level,max:target,is_max:level>=target,cost:(c*count)?{gold:c*count}:{},seconds:0,count});
  });

  out.__match={total,matched,misses};
  return out;
}
function IT(){const base=acc().items||[];const v=pastedVillage();if(!v)return base;const def=defenseItemsFromVillage(v);if(!def||!def.length)return base;const off=base.filter(i=>!['defenses','walls','traps','resources'].includes(i.category));return off.concat(def);}
function COMP(){const cur={},mx={};for(const i of IT()){const w=i.count||1;cur[i.category]=(cur[i.category]||0)+i.level*w;mx[i.category]=(mx[i.category]||0)+i.max*w;}const out={};for(const k in cur)out[k]=mx[k]?Math.round(1000*cur[k]/mx[k])/10:100;return out;}
function haveDefenses(){return !!pastedVillage()||!!acc().village_present;}
function githubVillage(){
  if(!DATA.repo)return null;
  const a=acc(),tag=(a.tag||'').replace('#',''),branch=DATA.branch||'master';
  // village_present is only as fresh as the last build, and it's monotonic
  // (the file never gets deleted once created) -- so trusting a "true" is
  // always safe, but trusting a stale "false" isn't: it can point a
  // one-tap "create new file" link at a path that already exists on
  // GitHub by now (exactly the "a file with the same name already exists"
  // error), if you'd already added it since this page was last built.
  // So only the true case gets the direct one-tap edit link; otherwise
  // this sends you to the account's folder -- always valid, since track.py
  // writes other files there on every run regardless of village.json --
  // where you can see for yourself whether it's there yet.
  if(a.village_present){
    return {url:'https://github.com/'+DATA.repo+'/edit/'+branch+'/data/accounts/'+tag+'/village.json',
            label:'✎ Edit on GitHub (all devices)'};
  }
  return {url:'https://github.com/'+DATA.repo+'/tree/'+branch+'/data/accounts/'+tag,
          label:'✎ Add on GitHub (all devices)'};
}
function remaining(){return IT().filter(i=>!i.is_max)}
function overallPct(){let c=0,m=0;for(const i of IT()){const w=i.count||1;c+=i.level*w;m+=i.max*w;}return m?Math.round(100*c/m):0;}
function ring(pct,color){const r=68,circ=2*Math.PI*r,off=circ*(1-pct/100);return '<svg width="160" height="160" viewBox="0 0 160 160"><circle cx="80" cy="80" r="'+r+'" fill="none" stroke="#21262d" stroke-width="12"/><circle cx="80" cy="80" r="'+r+'" fill="none" stroke="'+color+'" stroke-width="12" stroke-linecap="round" stroke-dasharray="'+circ+'" stroke-dashoffset="'+off+'" transform="rotate(-90 80 80)"/></svg>';}
function renderOverview(){
  const a=acc(),comp=COMP(),pct=overallPct();const rem=remaining().length;
  let dc=0,dm=0;for(const i of IT()){if(!DEFENSE.includes(i.category))continue;const w=i.count||1;dc+=i.level*w;dm+=i.max*w;}
  const defScore=dm?Math.round(100*dc/dm):null;
  const order=['heroes','troops','spells','pets','equipment','defenses','walls','traps','resources'];
  const health=order.filter(k=>k in comp).map(k=>{const p=comp[k];const col=rampColor(p,p>=100);return '<div class="hrow"><span class="hlabel">'+k+'</span><span class="htrack"><span class="hfill" style="width:'+p+'%;background:'+col+'"></span></span><span class="hpct">'+p+'%</span></div>';}).join('');
  const badge=pastedVillage()?'<span class="badge ok">● Accurate · village pasted (this device)</span>':(a.village_present?'<span class="badge ok">● Accurate · village.json imported (all devices)</span>':'<span class="badge warn">● Offense only · add your village for defenses</span>');
  const gh=githubVillage();
  const ghBtn=gh?(' <a class="af" href="'+gh.url+'" target="_blank" rel="noopener">'+gh.label+'</a>'):'';
  const importBtn='<div style="margin-top:12px">'+ghBtn+' <button class="af" onclick="openVillageModal()">'+(pastedVillage()?'↻ Update paste (this device only)':'＋ Paste here instead (this device only)')+'</button>'+(pastedVillage()?' <button class="af clear" onclick="clearVillage()">Remove pasted village</button>':'')+'</div>';
  const wars=(a.wars||[]).slice().sort((x,y)=>(y.date_seen||'').localeCompare(x.date_seen||'')).slice(0,8);
  const log=wars.length?wars.map(w=>{const st=parseInt(w.stars||0);const stars='★'.repeat(st)+'☆'.repeat(3-st);return '<div class="lrow"><span class="stars">'+stars+'</span><span class="mono">'+Math.round(w.destruction||0)+'%</span><span class="muted">vs TH'+esc(w.defender_th)+'</span><span class="leaguetag">'+esc(w.war_type)+'</span></div>';}).join(''):'<div class="faint">No war attacks recorded yet. They log automatically when you\'re in a clan war.</div>';
  const rk=a.ranked||{};
  const rkSeason=(label,s)=>s?('<div class="rline"><span class="k muted">'+label+'</span><span class="v mono">'+fmtNum(s.trophies)+' &nbsp;<span class="faint">rank '+(s.rank==null?'—':fmtNum(s.rank))+'</span></span></div>'):'';
  const rankedCard=rk.in_legend_league
   ?('<div class="card rk"><h3>Ranked</h3>'
     +'<div class="rline"><span class="k muted">Current trophies</span><span class="v mono">'+fmtNum(rk.trophies)+'</span></div>'
     +rkSeason('This season',rk.current_season)+rkSeason('Previous season',rk.previous_season)+rkSeason('Best season',rk.best_season)
     +'<div class="note">Supercell\'s public API only exposes season-level Ranked/Legend totals (trophies + rank), never a per-attack log — so that\'s what\'s shown here, not a fabricated hit-by-hit feed.</div></div>')
   :('<div class="card rk"><h3>Ranked</h3><div class="faint">Not in the Ranked (Legend) league yet — current trophies: '+fmtNum(rk.trophies)+', best: '+fmtNum(rk.best_trophies)+'.</div>'
     +'<div class="note">Supercell\'s public API has no per-attack Ranked battle log; only season aggregates once you reach Ranked/Legend.</div></div>');
  document.getElementById('page-overview').innerHTML=
   '<div class="card"><h3>TH Completion</h3><div class="ovtop"><div><div class="ring">'+ring(pct,'#d9a520')+'<div class="ringpct"><b>'+pct+'%</b><span>of TH'+esc(a.town_hall)+'</span></div></div></div>'
   +'<div class="ovstats"><div class="line"><span class="k">Remaining upgrades</span><span class="v">'+rem+'</span></div>'
   +'<div class="line"><span class="k">Offense to max</span><span class="v">'+a.offense_completion_pct+'%</span></div>'
   +'<div class="line"><span class="k">Defense score</span><span class="v">'+(defScore==null?'—':defScore+'%')+'</span></div>'
   +'<div class="line"><span class="k">Rush</span><span class="v">'+((a.rush||{}).band||'—')+'</span></div>'
   +'<div style="margin-top:14px">'+badge+'</div>'+importBtn+'</div></div></div>'
   +'<div class="card health"><h3>Village Health</h3>'+(health||'<div class="faint">No data.</div>')+'</div>'
   +'<div class="card"><h3>Key stats</h3><div class="cards6">'
   +'<div class="stat"><b>'+esc(a.trophies==null?'—':a.trophies)+'</b><span>trophies</span></div>'
   +'<div class="stat"><b>'+esc(a.war_stars==null?'—':a.war_stars)+'</b><span>war stars</span></div>'
   +'<div class="stat"><b>'+esc(a.attack_wins==null?'—':a.attack_wins)+'</b><span>attack wins</span></div>'
   +'<div class="stat"><b>'+esc(a.defense_wins==null?'—':a.defense_wins)+'</b><span>defense wins</span></div></div></div>'
   +rankedCard
   +'<div class="card log"><h3>War Log <span class="faint" style="text-transform:none;font-weight:400">— clan wars &amp; CWL</span></h3>'+log+'</div>';
}
function renderTracker(){
  const ITEMS=IT();const cats=[];for(const c of ['heroes','troops','spells','pets','equipment','defenses','walls','traps','resources'])if(ITEMS.some(i=>i.category===c))cats.push(c);
  if(!state.trackCat||!cats.includes(state.trackCat))state.trackCat=cats[0];
  const pills=cats.map(c=>'<button class="pill '+(c===state.trackCat?'active':'')+'" onclick="setTrackCat(\''+c+'\')">'+c+'</button>').join('');
  const items=ITEMS.filter(i=>i.category===state.trackCat);
  const grid=items.map(i=>{const pct=i.max?Math.round(100*i.level/i.max):0;const col=rampColor(pct,i.is_max);
    return '<div class="tile '+(i.is_max?'max':'')+'">'+(i.is_max?'<span class="maxbadge">MAX</span>':(i.unknown_cost?'<span class="maxbadge" style="background:var(--muted);color:#fff">NO DATA</span>':''))
      +'<div class="ic" style="background:'+CAT_COLOR[i.category]+'22;color:'+CAT_COLOR[i.category]+'">'+iconSVG(i.category,i.name)+'</div>'
      +'<div class="tname">'+esc(i.name)+'</div><div class="tlv">Lv '+i.level+' / '+i.max+'</div>'
      +'<div class="tbar"><div class="tfill" style="width:'+pct+'%;background:'+col+'"></div></div></div>';}).join('');
  document.getElementById('page-tracker').innerHTML='<div class="pills">'+pills+'</div><div class="grid">'+(grid||'<div class="faint">Nothing here.</div>')+'</div>';
}
function setTrackCat(c){state.trackCat=c;save();renderTracker();}
function renderPlanner(){
  const s=settings();
  const gp=['0','10','15','20'].map(o=>'<button class="'+(s.goldPass==o?'on':'')+'" onclick="setNum(\'goldPass\','+o+')">'+o+'%</button>').join('');
  const settingsHtml='<div class="card"><h3>Boosts &amp; builders <span class="faint" style="text-transform:none;font-weight:400">— set to match your game; the API can\'t detect these</span></h3>'
   +'<div class="settings"><div class="field"><label>Gold Pass build-time boost</label><div class="seg">'+gp+'</div></div>'
   +'<div class="field"><label>Event cost discount %</label><input type="number" min="0" max="95" value="'+s.eventCost+'" onchange="setNum(\'eventCost\',this.value)"></div>'
   +'<div class="field"><label>Event time discount %</label><input type="number" min="0" max="95" value="'+s.eventTime+'" onchange="setNum(\'eventTime\',this.value)"></div>'
   +'<div class="field"><label>Builders you have</label><input type="number" min="1" max="6" value="'+s.builders+'" onchange="setNum(\'builders\',this.value)"></div>'
   +'<div class="field"><label>Goblin builder (event)</label><div class="toggle '+(s.goblinB?'on':'')+'" onclick="setTog(\'goblinB\')"><span class="sw"></span><span class="muted">+1 builder</span></div></div>'
   +'<div class="field"><label>Goblin researcher (event)</label><div class="toggle '+(s.goblinR?'on':'')+'" onclick="setTog(\'goblinR\')"><span class="sw"></span><span class="muted">lab runs two</span></div></div>'
   +'</div><div class="note">Nothing to save. These recompute everything live and stick on this device.</div></div>';
  const sortRem=(arr)=>arr.slice().sort((a,b)=>{const au=!!a.unknown_cost,bu=!!b.unknown_cost;if(au!==bu)return au?1:-1;return (b.max-b.level)-(a.max-a.level);});
  const prioBlock=(title,cats,n)=>{const items=sortRem(remaining().filter(i=>cats.includes(i.category))).slice(0,n);
    const rows=items.map(i=>{const j=adj(i);const meta=j.unknown?'<span class="faint">no upgrade data yet</span>':(costText(j.cost)+'<br>'+fmtTime(j.seconds));return '<div class="pitem"><span class="pi-name"><span class="pi-ic" style="color:'+CAT_COLOR[i.category]+'">'+iconSVG(i.category,i.name)+'</span>'+esc(i.name)+' <span class="lv">'+i.level+'&rarr;'+i.max+'</span></span><span class="pi-meta">'+meta+'</span><button class="addbtn" onclick="openQueueModal(\''+esc(i.category)+'\',\''+esc(i.name).replace(/'/g,"\\'")+'\')">+ queue</button></div>';}).join('');
    return '<div class="prio card"><h4>'+title+' <span class="faint">top '+n+'</span></h4>'+(rows||'<div class="faint">All maxed here.</div>')+'</div>';};
  const p=plan(),bc=(s.builders||6)+(s.goblinB?1:0);
  const findItem=(nm)=>IT().find(i=>i.name===nm);
  const laneTime=(ids)=>ids.reduce((t,nm)=>{const it=findItem(nm);return t+(it?adj(it).seconds:0)},0);
  const laneBox=(title,key,items,parallel)=>{const t=laneTime(items);const eff=parallel&&parallel>1?t/parallel:t;
    const rows=items.length?items.map(nm=>{const it=findItem(nm);const timeLabel=it&&it.unknown_cost?'no data':fmtTime(it?adj(it).seconds:0);return '<div class="qitem"><span>'+esc(nm)+' <span class="faint mono">'+timeLabel+'</span></span><span class="x" onclick="removeFromLane(\''+key+'\',\''+esc(nm).replace(/'/g,"\\'")+'\')">✕</span></div>';}).join(''):'<div class="empty">Empty — add from the lists above</div>';
    return '<div class="lane" data-lane="'+key+'"><h5><span>'+title+'</span><span class="faint mono">'+fmtTime(eff)+'</span></h5><div class="sum">'+items.length+' item(s)'+(eff?' · done '+fmtDate(eff):'')+'</div>'+rows+'</div>';};
  let builderLanes='';for(let b=1;b<=bc;b++){const ids=(p.builders&&p.builders[b])||[];builderLanes+=laneBox('Builder '+b+(b>(s.builders||6)?' (goblin)':''),'builders:'+b,ids,1);}
  const lanesHtml='<div class="lanes">'+builderLanes
   +laneBox('Laboratory'+(s.goblinR?' (goblin ×2)':''),'lab',p.lab||[],s.goblinR?2:1)
   +laneBox('Pet House','pet',p.pet||[],1)+laneBox('Blacksmith','smith',p.smith||[],1)+'</div>';
  document.getElementById('page-planner').innerHTML=settingsHtml
   +'<div class="card"><h3>Priority upgrades</h3><div class="autofill"><button class="af" onclick="autofill(\'fast\')">⚡ Auto-fill (fastest)</button><button class="af" onclick="autofill(\'balanced\')">⚖️ Auto-fill (balanced)</button><button class="af clear" onclick="clearPlan()">🗑 Clear</button></div>'
   +'<div class="pcols">'+prioBlock('Defense',DEFENSE,10)+prioBlock('Offense (heroes)',['heroes'],10)+'</div>'
   +'<div class="pcols" style="margin-top:14px">'+prioBlock('Lab (troops &amp; spells)',['troops','spells'],5)+prioBlock('Pets',['pets'],5)+'</div>'
   +'<div class="pcols" style="margin-top:14px">'+prioBlock('Equipment',['equipment'],5)+prioBlock('Resources',['resources'],5)+'</div></div>'
   +'<div class="card"><h3>Your plan</h3>'+lanesHtml+'<div class="note">Builder count and goblin helpers are yours to set above — the game never exposes them. Finish dates assume each lane runs start to finish from now.</div></div>';
}
function laneForItem(cat){return LANE_OF[cat]||'builders';}
let qPending=null;
function openQueueModal(cat,name){
  qPending={cat,name};
  const lane=laneForItem(cat);
  document.getElementById('qmodal-title').textContent=name;
  let body='';
  if(lane==='builders'){
    document.getElementById('qmodal-sub').textContent='Choose which builder queues this upgrade.';
    const s=settings(),bc=(s.builders||6)+(s.goblinB?1:0),p=plan();
    const findItem=(nm)=>IT().find(i=>i.name===nm);
    for(let b=1;b<=bc;b++){
      const ids=(p.builders&&p.builders[b])||[];
      const t=ids.reduce((s2,nm)=>{const it=findItem(nm);return s2+(it?adj(it).seconds:0)},0);
      body+='<div class="qpick" onclick="confirmQueue('+b+')"><span>Builder '+b+(b>(s.builders||6)?' (goblin)':'')+'</span><span class="meta">'+(ids.length?ids.length+' queued · '+fmtTime(t):'free')+'</span></div>';
    }
  }else{
    const label=LANE_LABEL[lane]||lane;
    document.getElementById('qmodal-sub').textContent='This upgrades at your '+label+'.';
    body='<div class="qpick" onclick="confirmQueue()"><span>Add to '+label+' queue</span></div>';
  }
  document.getElementById('qmodal-body').innerHTML=body;
  document.getElementById('qmodal').style.display='flex';
}
function closeQueueModal(){qPending=null;document.getElementById('qmodal').style.display='none';}
function confirmQueue(builderIdx){
  if(!qPending)return;
  const{cat,name}=qPending,lane=laneForItem(cat),p=plan();
  if(lane==='builders'){p.builders=p.builders||{};for(const b in p.builders)p.builders[b]=(p.builders[b]||[]).filter(n=>n!==name);p.builders[builderIdx]=p.builders[builderIdx]||[];p.builders[builderIdx].push(name);}
  else{p[lane]=p[lane]||[];if(!p[lane].includes(name))p[lane].push(name);}
  save();closeQueueModal();renderPlanner();
  flashLane(lane==='builders'?('builders:'+builderIdx):lane);
}
function flashLane(key){setTimeout(()=>{const el=document.querySelector('[data-lane="'+key+'"]');if(!el)return;el.scrollIntoView({block:'center'});el.classList.add('flash');setTimeout(()=>el.classList.remove('flash'),1400);},60);}
function removeFromLane(key,name){const p=plan();if(key.indexOf('builders:')===0){const b=key.split(':')[1];p.builders[b]=(p.builders[b]||[]).filter(n=>n!==name);}else{p[key]=(p[key]||[]).filter(n=>n!==name);}save();renderPlanner();}
function clearPlan(){const k=acctKey();state.plans[k]={builders:{},lab:[],pet:[],smith:[]};save();renderPlanner();}
function autofill(mode){const k=acctKey();state.plans=state.plans||{};state.plans[k]={builders:{},lab:[],pet:[],smith:[]};const p=state.plans[k];const s=settings();const bc=(s.builders||6)+(s.goblinB?1:0);
  const sortRem=(arr)=>arr.slice().sort((a,b)=>{const au=!!a.unknown_cost,bu=!!b.unknown_cost;if(au!==bu)return au?1:-1;return mode==='fast'?adj(a).seconds-adj(b).seconds:(b.max-b.level)-(a.max-a.level);});
  const build=sortRem(remaining().filter(i=>BUILDER_CATS.includes(i.category))).slice(0,bc*4);
  p.builders={};const t=Array(bc+1).fill(0);for(const it of build){let best=1;for(let b=2;b<=bc;b++)if(t[b]<t[best])best=b;p.builders[best]=p.builders[best]||[];p.builders[best].push(it.name);t[best]+=adj(it).seconds;}
  p.lab=sortRem(remaining().filter(i=>['troops','spells'].includes(i.category))).slice(0,6).map(i=>i.name);
  p.pet=sortRem(remaining().filter(i=>i.category==='pets')).slice(0,4).map(i=>i.name);
  p.smith=sortRem(remaining().filter(i=>i.category==='equipment')).slice(0,4).map(i=>i.name);
  save();renderPlanner();}
function setNum(k,v){settings()[k]=Number(v);save();renderPlanner();}function setTog(k){settings()[k]=!settings()[k];save();renderPlanner();}
function openVillageModal(){var m=document.getElementById('vmodal');var t=document.getElementById('vjson');var cur=pastedVillage();t.value=cur?JSON.stringify(cur,null,2):'';document.getElementById('verr').textContent='';m.style.display='flex';}
function closeVillageModal(){document.getElementById('vmodal').style.display='none';}
function saveVillage(){
  var t=document.getElementById('vjson').value.trim();var err=document.getElementById('verr');
  if(!t){err.textContent='Paste your village JSON first.';return;}
  var v;try{v=JSON.parse(t);}catch(e){err.textContent="That isn't valid JSON: "+e.message;return;}
  if(typeof v!=='object'||v===null||!(Array.isArray(v.buildings)||Array.isArray(v.defenses)||Array.isArray(v.walls)||Array.isArray(v.traps)||Array.isArray(v.resources))){
    err.textContent="Parsed OK, but I don't see buildings, resources, walls or traps. Check the format below.";return;
  }
  const preview=defenseItemsFromVillage(v);
  const match=(preview&&preview.__match)||{total:0,matched:0,misses:[]};
  state.village=state.village||{};state.village[acctKey()]=v;save();closeVillageModal();renderAll();showPage('overview');
  if(match.total>0&&match.matched<match.total){
    const missed=match.total-match.matched;
    const list=(match.misses||[]).map(m=>'  • '+m).join('\n');
    setTimeout(()=>alert('Saved, but '+missed+' of '+match.total+' name(s) in your JSON didn\'t match'+(match.matched?' ('+match.matched+' matched fine):':'  :')+'\n\n'+list),150);
  }
}
function clearVillage(){state.village=state.village||{};delete state.village[acctKey()];save();renderAll();}
function showPage(p){state.page=p;save();document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active',b.dataset.p===p));document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id==='page-'+p));if(p==='overview')renderOverview();if(p==='tracker')renderTracker();if(p==='planner')renderPlanner();}
function setAcc(i){state.acc=i;save();document.querySelectorAll('.acct').forEach((b,idx)=>b.classList.toggle('active',idx===i));renderAll();}
function renderAll(){renderOverview();renderTracker();renderPlanner();}
function init(){const accts=document.getElementById('accts');if(DATA.accounts.length>1){accts.innerHTML=DATA.accounts.map((a,i)=>'<button class="acct '+(i===0?'active':'')+'" onclick="setAcc('+i+')">'+esc(a.name||a.tag)+'</button>').join('');}state.acc=state.acc||0;if(state.acc>=DATA.accounts.length)state.acc=0;renderAll();showPage(state.page||'overview');}
if(DATA.accounts.length){init();}else{document.querySelector('.wrap').innerHTML+='<div class="card"><div class="muted">No data yet. Run the tracker once and reopen this file.</div></div>';}
"""


def render(data_dir: Path, out_path: Path) -> bool:
    data = _read_json(data_dir / "dashboard_data.json") or {"accounts": [], "modifiers_default": {}}
    updated = data.get("captured_at") or datetime.now(timezone.utc).isoformat()
    try:
        updated = datetime.fromisoformat(updated.replace("Z", "+00:00")).astimezone(IST).strftime("%d %b %Y, %H:%M IST")
    except Exception:
        pass
    doc = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Village console</title><style>" + STYLE + "</style></head><body><div class=\"wrap\">"
        "<div class=\"topbar\"><h1>Village console</h1><span class=\"sub\">updated " + updated + "</span></div>"
        "<div class=\"nav\">"
        "<button class=\"navbtn active\" data-p=\"overview\" onclick=\"showPage('overview')\">\U0001F4CA Overview</button>"
        "<button class=\"navbtn\" data-p=\"tracker\" onclick=\"showPage('tracker')\">\U0001F4CC Tracker</button>"
        "<button class=\"navbtn\" data-p=\"planner\" onclick=\"showPage('planner')\">\U0001F3D7 Planner</button>"
        "</div><div class=\"accts\" id=\"accts\"></div>"
        "<div id=\"page-overview\" class=\"page active\"></div>"
        "<div id=\"page-tracker\" class=\"page\"></div>"
        "<div id=\"page-planner\" class=\"page\"></div>"
        "<div id=\"vmodal\" class=\"modal\"><div class=\"modalbox\">"
        "<h3 style=\"color:var(--gold)\">Paste your village JSON</h3>"
        "<p class=\"muted\" style=\"font-size:12px;margin:4px 0 0\">Your current defense, resource-building, trap and wall levels. <b>Saved in this browser only</b> &mdash; it won't show up on your other devices. For that, use the \"Add/Edit on GitHub\" button on the Overview page instead, which commits the file to the repo so every device picks it up. Names must match the game exactly (case doesn't matter) &mdash; \"buildings\" or \"defenses\" both work as the key for defensive buildings. A raw account export with numeric building ids (e.g. from a base-analysis tool) works too, translated automatically.</p>"
        "<textarea id=\"vjson\" spellcheck=\"false\" placeholder='{ \"town_hall\": 17, \"buildings\": [ {\"name\":\"Cannon\",\"level\":21} ], \"resources\": [ {\"name\":\"Gold Mine\",\"level\":17} ], \"traps\": [ {\"name\":\"Bomb\",\"level\":12} ], \"walls\": [ {\"level\":17,\"count\":250} ] }'></textarea>"
        "<div id=\"verr\" class=\"verr\"></div>"
        "<div class=\"modalbtns\"><button class=\"af\" onclick=\"saveVillage()\">Save</button><button class=\"af\" onclick=\"closeVillageModal()\">Cancel</button></div>"
        "</div></div>"
        "<div id=\"qmodal\" class=\"modal\"><div class=\"modalbox\" style=\"max-width:420px\">"
        "<h3 id=\"qmodal-title\" style=\"color:var(--gold)\">Queue upgrade</h3>"
        "<p id=\"qmodal-sub\" class=\"qsub\"></p>"
        "<div id=\"qmodal-body\"></div>"
        "<div class=\"modalbtns\"><button class=\"af\" onclick=\"closeQueueModal()\">Cancel</button></div>"
        "</div></div>"
        "<div class=\"note\" style=\"text-align:center;margin-top:18px\">This material is unofficial and is not endorsed by Supercell. For more information see Supercell's <a href=\"https://www.supercell.com/fan-content-policy\" target=\"_blank\" rel=\"noopener\">Fan Content Policy</a>.</div>"
        "</div><script>const DATA=" + json.dumps(data) + ";</script><script>" + APP_JS + "</script></body></html>"
    )
    out_path.write_text(doc)
    return True
