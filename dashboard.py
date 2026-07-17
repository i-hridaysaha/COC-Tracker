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
from datetime import datetime, timezone
from pathlib import Path


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
.af{background:var(--raised);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:9px 14px;font-size:13px;cursor:pointer;font-weight:600}
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
.ic .ico{width:30px;height:30px}
.pi-name{display:flex;align-items:center;gap:7px}
.pi-ic{width:16px;height:16px;flex:none;opacity:.9}
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

/* Original, offline icon set -- not game art (none ships with the data
   library and embedding Supercell's would violate the offline/no-CDN rule
   and copyright), just simple archetype glyphs so items read at a glance. */
const ICONS={
 crown:'<path d="M3 9l4 3 5-7 5 7 4-3-2 10H5L3 9z" fill="currentColor"/>',
 sword:'<path d="M4 20L20 4l-2.2-2.2L1.8 17.8z" fill="currentColor"/><circle cx="4" cy="20" r="1.8" fill="currentColor"/>',
 bow:'<path d="M6 3c6 3 6 15 0 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M6 3.5v17" stroke="currentColor" stroke-width="1.2"/><path d="M11 12h8m0 0l-3-2.4m3 2.4l-3 2.4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
 staff:'<circle cx="12" cy="4.2" r="2.2" fill="currentColor"/><path d="M12 6.4V21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M8 12.5l8-2M8 16.5l8-2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
 wing:'<path d="M2 13c4-7 10-9 14-9-2 3-2 6 0 8-4 2-8 2-11 1 1 1 3 2 5 2-3 2-6 1-8-2z" fill="currentColor"/>',
 bomb:'<circle cx="11" cy="14" r="7" fill="currentColor"/><path d="M14.5 8.2l1.8-2.7 1.8.9-1.3 2.4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/><circle cx="17.4" cy="4.6" r="1.3" fill="currentColor"/>',
 pickaxe:'<path d="M4.5 19.5l6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M8 15c-3-5-2-10 3-13 3 4 3 9-1 13z" fill="currentColor"/>',
 potion:'<path d="M10 2h4v3.4l3.3 7.4a4 4 0 01-3.7 5.6h-3.2a4 4 0 01-3.7-5.6L10 5.4V2z" fill="currentColor"/>',
 paw:'<circle cx="7" cy="8" r="2" fill="currentColor"/><circle cx="12" cy="6" r="2" fill="currentColor"/><circle cx="17" cy="8" r="2" fill="currentColor"/><circle cx="19" cy="13" r="2" fill="currentColor"/><path d="M12 12c4 0 6.2 3 5.6 6.3-3 1-4.1-1-5.6-1s-2.7 2-5.6 1C5.8 15 8 12 12 12z" fill="currentColor"/>',
 gem:'<path d="M6 3h12l4 6-10 12L2 9z" fill="currentColor"/><path d="M2 9h20M9.3 3l2.7 6-2.7 12M14.7 3l-2.7 6 2.7 12" stroke="var(--surface)" stroke-width="0.7" fill="none"/>',
 tower:'<path d="M6 21V10l2-2V5h2V3h4v2h2v3l2 2v11z" fill="currentColor"/><rect x="9.3" y="13.2" width="5.4" height="7.8" fill="var(--surface)"/>',
 spike:'<path d="M12 2l3 8h6l-9 12-3-8H3z" fill="currentColor"/>',
 brick:'<g fill="currentColor"><rect x="2" y="4" width="9" height="5" rx=".6"/><rect x="13" y="4" width="9" height="5" rx=".6"/><rect x="2" y="10.5" width="4" height="5" rx=".6"/><rect x="7.5" y="10.5" width="9" height="5" rx=".6"/><rect x="18" y="10.5" width="4" height="5" rx=".6"/><rect x="2" y="17" width="9" height="5" rx=".6"/><rect x="13" y="17" width="9" height="5" rx=".6"/></g>',
 coin:'<circle cx="12" cy="12" r="9.5" fill="currentColor"/><path d="M9.3 9.7c0-1.6 1.4-2.7 2.9-2.7 1.1 0 2 .4 2.5 1.1l-1 .9c-.3-.4-.8-.6-1.4-.6-.8 0-1.5.5-1.5 1.2 0 .6.5.9 1.7 1.2 1.9.5 2.5 1.3 2.5 2.5 0 1.5-1.3 2.6-3 2.6-1.2 0-2.2-.4-2.8-1.2l1-.9c.4.5 1.1.8 1.8.8.8 0 1.5-.4 1.5-1.1 0-.6-.4-1-1.8-1.4-1.7-.5-2.4-1.2-2.4-2.4z" fill="var(--surface)"/>',
 golem:'<path d="M12 3l2 3-1 2h-2l-1-2 2-3z" fill="currentColor"/><path d="M7 22v-7c0-2.8 2.2-5 5-5s5 2.2 5 5v7z" fill="currentColor"/><circle cx="9.7" cy="13.2" r="1.1" fill="var(--surface)"/><circle cx="14.3" cy="13.2" r="1.1" fill="var(--surface)"/>',
 giant:'<circle cx="12" cy="6" r="3.4" fill="currentColor"/><path d="M6 22v-6c0-3.3 2.7-6 6-6s6 2.7 6 6v6z" fill="currentColor"/><path d="M17.5 9l3-3 1.3 1.3-3 3z" fill="currentColor"/>',
 skeleton:'<circle cx="12" cy="8" r="5" fill="currentColor"/><circle cx="9.8" cy="7.5" r="1.3" fill="var(--surface)"/><circle cx="14.2" cy="7.5" r="1.3" fill="var(--surface)"/><path d="M10.3 10.2h3.4l-.6 2h-2.2z" fill="var(--surface)"/><path d="M5 22l6-7.3 6 7.3M6.7 22l4.6-8M17.3 22l-4.6-8" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>',
 mount:'<path d="M2.5 15.5c.8-3.3 3.8-5.7 7.2-5.7 1 0 1.9.2 2.7.6.9-1 2.2-1.7 3.7-1.7 3 0 5.4 2.4 5.4 5.4 0 .6-.1 1.2-.3 1.7.7.4 1.1 1.1 1.1 2 0 1.3-1.1 2.4-2.4 2.4H7.4c-2.9 0-5.3-2.3-5.3-5.2 0-.2 0-.4.4-.5z" fill="currentColor"/><circle cx="17.5" cy="12.7" r="1" fill="var(--surface)"/>',
 lightning:'<path d="M13 2L4 14h6l-2 8 10-13h-6z" fill="currentColor"/>',
 snowflake:'<path d="M12 1.5v21M3.9 6.25l16.2 11.5M20.1 6.25L3.9 17.75" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M12 1.5l-1.8 2.2 1.8 1.3 1.8-1.3zM12 22.5l-1.8-2.2 1.8-1.3 1.8 1.3z" fill="currentColor"/>',
 mask:'<path d="M4 9c0-3.9 3.6-7 8-7s8 3.1 8 7-3.6 7-8 7-8-3.1-8-7z" fill="currentColor"/><circle cx="9" cy="9" r="1.4" fill="var(--surface)"/><circle cx="15" cy="9" r="1.4" fill="var(--surface)"/><path d="M9 13.2c1 .9 5 .9 6 0" stroke="var(--surface)" stroke-width="1.1" fill="none" stroke-linecap="round"/><path d="M6 21c1.4-2 3.6-3 6-3s4.6 1 6 3" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/>',
 shield:'<path d="M12 2l8 3v6c0 5.2-3.4 8.9-8 11-4.6-2.1-8-5.8-8-11V5z" fill="currentColor"/><path d="M9 12l2 2 4-4" stroke="var(--surface)" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
 axe:'<path d="M14 2c3 0 6 2.5 6 6 0 2.6-1.6 4.4-3.4 5.2L14 11z" fill="currentColor"/><path d="M13.5 10.5L4 20l-1-1 9.5-9.5z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/>'
};
const CAT_ICON={heroes:'crown',troops:'sword',spells:'potion',pets:'paw',equipment:'gem',defenses:'tower',traps:'spike',walls:'brick',resources:'coin'};
// Ordered first-match-wins keyword table so named units read closer to what
// they actually are, instead of every troop sharing one generic 'sword'.
const NAME_ICON=[
 [/bomb|wall breaker/i,'bomb'],
 [/dragon|balloon|minion\b|lava hound|owl|phoenix|flying fortress/i,'wing'],
 [/wizard|witch|warden|druid|apprentice|healer/i,'staff'],
 [/archer|queen/i,'bow'],
 [/valkyrie/i,'axe'],
 [/golem/i,'golem'],
 [/skeleton/i,'skeleton'],
 [/hog rider/i,'mount'],
 [/miner|root rider/i,'pickaxe'],
 [/electro|lightning/i,'lightning'],
 [/\bice\b|frost|freeze/i,'snowflake'],
 [/headhunter|invisib/i,'mask'],
 [/shield|royal champion/i,'shield'],
 [/giant\b/i,'giant'],
 [/yeti/i,'paw'],
];
function iconKeyFor(cat,name){for(const[re,key]of NAME_ICON)if(re.test(name))return key;return CAT_ICON[cat]||'coin';}
function iconSVG(cat,name){const key=iconKeyFor(cat,name);return '<svg viewBox="0 0 24 24" class="ico">'+(ICONS[key]||ICONS.coin)+'</svg>';}
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
function adj(item){const s=settings();const timeCut=Math.min((s.goldPass||0)+(s.eventTime||0),95)/100;const costCut=Math.min(s.eventCost||0,95)/100;const seconds=Math.round((item.seconds||0)*(1-timeCut));const cost={};for(const k in (item.cost||{})){cost[k]=Math.round(item.cost[k]*(1-costCut));}return {seconds,cost};}
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
  const maxTh=e=>{let m=0;for(const l of e.l)if(l[3]<=th&&l[0]>m)m=l[0];return m;};
  // Next level only: a builder/lab slot performs one level-up at a time, not
  // the whole remaining climb to the Town Hall cap.
  const remain=(e,cur,target)=>{if(cur>=target)return[0,0,e.r];const by={};for(const l of e.l)by[l[0]]=l;const d=by[cur+1];return d?[d[1],d[2],e.r]:[0,0,e.r];};
  const addFrom=(list,cat,lookup)=>{(list||[]).forEach(b=>{total++;const e=lookup[norm(b.name)];
    if(!e){misses.push((b.name||'(no name)')+' -- name not recognized');return;}
    const target=maxTh(e);
    if(!target){misses.push((b.name||'(no name)')+' -- not unlocked at Town Hall '+th+' in the bundled data (check your "town_hall" field, or this is very new content the library doesn\'t know yet)');return;}
    matched++;const level=Math.min(+b.level||0,target);const[c,s,r]=remain(e,level,target);out.push({category:cat,name:b.name,level,max:target,is_max:level>=target,cost:c?{[r]:c}:{},seconds:s});});};
  addFrom(v.buildings||v.defenses,'defenses',bIdx);
  addFrom(v.resources,'resources',bIdx);
  addFrom(v.traps,'traps',tIdx);
  const we=T.wall;
  if(we&&we.l.length&&(v.walls||[]).length){
    const target=maxTh(we);
    (v.walls||[]).forEach(g=>{total++;const level=+g.level||0,count=+g.count||0;
      if(count<=0){misses.push('Wall lvl '+level+' -- count is 0');return;}
      if(!target){misses.push('Wall lvl '+level+' -- not unlocked at Town Hall '+th);return;}
      matched++;const[c]=remain(we,level,target);out.push({category:'walls',name:'Wall lvl '+level+' x'+count,level,max:target,is_max:level>=target,cost:(c*count)?{gold:c*count}:{},seconds:0,count});});
  }
  out.__match={total,matched,misses};
  return out;
}
function IT(){const base=acc().items||[];const v=pastedVillage();if(!v)return base;const def=defenseItemsFromVillage(v);if(!def||!def.length)return base;const off=base.filter(i=>!['defenses','walls','traps','resources'].includes(i.category));return off.concat(def);}
function COMP(){const cur={},mx={};for(const i of IT()){const w=i.count||1;cur[i.category]=(cur[i.category]||0)+i.level*w;mx[i.category]=(mx[i.category]||0)+i.max*w;}const out={};for(const k in cur)out[k]=mx[k]?Math.round(1000*cur[k]/mx[k])/10:100;return out;}
function haveDefenses(){return !!pastedVillage()||!!acc().village_present;}
function remaining(){return IT().filter(i=>!i.is_max)}
function overallPct(){let c=0,m=0;for(const i of IT()){const w=i.count||1;c+=i.level*w;m+=i.max*w;}return m?Math.round(100*c/m):0;}
function ring(pct,color){const r=68,circ=2*Math.PI*r,off=circ*(1-pct/100);return '<svg width="160" height="160" viewBox="0 0 160 160"><circle cx="80" cy="80" r="'+r+'" fill="none" stroke="#21262d" stroke-width="12"/><circle cx="80" cy="80" r="'+r+'" fill="none" stroke="'+color+'" stroke-width="12" stroke-linecap="round" stroke-dasharray="'+circ+'" stroke-dashoffset="'+off+'" transform="rotate(-90 80 80)"/></svg>';}
function renderOverview(){
  const a=acc(),comp=COMP(),pct=overallPct();const rem=remaining().length;
  let dc=0,dm=0;for(const i of IT()){if(!DEFENSE.includes(i.category))continue;const w=i.count||1;dc+=i.level*w;dm+=i.max*w;}
  const defScore=dm?Math.round(100*dc/dm):null;
  const order=['heroes','troops','spells','pets','equipment','defenses','walls','traps','resources'];
  const health=order.filter(k=>k in comp).map(k=>{const p=comp[k];const col=rampColor(p,p>=100);return '<div class="hrow"><span class="hlabel">'+k+'</span><span class="htrack"><span class="hfill" style="width:'+p+'%;background:'+col+'"></span></span><span class="hpct">'+p+'%</span></div>';}).join('');
  const badge=pastedVillage()?'<span class="badge ok">● Accurate · village pasted</span>':(a.village_present?'<span class="badge ok">● Accurate · village.json imported</span>':'<span class="badge warn">● Offense only · paste your village for defenses</span>');
  const importBtn='<button class="af" style="margin-top:12px" onclick="openVillageModal()">'+(haveDefenses()?'↻ Update village (paste JSON)':'＋ Paste village JSON (adds defenses)')+'</button>'+(pastedVillage()?' <button class="af clear" style="margin-top:12px" onclick="clearVillage()">Remove pasted village</button>':'');
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
    return '<div class="tile '+(i.is_max?'max':'')+'">'+(i.is_max?'<span class="maxbadge">MAX</span>':'')
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
  const sortRem=(arr)=>arr.slice().sort((a,b)=>(b.max-b.level)-(a.max-a.level));
  const prioBlock=(title,cats,n)=>{const items=sortRem(remaining().filter(i=>cats.includes(i.category))).slice(0,n);
    const rows=items.map(i=>{const j=adj(i);return '<div class="pitem"><span class="pi-name"><span class="pi-ic" style="color:'+CAT_COLOR[i.category]+'">'+iconSVG(i.category,i.name)+'</span>'+esc(i.name)+' <span class="lv">'+i.level+'&rarr;'+i.max+'</span></span><span class="pi-meta">'+costText(j.cost)+'<br>'+fmtTime(j.seconds)+'</span><button class="addbtn" onclick="openQueueModal(\''+esc(i.category)+'\',\''+esc(i.name).replace(/'/g,"\\'")+'\')">+ queue</button></div>';}).join('');
    return '<div class="prio card"><h4>'+title+' <span class="faint">top '+n+'</span></h4>'+(rows||'<div class="faint">All maxed here.</div>')+'</div>';};
  const p=plan(),bc=(s.builders||6)+(s.goblinB?1:0);
  const findItem=(nm)=>IT().find(i=>i.name===nm);
  const laneTime=(ids)=>ids.reduce((t,nm)=>{const it=findItem(nm);return t+(it?adj(it).seconds:0)},0);
  const laneBox=(title,key,items,parallel)=>{const t=laneTime(items);const eff=parallel&&parallel>1?t/parallel:t;
    const rows=items.length?items.map(nm=>'<div class="qitem"><span>'+esc(nm)+' <span class="faint mono">'+fmtTime(findItem(nm)?adj(findItem(nm)).seconds:0)+'</span></span><span class="x" onclick="removeFromLane(\''+key+'\',\''+esc(nm).replace(/'/g,"\\'")+'\')">✕</span></div>').join(''):'<div class="empty">Empty — add from the lists above</div>';
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
  const sortRem=(arr)=>arr.slice().sort((a,b)=>mode==='fast'?adj(a).seconds-adj(b).seconds:(b.max-b.level)-(a.max-a.level));
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
        updated = datetime.fromisoformat(updated.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")
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
        "<p class=\"muted\" style=\"font-size:12px;margin:4px 0 0\">Your current defense, resource-building, trap and wall levels. Saved in this browser only, per account. It adds the defense side to your Overview, Tracker and Planner instantly. Names must match the game exactly (case doesn't matter) &mdash; \"buildings\" or \"defenses\" both work as the key for defensive buildings.</p>"
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
        "</div><script>const DATA=" + json.dumps(data) + ";</script><script>" + APP_JS + "</script></body></html>"
    )
    out_path.write_text(doc)
    return True
