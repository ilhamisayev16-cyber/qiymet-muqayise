#!/usr/bin/env python3
"""Araz kataloq API/səhifələmə probe-u (nəticə data/probe/araz_catalog2.txt)."""
import re, json
from pathlib import Path
import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "probe"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "az"}
BASE, API = "https://arazmarket.az", "https://b7x9kq.arazmarket.az"
log = []
def L(*a):
    s = " ".join(str(x) for x in a); log.append(s); print(s)

def get(url, **kw):
    try:
        return requests.get(url, headers={**H, **kw.pop("headers", {})}, timeout=30, **kw)
    except Exception as e:
        L("ERR", url, e); return None

def ids(txt):
    return re.findall(r'"id":(\d+),"title":"([^"]+)","avg_rating"', txt.replace('\\"', '"'))

slug = "agardicilar-371"
pages = {}
for p in (1, 2, 3):
    r = get(f"{BASE}/az/categories/{slug}", params={"page": p})
    if r is not None:
        pages[p] = ids(r.text)
        L(f"page={p} status={r.status_code} products={len(pages[p])} first={pages[p][:2]}")
L("page1==page2:", pages.get(1) == pages.get(2))
html = get(f"{BASE}/az/categories/{slug}").text
t = html.replace('\\"', '"')
i = t.find('"sales_price"')
L("sample product json:", t[max(0, i - 700): i + 700])
for k in ("current_page", "last_page", "per_page", "total", "links", "meta", "next", "page"):
    m = re.findall(r'"%s":[^,}\]]{0,40}' % k, t)
    if m: L(k, m[:4])

# JS chunk-lardan API yolları
chunks = sorted(set(re.findall(r'/_next/static/[^"\\]+\.js', html)))[:60]
L("js chunks:", len(chunks))
paths = set()
for c in chunks:
    r = get(BASE + c)
    if r is not None and r.status_code == 200:
        paths |= set(re.findall(r'["\'`](/?(?:api/)?[a-z\-_/]*(?:product|categor|search|catalog)[a-z\-_/$\{\}\.]*)["\'`]', r.text))
L("api-like paths:", sorted(paths)[:80])

# kateqoriya id ilə sınaqlar
for path in [f"/api/categories/{slug}", "/api/categories/371", "/api/categories/371/products", "/api/category/371",
             f"/api/category/{slug}", "/api/products?category_id=371", "/api/product?category_id=371",
             "/api/products/category/371", f"/api/products/category/{slug}", "/api/category-products/371",
             "/api/products?categoryId=371", "/api/products?category=371", "/api/search/products?q=s%C3%BCd",
             "/api/products/search?q=s%C3%BCd", "/api/search?search=s%C3%BCd", "/api/products?search=s%C3%BCd"]:
    r = get(API + path, headers={"Accept": "application/json", "Origin": BASE, "Referer": BASE + "/"})
    if r is not None:
        L(f"{r.status_code} {len(r.text):>7}B sales_price={r.text.count('sales_price')} {path}")
        if r.status_code == 200 and "sales_price" in r.text:
            (OUT / ("araz_try_" + re.sub(r"\W+", "_", path) + ".json")).write_text(r.text[:30000], encoding="utf-8")
(OUT / "araz_catalog2.txt").write_text("\n".join(log), encoding="utf-8")
