import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import scraper as S
import sources as SRC

ROOT = Path(__file__).resolve().parent.parent
PRICES = json.load(open(ROOT / "data" / "prices.json", encoding="utf-8"))
HIST = json.load(open(ROOT / "data" / "history.json", encoding="utf-8"))


def mini(store="Neptun", n=300, price=1.0, wolt=True):
    key = "wolt_price" if wolt else "price"
    items = [{"name": f"Məhsul {i}", key: price} for i in range(n)]
    return {"stores": [store], "groups": [], "categories": {"sud": {"name": "Süd", "stores": {store: items}}}, "meta": {}}


# 9. mövcud formatlar qorunur
def test_existing_prices_json_format():
    ok, errs = SRC.validate_prices(PRICES, SRC.store_counts(PRICES))
    assert ok, errs
    assert set(PRICES) >= {"stores", "groups", "categories", "last_updated"}
    for c in PRICES["categories"].values():
        assert set(c) >= {"name", "stores"}


def test_existing_history_json_format():
    assert list(HIST) == ["h"]
    for k, v in list(HIST["h"].items())[:500]:
        assert len(k) == 16 and all(len(p) == 2 and isinstance(p[1], (int, float)) for p in v)


# 8. tarixçə əvvəlki kimi işləyir
def test_history_hash_stable_and_tracking():
    assert S._hk("Bravo", "Süd 1 L") == S._hk("Bravo", "Süd 1 L") and len(S._hk("Bravo", "x")) == 16
    d = mini("Araz", 3, 2.0, wolt=False)
    hist = {}
    old = S.track_changes("Araz", d, hist)
    items = [{"name": "Məhsul 0", "price": 1.5}, {"name": "Məhsul 1", "price": 2.0}]
    S.mark_changes(old, items, "Araz", hist, "2026-10-16", "2026-10-15")
    assert items[0]["pp"] == 2.0 and items[0]["pd"] == "2026-10-16" and "pp" not in items[1]
    assert hist[S._hk("Araz", "Məhsul 0")] == [["2026-10-15", 2.0], ["2026-10-16", 1.5]]


# 6. boş / kəskin azalmış nəticə köhnə datanı silmir
def test_empty_result_keeps_old_data():
    d = mini()
    before = copy.deepcopy(d)
    assert S.apply_to_data({}, {}, "Neptun", d, {}) is False
    assert d["categories"] == before["categories"]


def test_sharp_drop_keeps_old_data():
    d = mini(n=1000)
    new = {"sud": [{"name": "Y", "wolt_price": 1.0}] * 10}
    assert S.apply_to_data({}, new, "Neptun", d, {}) is False
    assert len(d["categories"]["sud"]["stores"]["Neptun"]) == 1000


def test_invalid_data_never_overwrites_file(tmp_path):
    out = tmp_path / "prices.json"
    good = mini()
    assert S._save(good, out) and out.exists()
    saved = out.read_text(encoding="utf-8")
    bad = copy.deepcopy(good)
    bad["categories"]["sud"]["stores"]["Neptun"][0]["wolt_price"] = -5
    assert S._save(bad, out) is False
    assert out.read_text(encoding="utf-8") == saved
    assert not list(tmp_path.glob("*.tmp"))


# Wolt söndürmə açarı
def test_wolt_switch_env_and_store_flag():
    assert SRC.wolt_enabled("Bravo", {}) is True
    for v in ("0", "false", "OFF", "no"):
        assert SRC.wolt_enabled("Bravo", {"WOLT_ENABLED": v}) is False


def test_wolt_off_sends_no_requests_and_keeps_data(tmp_path, monkeypatch):
    out = tmp_path / "prices.json"
    d = mini("Neptun", 300, 1.5)
    d["meta"]["Neptun"] = {"updated": "10.10.2026 07:00"}
    S._save(d, out)
    (tmp_path / "history.json").write_text('{"h":{}}')
    def boom(*a, **k): raise AssertionError("Wolt söndürülüb: sorğu göndərilməməlidir")
    for fn in ("scrape_wolt", "scrape_wolt_full", "scrape_wolt_multi", "_session"):
        monkeypatch.setattr(S, fn, boom)
    monkeypatch.setenv("WOLT_ENABLED", "0")
    monkeypatch.setattr("sys.argv", ["scraper.py", "--store", "neptun", "--out", str(out)])
    S.main()
    r = json.load(open(out, encoding="utf-8"))
    items = r["categories"]["sud"]["stores"]["Neptun"]
    assert len(items) == 300                                   # silinmədi
    assert all(i["wolt_price"] == 1.5 and i["stale"] for i in items)   # qiymət dəyişmədi, "arxiv" işarəli
    assert r["meta"]["Neptun"]["auto_update"] is False and r["meta"]["Neptun"]["updated"] == "10.10.2026 07:00"
    assert all("pp" not in i for i in items)                   # keçmiş qiymət "dəyişiklik" kimi göstərilmir


