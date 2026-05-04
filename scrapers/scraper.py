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
    {
        "id": "sud",
        "name": "Süd",
        "query": "sud",
        "filter": lambda n: any(w in n.lower() for w in ["süd","sud"]) and any(w in n.lower() for w in ["1l","1 l","1lt","1000ml","1litr"])
    },
    {
        "id": "yumurta",
        "name": "Yumurta",
        "query": "yumurta",
        "filter": lambda n: "yumurta" in n.lower()
    },
    {
        "id": "kere_yagi",
        "name": "Kərə yağı",
        "query": "kere yagi",
        "filter": lambda n: any(w in n.lower() for w in ["kərə","kere"]) and "yağ" in n.lower()
    },
    {
        "id": "pendir",
        "name": "Pendir",
        "query": "pendir",
        "filter": lambda n: "pendir" in n.lower()
    },
    {
        "id": "qatiq",
        "name": "Qatıq",
        "query": "qatiq",
        "filter": lambda n: any(w in n.lower() for w in ["qatıq","qatiq"])
    },
    {
        "id": "kartof",
        "name": "Kartof 1kq",
        "query": "kartof",
        "filter": lambda n: "kartof" in n.lower()
    },
    {
        "id": "pomidor",
        "name": "Pomidor 1kq",
        "query": "pomidor",
        "filter": lambda n: "pomidor" in n.lower()
    },
    {
        "id": "xiyar",
        "name": "Xiyar",
        "query": "xiyar",
        "filter": lambda n: "xiyar" in n.lower()
    },
    {
        "id": "soyan",
        "name": "Soğan 1kq",
        "query": "soyan",
        "filter": lambda n: any(w in n.lower() for w in ["soğan","soyan"])
    },
    {
        "id": "toyuq",
        "name": "Toyuq",
        "query": "toyuq",
        "filter": lambda n: "toyuq" in n.lower()
    },
    {
        "id": "yumşaq_icecek",
        "name": "Kola / Limonad",
        "query": "cola",
        "filter": lambda n: any(w in n.lower() for w in ["cola","kola","pepsi","fanta","sprite"])
    },
    {
        "id": "su",
        "name": "İçməli su",
        "query": "su",
        "filter": lambda n: any(w in n.lower() for w in ["mineral su","içməli su","mincər"]) or ("su" in n.lower() and any(w in n.lower() for w in ["1.5l","2l","0.5l","500ml","1l"]))
    },
    {
        "id": "zeytun_yagi",
        "name": "Zeytun yağı",
        "query": "zeytun yagi",
        "filter": lambda n: "zeytun" in n.lower() and "yağ" in n.lower()
    },
    {
        "id": "ay_cicayi",
        "name": "Ay çiçəyi yağı",
        "query": "ay cicayi yagi",
        "filter": lambda n: "ay çiçəyi" in n.lower() or "ay cicayi" in n.lower()
    },
    {
        "id": "duyu",
        "name": "Düyü",
        "query": "duyu",
        "filter": lambda n: any(w in n.lower() for w in ["düyü","duyu"])
    },
    {
        "id": "makaron",
        "name": "Makaron",
        "query": "makaron",
        "filter": lambda n: "makaron" in n.lower()
    },
    {
        "id": "sekerqum",
        "name": "Şəkər",
        "query": "sekerqum",
        "filter": lambda n: any(w in n.lower() for w in ["şəkər","sekerqum"])
    },
    {
        "id": "un",
        "name": "Un",
        "query": "un 1kq",
        "filter": lambda n: n.lower().startswith("un") or " un " in n.lower() or n.lower().endswith(" un")
    },
    {
        "id": "corek",
        "name": "Çörək",
        "query": "corek",
        "filter": lambda n: any(w in n.lower() for w in ["çörək","corek","lavaş","lavash"])
    },
]

def search_items(venue_slug, query):
    try:
        url = f"https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/{venue_slug}/assortment/items/search?language=az"
        r = requests.post(url, headers=HEADERS, json={"q": query}, timeout=15)
        if r.status_code != 200:
            print(f"  [{venue_slug}] status: {r.status_code}")
            return []
        data = r.json()
        if "items" in data: return data["items"]
        if "results" in data: return data["results"]
        if isinstance(data, list): return data
        return []
    except Exception as e:
        print(f"  Xəta: {e}")
        return []

def extract_price(item):
    for key in ["price","baseprice","unit_price"]:
        val = item.get(key)
        if isinstance(val, dict):
            val = val.get("amount") or val.get("value")
        if val and isinstance(val, (int,float)) and val > 0:
            return round(val / 100, 2)
    return None

def extract_name(item):
    name = item.get("name","")
    if isinstance(name, dict):
        return name.get("az") or name.get("en") or ""
    return str(name)

# Load old data
try:
    with open("data/prices.json","r",encoding="utf-8") as f:
        old_data = json.load(f)
except:
    old_data = {}

categories_result = {}

for cat in CATEGORIES:
    print(f"\n=== {cat['name']} ===")
    cat_stores = {}

    for store_name, slug in STORES.items():
        print(f"  {store_name}:")
        items = search_items(slug, cat["query"])
        found = []

        for item in items:
            name = extract_name(item)
            try:
                if cat["filter"](name):
                    price = extract_price(item)
                    if price:
                        found.append({"name": name, "price": price})
                        print(f"    ✅ {name}: ₼{price}")
            except:
                pass

        # Keep old data if nothing found
        if not found:
            old_store = old_data.get("categories",{}).get(cat["id"],{}).get("stores",{}).get(store_name,[])
            if old_store:
                found = old_store
                print(f"    ⚠️ Köhnə data: {len(found)} məhsul")
            else:
                print(f"    ❌ Tapılmadı")

        cat_stores[store_name] = found

    categories_result[cat["id"]] = {
        "name": cat["name"],
        "stores": cat_stores
    }

output = {
    "last_updated": datetime.now().strftime("%d %B %Y, %H:%M"),
    "categories": categories_result
}

with open("data/prices.json","w",encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n✅ Done!")
