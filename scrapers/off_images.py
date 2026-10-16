"""Məhsul şəkilləri Open Food Facts-dən (açıq məhsul bazası, şəkillər CC BY-SA 3.0), ştrix-koda görə.

Scraper Wolt məhsullarına "gtin" (ştrix-kod) yazır. Bu skript onu prices.json-da "im"-ə çevirir: OFF-dakı ön şəklin yolu,
məs. "476/009/510/1025/front_az.3" (sayt https://images.openfoodfacts.org/images/products/<im>.200.jpg göstərir), sonra
"gtin" silinir. OFF-da şəkli olmayan məhsulda "im" yoxdur, sayt ikon göstərir. Mağazanın/Wolt-un şəkli istifadə olunmur.

Keş: data/off_images.json {gtin: [yol və ya "", "YYYY-MM-DD"]}. Tapılmayanlar RECHECK_DAYS gündən sonra yenidən soruşulur.
Bir şəkli saytdan götürmək lazım olsa (etiraz): həmin gtin-i ["", "9999-12-31"] et, bir daha soruşulmur və göstərilmir.
"""
import json, os, re, sys, time
from datetime import date, timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICES = os.path.join(ROOT, "data", "prices.json")
CACHE = os.path.join(ROOT, "data", "off_images.json")
API = "https://search.openfoodfacts.org/search"
UA = "harda-ucuz/1.0 (https://github.com/ilhamisayev16-cyber/harda-ucuz)"
BATCH = 100
RECHECK_DAYS = 30
BUDGET = int(os.environ.get("OFF_BUDGET_SEC", "1500"))   # vaxt bitərsə qalanı növbəti gün (scrape-i ləngitməsin)
LANGS = ("az", "en", "ru", "tr")
IM_RX = re.compile(r"^\d{3}/\d{3}/\d{3}/\d+/front_[a-z]{2,3}\.\d+$")   # index.html də eyni yoxlamanı edir


def folder(code):
    """OFF şəkil qovluğu: 13 rəqəmə qədər soldan 0, sonra 3/3/3/qalan."""
    c = code.zfill(13)
    return f"{c[:3]}/{c[3:6]}/{c[6:9]}/{c[9:]}"


def front(code, images):
    """Ön şəklin yolu (200 px ölçüsü olan); dil sırası LANGS, sonra istənilən front_*. Yoxdursa ""."""
    fr = {k[6:]: v for k, v in (images or {}).items() if k.startswith("front_") and isinstance(v, dict)}
    for lang in [l for l in LANGS if l in fr] + sorted(l for l in fr if l not in LANGS):
        v = fr[lang]
        rev = str(v.get("rev") or "")
        if rev.isdigit() and "200" in (v.get("sizes") or {}) and re.fullmatch(r"[a-z]{2,3}", lang):
            im = f"{folder(code)}/front_{lang}.{rev}"
            if IM_RX.match(im): return im
    return ""


def lookup(ses, codes):
    """{gtin: yol} — OFF axtarışı, bir sorğuda BATCH kod. Cavabda olmayan kod = şəkil yoxdur."""
    r = None
    for attempt in range(4):
        try:
            r = ses.get(API, params={"q": "code:(" + " OR ".join(codes) + ")", "fields": "code,images",
                                     "page_size": len(codes)}, timeout=60)
            if r.status_code == 200: break
        except requests.RequestException:
            r = None
        time.sleep(5 * (attempt + 1))
    if r is None or r.status_code != 200: return None
    out = {c: "" for c in codes}
    for p in r.json().get("hits") or []:
        c = str(p.get("code") or "")
        if c in out: out[c] = front(c, p.get("images"))
    return out


def run():
    with open(PRICES, encoding="utf-8") as f: data = json.load(f)
    try:
        with open(CACHE, encoding="utf-8") as f: cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    today = date.today().isoformat()
    stale = (date.today() - timedelta(days=RECHECK_DAYS)).isoformat()
    items = [it for c in data["categories"].values() for l in c["stores"].values() for it in l if it.get("gtin")]
    need = sorted({it["gtin"] for it in items if it["gtin"] not in cache or (not cache[it["gtin"]][0] and cache[it["gtin"]][1] < stale)})
    print(f"[OFF] ştrix-kodlu məhsul: {len(items)}, soruşulacaq kod: {len(need)}", flush=True)
    ses = requests.Session(); ses.headers["User-Agent"] = UA
    t0, done = time.time(), 0
    for i in range(0, len(need), BATCH):
        if time.time() - t0 > BUDGET:
            print(f"[OFF] vaxt bitdi, qalan {len(need) - i} kod növbəti dəfə", flush=True); break
        res = lookup(ses, need[i:i + BATCH])
        if res is None:
            print("[OFF] axtarış cavab vermir, növbəti dəfə", flush=True); break
        for c, im in res.items(): cache[c] = [im, today]
        done += len(res)
        time.sleep(1)
    n = 0
    for c in data["categories"].values():
        for l in c["stores"].values():
            for it in l:
                g = it.pop("gtin", None)
                if g is None: continue
                im = (cache.get(g) or [""])[0]
                if im: it["im"] = im; n += 1
                else: it.pop("im", None)
    with open(PRICES + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))   # scraper.py ilə eyni format
    os.replace(PRICES + ".tmp", PRICES)
    with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dict(sorted(cache.items())), f, separators=(",", ":"))
        f.write("\n")
    os.replace(CACHE + ".tmp", CACHE)
    hit = sum(1 for v in cache.values() if v[0])
    print(f"[OFF] soruşuldu {done}; keşdə {len(cache)} kod, {hit} şəkilli; şəkilli məhsul {n}/{len(items)}", flush=True)


if __name__ == "__main__":
    sys.exit(run())