def test_wolt_off_own_plus_wolt_store_keeps_archived_wolt_items():
    d = S.empty_data()
    d["categories"]["sud"]["stores"]["OBA"] = [{"name": "A", "price": 1.0, "wolt_price": 1.1}, {"name": "OnlyWolt", "wolt_price": 2.0}]
    own = {"sud": [{"name": "A", "price": 1.2}]}
    assert S.apply_to_data(own, {}, "OBA", d, {}, wolt_on=False)
    items = {i["name"]: i for i in d["categories"]["sud"]["stores"]["OBA"]}
    assert items["A"]["price"] == 1.2 and "stale" not in items["A"]
    assert items["OnlyWolt"]["wolt_price"] == 2.0 and items["OnlyWolt"]["stale"] is True


def test_failed_run_keeps_previous_files(tmp_path, monkeypatch):
    out = tmp_path / "prices.json"
    S._save(mini("Neptun", 300), out)
    (tmp_path / "history.json").write_text('{"h":{"abc":[["2026-10-01",1.0]]}}')
    b1, b2 = out.read_bytes(), (tmp_path / "history.json").read_bytes()
    monkeypatch.setattr(S, "scrape_wolt", lambda s: {})        # Wolt boş qaytardı
    monkeypatch.setattr("sys.argv", ["scraper.py", "--store", "neptun", "--out", str(out)])
    S.main()
    r = json.load(open(out, encoding="utf-8"))
    assert len(r["categories"]["sud"]["stores"]["Neptun"]) == 300
    assert json.load(open(tmp_path / "history.json"))["h"]["abc"] == [["2026-10-01", 1.0]]


# 10. kateqoriyalaşdırma reqressiya
@pytest.mark.parametrize("name,cat", [("Dobry Alma şirəsi 1 L", "sirə"), ("Coca-Cola 1 L", "kola"), ("Nescafe Gold 190 q", "qəhvə")])
def test_classification_smoke(name, cat):
    got = S.classify(name)
    assert got in S.CATEGORIES and got != "diger", (name, got)


def test_classification_corpus_from_real_data():
    """Real datadakı məhsulların 'digər' payı kiçik qalır (təsnifat pozulmayıb)."""
    n = dg = 0
    for cid, c in PRICES["categories"].items():
        for items in c["stores"].values():
            for it in items:
                n += 1; dg += cid == "diger"
    assert n > 10000 and dg / n < 0.05


# 7. yeni JSON ilə index.html uyğunluğu (node varsa)
@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_index_html_reads_new_and_old_json(tmp_path):
    d = copy.deepcopy(PRICES)
    for c in d["categories"].values():                         # yüngül nüsxə
        for s in c["stores"]:
            c["stores"][s] = c["stores"][s][:25]
    cid = next(k for k, c in d["categories"].items() if c["stores"].get("Bravo"))
    d["categories"][cid]["stores"]["Bravo"][0].update({"stale": True})
    d["meta"] = {"Bravo": {"source_type": "wolt-arxiv", "auto_update": False, "last_success": None}}
    f = tmp_path / "db.json"; f.write_text(json.dumps(d, ensure_ascii=False))
    js = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
const db=JSON.parse(require('fs').readFileSync({json.dumps(str(f))},'utf8'));
for(const old of [true,false]){{
  const D=JSON.parse(JSON.stringify(db)); if(old) for(const c of Object.values(D.categories)) for(const s in c.stores) for(const it of c.stores[s]){{delete it.stale}}
  api.setDB(D); let n=0; for(const g of api.GL()) n+=api.groups(g.id).length;
  if(!(n>0)) throw new Error('qrup yoxdur'); console.log('ok',old,n);
}}"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.count("ok") == 2, r.stderr[-500:]


# ── ad təmizliyi, dublikatlar, şəkil linkləri ──
def test_clean_name():
    assert S.clean_name("FAIRY LIMON MAYE QABYUYAN , 750 ml") == "Fairy Limon Maye Qabyuyan, 750 ml"
    assert S.clean_name("Princessa Nuri Zavtrak V Benqali ,") == "Princessa Nuri Zavtrak V Benqali"
    assert S.clean_name("Crystalex  Maye ( Limon )  750 ml") == "Crystalex Maye (Limon) 750 ml"
    assert S.clean_name("Coca-Cola 1 L") == "Coca-Cola 1 L"


