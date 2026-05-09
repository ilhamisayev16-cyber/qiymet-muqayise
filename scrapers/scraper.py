#!/usr/bin/env python3
"""
QiymətMüqayisə — Tam Scraper
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ÖZ MƏNBƏLƏR:
  Bravo  → birmarket.az API
  OBA    → oba-we-api-p-app-01.azurewebsites.net
  Araz   → arazmarket.az (Playwright)

WOLT (hamısı):
  Bravo, OBA, Araz, Neptun, Rahat

NƏTICƏ:
  data/prices.json
  Hər məhsulda: price (öz qiymət) + wolt_price (Wolt qiyməti)
  Neptun/Rahat üçün yalnız wolt_price var

İSTİFADƏ:
  python scraper.py              → hamısı
  python scraper.py --store oba  → yalnız OBA (öz + Wolt)
  python scraper.py --wolt-only  → yalnız Wolt
  python scraper.py --own-only   → yalnız öz mənbələr
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json, re, time, argparse
from datetime import datetime
from pathlib import Path

# ─── Kateqoriya açar sözləri ───────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    "sud":         {"name":"Süd",              "kw":["süd","milk"]},
    "yumurta":     {"name":"Yumurta",          "kw":["yumurta"]},
    "kere_yagi":   {"name":"Kərə yağı",        "kw":["kərə yağ","butter"]},
    "pendir":      {"name":"Pendir",           "kw":["pendir"]},
    "qatiq":       {"name":"Qatıq",            "kw":["qatıq","yoqurt","yogurt"]},
    "xama":        {"name":"Xama",             "kw":["xama"]},
    "kefir":       {"name":"Kefir",            "kw":["kefir"]},
    "ayran":       {"name":"Ayran",            "kw":["ayran"]},
    "kartof":      {"name":"Kartof",           "kw":["kartof"]},
    "pomidor":     {"name":"Pomidor",          "kw":["pomidor","tomat"]},
    "xiyar":       {"name":"Xiyar",            "kw":["xiyar"]},
    "soyan":       {"name":"Soğan",            "kw":["soğan","soyan"]},
    "kelem":       {"name":"Kələm",            "kw":["kələm","kelem","kapusta"]},
    "yerkoyu":     {"name":"Yerkökü",          "kw":["yerkökü","yerkoku"]},
    "cuqundur":    {"name":"Çuğundur",         "kw":["çuğundur","cugundur","svekla"]},
    "qabaq":       {"name":"Qabaq",            "kw":["qabaq"]},
    "badimcan":    {"name":"Badımcan",         "kw":["badımcan","badimcan"]},
    "biber":       {"name":"Bibər",            "kw":["bibər","biber"]},
    "sarimsaq":    {"name":"Sarımsaq",         "kw":["sarımsaq","sarimsaq"]},
    "ispanaq":     {"name":"İspanaq",          "kw":["ispanaq"]},
    "alma":        {"name":"Alma",             "kw":["alma"]},
    "armud":       {"name":"Armud",            "kw":["armud"]},
    "saftal":      {"name":"Şaftalı",          "kw":["şaftalı","nektarin"]},
    "gilas":       {"name":"Gilas",            "kw":["gilas","albalı"]},
    "uzum":        {"name":"Üzüm",             "kw":["üzüm"]},
    "banan":       {"name":"Banan",            "kw":["banan"]},
    "kivi":        {"name":"Kivi",             "kw":["kivi"]},
    "limon":       {"name":"Limon",            "kw":["limon"]},
    "portaqal":    {"name":"Portağal",         "kw":["portağal","portakal"]},
    "nar":         {"name":"Nar",              "kw":["nar"]},
    "toyuq":       {"name":"Toyuq",            "kw":["toyuq","cücə","broyle"]},
    "dana_ati":    {"name":"Dana əti",         "kw":["dana"]},
    "qoyun_ati":   {"name":"Qoyun əti",        "kw":["qoyun","quzu"]},
    "hindi":       {"name":"Hindi",            "kw":["hindi"]},
    "kolbasa":     {"name":"Kolbasa",          "kw":["kolbasa","salam"]},
    "sosis":       {"name":"Sosis",            "kw":["sosis","sosiska"]},
    "baliq":       {"name":"Balıq",            "kw":["balıq","tuna","skumbriya"]},
    "duyu":        {"name":"Düyü",             "kw":["düyü","pirinc"]},
    "merci":       {"name":"Mərcimək",         "kw":["mərcimək","merci"]},
    "noxud":       {"name":"Noxud",            "kw":["noxud"]},
    "fasulya":     {"name":"Fasulya",          "kw":["fasulya","lobya"]},
    "qarabashaq":  {"name":"Qarabaşaq",        "kw":["qarabaşaq","grechka"]},
    "yulaf":       {"name":"Yulaf",            "kw":["yulaf","ovsyanka"]},
    "un":          {"name":"Un",               "kw":[" un ","unun","un,"]},
    "makaron":     {"name":"Makaron",          "kw":["makaron","spagetti","vermişel"]},
    "corek":       {"name":"Çörək",            "kw":["çörək","lavaş"]},
    "pecenye":     {"name":"Peçenye",          "kw":["peçenye","biskvit","kraker","vafli"]},
    "cay":         {"name":"Çay",              "kw":["çay","lipton","ahmad"]},
    "qehve":       {"name":"Qəhvə",            "kw":["qəhvə","nescafe","lavazza"]},
    "sire":        {"name":"Şirə/Mors",        "kw":["şirə","mors","nektar","meyvə suyu"]},
    "su":          {"name":"Su",               "kw":["mineral su","içməli su","mənbə suyu"]},
    "kola":        {"name":"Kola/Limonad",     "kw":["kola","limonad","pepsi","fanta","sprite"]},
    "energetik":   {"name":"Energetik",        "kw":["red bull","monster","energy drink","burn","hell energy"]},
    "sokolad":     {"name":"Şokolad",          "kw":["şokolad"]},
    "halva":       {"name":"Halva/Şirniyyat",  "kw":["halva","konfet","karamel","marmelad"]},
    "bal":         {"name":"Bal",              "kw":["bal ","bal,","bal\n"]},
    "dondurma":    {"name":"Dondurma",         "kw":["dondurma"]},
    "zeytun_yagi": {"name":"Zeytun yağı",      "kw":["zeytun yağ"]},
    "ay_cicayi":   {"name":"Günəbaxan yağı",   "kw":["günəbaxan yağ","ayçiçəyi yağ","bitki yağ"]},
    "mayonez":     {"name":"Mayonez",          "kw":["mayonez"]},
    "ketcup":      {"name":"Ketçup/Sous",      "kw":["ketçup","ketchup"]},
    "xardal":      {"name":"Xardal",           "kw":["xardal"]},
    "duz":         {"name":"Duz",              "kw":["duz"]},
    "sekerqum":    {"name":"Şəkər",            "kw":["şəkər"]},
    "istiot":      {"name":"İstiot/Ədviyyat",  "kw":["istiot","ədviyyat"]},
    "yumurta":     {"name":"Yumurta",          "kw":["yumurta"]},
}

# Wolt venue slug-ları
WOLT_VENUES = {
    "Bravo":   "bravo-supermarket-globus-centre",
    "OBA":     "oba-market-nerimanov-1",
    "Araz":    "araz-supermarket-narimanov",
    "Neptun":  "neptun-supermarket-28",
    "Rahat":   "rahat-supermarket-heydar-aliyev",
}

ALL_STORES = ["Bravo", "OBA", "Araz", "Neptun", "Rahat"]

# ─── Köməkçilər ────────────────────────────────────────────────────────────
def clean_price(raw) -> float | None:
    if raw is None: return None
    s = str(raw).replace("₼","").replace("\xa0","").replace(" ","").replace(",",".").strip()
    m = re.search(r"(\d+\.?\d*)", s)
    return round(float(m.group(1)), 2) if m else None

def assign_cat(name: str) -> str | None:
    n = name.lower()
    for cat_id, info in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in n for kw in info["kw"]):
            return cat_id
    return None

def similar(a: str, b: str) -> float:
    wa = set(re.sub(r"[^\w\s]","",a.lower()).split())
    wb = set(re.sub(r"[^\w\s]","",b.lower()).split())
    if not wa or not wb: return 0
    return len(wa & wb) / max(len(wa), len(wb))

def empty_data() -> dict:
    return {
        "last_updated": "",
        "stores": ALL_STORES,
        "categories": {
            cat_id: {
                "name": info["name"],
                "stores": {s: [] for s in ALL_STORES}
            }
            for cat_id, info in CATEGORY_KEYWORDS.items()
        }
    }

# ═══════════════════════════════════════════════════════════════════════════
#  WOLT scraper
# ═══════════════════════════════════════════════════════════════════════════
WOLT_HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Content-Type": "application/json",
    "Origin":       "https://wolt.com",
    "Referer":      "https://wolt.com/",
}

def wolt_search(venue_slug: str, query: str) -> list:
    import requests
    url = (f"https://consumer-api.wolt.com/consumer-api/consumer-assortment"
           f"/v1/venues/slug/{venue_slug}/assortment/items/search?language=az")
    try:
        r = requests.post(url, headers=WOLT_HEADERS, json={"q": query}, timeout=15)
        if r.status_code != 200:
            return []
        d = r.json()
        return d.get("items") or d.get("results") or (d if isinstance(d, list) else [])
    except Exception:
        return []

def wolt_price(item: dict) -> float | None:
    for k in ["price","baseprice","unit_price"]:
        v = item.get(k)
        if isinstance(v, dict): v = v.get("amount") or v.get("value")
        if isinstance(v, (int,float)) and v > 0:
            return round(v / 100, 2)
    return None

def wolt_name(item: dict) -> str:
    n = item.get("name","")
    if isinstance(n, dict): return n.get("az") or n.get("en") or ""
    return str(n)

def scrape_wolt_store(store_name: str) -> dict:
    """Returns {cat_id: [{name, wolt_price}]}"""
    slug = WOLT_VENUES.get(store_name)
    if not slug:
        return {}
    results = {cat: [] for cat in CATEGORY_KEYWORDS}
    seen = set()

    print(f"  [Wolt/{store_name}] axtarılır…", end="", flush=True)
    queries = set()
    for info in CATEGORY_KEYWORDS.values():
        queries.add(info["kw"][0])

    for q in queries:
        items = wolt_search(slug, q)
        for item in items:
            name  = wolt_name(item)
            price = wolt_price(item)
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


# ═══════════════════════════════════════════════════════════════════════════
#  ÖZ MƏNBƏLƏR
# ═══════════════════════════════════════════════════════════════════════════

# ── Bravo (birmarket.az) ────────────────────────────────────────────────────
def scrape_bravo_own() -> dict:
    import requests
    results = {cat: [] for cat in CATEGORY_KEYWORDS}
    seen = set()
    HEADERS = {"User-Agent":"Mozilla/5.0","Accept":"application/json",
                "Referer":"https://birmarket.az/"}
    page, per = 1, 48
    print("  [Bravo/öz] birmarket.az…", end="", flush=True)
    while True:
        try:
            r = requests.get("https://api.birmarket.az/api/v3/products",
                             params={"category_id":4497,"page":page,"per_page":per},
                             headers=HEADERS, timeout=20)
            if r.status_code != 200: break
            d = r.json()
            items = (d.get("data",{}).get("products") or d.get("products") or
                     d.get("items") or (d if isinstance(d,list) else []))
            if not items: break
            for p in items:
                name = p.get("name") or p.get("title") or ""
                pid  = str(p.get("id") or name)
                if not name or pid in seen: continue
                price = clean_price(p.get("price") or p.get("sell_price") or
                                    p.get("current_price") or p.get("discounted_price"))
                if price is None: continue
                seen.add(pid)
                cat = assign_cat(name)
                if cat: results[cat].append({"name":name,"price":price})
            last = (d.get("data",{}).get("last_page") or d.get("last_page") or
                    d.get("meta",{}).get("last_page"))
            if (last and page >= int(last)) or len(items) < per: break
            print(f" {page}", end="", flush=True)
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"\n  [Bravo/öz] xəta: {e}")
            break
    print()
    print(f"  [Bravo/öz] {sum(len(v) for v in results.values())} məhsul")
    return results

# ── OBA (app API) ────────────────────────────────────────────────────────────
OBA_API = "https://oba-we-api-p-app-01.azurewebsites.net/api/v1/obaPlus/catalog/products"

def scrape_oba_own() -> dict:
    import requests
    results = {cat: [] for cat in CATEGORY_KEYWORDS}
    HEADERS = {"User-Agent":"okhttp/4.9.2","Accept":"application/json",
               "Accept-Encoding":"gzip","accept-language":"az"}
    page, ps = 1, 50
    total = 0
    print("  [OBA/öz] tətbiq API…", end="", flush=True)
    while True:
        try:
            r = requests.get(OBA_API,
                             params={"page":page,"pageSize":ps,"sortBy":0,"descending":"false"},
                             headers=HEADERS, timeout=30)
            if r.status_code == 401:
                print("\n  [OBA/öz] 401 — token lazımdır, keçilir")
                return _oba_web_fallback()
            if r.status_code != 200: break
            d = r.json()
            items = (d.get("data",{}).get("products") or d.get("data",{}).get("items") or
                     d.get("products") or d.get("items") or d.get("result") or
                     (d if isinstance(d,list) else []))
            if not items:
                for v in (d.values() if isinstance(d,dict) else []):
                    if isinstance(v,list) and v: items=v; break
            if not items: break
            for p in items:
                name = (p.get("name") or p.get("productName") or
                        p.get("nameAz") or p.get("title") or "")
                price = clean_price(p.get("price") or p.get("sellPrice") or
                                    p.get("currentPrice") or p.get("salePrice") or
                                    p.get("discountedPrice") or p.get("basePrice"))
                if not name or price is None: continue
                total += 1
                cat = assign_cat(name)
                if cat: results[cat].append({"name":name,"price":price})
            print(f" {page}", end="", flush=True)
            tp = (d.get("data",{}).get("totalPages") or d.get("totalPages") or d.get("pageCount"))
            if (tp and page >= int(tp)) or len(items) < ps: break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"\n  [OBA/öz] xəta: {e}")
            break
    print()
    total2 = sum(len(v) for v in results.values())
    print(f"  [OBA/öz] {total2} məhsul")
    if total2 == 0: return _oba_web_fallback()
    return results

def _oba_web_fallback() -> dict:
    import requests
    from bs4 import BeautifulSoup
    results = {cat: [] for cat in CATEGORY_KEYWORDS}
    HEADERS = {"User-Agent":"Mozilla/5.0","Accept-Language":"az"}
    for pg in range(1, 200):
        r = requests.get(f"https://oba.az/az/products/?page={pg}", headers=HEADERS, timeout=30)
        if r.status_code != 200: break
        soup = BeautifulSoup(r.text,"html.parser")
        items = soup.select(".product-item,[class*='product']")
        if not items: break
        found = 0
        for item in items:
            ne = item.select_one("[class*='name'],[class*='title'],h3,h4")
            pe = item.select_one("[class*='price']")
            if not ne or not pe: continue
            name = ne.get_text(strip=True)
            price = clean_price(pe.get_text(strip=True))
            if not name or price is None: continue
            found += 1
            cat = assign_cat(name)
            if cat: results[cat].append({"name":name,"price":price})
        if found == 0: break
        time.sleep(0.4)
    return results

# ── Araz (Playwright) ────────────────────────────────────────────────────────
ARAZ_CATS = [
    ("sud-ve-sud-mehlulati-1",           "Süd"),
    ("et-ve-et-mehsullari-3",            "Ət"),
    ("meyveler-ve-teravezler-5",         "Meyvə/Tərəvəz"),
    ("icecekler-7",                      "İçəcəklər"),
    ("sirin-mehsullar-8",                "Şirniyyat"),
    ("yaglar-ve-sous-9",                 "Yağlar"),
    ("quru-erzaq-10",                    "Quru ərzaq"),
    ("balik-ve-deniz-mehsullari-11",     "Balıq"),
    ("unnlu-mehsullar-unlu-confet-6",    "Unlu"),
    ("konservlesdirilmis-mehsullar-1869","Konservlər"),
]

def scrape_araz_own() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [Araz/öz] Playwright yoxdur")
        return {cat: [] for cat in CATEGORY_KEYWORDS}

    results = {cat: [] for cat in CATEGORY_KEYWORDS}
    seen = set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(locale="az-AZ",
            user_agent="Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/112 Mobile Safari/537.36")
        pg = ctx.new_page()
        for slug, label in ARAZ_CATS:
            print(f"  [Araz/öz] {label}…", end="", flush=True)
            try:
                pg.goto(f"https://www.arazmarket.az/az/categories/{slug}",
                        wait_until="domcontentloaded", timeout=30_000)
                time.sleep(2)
                prev = 0
                for _ in range(25):
                    pg.evaluate("window.scrollTo(0,document.body.scrollHeight)")
                    time.sleep(1)
                    try:
                        btn = pg.locator("button:has-text('Daha'),button:has-text('Load')")
                        if btn.count() > 0:
                            btn.first.click(); time.sleep(1.5)
                    except Exception: pass
                    curr = pg.locator("a[href*='/products/']").count()
                    if curr == prev: break
                    prev = curr
                found = 0
                for card in pg.locator("a[href*='/products/']").all():
                    try:
                        lines = [l.strip() for l in card.inner_text().splitlines() if l.strip()]
                        name, price = "", None
                        for line in lines:
                            p = clean_price(line)
                            if p and 0.1 < p < 5000:
                                if price is None: price = p
                            elif len(line) > len(name) and not re.match(r"^\d",line):
                                name = line
                        if not name:
                            href = card.get_attribute("href") or ""
                            name = re.sub(r"-\d+$","",href.split("/")[-1]).replace("-"," ").title()
                        if not name or price is None: continue
                        uid = name.lower().strip()
                        if uid in seen: continue
                        seen.add(uid)
                        found += 1
                        cat = assign_cat(name)
                        if cat: results[cat].append({"name":name,"price":price})
                    except Exception: continue
                print(f" {found}")
            except Exception as e:
                print(f" xəta: {e}")
        browser.close()
    print(f"  [Araz/öz] cəmi {sum(len(v) for v in results.values())} məhsul")
    return results


# ═══════════════════════════════════════════════════════════════════════════
#  BİRLƏŞDİRMƏ
# ═══════════════════════════════════════════════════════════════════════════
def merge_own_and_wolt(own: dict, wolt: dict) -> list:
    """
    Öz qiymətlər + Wolt qiymətlərini birləşdir.
    Eyni məhsul varsa — price + wolt_price bir yerdə.
    Yalnız Wolt-da varsa — wolt_price ilə əlavə et.
    """
    merged = []
    used_wolt = set()
    # Əvvəl öz məhsullar
    for item in own:
        entry = {"name": item["name"], "price": item["price"]}
        # Wolt-da oxşar məhsul axtarıq
        best_sim, best_wp = 0, None
        for i, wi in enumerate(wolt):
            s = similar(item["name"], wi["name"])
            if s > best_sim:
                best_sim, best_wp = s, (i, wi["wolt_price"])
        if best_sim >= 0.55 and best_wp:
            wp = best_wp[1]
            if wp != item["price"]:
                entry["wolt_price"] = wp
            used_wolt.add(best_wp[0])
        merged.append(entry)
    # Yalnız Wolt-da olan məhsullar
    for i, wi in enumerate(wolt):
        if i not in used_wolt:
            merged.append({"name": wi["name"], "wolt_price": wi["wolt_price"]})
    return merged

def build_data(own_results: dict, wolt_results: dict, store: str,
               data: dict) -> None:
    """data["categories"][cat]["stores"][store] = [...] ilə doldur"""
    for cat_id in CATEGORY_KEYWORDS:
        own  = own_results.get(cat_id, [])
        wolt = wolt_results.get(cat_id, [])
        if store in ("Neptun","Rahat"):
            # Yalnız Wolt
            items = [{"name": w["name"], "wolt_price": w["wolt_price"]} for w in wolt]
        else:
            items = merge_own_and_wolt(own, wolt)
        if cat_id not in data["categories"]:
            data["categories"][cat_id] = {
                "name": CATEGORY_KEYWORDS[cat_id]["name"],
                "stores": {s: [] for s in ALL_STORES}
            }
        data["categories"][cat_id]["stores"][store] = items


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", choices=["bravo","oba","araz","neptun","rahat","all"], default="all")
    ap.add_argument("--wolt-only",  action="store_true")
    ap.add_argument("--own-only",   action="store_true")
    ap.add_argument("--out", default="../data/prices.json")
    args = ap.parse_args()

    out = (Path(__file__).parent / args.out).resolve()

    if out.exists():
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        # Köhnə strukturda stores açarı yoxdursa əlavə et
        if "stores" not in data:
            data["stores"] = ALL_STORES
        print(f"📂  Mövcud data: {out}")
    else:
        data = empty_data()

    targets = (["bravo","oba","araz","neptun","rahat"]
               if args.store == "all" else [args.store])

    for store in targets:
        sname = store.capitalize() if store not in ("oba","rahat") else store.upper() if store=="oba" else "Rahat"
        sname = {"bravo":"Bravo","oba":"OBA","araz":"Araz",
                 "neptun":"Neptun","rahat":"Rahat"}[store]

        print(f"\n{'═'*54}")
        print(f"  {sname}")
        print(f"{'═'*54}")

        own_res  = {}
        wolt_res = {}

        # ── Öz mənbə ──
        if not args.wolt_only and sname not in ("Neptun","Rahat"):
            if sname == "Bravo":   own_res = scrape_bravo_own()
            elif sname == "OBA":   own_res = scrape_oba_own()
            elif sname == "Araz":  own_res = scrape_araz_own()

        # ── Wolt ──
        if not args.own_only:
            wolt_res = scrape_wolt_store(sname)

        build_data(own_res, wolt_res, sname, data)

    data["last_updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    kb = out.stat().st_size // 1024
    print(f"\n✅  Saxlandı → {out}  ({kb} KB)")

    print("\n📊  Nəticə:")
    for sname in ALL_STORES:
        own_c  = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(sname,[]) if "price" in p)
        wolt_c = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(sname,[]) if "wolt_price" in p)
        print(f"   {sname:8} → öz: {own_c:4}  |  Wolt: {wolt_c:4}")

if __name__ == "__main__":
    main()
