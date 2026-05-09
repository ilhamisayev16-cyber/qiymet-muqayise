#!/usr/bin/env python3
"""
QiymətMüqayisə Scraper
  Bravo  -> birmarket.az API
  OBA    -> oba-we-api / oba.az fallback
  Araz   -> Wolt  (sayt bloklayır)
  Neptun -> Wolt
  Rahat  -> Wolt

İstifadə:
  python scraper.py
  python scraper.py --store bravo
  python scraper.py --store oba
"""
import json, re, time, argparse
from datetime import datetime
from pathlib import Path

CATEGORIES = {
    "sud":       {"name":"Süd",              "kw":["süd","milk"],
                  "excl":["şokolad","kakao","qatıq","kefir","ayran","xama","soya"]},
    "yumurta":   {"name":"Yumurta",          "kw":["yumurta"]},
    "kere_yagi": {"name":"Kərə yağı",        "kw":["kərə yağ","butter"]},
    "pendir":    {"name":"Pendir",           "kw":["pendir"]},
    "qatiq":     {"name":"Qatıq/Yoqurt",     "kw":["qatıq","yoqurt","yogurt"],
                  "excl":["içki","şirə","dadlı"]},
    "xama":      {"name":"Xama",             "kw":["xama","smetana"]},
    "kefir":     {"name":"Kefir",            "kw":["kefir"]},
    "ayran":     {"name":"Ayran",            "kw":["ayran"]},
    "kartof":    {"name":"Kartof",           "kw":["kartof"]},
    "pomidor":   {"name":"Pomidor",          "kw":["pomidor","tomat"],
                  "excl":["pasta","sous","ketçup","şirəsi","suyu","konserv"]},
    "xiyar":     {"name":"Xiyar",            "kw":["xiyar"],"excl":["turşu"]},
    "soyan":     {"name":"Soğan",            "kw":["soğan","soyan"]},
    "kelem":     {"name":"Kələm",            "kw":["kələm","kapusta"]},
    "yerkoyu":   {"name":"Yerkökü",          "kw":["yerkökü","morkov"]},
    "cuqundur":  {"name":"Çuğundur",         "kw":["çuğundur","svekla"]},
    "badimcan":  {"name":"Badımcan",         "kw":["badımcan"]},
    "biber":     {"name":"Bibər",            "kw":["bibər"],"excl":["sous","pasta","turşu"]},
    "sarimsaq":  {"name":"Sarımsaq",         "kw":["sarımsaq"]},
    "alma":      {"name":"Alma",             "kw":["alma"],
                  "excl":["şirəsi","suyu","nektarı","ətirli","dadlı","mors","sirkə"]},
    "armud":     {"name":"Armud",            "kw":["armud"],"excl":["şirəsi","suyu","dadlı"]},
    "saftal":    {"name":"Şaftalı",          "kw":["şaftalı","nektarin"],"excl":["şirəsi","dadlı"]},
    "gilas":     {"name":"Gilas/Albalı",     "kw":["gilas","albalı"],"excl":["şirəsi","dadlı"]},
    "uzum":      {"name":"Üzüm",             "kw":["üzüm"],
                  "excl":["şirəsi","suyu","sirkə","şərab","kişmiş","dadlı"]},
    "banan":     {"name":"Banan",            "kw":["banan"],"excl":["dadlı","çip"]},
    "kivi":      {"name":"Kivi",             "kw":["kivi"],"excl":["dadlı"]},
    "limon":     {"name":"Limon",            "kw":["limon"],"excl":["dadlı","limonad"]},
    "portaqal":  {"name":"Portağal",         "kw":["portağal","portakal"],"excl":["şirəsi","suyu","dadlı"]},
    "nar":       {"name":"Nar",              "kw":["nar"],"excl":["şirəsi","suyu","dadlı"]},
    "toyuq":     {"name":"Toyuq",            "kw":["toyuq","cücə","broylyer"]},
    "dana_ati":  {"name":"Dana əti",         "kw":["dana"]},
    "qoyun_ati": {"name":"Qoyun/Quzu əti",   "kw":["qoyun","quzu"]},
    "hindi":     {"name":"Hindi",            "kw":["hindi"]},
    "kolbasa":   {"name":"Kolbasa",          "kw":["kolbasa","salam"],"excl":["sosis"]},
    "sosis":     {"name":"Sosis",            "kw":["sosis","sosiska"]},
    "baliq":     {"name":"Balıq",            "kw":["balıq","tuna","skumbriya","losos"]},
    "duyu":      {"name":"Düyü",             "kw":["düyü","pirinc"]},
    "merci":     {"name":"Mərcimək",         "kw":["mərcimək"]},
    "noxud":     {"name":"Noxud",            "kw":["noxud"]},
    "fasulya":   {"name":"Fasulya",          "kw":["fasulya","lobya"]},
    "qarabashaq":{"name":"Qarabaşaq",        "kw":["qarabaşaq","grechka"]},
    "yulaf":     {"name":"Yulaf",            "kw":["yulaf","ovsyanka"]},
    "un":        {"name":"Un",               "kw":["buğda unu","ali növ un","birinci növ un","çovdar unu"]},
    "makaron":   {"name":"Makaron",          "kw":["makaron","spagetti","vermişel"]},
    "corek":     {"name":"Çörək",            "kw":["çörək","lavaş"]},
    "pecenye":   {"name":"Peçenye/Biskvit",  "kw":["peçenye","biskvit","kraker","vafli"]},
    "cay":       {"name":"Çay",              "kw":["çay","lipton","ahmad"],"excl":["çaydan"]},
    "qehve":     {"name":"Qəhvə",            "kw":["qəhvə","nescafe","lavazza"]},
    "sire":      {"name":"Şirə/Mors/Nektar", "kw":["şirəsi","şirə","mors","nektar",
                                                    "meyvə suyu","alma suyu","portağal suyu"]},
    "su":        {"name":"Su",               "kw":["mineral su","içməli su","mənbə suyu"]},
    "kola":      {"name":"Kola/Limonad",     "kw":["kola","limonad","pepsi","fanta","sprite"]},
    "energetik": {"name":"Energetik",        "kw":["red bull","monster","burn ","hell energy"]},
    "sokolad":   {"name":"Şokolad",          "kw":["şokolad"]},
    "halva":     {"name":"Halva/Konfet",     "kw":["halva","konfet","karamel","marmelad"]},
    "bal":       {"name":"Bal",              "kw":["təbii bal","çiçək balı","bal "]},
    "dondurma":  {"name":"Dondurma",         "kw":["dondurma","plombir"]},
    "zeytun_yagi":{"name":"Zeytun yağı",     "kw":["zeytun yağ"]},
    "bitki_yagi":{"name":"Bitki yağı",       "kw":["günəbaxan yağ","ayçiçəyi yağ","bitki yağ"]},
    "mayonez":   {"name":"Mayonez",          "kw":["mayonez"]},
    "ketcup":    {"name":"Ketçup/Sous",      "kw":["ketçup","ketchup","tomat sousu"]},
    "duz":       {"name":"Duz",              "kw":["duz"]},
    "sekerqum":  {"name":"Şəkər",            "kw":["şəkər"]},
    "istiot":    {"name":"İstiot/Ədviyyat",  "kw":["istiot","ədviyyat","zirə","darçın"]},
}

