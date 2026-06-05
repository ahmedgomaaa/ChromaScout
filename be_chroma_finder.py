#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
  BLUE ESSENCE EMPORIUM - CHROMA / SHARD MATCHER
============================================================================
What it does, in plain English:
  1. Talks to your RUNNING League of Legends client (the LCU API).
  2. Reads your Hextech loot and finds your SKIN SHARDS (skins you have NOT
     unlocked yet - they are sitting in loot).
  3. Reads the live store catalog and finds every CHROMA you can buy with
     BLUE ESSENCE right now (the Blue Essence Emporium offers).
  4. Tells you which of your shards are "worth unlocking": once unlocked you
     own the base skin, and THEN you can buy that skin's chroma with BE.
  5. Prints nice tables and saves the raw data to ./lcu_dump/ so you can
     verify everything yourself (and reuse it for a web page later).

You do NOT need to know how any of this works. Just keep the League client
open and run this script. If something is missing it tries to fix itself.

Requires: a running League client + Python 3.8+. Everything else is handled.
============================================================================
"""

import sys
import os
import re
import json
import base64
import ssl
import subprocess
import tempfile
import platform
import traceback
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# 0. Make the console able to print nice characters on a fresh Windows box.
# --------------------------------------------------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Python 3.7+
except Exception:
    pass


# --------------------------------------------------------------------------
# Choose a WRITABLE output folder that works on anyone's machine.
#   - EMPORIUM_OUT (set by the .bat to its own folder) is tried first.
#   - then ~/EmporiumChromaFinder, then a temp folder, then cwd.
# Everything (dumps, html, log) goes under here so the user can find it.
# --------------------------------------------------------------------------
def _pick_output_dir():
    tried = []
    candidates = []
    env = os.environ.get("EMPORIUM_OUT")
    if env:
        candidates.append(env)
    candidates.append(os.path.join(os.path.expanduser("~"), "EmporiumChromaFinder"))
    candidates.append(os.path.join(tempfile.gettempdir(), "EmporiumChromaFinder"))
    candidates.append(os.getcwd())
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            t = os.path.join(c, ".writetest")
            with open(t, "w") as f:
                f.write("ok")
            os.remove(t)
            return os.path.abspath(c), tried
        except Exception as e:
            tried.append(f"{c}  ->  {e}")
    return os.path.abspath(os.getcwd()), tried


OUTPUT_DIR, _OUT_TRIED = _pick_output_dir()
DUMP_DIR = os.path.join(OUTPUT_DIR, "lcu_dump")
HTML_PATH = os.path.join(OUTPUT_DIR, "chroma_report.html")
LOG_PATH = os.path.join(OUTPUT_DIR, "run_log.txt")

# Fresh log each run, with full environment context for debugging on any PC.
try:
    _logf = open(LOG_PATH, "w", encoding="utf-8")
    _logf.write("Blue Essence Emporium finder - run log\n")
    _logf.write(f"time         : {datetime.now().isoformat()}\n")
    _logf.write(f"python       : {sys.version.splitlines()[0]}\n")
    _logf.write(f"executable   : {sys.executable}\n")
    _logf.write(f"platform     : {platform.platform()}\n")
    _logf.write(f"script       : {os.path.abspath(__file__)}\n")
    _logf.write(f"cwd          : {os.getcwd()}\n")
    _logf.write(f"EMPORIUM_OUT : {os.environ.get('EMPORIUM_OUT')}\n")
    _logf.write(f"output dir   : {OUTPUT_DIR}\n")
    if _OUT_TRIED:
        _logf.write("output fallbacks tried:\n  " + "\n  ".join(_OUT_TRIED) + "\n")
    _logf.write("-" * 60 + "\n")
    _logf.flush()
except Exception:
    _logf = None


def _log(line):
    if _logf:
        try:
            _logf.write(line + "\n")
            _logf.flush()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Pretty printing helpers (also write everything to the log file)
# --------------------------------------------------------------------------
def say(msg):       print(msg);                  _log(msg)
def step(msg):      print(f"\n>>> {msg}");        _log(f">>> {msg}")
def ok(msg):        print(f"  [OK]   {msg}");     _log(f"[OK] {msg}")
def info(msg):      print(f"  [info] {msg}");     _log(f"[info] {msg}")
def warn(msg):      print(f"  [warn] {msg}");     _log(f"[warn] {msg}")
def fail(msg):      print(f"  [ERROR] {msg}");    _log(f"[ERROR] {msg}")


def print_table(headers, rows):
    """Print a clean ASCII table. rows = list of lists (all strings)."""
    cols = len(headers)
    widths = [len(str(h)) for h in headers]
    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(str(r[i])))

    def line(ch="-", junc="+"):
        return junc + junc.join(ch * (w + 2) for w in widths) + junc

    def fmt(cells):
        return "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)) + " |"

    print(line("="))
    print(fmt(headers))
    print(line("="))
    if not rows:
        print(fmt(["(none)"] + [""] * (cols - 1)))
    for r in rows:
        print(fmt(r))
    print(line("-"))


def die(msg, hint=""):
    """Print a friendly fatal error and exit cleanly (no scary traceback)."""
    print("\n" + "!" * 70)
    fail(msg)
    if hint:
        print("\n  What to do:")
        for ln in hint.strip().splitlines():
            print("    " + ln.strip())
    print(f"\n  A detailed log was saved to:\n    {LOG_PATH}")
    print("  If you're stuck, send that file to whoever shared this with you.")
    print("!" * 70)
    # Keep window open if double-clicked
    try:
        input("\nPress ENTER to close...")
    except Exception:
        pass
    sys.exit(1)


# --------------------------------------------------------------------------
# 1. Make sure 'requests' is available; if not, install it. If install fails,
#    fall back to Python's built-in urllib so the script STILL works.
# --------------------------------------------------------------------------
def get_http_getter():
    """Return a function get(url, auth_token) -> (status_code, text)."""
    try:
        import requests  # noqa
    except ImportError:
        info("'requests' library not found - trying to install it for you...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet",
                 "--disable-pip-version-check", "requests"]
            )
            ok("Installed 'requests'.")
        except Exception as e:
            warn(f"Could not install 'requests' ({e}). Using built-in fallback instead.")

    # Try requests again
    try:
        import requests
        import urllib3
        urllib3.disable_warnings()  # silence self-signed cert warning

        def _get(url, token):
            r = requests.get(url, auth=("riot", token), verify=False, timeout=30)
            return r.status_code, r.text
        return _get
    except Exception:
        # Pure stdlib fallback (urllib)
        import urllib.request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        def _get(url, token):
            auth = "Basic " + base64.b64encode(f"riot:{token}".encode()).decode()
            req = urllib.request.Request(url, headers={"Authorization": auth,
                                                       "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                    return resp.status, resp.read().decode("utf-8", "replace")
            except Exception as e:
                # mimic a status for callers
                code = getattr(e, "code", 0)
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")
                except Exception:
                    body = str(e)
                return code, body
        return _get


# --------------------------------------------------------------------------
# 2. Find the League client connection details (port + password).
#    Method A: the 'lockfile' (exists only while the client runs).
#    Method B: read the client's process command-line arguments.
# --------------------------------------------------------------------------
def find_credentials():
    # --- Method A: lockfile on any drive, common install paths ---
    subpaths = [
        r"Riot Games\League of Legends\lockfile",
        r"Games\Riot Games\League of Legends\lockfile",
        r"Program Files\Riot Games\League of Legends\lockfile",
        r"Program Files (x86)\Riot Games\League of Legends\lockfile",
        r"Riot Games\Library\League of Legends\lockfile",
    ]
    drives = [f"{chr(c)}:\\" for c in range(ord("A"), ord("Z") + 1)]
    for d in drives:
        if not os.path.exists(d):
            continue
        for sp in subpaths:
            p = os.path.join(d, sp)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    parts = f.read().strip().split(":")
                if len(parts) >= 5:
                    info(f"Found lockfile: {p}")
                    return int(parts[2]), parts[3]
            except OSError:
                continue

    info("No lockfile found - reading the client's process arguments instead.")

    # --- Method B: process command line ---
    cmdline = _get_leagueux_cmdline()
    if cmdline:
        port = re.search(r"--app-port=(\d+)", cmdline)
        token = re.search(r"--remoting-auth-token=([\w\-]+)", cmdline)
        if port and token:
            return int(port.group(1)), token.group(1)

    return None, None


def _get_leagueux_cmdline():
    """Get LeagueClientUx.exe command line via PowerShell, then WMIC, then psutil."""
    # PowerShell (most reliable on Win10/11)
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"name='LeagueClientUx.exe'\" "
             "| Select-Object -ExpandProperty CommandLine"],
            text=True, stderr=subprocess.DEVNULL, timeout=30)
        if out and out.strip():
            return out
    except Exception:
        pass
    # WMIC (older systems)
    try:
        out = subprocess.check_output(
            ["wmic", "process", "where", "name='LeagueClientUx.exe'", "get", "CommandLine"],
            text=True, stderr=subprocess.DEVNULL, timeout=30)
        if out and out.strip():
            return out
    except Exception:
        pass
    # psutil (cross-platform, if installed)
    try:
        import psutil
        for proc in psutil.process_iter(["name", "cmdline"]):
            if proc.info["name"] and "LeagueClientUx" in proc.info["name"]:
                return " ".join(proc.info["cmdline"] or [])
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------
# Helpers for interpreting the data
# --------------------------------------------------------------------------
def is_blue_essence(currency):
    """The store calls Blue Essence 'IP' (legacy name). Be flexible for the future."""
    if not currency:
        return False
    c = str(currency).lower()
    return c == "ip" or c == "be" or "blue" in c


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def current_be_price(entry, now=None):
    """
    Return (price, end_date) if this item is buyable with Blue Essence RIGHT NOW.

    IMPORTANT: the Emporium puts normal chromas on a Blue Essence *sale*. The BE
    price usually lives in entry['sale']['prices'], NOT in the base entry['prices']
    (which often shows only the RP price). So we must check BOTH places. When the
    BE price comes from a sale, we only accept it if today is inside the sale's
    start/end window (otherwise we'd pick up old or upcoming sales).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # 1) An active, in-window sale priced in Blue Essence (the Emporium case)
    sale = entry.get("sale") or {}
    start, end = _parse_dt(sale.get("startDate")), _parse_dt(sale.get("endDate"))
    in_window = (start is None or start <= now) and (end is None or now <= end)
    if in_window:
        for p in (sale.get("prices") or []):
            if is_blue_essence(p.get("currency")):
                return p.get("cost"), sale.get("endDate")

    # 2) A permanent Blue Essence price in the base price list
    for p in (entry.get("prices") or []):
        if is_blue_essence(p.get("currency")):
            return p.get("cost"), sale.get("endDate")

    return None


def iso_to_nice(s):
    """Turn an ISO timestamp into a short readable date, or return as-is."""
    if not s:
        return "?"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return s


def name_of(catalog_entry):
    loc = (catalog_entry.get("localizations") or {})
    # prefer en_US, else first available
    if "en_US" in loc and loc["en_US"].get("name"):
        return loc["en_US"]["name"]
    for v in loc.values():
        if v.get("name"):
            return v["name"]
    return catalog_entry.get("name") or f"item {catalog_entry.get('itemId')}"


def save_json(name, data):
    path = os.path.join(DUMP_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


# ==========================================================================
# MAIN
# ==========================================================================
def main():
    print(__doc__)
    os.makedirs(DUMP_DIR, exist_ok=True)

    http_get = get_http_getter()

    # ---- Connect ----------------------------------------------------------
    step("Step 1/5: Connecting to your League client")
    port, token = find_credentials()
    if not port or not token:
        die("Could not find the League client connection details.",
            """Make sure the League of Legends client is OPEN and you are logged in
               (you must be past the login screen, sitting in the client home).
               Then run this script again.""")
    base = f"https://127.0.0.1:{port}"
    info(f"Client API at {base}")

    def api(path):
        """GET a JSON endpoint and return parsed data, with friendly errors."""
        try:
            status, body = http_get(base + path, token)
        except Exception as e:
            die(f"Could not reach the client ({e}).",
                """The client port may have changed (this happens every restart).
                   Close this window, make sure League is running, and run again.""")
        if status == 0:
            die("Connection refused by the client.",
                """The client is closed, still loading, or the port changed.
                   Open League, wait until you're on the home screen, run again.""")
        if status == 401:
            die("The client rejected our password (401 Unauthorized).",
                "Restart the League client, then run this script again.")
        if status == 404:
            die(f"Endpoint not found (404): {path}",
                "Riot may have moved this endpoint in a patch. Tell the author.")
        if status != 200:
            die(f"Unexpected response {status} from {path}",
                f"Raw response: {body[:300]}")
        try:
            return json.loads(body)
        except Exception:
            die(f"Could not understand the response from {path}.",
                f"Raw response start: {body[:300]}")

    me = api("/lol-summoner/v1/current-summoner")
    who = me.get("gameName") or me.get("displayName") or "Summoner"
    ok(f"Connected as: {who}  (level {me.get('summonerLevel', '?')})")

    # ---- Your skin shards -------------------------------------------------
    step("Step 2/5: Reading your skin shards from loot")
    loot = api("/lol-loot/v1/player-loot")
    save_json("player-loot.json", loot)
    # SKIN_RENTAL = a skin SHARD (not unlocked). SKIN = already permanent.
    shards = [x for x in loot if x.get("type") == "SKIN_RENTAL"]
    shard_by_skinid = {}
    shard_list = []
    for s in shards:
        sid = s.get("storeItemId")
        nm = s.get("itemDesc") or s.get("lootName") or f"skin {sid}"
        shard_by_skinid[sid] = nm
        shard_list.append({
            "skinId": sid, "name": nm, "count": s.get("count", 1),
            "value": s.get("value"),                     # skin's RP value
            "unlockCost": s.get("upgradeEssenceValue"),  # Orange Essence to unlock
            "disenchant": s.get("disenchantValue"),      # OE you'd get if you scrap it
            "rarity": s.get("rarity"),
        })
    shard_list.sort(key=lambda x: x["name"].lower())
    save_json("my_skin_shards.json", shard_list)

    if not shard_list:
        warn("You have ZERO skin shards in loot right now - nothing to match.")
    else:
        ok(f"Found {len(shard_list)} skin shard(s).")

    # ---- Your essence balances (from the loot CURRENCY entries) ----------
    cur_map = {"CURRENCY_cosmetic": "orange", "CURRENCY_champion": "blue",
               "CURRENCY_mythic": "mythic", "CURRENCY_RP": "rp"}
    balances = {"orange": 0, "blue": 0, "mythic": 0, "rp": 0}
    for d in loot:
        key = cur_map.get(d.get("lootId"))
        if key:
            balances[key] = d.get("count", 0)
    save_json("my_balances.json", balances)
    ok(f"Orange Essence: {balances['orange']:,}  |  Blue Essence: {balances['blue']:,}")

    # ---- Skins you already OWN (for the "My Skins" gallery) ---------------
    owned_list = []
    try:
        sumid = me.get("summonerId")
        skins_min = api(f"/lol-champions/v1/inventories/{sumid}/skins-minimal")
        for s in skins_min:
            if s.get("isBase"):
                continue  # skip default skins
            if not (s.get("ownership") or {}).get("owned"):
                continue
            owned_list.append({
                "skinId": s.get("id"),
                "name": s.get("name"),
                "championId": s.get("championId"),
                "splashPath": s.get("splashPath"),
                "tilePath": s.get("tilePath"),
            })
        owned_list.sort(key=lambda x: (x.get("name") or "").lower())
        save_json("my_owned_skins.json", owned_list)
        ok(f"You own {len(owned_list)} skin(s) (non-default).")
    except Exception as e:
        warn(f"Could not read owned skins ({e}). The 'My Skins' view will be empty.")

    # ---- Blue Essence chromas in the live store ---------------------------
    step("Step 3/5: Reading Blue Essence chroma offers from the store")
    catalog = api("/lol-store/v1/catalog")
    save_json("store_catalog.json", catalog)

    be_chromas = []
    for c in catalog:
        if c.get("inventoryType") != "CHAMPION_SKIN":
            continue
        if c.get("subInventoryType") != "RECOLOR":   # RECOLOR == chroma
            continue
        if c.get("active") is False:                 # not currently offered
            continue
        # Is it buyable with Blue Essence right now? (checks the sale block too)
        be = current_be_price(c)
        if be is None:
            continue
        be_price, sale_end = be
        # the base skin you must OWN to buy this chroma
        base_skin = None
        champ_id = None
        for r in (c.get("itemRequirements") or []):
            if r.get("inventoryType") == "CHAMPION_SKIN":
                base_skin = r.get("itemId")
            elif r.get("inventoryType") == "CHAMPION":
                champ_id = r.get("itemId")
        sale = c.get("sale") or {}
        be_chromas.append({
            "chromaId": c.get("itemId"),
            "chromaName": name_of(c),
            "championId": champ_id,
            "requiredBaseSkinId": base_skin,
            "bePrice": be_price,
            "saleStart": sale.get("startDate"),
            "saleEnd": sale_end,
            "iconFile": c.get("iconUrl"),   # e.g. championsskin_32019.jpg (for your web page later)
        })
    be_chromas.sort(key=lambda x: x["chromaName"].lower())
    save_json("emporium_be_chromas.json", be_chromas)
    ok(f"Found {len(be_chromas)} chroma(s) purchasable with Blue Essence right now.")

    # ---- Intersect --------------------------------------------------------
    step("Step 4/5: Matching your shards against the BE chromas")
    matches = []                       # one row per chroma (saved to JSON)
    by_shard = {}                      # skinId -> list of matching chromas
    for ch in be_chromas:
        bsid = ch["requiredBaseSkinId"]
        if bsid in shard_by_skinid:
            row = {**ch, "shardName": shard_by_skinid[bsid], "shardSkinId": bsid}
            matches.append(row)
            by_shard.setdefault(bsid, []).append(row)
    matches.sort(key=lambda x: (x["shardName"].lower(), x["chromaName"].lower()))
    save_json("ANSWER_matches.json", matches)

    matched_skinids = set(by_shard)
    cost_by_skinid = {s["skinId"]: s.get("unlockCost") for s in shard_list}

    def how_many_affordable(costs, budget):
        """Greedy: how many shards can 'budget' OE unlock, cheapest first."""
        n, spent = 0, 0
        for c in sorted(c for c in costs if c):
            if spent + c <= budget:
                spent += c
                n += 1
            else:
                break
        return n, spent

    orange = balances["orange"]

    # ---- Report -----------------------------------------------------------
    step("Step 5/5: Results")

    say(f"\nYOUR ESSENCE:  Orange (unlocks shards): {orange:,} OE   |   "
        f"Blue (buys chromas): {balances['blue']:,} BE")

    say("\nYOUR SKIN SHARDS (skins you have not unlocked yet):")
    print_table(
        ["#", "Skin shard", "Unlock (OE)", "Value (RP)", "BE chromas", "Afford now?"],
        [[i + 1, s["name"], f'{(s.get("unlockCost") or 0):,}', f'{(s.get("value") or 0):,}',
          str(len(by_shard[s["skinId"]])) if s["skinId"] in matched_skinids else "-",
          "YES" if (s.get("unlockCost") or 0) <= orange else "no"]
         for i, s in enumerate(shard_list)]
    )

    say("\n\nTHE ANSWER - shards worth unlocking (sorted by unlock cost, cheapest first):")
    summary_rows = []
    matched_sorted = sorted(by_shard.items(),
                            key=lambda kv: (cost_by_skinid.get(kv[0]) or 0, shard_by_skinid[kv[0]].lower()))
    for sid, chs in matched_sorted:
        prices = sorted({c["bePrice"] for c in chs})
        price_str = " / ".join(f"{p:,}" for p in prices)
        cost = cost_by_skinid.get(sid) or 0
        afford = "YES" if cost <= orange else "no"
        summary_rows.append([shard_by_skinid[sid], f'{cost:,}', str(len(chs)), price_str + " BE", afford])
    print_table(
        ["Skin shard (unlock first)", "Unlock (OE)", "# chromas", "BE price each", "Afford now?"],
        summary_rows
    )

    # ---- Affordability -----------------------------------------------------
    say("\n\nWHAT YOUR ORANGE ESSENCE CAN DO RIGHT NOW:")
    n_all, spent_all = how_many_affordable([s.get("unlockCost") for s in shard_list], orange)
    n_worth, spent_worth = how_many_affordable([cost_by_skinid[sid] for sid in matched_skinids], orange)
    say(f"  - You have {orange:,} OE.")
    say(f"  - Across ALL {len(shard_list)} shards (cheapest first): you can unlock {n_all} "
        f"(spending {spent_all:,} OE).")
    say(f"  - Among the {len(matched_skinids)} WORTH-UNLOCKING shards: you can unlock {n_worth} "
        f"(spending {spent_worth:,} OE).")
    if matched_skinids:
        cheapest_worth = min(cost_by_skinid[sid] for sid in matched_skinids)
        if n_worth == 0:
            say(f"  - Cheapest worth-unlocking shard costs {cheapest_worth:,} OE - "
                f"you're {cheapest_worth - orange:,} OE short. Disenchant other loot to top up.")

    if matches:
        say(f"\n  => {len(matched_skinids)} of your {len(shard_list)} shards are worth unlocking,")
        say(f"     unlocking access to {len(matches)} Blue Essence chroma(s) total.")
        say("     Unlock the shard first (you must OWN the base skin), then buy its")
        say("     chroma(s) with Blue Essence in the Emporium before the sale ends.")
    else:
        say("\n  => None of your current shards have a Blue Essence chroma on offer")
        say("     this rotation. Check back next patch - offers rotate.")

    say(f"\nRaw data saved in:  {DUMP_DIR}")
    say("  - my_skin_shards.json       (your shards)")
    say("  - emporium_be_chromas.json  (all BE chromas on sale)")
    say("  - ANSWER_matches.json       (the matches above, with image filenames)")
    say("  - player-loot.json / store_catalog.json  (full raw dumps)")

    # ---- Build the nice HTML report (best effort - never break the run) ----
    step("Bonus: building a visual HTML report (with chroma images)")
    try:
        import make_webpage
        make_webpage.DUMP_DIR = DUMP_DIR     # reuse our writable dump folder for the skins cache
        out = make_webpage.generate(matches, shard_list, summoner=who,
                                    owned=owned_list, balances=balances,
                                    out_path=HTML_PATH)
        ok(f"Report saved: {out}")
        try:
            import webbrowser
            webbrowser.open("file:///" + out.replace("\\", "/"))
            ok("Opened it in your browser.")
        except Exception as e:
            warn(f"Could not auto-open the browser ({e}). Open this file yourself: {out}")
    except Exception as e:
        warn(f"Could not build the HTML report ({e}). The data above is still valid.")
        _log("HTML build traceback:\n" + traceback.format_exc())

    say(f"\nEverything is saved in:  {OUTPUT_DIR}")
    say(f"  - chroma_report.html   (open this - the visual report)")
    say(f"  - run_log.txt          (detailed log, send this if anything looked wrong)")

    # Keep window open if double-clicked
    try:
        input("\nDone. Press ENTER to close...")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        # Last-resort friendly catch so a noob never sees a raw traceback.
        _log("FATAL traceback:\n" + traceback.format_exc())
        die(f"Something unexpected went wrong: {e}",
            "This is a bug. Send the run_log.txt file (path shown below) to whoever shared this.")
