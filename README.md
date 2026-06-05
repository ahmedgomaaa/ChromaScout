# Blue Essence Emporium — Chroma & Shard Finder

A small Windows tool that reads your **running League of Legends client** and tells you
which of your **skin shards** are worth unlocking right now — because their **chroma is
currently on sale for Blue Essence** in the Blue Essence Emporium.

It then builds a clean visual HTML report (with chroma art), shows your Orange/Blue
Essence balances, and works out how many shards you can actually afford to unlock.

> **No Riot API key required.** Everything is read locally from your own client; image
> art comes from the public Community Dragon CDN. Nothing is uploaded anywhere.

> 🇪🇬 **بتقرأ عربى؟** فيه شرح كامل بالمصرى في [آخر الصفحة](#arabic-full) ⬇️

![ChromaScout — the "Worth Unlocking" view: essence balances, shards with their on-sale chromas, unlock costs, and affordability](screenshot.png)

---

## Why this exists

The Blue Essence Emporium is a limited-time event. Its chroma offers are **randomized per
patch with no public preview**, so the only reliable source of "what's on sale right now"
is your own client.

A chroma can only be bought if you **own its base skin**. If a skin is sitting in your loot
as an *unlocked shard*, the practical question is:

> *"Which of my shards are worth unlocking, because once I own the skin I could immediately
> buy its chroma with Blue Essence?"*

This tool answers exactly that:

```
answer = { skin shards in your loot }  ∩  { skins whose chroma is on BE sale now }
```

---

## What it shows

- **Your skin shards**, with each one's unlock cost (Orange Essence) and skin value (RP).
- **Which shards have a chroma on Blue Essence sale**, how many, and the price.
- **Your essence balances** (Orange = unlocks shards, Blue = buys chromas).
- **How many shards your Orange Essence can unlock right now** (cheapest-first), and how
  much more you'd need for the rest.
- A **visual HTML report** with two tabs:
  - **⚒ Worth Unlocking** — shard cards with their on-sale chroma thumbnails, unlock cost,
    value, an "affordable now" badge, and sorting (by # chromas, value, unlock cost, or
    affordability).
  - **★ My Skins** — a big-splash gallery of every skin you already own.

---

## Quick start (non-technical — just want the answer)

1. Download **`EmporiumChromaFinder.bat`** from the [Releases](../../releases) page.
2. Open the **League of Legends client** and log in (reach the home screen).
3. Double-click **`EmporiumChromaFinder.bat`**.

That's it. If Python isn't installed it will offer to install it for you. When it finishes,
a browser tab opens with your report, and all files are saved next to the `.bat`.

> Windows SmartScreen may show *"Windows protected your PC"* for a `.bat` →
> **More info → Run anyway**. The file is plain text — you can open it in Notepad to inspect it.

---

## Run from source (developers / auditors)

Requirements: **Windows**, **Python 3.8+**, a **running League client**.

```bash
python be_chroma_finder.py
```

`requests` is auto-installed if missing; if that fails it falls back to the standard-library
`urllib`, so there are effectively no hard dependencies.

To (re)build the single distributable `.bat` from the source files:

```bash
python build_bat.py        # -> EmporiumChromaFinder.bat
```

### Files

| File | Role |
|------|------|
| `be_chroma_finder.py` | Main program: connects to the client, reads loot/essence/skins, finds BE chromas, matches, prints tables, writes data. |
| `make_webpage.py` | Builds the standalone HTML report from the saved data. Imported by the finder, or run alone: `python make_webpage.py`. |
| `build_bat.py` | Bundles the two scripts into one self-contained `EmporiumChromaFinder.bat`. |

---

## How it works

### 1. Connecting to the client (LCU API)
The League client exposes a local REST API (the **LCU API**) on `https://127.0.0.1:<port>`
with HTTP Basic auth (`riot` / token) and a self-signed certificate. The tool gets the port
and token from the **lockfile** (searched across every drive and common install paths), and
falls back to reading them from the `LeagueClientUx.exe` process arguments
(`--app-port`, `--remoting-auth-token`).

### 2. Reading your shards
`GET /lol-loot/v1/player-loot` → entries with `type == "SKIN_RENTAL"` are skin **shards**
(not yet unlocked). Each carries the skin id (`storeItemId`), name, the Orange Essence
unlock cost (`upgradeEssenceValue`), and RP value.

### 3. Finding the Blue Essence chromas — the key insight
The Emporium feeds the **regular store catalog**: `GET /lol-store/v1/catalog`. In this
catalog, **`IP` is Blue Essence** (the legacy "Influence Points" name). Chromas are entries
with `inventoryType == "CHAMPION_SKIN"` and `subInventoryType == "RECOLOR"`.

The important subtlety: a chroma's normal `prices` block usually shows only the **RP** price.
The **Blue Essence price lives in the `sale` block** (`sale.prices`) — that's the Emporium
discount. So the tool checks **both** places, and when the BE price comes from a sale it
verifies *today is inside the sale's start/end window*. Each chroma's `itemRequirements`
names the base skin you must own — that's the join key against your shards.

### 4. Essence & affordability
Balances come from the loot `CURRENCY` entries: `CURRENCY_cosmetic` = Orange Essence,
`CURRENCY_champion` = Blue Essence. Unlock counts are computed greedily (cheapest shard first).

### 5. The report art
Image URLs are derived from **Community Dragon** (public, keyless, CORS-friendly):
- Chroma icon: `…/v1/champion-chroma-images/{championId}/{chromaId}.png`
- Skin splash: from `skins.json` paths (`/lol-game-data/assets/...` → CDN base, lowercased)

### 6. The single-file `.bat`
`build_bat.py` embeds both Python files after a marker inside a batch launcher. At runtime
the launcher locates Python (or installs it via `winget`), unpacks the embedded scripts to
`%TEMP%`, and runs them. Output is written next to the `.bat` (or your home folder if that
location is read-only).

---

## Output files

All written to the folder the tool runs from (or `%USERPROFILE%\EmporiumChromaFinder` as a fallback):

| File | Contents |
|------|----------|
| `chroma_report.html` | The visual report (open this). |
| `run_log.txt` | Detailed run log — attach this when reporting a problem. |
| `lcu_dump/ANSWER_matches.json` | The shard→chroma matches (with image ids). |
| `lcu_dump/my_skin_shards.json` | Your shards + unlock costs/values. |
| `lcu_dump/emporium_be_chromas.json` | Every chroma on BE sale this rotation. |
| `lcu_dump/*.json` | Raw dumps (loot, store catalog, owned skins) for verification. |

---

## Privacy & safety

- **Local only.** The tool talks to `127.0.0.1` (your own client) and reads public art from
  Community Dragon. It does **not** send your data anywhere.
- **No credentials stored.** The LCU token is read live and used only for the local session.
- **The output files contain your account data** (summoner name, owned skins, loot). They are
  git-ignored by default — don't commit `lcu_dump/`, `chroma_report.html`, or `run_log.txt`.
- This is a read-only tool: it never disenchants, purchases, or modifies anything in your account.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| "Could not find the League client" / "Connection refused" | Client is closed or still loading. Open it, reach the home screen, run again. |
| "401 Unauthorized" | The session token changed — restart the client and rerun. |
| "404" on an endpoint | Riot moved it in a patch. Open an issue with your `run_log.txt`. |
| "Could not unpack the embedded finder" (`.bat`) | You ran it from *inside* the zip. Extract first, then run the `.bat`. |
| `winget` not available | Install Python from python.org and tick **Add python.exe to PATH**, then rerun. |
| Empty shard list | You have no skin shards in loot right now (or you opened them all). |

---

## Disclaimer

This project is **not affiliated with, endorsed by, or sponsored by Riot Games**. League of
Legends and all related assets are property of Riot Games, Inc. It only reads data the client
already exposes locally and does not automate gameplay. Use at your own discretion.

## License

[MIT](LICENSE) — do whatever you like; no warranty.

---

<a id="arabic-full"></a>
<div dir="rtl" align="right">

# 🇪🇬 بالمصرى — الشرح الكامل

<p>أداة صغيرة على الويندوز بتقرا <b>كلاينت League of Legends</b> اللى شغّال عندك، وبتقولك أنهى <b>سكنات عندك على شكل Shards</b> تستاهل تفتحها دلوقتى — عشان <b>الكروما بتاعتها معروضة بالـ Blue Essence</b> فى الـ Emporium حاليًا.</p>

<p>وبعدين بتعملك صفحة HTML شيك (بصور الكروما)، وبتوريك رصيدك من الإسنس البرتقانى والأزرق، وبتحسبلك تقدر تفتح كام Shard فعليًا.</p>

<blockquote><b>مش محتاج أى Riot API key.</b> كل حاجة بتتقرا محليًا من الكلاينت بتاعك؛ الصور بس بتيجى من سيرفر Community Dragon العام. مفيش أى حاجة بتترفع لأى مكان.</blockquote>

<h2>ليه الأداة دى موجودة</h2>

<p>الـ Blue Essence Emporium حدث لفترة محدودة. عروض الكروما بتاعته <b>بتتعمل عشوائى كل باتش ومن غير أى preview</b>، فالمصدر الوحيد الموثوق لـ"إيه المعروض دلوقتى" هو الكلاينت بتاعك انت.</p>

<p>الكروما مينفعش تشتريها غير لو إنت <b>مالِك السكن الأساسى</b>. ولو السكن لسه عندك Shard مفتوحش، السؤال العملى:</p>

<blockquote><i>"أفتح أنهى Shard، عشان أول ما أملك السكن أقدر على طول أشترى الكروما بتاعته بالـ Blue Essence؟"</i></blockquote>

<p>والأداة بتجاوب على ده بالظبط:</p>

<pre><code>الإجابة = { الـ Shards اللى فى اللوت بتاعك }  ∩  { السكنات اللى كرومتها معروضة بالـ BE دلوقتى }</code></pre>

<h2>بتوريك إيه</h2>

<ul>
<li><b>الـ Shards بتاعتك</b>، وكل واحد بتكلفة فتحه (إسنس برتقانى) وقيمة السكن (RP).</li>
<li><b>أنهى Shards ليها كروما معروضة بالـ Blue Essence</b>، وعددها، وسعرها.</li>
<li><b>رصيدك من الإسنس</b> (برتقانى = بيفتح الـ Shards، أزرق = بيشترى الكروما).</li>
<li><b>تقدر تفتح كام Shard برصيدك دلوقتى</b> (بيبدأ بالأرخص)، وفاضلك كام عشان الباقى.</li>
<li><b>صفحة HTML</b> فيها تبويبين:
  <ul>
  <li><b>⚒ تستاهل تفتحها</b> — كروت للـ Shards فيها صور الكروما المعروضة، تكلفة الفتح، القيمة، علامة "تقدر تشتريها دلوقتى"، وترتيب (بعدد الكروما، أو القيمة، أو التكلفة، أو المقدور عليه).</li>
  <li><b>★ سكناتى</b> — معرض بصور كبيرة لكل السكنات اللى انت مالكها.</li>
  </ul>
</li>
</ul>

<h2>التشغيل السريع (لو عايز النتيجة بس)</h2>

<ol>
<li>نزّل ملف <b>EmporiumChromaFinder.bat</b> من صفحة الـ <a href="../../releases">Releases</a>.</li>
<li>افتح كلاينت اللعبة وسجّل دخول لحد الشاشة الرئيسية.</li>
<li>اعمل <b>دبل-كليك</b> على <b>EmporiumChromaFinder.bat</b>.</li>
</ol>

<p>وخلاص. لو Python مش متسطّب هيعرض يسطّبه لك. أول ما يخلّص هيفتح تبويب فى المتصفح بالنتيجة، وكل الملفات بتتحفظ جنب الـ .bat.</p>

<blockquote>ويندوز ممكن يطلّع <i>"Windows protected your PC"</i> لأى ملف ‎.bat → دوس <b>More info ← Run anyway</b>. الملف نص عادى تقدر تفتحه بالـ Notepad وتطمّن.</blockquote>

<h2>التشغيل من السورس (للمطوّرين / المراجعين)</h2>

<p>المتطلبات: <b>ويندوز</b>، <b>Python 3.8+</b>، و<b>كلاينت شغّال</b>.</p>

<pre><code>python be_chroma_finder.py</code></pre>

<p>مكتبة <code>requests</code> بتتسطّب لوحدها لو مش موجودة؛ ولو فشل بيرجع لـ<code>urllib</code> المدمجة، فعمليًا مفيش أى dependencies إجبارية.</p>

<p>عشان تبنى ملف الـ ‎.bat الواحد من ملفات السورس:</p>

<pre><code>python build_bat.py        # ‎-> EmporiumChromaFinder.bat</code></pre>

<h3>الملفات</h3>

<table>
<tr><th>الملف</th><th>دوره</th></tr>
<tr><td><code>be_chroma_finder.py</code></td><td>البرنامج الأساسى: بيتصل بالكلاينت، بيقرا اللوت/الإسنس/السكنات، بيلاقى كروما الـ BE، بيطابق، بيطبع الجداول، بيحفظ الداتا.</td></tr>
<tr><td><code>make_webpage.py</code></td><td>بيبنى صفحة الـ HTML من الداتا المحفوظة. بيتستدعى من البرنامج الأساسى، أو لوحده: <code>python make_webpage.py</code>.</td></tr>
<tr><td><code>build_bat.py</code></td><td>بيجمّع السكريبتين فى ملف <code>EmporiumChromaFinder.bat</code> واحد مكتفى بذاته.</td></tr>
</table>

<h2>بيشتغل إزاى</h2>

<h3>١. الاتصال بالكلاينت (LCU API)</h3>
<p>الكلاينت بيعرض REST API محلى (الـ <b>LCU API</b>) على <code>https://127.0.0.1:&lt;port&gt;</code> بـ HTTP Basic auth (<code>riot</code> / token) وشهادة self-signed. الأداة بتجيب الـ port والـ token من الـ <b>lockfile</b> (بتدوّر عليه فى كل البارتشنات وأماكن التثبيت الشائعة)، ولو ملقتهوش بترجع تقراهم من arguments بتاعة عملية <code>LeagueClientUx.exe</code> (<code>--app-port</code> و <code>--remoting-auth-token</code>).</p>

<h3>٢. قراية الـ Shards</h3>
<p><code>GET /lol-loot/v1/player-loot</code> ← العناصر اللى <code>type == "SKIN_RENTAL"</code> دى الـ <b>Shards</b> (لسه مفتوحتش). كل واحد فيه id السكن (<code>storeItemId</code>)، الاسم، تكلفة الفتح بالإسنس البرتقانى (<code>upgradeEssenceValue</code>)، وقيمة الـ RP.</p>

<h3>٣. لقا كروما الـ Blue Essence — النقطة المهمة</h3>
<p>الـ Emporium بيغذّى <b>كتالوج المتجر العادى</b>: <code>GET /lol-store/v1/catalog</code>. فى الكتالوج ده <b><code>IP</code> = Blue Essence</b> (الاسم القديم "Influence Points"). الكروما عناصر <code>inventoryType == "CHAMPION_SKIN"</code> و<code>subInventoryType == "RECOLOR"</code>.</p>
<p>النقطة الدقيقة: بلوك <code>prices</code> العادى بتاع الكروما بيبيّن سعر الـ <b>RP</b> بس عادةً. سعر الـ <b>Blue Essence موجود فى بلوك <code>sale</code></b> (<code>sale.prices</code>) — ده خصم الـ Emporium. فالأداة بتشيك على <b>الاتنين</b>، ولما السعر ييجى من sale بتتأكد إن <i>النهاردة جوّه فترة العرض</i>. و<code>itemRequirements</code> بتاعة كل كروما بتقول السكن الأساسى اللى لازم تملكه — ده مفتاح الربط مع الـ Shards بتاعتك.</p>

<h3>٤. الإسنس والمقدور عليه</h3>
<p>الأرصدة بتيجى من عناصر <code>CURRENCY</code> فى اللوت: <code>CURRENCY_cosmetic</code> = إسنس برتقانى، <code>CURRENCY_champion</code> = إسنس أزرق. عدد اللى تقدر تفتحه بيتحسب بطريقة جشعة (الأرخص الأول).</p>

<h3>٥. صور التقرير</h3>
<p>روابط الصور بتتكوّن من <b>Community Dragon</b> (عام، من غير key، وبيشتغل من المتصفح):</p>
<ul>
<li>أيقونة الكروما: <code>…/v1/champion-chroma-images/{championId}/{chromaId}.png</code></li>
<li>سبلاش السكن: من مسارات <code>skins.json</code> (<code>/lol-game-data/assets/...</code> ← قاعدة الـ CDN، بحروف صغيرة).</li>
</ul>

<h3>٦. ملف الـ .bat الواحد</h3>
<p><code>build_bat.py</code> بيدمج ملفّى البايثون بعد marker جوّه launcher batch. وقت التشغيل الـ launcher بيلاقى Python (أو بيسطّبه بالـ <code>winget</code>)، بيفك السكريبتات المدمجة فى <code>%TEMP%</code>، وبيشغّلها. الخرج بيتكتب جنب الـ .bat (أو فى فولدر الهوم بتاعك لو المكان read-only).</p>

<h2>ملفات الخرج</h2>

<p>كله بيتكتب فى الفولدر اللى الأداة شغّالة منه (أو <code>%USERPROFILE%\EmporiumChromaFinder</code> كبديل):</p>

<table>
<tr><th>الملف</th><th>المحتوى</th></tr>
<tr><td><code>chroma_report.html</code></td><td>التقرير المرئى (افتح ده).</td></tr>
<tr><td><code>run_log.txt</code></td><td>لوج مفصّل — ابعته لو فيه مشكلة.</td></tr>
<tr><td><code>lcu_dump/ANSWER_matches.json</code></td><td>مطابقات الـ Shard ← كروما (بأرقام الصور).</td></tr>
<tr><td><code>lcu_dump/my_skin_shards.json</code></td><td>الـ Shards بتاعتك + التكلفة/القيمة.</td></tr>
<tr><td><code>lcu_dump/emporium_be_chromas.json</code></td><td>كل الكروما المعروضة بالـ BE الروتيشن ده.</td></tr>
<tr><td><code>lcu_dump/*.json</code></td><td>نسخ خام (لوت، كتالوج، سكنات مملوكة) للتأكيد.</td></tr>
</table>

<h2>الخصوصية والأمان</h2>

<ul>
<li><b>محلى بس.</b> الأداة بتكلّم <code>127.0.0.1</code> (الكلاينت بتاعك) وبتقرا صور عامة من Community Dragon. <b>مش بتبعت بياناتك</b> لأى مكان.</li>
<li><b>مفيش credentials بتتخزّن.</b> الـ token بيتقرا لايف ويُستخدم للجلسة المحلية بس.</li>
<li><b>ملفات الخرج فيها بيانات حسابك</b> (اسم السمونر، السكنات، اللوت). دى متجاهَلة فى git افتراضيًا — متعملش commit لـ<code>lcu_dump/</code> أو <code>chroma_report.html</code> أو <code>run_log.txt</code>.</li>
<li>دى أداة قراية بس: عمرها ما بتفك أو تشترى أو تغيّر أى حاجة فى حسابك.</li>
</ul>

<h2>حل المشاكل</h2>

<table>
<tr><th>العَرَض</th><th>السبب / الحل</th></tr>
<tr><td>"Could not find the League client" / "Connection refused"</td><td>الكلاينت مقفول أو لسه بيحمّل. افتحه، وصّل للشاشة الرئيسية، وجرّب تانى.</td></tr>
<tr><td>"401 Unauthorized"</td><td>الـ token اتغيّر — اقفل الكلاينت وافتحه وجرّب تانى.</td></tr>
<tr><td>"404" على endpoint</td><td>ريوت غيّرته فى باتش. افتح issue ومعاه <code>run_log.txt</code>.</td></tr>
<tr><td>"Could not unpack the embedded finder" (‎.bat)</td><td>شغّلته من جوّه الـ zip. فك الضغط الأول، وبعدين شغّل الـ .bat.</td></tr>
<tr><td><code>winget</code> مش موجود</td><td>سطّب Python من python.org وحطّ علامة <b>Add python.exe to PATH</b>، وبعدين جرّب تانى.</td></tr>
<tr><td>قايمة Shards فاضية</td><td>مفيش عندك Shards دلوقتى (أو فتحتهم كلهم).</td></tr>
</table>

<h2>إخلاء مسؤولية</h2>

<p>المشروع ده <b>مش تابع لريوت جيمز ولا معتمَد منها ولا برعايتها</b>. League of Legends وكل أصولها ملك Riot Games, Inc. الأداة بتقرا بس داتا الكلاينت بيعرضها محليًا أصلًا، ومبتعملش أتمتة للّعب. استخدمها على مسؤوليتك.</p>

<h2>الترخيص</h2>

<p><a href="LICENSE">MIT</a> — اعمل اللى انت عايزه؛ من غير أى ضمان.</p>

</div>
