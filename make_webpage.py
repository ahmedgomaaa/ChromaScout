#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Builds a nice standalone HTML report from the data that be_chroma_finder.py
saved into ./lcu_dump/ .

- Reads  lcu_dump/ANSWER_matches.json  and  lcu_dump/my_skin_shards.json
- Pulls chroma / splash art from Community Dragon (a PUBLIC, keyless CDN -
  you do NOT need a Riot developer API key for images).
- Writes  chroma_report.html  : a single self-contained file you can double
  click or send to anyone. The data is baked in; only the images load online.

Run it on its own:      python make_webpage.py
Or it is called automatically at the end of be_chroma_finder.py.
"""

import os
import re
import json
import sys

ASSET_BASE = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
HERE = os.path.dirname(os.path.abspath(__file__))
DUMP_DIR = os.path.join(HERE, "lcu_dump")
OUT_HTML = os.path.join(HERE, "chroma_report.html")


def asset_url(game_path):
    """Convert a '/lol-game-data/assets/...' path to a Community Dragon URL."""
    if not game_path:
        return None
    p = re.sub(r"^/lol-game-data/assets/", "", game_path)
    return (ASSET_BASE + p).lower()


def chroma_img(champion_id, chroma_id):
    return f"{ASSET_BASE}v1/champion-chroma-images/{champion_id}/{chroma_id}.png"


def champ_icon(champion_id):
    return f"{ASSET_BASE}v1/champion-icons/{champion_id}.png"


def load_skins_index():
    """Return dict {skinId(str): skinObj} for splash art. Best-effort; may be None."""
    local = os.path.join(DUMP_DIR, "cdragon_skins.json")
    # 1) already downloaded?
    if os.path.exists(local):
        try:
            with open(local, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 2) try to download it once (needs internet)
    url = ASSET_BASE + "v1/skins.json"
    try:
        try:
            import requests
            data = requests.get(url, timeout=60).json()
        except Exception:
            import urllib.request
            with urllib.request.urlopen(url, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        os.makedirs(DUMP_DIR, exist_ok=True)
        with open(local, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception:
        # No internet / blocked - we'll just fall back to champion icons.
        return None


def build_model(matches, shard_list, skins_index):
    """Group matches by shard and attach image URLs. Returns a list of shard dicts."""
    by_shard = {}
    for m in matches:
        by_shard.setdefault(m["shardSkinId"], []).append(m)

    shards = []
    for s in shard_list:
        sid = s["skinId"]
        chs = sorted(by_shard.get(sid, []), key=lambda c: c["chromaName"].lower())
        champ_id = chs[0]["championId"] if chs else None

        # parent splash from skins.json (nice banner); fallback to champion icon
        splash = None
        if skins_index:
            sk = skins_index.get(str(sid)) or {}
            splash = asset_url(sk.get("uncenteredSplashPath")
                               or sk.get("splashPath")
                               or sk.get("tilePath"))
        if not splash and champ_id:
            splash = champ_icon(champ_id)

        chroma_items = []
        for c in chs:
            cid = c["chromaId"]
            ccid = c["championId"]
            # strip the redundant "SkinName (" prefix for a short label
            short = c["chromaName"]
            m = re.search(r"\(([^)]+)\)\s*$", short)
            short = m.group(1) if m else short
            chroma_items.append({
                "name": c["chromaName"],
                "short": short,
                "price": c["bePrice"],
                "img": chroma_img(ccid, cid),
                "icon": champ_icon(ccid),
                "emerald": c["bePrice"] >= 10000,
            })

        prices = sorted({c["price"] for c in chroma_items})
        shards.append({
            "name": s["name"],
            "skinId": sid,
            "championId": champ_id,
            "splash": splash,
            "icon": champ_icon(champ_id) if champ_id else None,
            "count": len(chroma_items),
            "minPrice": prices[0] if prices else None,
            "maxPrice": prices[-1] if prices else None,
            "value": s.get("value"),            # skin RP value
            "unlockCost": s.get("unlockCost"),  # Orange Essence to unlock
            "disenchant": s.get("disenchant"),  # OE if scrapped
            "rarity": s.get("rarity"),
            "chromas": chroma_items,
        })

    # matched shards first (most chromas first), then the "no chroma" ones
    shards.sort(key=lambda x: (x["count"] == 0, -x["count"], x["name"].lower()))
    return shards


def build_owned(owned_list):
    """Build the 'My Skins' gallery model with big splash URLs."""
    out = []
    for s in (owned_list or []):
        cid = s.get("championId")
        splash = asset_url(s.get("splashPath")) or (champ_icon(cid) if cid else None)
        tile = asset_url(s.get("tilePath"))
        out.append({
            "name": s.get("name"),
            "skinId": s.get("skinId"),
            "championId": cid,
            "splash": splash,
            "tile": tile,
            "icon": champ_icon(cid) if cid else None,
        })
    out.sort(key=lambda x: (x["name"] or "").lower())
    return out


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blue Essence Emporium — Worth Unlocking</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#070b16; --bg2:#0a1428; --panel:#0e1a30; --panel2:#10203a;
    --gold:#c8aa6e; --gold-bright:#f0e6d2; --teal:#0ac8b9; --blue:#0596aa;
    --emerald:#1fd35b; --text:#cdd6e4; --muted:#7a8aa3; --line:#1d2d4a;
  }
  *{box-sizing:border-box}
  body{
    margin:0; background:radial-gradient(1200px 600px at 50% -200px,#13243f 0%,var(--bg) 60%);
    color:var(--text); font-family:'Inter',system-ui,Segoe UI,Roboto,sans-serif;
    min-height:100vh; padding-bottom:60px;
  }
  a{color:var(--teal)}
  header{
    text-align:center; padding:44px 20px 18px; border-bottom:1px solid var(--line);
    background:linear-gradient(180deg,rgba(200,170,110,.06),transparent);
  }
  h1{
    font-family:'Cinzel',serif; font-weight:700; letter-spacing:.5px; margin:0;
    font-size:clamp(26px,4vw,40px); color:var(--gold-bright);
    text-shadow:0 2px 18px rgba(200,170,110,.25);
  }
  .sub{color:var(--muted); margin-top:8px; font-size:15px}
  .chips{display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-top:18px}
  .chip{
    background:var(--panel); border:1px solid var(--line); border-radius:999px;
    padding:8px 16px; font-size:14px; display:flex; gap:8px; align-items:center;
  }
  .chip b{color:var(--gold); font-size:16px}
  .chip.oe b{color:#ff9d4d}
  .chip.be b{color:#3aa0ff}
  .toolbar{max-width:1200px; margin:24px auto 0; padding:0 20px; display:flex; gap:12px; flex-wrap:wrap; align-items:center}
  .search{
    flex:1; min-width:220px; background:var(--panel); border:1px solid var(--line);
    color:var(--text); padding:11px 14px; border-radius:10px; font-size:15px; outline:none;
  }
  .search:focus{border-color:var(--gold)}
  .btn{
    background:var(--panel); border:1px solid var(--line); color:var(--text);
    padding:11px 16px; border-radius:10px; cursor:pointer; font-size:14px; user-select:none;
  }
  .btn.active{border-color:var(--emerald); color:var(--emerald)}
  .grid{
    max-width:1200px; margin:22px auto 0; padding:0 20px;
    display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:20px;
  }
  .card{
    background:var(--panel); border:1px solid var(--line); border-radius:16px; overflow:hidden;
    display:flex; flex-direction:column; box-shadow:0 10px 30px rgba(0,0,0,.35);
    transition:transform .15s ease, border-color .15s ease;
  }
  .card:hover{transform:translateY(-3px); border-color:var(--gold)}
  .card.empty{opacity:.55}
  .banner{
    position:relative; height:150px; background-size:cover; background-position:center 22%;
    background-color:var(--panel2);
  }
  .banner::after{content:""; position:absolute; inset:0;
    background:linear-gradient(180deg,rgba(7,11,22,.05) 0%,rgba(7,11,22,.55) 60%,var(--panel) 100%)}
  .banner .ttl{position:absolute; left:16px; right:16px; bottom:10px; z-index:2}
  .banner .ttl h2{
    margin:0; font-family:'Cinzel',serif; font-size:20px; color:#fff;
    text-shadow:0 2px 10px rgba(0,0,0,.8);
  }
  .badge{
    display:inline-block; margin-bottom:6px; font-size:11px; letter-spacing:.5px;
    text-transform:uppercase; padding:3px 9px; border-radius:6px;
    background:rgba(200,170,110,.18); color:var(--gold); border:1px solid rgba(200,170,110,.4);
  }
  .meta{display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border-bottom:1px solid var(--line)}
  .meta .price{color:var(--gold); font-weight:600}
  .meta .price .em{color:var(--emerald)}
  .meta small{color:var(--muted)}
  .costbar{display:flex; gap:8px; align-items:center; padding:10px 16px; border-bottom:1px solid var(--line); font-size:13px; flex-wrap:wrap}
  .pill{padding:3px 9px; border-radius:6px; border:1px solid var(--line); background:var(--bg2)}
  .pill .v{color:#ff9d4d; font-weight:600}
  .pill .rp{color:#3aa0ff; font-weight:600}
  .afford{margin-left:auto; padding:3px 10px; border-radius:6px; font-weight:600}
  .afford.yes{color:var(--emerald); border:1px solid rgba(31,211,91,.4); background:rgba(31,211,91,.1)}
  .afford.no{color:#ff7d7d; border:1px solid rgba(255,125,125,.35); background:rgba(255,125,125,.08)}
  .chromas{display:flex; flex-wrap:wrap; gap:12px; padding:16px}
  .chroma{width:74px; text-align:center}
  .chroma .imgwrap{
    width:64px; height:64px; margin:0 auto; border-radius:50%; overflow:hidden;
    border:2px solid var(--line); background:var(--bg2);
  }
  .chroma.em .imgwrap{border-color:var(--emerald); box-shadow:0 0 10px rgba(31,211,91,.5)}
  .chroma img{width:100%; height:100%; object-fit:cover; display:block}
  .chroma .nm{font-size:11px; color:var(--muted); margin-top:5px; line-height:1.25}
  .chroma .pr{font-size:11px; color:var(--gold); font-weight:600}
  .chroma.em .pr{color:var(--emerald)}
  .none{padding:18px 16px; color:var(--muted); font-size:14px}
  footer{max-width:1200px; margin:36px auto 0; padding:18px 20px; color:var(--muted); font-size:13px; text-align:center; border-top:1px solid var(--line)}
  .hidden{display:none !important}

  /* view tabs */
  .tabs{display:flex; gap:10px; justify-content:center; margin-top:22px; flex-wrap:wrap}
  .tab{
    background:var(--panel); border:1px solid var(--line); color:var(--text);
    padding:11px 22px; border-radius:10px; cursor:pointer; font-size:15px; font-weight:600;
    display:flex; gap:8px; align-items:center;
  }
  .tab .n{color:var(--muted); font-weight:500}
  .tab.active{border-color:var(--gold); color:var(--gold-bright); background:linear-gradient(180deg,rgba(200,170,110,.12),var(--panel))}
  .tab.active .n{color:var(--gold)}

  /* My Skins gallery - bigger splashes */
  .gallery{
    max-width:1280px; margin:22px auto 0; padding:0 20px;
    display:grid; grid-template-columns:repeat(auto-fill,minmax(440px,1fr)); gap:22px;
  }
  .skin{
    position:relative; border-radius:16px; overflow:hidden; border:1px solid var(--line);
    box-shadow:0 12px 34px rgba(0,0,0,.45); aspect-ratio:1215/717; background:var(--panel2);
    transition:transform .15s ease, border-color .15s ease;
  }
  .skin:hover{transform:translateY(-3px); border-color:var(--gold)}
  .skin img{width:100%; height:100%; object-fit:cover; display:block}
  .skin .cap{
    position:absolute; left:0; right:0; bottom:0; padding:34px 18px 14px; z-index:2;
    background:linear-gradient(180deg,transparent,rgba(7,11,22,.9));
  }
  .skin .cap h3{margin:0; font-family:'Cinzel',serif; font-size:21px; color:#fff; text-shadow:0 2px 12px rgba(0,0,0,.9)}
  .skin .cap small{color:var(--gold); font-size:12px}
  @media(max-width:520px){ .gallery{grid-template-columns:1fr} .grid{grid-template-columns:1fr} }
</style>
</head>
<body>
<header>
  <h1>Blue Essence Emporium — Worth Unlocking</h1>
  <div class="sub">__SUBTITLE__</div>
  <div class="chips">
    <div class="chip oe">🟠 Orange Essence <b>__OE__</b></div>
    <div class="chip be">🔵 Blue Essence <b>__BE__</b></div>
    <div class="chip">Shards worth unlocking <b>__N_SHARDS__</b></div>
    <div class="chip">Chromas unlocked <b>__N_CHROMAS__</b></div>
    <div class="chip">Unlockable with your OE <b id="affordCount">__N_AFFORD__</b></div>
    <div class="chip">Emporium ends <b>__SALE_END__</b></div>
  </div>
  <div class="tabs">
    <div id="tabShards" class="tab active">⚒ Worth Unlocking</div>
    <div id="tabOwned" class="tab">★ My Skins <span class="n">(__N_OWNED__)</span></div>
  </div>
</header>

<div class="toolbar">
  <input id="search" class="search" placeholder="Filter by skin or chroma name…">
  <select id="sort" class="search" style="flex:0 0 auto; min-width:200px">
    <option value="chromas"># Chromas (most first)</option>
    <option value="value">Skin value (RP, high→low)</option>
    <option value="costAsc">Cheapest to unlock (OE)</option>
    <option value="costDesc">Priciest to unlock (OE)</option>
    <option value="affordFirst">Affordable now first</option>
    <option value="name">Name (A→Z)</option>
  </select>
  <div id="emFilter" class="btn">Show only Emerald (10k)</div>
</div>

<div id="grid" class="grid"></div>
<div id="gallery" class="gallery hidden"></div>

<footer>
  Images from <a href="https://www.communitydragon.org/" target="_blank" rel="noopener">Community Dragon</a>
  (public CDN — no API key needed). Data read live from your League client.
  A chroma needs you to OWN its base skin, so unlock the shard first, then buy the chroma with Blue Essence.
  <br>Generated __GENERATED__.
</footer>

<script>
const SHARDS = __DATA__;
const OWNED  = __OWNED__;
const BALANCES = __BALANCES__;
const OE = BALANCES.orange || 0;

const grid = document.getElementById('grid');
const gallery = document.getElementById('gallery');
const search = document.getElementById('search');
const sortSel = document.getElementById('sort');
const emFilter = document.getElementById('emFilter');
const tabShards = document.getElementById('tabShards');
const tabOwned = document.getElementById('tabOwned');
const affordCount = document.getElementById('affordCount');
let emeraldOnly = false;
let view = 'shards';   // 'shards' | 'owned'

const fmt = n => (n==null ? '?' : n.toLocaleString());

function sortedShards(){
  const key = sortSel.value;
  const arr = SHARDS.slice();
  const cost = s => (s.unlockCost==null ? Infinity : s.unlockCost);
  const cmp = {
    chromas:    (a,b)=> b.count-a.count || (a.unlockCost||0)-(b.unlockCost||0),
    value:      (a,b)=> (b.value||0)-(a.value||0),
    costAsc:    (a,b)=> cost(a)-cost(b),
    costDesc:   (a,b)=> cost(b)-cost(a),
    name:       (a,b)=> a.name.localeCompare(b.name),
    affordFirst:(a,b)=> ((cost(b)<=OE)-(cost(a)<=OE)) || cost(a)-cost(b),
  }[key] || ((a,b)=>0);
  // keep "no chroma" shards at the bottom for the unlocking views
  return arr.sort((a,b)=> (a.count===0)-(b.count===0) || cmp(a,b));
}

function priceLabel(s){
  if(!s.count) return '';
  if(s.minPrice === s.maxPrice) return s.minPrice.toLocaleString() + ' BE';
  return s.minPrice.toLocaleString() + ' / <span class="em">' + s.maxPrice.toLocaleString() + '</span> BE';
}

function cardHTML(s){
  const banner = s.splash ? `style="background-image:url('${s.splash}')"` : '';
  const chromas = s.chromas.map(c => `
    <div class="chroma ${c.emerald?'em':''}" data-name="${c.name.toLowerCase()}">
      <div class="imgwrap">
        <img loading="lazy" src="${c.img}" alt="${c.name}"
             onerror="this.onerror=null;this.src='${c.icon}'">
      </div>
      <div class="nm">${c.short}</div>
      <div class="pr">${c.price.toLocaleString()}</div>
    </div>`).join('');
  const canAfford = s.unlockCost!=null && s.unlockCost <= OE;
  const affordHTML = s.unlockCost==null ? ''
    : (canAfford ? `<span class="afford yes">✓ Affordable</span>`
                 : `<span class="afford no">Need ${fmt(s.unlockCost-OE)} more OE</span>`);
  const costbar = `<div class="costbar">
      <span class="pill">Unlock: <span class="v">${fmt(s.unlockCost)} OE</span></span>
      <span class="pill">Value: <span class="rp">${fmt(s.value)} RP</span></span>
      ${affordHTML}
    </div>`;
  const body = s.count
    ? `${costbar}
       <div class="meta"><span class="price">${priceLabel(s)}</span><small>${s.count} chroma${s.count>1?'s':''} · skin ${s.skinId}</small></div>
       <div class="chromas">${chromas}</div>`
    : `${costbar}<div class="none">No Blue Essence chromas for this skin this rotation.</div>`;
  return `<div class="card ${s.count?'':'empty'}" data-name="${s.name.toLowerCase()}" data-em="${s.chromas.some(c=>c.emerald)?1:0}" data-has="${s.count?1:0}">
      <div class="banner" ${banner}>
        <div class="ttl">${s.count?'<span class="badge">Unlock shard first</span><br>':''}<h2>${s.name}</h2></div>
      </div>
      ${body}
    </div>`;
}

function skinHTML(s){
  return `<div class="skin" data-name="${(s.name||'').toLowerCase()}">
      <img loading="lazy" src="${s.splash||s.icon}" alt="${s.name}"
           onerror="this.onerror=null;this.src='${s.tile||s.icon}'">
      <div class="cap"><h3>${s.name}</h3><small>skin ${s.skinId}</small></div>
    </div>`;
}

function renderShards(){
  const q = search.value.trim().toLowerCase();
  grid.innerHTML = sortedShards().map(cardHTML).join('');
  document.querySelectorAll('#grid .card').forEach(card=>{
    const name = card.dataset.name;
    const hasEm = card.dataset.em === '1';
    const has = card.dataset.has === '1';
    let show = true;
    if(emeraldOnly && !hasEm) show = false;
    if(q){
      const inName = name.includes(q);
      const inChroma = [...card.querySelectorAll('.chroma')].some(c=>c.dataset.name.includes(q));
      if(!inName && !inChroma) show = false;
    }
    card.classList.toggle('hidden', !show);
    if(q && has){
      card.querySelectorAll('.chroma').forEach(c=>{
        c.style.opacity = (name.includes(q) || c.dataset.name.includes(q)) ? '1' : '.25';
      });
    } else {
      card.querySelectorAll('.chroma').forEach(c=> c.style.opacity='1');
    }
  });
}

function renderOwned(){
  const q = search.value.trim().toLowerCase();
  gallery.innerHTML = OWNED.map(skinHTML).join('');
  document.querySelectorAll('#gallery .skin').forEach(card=>{
    card.classList.toggle('hidden', q && !card.dataset.name.includes(q));
  });
}

function render(){
  if(view === 'shards') renderShards(); else renderOwned();
}

function setView(v){
  view = v;
  const shards = v === 'shards';
  grid.classList.toggle('hidden', !shards);
  gallery.classList.toggle('hidden', shards);
  tabShards.classList.toggle('active', shards);
  tabOwned.classList.toggle('active', !shards);
  emFilter.classList.toggle('hidden', !shards);   // these only apply to the shards view
  sortSel.classList.toggle('hidden', !shards);
  search.placeholder = shards ? 'Filter by skin or chroma name…' : 'Filter your skins by name…';
  render();
}

// How many WORTH-UNLOCKING shards your OE can unlock (cheapest first).
function updateAffordCount(){
  const costs = SHARDS.filter(s=>s.count && s.unlockCost!=null).map(s=>s.unlockCost).sort((a,b)=>a-b);
  let n=0, spent=0;
  for(const c of costs){ if(spent+c<=OE){ spent+=c; n++; } else break; }
  affordCount.textContent = n;
}

search.addEventListener('input', render);
sortSel.addEventListener('change', render);
emFilter.addEventListener('click', ()=>{
  emeraldOnly = !emeraldOnly;
  emFilter.classList.toggle('active', emeraldOnly);
  render();
});
tabShards.addEventListener('click', ()=> setView('shards'));
tabOwned.addEventListener('click', ()=> setView('owned'));
updateAffordCount();
setView('shards');
</script>
</body>
</html>
"""


