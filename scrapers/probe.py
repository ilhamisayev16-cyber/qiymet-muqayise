#!/usr/bin/env python3
"""Araz saytının kataloq strukturunu yoxlayır (nəticə data/probe/araz_catalog.txt)."""
import re, json
from pathlib import Path
import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "probe"
OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "az"}
BASE = "https://arazmarket.az"
API = "https://b7x9kq.arazmarket.az"
log = []
def L(*a):
    s = " ".join(str(x) for x in a); log.append(s); print(s)

home = requests.get(BASE + "/az", headers=H, timeout=30).text.replace('\\"', '"')
slugs = sorted(set(re.findall(r'"category_slug":"([^"]+)"', home)))
L("category slugs:", len(slugs), slugs[:15])
L("all hrefs:", sorted(set(re.findall(r'href="(/az/[^"#?]{2,80})"', home)))[:60])

def probe(url, **kw):
    try:
        r = requests.get(url, headers={**H, **kw.get("headers", {})}, timeout=30, params=kw.get("params"))
        txt = r.text.replace('\\"', '"')
        n = len(re.findall(r'"sales_price"', txt))
        L(f"{r.status_code} {len(txt):>8}B products={n:<4} ct={r.headers.get('content-type','')[:30]} {r.url}")
        return r, txt
    except Exception as e:
        L("ERR", url, e)
        return None, ""

s = slugs[0] if slugs else "sud"
for path in [f"/az/category/{s}", f"/az/categories/{s}", f"/az/catalog/{s}", f"/az/products?category={s}",
             f"/az/products", f"/az/search?q=s%C3%BCd", f"/az/campaigns", f"/az/basket"]:
    r, txt = probe(BASE + path)
    if r is not None and r.status_code == 200 and "sales_price" in txt:
        (OUT / ("araz_" + re.sub(r"\W+", "_", path) + ".html")).write_text(txt[:150000], encoding="utf-8")
for path in ["/api/products", "/api/v1/products", "/api/categories", "/api/v1/categories", "/api/home",
             "/api/v1/home", "/api/campaigns", "/api/search?q=s%C3%BCd", "/api/v1/search?q=s%C3%BCd",
             "/api/v1/products?category_id=1180", "/api/products?category_id=1180"]:
    r, txt = probe(API + path, headers={"Accept": "application/json", "Origin": BASE, "Referer": BASE + "/"})
    if r is not None and r.status_code == 200:
        (OUT / ("araz_api_" + re.sub(r"\W+", "_", path) + ".json")).write_text(txt[:60000], encoding="utf-8")
(OUT / "araz_catalog.txt").write_text("\n".join(log), encoding="utf-8")
