import requests
import json
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "app-language": "az",
}

# Wolt-da Bakı mağazalarının slug-ları
STORES = {
    "Bravo":  "bravo-supermarket-nizami",
    "Neptun": "neptun-supermarket-28",
    "Rahat":  "rahat-supermarket",
    "OBA":    "oba-market-narimanov",
}

SEARCH_TERMS = [
    {"id": "sud-1l",          "name": "Süd 1L",              "query": "süd"},
    {"id": "yumurta-10",      "name": "Yumurta 10 ədəd",     "query": "yumurta"},
    {"id": "kere-yagi-200q",  "name": "Kərə yağı 200q",      "query": "kərə yağı"},
    {"id": "ag-corek",        "name": "Ağ çörək",             "query": "çörək"},
    {"id": "pomidor-1kq",     "name": "Pomidor 1kq",          "query": "pomidor"},
    {"id": "kartof-1kq",      "name": "Kartof 1kq",           "query": "kartof"},
    {"id": "soyan-1kq",       "name": "Soğan 1kq",            "query": "soğan"},
    {"id": "toyuq-1kq",       "name": "Toyuq 1kq",            "query": "toyuq"},
    {"id": "duyü-1kq",        "name": "Düyü 1kq",             "query": "düyü"},
    {"id": "sekerqum-1kq",    "name": "Şəkər 1kq",            "query": "şəkər"},
    {"id": "un-1kq",          "name": "Un 1kq",               "query": "un"},
    {"id": "ay-cicayi-1l",    "name": "Ay çiçəyi yağı 1L",   "query": "ay çiçəyi"},
]

def get_wolt_price(venue_slug, query):
    try:
        url = f"https://consumer-api.wolt.com/consumer-api/v1/venues/slug/{venue_slug}/menu/items/?q={requests.utils.quote(query)}&language=az"
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        items = data.get("items", [])
        if items:
            price_cents = items[0].get("price", None)
            if price_cents:
                return round(price_cents / 100, 2)
    except Exception as e:
        print(f"  Wolt error [{venue_slug}] '{query}': {e}")
    return None

results = []
for product in SEARCH_TERMS:
    print(f"\n{product['name']}:")
    prices = {}
    for store_name, slug in STORES.items():
        price = get_wolt_price(slug, product["query"])
        prices[store_name] = price
        print(f"  {store_name}: {price}")
    results.append({
        "id": product["id"],
        "name": product["name"],
        "prices": prices
    })

output = {
    "last_updated": datetime.now().strftime("%d %B %Y, %H:%M"),
    "products": results
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nDone!")
