#!/usr/bin/env python3
"""Neptun və Bravo mənbə yoxlaması (data/probe/nb.txt)."""
import re
from pathlib import Path
import requests
OUT = Path(__file__).resolve().parent.parent / "data" / "probe"; OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "az"}
log = []
def L(*a):
    s = " ".join(str(x) for x in a); log.append(s); print(s)
for key, url in {"neptun": "https://neptun.az", "neptun_az": "https://neptun.az/az", "neptun_shop": "https://shop.neptun.az",
                 "bravo": "https://bravo.az", "bravoonline": "https://bravoonline.az", "bravo_super": "https://bravosupermarket.az",
                 "birmarket": "https://birmarket.az"}.items():
    try:
        r = requests.get(url, headers=H, timeout=25)
        t = r.text
        L(f"{key}: {r.status_code} {len(t)}B final={r.url} title={(re.search(r'<title>(.*?)</title>', t, re.S) or [0,''])[1].strip()[:80]}")
        L("  next:", "__NEXT_DATA__" in t, "__next_f" in t, " api:", sorted(set(re.findall(r'https?://[a-z0-9.\-]+/api[A-Za-z0-9/_\-]*', t)))[:6],
          " links:", sorted(set(re.findall(r'href="(/[^"#?]{2,50})"', t)))[:20])
        L("  price snippets:", re.findall(r".{40}\d+[.,]\d{2}\s*(?:₼|AZN|man).{10}", t)[:3])
        (OUT / (key + ".html")).write_text(t[:150000], encoding="utf-8")
    except Exception as e:
        L(f"{key}: ERR {e}")
(OUT / "nb.txt").write_text("\n".join(log), encoding="utf-8")
