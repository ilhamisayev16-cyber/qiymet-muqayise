import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright

PRODUCTS = [
    {"id": "sud-1l", "name": "Süd 1L", "query": "süd 1l"},
    {"id": "yumurta-10", "name": "Yumurta 10 ədəd", "query": "yumurta 10"},
    {"id": "kere-yagi-200q", "name": "Kərə yağı 200q", "query": "kərə yağı"},
    {"id": "ag-corek", "name": "Ağ çörək", "query": "çörək"},
    {"id": "pomidor-1kq", "name": "Pomidor 1kq", "query": "pomidor"},
    {"id": "kartof-1kq", "name": "Kartof 1kq", "query": "kartof"},
    {"id": "soyan-1kq", "name": "Soğan 1kq", "query": "soğan"},
    {"id": "toyuq-1kq", "name": "Toyuq 1kq", "query": "toyuq"},
    {"id": "duyü-1kq", "name": "Düyü 1kq", "query": "düyü"},
    {"id": "sekerqum-1kq", "name": "Şəkər 1kq", "query": "şəkər"},
    {"id": "un-1kq", "name": "Un 1kq", "query": "un 1kq"},
    {"id": "ay-cicayi-1l", "name": "Ay çiçəyi yağı 1L", "query": "ay çiçəyi yağı"},
]

def extract_price(text):
    nums = re.findall(r'\d+[.,]\d+', text.replace(',', '.'))
    for n in nums:
        val = float(n.replace(',', '.'))
        if 0.1 < val < 100:
            return round(val, 2)
    return None

async def scrape_store(page, url, price_selector, query):
    try:
        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        els = await page.query_selector_all(price_selector)
        for el in els:
            text = await el.inner_text()
            p = extract_price(text)
            if p:
                return p
    except Exception as e:
        print(f"  Error: {e}")
    return None

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        results = []
        for product in PRODUCTS:
            q = product["query"]
            print(f"\n{product['name']}:")
            prices = {}

            # Bravo (birmarket.az)
            prices["Bravo"] = await scrape_store(
                page,
                f"https://birmarket.az/search?q={q}",
                "[class*='price']", q
            )
            print(f"  Bravo: {prices['Bravo']}")

            # Neptun
            prices["Neptun"] = await scrape_store(
                page,
                f"https://neptun.az/index.php?route=product/search&search={q}",
                ".price-new, [class*='price']", q
            )
            print(f"  Neptun: {prices['Neptun']}")

            # Rahat
            prices["Rahat"] = await scrape_store(
                page,
                f"https://rahatmarket.az/index.php?route=product/search&search={q}",
                ".price-new, [class*='price']", q
            )
            print(f"  Rahat: {prices['Rahat']}")

            # OBA
            prices["OBA"] = await scrape_store(
                page,
                f"https://oba.az/search/?q={q}",
                "[class*='price']", q
            )
            print(f"  OBA: {prices['OBA']}")

            results.append({
                "id": product["id"],
                "name": product["name"],
                "prices": prices
            })

        await browser.close()

        output = {
            "last_updated": datetime.now().strftime("%d %B %Y, %H:%M"),
            "products": results
        }
        with open("data/prices.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("\nDone!")

asyncio.run(main())
