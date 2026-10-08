#!/usr/bin/env python3
"""Mağaza saytlarının strukturunu yoxlayır və nəticəni data/probe/ qovluğuna yazır.
GitHub Actions-da (internet var) işlədilir; nəticəyə baxıb düzgün scraper yazılır."""
import re, sys
from pathlib import Path
import requests

URLS = {
    "araz_home": "https://arazmarket.az/az",
    "rahat_aksiya": "https://rahatmarket.az/az/aksiyalar/rahat-market",
    "rahat_home": "https://rahatmarket.az/az",
    "oba_home": "https://oba.az/az",
}
OUT = Path(__file__).resolve().parent.parent / "data" / "probe"
OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "az"}

for key, url in URLS.items():
    lines = [f"URL: {url}"]
    try:
        r = requests.get(url, headers=H, timeout=30)
        html = r.text
        lines += [f"status: {r.status_code}", f"bytes: {len(html)}", f"content-type: {r.headers.get('content-type')}"]
        lines.append("title: " + (re.search(r"<title>(.*?)</title>", html, re.S) or [None, ""])[1].strip())
        lines.append("json-ld blocks: %d" % len(re.findall(r"application/ld\+json", html)))
        lines.append("__NEXT_DATA__: %s" % ("__NEXT_DATA__" in html))
        lines.append("api-like urls: " + ", ".join(sorted(set(re.findall(r"[\"'](/?(?:api|graphql)[^\"' ]{0,80})", html)))[:20]))
        lines.append("category-like links: " + ", ".join(sorted(set(re.findall(r'href="(/az/[^"#?]{3,60})"', html)))[:40]))
        lines.append("price snippets: " + " | ".join(re.findall(r".{40}\d+[.,]\d{2}\s*(?:₼|AZN|man).{10}", html)[:8]))
        (OUT / f"{key}.html").write_text(html[:200000], encoding="utf-8")
    except Exception as e:
        lines.append(f"ERROR: {e}")
    (OUT / f"{key}.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines), "\n")
