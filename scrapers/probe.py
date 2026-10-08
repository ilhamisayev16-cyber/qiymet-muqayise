#!/usr/bin/env python3
"""neptun.az real brauzerlə (Playwright) yoxlanır → data/probe/neptun.txt"""
import re, json
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT = Path(__file__).resolve().parent.parent / "data" / "probe"; OUT.mkdir(parents=True, exist_ok=True)
log = []
def L(*a):
    s = " ".join(str(x) for x in a); log.append(s); print(s)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                        locale="az-AZ", viewport={"width": 1366, "height": 900})
    pg = ctx.new_page()
    seen = []
    def on_resp(r):
        try:
            ct = r.headers.get("content-type", "")
            if r.request.resource_type in ("xhr", "fetch") or "json" in ct:
                seen.append((r.status, r.request.method, r.url[:160], ct[:30]))
        except Exception: pass
    pg.on("response", on_resp)
    try:
        resp = pg.goto("https://neptun.az/", wait_until="networkidle", timeout=60000)
        L("status:", resp.status if resp else None, "url:", pg.url, "title:", pg.title())
    except Exception as e:
        L("goto ERR", e)
    pg.wait_for_timeout(4000)
    html = pg.content()
    L("html bytes:", len(html))
    L("text:", re.sub(r"\s+", " ", pg.inner_text("body"))[:600] if html else "")
    L("links:", sorted(set(pg.eval_on_selector_all("a[href]", "els=>els.map(e=>e.getAttribute('href'))")))[:50])
    L("xhr/json responses:")
    for s in seen[:40]: L("  ", *s)
    (OUT / "neptun.html").write_text(html[:200000], encoding="utf-8")
    pg.screenshot(path=str(OUT / "neptun.png"))
    b.close()
(OUT / "neptun.txt").write_text("\n".join(log), encoding="utf-8")