def test_dedupe_keeps_own_then_cheaper_and_distinct_sizes():
    items = [{"name": "Vernel 1.44 L Lale", "price": 8.99}, {"name": "Vernel 1,44 L Lalə", "price": 5.99},
             {"name": "Su 1.5 L", "price": 1.0}, {"name": "Su 15 L", "price": 5.0},
             {"name": "Klar Maye 500ml", "wolt_price": 2.49}, {"name": "KLAR MAYE, 500 ml", "price": 3.99}]
    out = S.dedupe(items)
    assert [i["name"] for i in out] == ["Vernel 1,44 L Lalə", "Su 1.5 L", "Su 15 L", "KLAR MAYE, 500 ml"]


def test_tidy_cleans_old_data_and_drops_images():
    d = mini("OBA", 2, 1.0, wolt=False)
    d["categories"]["sud"]["stores"]["OBA"] = [{"name": "Süd , 1 l", "price": 1.2, "img": "https://x/y.png"},
                                               {"name": "Süd, 1 l", "price": 1.1}]
    S.tidy(d)
    assert d["categories"]["sud"]["stores"]["OBA"] == [{"name": "Süd, 1 l", "price": 1.1}]


def test_apply_to_data_cleans_names_and_keeps_change_tracking():
    d = S.empty_data()
    d["categories"]["sud"]["stores"]["Neptun"] = [{"name": "Süd Atena , 1 l", "wolt_price": 2.0}]
    new = {"sud": [{"name": "Süd Atena , 1 l", "wolt_price": 1.5}, {"name": "Süd  Atena, 1 l", "wolt_price": 1.6}]}
    assert S.apply_to_data({}, new, "Neptun", d, {})
    items = d["categories"]["sud"]["stores"]["Neptun"]
    assert len(items) == 1 and items[0]["name"] == "Süd Atena, 1 l" and items[0]["wolt_price"] == 1.5
    assert items[0]["pp"] == 2.0                               # köhnə (təmizlənməmiş) adla da qiymət dəyişikliyi tapılır


def test_no_image_links_written():
    _, e = S._wolt_entry({"name": "Süd 1 L", "price": 199, "image": {"url": "https://img/x.png"}})
    assert e == {"name": "Süd 1 L", "wolt_price": 1.99}


# ── öz sayt ↔ Wolt birləşdirmə: ölçü, diakritika, dad/rəng ──
def test_merge_own_wolt_needs_same_size():
    own = [{"name": "Süd Atena 1 L", "price": 2.6}]
    wolt = [{"name": "Atena Süd 0.5 L", "wolt_price": 1.5}, {"name": "Atena Süd 1000 ml", "wolt_price": 2.7}]
    out = S.merge_own_wolt(own, wolt)
    assert out[0] == {"name": "Süd Atena 1 L", "price": 2.6, "wolt_price": 2.7}
    assert {"name": "Atena Süd 0.5 L", "wolt_price": 1.5} in out and len(out) == 2   # 0.5 L itmir


def test_merge_own_wolt_folds_diacritics_and_rejects_variants():
    own = [{"name": "GUNEBAXAN YAGI ATENA, 1 l", "price": 4.0}, {"name": "Crystalex Qabyuyan Maye Limon 450ml", "price": 2.49},
           {"name": "Chivas Regal Viski 18 Yaş 700ml", "price": 163.0}]
    wolt = [{"name": "Atena Günəbaxan yağı 1 L", "wolt_price": 4.3}, {"name": "Crystalex Qabyuyan Maye Alma 450ml", "wolt_price": 2.25},
            {"name": "Chivas Regal Viski 12 Yaş 700 ml", "wolt_price": 160.0}]
    out = {i["name"]: i for i in S.merge_own_wolt(own, wolt)}
    assert out["GUNEBAXAN YAGI ATENA, 1 l"].get("wolt_price") == 4.3
    assert "wolt_price" not in out["Crystalex Qabyuyan Maye Limon 450ml"]     # Limon ≠ Alma
    assert "wolt_price" not in out["Chivas Regal Viski 18 Yaş 700ml"]          # 18 ≠ 12
    assert len(out) == 5


def test_merge_own_wolt_rejects_far_prices():
    out = S.merge_own_wolt([{"name": "Prezident Kərə Yağı 82% 1kq", "price": 38.1}], [{"name": "Prezident Kərə Yağı 82% 1 kg", "wolt_price": 7.65}])
    assert "wolt_price" not in out[0] and len(out) == 2


# ── vaxt: Bakı vaxtı ──
def test_times_are_baku_time():
    from datetime import timedelta
    assert SRC.now().utcoffset() == timedelta(hours=4)
    d = S.empty_data()
    assert S.apply_to_data({}, {"sud": [{"name": "Məhsul 0", "wolt_price": 1.0}]}, "Neptun", d, {})
    from datetime import datetime
    upd = datetime.strptime(d["meta"]["Neptun"]["updated"], "%d.%m.%Y %H:%M")
    assert abs(upd - SRC.now().replace(tzinfo=None)) < timedelta(minutes=2)