ALL_STORES = ["Bravo","OBA","Araz","Neptun","Rahat"]

WOLT_SLUGS = {
    "Bravo":  "bravo-supermarket-globus-centre",
    "OBA":    "oba-market-nerimanov-1",
    "Araz":   "araz-supermarket-narimanov",
    "Neptun": "neptun-supermarket-28",
    "Rahat":  "rahat-supermarket-heydar-aliyev",
}

JUICE_WORDS = ["şirəsi","suyu","nektarı","mors","şərbəti","kompot","içkisi",
               "limonadı","ətirli dadlı","dadlı"]

def clean_price(raw):
    if raw is None: return None
    s = re.sub(r"[^\d,.]", "", str(raw)).replace(",",".")
    m = re.search(r"\d+\.?\d*", s)
    if not m: return None
    v = float(m.group())
    return round(v, 2) if 0.05 < v < 9999 else None

def has_juice(name):
    n = name.lower()
    return any(w in n for w in JUICE_WORDS)

def assign_cat(name):
    n = name.lower()
    if has_juice(n):
        return "sire"
    for cid, info in CATEGORIES.items():
        if any(e.lower() in n for e in info.get("excl",[])):
            continue
        if any(kw.lower() in n for kw in info["kw"]):
            return cid
    return None

def sim(a, b):
    wa = set(re.sub(r"[^\w\s]","",a.lower()).split())
    wb = set(re.sub(r"[^\w\s]","",b.lower()).split())
    if not wa or not wb: return 0
    return len(wa & wb) / max(len(wa), len(wb))

def empty_data():
    return {
        "last_updated": "",
        "stores": ALL_STORES,
        "categories": {
            cid: {"name": info["name"], "stores": {s: [] for s in ALL_STORES}}
            for cid, info in CATEGORIES.items()
        }
    }

