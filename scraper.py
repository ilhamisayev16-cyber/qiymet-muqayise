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
    "Rahat":  "rahat-supermarket-heydar-aliyev",
    "OBA":    "oba-market-nerimanov-1",
}

CATEGORIES = [
    {"id": "sud",     "name": "Süd 1L",      "query": "sud",     "filter": lambda n: any(w in n.lower() for w in ["süd","sud"]) and any(w in n.lower() for w in ["1l","1 l","1lt","1000ml"])},
    {"id": "yumurta","name": "Yumurta",      "query": "yumurta", "filter": lambda n: "yumurta" in n.lower()},
    {"id": "kartof",  "name": "Kartof 1kq",  "query": "kartof",  "filter": lambda n: "kartof" in n.lower()},
    {"id": "pomidor", "name": "Pomidor 1kq", "query": "pomidor", "filter": lambda n: "pomidor" in n.lower()},
    {"id": "toyuq",   "name": "Toyuq",       "query": "toyuq",   "filter": lambda n: "toyuq" in n.lower()},
]

def search_items(venue_slug, query):
    try:
        url = f"https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/{venue_slug}/assortment/items/search?language=az"
        r = requests.post(url, headers=HEADERS, json={"q": query}, timeout=15)
        print(f"  [{venue_slug}] status: {r.status_code}")
        if r.status_code != 200:
            return []
        data = r.json()
        # Try different response structures
        if "items" in data:
            return data["items"]
        if "results" in data:
            return data["results"]
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"  Xəta: {e}")
        return []

def extract_price(item):
    for key in ["price", "baseprice", "unit_price"]:
        val = item.get(key)
        if isinstance(val, dict):
            val = val.get("amount") or val.get("value")
        if val and isinstance(val, (int, float)) and val > 0:
            return round(val / 100, 2)
    return None

def extract_name(item):
    name = item.get("name", "")
    if isinstance(name, dict):
        return name.get("az") or name.get("en") or ""
    return str(name)

# Load old data to preserve if scrape fails
try:
    with open("data/prices.json", "r", encoding="utf-8") as f:
        old_data = json.load(f)
except:
    old_data = {}

results = {}

for cat in CATEGORIES:
    print(f"\n=== {cat['name']} ===")
    cat_results = {}

    for store_name, slug in STORES.items():
        print(f"\n  {store_name}:")
        items = search_items(slug, cat["query"])
        found = []

        for item in items:
            name = extract_name(item)
            if cat["filter"](name):
                price = extract_price(item)
                if price:
                    found.append({"name": name, "price": price})
                    print(f"    ✅ {name}: ₼{price}")

        # Keep old data if nothing found
        if not found:
            old_store = old_data.get("categories", {}).get(cat["id"], {}).get("stores", {}).get(store_name, [])
            if old_store:
                found = old_store
                print(f"    ⚠️ Köhnə data saxlanıldı ({len(found)} məhsul)")
            else:
                print(f"    ❌ Tapılmadı")

        cat_results[store_name] = found

    results[cat["id"]] = {
        "name": cat["name"],
        "stores": cat_results
    }

output = {
    "last_updated": datetime.now().strftime("%d %B %Y, %H:%M"),
    "categories": results
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n✅ Done!")
