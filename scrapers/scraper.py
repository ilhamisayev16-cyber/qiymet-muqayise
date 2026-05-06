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
    # ── SÜD MƏHSULLARI ──────────────────────────────────────────────
    {"id":"sud","name":"Süd","query":"sud",
     "filter": lambda n: any(w in n.lower() for w in ["süd","sud"]) and any(w in n.lower() for w in ["1l","1 l","1lt","1000ml","1litr"])},
    {"id":"xama","name":"Xama","query":"xama",
     "filter": lambda n: any(w in n.lower() for w in ["xama","qaymaq smet"]) and not any(w in n.lower() for w in ["çips","lays","kreker","mayonez","suxari"])},
    {"id":"qatiq","name":"Qatıq","query":"qatiq",
     "filter": lambda n: any(w in n.lower() for w in ["qatıq","qatiq"])},
    {"id":"kesmik","name":"Kəsmik","query":"kesmik",
     "filter": lambda n: any(w in n.lower() for w in ["kəsmik","kesmik","tvorog"])},
    {"id":"ayran","name":"Ayran","query":"ayran",
     "filter": lambda n: "ayran" in n.lower()},
    {"id":"kefir","name":"Kefir","query":"kefir",
     "filter": lambda n: "kefir" in n.lower()},
    {"id":"kere_yagi","name":"Kərə yağı","query":"kere yagi",
     "filter": lambda n: any(w in n.lower() for w in ["kərə","kere"]) and "yağ" in n.lower()},
    {"id":"pendir","name":"Pendir","query":"pendir",
     "filter": lambda n: "pendir" in n.lower()},

    # ── ƏT VƏ QUŞÇULUQ ──────────────────────────────────────────────
    {"id":"toyuq","name":"Toyuq","query":"toyuq",
     "filter": lambda n: "toyuq" in n.lower() and not any(w in n.lower() for w in ["bulyon","ədviyyat","çips","pişik","it ","felix","darling"])},
    {"id":"mal_eti","name":"Mal əti","query":"mal eti",
     "filter": lambda n: any(w in n.lower() for w in ["mal əti","mal eti","beef","dana əti","dana eti"])},
    {"id":"qoyun_eti","name":"Qoyun əti","query":"qoyun eti",
     "filter": lambda n: any(w in n.lower() for w in ["qoyun","quzu","lamb"])},
    {"id":"qiyme","name":"Qiymə","query":"qiyme",
     "filter": lambda n: any(w in n.lower() for w in ["qiymə","qiyme","farş","fars"])},
    {"id":"kolbasa","name":"Kolbasa","query":"kolbasa",
     "filter": lambda n: any(w in n.lower() for w in ["kolbasa","salam","sosiska","sosis"]) and not "balıq" in n.lower()},

    # ── BALIQ ────────────────────────────────────────────────────────
    {"id":"ton_baligi","name":"Ton balığı","query":"ton baligi",
     "filter": lambda n: any(w in n.lower() for w in ["ton balığı","ton baligi","tuna"])},
    {"id":"siyenek","name":"Siyənək","query":"siyenek",
     "filter": lambda n: any(w in n.lower() for w in ["siyənək","siyenek","herring"])},

    # ── TƏRƏVƏZ ─────────────────────────────────────────────────────
    {"id":"kartof","name":"Kartof","query":"kartof",
     "filter": lambda n: "kartof" in n.lower() and not any(w in n.lower() for w in ["fri","çips","ədviyyat","nişasta","püre","kraxmal"])},
    {"id":"pomidor","name":"Pomidor","query":"pomidor",
     "filter": lambda n: "pomidor" in n.lower() and not any(w in n.lower() for w in ["sous","turşu","şirə","ketçup","pasta","ədviyyat","çips"])},
    {"id":"xiyar","name":"Xiyar","query":"xiyar",
     "filter": lambda n: "xiyar" in n.lower() and not any(w in n.lower() for w in ["turşu","sabun","krem","duş"])},
    {"id":"soyan","name":"Soğan","query":"soyan",
     "filter": lambda n: any(w in n.lower() for w in ["soğan","soyan"]) and not any(w in n.lower() for w in ["çips","lays","xama","kreker"])},
    {"id":"kelem","name":"Kələm","query":"kelem",
     "filter": lambda n: any(w in n.lower() for w in ["kələm","kelem","kapusta"])},
    {"id":"yerkoky","name":"Yerkökü","query":"yerkoku",
     "filter": lambda n: any(w in n.lower() for w in ["yerkökü","yerkoku","morkov"])},
    {"id":"badimcan","name":"Badımcan","query":"badimcan",
     "filter": lambda n: any(w in n.lower() for w in ["badımcan","badimcan","badincan"])},
    {"id":"biber","name":"Bibər","query":"biber",
     "filter": lambda n: any(w in n.lower() for w in ["bibər","biber"]) and "kg" not in n.lower() and not any(w in n.lower() for w in ["ədviyyat","sous","turşu","çips","qara","istiot"])},
    {"id":"sarımsaq","name":"Sarımsaq","query":"sarimısaq",
     "filter": lambda n: any(w in n.lower() for w in ["sarımsaq","sarimisaq","sarimsaq"])},
    {"id":"qabaq","name":"Qabaq","query":"qabaq",
     "filter": lambda n: "qabaq" in n.lower() and not any(w in n.lower() for w in ["toxum","yağ"])},
    {"id":"cugundur","name":"Çuğundur","query":"cugundur",
     "filter": lambda n: any(w in n.lower() for w in ["çuğundur","cugundur","svekla"])},

    # ── MEYVƏ ────────────────────────────────────────────────────────
    {"id":"alma","name":"Alma","query":"alma",
     "filter": lambda n: "alma" in n.lower() and any(w in n.lower() for w in [" kq"," kg","1kq","1 kq"]) and not any(w in n.lower() for w in ["şirə","mürəbbə","kompot","çay","ədviyyat"])},
    {"id":"armud","name":"Armud","query":"armud",
     "filter": lambda n: "armud" in n.lower() and not any(w in n.lower() for w in ["şirə","mürəbbə","kompot"])},
    {"id":"banan","name":"Banan","query":"banan",
     "filter": lambda n: "banan" in n.lower() and not any(w in n.lower() for w in ["şirə","çips","uşaq"])},
    {"id":"limon","name":"Limon","query":"limon",
     "filter": lambda n: "limon" in n.lower() and any(w in n.lower() for w in [" kq"," kg","1kq","ədəd"]) and not any(w in n.lower() for w in ["şirə","içki","su","çay"])},
    {"id":"portakal","name":"Portağal","query":"portakal",
     "filter": lambda n: any(w in n.lower() for w in ["portağal","portakal"]) and not any(w in n.lower() for w in ["şirə","içki"])},
    {"id":"uzum","name":"Üzüm","query":"uzum",
     "filter": lambda n: any(w in n.lower() for w in ["üzüm","uzum"]) and not any(w in n.lower() for w in ["şirə","şərab","sirkə"])},

    # ── TAXIL VƏ DƏNLİ ──────────────────────────────────────────────
    {"id":"duyu","name":"Düyü","query":"duyu",
     "filter": lambda n: any(w in n.lower() for w in ["düyü","duyu"]) and not any(w in n.lower() for w in ["çips","xlebt","vafli","sıyıq","unu","vermişel"])},
    {"id":"makaron","name":"Makaron","query":"makaron",
     "filter": lambda n: "makaron" in n.lower()},
    {"id":"un","name":"Un","query":"un 1kq",
     "filter": lambda n: (n.lower().startswith("un") or " un " in n.lower() or n.lower().endswith(" un")) and not any(w in n.lower() for w in ["çörək","xlebt"])},
    {"id":"yulaf","name":"Yulaf","query":"yulaf",
     "filter": lambda n: any(w in n.lower() for w in ["yulaf","ovsyanka","ovs"])},
    {"id":"qarabashaq","name":"Qarabaşaq","query":"qarabashaq",
     "filter": lambda n: any(w in n.lower() for w in ["qarabaşaq","qarabashaq","grechka"])},
    {"id":"merci","name":"Mərci","query":"merci",
     "filter": lambda n: any(w in n.lower() for w in ["mərci","merci","lentil","chechevitsa"])},
    {"id":"noxud","name":"Noxud","query":"noxud",
     "filter": lambda n: any(w in n.lower() for w in ["noxud","gorox"]) and not "ədviyyat" in n.lower()},
    {"id":"lobya","name":"Lobya","query":"lobya",
     "filter": lambda n: any(w in n.lower() for w in ["lobya","fasol"]) and not any(w in n.lower() for w in ["konserv","turşu"])},
    {"id":"sekerqum","name":"Şəkər","query":"sekerqum",
     "filter": lambda n: any(w in n.lower() for w in ["şəkər","sekerqum"])},
    {"id":"duz","name":"Duz","query":"duz",
     "filter": lambda n: "duz" in n.lower() and any(w in n.lower() for w in ["1kq","500q","1 kq"]) and not any(w in n.lower() for w in ["xiyar","pomidor","turşu","pendir"])},

    # ── ÇÖRƏK ────────────────────────────────────────────────────────
    {"id":"corek","name":"Çörək","query":"corek",
     "filter": lambda n: any(w in n.lower() for w in ["çörək","corek","lavaş","lavash"])},

    # ── YAĞLAR ───────────────────────────────────────────────────────
    {"id":"ay_cicayi","name":"Ay çiçəyi yağı","query":"ay cicayi yagi",
     "filter": lambda n: any(w in n.lower() for w in ["ay çiçəyi","ay cicayi","günəbaxan yağ","gunebaxan yag"])},
    {"id":"zeytun_yagi","name":"Zeytun yağı","query":"zeytun yagi",
     "filter": lambda n: "zeytun" in n.lower() and "yağ" in n.lower() and not any(w in n.lower() for w in ["sabun","krem","şampun","balıq","ton","sardina"])},
    {"id":"kere_yagi_spred","name":"Kərə yağı / Spred","query":"spred",
     "filter": lambda n: any(w in n.lower() for w in ["spred","margarin"]) },

    # ── SOUSLƏR VƏ ƏDVİYYAT ─────────────────────────────────────────
    {"id":"ketcup","name":"Ketçup","query":"ketcup",
     "filter": lambda n: any(w in n.lower() for w in ["ketçup","ketchup","kecap"])},
    {"id":"mayonez","name":"Mayonez","query":"mayonez",
     "filter": lambda n: "mayonez" in n.lower()},
    {"id":"xardal","name":"Xardal","query":"xardal",
     "filter": lambda n: "xardal" in n.lower()},
    {"id":"sirke","name":"Sirkə","query":"sirke",
     "filter": lambda n: "sirkə" in n.lower() or "sirke" in n.lower()},
    {"id":"qara_istiot","name":"Qara istiot","query":"qara istiot",
     "filter": lambda n: any(w in n.lower() for w in ["qara istiot","black pepper","istiot"])},

    # ── İÇKİLƏR ─────────────────────────────────────────────────────
    {"id":"su","name":"İçməli su","query":"su",
     "filter": lambda n: any(w in n.lower() for w in ["mineral su","içməli su"]) or ("su" in n.lower() and any(w in n.lower() for w in ["1.5l","2l","0.5l","500ml","1l"]))},
    {"id":"cola","name":"Kola / Limonad","query":"cola",
     "filter": lambda n: any(w in n.lower() for w in ["cola","kola","pepsi","fanta","sprite"])},
    {"id":"cay","name":"Çay","query":"cay",
     "filter": lambda n: any(w in n.lower() for w in ["çay","lipton","tess","ahmad"]) and not any(w in n.lower() for w in ["fincan","dəsti","qab"])},
    {"id":"qehve","name":"Qəhvə","query":"qehve",
     "filter": lambda n: any(w in n.lower() for w in ["qəhvə","qehve","nescafe","coffee","lavazza","jacobs"])},
    {"id":"sire","name":"Şirə / Meyve suyu","query":"sire",
     "filter": lambda n: any(w in n.lower() for w in ["şirə","meyve suyu","juice"]) and any(w in n.lower() for w in ["1l","1 l","2l","200ml","0.5l"])},
    {"id":"energetik","name":"Energetik içki","query":"energetik",
     "filter": lambda n: any(w in n.lower() for w in ["red bull","monster","energy","burn","hell"])},

    # ── ŞİRNİYYAT ────────────────────────────────────────────────────
    {"id":"shokolad","name":"Şokolad","query":"shokolad",
     "filter": lambda n: any(w in n.lower() for w in ["şokolad","shokolad"]) and not any(w in n.lower() for w in ["yumurta","içki","tort","kek"])},
    {"id":"bal","name":"Bal","query":"bal",
     "filter": lambda n: "bal" in n.lower() and any(w in n.lower() for w in ["1kq","500q","250q","kq"]) and not any(w in n.lower() for w in ["balıq","balaca","bala","banan"])},
    {"id":"murrebbe","name":"Mürəbbə","query":"murrebbe",
     "filter": lambda n: any(w in n.lower() for w in ["mürəbbə","murrebbe","cem","jam","confiture"])},

    # ── HAZIR QİDA ───────────────────────────────────────────────────
    {"id":"pelmeni","name":"Pelmeni","query":"pelmeni",
     "filter": lambda n: "pelmeni" in n.lower()},
    {"id":"varenik","name":"Varenik","query":"varenik",
     "filter": lambda n: "varenik" in n.lower()},

    # ── UŞAQ QİDASI ──────────────────────────────────────────────────
    {"id":"usaq_puryesi","name":"Uşaq püresi","query":"usaq puresi",
     "filter": lambda n: any(w in n.lower() for w in ["agusha","fruto","uşaq püresi","bebi","kabrita"]) and "püre" in n.lower()},

    # ── DİGƏR ────────────────────────────────────────────────────────
    {"id":"yumurta","name":"Yumurta","query":"yumurta",
     "filter": lambda n: "yumurta" in n.lower() and not any(w in n.lower() for w in ["şokolad","sürpriz","boyası","fırça","oyuncaq","əriştə","şampun"])},
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

# Load old data to preserve if scrape fails
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
