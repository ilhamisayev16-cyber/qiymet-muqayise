import requests
import json
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

STORES = {
    "Bravo":  "bravo-supermarket-globus-centre",
    "Neptun": "neptun-supermarket-28",
    "Rahat":  "aze_3p-nov24_cl_rahat_supermarket",
    "OBA":    "oba-market-nerimanov-1",
}

def search_wolt(venue_slug, query):
    try:
        url = f"https://consumer-api.wolt.com/consumer-api/v1/venues/slug/{venue_slug}/menu/items/?q={requests.utils.quote(query)}&language=az"
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        return data.get("items", [])
    except Exception as e:
        print(f"  Xəta [{venue_slug}]: {e}")
        return []

def is_1_liter(name):
    name_lower = name.lower()
    return "1l" in name_lower or "1 l" in name_lower or "1000ml" in name_lower or "1000 ml" in name_lower or "1lt" in name_lower

results = {}

for store_name, slug in STORES.items():
    print(f"\n{store_name} - süd axtarılır...")
    items = search_wolt(slug, "süd")
    store_results = []
    for item in items:
        name = item.get("name", "")
        price_cents = item.get("price", None)
        if price_cents and is_1_liter(name):
            price = round(price_cents / 100, 2)
            store_results.append({"name": name, "price": price})
            print(f"  ✅ {name}: ₼{price}")
    if not store_results:
        print(f"  ❌ Heç nə tapılmadı")
    results[store_name] = store_results

output = {
    "last_updated": datetime.now().strftime("%d %B %Y, %H:%M"),
    "category": "Süd 1L",
    "stores": results
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nDone!")
