import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

PRODUCTS = [
    {"id": "sud-1l", "name": "Süd 1L", "query": "süd 1l"},
    {"id": "yumurta-10", "name": "Yumurta 10 ədəd", "query": "yumurta 10"},
    {"id": "kere-yagi-200q", "name": "Kərə yağı 200q", "query": "kərə yağı"},
    {"id": "ag-corek", "name": "Ağ çörək", "query": "ağ çörək"},
    {"id": "pomidor-1kq", "name": "Pomidor 1kq", "query": "pomidor"},
    {"id": "kartof-1kq", "name": "Kartof 1kq", "query": "kartof"},
    {"id": "soyan-1kq", "name": "Soğan 1kq", "query": "soğan"},
    {"id": "toyuq-1kq", "name": "Toyuq 1kq", "query": "toyuq"},
    {"id": "duyü-1kq", "name": "Düyü 1kq", "query": "düyü"},
    {"id": "sekerqum-1kq", "name": "Şəkər 1kq", "query": "şəkər"},
    {"id": "un-1kq", "name": "Un 1kq", "query": "un 1kq"},
    {"id": "ay-cicayi-1l", "name": "Ay çiçəyi yağı 1L", "query": "ay çiçəyi yağı"},
]

def get_price(text):
    nums = re.findall(r'\d+[.,]\d+|\d+', text.replace(',', '.'))
    for n in nums:
        val = float(n.replace(',', '.'))
        if 0.1 < val < 100:
            return round(val, 2)
    return None

def scrape_birmarket(query):
    try:
        url = f"https://birmarket.az/search?q={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select("[class*='price']"):
            p = get_price(el.get_text())
            if p: return p
    except Exception as e:
        print(f"birmarket error: {e}")
    return None

def scrape_neptun(query):
    try:
        url = f"https://neptun.az/index.php?route=product/search&search={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select(".price-new, .price, [class*='price']"):
            p = get_price(el.get_text())
            if p: return p
    except Exception as e:
        print(f"neptun error: {e}")
    return None

def scrape_rahat(query):
    try:
        url = f"https://rahatmarket.az/index.php?route=product/search&search={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select(".price-new, .price, [class*='price']"):
            p = get_price(el.get_text())
            if p: return p
    except Exception as e:
        print(f"rahat error: {e}")
    return None

def scrape_oba(query):
    try:
        url = f"https://oba.az/search/?q={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup.select("[class*='price']"):
            p = get_price(el.get_text())
            if p: return p
    except Exception as e:
        print(f"oba error: {e}")
    return None

SCRAPERS = {
    "Bravo": scrape_birmarket,
    "Neptun": scrape_neptun,
    "Rahat": scrape_rahat,
    "OBA": scrape_oba,
}

results = []
for product in PRODUCTS:
    print(f"\n{product['name']}:")
    prices = {}
    for store, fn in SCRAPERS.items():
        price = fn(product["query"])
        prices[store] = price
        print(f"  {store}: {price}")
        time.sleep(1)
    results.append({"id": product["id"], "name": product["name"], "prices": prices})

output = {
    "last_updated": datetime.now().strftime("%d %B %Y, %H:%M"),
    "products": results
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nDone!")