# ── BRAVO — birmarket.az ──────────────────────────────────────────────────
def scrape_bravo():
    import requests
    results = {c: [] for c in CATEGORIES}
    seen = set()
    total = 0
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124",
        "Accept": "application/json",
        "Referer": "https://birmarket.az/",
        "Origin": "https://birmarket.az",
    })

    # Known working endpoints (try each)
    endpoints = [
        ("https://api.birmarket.az/api/v3/products", {"category_id": 4497}),
        ("https://api.birmarket.az/api/v2/products", {"category_id": 4497}),
        ("https://api.birmarket.az/api/v1/products", {"category_id": 4497}),
        ("https://birmarket.az/api/v3/products",     {"category_id": 4497}),
    ]

    base_url = None
    base_params = {}
    for url, params in endpoints:
        try:
            r = session.get(url, params={**params, "page":1,"per_page":4}, timeout=12)
            if r.status_code == 200:
                d = r.json()
                items = _extract_list(d)
                if items:
                    base_url, base_params = url, params
                    print(f"  [Bravo] ✓ endpoint tapıldı: {url}")
                    break
        except Exception:
            continue

    if not base_url:
        print("  [Bravo] ✗ birmarket.az API cavab vermir — Wolt istifadə ediləcək")
        return results, False  # signal to use Wolt

    page, per = 1, 48
    while True:
        try:
            r = session.get(base_url, params={**base_params,"page":page,"per_page":per}, timeout=20)
            if r.status_code != 200: break
            d = r.json()
            items = _extract_list(d)
            if not items: break
            for p in items:
                name = (p.get("name") or p.get("title") or p.get("nameAz") or "")
                if not name: continue
                pid = str(p.get("id") or name)
                if pid in seen: continue
                price = clean_price(p.get("price") or p.get("sell_price") or
                                    p.get("current_price") or p.get("discounted_price"))
                if price is None: continue
                seen.add(pid); total += 1
                cat = assign_cat(name)
                if cat: results[cat].append({"name": name, "price": price})
            print(f"  [Bravo] səhifə {page} — {total} məhsul", end="\r")
            last = (d.get("data",{}).get("last_page") or d.get("last_page") or
                    d.get("meta",{}).get("last_page"))
            if (last and page >= int(last)) or len(items) < per: break
            page += 1; time.sleep(0.25)
        except Exception as e:
            print(f"\n  [Bravo] xəta: {e}"); break

    print(f"\n  [Bravo] ✓ {total} məhsul (birmarket.az)")
    return results, total > 0

def _extract_list(d):
    if isinstance(d, list) and d: return d
    for k in ["products","items","data","result","results","content"]:
        v = d.get(k)
        if isinstance(v, list) and v: return v
        if isinstance(v, dict):
            for k2 in ["products","items","data"]:
                v2 = v.get(k2)
                if isinstance(v2, list) and v2: return v2
    return []

# ── OBA ──────────────────────────────────────────────────────────────────
OBA_API = "https://oba-we-api-p-app-01.azurewebsites.net/api/v1/obaPlus/catalog/products"

def scrape_oba():
    import requests
    results = {c: [] for c in CATEGORIES}
    heads = {"User-Agent":"okhttp/4.9.2","Accept":"application/json",
             "Accept-Encoding":"gzip","accept-language":"az"}
    page, ps, total = 1, 50, 0
    print("  [OBA] tətbiq API…", end="", flush=True)
    while True:
        try:
            r = requests.get(OBA_API,
                params={"page":page,"pageSize":ps,"sortBy":0,"descending":"false"},
                headers=heads, timeout=30)
            if r.status_code == 401:
                print("\n  [OBA] 401 → web fallback")
                return _oba_web()
            if r.status_code != 200: break
            d = r.json()
            items = _extract_list(d) or _extract_list(d.get("data",{}))
            if not items: break
            for p in items:
                name = (p.get("name") or p.get("productName") or p.get("nameAz") or "")
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
            page += 1; time.sleep(0.3)
        except Exception as e:
            print(f"\n  [OBA] xəta: {e}"); break
    print(f"\n  [OBA] ✓ {total} məhsul")
    return results if total > 0 else _oba_web()

def _oba_web():
    import requests
    from bs4 import BeautifulSoup
    results = {c: [] for c in CATEGORIES}
    heads = {"User-Agent":"Mozilla/5.0","Accept-Language":"az"}
    total = 0
    print("  [OBA] oba.az web scrape…")
    for pg in range(1, 400):
        try:
            r = requests.get(f"https://oba.az/az/products/?page={pg}", headers=heads, timeout=30)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text,"html.parser")
            cards = soup.select(".product-card,.product-item,[class*='product']")
            if not cards: break
            found = 0
            for c in cards:
                ne = c.select_one("[class*='name'],[class*='title'],h3,h4")
                pe = c.select_one("[class*='price']")
                if not ne or not pe: continue
                name = ne.get_text(strip=True)
                price = clean_price(pe.get_text(strip=True))
                if not name or price is None: continue
                found += 1; total += 1
                cat = assign_cat(name)
                if cat: results[cat].append({"name":name,"price":price})
            if found == 0: break
            print(f"  [OBA/web] s.{pg}: {found} məhsul", end="\r")
            time.sleep(0.35)
        except Exception as e:
            print(f"\n  [OBA/web] xəta: {e}"); break
    print(f"\n  [OBA/web] ✓ {total} məhsul")
    return results

