#!/usr/bin/env python3
"""
QiymətMüqayisə — Tam Scraper v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ÖZ MƏNBƏLƏR:
  Bravo  → birmarket.az (bütün kateqoriyalar, çoxlu API cəhdləri)
  OBA    → oba-we-api-p-app-01.azurewebsites.net  +  oba.az fallback
  Araz   → arazmarket.az (Playwright, network intercept)

WOLT (hamısı):
  Bravo, OBA, Araz, Neptun, Rahat

NƏTICƏ → data/prices.json

İSTİFADƏ:
  python scraper.py                  → hamısı
  python scraper.py --store bravo    → yalnız Bravo
  python scraper.py --wolt-only      → yalnız Wolt
  python scraper.py --own-only       → yalnız öz mənbələr
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json, re, time, argparse, sys
from datetime import datetime
from pathlib import Path

# ─── Kateqoriyalar ─────────────────────────────────────────────────────────
CATEGORIES = {
    "sud":         {"name":"Süd",             "kw":["süd","milk"],"excl":["şokolad","soya","kakao","qatıq","kefir","ayran","xama"]},
    "yumurta":     {"name":"Yumurta",         "kw":["yumurta"]},
    "kere_yagi":   {"name":"Kərə yağı",       "kw":["kərə yağ","butter"]},
    "pendir":      {"name":"Pendir",          "kw":["pendir"]},
    "qatiq":       {"name":"Qatıq / Yoqurt",  "kw":["qatıq","yoqurt","yogurt"],"excl":["içki","şirə"]},
    "xama":        {"name":"Xama",            "kw":["xama"]},
    "kefir":       {"name":"Kefir",           "kw":["kefir"]},
    "ayran":       {"name":"Ayran",           "kw":["ayran"]},
    "kartof":      {"name":"Kartof",          "kw":["kartof"]},
    "pomidor":     {"name":"Pomidor",         "kw":["pomidor","tomat"],"excl":["pasta","sous","ketçup","ketchup","şirəsi","suyu"]},
    "xiyar":       {"name":"Xiyar",           "kw":["xiyar"],"excl":["turşu"]},
    "soyan":       {"name":"Soğan",           "kw":["soğan","soyan"]},
    "kelem":       {"name":"Kələm",           "kw":["kələm","kelem","kapusta"]},
    "yerkoyu":     {"name":"Yerkökü",         "kw":["yerkökü","yerkoku"]},
    "cuqundur":    {"name":"Çuğundur",        "kw":["çuğundur","cugundur","svekla"]},
    "qabaq":       {"name":"Qabaq",           "kw":["qabaq"],"excl":["toxum","yağ","şirə"]},
    "badimcan":    {"name":"Badımcan",        "kw":["badımcan","badimcan"]},
    "biber":       {"name":"Bibər",           "kw":["bibər","biber"],"excl":["sous","pasta","turşu"]},
    "sarimsaq":    {"name":"Sarımsaq",        "kw":["sarımsaq","sarimsaq"]},
    "ispanaq":     {"name":"İspanaq",         "kw":["ispanaq"]},
    "alma":        {"name":"Alma",            "kw":["alma"],"excl":["şirə","suyu","nektarı","ətirli","dadlı","mors","kompot"]},
    "armud":       {"name":"Armud",           "kw":["armud"],"excl":["şirə","suyu","nektarı","ətirli","dadlı"]},
    "saftal":      {"name":"Şaftalı",         "kw":["şaftalı","nektarin"],"excl":["şirə","suyu","nektarı","ətirli","dadlı"]},
    "gilas":       {"name":"Gilas / Albalı",  "kw":["gilas","albalı"],"excl":["şirə","suyu","nektarı","ətirli","dadlı","qatıq","yoqurt"]},
    "uzum":        {"name":"Üzüm",            "kw":["üzüm"],"excl":["şirəsi","suyu","nektarı","ətirli","dadlı","sirkə","şərab","kişmiş"]},
    "banan":       {"name":"Banan",           "kw":["banan"],"excl":["şirə","suyu","dadlı","ətirli","çip"]},
    "kivi":        {"name":"Kivi",            "kw":["kivi"],"excl":["şirə","suyu","dadlı","ətirli"]},
    "limon":       {"name":"Limon",           "kw":["limon"],"excl":["şirə","suyu","dadlı","ətirli","şərbət","limonad"]},
    "portaqal":    {"name":"Portağal",        "kw":["portağal","portakal"],"excl":["şirə","suyu","nektarı","ətirli","dadlı","limonad"]},
    "nar":         {"name":"Nar",             "kw":["nar"],"excl":["şirəsi","suyu","nektarı","ətirli","dadlı","mors"]},
    "toyuq":       {"name":"Toyuq",           "kw":["toyuq","cücə","broyle"],"excl":["sous","marinad","hazır"]},
    "dana_ati":    {"name":"Dana əti",        "kw":["dana"]},
    "qoyun_ati":   {"name":"Qoyun əti",       "kw":["qoyun","quzu"]},
    "hindi":       {"name":"Hindi əti",       "kw":["hindi"]},
    "kolbasa":     {"name":"Kolbasa",         "kw":["kolbasa","salam"],"excl":["sosis","sosiska"]},
    "sosis":       {"name":"Sosis",           "kw":["sosis","sosiska"]},
    "baliq":       {"name":"Balıq",           "kw":["balıq","tuna","skumbriya","losos","qızılbalıq"]},
    "duyu":        {"name":"Düyü",            "kw":["düyü","pirinc"]},
    "merci":       {"name":"Mərcimək",        "kw":["mərcimək","merci"]},
    "noxud":       {"name":"Noxud",           "kw":["noxud"]},
    "fasulya":     {"name":"Fasulya / Lobya", "kw":["fasulya","lobya"]},
    "qarabashaq":  {"name":"Qarabaşaq",       "kw":["qarabaşaq","grechka"]},
    "yulaf":       {"name":"Yulaf",           "kw":["yulaf","ovsyanka"]},
    "un":          {"name":"Un",              "kw":["buğda unu","çovdar unu","birinci növ un","ikinci növ un","ali növ un"]},
    "makaron":     {"name":"Makaron",         "kw":["makaron","spagetti","vermişel","penne","fettuccine"]},
    "corek":       {"name":"Çörək",           "kw":["çörək","lavaş"]},
    "pecenye":     {"name":"Peçenye / Biskvit","kw":["peçenye","biskvit","kraker","vafli"]},
    "cay":         {"name":"Çay",             "kw":["çay","lipton","ahmad","tea"],"excl":["çaydan"]},
    "qehve":       {"name":"Qəhvə",           "kw":["qəhvə","nescafe","lavazza","coffee","café"]},
    "sire":        {"name":"Şirə / Mors / Nektar","kw":["şirəsi","şirə","mors","nektar","meyvə suyu","alma suyu","portağal suyu","üzüm suyu","nar suyu","gilas suyu","albalı suyu"]},
    "su":          {"name":"Su",              "kw":["mineral su","içməli su","mənbə suyu","damacana"]},
    "kola":        {"name":"Kola / Limonad",  "kw":["kola","limonad","pepsi","fanta","sprite","schweppes","7up"]},
    "energetik":   {"name":"Energetik içki",  "kw":["red bull","monster","burn ","hell energy","energy drink","adrenaline"]},
    "sokolad":     {"name":"Şokolad",         "kw":["şokolad","chocolate"]},
    "halva":       {"name":"Halva / Konfet",  "kw":["halva","konfet","karamel","marmelad","lolipop"]},
    "bal":         {"name":"Bal",             "kw":["bal ","bal,","təbii bal","çiçək balı"]},
    "dondurma":    {"name":"Dondurma",        "kw":["dondurma","eskimo","plombir"]},
    "zeytun_yagi": {"name":"Zeytun yağı",     "kw":["zeytun yağ","olive oil"]},
    "ay_cicayi":   {"name":"Günəbaxan / Bitki yağı","kw":["günəbaxan yağ","ayçiçəyi yağ","bitki yağ","rafine yağ"]},
    "mayonez":     {"name":"Mayonez",         "kw":["mayonez"]},
    "ketcup":      {"name":"Ketçup / Sous",   "kw":["ketçup","ketchup","tomat sousu","domates salçası"]},
    "xardal":      {"name":"Xardal",          "kw":["xardal"]},
    "duz":         {"name":"Duz",             "kw":["duz"]},
    "sekerqum":    {"name":"Şəkər",           "kw":["şəkər","saxaroza"]},
    "istiot":      {"name":"İstiot / Ədviyyat","kw":["istiot","ədviyyat","zirə","darçın","mixək","muskat"]},
}

WOLT_VENUES = {
    "Bravo":  "bravo-supermarket-globus-centre",
    "OBA":    "oba-market-nerimanov-1",
    "Araz":   "araz-supermarket-narimanov",
    "Neptun": "neptun-supermarket-28",
    "Rahat":  "rahat-supermarket-heydar-aliyev",
}
ALL_STORES = ["Bravo", "OBA", "Araz", "Neptun", "Rahat"]

JUICE_SUFFIXES = ["şirəsi","suyu","nektarı","nektari","mors","şərbəti","kompot",
                  "içkisi","limonadı","ətirli","dadlı","dadli"]

# ─── Utils ──────────────────────────────────────────────────────────────────
def clean_price(raw) -> float | None:
    if raw is None: return None
    s = str(raw).replace("₼","").replace("\xa0","").replace(" ","").replace(",",".").strip()
    m = re.search(r"(\d+\.?\d*)", s)
    v = float(m.group(1)) if m else None
    return round(v, 2) if v and 0.05 < v < 9999 else None

def has_juice_suffix(name: str) -> bool:
    n = name.lower()
    return any(s in n for s in JUICE_SUFFIXES)

def assign_cat(name: str) -> str | None:
    n = name.lower()
    if has_juice_suffix(n):
        return "sire"
    for cat_id, info in CATEGORIES.items():
        excl = info.get("excl", [])
        if any(e.lower() in n for e in excl):
            continue
        if any(kw.lower() in n for kw in info["kw"]):
            return cat_id
    return None

def similarity(a: str, b: str) -> float:
    wa = set(re.sub(r"[^\w\s]","",a.lower()).split())
    wb = set(re.sub(r"[^\w\s]","",b.lower()).split())
    if not wa or not wb: return 0
    return len(wa & wb) / max(len(wa), len(wb))

def empty_data() -> dict:
    return {
        "last_updated": "",
        "stores": ALL_STORES,
        "categories": {
            cid: {"name": info["name"], "stores": {s: [] for s in ALL_STORES}}
            for cid, info in CATEGORIES.items()
        }
    }

# ══════════════════════════════════════════════════════════════════
#  BRAVO — birmarket.az
# ══════════════════════════════════════════════════════════════════
BRAVO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "az,en;q=0.9",
    "Origin": "https://birmarket.az",
    "Referer": "https://birmarket.az/",
}

# Known birmarket.az category IDs for food
BRAVO_CATEGORY_IDS = [
    4497,   # Dukan / Ərzaq
    4498, 4499, 4500, 4501, 4502, 4503, 4504, 4505,
    4506, 4507, 4508, 4509, 4510, 4511, 4512, 4513,
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    100, 101, 102, 103, 104, 105,
]

def _bravo_fetch_page(session, url: str, params: dict) -> list:
    """Try to extract product list from any response structure."""
    import requests
    try:
        r = session.get(url, params=params, headers=BRAVO_HEADERS, timeout=25)
        if r.status_code != 200:
            return []
        d = r.json()
    except Exception:
        return []

    # Try common structures
    if isinstance(d, list): return d
    for key in ["products","items","data","result","results","content"]:
        v = d.get(key)
        if isinstance(v, list) and v: return v
        if isinstance(v, dict):
            for k2 in ["products","items","data","result"]:
                v2 = v.get(k2)
                if isinstance(v2, list) and v2: return v2
    return []

def scrape_bravo_own() -> dict:
    import requests
    results = {cat: [] for cat in CATEGORIES}
    seen = set()
    session = requests.Session()
    total = 0

    print("  [Bravo] birmarket.az API axtarılır…")

    # ── Strategy 1: search-based (one query per category) ──
    search_url = "https://api.birmarket.az/api/v3/products/search"
    search_url2 = "https://api.birmarket.az/api/v1/products/search"
    search_urls = [search_url, search_url2,
                   "https://birmarket.az/api/v3/products/search",
                   "https://birmarket.az/api/products/search"]

    search_queries = list({info["kw"][0] for info in CATEGORIES.values()})
    strategy1_ok = False

    for surl in search_urls:
        try:
            r = session.get(surl, params={"q": search_queries[0], "page": 1, "per_page": 5},
                            headers=BRAVO_HEADERS, timeout=15)
            if r.status_code == 200 and r.json():
                print(f"  [Bravo] Search endpoint tapıldı: {surl}")
                strategy1_ok = True
                # Scrape all queries
                for q in search_queries:
                    page = 1
                    while True:
                        items = _bravo_fetch_page(session, surl, {"q": q, "page": page, "per_page": 50})
                        if not items: break
                        for p in items:
                            name = (p.get("name") or p.get("title") or
                                    p.get("product_name") or p.get("nameAz") or "")
                            if not name: continue
                            pid = str(p.get("id") or name)
                            if pid in seen: continue
                            price = clean_price(
                                p.get("price") or p.get("sell_price") or
                                p.get("current_price") or p.get("discounted_price") or
                                p.get("salePrice") or p.get("basePrice"))
                            if price is None: continue
                            seen.add(pid); total += 1
                            cat = assign_cat(name)
                            if cat: results[cat].append({"name": name, "price": price})
                        if len(items) < 50: break
                        page += 1
                        time.sleep(0.2)
                break
        except Exception:
            continue

    if not strategy1_ok:
        # ── Strategy 2: category pagination ──
        product_urls = [
            "https://api.birmarket.az/api/v3/products",
            "https://api.birmarket.az/api/v2/products",
            "https://api.birmarket.az/api/v1/products",
            "https://birmarket.az/api/v3/products",
            "https://birmarket.az/api/products",
        ]
        for cat_id in BRAVO_CATEGORY_IDS:
            found_url = None
            for purl in product_urls:
                items = _bravo_fetch_page(session, purl,
                    {"category_id": cat_id, "page": 1, "per_page": 1})
                if items:
                    found_url = purl
                    break
            if not found_url:
                continue
            print(f"  [Bravo] kateqoriya {cat_id}…", end="", flush=True)
            page = 1
            while True:
                items = _bravo_fetch_page(session, found_url,
                    {"category_id": cat_id, "page": page, "per_page": 48})
                if not items: break
                n_added = 0
                for p in items:
                    name = (p.get("name") or p.get("title") or
                            p.get("product_name") or p.get("nameAz") or "")
                    if not name: continue
                    pid = str(p.get("id") or name)
                    if pid in seen: continue
                    price = clean_price(
                        p.get("price") or p.get("sell_price") or
                        p.get("current_price") or p.get("discounted_price") or
                        p.get("salePrice") or p.get("basePrice"))
                    if price is None: continue
                    seen.add(pid); total += 1; n_added += 1
                    cat = assign_cat(name)
                    if cat: results[cat].append({"name": name, "price": price})
                print(f" p{page}({n_added})", end="", flush=True)
                if len(items) < 48: break
                page += 1
                time.sleep(0.3)
            print()

    # ── Strategy 3: Playwright fallback ──
    if total < 50:
        print("  [Bravo] Playwright fallback cəhdi…")
        results = _bravo_playwright(results, seen)
    else:
        print(f"  [Bravo] ✓ {total} məhsul tapıldı (öz sayt)")

    return results

def _bravo_playwright(results: dict, seen: set) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [Bravo] Playwright yoxdur")
        return results

    food_categories = [
        "https://birmarket.az/az/catalog/erzeq-mehsullari",
        "https://birmarket.az/az/catalog/sud-mehsullari",
        "https://birmarket.az/az/catalog/et-ve-qusbazliq",
        "https://birmarket.az/az/catalog/meyveler-ve-terevezer",
        "https://birmarket.az/az/catalog/icecekler",
        "https://birmarket.az/az/catalog/unlu-mehsullar",
        "https://birmarket.az/az/catalog/sekerleme",
    ]
    total = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 Chrome/124 Safari/537.36",
            locale="az-AZ")
        # Intercept API calls
        captured = []
        def handle_response(response):
            url = response.url
            if "product" in url.lower() or "catalog" in url.lower():
                try:
                    j = response.json()
                    if isinstance(j, list):
                        captured.extend(j)
                    elif isinstance(j, dict):
                        for k in ["products","items","data","result","results"]:
                            v = j.get(k)
                            if isinstance(v, list):
                                captured.extend(v); break
                            if isinstance(v, dict):
                                for k2 in ["products","items"]:
                                    v2 = v.get(k2)
                                    if isinstance(v2, list):
                                        captured.extend(v2); break
                except Exception:
                    pass

        page = ctx.new_page()
        page.on("response", handle_response)

        for url in food_categories:
            try:
                print(f"  [Bravo/PW] {url.split('/')[-1]}…", end="", flush=True)
                captured.clear()
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                for _ in range(8):
                    page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
                    time.sleep(1.2)
                # Try "load more"
                for _ in range(5):
                    try:
                        btn = page.locator("button:has-text('Daha'),button:has-text('Hamısı'),"
                                           "button:has-text('Load'),[class*='load-more']")
                        if btn.count():
                            btn.first.click(); time.sleep(1.5)
                    except Exception:
                        break

                n = 0
                for p in captured:
                    name = (p.get("name") or p.get("title") or p.get("nameAz") or "")
                    if not name: continue
                    pid = str(p.get("id") or name)
                    if pid in seen: continue
                    price = clean_price(
                        p.get("price") or p.get("sell_price") or
                        p.get("current_price") or p.get("discounted_price"))
                    if price is None: continue
                    seen.add(pid); n += 1; total += 1
                    cat = assign_cat(name)
                    if cat: results[cat].append({"name": name, "price": price})

                # DOM fallback if API didn't fire
                if n == 0:
                    cards = page.locator("[class*='product-card'],[class*='ProductCard'],"
                                        "[class*='product-item']").all()
                    for card in cards:
                        try:
                            ne = card.locator("[class*='name'],[class*='title'],h3,h4").first
                            pe = card.locator("[class*='price']").first
                            name = ne.inner_text(timeout=2000).strip()
                            price = clean_price(pe.inner_text(timeout=2000))
                            if not name or price is None: continue
                            uid = name.lower()
                            if uid in seen: continue
                            seen.add(uid); n += 1; total += 1
                            cat = assign_cat(name)
                            if cat: results[cat].append({"name": name, "price": price})
                        except Exception:
                            continue
                print(f" {n}")
            except Exception as e:
                print(f" xəta: {e}")
        browser.close()
    print(f"  [Bravo/PW] ✓ cəmi {total} məhsul")
    return results

# ══════════════════════════════════════════════════════════════════
#  OBA
# ══════════════════════════════════════════════════════════════════
OBA_API = "https://oba-we-api-p-app-01.azurewebsites.net/api/v1/obaPlus/catalog/products"

def scrape_oba_own() -> dict:
    import requests
    results = {cat: [] for cat in CATEGORIES}
    HEADS = {"User-Agent": "okhttp/4.9.2", "Accept": "application/json",
             "Accept-Encoding": "gzip", "accept-language": "az"}
    page, ps = 1, 50
    total = 0
    print("  [OBA] tətbiq API…", end="", flush=True)

    while True:
        try:
            r = requests.get(OBA_API,
                params={"page": page, "pageSize": ps, "sortBy": 0, "descending": "false"},
                headers=HEADS, timeout=30)
            if r.status_code == 401:
                print("\n  [OBA] 401 — web fallback")
                return _oba_web_fallback()
            if r.status_code != 200:
                break
            d = r.json()
            items = (d.get("data", {}).get("products") or
                     d.get("data", {}).get("items") or
                     d.get("products") or d.get("items") or
                     d.get("result") or
                     (d if isinstance(d, list) else []))
            if not items:
                for v in (d.values() if isinstance(d, dict) else []):
                    if isinstance(v, list) and v:
                        items = v; break
            if not items: break

            for p in items:
                name = (p.get("name") or p.get("productName") or
                        p.get("nameAz") or p.get("title") or "")
                price = clean_price(
                    p.get("price") or p.get("sellPrice") or
                    p.get("currentPrice") or p.get("salePrice") or
                    p.get("discountedPrice") or p.get("basePrice"))
                if not name or price is None: continue
                total += 1
                cat = assign_cat(name)
                if cat: results[cat].append({"name": name, "price": price})

            print(f" {page}", end="", flush=True)
            tp = (d.get("data", {}).get("totalPages") or
                  d.get("totalPages") or d.get("pageCount"))
            if (tp and page >= int(tp)) or len(items) < ps: break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"\n  [OBA] xəta: {e}"); break

    print(f"\n  [OBA] ✓ {total} məhsul")
    if total == 0: return _oba_web_fallback()
    return results

def _oba_web_fallback() -> dict:
    import requests
    from bs4 import BeautifulSoup
    results = {cat: [] for cat in CATEGORIES}
    HEADS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "az"}
    total = 0
    print("  [OBA] oba.az web scrape…")
    for pg in range(1, 300):
        r = requests.get(f"https://oba.az/az/products/?page={pg}",
                         headers=HEADS, timeout=30)
        if r.status_code != 200: break
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".product-card,.product-item,[class*='product']")
        if not cards: break
        found = 0
        for c in cards:
            ne = c.select_one("[class*='name'],[class*='title'],h3,h4,a[class*='product']")
            pe = c.select_one("[class*='price']")
            if not ne or not pe: continue
            name = ne.get_text(strip=True)
            price = clean_price(pe.get_text(strip=True))
            if not name or price is None: continue
            found += 1; total += 1
            cat = assign_cat(name)
            if cat: results[cat].append({"name": name, "price": price})
        if found == 0: break
        print(f"    s.{pg}: {found}", end="\r", flush=True)
        time.sleep(0.4)
    print(f"\n  [OBA/web] ✓ {total} məhsul")
    return results

# ══════════════════════════════════════════════════════════════════
#  ARAZ — arazmarket.az (Playwright + network intercept)
# ══════════════════════════════════════════════════════════════════
ARAZ_CAT_SLUGS = [
    "sud-ve-sud-mehlulati-1",
    "et-ve-et-mehsullari-3",
    "meyveler-ve-teravezler-5",
    "icecekler-7",
    "sirin-mehsullar-8",
    "yaglar-ve-sous-9",
    "quru-erzaq-10",
    "balik-ve-deniz-mehsullari-11",
    "unnlu-mehsullar-unlu-confet-6",
    "konservlesdirilmis-mehsullar-1869",
    "sut-mehsullari-112",
    "kolbasa-ve-sosis-113",
]

def scrape_araz_own() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [Araz] Playwright yoxdur")
        return {cat: [] for cat in CATEGORIES}

    results = {cat: [] for cat in CATEGORIES}
    seen = set()
    total = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="az-AZ",
            user_agent="Mozilla/5.0 (Linux; Android 12; Samsung SM-G991B) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/112.0.0.0 Mobile Safari/537.36",
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
        )

        # Intercept JSON API responses from arazmarket
        captured_items = []
        def on_response(resp):
            url = resp.url
            if not ("arazmarket" in url or "araz" in url.lower()): return
            ct = resp.headers.get("content-type","")
            if "json" not in ct: return
            try:
                j = resp.json()
                items = None
                if isinstance(j, list):
                    items = j
                elif isinstance(j, dict):
                    for k in ["products","items","data","result","results","content","list"]:
                        v = j.get(k)
                        if isinstance(v, list) and v:
                            items = v; break
                        if isinstance(v, dict):
                            for k2 in ["products","items","list"]:
                                v2 = v.get(k2)
                                if isinstance(v2, list) and v2:
                                    items = v2; break
                            if items: break
                if items:
                    captured_items.extend(items)
            except Exception:
                pass

        page = ctx.new_page()
        page.on("response", on_response)

        for slug in ARAZ_CAT_SLUGS:
            label = slug.split("-")[0].capitalize()
            print(f"  [Araz] {label}…", end="", flush=True)
            captured_items.clear()
            n = 0

            try:
                page.goto(f"https://www.arazmarket.az/az/categories/{slug}",
                          wait_until="domcontentloaded", timeout=35_000)
                time.sleep(2)

                # Scroll & load more
                prev_count = 0
                for _ in range(20):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.2)
                    # click "load more" if present
                    for sel in ["button:has-text('Daha çox')", "button:has-text('Daha')",
                                "button:has-text('Load more')", "[class*='load-more']",
                                "[class*='show-more']"]:
                        try:
                            b = page.locator(sel)
                            if b.count() > 0:
                                b.first.scroll_into_view_if_needed()
                                b.first.click(); time.sleep(1.5)
                        except Exception:
                            pass
                    curr = page.locator("a[href*='/products/']").count()
                    if curr == prev_count: break
                    prev_count = curr

                # ── Use intercepted JSON first ──
                for item in captured_items:
                    name = (item.get("name") or item.get("productName") or
                            item.get("nameAz") or item.get("title") or
                            (item.get("name_az") if isinstance(item.get("name_az"), str) else None) or "")
                    if isinstance(name, dict):
                        name = name.get("az") or name.get("en") or ""
                    price = clean_price(
                        item.get("price") or item.get("sell_price") or
                        item.get("salePrice") or item.get("currentPrice") or
                        item.get("discountedPrice") or item.get("basePrice") or
                        item.get("sellPrice"))
                    if not name or price is None: continue
                    uid = name.lower().strip()
                    if uid in seen: continue
                    seen.add(uid); n += 1; total += 1
                    cat = assign_cat(name)
                    if cat: results[cat].append({"name": name, "price": price})

                # ── DOM fallback ──
                if n == 0:
                    for card in page.locator("a[href*='/products/']").all():
                        try:
                            lines = [l.strip() for l in card.inner_text().splitlines() if l.strip()]
                            name, price = "", None
                            for line in lines:
                                p = clean_price(line)
                                if p and 0.1 < p < 5000:
                                    if price is None: price = p
                                elif len(line) > len(name) and not re.match(r"^\d", line):
                                    name = line
                            if not name:
                                href = card.get_attribute("href") or ""
                                name = re.sub(r"-\d+$","",href.split("/")[-1]).replace("-"," ").title()
                            if not name or price is None: continue
                            uid = name.lower().strip()
                            if uid in seen: continue
                            seen.add(uid); n += 1; total += 1
                            cat = assign_cat(name)
                            if cat: results[cat].append({"name": name, "price": price})
                        except Exception:
                            continue

                print(f" {n}")
            except Exception as e:
                print(f" xəta: {e}")

        browser.close()
    print(f"  [Araz] ✓ cəmi {total} məhsul")
    return results

# ══════════════════════════════════════════════════════════════════
#  WOLT
# ══════════════════════════════════════════════════════════════════
WOLT_HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Content-Type": "application/json",
    "Origin":       "https://wolt.com",
    "Referer":      "https://wolt.com/",
}

def _wolt_search(slug: str, query: str) -> list:
    import requests
    url = (f"https://consumer-api.wolt.com/consumer-api/consumer-assortment"
           f"/v1/venues/slug/{slug}/assortment/items/search?language=az")
    try:
        r = requests.post(url, headers=WOLT_HEADERS, json={"q": query}, timeout=15)
        if r.status_code != 200: return []
        d = r.json()
        return d.get("items") or d.get("results") or (d if isinstance(d, list) else [])
    except Exception:
        return []

def _wolt_price(item: dict) -> float | None:
    for k in ["price", "baseprice", "unit_price"]:
        v = item.get(k)
        if isinstance(v, dict): v = v.get("amount") or v.get("value")
        if isinstance(v, (int, float)) and v > 0:
            return round(v / 100, 2)
    return None

def _wolt_name(item: dict) -> str:
    n = item.get("name", "")
    if isinstance(n, dict): return n.get("az") or n.get("en") or ""
    return str(n)

def scrape_wolt_store(store: str) -> dict:
    slug = WOLT_VENUES.get(store)
    if not slug: return {}
    results = {cat: [] for cat in CATEGORIES}
    seen = set()
    print(f"  [Wolt/{store}] axtarılır…", end="", flush=True)

    queries = list({info["kw"][0] for info in CATEGORIES.values()})
    for q in queries:
        for item in _wolt_search(slug, q):
            name = _wolt_name(item)
            price = _wolt_price(item)
            if not name or price is None: continue
            uid = name.lower().strip()
            if uid in seen: continue
            seen.add(uid)
            cat = assign_cat(name)
            if cat:
                results[cat].append({"name": name, "wolt_price": price})
        time.sleep(0.15)

    total = sum(len(v) for v in results.values())
    print(f" {total} məhsul")
    return results

# ══════════════════════════════════════════════════════════════════
#  BİRLƏŞDİRMƏ
# ══════════════════════════════════════════════════════════════════
def merge(own: list, wolt: list) -> list:
    merged = []
    used = set()
    for item in own:
        entry = {"name": item["name"], "price": item["price"]}
        best_s, best_i = 0, -1
        for i, w in enumerate(wolt):
            s = similarity(item["name"], w["name"])
            if s > best_s: best_s, best_i = s, i
        if best_s >= 0.5 and best_i >= 0:
            wp = wolt[best_i]["wolt_price"]
            if abs(wp - item["price"]) > 0.005:
                entry["wolt_price"] = wp
            used.add(best_i)
        merged.append(entry)
    for i, w in enumerate(wolt):
        if i not in used:
            merged.append({"name": w["name"], "wolt_price": w["wolt_price"]})
    return merged

def build_data(own: dict, wolt: dict, store: str, data: dict):
    for cat_id in CATEGORIES:
        if store in ("Neptun", "Rahat"):
            items = [{"name": w["name"], "wolt_price": w["wolt_price"]}
                     for w in wolt.get(cat_id, [])]
        else:
            items = merge(own.get(cat_id, []), wolt.get(cat_id, []))
        data["categories"][cat_id]["stores"][store] = items

# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", choices=["bravo","oba","araz","neptun","rahat","all"],
                    default="all")
    ap.add_argument("--wolt-only",  action="store_true")
    ap.add_argument("--own-only",   action="store_true")
    ap.add_argument("--out", default="../data/prices.json")
    args = ap.parse_args()

    out = (Path(__file__).parent / args.out).resolve()
    if out.exists():
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        if "stores" not in data: data["stores"] = ALL_STORES
        for cid, info in CATEGORIES.items():
            if cid not in data["categories"]:
                data["categories"][cid] = {"name": info["name"],
                                           "stores": {s: [] for s in ALL_STORES}}
        print(f"📂  Mövcud data yükləndi: {out}")
    else:
        data = empty_data()

    targets = (["bravo","oba","araz","neptun","rahat"]
               if args.store == "all" else [args.store])
    name_map = {"bravo":"Bravo","oba":"OBA","araz":"Araz",
                "neptun":"Neptun","rahat":"Rahat"}

    for t in targets:
        sname = name_map[t]
        print(f"\n{'═'*56}\n  {sname}\n{'═'*56}")

        own_res, wolt_res = {}, {}

        if not args.wolt_only and sname not in ("Neptun","Rahat"):
            if   sname == "Bravo": own_res = scrape_bravo_own()
            elif sname == "OBA":   own_res = scrape_oba_own()
            elif sname == "Araz":  own_res = scrape_araz_own()

        if not args.own_only:
            wolt_res = scrape_wolt_store(sname)

        build_data(own_res, wolt_res, sname, data)

    data["last_updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅  Saxlandı: {out}  ({out.stat().st_size//1024} KB)")

    print("\n📊  Nəticə:")
    for s in ALL_STORES:
        own_c  = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(s,[]) if "price" in p)
        wolt_c = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(s,[]) if "wolt_price" in p)
        print(f"   {s:8} → öz: {own_c:4}  |  Wolt: {wolt_c:4}")

if __name__ == "__main__":
    main()
