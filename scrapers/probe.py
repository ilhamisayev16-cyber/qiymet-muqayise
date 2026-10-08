#!/usr/bin/env python3
"""Rahat Wolt brend səhifəsi və OBA məhsul səhifəsi probe-u (data/probe/obarahat.txt)."""
import re
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

# 1) Wolt Rahat brend
r = get("https://wolt.com/az/aze/baku/brand/rahat-supermarket")
if r is not None:
    t = r.text.replace('\\"', '"')
    L("wolt brand", r.status_code, len(t))
    L("venue slugs:", sorted(set(re.findall(r'/venue/([a-z0-9\-]+)', t)))[:40])
    L("slug fields:", sorted(set(re.findall(r'"slug":"([a-z0-9\-]*rahat[a-z0-9\-]*)"', t)))[:40])
    (OUT / "rahat_wolt_brand.html").write_text(t[:120000], encoding="utf-8")

# 2) OBA
r = get("https://oba.az/products/")
if r is not None:
    t = r.text
    L("oba /products/", r.status_code, len(t), r.url)
    L("title:", (re.search(r"<title>(.*?)</title>", t, re.S) or [0, ""])[1].strip())
    L("json-ld:", t.count("ld+json"), " __NEXT_DATA__:", "__NEXT_DATA__" in t, " next_f:", "__next_f" in t)
    L("api-like:", sorted(set(re.findall(r'(?:https?:)?//[a-z0-9.\-]+/(?:api|v\d)[A-Za-z0-9/_\-?=&.]*', t)))[:30])
    L("hrefs:", sorted(set(re.findall(r'href="(/[^"#?]{2,70})"', t)))[:60])
    L("price snippets:", re.findall(r".{60}\d+[.,]\d{2}\s*(?:₼|AZN|man).{20}", t)[:6])
    (OUT / "oba_products.html").write_text(t[:200000], encoding="utf-8")
    for c in sorted(set(re.findall(r'(?:src|href)="([^"]+\.js[^"]*)"', t)))[:25]:
        u = c if c.startswith("http") else "https://oba.az" + (c if c.startswith("/") else "/" + c)
        j = get(u)
        if j is not None and j.status_code == 200:
            p = sorted(set(re.findall(r'["\'`]((?:https?://[^"\'`]+)?/?(?:api/)?[a-zA-Z\-_/]*(?:product|categor|catalog)[a-zA-Z\-_/{}$.?=&]*)["\'`]', j.text)))[:15]
            if p: L("js", c[:60], p)
(OUT / "obarahat.txt").write_text("\n".join(log), encoding="utf-8")
