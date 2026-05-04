import requests
import json
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://wolt.com",
    "Referer": "https://wolt.com/",
}

STORES = {
    "Bravo":  "bravo-supermarket-globus-centre",
    "Neptun": "neptun-supermarket-28",
    "Rahat":  "aze_3p-nov24_cl_rahat_supermarket",
    "OBA":    "oba-market-nerimanov-1",
}

def search_items(venue_slug, query):
    try:
        url = f"https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/{venue_slug}/assortment/items/search?language=az"
        r = requests.post(url, headers=HEADERS, json={"q": query}, timeout=15)
        print(f"  Status: {r.status_code}")
        data = r.json()
        return data.get("items", data.get("results", []))
    except Exception as e:
        print(f"  Xəta: {e}")
        return []

def is_milk_1l(name):
    n = name.lower()
    has_milk = any(w in n for w in ["süd", "sud", "milk"])
    has_size = any(w in n for w in ["1l", "1 l", "1lt", "1000ml", "1 litr", "1litr"])
    return has_milk and has_size

results = {}

for store_name, slug in STORES.items():
    print(f"\n{store_name} - süd axtarılır...")
    items = search_items(slug, "sud")
    store_results = []

    for item in items:
        name = item.get("name", "")
        if isinstance(name, dict):
            name = name.get("az", name.get("en", ""))
        if is_milk_1l(name):
            price_cents = item.get("price", item.get("baseprice", None))
            if isinstance(price_cents, dict):
                price_cents = price_cents.get("amount", None)
            if price_cents:
                price = round(price_cents / 100, 2)
                store_results.append({"name": name, "price": price})
                print(f"  ✅ {name}: ₼{price}")

    if not store_results:
        print(f"  ❌ Tapılmadı")
    results[store_name] = store_results

output = {
    "last_updated": datetime.now().strftime("%d %B %Y, %H:%M"),
    "category": "Süd 1L",
    "stores": results
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nDone!")
