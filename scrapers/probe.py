#!/usr/bin/env python3
"""OBA səhifələmə + Wolt Bakı filial siyahısı (data/probe/probe3.txt)."""
import re, json
from pathlib import Path
import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "probe"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "az"}
log = []
def L(*a):
    s = " ".join(str(x) for x in a); log.append(s); print(s)
def get(url, **kw):
    try:
        return requests.get(url, headers={**H, **kw.pop("headers", {})}, timeout=30, **kw)
    except Exception as e:
        L("ERR", url, e)

# ── OBA ──
def cards(t):
    return re.findall(r'<h3[^>]*>([^<]+)</h3>.*?<p class="color-mako[^>]*>([^<]*)</p>.*?<span class="fs-lg-24 fs-20 lh-24 fw-400">([\d.,]+)</span>', t, re.S)
r0 = get("https://oba.az/products/")
c0 = cards(r0.text)
L("oba page1 cards:", len(c0), c0[:2])
t = r0.text
i = t.find("more-products")
L("more-products snippet:", re.sub(r"\s+", " ", t[i - 200:i + 700]))
L("pagination-ish:", re.findall(r'(?:data-page|data-url|data-next|load-more|loadmore)[^>]{0,120}', t)[:8])
types = re.findall(r'/products/\?type=([0-9a-f\-]{36})', t)
L("category types:", len(types))
for q in ("page=2", "p=2", "pg=2", "pageNum=2", "start=24"):
    r = get("https://oba.az/products/?" + q)
    if r is not None:
        c = cards(r.text)
        L(f"?{q}: {r.status_code} cards={len(c)} same_as_p1={c == c0} first={c[:1]}")
for ty in types[:2]:
    r = get(f"https://oba.az/products/?type={ty}")
    if r is not None:
        c = cards(r.text); L(f"type {ty[:8]}: cards={len(c)} cats={sorted(set(x[1] for x in c))[:3]}")
    r = get(f"https://oba.az/products/?type={ty}&page=2")
    if r is not None:
        c = cards(r.text); L(f"type {ty[:8]} page2: cards={len(c)} first={c[:1]}")
for u in ("https://oba.az/products/?ajax=1&page=2", "https://oba.az/products/page2", "https://oba.az/products/page-2/"):
    r = get(u, headers={"X-Requested-With": "XMLHttpRequest"})
    if r is not None: L(u, r.status_code, len(r.text), len(cards(r.text)))

# ── Wolt Bakı filialları ──
WH = {"Accept": "application/json", "Origin": "https://wolt.com", "Referer": "https://wolt.com/"}
found = {}
for url in ("https://consumer-api.wolt.com/v1/pages/restaurants?lat=40.4093&lon=49.8671",
            "https://consumer-api.wolt.com/v1/pages/shops?lat=40.4093&lon=49.8671",
            "https://consumer-api.wolt.com/v1/pages/search?q=rahat&lat=40.4093&lon=49.8671",
            "https://restaurant-api.wolt.com/v1/pages/shops?lat=40.4093&lon=49.8671",
            "https://consumer-api.wolt.com/v1/pages/delivery?lat=40.4093&lon=49.8671"):
    r = get(url, headers=WH)
    if r is None: continue
    L("wolt", r.status_code, len(r.text), url)
    if r.status_code == 200:
        txt = r.text
        for m in re.finditer(r'"slug":"([a-z0-9\-]+)"', txt):
            found[m.group(1)] = 1
        (OUT / ("wolt_" + re.sub(r"\W+", "_", url[30:90]) + ".json")).write_text(txt[:200000], encoding="utf-8")
for name in ("rahat", "araz", "oba", "neptun", "bravo"):
    L(name, "slugs:", sorted(s for s in found if name in s)[:20])
(OUT / "probe3.txt").write_text("\n".join(log), encoding="utf-8")