# ── WOLT ─────────────────────────────────────────────────────────────────
WOLT_HEADS = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
    "Content-Type":"application/json",
    "Origin":"https://wolt.com",
    "Referer":"https://wolt.com/",
}

def scrape_wolt(store):
    import requests
    slug = WOLT_SLUGS.get(store)
    if not slug: return {}
    results = {c: [] for c in CATEGORIES}
    seen = set()
    url = (f"https://consumer-api.wolt.com/consumer-api/consumer-assortment"
           f"/v1/venues/slug/{slug}/assortment/items/search?language=az")
    queries = list({info["kw"][0] for info in CATEGORIES.values()})
    print(f"  [Wolt/{store}]", end="", flush=True)
    for q in queries:
        try:
            r = requests.post(url, headers=WOLT_HEADS, json={"q":q}, timeout=15)
            if r.status_code != 200: continue
            items = r.json().get("items") or []
            for item in items:
                name = item.get("name","")
                if isinstance(name, dict): name = name.get("az") or name.get("en") or ""
                price = None
                for k in ["price","baseprice","unit_price"]:
                    v = item.get(k)
                    if isinstance(v,dict): v = v.get("amount") or v.get("value")
                    if isinstance(v,(int,float)) and v>0: price = round(v/100,2); break
                if not name or price is None: continue
                uid = name.lower().strip()
                if uid in seen: continue
                seen.add(uid)
                cat = assign_cat(name)
                if cat: results[cat].append({"name":name,"wolt_price":price})
        except Exception:
            pass
        time.sleep(0.15)
    total = sum(len(v) for v in results.values())
    print(f" {total} məhsul")
    return results

# ── BİRLƏŞDİRMƏ ──────────────────────────────────────────────────────────
def merge_own_wolt(own_list, wolt_list):
    merged = []
    used = set()
    for item in own_list:
        entry = {"name": item["name"], "price": item["price"]}
        best_s, best_i = 0, -1
        for i, w in enumerate(wolt_list):
            s = sim(item["name"], w["name"])
            if s > best_s: best_s, best_i = s, i
        if best_s >= 0.5 and best_i >= 0:
            wp = wolt_list[best_i]["wolt_price"]
            if abs(wp - item["price"]) > 0.005:
                entry["wolt_price"] = wp
            used.add(best_i)
        merged.append(entry)
    # Wolt-only items
    for i, w in enumerate(wolt_list):
        if i not in used:
            merged.append({"name": w["name"], "wolt_price": w["wolt_price"]})
    return merged

def apply_to_data(own_res, wolt_res, store, data):
    wolt_only = store in ("Neptun","Rahat")
    for cid in CATEGORIES:
        if wolt_only:
            items = [{"name":w["name"],"wolt_price":w["wolt_price"]}
                     for w in wolt_res.get(cid,[])]
        else:
            items = merge_own_wolt(own_res.get(cid,[]), wolt_res.get(cid,[]))
        data["categories"][cid]["stores"][store] = items

# ── MAIN ─────────────────────────────────────────────────────────────────
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
        if "stores" not in data: data["stores"] = ALL_STORES
        for cid, info in CATEGORIES.items():
            if cid not in data["categories"]:
                data["categories"][cid] = {"name":info["name"],"stores":{s:[] for s in ALL_STORES}}
    else:
        data = empty_data()

    name_map = {"bravo":"Bravo","oba":"OBA","araz":"Araz","neptun":"Neptun","rahat":"Rahat"}
    targets = list(name_map.keys()) if args.store=="all" else [args.store]

    for t in targets:
        sname = name_map[t]
        print(f"\n{'─'*50}\n  {sname}\n{'─'*50}")
        own_res, wolt_res = {}, {}

        # Own source
        if not args.wolt_only:
            if sname == "Bravo":
                own_res, ok = scrape_bravo()
                if not ok:
                    print("  [Bravo] birmarket.az işləmədi → Wolt-dan çəkilir")
                    wolt_res = scrape_wolt("Bravo")
                    apply_to_data({}, wolt_res, "Bravo", data)
                    continue
            elif sname == "OBA":
                own_res = scrape_oba()
            # Araz, Neptun, Rahat — öz saytları yoxdur/bloklayır → Wolt
            elif sname in ("Araz","Neptun","Rahat"):
                pass  # goes straight to Wolt below

        # Wolt
        if not args.own_only:
            wolt_res = scrape_wolt(sname)

        apply_to_data(own_res, wolt_res, sname, data)

    data["last_updated"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out,"w",encoding="utf-8") as f:
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