# ── sayt qurma: hazır kartlar, statik səhifələr, sitemap (node varsa) ──
@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_build_site(tmp_path):
    d = copy.deepcopy(PRICES)
    for c in d["categories"].values():                         # yüngül nüsxə
        for s in c["stores"]:
            c["stores"][s] = c["stores"][s][:40]
    src = tmp_path / "prices.json"; src.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(ROOT / "scripts" / "build_site.js"), "--prices", str(src), "--out", str(tmp_path / "site"),
                        "--site", "https://example.org/q/"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    assert "⚠" not in r.stdout + r.stderr                      # hazır kartlar brauzerin hesabladığı ilə eynidir
    g = json.load(open(tmp_path / "site" / "data" / "groups.json", encoding="utf-8"))
    assert g["v"] == d["last_updated"] and len(g["s"]) == 16
    assert set(g["g"]) == {x["id"] for x in d["groups"] if any(d["categories"].get(c, {}).get("stores", {}).get(s) for c in x["cats"] for s in d["stores"])}
    for p in g["g"].values():
        ix = [i for m in p["m"] for i in m]
        assert len(ix) == len(set(ix)) and all(0 <= i < p["n"] for i in ix)
    sm = (tmp_path / "site" / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://example.org/q/qiymetler/</loc>" in sm and sm.count("<url>") > 20
    page = (tmp_path / "site" / "qiymetler" / "sud" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://example.org/q/qiymetler/sud/">' in page and "#/c/sud" in page and "<script" not in page


# ── böyük aksiya (50%+): Wolt qiyməti varsa o göstərilir ──
def test_big_own_discount_falls_back_to_wolt_price():
    own = [{"name": "Avokado əd", "price": 0.99, "rp": 3.49}, {"name": "Banan kq", "price": 2.0, "rp": 2.5},
           {"name": "Kivi kq", "price": 1.0, "rp": 4.0}]
    wolt = [{"name": "Avokado əd", "wolt_price": 1.99}, {"name": "Banan kq", "wolt_price": 2.2}]
    out = {i["name"]: i for i in S.merge_own_wolt(own, wolt)}
    assert out["Avokado əd"] == {"name": "Avokado əd", "wolt_price": 1.99}      # 72% aksiya → Wolt
    assert out["Banan kq"] == {"name": "Banan kq", "price": 2.0, "wolt_price": 2.2}   # kiçik aksiya: öz qiymət
    assert out["Kivi kq"] == {"name": "Kivi kq", "price": 1.0}                  # Wolt yoxdur: öz qiymət qalır
    assert len(out) == 3 and all("rp" not in i for i in out.values())


# ── BÖYÜK hərfli adlar ──
@pytest.mark.parametrize("raw,want", [
    ("DR.MILK KAUNAS XAMA 20% 350 GR", "Dr.Milk Kaunas Xama 20% 350 gr"),
    ("KLAR ULTRA YAG SOKUCU, 500 ml", "Klar Ultra Yag Sokucu, 500 ml"),
    ("TAC GİLƏZİ AĞ YUMURTA 10 ƏD", "Tac Giləzi Ağ Yumurta 10 əd"),
    ("Coca-Cola 1 L", "Coca-Cola 1 L"), ("XXL", "XXL"), ("Pencil Coloredi-252", "Pencil Coloredi-252")])
def test_all_caps_names_are_normalised(raw, want):
    assert S.clean_name(raw) == want


# ── "Digər"-dəki məhsulların yeri ──
def test_reassign_other_by_keyword_brand_word_and_duplicate():
    d = S.empty_data()
    st = d["categories"]
    st["siqaret"]["stores"]["Bravo"] = [{"name": f"Kent Nanotek {i}", "wolt_price": 5.0} for i in range(3)]
    st["konfet"]["stores"]["Bravo"] = [{"name": "Beyaz Trubka, 1 kg", "price": 3.0}]
    st["diger"]["stores"]["Bazarstore"] = [{"name": "Kent Nanotek Neo 4", "price": 5.2},       # brend → siqaret
                                           {"name": "St Skuter Sc001 530-12", "price": 40.0},  # açar söz → oyuncaq
                                           {"name": "Urojay Qapaq 82 Mm 20 Li", "price": 2.0},  # qeyri-qida → məişət
                                           {"name": "Bumbuz 1 Kq", "price": 4.0}]               # bilinmir → qalır
    st["diger"]["stores"]["Bravo"] = [{"name": "Beyaz Trubka , 1 kg", "price": 3.0}]          # eyni mağazada artıq var → silinir
    assert S.reassign_other(d) == 4
    assert [i["name"] for i in st["diger"]["stores"]["Bazarstore"]] == ["Bumbuz 1 Kq"] and st["diger"]["stores"]["Bravo"] == []
    assert {i["name"] for i in st["siqaret"]["stores"]["Bazarstore"]} == {"Kent Nanotek Neo 4"}
    assert st["oyuncaq"]["stores"]["Bazarstore"][0]["name"].startswith("St Skuter")
    assert st["mesis"]["stores"]["Bazarstore"][0]["name"].startswith("Urojay Qapaq")


def test_reassign_other_on_real_data_never_grows_other():
    # prices.json scraper tərəfindən artıq emal olunub: "diger"-də qalanlar köçürülə bilməyənlərdir, ona görə yalnız artmamasını yoxlayırıq
    # (azalma məntiqi yuxarıdakı sintetik testlə örtülür)
    d = copy.deepcopy(PRICES)
    n0 = sum(len(l) for l in d["categories"]["diger"]["stores"].values())
    S.reassign_other(d)
    n1 = sum(len(l) for l in d["categories"]["diger"]["stores"].values())
    assert n1 <= n0
    ok, errs = SRC.validate_prices(d)
    assert ok, errs


# ── kartın adı: ən oxunaqlı üzv ──
@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_card_shows_most_readable_name(tmp_path):
    db = {"stores": ["OBA", "Bravo"], "groups": [{"id": "sud", "name": "Süd", "cats": ["qatilasdirilmis"]}],
          "categories": {"qatilasdirilmis": {"name": "Qatılaşdırılmış süd", "stores": {
              "OBA": [{"name": "QUSTIYAR QATILASDIRILMIS SUD, 370 g", "price": 2.89}],
              "Bravo": [{"name": "Qustiyar Qatılaşdırılmış Süd 370qr", "wolt_price": 2.7}]}}}}
    f = tmp_path / "db.json"; f.write_text(json.dumps(db, ensure_ascii=False))
    js = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
api.setDB(JSON.parse(require('fs').readFileSync({json.dumps(str(f))},'utf8')));
const g=api.groups('sud'); console.log(JSON.stringify(g.map(x=>[x.name,Object.keys(x.offers).length])));"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    assert json.loads(r.stdout.strip()) == [["Qustiyar Qatılaşdırılmış Süd 370qr", 2]]


# ── növ etiketi: ad növü demirsə alt növ yazılır, etibarlı deyilsə heç nə ──
@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_type_label_only_when_name_hides_type_and_data_agrees(tmp_path):
    sok = [{"name": n, "wolt_price": 5.0} for n in ["Merci Storck Knusper 250qr", "Merci Storck Südlü Şokolad 100qr",
           "Storck Merci Tünd Şokolad 100qr", "Storck Toffifee 125qr", "Storck Riesen 105qr", "Milka Südlü Şokolad 90qr",
           "Twix 50qr", "Skumbriya Merci 200qr"]]
    bal = [{"name": n, "wolt_price": 3.0} for n in ["Santa Skumbriya Hisə 300qr", "Vici Skumbriya File 200qr", "Skumbriya Dondurulmuş kq"]]
    db = {"stores": ["Bravo"], "groups": [{"id": "sirniyyat", "name": "Şirniyyat", "cats": ["sokolad"]},
                                          {"id": "et", "name": "Ət, balıq", "cats": ["baliq"]}],
          "categories": {"sokolad": {"name": "Şokolad", "stores": {"Bravo": sok}},
                         "baliq": {"name": "Balıq", "stores": {"Bravo": bal}}}}
    f = tmp_path / "db.json"; f.write_text(json.dumps(db, ensure_ascii=False))
    js = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
api.setDB(JSON.parse(require('fs').readFileSync({json.dumps(str(f))},'utf8')));
const g=api.groups('sirniyyat'); const pre=Object.fromEntries(g.map(x=>[x.name,api.typeOf(x)]));   // indeks hazır deyil: etiket yox
for(const x of g) delete x.tp; api.tpIdx();
const out=Object.fromEntries(g.map(x=>[x.name,api.typeOf(x)]));
const k=g.find(x=>x.name.includes('Knusper'));
console.log(JSON.stringify({{pre,out,meta:api.metaOf(k)}}));"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    d = json.loads(r.stdout.strip())
    assert not any(d["pre"].values())
    o = d["out"]
    assert o["Merci Storck Knusper 250qr"] == "Şokolad"          # ad növü demir, Storck/Merci başqa şokoladlarda da var
    assert o["Milka Südlü Şokolad 90qr"] == ""                    # ad özü deyir
    assert o["Twix 50qr"] == ""                                   # dəstəkləyən söz yoxdur (yalnız bir məhsul)
    assert o["Skumbriya Merci 200qr"] == ""                       # "Skumbriya" başqa alt növü (balıq) göstərir
    assert d["meta"] == '<b class="tp">Şokolad</b> · 250 q'


# ── qiymət dəyişikliyi nişanı: mənbə dəyişikliyi və 2x-dən böyük sıçrayış dəyişiklik deyil ──
def test_no_change_badge_on_source_switch_or_implausible_jump():
    old = {"Avokado əd": {"name": "Avokado əd", "price": 0.99, "wolt_price": 1.99},
           "Banan kq": {"name": "Banan kq", "price": 2.0},
           "Kivi kq": {"name": "Kivi kq", "wolt_price": 1.0},
           "Alma kq": {"name": "Alma kq", "wolt_price": 1.99, "pp": 0.99, "pd": "2026-10-16"}}
    items = [{"name": "Avokado əd", "wolt_price": 1.99}, {"name": "Banan kq", "price": 1.8},
             {"name": "Kivi kq", "wolt_price": 3.5}, {"name": "Alma kq", "wolt_price": 1.99}]
    hist = {}
    S.mark_changes(old, items, "Araz", hist, "2026-10-17", "2026-10-16")
    by = {i["name"]: i for i in items}
    assert "pp" not in by["Avokado əd"]                     # öz sayt → Wolt
    assert by["Banan kq"]["pp"] == 2.0                      # adi dəyişiklik qalır
    assert "pp" not in by["Kivi kq"]                        # 3.5 dəfə: real sayılmır
    assert "pp" not in by["Alma kq"]                        # köhnə yanıldıcı nişan da daşınmır
    assert list(hist) == [S._hk("Araz", "Banan kq")]


def test_clean_name_strips_trailing_barcode():
    assert S.clean_name("Yağ Svalya 200qr 82% 4770275045353") == "Yağ Svalya 200qr 82%"
    assert S.clean_name("Şor Rb 1 Kg 2100419") == "Şor Rb 1 Kg 2100419"   # qısa kod toxunulmur


@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_index_csp_hash_matches_inline_script():
    r = subprocess.run(["node", str(ROOT / "scripts" / "csp_hash.js"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ── məhsul ikonu: dad/ətir sözü məhsulun özünü üstələmir, hər ikonun öz SVG faylı var ──
ICON_CASES = [
    ("Lays Maxx Barbekü Toyuq Qanadı Çipsi 100qr", "hazir", "cips", "🥔"),
    ("Fanat Suxarı Toyuqlu Ketçuplu 80qr", "hazir", "cips", "🥨"),
    ("Lays MAXX Pizza 4 Pendir 100 Gr", "hazir", "cips", "🥔"),
    ("Kaija Losos File 170 gr Tomat Kremli", "konserv", "konserv", "🐟"),
    ("Dardanel Ton Balığı Qarğıdalı ilə 185qr", "konserv", "konserv", "🐟"),
    ("Sloboda Provansal Zeytunlu Mayonez 67% Paket, 400 ml", "yag_sous", "mayonez", "🫙"),
    ("Biscolata Vafli 117 Q Minis Findiqli 18", "sirniyyat", "vafli", "🧇"),
    ("Natura Şaftalı Şirəsi 1 l", "iceckiler", "sire", "🧃"),
    ("Lipton Soyuq Çay Şaftalı Ətirli 500ml", "iceckiler", "soyuq_cay", "🧋"),
    ("Badamlı Premium Qazlı Su Şb 0.33l", "iceckiler", "qazli_su", "🫧"),
    ("Badamlı Qazsız Su Pet 500ml", "iceckiler", "su", "💧"),
    ("Greenfield Earl Grey Fantazy 50 qr", "iceckiler", "cay", "🍵"),
    ("Bella Pambiq Disk 80 Li", "gigiyena", "beden_baximi", "🧴"),
    ("Colgate Total Diş Məcunu 75ml", "gigiyena", "dis_baximi", "🪥"),
    ("Doneqal Dırnaq Pilkasi Art P010", "gigiyena", "beden_baximi", "💅"),
    ("Hacker Ağcaqanad Üçün Maye 480 saat", "ev", "temizlik", "🦟"),
    ("Aura Şam Ətirli Kofe 32 Saat", "ev", "mesis", "🕯️"),
    ("Domestos Tualet Geli 750ml Şam Ağacı Təravətli", "ev", "temizlik", "🚽"),
    ("Abc Yuyucu Toz Lavanda Avtomat Paket 3kq", "ev", "yuyucu", "🧺"),
    ("Titiz Diş Fırça Qabı 268-2685", "ev", "yuyucu", "🪥"),
    ("Fairy Qab Yuyucu Maye Limon Ətirli 650 ml", "ev", "qabyuyan", "🧽"),
    ("Poltino Dondurulmuş Albalı Çəyirdəksiz 400 qr", "hazir", "dondurulmus", "🍒"),
    ("Vici Brokoli 400 Q Dondurulmuş", "hazir", "dondurulmus", "🥦"),
    ("Köz Künəfə Dondurulmuş 135 qr", "hazir", "dondurulmus", "🍯"),
    ("Super Sun Yarpaq Dolması 300 qr", "hazir", "hazir_yemek", "🥘"),
    ("Miad Alman Yağı Eximo 1 kq", "hazir", "dondurulmus", "🧈"),
    ("Alma Granny Smith kq", "meyve", "alma", "🍏"),
    ("Konti \"Сладкое Созвучие\" Шоколад", "sirniyyat", "konfet", "🍫"),
]


def test_product_icons():
    js = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
const cases={json.dumps([c[:3] for c in ICON_CASES], ensure_ascii=False)};
console.log(JSON.stringify(cases.map(([name,t,c])=>api.iconOf({{name,t,c}}))));"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    got = json.loads(r.stdout.strip())
    bad = [(c[0], c[3], g) for c, g in zip(ICON_CASES, got) if g != c[3]]
    assert not bad, bad


def test_icon_lists_have_no_duplicate_keys_and_every_icon_has_svg():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    body = html[html.index("const EMOJI={"):html.index("const ICON_ALL")]
    for name, lst in re.findall(r'(\w+):IC\(\{([\s\S]*?)\}\)', body):
        keys = re.findall(r'"([^"]+)":"', lst)
        assert len(keys) == len(set(keys)), (name, [k for k in keys if keys.count(k) > 1])
    have = {p.stem for p in (ROOT / "assets" / "twemoji").glob("*.svg")}
    listed = set(re.search(r'var HAVE=new Set\("([^"]+)"', (ROOT / "assets" / "twemoji.js").read_text()).group(1).split())
    assert listed == have
    emo = re.compile("[\U0001F300-\U0001FAFF☀-➿⏰-⏿⬀-⯿]️?")
    missing = {e for e in emo.findall(body) if "-".join(f"{ord(ch):x}" for ch in e if ch != "️") not in have}
    assert not missing, missing


def test_own_plus_wolt_store_multi_branch_switch_skips_only_wolt_badges(monkeypatch):
    d = S.empty_data()
    d["categories"]["sud"]["stores"]["Araz"] = [{"name": "Süd Atena 1 l", "price": 2.0}, {"name": "Kefir Atena 1 l", "wolt_price": 2.0}]
    d["meta"] = {"Araz": {"updated": "15.10.2026 07:00"}}
    monkeypatch.setitem(S.WOLT_SRC, "Araz", "multi-" + S.WOLT_SRC_VER)
    own = {"sud": [{"name": "Süd Atena 1 l", "price": 1.8}]}
    wolt = {"sud": [{"name": "Kefir Atena 1 l", "wolt_price": 1.8}]}
    assert S.apply_to_data(own, wolt, "Araz", d, {})
    by = {i["name"]: i for i in d["categories"]["sud"]["stores"]["Araz"]}
    assert by["Süd Atena 1 l"]["pp"] == 2.0                  # öz sayt qiymət dəyişikliyi qalır
    assert "pp" not in by["Kefir Atena 1 l"]                 # Wolt üsulu dəyişib: median fərqi nişan deyil
    assert d["meta"]["Araz"]["src"] == "multi-" + S.WOLT_SRC_VER
    monkeypatch.delitem(S.WOLT_SRC, "Araz")                  # növbəti gün Wolt alınmadı: üsul yaddaşda qalır
    assert S.apply_to_data(own, {}, "Araz", d, {})
    assert d["meta"]["Araz"]["src"] == "multi-" + S.WOLT_SRC_VER


# ── məhsul şəkilləri: Open Food Facts, ştrix-koda görə (mağazanın şəkli yox) ──
def test_wolt_entry_keeps_only_valid_barcode():
    _, e = S._wolt_entry({"name": "Süd 1 L", "price": 199, "barcode_gtin": "4760095101025", "images": [{"url": "https://img/x.png"}]})
    assert e == {"name": "Süd 1 L", "wolt_price": 1.99, "gtin": "4760095101025"}
    for bad in ("", "12ab", "123", None, 4760095101025):
        _, e = S._wolt_entry({"name": "Süd 1 L", "price": 199, "barcode_gtin": bad})
        assert "gtin" not in e


def test_off_front_image_path():
    import off_images as O
    assert O.folder("4760095101025") == "476/009/510/1025"
    assert O.folder("12345678") == "000/001/234/5678"
    sz = {"200": {"w": 150, "h": 200}}
    imgs = {"1": {"sizes": sz}, "front_ru": {"rev": "3", "sizes": sz}, "front_az": {"rev": 7, "sizes": sz},
            "ingredients_az": {"rev": "4", "sizes": sz}}
    assert O.front("4760095101025", imgs) == "476/009/510/1025/front_az.7"
    assert O.front("4760095101025", {"front_ru": {"rev": "3", "sizes": sz}}) == "476/009/510/1025/front_ru.3"
    assert O.front("4760095101025", {"front_az": {"rev": "3", "sizes": {"400": {}}}}) == ""   # 200 px yoxdur
    assert O.front("4760095101025", {"ingredients_az": {"rev": "3", "sizes": sz}}) == ""
    assert O.front("4760095101025", {"front_x\"y": {"rev": "3", "sizes": sz}}) == ""


def test_off_images_turns_barcode_into_image_and_uses_cache(tmp_path, monkeypatch):
    import off_images as O
    d = mini("Neptun", 0)
    d["categories"]["sud"]["stores"]["Neptun"] = [
        {"name": "A", "wolt_price": 1.0, "gtin": "4760095101025"},
        {"name": "B", "wolt_price": 1.0, "gtin": "4760000000001"},
        {"name": "C", "wolt_price": 1.0, "gtin": "4760000000002"},
        {"name": "D", "wolt_price": 1.0, "im": "476/000/000/0003/front_az.1"}]   # arxiv məhsul: köhnə şəkil qalır
    p, c = tmp_path / "prices.json", tmp_path / "off.json"
    p.write_text(json.dumps(d, ensure_ascii=False))
    c.write_text(json.dumps({"4760000000002": ["", "9999-12-31"]}))   # götürülmüş şəkil: bir daha soruşulmur
    monkeypatch.setattr(O, "PRICES", str(p)); monkeypatch.setattr(O, "CACHE", str(c))
    asked = []
    def fake(ses, codes):
        asked.append(list(codes))
        return {k: ("476/009/510/1025/front_az.3" if k == "4760095101025" else "") for k in codes}
    monkeypatch.setattr(O, "lookup", fake)
    O.run()
    items = json.loads(p.read_text())["categories"]["sud"]["stores"]["Neptun"]
    assert asked == [["4760000000001", "4760095101025"]]
    assert items == [{"name": "A", "wolt_price": 1.0, "im": "476/009/510/1025/front_az.3"},
                     {"name": "B", "wolt_price": 1.0}, {"name": "C", "wolt_price": 1.0},
                     {"name": "D", "wolt_price": 1.0, "im": "476/000/000/0003/front_az.1"}]
    cache = json.loads(c.read_text())
    assert cache["4760095101025"][0] and cache["4760000000001"][0] == "" and cache["4760000000002"] == ["", "9999-12-31"]
    asked.clear(); p.write_text(json.dumps(d, ensure_ascii=False)); O.run()
    assert asked == []                                          # keşdən: təkrar sorğu yoxdur


@pytest.mark.skipif(shutil.which("node") is None, reason="node yoxdur")
def test_card_photo_from_open_food_facts_else_icon(tmp_path):
    db = {"stores": ["OBA", "Bravo"], "groups": [{"id": "sud", "name": "Süd", "cats": ["sud"]}],
          "categories": {"sud": {"name": "Süd", "stores": {
              "OBA": [{"name": "Azərsüd Süd 3.2% 1 l", "price": 2.8}, {"name": "Milla Süd 3.2% 1 l", "price": 2.7}],
              "Bravo": [{"name": "Azərsüd Süd 3.2% 1l", "wolt_price": 2.89, "im": "476/009/510/1025/front_az.3"},
                        {"name": "Milla Süd 3.2% 1l", "wolt_price": 2.79, "im": "x\"><script>"}]}}}}
    f = tmp_path / "db.json"; f.write_text(json.dumps(db, ensure_ascii=False))
    js = f"""const api=require({json.dumps(str(ROOT / 'tests' / 'site_harness.js'))})({json.dumps(str(ROOT / 'index.html'))});
api.setDB(JSON.parse(require('fs').readFileSync({json.dumps(str(f))},'utf8')));
console.log(JSON.stringify(api.groups('sud').map(g=>[g.name.split(' ')[0],api.picOf(g)])));"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    got = dict(json.loads(r.stdout.strip()))
    assert got["Azərsüd"].startswith('<img class="ph" src="https://images.openfoodfacts.org/images/products/476/009/510/1025/front_az.3.200.jpg"')
    assert "<" not in got["Milla"]                              # yolu düzgün olmayan "im" göstərilmir: ikon


def test_fluent_icon_list_matches_files_and_license():
    js = (ROOT / "assets" / "twemoji.js").read_text(encoding="utf-8")
    fl = set(re.search(r'var FL=new Set\("([^"]*)"', js).group(1).split())
    files = {p.stem for p in (ROOT / "assets" / "fluent").glob("*.webp")}
    assert fl == files and len(fl) > 150
    assert fl <= {p.stem for p in (ROOT / "assets" / "twemoji").glob("*.svg")}   # Fluent yüklənməsə Twemoji-yə düşür
    assert "MIT License" in (ROOT / "assets" / "fluent" / "LICENSE").read_text(encoding="utf-8")