def generate(matches, shard_list, summoner="Summoner", out_path=OUT_HTML,
             skins_index="auto", owned=None, balances=None):
    if skins_index == "auto":
        skins_index = load_skins_index()
    balances = balances or {"orange": 0, "blue": 0, "mythic": 0, "rp": 0}
    shards = build_model(matches, shard_list, skins_index)
    owned_model = build_owned(owned)

    matched = [s for s in shards if s["count"]]
    n_shards = len(matched)
    n_chromas = sum(s["count"] for s in matched)

    # how many worth-unlocking shards the OE can unlock (cheapest first)
    orange = balances.get("orange", 0)
    n_afford, spent = 0, 0
    for c in sorted(s["unlockCost"] for s in matched if s.get("unlockCost")):
        if spent + c <= orange:
            spent += c
            n_afford += 1
        else:
            break

    sale_end = "?"
    if matches:
        ends = [m.get("saleEnd") for m in matches if m.get("saleEnd")]
        if ends:
            sale_end = min(ends)[:10]

    from datetime import datetime
    html = (HTML_TEMPLATE
            .replace("__DATA__", json.dumps(shards, ensure_ascii=False))
            .replace("__OWNED__", json.dumps(owned_model, ensure_ascii=False))
            .replace("__BALANCES__", json.dumps(balances, ensure_ascii=False))
            .replace("__SUBTITLE__", f"Loot of {summoner} · skins you have as shards whose chroma is on Blue Essence sale now")
            .replace("__N_SHARDS__", str(n_shards))
            .replace("__N_CHROMAS__", str(n_chromas))
            .replace("__N_OWNED__", str(len(owned_model)))
            .replace("__N_AFFORD__", str(n_afford))
            .replace("__OE__", f'{orange:,}')
            .replace("__BE__", f'{balances.get("blue", 0):,}')
            .replace("__SALE_END__", sale_end)
            .replace("__GENERATED__", datetime.now().strftime("%Y-%m-%d %H:%M")))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    try:
        matches = json.load(open(os.path.join(DUMP_DIR, "ANSWER_matches.json"), encoding="utf-8"))
        shard_list = json.load(open(os.path.join(DUMP_DIR, "my_skin_shards.json"), encoding="utf-8"))
    except FileNotFoundError:
        print("Could not find lcu_dump/ANSWER_matches.json - run be_chroma_finder.py first.")
        sys.exit(1)
    owned = []
    try:
        owned = json.load(open(os.path.join(DUMP_DIR, "my_owned_skins.json"), encoding="utf-8"))
    except FileNotFoundError:
        pass
    balances = None
    try:
        balances = json.load(open(os.path.join(DUMP_DIR, "my_balances.json"), encoding="utf-8"))
    except FileNotFoundError:
        pass
    out = generate(matches, shard_list, owned=owned, balances=balances)
    print(f"Wrote {out}")
    # try to open it in the default browser for convenience
    try:
        import webbrowser
        webbrowser.open("file:///" + out.replace("\\", "/"))
    except Exception:
        pass


if __name__ == "__main__":
    main()
