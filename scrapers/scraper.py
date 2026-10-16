#!/usr/bin/env python3
"""
Harda Ucuz Scraper
  Bravo  -> Wolt
  OBA    -> oba.az
  Araz   -> arazmarket.az API (+ Wolt)
  Neptun -> Wolt (neptun.az kataloqu işləmir)
  Tamstore, Rahat -> Wolt (öz saytlarında qiymətli kataloq yoxdur)
  SPAR -> Wolt
  Bazarstore -> bazarstore.az (nopCommerce HTML)

İstifadə:
  python scraper.py
  python scraper.py --store bravo
  python scraper.py --store oba
  python scraper.py --recategorize   (şəbəkəsiz: mövcud datanı yenidən təsnif edir)
"""
import json, os, re, time, argparse
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from sources import SOURCES, wolt_enabled, source_meta, validate_prices, store_counts, atomic_write_json, now

def _low(t):
    """Kiçik hərf + I/İ/ı eyniləşdirilir (saytlar böyük hərfdə "QIRMIZI"/"QİRMİZİ" qarışıq yazır)."""
    return t.replace("İ", "i").replace("ı", "i").replace("I", "i").lower()

# ── Mətn normallaşdırma (index.html-dəki fold() ilə eyni) ─────────────────────────────────────────────────
# 1-ci səviyyə: diakritik, artıq nöqtə (U+0307: "İ̇çkisi"), é/ä, apostrof, nbsp, kiril. Təsnifat YALNIZ bunu işlədir.
_DIA = str.maketrans({"ç":"c","ə":"e","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u","̇":"","é":"e","è":"e","ê":"e","ë":"e","ė":"e",
                      "ä":"a","â":"a","à":"a","á":"a","å":"a","ã":"a","í":"i","î":"i","ï":"i","ó":"o","ô":"o","ò":"o","õ":"o",
                      "ú":"u","û":"u","ù":"u","ñ":"n","'":"","’":"","‘":"","`":"","´":""," ":" ",
                      "×":"x","–":"-","—":"-"})
_CYR_T = {"а":"a","б":"b","в":"v","г":"q","д":"d","е":"e","ё":"yo","ж":"j","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n",
          "о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"x","ц":"c","ч":"c","ш":"s","щ":"s","ъ":"","ы":"i","ь":"",
          "э":"e","ю":"yu","я":"ya","ә":"e","і":"i","ј":"j","ғ":"g","ү":"u","ө":"o","һ":"h"}
_CYR_H = {"р":"p","с":"c","у":"y"}   # latın sözündə oxşar kiril hərfi: "Сola", "Fermentу"
_CYR_RX, _CYRW_RX = re.compile("[Ѐ-ӿ]"), re.compile("[a-zЀ-ӿ]+")

def _cyr(m):
    w = m.group()
    if not _CYR_RX.search(w): return w
    h = re.search("[a-z]", w) is not None
    return "".join((h and _CYR_H.get(c)) or _CYR_T.get(c, c) for c in w)

def _f(t):
    """Diakritiksiz müqayisə: "Günəbaxan Yağı" = "GUNEBAXAN YAGI" = "Gunebaxan Yagi"; "Доширак" = "dosirak"."""
    t = _low(t).translate(_DIA)
    return _CYRW_RX.sub(_cyr, t) if _CYR_RX.search(t) else t

# 2-ci səviyyə (transliterasiya): shokolad=şokolad, chips=çips, xlebtsi=xlebçi, wafers=vafers, ekstra=extra.
# Təsnifatda yalnız ad heç nə vermədikdə 2-ci cəhd kimi işlənir ("dish" -> "dis" = "diş" riski).
_KEY_C = {"s":"s","c":"c","k":"x","z":"j","g":"g"}
_KEY_R = [(re.compile(r"ks(?!h)"), "x"), (re.compile(r"([sckzg])h"), lambda m: _KEY_C[m.group(1)]),
          (re.compile(r"ts(?=[aeiouy])"), "c"), (re.compile(r"(^|[^\d])w"), r"\1v")]

def _k(t):
    t = _f(t)
    for rx, r in _KEY_R: t = rx.sub(r, t)
    return t


# ── Kateqoriyalar: Wolt (Bravo/Tamstore), Araz və OBA-nın öz bölgüsünə uyğun ~19 qrup / alt növlər ──────────
# "kw" = məhsul adında açar söz (mağazanın kateqoriyası yoxdursa); kw=[] olanlar yalnız mağaza kateqoriyasına görə.
# SIRA VACİBDİR: ad üzrə ilk uyğun gələn götürülür.
def _c(name, kw=(), excl=()):
    d = {"name": name, "kw": list(kw)}
    if excl: d["excl"] = list(excl)
    return d

CATEGORIES = {
    # geyim / tekstil (Bazarstore, OBA)
    "tekstil":   _c("Ev tekstili",       ["hamam dəsmal","əl dəsmal","çimərlik dəsmal","körpə dəsmal","yastıq","yorğan","kilim","pərdə","çarpayı","xalça","ədyal","paltar asılqan","əl-üz dəsmal","hamam dəs","alez"], ["çoban"]),
    "ayaqqabi":  _c("Ayaqqabı, corab",   ["ayaqqabı","çəkənək","corab","çorab","kalqotka","kapron","ayaqalt"]),
    "geyim":     _c("Geyim",             ["köynək","mayka","futbolka","boxer","şort","gödəkçə","hoody","shirt","kota ","fufayka","svitşot","ətək","etek","köynək","şalvar","şərf"]),
    # heyvan yemi ("Felix Junior" uşaq məhsulu deyil), ev / gigiyena (ən əvvəl: "limon ətirli qabyuyan" meyvə olmasın)
    "pisik_yemi":_c("Pişik yemi",        ["pişik","whiskas","felix","kitekat","sheba"], ["qumu","qum "]),
    "it_yemi":   _c("İt yemi",           ["itlər","köpək","pedigree","chappi","it üçün","it yemi","it quru","it nəm"]),
    "heyvan_diger":_c("Heyvan baxımı, aksesuar", ["nəm yem","quru yem","royal canin","pişik qumu"]),
    "qabyuyan":  _c("Qabyuyan vasitə",   ["qabyuyan","qab yuyan","maşın duzu","fairy","qab yuyucu"]),
    "yuyucu":    _c("Paltar yuyucu",     ["yuyucu","ləkə aparan","ləkə təmizləyən","paltaryuyan","kir yuyan","paltar suyu","ariel","persil","yumşaldıcı","kondisioner","perwoll","yuma gel","yuma toz","yumuşaldıcı","vanish","bingo","avtomat","automat","ləkə təmizləy","softener","vernel","pods","geyim şampun"]),
    "temizlik":  _c("Təmizlik vasitəsi", ["təmizlə","ağardıcı","dezinfeksiya","domestos","cif ","təmizlik","təravətləndirici","həşərat","hava trvt","hava təravətləndirici","ağcaqanad","ovma tozu","glade","air-wick","wc","bulasik","bulaşıq","sökücü"], ["makiyaj","üz üçün","təmizlənmiş","təmizlənmə"]),
    "zibil":     _c("Zibil torbası",     ["zibil"]),
    "bisirme":   _c("Folqa, streç, bişirmə", ["folqa","streç","pergament","bişirmə kağız","sellofan"]),
    "kagiz":     _c("Kağız məhsulları",  ["tualet kağız","kağız dəsmal","mətbəx kağız","salfet","dəsmal","kağız məhsul"]),
    "qadin_gig": _c("Qadın gigiyenası",  ["qadın bez","gündəlik bez","panty","carefree","libresse","discreet","molped","always","kotex","tampon","gigiyenik","gündəlik","bella","ped ","bella bez"]),
    "usaq_baxim":_c("Uşaq baxımı",       ["uşaq bezi","uşaq yağı","johnson","önlem","dory baby","sleepy","lody","evy baby","bezi","pampers","huggies","molfix","uşaq şampun","uşaq sabun","uşaq krem","tuman","pants","baby ","junior"]),
    "dis_baximi":_c("Diş və ağız baxımı",["diş","ağız","colgate","listerine","splat","oral-b","oral b"]),
    "tras":      _c("Təraş",             ["təraş","tıraş","gillette","ülgüc","arko"]),
    "sac_boya":  _c("Saç boyası",        ["saç boyası","palette","boyası","miss magic"], ["dırnaq"]),
    "sac_baximi":_c("Saç baxımı",        ["şampun","saç","balzam","pantene","elseve","head & shoulders","h&s","garnier"], ["dodaq","balzamik","balsamic"]),
    "deo":       _c("Dezodorant",        ["dezodorant","deodorant","dezodrant","dezodarant","roll-on","roll on","deo","antiperspirant","rexona","old spice","speed stick"]),
    "etir":      _c("Parfüm və ətir",    ["parfüm","ətir","tualet suyu","kolon"]),
    "kosmetika": _c("Makiyaj və kosmetika",["makiyaj","dırnaq boyası","kirpik","dodaq","pudra","maskara","lak ","kosmetik","manikür","miselyar","misellyar","micellar","makyaj","kontur"], ["duş gel"]),
    "beden_baximi":_c("Bədən və üz baxımı",["sabun","duş gel","duş geli","əl kremi","üz kremi","bədən kremi","losyon","nivea","dove","maska","tonik","serum",
                  "bədən üçün","üz üçün","günəş krem","vazelin","pambıq","vanna","geli","sprey","vaseline","prezervativ","əl krem","krem yağı","qulaq çöpü","qulaq çubu","pambıqlı çubu","kulak"], ["schweppes","şırnaq"]),
    # uşaq
    "usaq_qida": _c("Uşaq qidası",       ["uşaq sıyıq","uşaq qida","uşaq pürə","uşaq süd","süd qarışığ","uşaq","bebi","aptamil","nutrilon","kabrita","gerber","hipp","agusha","nanny","fruto","nestogen","similac","bellakt"]),
    # spirtli / tütün
    "pive":      _c("Pivə",              ["pivə"], ["spirtsiz","alkoqolsuz"]),
    "araq":      _c("Araq və votka",     ["araq","votka","vodka","kazatskaya"]),
    "viski":     _c("Viski",             ["viski","burbon","whisky","whiskey"]),
    "serab":     _c("Şərab və şampan",   ["şərab","şampan","vermut","martini","sidr"], ["konyak","likör","brendi","araq","vodka","balzam"]),
    "likor":     _c("Konyak, likör, digər",["konyak","brendi","likör","tekila","rakı","spirtli","alkoqollu","gin ","beefeater"], ["spirtsiz","alkoqolsuz"]),
    "siqaret":   _c("Siqaret və tütün",  ["siqaret","tütün","terea","heets","ploom","rothmans","sobranie","marlboro","winston","parliament","davidoff","dunhill","compact","pall mall","alışqan","nano ","viceroy","ld club","kent beat","argo","black style","want line","winchester"], ["dəsmal","makyaj","hava","qab","oyun","çöpü","qulaq","baby","bag"]),
    # şirniyyat / içki (emal olunmuş məhsullar meyvə-tərəvəzdən əvvəl)
    "dondurma":  _c("Dondurma",          ["dondurma","plombir","plom.","vafli stəkan","vafli stekan","cornetto","magnum","algida","vienetta","maxibon","eskimo"]),
    "krem_pasta":_c("Şokolad əzməsi, krem pasta",["nutella","əzmə","krem şokolad","krem pasta","şanti","şokolad yağ","sokalad yag","şokokrem","şokolad krem","şokolad pasta"], ["yulaf əzmə"]),
    "pecenye":   _c("Peçenye və biskvit",["biskrem","peçenye","biskvit","kraker","kreker","bisküvit","kurabiye","kurabiyə","pryanik","biskuvi","biskivit","pirojnı","biskuvi","pryannik","pryanko","peçenya","qurabiye","cookie","cookies","biscuit","pechenye","pechenie","digestive","otrubi","etimek"]),
    "vafli":     _c("Vafli",             ["vafli","gofret","waflim","wafer"]),
    "keks":      _c("Keks və kruasan",   ["keks","donut","pirojnoye","pirojnoe","krouassan","kruasan","rulet","pirojna","kruassan","kruasan","muffin","brauni","browni","cake","popkek","kek","künəfə","topkek","macarons","puf "]),
    "tort":      _c("Tort",              ["tort","paxlava","ptifur","kadayif"], ["tortimilka","tortiglioni"]),
    "sokolad":   _c("Şokolad",           ["şokolad","shokolad","sokalad","çikolata","baton","choco","pudinq","kitkat","snickers","twix","bounty","pralin","mars ","biskolata","biscolata","today goldies","konfirom","plitka","tweels","alpengold"], ["isti şokolad","hot chocolate"]),
    "konfet":    _c("Konfet, jele, saqqız",["konfet","sürpriz","surprise","oyuncaq yumurta","oyuncaqlı yumurta","toffee","iris","meller","süd damla","mentos","skittles","dirol","orbit","eclipse","fruittella","fruit-tella","karamel","jele","zefir","draje","saqqız","jelibon","marmelad","pastila","roshen","ülker","tic tac","sour","qummi","haribo","kinder","ferrero","raffaello","lolipop","candy","bonbon","medvejata","toybox","bükmə","lollipop","ozmo","kakoslu","gummi","marshmallow","marşmelou","marsmelou","sufle","bebeto","chupa chups"], ["soyuq kofe"]),
    "halva":     _c("Halva və lokum",    ["halva","lokum","kozinak","pişmaniyə","pismaniye","xalva"]),
    "bal":       _c("Bal",               ["təbii bal","çiçək balı","bal ","dağ balı","çiçək balı","cökə balı","ağac balı","süzmə bal"]),
    "soyuq_cay": _c("Soyuq çay",         ["soyuq çay","ice tea","fuse tea","bubble tea","buzz tea"]),
    "energetik": _c("Enerji içkisi",     ["red bull","monster","burn ","hell energy","hell","predator","full nitro","full energy","energy drink","xl energy",
                                         "adrenalin","bizon","gorilla","enerji"], ["coffee","kofe","qəhvə","latte","kapuçino","cappuccino","vitamin","pivə"]),
    "kola":      _c("Kola və qazlı içki",["kola","pepsi","fanta","sprite","qazlı içki","soda","qazlı","cola","mountain dew","mirinda","7up","gazoz","qazoz","schweppes","alkoqolsuz pivə","spirtsiz pivə"]),
    "limonad":   _c("Limonad",           ["limonad","içki","icki","mountain dew","kvas","moxito","mojito","mohito","chernogolovka","milkis","vips"]),
    "cay":       _c("Çay",               ["çay","lipton","ahmad","azərçay","pekoe","tamashaee","akbar","greenfield","buket"], ["çaydan"]),
    "qehve":     _c("Qəhvə və kakao",    ["qəhvə","isti şokolad","hot chocolate","nescafe","lavazza","kofe","coffee","kakao","jacobs","jacob","kürükahveci","kahve","caffito","3-də 1","3ü 1","3in1","3 in 1","monarch","mokka","espresso","cappuccino","kapuçino","kappuçino","capuccino","latte","mocha","starbucks"], ["qəhvəyi"]),
    "sire":      _c("Şirə və nektar",    ["şirəsi","şirə","mors","nektar","meyvə suyu","alma suyu","portağal suyu","kompot","sandora","cappy"]),
    "qazli_su":  _c("Qazlı su, mineral",  ["mineral su","qazlı su","borjomi","narzan"]),
    "su":        _c("Su",                ["içməli su","mənbə suyu","qazsız","essentuki","yessentuki","sirab","bonaqua","badamlı","dübrar","kəhriz","sarıkız","damla su"]),
    "cips":      _c("Çips",              ["çips","chips","popkorn","popcorn","pretzel","qrenki","grenki","xrusteam","lays","pringles","cheetos","çubuq","crisp","potato","xlebsi","xlebci","xlebtsi","suxari","snack","sticks","poof","joyzz","doritos","qarğıdalı çubuq"], ["qulaq","bambuk"]),
    "tum":       _c("Tum və ləpə",       ["tum","tumu","tumlar","günəbaxan ləpə","balqabaq ləpə","mister tum","ləpə","suxari"]),
    "mayonez":   _c("Mayonez",           ["mayonez"]),
    "ketcup":    _c("Ketçup və sous",    ["ketçup","ketchup","sous"], ["sousunda","sousda"]),
    "xardal":    _c("Xardal, xrən, acika",["xardal","xrən","acika"]),
    "sirke":     _c("Sirkə",             ["sirkə","uksus"]),
    "zeytun_yagi":_c("Zeytun yağı",      ["zeytun yağ"], ["yağında","yağda","krem","sabun","şampun","balzam","losyon"]),
    "bitki_yagi":_c("Bitki yağı",        ["günəbaxan yağ","ayçiçəyi yağ","bitki yağ","qarğıdalı yağ"], ["yağında","yağda"]),
    "makaron":   _c("Makaron",           ["makaron","spagetti","vermişel","penne","fusilli","farfalle","lazanya","tagliatelle","fettuccine","spaghetti"]),
    "eriste":    _c("Əriştə",            ["əriştə","doşirak","noodle","lapşa","lapsha","siemsam","ramen","düyü vermişel","düyü vermeşil"]),
    "corek":     _c("Çörək",             ["çörək","lavaş","çörəyi","coreyi","hot dog","tost","bulka","qoğal","simit","kətə"]),
    "hazir_yemek":_c("Hazır yemək, şorba",["pelmen","manti","xinkali","vareniki","naget","nuggets","naqqet","şnitzel","gyoza","pizza","piroq","börək","borek","lahmacun","qutab","hazır yemək","şorba","xacapuri","hazır sup","sup ","xəngəl","dolma","kabab","xəmir","naggets"], ["qabartma"]),
    "susi":      _c("Suşi",              ["suşi","sushi","nori"]),
    "konserv":   _c("Konserv",           ["konserv","tomatda","sousunda","ton balığ","ton balıq","şprot","sprot","sardina","kilka","ajvar","salatı","leco","lecho","tuna"]),
    "zeytun":    _c("Zeytun",            ["zeytun","maslin"]),
    "tursu":     _c("Turşu",             ["turşu","turshu"]),
    "pomidor_pasta":_c("Pomidor pastası", ["pomidor pasta","tomat pasta"]),
    "murebbe":   _c("Mürəbbə və cem",    ["mürəbbə","povidla","cem","cemi","povidlo","bəkməz","behmez"]),
    # ət
    "sosis":     _c("Sosis",             ["sosis","sosiska","sardelka"]),
    "kolbasa":   _c("Kolbasa",           ["kolbasa","salam","servelat","vetçina","sucuq","sucuk","jambon","krakov","doktorskaya","rosko"], ["sosis"]),
    "hise":      _c("Hisə verilmiş ət",  ["hisə verilmiş","hisə","bekon"]),
    "deniz":     _c("Dəniz məhsulları",  ["krevet","midiya","kalamar","kürü","xərçəng"], ["kuru maya"]),
    "baliq":     _c("Balıq",             ["balıq","qaxac","tuna","ton ","skumbriya","losos","siyənək","seld ","seledka","forel","kilkə","kilka","sprot"]),
    "toyuq":     _c("Toyuq",             ["toyuq","cücə","broylyer","bud","qanad","tabaka"]),
    "dana_ati":  _c("Dana əti",          ["dana"]),
    "qoyun_ati": _c("Qoyun, quzu əti",   ["qoyun","quzu"]),
    "hindi":     _c("Hindi",             ["hindi","hinduşka"]),
    "et_diger":  _c("Digər ət məhsulları",["kotlet","küftə"]),
    # süd məhsulları
    "pendir":    _c("Pendir",            ["pendir","krem çiz","kremçiz","cream cheese","mascarpone","maskarpone","mozzarella","motsarella","rikotta","ricotta",
                                         "feta","brınza","cheddar","çeddar","gouda","parmesan","camembert"], ["mayası"]),
    "kere_yagi": _c("Kərə yağı",         ["kərə yağ","butter","spred","marqarin","margarin","əridilmiş yağ","eridilmish yag"]),
    "xama":      _c("Xama",              ["xama","smetana"]),
    "qaymaq":    _c("Qaymaq",            ["qaymaq"], ["qatıq","qatığı","kefir","ayran","dovğa","kəsmik","yoqurt","xama"]),
    "kesmik":    _c("Kəsmik",            ["kəsmik","şor"]),
    "sirok":     _c("Sırok və desert",   ["sırok","desert"]),
    "yoqurt":    _c("Yoqurt",            ["yoqurt","yogurt"], ["içki","şirə"]),
    "qatiq":     _c("Qatıq",             ["qatıq","qatığı","katık"]),
    "kefir":     _c("Kefir və ayran",    ["kefir","ayran","dovğa"]),
    "sud":       _c("Süd",               ["süd","südlü kokteyl","süd kokteyl"], ["kakao","soya"]),
    "yumurta":   _c("Yumurta",           ["yumurta"], ["fırça","şokolad","sürpriz","surprise","kinder","oyuncaq","ozmo","toybox","kids box","ozibox"]),
    "qoz":       _c("Qoz-fındıq, quru meyvə",["fındıq","qoz","badam","fıstıq","kişmiş","qurudulmuş","çərəz","püstə","kaju","xurma","quru ərik","innab","araxis","antep","noğul","toxumu"]),
    # tərəvəz
    "kartof":    _c("Kartof",            ["kartof"]),
    "pomidor":   _c("Pomidor",           ["pomidor","tomat"]),
    "xiyar":     _c("Xiyar",             ["xiyar"]),
    "soyan":     _c("Soğan",             ["soğan","soyan"]),
    "kelem":     _c("Kələm",             ["kələm","kapusta"]),
    "yerkoyu":   _c("Yerkökü",           ["yerkökü","morkov"]),
    "cuqundur":  _c("Çuğundur",          ["çuğundur","svekla"]),
    "badimcan":  _c("Badımcan",          ["badımcan"]),
    "biber":     _c("Bibər",             ["bibər"]),
    "sarimsaq":  _c("Sarımsaq",          ["sarımsaq"]),
    "goyerti":   _c("Göyərti",           ["göyərti","cəfəri","şüyüd","reyhan","ispanaq","kərəviz"]),
    "gobelek":   _c("Göbələk",           ["göbələk"]),
    "balqabaq":  _c("Balqabaq, kabak",   ["balqabaq","kabak"]),
    # meyvə
    "alma":      _c("Alma",              ["alma"], ["sirkə"]),
    "armud":     _c("Armud",             ["armud","heyva"]),
    "saftal":    _c("Şaftalı, ərik",     ["şaftalı","nektarin","ərik","gavalı"]),
    "gilas":     _c("Gilas, albalı",     ["gilas","albalı"]),
    "uzum":      _c("Üzüm",              ["üzüm"], ["sirkə","şərab","kişmiş"]),
    "banan":     _c("Banan",             ["banan"]),
    "kivi":      _c("Kivi",              ["kivi"]),
    "limon":     _c("Limon",             ["limon"], ["limonsıxan","limon sıxan"]),
    "portaqal":  _c("Portağal",          ["portağal","portakal"]),
    "mandarin":  _c("Mandarin, qreypfrut",["mandarin","qreypfrut","naringi"]),
    "nar":       _c("Nar",               ["nar"]),
    "ekzotik":   _c("Ekzotik meyvə",     ["ananas","avokado","avakado","mango","kokos","papaya","pitaya"]),
    "gile":      _c("Giləmeyvə",         ["çiyələk","moruq","qaragilə","böyürtkən","əzgil"]),
    "qarpiz":    _c("Qarpız, yemiş",     ["qarpız","yemiş"]),
    # bakaliya
    "duyu":      _c("Düyü",              ["düyü","pirinc","sella","basmati"], ["unu"]),
    "merci":     _c("Mərcimək",          ["mərcimək","mərci qırmızı","mərci yaşıl","mərci sarı","qırmızı mərci","yaşıl mərci","sarı mərci"]),
    "noxud":     _c("Noxud",             ["noxud"]),
    "fasulya":   _c("Lobya, fasulya",    ["fasulya","lobya"]),
    "qarabashaq":_c("Qarabaşaq",         ["qarabaşaq","grechka"]),
    "yulaf":     _c("Yulaf",             ["yulaf","ovsyanka","gerkules","qerkules","herkules"]),
    "bulgur":    _c("Bulğur",            ["bulğur","bulqur","manna","yarması","yarma "]),
    "un":        _c("Un",                ["buğda unu","ali növ un","birinci növ un","çovdar unu","qarğıdalı unu","unu","un"]),
    "seher":     _c("Səhər yeməyi, müsli",["müsli","sıyıq","qranola","granola","qronola","corn flakes","səhər yemək","lopa","səhər yeməyi","nesquik"]),
    "duz":       _c("Duz",               ["duz","duzu","xörək duzu"]),
    "sekerqum":  _c("Şəkər",             ["şəkər","qənd"], ["şəkərbura","şəkərçörə","şəkər çörə"]),
    "istiot":    _c("İstiot və ədviyyat",["istiot","ədviyyat","zirə","darçın","mixək","kəkik","sarıkök","zəfəran","paprika","pul bibər","acı biber","aci biber","kara biber","qarabibər","keşniş","qabartma tozu","vanilin","kraxmal","nişasta","maya"]),
    "bulyon":    _c("Bulyon",            ["bulyon"]),
    # digər
    "saglam":    _c("Sağlam və diyet qida",["dietik","diyet","diabetik","podslastitel","şirinləşdirici","protein","qlütensiz","glutensiz","vitadiet","fitnes","fitness"]),
    "mesis":     _c("Mətbəx və məişət əşyaları",["stəkan","boşqab","qaşıq","çəngəl","tava","qazan","süpürgə","əlcək","kibrit","batareya","lampa","lamp","plastik","paket","süngər","fincan","saxlama","mətbəx","qab ","şüşə qab","ləyən","organayzer","asılqan","piknik","bıçaq","süzgəc","kley","mop","fırça","daraq","tərlik","bəzək","stol","ütü","çanta","qabı","dəsti","şüşə ","bez ","torbası","ventilyator","çamadan","tük toplayıcı","örtüyü","doğrama","blender","dograyici","filter","butulkası","matara","şam ","keramika","termos","portatif","dibçək","buz qəlibi","qəlib","sıxan","limonsıxan","duzluq","üzmə halqa","skoç","yeni il","işığı","torpaq","üzmə","torpağ","sürahi","masa","mikser","sürtgəc","dilimləyici","qıfıl","bakal"], ["şam fıstı","stəkanda"]),
    "oyuncaq":   _c("Oyuncaq",           ["oyuncaq","konstruktor","pazl","kukla","oyuncağ","şar ","oyun ","puzzle","fiqur","stadion"]),
    "dereterlik":_c("Dəftərxana",        ["dəftər","qələm","karandaş","marker","albom","qayçı"]),
    "avto":      _c("Avtomobil məhsulları",["maşın üçün","avtomobil","avto "]),
    # yalnız mağaza kateqoriyasına görə
    "sebze_diger":_c("Digər tərəvəz", ["aysberq","kahı"]),
    "meyve_diger":_c("Digər meyvə"),
    "dondurulmus":_c("Dondurulmuş məhsul", ["dondurulmuş","donmus","donmuş","fry me","donuq"]),
    "bakliyyat": _c("Taxıl, bakliyyat", ["irmik","mannı"]),
    "sous_diger":_c("Digər sous", ["narşərab"]),
    "diger":     _c("Digər məhsullar"),
}

# Saytda göstərilən ümumi kateqoriyalar (alt növlər = yuxarıdakı kateqoriyalar)
GROUPS = [
    {"id":"meyve",    "name":"Meyvə",                 "cats":["alma","armud","saftal","gilas","uzum","portaqal","mandarin","limon","banan","kivi","nar","ekzotik","gile","qarpiz","meyve_diger"]},
    {"id":"sebze",    "name":"Tərəvəz",               "cats":["kartof","pomidor","xiyar","soyan","kelem","yerkoyu","cuqundur","badimcan","biber","sarimsaq","goyerti","gobelek","balqabaq","sebze_diger"]},
    {"id":"sud",      "name":"Süd məhsulları və yumurta","cats":["sud","yoqurt","qatiq","kefir","xama","qaymaq","kesmik","sirok","pendir","kere_yagi","yumurta"]},
    {"id":"et",       "name":"Ət, balıq, kolbasa",    "cats":["toyuq","hindi","dana_ati","qoyun_ati","et_diger","kolbasa","sosis","hise","baliq","deniz"]},
    {"id":"corek",    "name":"Çörək və unlu məmulat", "cats":["corek"]},
    {"id":"bakaliya", "name":"Taxıl, makaron, un",    "cats":["duyu","merci","noxud","fasulya","qarabashaq","yulaf","bulgur","bakliyyat","makaron","eriste","un","seher"]},
    {"id":"sirniyyat","name":"Şirniyyat və desert",   "cats":["sokolad","konfet","halva","pecenye","vafli","keks","tort","dondurma","bal","murebbe","krem_pasta"]},
    {"id":"hazir",    "name":"Qəlyanaltı və hazır yemək","cats":["cips","tum","qoz","hazir_yemek","dondurulmus","susi"]},
    {"id":"konserv",  "name":"Konserv və turşu",      "cats":["konserv","zeytun","tursu","pomidor_pasta"]},
    {"id":"iceckiler","name":"İçkilər",               "cats":["su","qazli_su","kola","limonad","soyuq_cay","sire","energetik","cay","qehve"]},
    {"id":"yag_sous", "name":"Yağ, sous, ədviyyat",   "cats":["zeytun_yagi","bitki_yagi","mayonez","ketcup","xardal","sous_diger","sirke","duz","sekerqum","istiot","bulyon"]},
    {"id":"usaq",     "name":"Uşaq məhsulları",       "cats":["usaq_qida","usaq_baxim"]},
    {"id":"gigiyena", "name":"Gigiyena və baxım",     "cats":["beden_baximi","deo","etir","tras","kosmetika","sac_baximi","sac_boya","dis_baximi","qadin_gig","kagiz"]},
    {"id":"ev",       "name":"Ev və məişət",          "cats":["qabyuyan","yuyucu","temizlik","zibil","bisirme","mesis"]},
    {"id":"heyvan",   "name":"Heyvan yemi",           "cats":["pisik_yemi","it_yemi","heyvan_diger"]},
    {"id":"oyuncaq",  "name":"Oyuncaq və dəftərxana", "cats":["oyuncaq","dereterlik","avto"]},
    {"id":"spirtli",  "name":"Spirtli içkilər",       "cats":["pive","araq","viski","serab","likor"]},
    {"id":"tutun",    "name":"Tütün məhsulları",      "cats":["siqaret"]},
    {"id":"saglam",   "name":"Sağlam və diyet qida",   "cats":["saglam"]},
    {"id":"geyim",    "name":"Geyim və tekstil",       "cats":["geyim","ayaqqabi","tekstil"]},
    {"id":"diger",    "name":"Digər məhsullar",       "cats":["diger"]},
]
_missing = {c for g in GROUPS for c in g["cats"]} ^ set(CATEGORIES)
assert not _missing, _missing

ALL_STORES = ["Bravo","OBA","Araz","Neptun","Tamstore","Rahat","Bazarstore","SPAR"]
# Öz saytı/API-si olmayan mağazalar: qiymət yalnız Wolt-dan (saytda <sup>W</sup> ilə işarələnir).
# Neptun (neptun.az boş cavab verir), Bravo/Tamstore/Rahat (saytlarında yalnız kampaniyalar var) — 2026-10 yoxlanılıb.
WOLT_ONLY = {"Bravo","Neptun","Tamstore","Rahat","SPAR"}

# Hər mağaza üçün bir neçə Wolt filialı: ilk işləyən istifadə olunur.
# Mühit dəyişəni ilə əvəz etmək olar: WOLT_SLUG_NEPTUN=... (vergüllə bir neçə)
WOLT_SLUGS = {
    "Bravo":  ["bravo-supermarket-globus-centre", "bravo-supermarket-28-may",
               "bravo-supermarket-narimanov"],
    "OBA":    ["oba-market-nerimanov-1", "oba-market-narimanov", "oba-market-yasamal"],
    "Araz":   ["araz-supermarket-20-yanvarr", "araz-supermarket-narimanov", "araz-supermarket-yasamal",
               "araz-supermarket-28-may"],
    "Tamstore": ["tamstore-narimanov-1", "tamstore-papanin"],
    "Rahat":  ["rahat-supermarket-yasamal", "rahat-supermarket-azadlig", "rahat-supermarket-bayil"],
    "Neptun": ["neptun-supermarket-28", "neptun-supermarket-narimanovv", "neptun-8-mkr",
               "neptun-supermarket-xalqlar"],
    "SPAR":   ["spar-axundov", "araz-spar-1-3mkr", "araz-supermarket-hacibeyli"],
}

# Çoxfilialli şəbəkələr: bu filialların hamısının kataloqu birləşdirilir (məhsul sayı artır).
# Wolt filialları fərqli çeşid saxlayır (Koroğlu hipermarketi ~14 min, kiçik filial ~6 min məhsul).
# Eyni məhsulun qiyməti filiallarda fərqli ola bilər: filiallar üzrə median götürülür (cüt sayda aşağı orta).
# Mühit dəyişəni ilə əvəz etmək olar: WOLT_BRANCHES_BRAVO=slug1,slug2
WOLT_BRANCHES = {
    "Bravo": ["bravo-hypermarket-koroglu", "bravo-radiozavod", "bravo-supermarket-globus-centre",
              "bravo-supermarket-yeni-yasamal", "bravo-azadlig-avenue", "bravo-supermarket-5-sayli-xestexana",
              # 2026-10-16: 56 filial ölçülüb, 100-dən çox yeni məhsul verənlər əlavə olunub (15971 -> 16946)
              "bravo-hypermarket-20-yanvar", "bravo-supermarket-bakixanov", "bravo-supermarket-babek-pr-ti-2004",
              "bravo-superstore-genclik-mall", "bravo-supermarket-masazr"],
    # Neptun və Tamstore qiymətləri filiallarda eynidir (sınaq: 100% uyğun); filiallar yalnız çeşidi artırır
    "Neptun": ["neptun-supermarket-narimanovv", "neptun-supermarket-28", "neptun-supermarket-ag-sheher",
               "neptun-8-mkr", "neptun-supermarket-3-mkr",
               # 2026-10-16: 12 filial ölçülüb (10853 -> 11609)
               "market11",   # market11 = Neptun Tbilisi prospekti
               "neptun-supermarket-xirdalan", "neptun-supermarket-xalqlar"],
    "Tamstore": ["tamstore-narimanov-1", "tamstore-genclik", "tamstore-yeni-yasamal", "tamstore-papanin",
                 "tamstore-olimpik-star", "tamstore-bineqedi",
                 # 2026-10-16: 30 filial ölçülüb (8333 -> 9849)
                 "tamstore-xetai", "tamstore-sumqayit", "tamstore-masazir", "tamstore-novxani",
                 "tamstore-superstore-khirdalan", "tamstore-badamdar", "tamstore-bayil"],
    # 2026-10-16 sınağı (filialın verdiyi yeni məhsul sayı ilə sıralanıb; ~100-dən az yeni verən filiallar götürülməyib).
    # Araz: 20 Yanvar tək 6554 -> 8 filial 10599; qiymətlər filiallarda 94-99.9% eyni.
    "Araz": ["araz-supermarket-20-yanvarr", "araz-novxani-superstore-f", "araz-supermarket-sumgait-9-microdistrict",
             "araz-supermarket-space-glass-plaza", "araz-supermarket-xirdalan", "araz-supermarket-nefilr",
             "araz-supermarket-narimanov", "araz-yasamal-3-superstore-f"],
    # OBA-nın Wolt kataloqu kiçikdir (~1000/filial); əsas qiymətlər öz saytındandır. 995 -> 1437.
    "OBA": ["oba-market-nerimanov-1", "oba-market-masazir-2", "oba-market-badamdar"],
    # Rahat: Yasamal 5515 -> 13648. Rahat Gourmet filialları başqa çeşid saxlayır (supermarketlə ~120 ortaq məhsul).
    # "Ingilab" filialı ~6% ucuzdur: Azadlıq da əlavə olunub ki, median bir filiala bağlı qalmasın.
    "Rahat": ["rahat-supermarket-yasamal", "rahat-supermarket-ingilab", "rahat-supermarket-azadlig",
              "rahat-gourmet-buzovna", "rahat-gourmet-mardakan", "rahat-gourmet-nasimi"],
    # SPAR: Axundov 4175 -> 3 filial 7802; qiymətlər 98% eyni.
    "SPAR": ["spar-axundov", "araz-spar-1-3mkr", "araz-supermarket-hacibeyli"],
}

def wolt_slugs(store):
    env = os.environ.get("WOLT_SLUG_" + store.upper(), "")
    extra = [x.strip() for x in env.split(",") if x.strip()]
    return extra + WOLT_SLUGS.get(store, [])

JUICE_WORDS = ["şirəsi","suyu","nektarı","mors","şərbəti","kompot","içkisi","sandora","cappy","pfanner","tropicana","fruktoviy","fruktovy","zolotoy sad"]
# su: "qazlı/mineral" -> qazli_su, qalanı -> su
_WATER = re.compile(_f(r"(?<!\w)su mineral|(?<!\w)(mineral|minerallı|içməli|mənbə|bulaq|kaynak|mədən|maden|qazlı|qazsız|təbii) su(yu)?(?!\w)|(?<!\w)su(?!\w).*(?<!\w)(qazlı|qazsız)|"
                       r"(?<!\w)su (\d|pet|şüşə)|sirab|bonaqua|borjomi|narzan|essentuki|yessentuki|dübrar|kəhriz|sarıkız|istisu|kızılay"))
_NOT_WATER = re.compile(_f(r"limonad|içki|(?<!\w)çay|misel|micel|mitsel|(?<!plastik )(?<!şüşə )qab(?!\w)|qabı|oyunca|tapança|filtr|pompa|vedrə|bakal|gödəkçə|yumşal|yumuşal|(?<!\w)gel(?!\w)|sabun|tonik|pəri|şampun|balzam|krem|losyon|termal|sprey|maska|kondisioner|şirə"))
_FIZZ = re.compile(_f(r"(?<!\w)(qazlı|mineral|minerallı|mədən|maden)|borjomi|narzan|essentuki|istisu|sarıkız|kızılay"))
_NOT_JUICE = re.compile(_f(r"çamaşır|paltar suyu|tualet suyu|gül suyu|ağız suyu|şüşə suyu|suyunda"))

def clean_price(raw):
    if raw is None: return None
    s = re.sub(r"[^\d,.]", "", str(raw)).replace(",",".")
    m = re.search(r"\d+\.?\d*", s)
    if not m: return None
    v = float(m.group())
    return round(v, 2) if 0.05 < v < 9999 else None

_JUICE = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(_f(w)) for w in JUICE_WORDS) + r")(?![kdh])")   # "Morskoy", "Şüyüdlü", "Morshynska" deyil
def has_juice(name):
    n = _f(name)
    return bool(_JUICE.search(n)) and not re.search(r"dondurulmus|donmus", n)

def _kw_re(words):
    # söz əvvəlində uyğunluq: "nar" -> "Nar", amma "Qarnar"/"Narzan" yox
    # qısa açar sözlər (nar, bal, su, un) tam söz kimi axtarılır
    # sonu q/k olan söz şəkilçi ilə ğ/y olur: "sıyıq" -> "sıyığı", "çörək" -> "çörəyi"
    # uzun açar söz əvvəl: "pambıqlı çubuq" "pambıq"-dan, "uşaq sıyığı" "uşaq"-dan əvvəl yoxlanılsın
    # qısa açar söz defisdən sonra da axtarılmır: "Rexona Men-titan-un-lime" -> "un" deyil
    stem = lambda w: re.sub(r"(?<=\w\w\w)q$", "[qg]", re.sub(r"(?<=\w\w\w)k$", "[ky]", re.escape(w)))
    parts = [("(?<!-)" if len(w.strip()) <= 3 else "") + stem(_f(w)) + (r"(?!\w)" if not w.endswith(" ") and (len(w) <= 3 or _f(w) in ("nar", "bal", "duz", "serf", "masa", "fanta", "pepsi", "dove", "hipp", "fruto", "bella", "buket", "arko", "sour", "ozmo", "lays", "hell", "iris", "pods", "hindi", "cola")) else "")
             for w in sorted(words, key=lambda w: -len(w.strip()))]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + ")")

# Ad üzrə zəif sübut: mağazanın dəqiq kateqoriyasını eyni qrup daxilində dəyişmir.
# _BRAND: bir neçə növ məhsulu olan brendlər ("Fairy" həm qabyuyan, həm səth təmizləyicisi; "Arko" həm təraş, həm krem)
#         və tez-tez dad/tərkib kimi işlənən sözlər ("kakao", "ləpə", "puf"): adda daha aydın növ sözü axtarılır
# _AMBIG: çoxmənalı sözlər ("baton" çörək/şokolad, "paket") — ümumi kateqoriyanı başqa qrupa da aparmır
_BRAND = {_f(w) for w in """fairy bingo vanish bella garnier gillette arko nivea dove kabrita agusha nutella kitkat snickers
twix bounty fruto konfirom biskolata biscolata roshen ülker kinder ozmo lipton tamashaee rosko nesquik maska ağardıcı sirab badamlı bonaqua dübrar sarıkız
kakao otrubi ləpə puf marshmallow""".split()} | {"mister tum", "old spice", "royal canin"}
_AMBIG = {_f(w) for w in """baton plitka choco kakoslu sour candy mətbəx paket plastik qab şüşə soda içki icki qazlı gündəlik avtomat
kondisioner pudinq biskvit qazsız moxito pizza kabab sprey geli bezi tuman junior baby çubuq sürpriz surprise desert sticks uşaq""".split()} | {"qazli icki", "quru yem", "nem yem", "suse qab", "~"}
# _kw_re-dəki q/k -> ğ/y kökü ilə tapılan forma da zəifdir: "Pudinq" -> "puding", "çubuğu" -> "cubug"
_BRAND |= {w[:-1] + {"q": "g", "k": "y"}[w[-1]] for w in _BRAND if len(w) > 3 and w[-1] in "qk"}
_AMBIG |= {w[:-1] + {"q": "g", "k": "y"}[w[-1]] for w in _AMBIG if len(w) > 3 and w[-1] in "qk"}
_FLAVOR_KW = {"sokolad", "karamel", "kakao"}   # dad sözü: eyni qrupun dəqiq kateqoriyasını dəyişmir ("Dondurma > Karamel", "Krem pasta > Şokolad")
_WEAK_KW = _BRAND | _AMBIG

_CAT_RE = {
    cid: (_kw_re(info["kw"]), _kw_re(info["excl"]) if info.get("excl") else None)
    for cid, info in CATEGORIES.items() if info["kw"]
}

_ADJ = re.compile(r"l[iuea]|s[iu]z")   # açar sözdən sonra "-lı/-lu/-la", "-sız": "limonlu", "şəkərsiz" -> sifət, məhsulun özü deyil
# açar sözdən sonra dad təsviri: "Kabab ilə suxari", "Brauni içlikli şokolad" -> məhsul başqadır
_FLAVOR_NEXT = re.compile(_f(r"\s+(dadlı|ətirli|aromalı|içlikli|dolğulu|ilə|qatqılı|sousunda|sousda|kremli|ləzzətli|əlavəli|kaplamalı|örtüklü|qlazurlu|flavou?red)(?!\w)|\s+ekstrakt|\s+\w+[ıiuü]\s+ilə(?!\w)|\s+(və|&)\s+\w+l[ıiuü](?!\w)|\s+yağlı(?!\w)"))
# təbii məhsul kateqoriyaları: "dadlı/aromalı/konserv" olanlar bura aid deyil
_MEAT = {"toyuq","hindi","dana_ati","qoyun_ati","baliq"}
_STRICT = {c for g in GROUPS if g["id"] in ("meyve","sebze") for c in g["cats"]} | _MEAT
_STRICT_EXCL = _kw_re(["şirə","suyu","sous","pasta","konserv","turşu","mürəbbə","cem","kompot","çip",
                       "dadlı","aromalı","ətirli","ləzzətli","ədviyyat","nişasta","qurusu","kürü","duzu","povidla","tablet","cleaner",
                       "pürə","yoqurt","yogurt","mirinda","spr","qurudulmuş","pastila","gel","krem"])
_FRUIT = {c for g in GROUPS if g["id"] == "meyve" for c in g["cats"]}
_SIZE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?\s*(?:ml|l|lt|litr|q|qr|gr|g|kq|kg|sm|mm|m)(?!\w)")
_DRINK = re.compile(r"(?<!\w)su(?!\w)|moxito|mohito|mojito|qazli|qazoz|gazoz|(?<!\w)piv|kokteyl|icki|soda|limonad|(?<!\w)tea(?!\w)|(?<!\w)cay|krem|sabun|gel(?!\w)|sampun|teravet")
_PET = _kw_re(["yem","pişik","itlər","bulyon","əriştə","kub"])
_MEAT_PROC = _kw_re(["burger","naqqet","naget","nugget","naggets","şnitzel","snitzel","gyoza","pelmen","kotlet","küftə"])   # "Toyuq Burger" xam ət deyil
_LIQUID = re.compile(r"\d\s*(?:ml|l|lt|litr)(?!\w)")
_FOR = re.compile(r"\s+ucun(?!\w)")   # "Balıq üçün ədviyyat", "Qanad üçün marinad": ət/meyvə-tərəvəz təyinatdır
# açar sözdən sonra bu sözlər gəlirsə söz yalnız daddır ("Pendir ilə kraker"), mağaza rəfi üstündür
_FLAV_STRONG = re.compile(_f(r"\s+(dadlı|ətirli|aromalı|içlikli|dolğulu|ilə|qatqılı|sousunda|sousda|ləzzətli|əlavəli|flavou?red)(?!\w)"))

_EN = {"dish", "fish", "wash", "brush", "shine", "shar", "irish"}   # transliterasiya edilməyən sözlər: "dish" -> "dis" = "diş" olmasın

def assign_cat(name):
    return _name_cat(name)[0]

def _adj(n, m, hy=False):
    """Uyğunluq sifətdir: açar sözdən sonra "-lı/-lu/-la", "-sız" ("Limonlu", "Şəkərsiz"), amma "Xardalı" deyil.
    hy: meyvə/ət sözü defisli sifətin hissəsidir ("Banan-Armudlu sıyıq")."""
    rest = "" if m.group().endswith(" ") else re.match(r"\w*", n[m.end():]).group()
    w = re.match(r"\w+(?:-\w+)*", n[m.start():]).group().split("-")
    return bool(rest and _ADJ.fullmatch(rest)) or (hy and len(w) > 1 and bool(re.search(r"\w\w(l[iu]|s[iu]z)$", w[-1])))

_KQ = re.compile(r"(?<![a-z])k[qg](?!\w)")

_DIAW = re.compile("[əşçğöü]")
_MASA, _SAC = re.compile(r"(?<!\w)masa(?!\w)"), re.compile(r"(?<!\w)sac(?!\w)")

def _norm(name):
    """_f + sinonim düzəlişi: diakritikasız eyni yazılan sözlər ("Maşa" ≠ "masa", diakritikalı adda "Sac lavaşı" ≠ "saç")."""
    n, low = _f(name), _low(name)
    if "maşa" in low and not _MASA.search(low): n = _MASA.sub("masha", n)
    if _SAC.search(low) and "saç" not in low and _DIAW.search(low): n = _SAC.sub("sac_", n)
    if "həll" in low: n = re.sub(r"(?<!\w)hell(?!\w)", "hall", n)   # "Həll olunan" ≠ "Hell"
    return n

def _name_cat(name, only=None):
    """(alt növ, uyğun gələn açar söz). only: yalnız bu alt növlər arasında axtarılır."""
    n, up = _norm(name), name.isupper()
    r = _name_cat_n(n, up, only)
    if r[0] == "diger":   # OBA/Araz transliterasiyası: "Shampun", "Qarabashaq", "Vermishel", "Bishirme", "Choreyi"
        n2 = " ".join(w if w in _EN else _k(w) for w in n.split(" "))
        r2 = _name_cat_n(n2, up, only) if n2 != n else r
        if r2[1] != "~": r = r2   # zəif təxmin ("Kiwi" -> "kivi" + 1l) götürülmür
    if r[0] == "sokolad" and _KQ.search(n): r = ("konfet", r[1])   # çəki ilə satılan şokolad konfetdir ("Şokolad Karakum kq")
    return r

# uşaq sıyığı: körpə brendi, yaş ("6 ay", "6+", "1-ci") və ya Nestle (Bistrov böyüklər üçündür), "Şaqayka"
_PORRIDGE = re.compile(r"(?<!\w)(siyi[qgy]|kasha|kasa(?!\w))")
_BABY = re.compile(r"saqayka|shaqayka|kabrita|gerber|virastu|(?<!\w)hipp(?!\w)|(?<!\w)beb[ei](?!\w)|fruto|nyanya|nanny|fleur alpine|gipopo|agusha|agusa|aqusa|"
                   r"(?<!\w)(usaq|korpe)|\d\s*\+(?!\d)|\d\s*-?\s*(ay|m)(?!\w)|\d\s*aydan|hipoal|1-(ci|ya)(?!\w)")

def _ncat(name, only):
    c, k = _name_cat(name, only)
    return c, k.lstrip("@")

def _name_cat_n(n, up, only=None):
    if not only or "usaq_qida" in only:
        if _PORRIDGE.search(n) and (_BABY.search(n) or ("nestle" in n and "bistr" not in n)): return "usaq_qida", "siyiq"
    fb = None
    sz = _SIZE.search(n)
    tail = sz.start() if sz and up and len(n[:sz.start()].split()) >= 2 else len(n)   # "MƏHSUL 200 ML DAD" (Bazarstore)
    if only is None and _WATER.search(n) and not _NOT_WATER.search(n):
        return ("qazli_su" if _FIZZ.search(n) and "qazsiz" not in n else "su"), "su"
    if only is None and has_juice(n) and not _NOT_JUICE.search(n) and not re.search(r"enerji|energy|(?<!\w)cay(?!\w)|qehve|kofe", n):
        return "sire", ("icki" if "icki" in n else "sire")
    for cid, (kw, ex) in _CAT_RE.items():
        if only and cid not in only: continue
        if ex and ex.search(n):
            continue
        if cid in ("tum", "qoz", "cips") and _LIQUID.search(n):
            continue   # "Reyhan Tumu 330ml" içkidir
        if cid in _STRICT and (_STRICT_EXCL.search(n) or _LIQUID.search(n)):
            if cid in _FRUIT and _LIQUID.search(n) and kw.search(n) and not _DRINK.search(n):
                fb = fb or ("sire", "~")   # "Rich Albalı 1l" — şirədir
            continue
        for m in kw.finditer(n):
            if _adj(n, m, cid in _STRICT):
                continue   # "Limonlu ..." — eyni addakı növbəti uyğunluğa bax
            if m.start() > tail:   # ölçüdən sonra: "... 200 ML ŞOKOLAD" — dad/növ təsviri
                fb = fb or (cid, "~")
                break
            if cid in _STRICT:   # real məhsulun adı açar sözlə başlayır: "Yerli Alma", "Limon kq"
                pos = len(re.findall(r"[\w-]+", n[:m.start()]))
                if pos > ((4 if cid == "baliq" else 3) if cid in _MEAT else 1) or (cid in _MEAT and _PET.search(n)):
                    break
                if cid in _MEAT and _MEAT_PROC.search(n):
                    fb = fb or (cid, "~")   # zəif təxmin: mağaza kateqoriyası (dondurulmuş, konserv) üstündür
                    break
            we = m.start() + len(re.match(r"\w+", n[m.start():]).group())
            if _FLAVOR_NEXT.match(n, we) or (cid in _STRICT and _FOR.match(n, we)):
                # başqa növ tapılmasa: "Kurabiye dadlı"; "@" = yalnız dad/təyinat sözüdür ("Pendir ilə", "Balıq üçün"), mağaza rəfi üstündür
                fl = _FLAV_STRONG.match(n, we) or (cid in _STRICT and (_FOR.match(n, we) or _FLAVOR_NEXT.match(n, we)))
                fb = fb or (cid, ("@" if fl else "") + m.group().strip())
                continue
            kws = [x.group().strip() for x in kw.finditer(n, m.start()) if x.start() <= tail and not _adj(n, x)]
            k = next((x for x in kws if x not in _WEAK_KW), kws[0])
            if k not in _WEAK_KW: return cid, k
            fb = fb or (cid, k)   # brend/çoxmənalı söz ("Fairy", "baton"): daha aydın növ sözü axtarılır
            break
    return fb or ("diger", "")

# Mağazanın öz kateqoriya adı (Wolt/Araz/OBA) -> bizim alt növ. Yol "Üst > Alt > Yarpaq" seqmentlərə bölünür və
# ƏN DƏRİN məlumatlı seqmentdən yuxarıya doğru yoxlanılır. "X və Y, Z" seqmenti hissələrə bölünür; hər hissənin ilk uyğun
# qaydası "alternativ" sayılır ("Çay və Kofe" -> çay/qəhvə): məhsul adı onlardan birini göstərirsə ad seçilir.
# SIRA: emal olunmuş məhsul (çips, turşu, konserv, sous, şirə) xammaldan (kartof, xiyar, balıq) ƏVVƏL — "Kartof Çipsi" çipsdir.
# (?<!\w) = söz əvvəli: "kağız" içində "ağız", "daraq" içində "araq", "turşular" içində "sular" tapılmasın.
_PATH_SPEC = [
    ("siqaret", r"tütün|siqaret|alışqan|terea|ploom|heets|qızdırılan"),
    ("qabyuyan", r"qabyuma|qab yuma|qoruyucu duz|maşın duzu"), ("mesis", r"(?<!\w)qabı(?!\w)"),   # "Qoruyucu duz", "Duz yağ qabı" qida deyil
    ("konfet", r"ağız təravət|saqqız|uşaq şirniyyat|sürpriz"),
    # şəxsi baxım (qida sözləri ilə toqquşmasın: "Saç jelesi", "Uşaq şampunu")
    ("usaq_baxim", r"uşaq.{0,12}(bez|şampun|yağ|sabun|duş|baxım|gigiyen|ləvazimat|krem|salfet)|(şampun|sabun|krem|yağ)\w* uşaq|körpə bez"),
    ("usaq_qida", r"(uşaq|körpə) (qida|yemək|süd|püre|sıyı[qğ])"),
    ("sac_boya", r"saç boya"), ("sac_baximi", r"(?<!\w)saç(?! lavaş| çörə)|şampun|balzam"), ("dis_baximi", r"(?<!\w)(diş|ağız)(?![kp])"),
    ("deo", r"dezodor|dezodar|deodor|tər əleyhinə"), ("tras", r"təraş"),
    # içkilər
    ("kola", r"spirtsiz piv|alkoqolsuz piv"),
    ("pive", r"(?<!\w)piv"), ("araq", r"(?<!\w)araq|vodka"), ("viski", r"viski|burbon"), ("serab", r"şərab|şampan|vermut"),
    ("likor", r"konyak|brendi|likör|tekila|rakı|\brom\b|\bcin\b|(spirtli|alkoqollu) kokteyl"),
    ("energetik", r"enerji|energetik|red bull|sport içki"),
    ("sire", r"şirə|nektar|kompot|meyvə su(?!d)"), ("soyuq_cay", r"soyuq çay|ice.?tea|fuse.?tea"),
    ("qazli_su", r"qazlı su|mineral"), ("su", r"qazsız su(?!\w)|içməli su(?!\w)|sağlam su(?!\w)|xxl su(?!\w)|^su$|(?<!\w)sular|sadə su(?!\w)"),
    ("limonad", r"limonad"), ("kola", r"cola|soda|qazlı .*içki|^kola|qazlı .*kokteyl"),
    ("cay", r"(?<!\w)çay|dəmləmə"), ("qehve", r"qəhvə|kofe|kakao|süd tozu|kapsul|isti şokolad"),
    # dondurulmuş (məhsul növünə görə)
    ("dondurulmus", r"dondurulmuş (meyvə|tərəvəz|kartof|börək|mantı|milföy|yarımfabrikat|xəmir|qida)|donmuş (meyvə|tərəvəz|qida)|yarımfabrikat"),
    ("dondurma", r"dondurma|donmuş desert"),
    # emal olunmuş: sous, turşu, konserv, çips, tum, şirniyyat yağları
    ("mayonez", r"mayonez"), ("ketcup", r"ketçup|ketchup|(?<!\w)sous(?!lu)"), ("xardal", r"xardal|xrən|acika"), ("sirke", r"sirkə"),
    ("zeytun", r"zeytun(?! yağ)"), ("tursu", r"turşu"), ("pomidor_pasta", r"pomidor pasta|tomat pasta|^pastalar$"), ("konserv", r"konserv"),
    ("cips", r"çips|chips|ekstruder|xıtır|suxari|popkorn"), ("tum", r"^tum|tumlar|(?<!\w)tumu|ləpə(?!li)|araxis(?!li)|püstə(?!li)"),
    ("krem_pasta", r"krem şokolad|əzmə|krem pasta|şokolad yağ|şanti"),
    ("susi", r"(?<!\w)(suşi|sushi)|asiya mətbəxi"), ("deniz", r"dəniz məhsul|krevet|midiya|kalamar|kürü"), ("baliq", r"balıq"),
    ("yumurta", r"yumurta"), ("toyuq", r"toyu[qğ]|cücə|broyler"), ("hindi", r"hindi(?!stan)|hinduşka"), ("qoyun_ati", r"qoyun|quzu"), ("dana_ati", r"(?<!\w)dana|mal əti|qırmızı ət"),
    ("hise", r"hisə verilmiş"), ("sosis", r"sosis|sardelka"), ("kolbasa", r"kolbasa|delikates|qastronom|emal olunmuş ət|salam"),
    # süd məhsulları
    ("pendir", r"pendir|pendır|labne"), ("xama", r"xama|smetana"), ("qaymaq", r"qaymaq"),
    ("kesmik", r"kəsmik|(?<!\w)şor(?!\w)"), ("sirok", r"sırok"), ("sud", r"süd kokteyl|südlü kokteyl"), ("yoqurt", r"yoqurt|yogurt|kokteyl"),
    ("kefir", r"kefir|ayran|dovğa"), ("qatiq", r"qatı[qğ]"), ("zeytun_yagi", r"zeytun yağ"),
    ("bitki_yagi", r"günəbaxan|qarğıdalı yağ|duru yağ|^yağlar$|ayçiçəyi|duru və əridilmiş yağ"),
    ("kere_yagi", r"kərə yağ|kərə və|spred|marqarin|margarin|bitki tərkibli yağ|melanj|əridilmiş yağ"),
    ("sud", r"pasterizə|uzun ?ömürlü|qatılaşdırılmış süd|südlər|^süd$|(?<!\w)süd$|südü$|aromalı süd"),
    # şirniyyat
    ("murebbe", r"mürəbbə|(?<!\w)cem|povidla"), ("bal", r"^bal$|^bal,|(?<!\w)bal və"),
    ("halva", r"halva|lokum|kozinak"), ("pecenye", r"peçenye|biskvit|kraker|kreker|bisküvit|kurabiy|pryanik"), ("vafli", r"vafli|gofret"),
    ("keks", r"keks|kruass?an|rulet|(?<!\w)kek(?!\w)"), ("tort", r"tort|pirojna|paxlava|şərbətli"), ("sokolad", r"şokolad|shokolad"),
    ("konfet", r"konfet|jele|draje|jelibon|şəkərləmə|marmelad|karamel|fərəhləndirici|meyvəli bar|nanəli"),
    # qəlyanaltı, bakaliya
    ("qoz", r"(?<!\w)qoz|fındıq|fıstıq|quru meyvə"),
    ("hazir_yemek", r"hazır yemək|hazır qida|şorba|hazır sup|tez hazırlanan|ketrinq"),
    ("makaron", r"makaron|spagetti|vermişel|vermeşel|vermesel|vermeşil"), ("eriste", r"əriştə"), ("duyu", r"düyü"), ("merci", r"mərci"), ("noxud", r"noxud"),
    ("fasulya", r"lobya|fasulya"), ("qarabashaq", r"qarabaşaq"), ("yulaf", r"yulaf"), ("bulgur", r"bulğur|manna"),
    ("seher", r"müsli|sıyı[qğ]|qranola|taxıl məhsul"), ("bakliyyat", r"dənli|paxlalı|bakliy?yat|yarma"),
    ("un", r"buğda un|ali növ|^un$|^un və|^un məhsul|un və un|ağ un|quru un"), ("corek", r"çörə[ky]|lavaş|mayalı|bişinti|təndir|(?<!\w)kətə"),
    ("bulyon", r"bulyon"), ("duz", r"^duz$|duz və|(?<!\w)duzu?$"), ("sekerqum", r"şəkər|qənd|noğul"), ("istiot", r"ədviyyat|nişasta"),
    # meyvə / tərəvəz (xammal: emal olunmuşlardan sonra)
    ("goyerti", r"göyərti"), ("gobelek", r"göbələk"), ("balqabaq", r"balqabaq|kabak"), ("cuqundur", r"çuğundur"),
    ("kelem", r"kələm"), ("sarimsaq", r"sarımsaq"), ("kartof", r"^kartof"), ("soyan", r"^soğan"), ("badimcan", r"badımcan"),
    ("biber", r"^bibər"), ("xiyar", r"^xi?yar|^xıyar"), ("pomidor", r"^pomidor"), ("yerkoyu", r"^kök$|yerkökü"),
    ("ekzotik", r"ananas|ekzotik|kokos|avokado|avakado"), ("mandarin", r"mandarin|qreypfrut"), ("portaqal", r"^portağal"),
    ("limon", r"^limon"), ("alma", r"^alma"), ("armud", r"^armud"), ("banan", r"^banan"), ("kivi", r"^kivi"), ("nar", r"^nar$"),
    ("uzum", r"^üzüm"), ("saftal", r"^şaftalı|^ərik|^gavalı"), ("gilas", r"^gilas|^albalı"), ("gile", r"giləmeyvə"), ("qarpiz", r"qarpız|yemiş"),
    # gigiyena / ev / heyvan / oyuncaq
    ("qadin_gig", r"qadınlar üçün gigiyen|qadın gigiyen|qadın bez|qoruyucu(?! duz)|molped|tampon"),
    ("etir", r"parfüm|(?<!\w)ətir(?!li)|kaloniya|kolonya"), ("kosmetika", r"makiyaj|dırnaq|manikür|kosmetik məhsul"),
    ("dereterlik", r"dəftərxana|məktəb|ofis|qələm|karandaş|dəftər"),
    ("mesis", r"bişirmə (avadanlıq|qab)"), ("bisirme", r"bişirmə|folqa|streç"),
    ("kagiz", r"kağız məhsul|tualet kağız|salfet|dəsmal|(?<!\w)kağız"),
    ("qabyuyan", r"qabyuyan|qab yuyan"), ("yuyucu", r"yuyucu|paltar|çamaşır|yumşaldıcı|ağardıcı|deterjan"),
    ("zibil", r"zibil"),
    ("temizlik", r"təmizlik vasitə|təmizləyici|döşəmə|şüşə təmiz|tualet təmiz|toz təmiz|xalça|boru|aerozol|ümumi təmizlik|həşərat|hava təravət|təmizliy|təmizlik"),
    ("mesis", r"xırdavat|məişət|mətbəx|ləvazimat|süngər|bezlər|əlcək|birdəfə|saxlama"),
    ("mesis", r"ayaqqabı (təmiz|baxım|parıl|krem)"), ("ayaqqabi", r"başmaq|corab|ayaqqabı"),
    ("beden_baximi", r"prezervativ|sabun|(?<!\w)duş|bədən|(?<!\w)dəri|\büz\b|üz və|krem|günəş|gigiyena məhsul|kişilər üçün gig|pambıq"),
    ("pisik_yemi", r"pişik"), ("it_yemi", r"it qida|itlər|it yem|it və"), ("heyvan_diger", r"heyvan|zoo ?shop"),
    ("oyuncaq", r"oyuncaq(?!lı)|hobbi"), ("avto", r"avto|maşın"),
    ("usaq_qida", r"(uşaq|körpə) (qida|yemək|süd|püre|sıyı[qğ])|mama|ana və"),   # sonda: "Uşaq oyuncaqları" öz növünə düşsün
]
# ümumi (üst səviyyə və ya qarışıq) qaydalar: alt növü məhsul adı dəqiqləşdirir
_PATH_GEN = [
    ("likor", r"spirtli|alkoqollu|elit içki"), ("sire", r"qazsız içki|meyvə aromalı"), ("kola", r"spirtsiz|alkoqolsuz|içki"),
    ("sud", r"süd məhsul|süd və süd|yoqurt və kəsmik|süd və emal"), ("meyve_diger", r"meyvə(?!li)"), ("sebze_diger", r"tərəvəz(?!li)"),
    ("et_diger", r"(?<!\w)ət məhsul|təzə ət|ağ ət|^ət$"),
    ("konfet", r"şirniyyat|qənnadı|(?<!\w)çəki"), ("corek", r"un məmulat|unlu|bişmə|xəmir"),
    ("qoz", r"çərəz(?!li)|atışdırmalıq"), ("cips", r"snack|snek|qəlyanaltı"), ("seher", r"səhər yemə"),
    ("cay", r"(?<!\w)çay"), ("hazir_yemek", r"hazır"), ("konserv", r"konserv"), ("dondurulmus", r"dondurulmuş|donmuş"),
    ("bitki_yagi", r"(?<!\w)yağ"), ("istiot", r"(?<!\w)duz"), ("sekerqum", r"şəkər"),
    ("saglam", r"sağlam qida|sağlam yaşam|dietik|diabetik|qlütensiz|glutensiz|protein"), ("bakliyyat", r"quru qida"),
    ("tekstil", r"tekstil"), ("geyim", r"geyim"), ("heyvan_diger", r"zoo"), ("usaq_qida", r"uşaq|körpə"),
    ("mesis", r"manqal|dekorasiya|elektronika|səyahət|mebel|işıqlandırma|dəmirçi|take away|istirahət|bio məhsul|hobbi|(?<!\w)bağ(?!\w)|bağça|bəzək"),
    ("sous_diger", r"dadlandırıcı"), ("beden_baximi", r"kosmetik|təmizlik və|şəxsi baxım|hamam|qulluq vasitə|baxım"), ("mesis", r"ev və bağ|ev əşya"),
]
_PATH_SPEC = [(c, re.compile(_f(r), re.I)) for c, r in _PATH_SPEC]
_PATH_GEN = [(c, re.compile(_f(r), re.I)) for c, r in _PATH_GEN]
_PATH_SKIP = re.compile(_f(r"endirim|kampaniya|aksiya|yeni məhsul|hamısına bax|wolta özəl|^(other|digər|diqər|digərləri?)$"))
_PATH_OTHER = re.compile(_f(r"(?<!\w)(digər|diqər|other|qarışıq|müxtəlif)"))   # "Digər souslar" -> ümumi
_CANNED = re.compile(_f(r"konserv|turşu"))
CAT2GROUP = {c: g["id"] for g in GROUPS for c in g["cats"]}
_PRODUCE = {c for g in GROUPS if g["id"] in ("meyve","sebze") for c in g["cats"]}
_PROCESSED = {"konserv": _STRICT | {"noxud","fasulya","deniz","zeytun_yagi","bitki_yagi"}, "dondurulmus": _PRODUCE | {"noxud","fasulya"},
              "kolbasa": _MEAT, "sosis": _MEAT, "hise": _MEAT}

_COORD = re.compile(r"\s+ve\s+|[,/&+]")

def _first(rules, t):
    return next((cid for cid, rx in rules if rx.search(t)), None)

_GEN_ORDER = {}
for _i, (_cid, _) in enumerate(_PATH_GEN): _GEN_ORDER.setdefault(_cid, _i)

def _seg_hits(sg):
    """Seqment "X və Y, Z" hissələrə bölünür; hər hissənin ilk dəqiq qaydası alternativ olur ("Çay və Kofe" -> çay, qəhvə).
    Tək sözlü hissə qonşunun sözü ilə oxunur: "Sadə və mineral sular" -> "sadə sular", "Uşaq qidası və baxımı" -> "uşaq baxımı".
    Nəticə: (dəqiq alt növlər, ümumi alt növlər); hər ikisi varsa seqment qarışıqdır (ümumi sayılır)."""
    parts = [p.strip() for p in _COORD.split(sg) if p.strip()]
    spec, gen = [], []
    for i, p in enumerate(parts):
        c, g = _first(_PATH_SPEC, p), _first(_PATH_GEN, p)
        if not c and len(parts) > 1:
            own = {_first(_PATH_SPEC, parts[-1]), _first(_PATH_SPEC, parts[0])}
            for x in ([p + " " + parts[-1].split()[-1]] if i < len(parts) - 1 else []) + ([parts[0].split()[0] + " " + p] if i > 0 else []):
                c = _first(_PATH_SPEC, x)
                if c and c not in own: break
                c = None
        if c: spec.append(c)
        elif g: gen.append(g)
    # əsas növ: ilk hissənin növü ("Uşaq qidası və baxımı" -> uşaq qidası), zəif ümumi növdürsə ("Duş otağı və ...") növbəti
    spec = list(dict.fromkeys(sorted(spec, key=lambda c: c in ("beden_baximi", "mesis", "avto"))))
    return spec, sorted(set(gen), key=_GEN_ORDER.get)

_FROZEN = re.compile(_f(r"dondurulmuş|donmuş"))
_KIDSEG = re.compile(_f(r"(?<!\w)(uşaq|körpə)"))
def _state(pc, segs):
    """Emal halı xammaldan üstündür: "Konservlər > Tərəvəzlər" -> konserv, "Dondurulmuş > Meyvələr" -> dondurulmuş.
    Uşaq bölməsindəki baxım məhsulu uşaq baxımıdır: "Uşaq Məhsulları > Diş baxımı"."""
    if CAT2GROUP[pc] == "gigiyena" and any(_KIDSEG.search(s) for s in segs): return "usaq_baxim"
    if pc in _STRICT or pc == "et_diger":
        if any(_CANNED.search(s) for s in segs): return "konserv"
        if pc in _PRODUCE and any(_FROZEN.search(s) for s in segs): return "dondurulmus"
    return pc

@lru_cache(maxsize=4096)
def _path_info(path):
    """(alt növ, ümumi?, alternativlər) və ya (None, False, ())."""
    segs = [x.strip() for x in _f(path).split(">") if x.strip()]
    oth = bool(segs) and bool(_PATH_OTHER.match(segs[-1]))   # "Souslar > Other": rəfin qarışıq hissəsi, ad dəqiqləşdirir
    segs = [s for s in segs if not _PATH_SKIP.search(s)]
    for k in range(len(segs) - 1, -1, -1):   # ən dərin məlumatlı seqment: əvvəl dəqiq, sonra ümumi qaydalar
        spec, gen = _seg_hits(segs[k])
        if spec:
            pc = _state(spec[0], segs)
            if pc != spec[0]: return pc, oth, frozenset(spec)
            return pc, oth or bool(gen) or bool(_PATH_OTHER.search(segs[k])), frozenset(spec) | frozenset(gen)
        if gen:
            pc = _state(gen[0], segs)
            if pc != gen[0]: return pc, oth, frozenset(gen)
            # üst seqmentdə eyni qrupdan dəqiq növ varsa standart odur: "Çips, Çərəz və Qəlyanaltılar > Qəlyanaltılar" -> çips
            # ("Şokolad və Şirniyyat > Digər Şirniyyatlar" isə ümumi hissəyə aiddir: şokolad deyil)
            up = [h for h, g in (_seg_hits(u) for u in segs[:k]) if len(h) == 1 and CAT2GROUP[h[0]] == CAT2GROUP[pc] and pc not in g]
            return (up[-1][0] if up else pc), True, frozenset(gen)
    return None, False, frozenset()

def cat_from_path(path):
    """(alt növ, ümumi?) və ya (None, False)."""
    return _path_info(path)[:2]

# Mağazanın çox ümumi (üst səviyyə) kateqoriyaları, məs. OBA: "Şirniyyat", "Spirtli içkilər" — alt növü ad üzrə təyin olunur
_COARSE = {_f(x) for x in ["Şirniyyat","Təmizlik","Spirtli içkilər","Konserva və dəniz məhsulları","Heyvan qidaları",
                           "Un məmulatları","Kosmetika","Ev əşyaları","İçkilər","Süd məhsulları","Meyvə-tərəvəz"]}
_WEAK = {"bakliyyat", "dondurulmus", "konserv", "mesis", "beden_baximi", "kosmetika", "temizlik", "hazir_yemek"}

def _has_kw(cid, n):
    """Adda bu alt növün aydın açar sözü məhsul adı kimi (sifət/brend yox) varmı."""
    if cid not in _CAT_RE: return False
    for m in _CAT_RE[cid][0].finditer(n):
        if m.group().strip() not in _WEAK_KW and not _adj(n, m): return True
    return False

def _produce_in(name):
    """Tərəvəz/meyvə yolunda: adın istənilən yerində meyvə-tərəvəz adı (sifət deyilsə)."""
    n = _f(name)
    if _STRICT_EXCL.search(n) or _LIQUID.search(n): return None
    return next((cid for cid in _PRODUCE if _has_kw(cid, n)), None)

def _grps(c):   # uşaq baxımı həm də gigiyenadır ("Körpə yağı" > Təmizlik və Kosmetika)
    return {CAT2GROUP[c], "gigiyena"} if c == "usaq_baxim" else {CAT2GROUP[c]}

_KID = re.compile(_kw_re(["uşaq","usaq","körpə","baby","bebe","kids","junior","dalin","uşastıy","ushastiy","johnson"]).pattern
                  + r"|\d\s*\+?\s*ay(?!\w)|\d\s*\+(?!\d)")   # "6+ ay", "6+" ("2+1" aksiyadır)
_NONFOOD = {"gigiyena", "ev", "heyvan", "oyuncaq", "geyim", "tutun"}
_NFC = frozenset(c for c, g in CAT2GROUP.items() if g in _NONFOOD) | {"usaq_baxim"}
# qeyri-qida rəfində adda axtarılan növlər: heyvan rəfində yalnız heyvan növləri ("Oyuncaq toyuq budu", "Heyvan çantası")
_NF_ONLY = {g: frozenset(c for c in _NFC if (CAT2GROUP[c] == "heyvan") == (g == "heyvan")) for g in _NONFOOD}
_NF_GRP = {g: frozenset(c for c in _NFC if g in _grps(c)) for g in _NONFOOD}   # əvvəl rəfin öz qrupu: "Yumşaldıcı Misellyar Suyu" > Dəri baxımı
_FOODC = frozenset(c for c, g in CAT2GROUP.items() if g not in _NONFOOD and g != "diger") - {"usaq_baxim"}
_SWC = frozenset(c for c, g in CAT2GROUP.items() if g == "sirniyyat")
_CHIPS = {_f("qarğıdalı çubuq")} | {_f(w) for w in "çips chips popkorn popcorn pretzel qrenki grenki xrusteam lays pringles cheetos doritos xlebsi xlebci xlebtsi suxari".split()}
_CEREAL = {_f(w) for w in ["lopa", "sıyıq", "müsli", "corn flakes", "səhər yeməyi", "səhər yemək"]}
_BAR = re.compile(r"(?<!\w)(bar|baton\w*)(?!\w)")
_DOUGH = {_f(w) for w in "börək borek xəngəl qutab xəmir lahmacun xacapuri manti pelmen vareniki xinkali pizza".split()}
_WEIGHT = re.compile(r"\d\s*(?:q|qr|gr|g|kq|kg)(?!\w)|(?<![a-z])k[qg](?!\w)")
_NOJUICE = {"soyuq_cay", "kola", "limonad", "energetik", "qehve"}
# ümumi "Şirniyyat" rəfində (OBA, Neptun: çörək, çərəz, süd də var) qida sözü yalnız şirniyyat əlaməti olduqda dad sayılır
_SWEET_CUE = re.compile(r"sokolad|sokalad|shok|(?<!\w)sok(?:\.|(?!\w))|choco|(?<!\w)bar(?!\w)|baton|krem|qlazur|karamel|(?<!\w)kar\.|(?<!\w)konf|desert|"
                        r"(?<!\w)pec|(?<!\w)ile(?!\w)|dadli|(?<!\w)balli|kakao|tund|formal|vafli|sweet")

_SNACK = frozenset(["cips", "tum", "qoz"])

def _kwpos(n, kw):
    i = n.find(kw)
    return len(re.findall(r"[\w-]+", n[:i])) if i >= 0 else 99

def _snack_flavor(nc, kw, n):
    """Çərəz rəfində dad sözü: ət, meyvə-tərəvəz, konserv, sous, süd/içki (həcmsiz), hazır yemək (xəmir deyilsə).
    Ədviyyat (çəki ilə ədviyyat satılır), adın əvvəlindəki pendir, çörək, makaron, şirniyyat, qeyri-qida çıxa bilər."""
    g = CAT2GROUP[nc]
    if g in ("et", "meyve", "sebze", "konserv") or (nc == "hazir_yemek" and kw not in _DOUGH): return True
    if g in ("sud", "spirtli", "iceckiler", "yag_sous") and not _LIQUID.search(n):
        return not (nc in ("istiot", "duz", "cay", "qehve") or (nc == "pendir" and _kwpos(n, kw) <= 1))
    return False

def _sweet_out(nc, kw, name, n):
    """Şirniyyat rəfindən çıxa bilən real məhsul növü: çörək, sağlam qida, tum, çips/popkorn, börək/xəngəl/qutab, içki (həcmi ilə),
    şirniyyat sözü və çəkisi olmayan qeyri-qida ("Cib salfeti"). Qalan qida sözləri dad/içlikdir: "Fındıqlı", "Süd dadlı", "Kola"."""
    g = CAT2GROUP[nc]
    if g in ("corek", "saglam") or nc == "tum" or (g in ("iceckiler", "sud") and _LIQUID.search(n)): return True
    if nc == "cips": return kw in _CHIPS
    if nc == "seher": return kw in _CEREAL and not _BAR.search(n)   # "Bistrov taxıl lopaları", amma "Granola bar" şirniyyatdır
    if nc == "usaq_qida": return kw not in _AMBIG and bool(_BABY.search(n))   # "Kabrita puding 6+ ay"
    if nc == "hazir_yemek": return kw in _DOUGH
    return nc in _NFC and not _WEIGHT.search(n) and _name_cat(name, _SWC)[0] == "diger"

def classify(name, path=""):
    """Mağazanın öz kateqoriyası (varsa) + məhsul adı. Mağaza kateqoriyası dəqiqdirsə ona üstünlük verilir;
    ümumi/"digər"/qarışıq olduqda və ya ad kateqoriyanın alternativlərindən birini göstərirsə ad üzrə nəticə götürülür."""
    nc, kw = _name_cat(name)
    if not path: return nc
    pc, gen, alts = _path_info(path)
    if pc is None or pc == "diger": return nc   # mağaza kateqoriyası məlumat vermirsə ("Sağlam qida" və s.) ada görə
    flav, kw = kw[:1] == "@", kw.lstrip("@")
    # yalnız dad/təyinat sözü ("Pendir ilə kraker", "Qanad üçün marinad"): mağaza rəfi
    if flav and nc != "diger" and CAT2GROUP[nc] not in (CAT2GROUP[pc], "sirniyyat", "gigiyena", "ev"): return pc
    coarse = _f(path).strip() in _COARSE
    gen = gen or coarse
    # "Rich Albalı 1l" kimi təxmin dəqiq mağaza kateqoriyasını, soyuq çay/kola qarışıq rəfini dəyişmir ("Bergtea Şaftalı 1l")
    if kw == "~" and (not gen or (len(alts) > 1 and alts & _NOJUICE)): nc = "diger"
    if pc in _PRODUCE and (nc == "diger" or kw in _WEAK_KW): nc = _produce_in(name) or nc   # "4 Fəsil Pomidor Çeri paket" > Tərəvəzlər
    if nc == "diger": return pc
    n, gp = _f(name), CAT2GROUP[pc]
    # qeyri-qida rəfi (gigiyena, ev, heyvan, oyuncaq) addakı qida sözünə uymur: "Rexona Men-titan-un", "Arko Krem Zeytun Yağı",
    # "Keks qəlibi", "Sprey boya qəhvəyi" — adda qeyri-qida növü axtarılır, yoxdursa mağaza kateqoriyası
    if gp in _NONFOOD and nc in _FOODC:
        nc, kw = _ncat(name, _NF_GRP[gp])
        if nc == "diger": nc, kw = _ncat(name, _NF_ONLY[gp])
        if nc == "diger" or kw in _AMBIG: return pc
    if gp == "sirniyyat" and gen and kw == "piroq": return "keks"   # şirniyyat rəfində şirin piroq
    # geniş şirniyyat rəfində ("Çəki şirniyyatları", "Şirniyyat ədədli") başqa qrupun qida sözü dad/içlikdir: "Fındıqlı şokolad", "Süd dadlı"
    if (gp == "sirniyyat" and gen and CAT2GROUP[nc] != "sirniyyat" and not _sweet_out(nc, kw, name, n)
            and (not coarse or _SWEET_CUE.search(n) or _name_cat(name, _SWC)[0] != "diger")):
        nc, kw = _ncat(name, _SWC)
        if nc == "diger": return pc
    # dondurma rəfində şirniyyat sözü növ/dad təsviridir ("Vafli stəkan", "Cookie"); şirniyyat/çörək rəfində "plombir" daddır
    if pc == "dondurma" and not gen and CAT2GROUP[nc] == "sirniyyat": return pc
    if nc == "dondurma" and gp in ("sirniyyat", "corek"):
        alt = _ncat(name, _SWC - {"dondurma"})
        if alt[0] != "diger" and alt[1] not in _WEAK_KW: nc, kw = alt   # "Rulet Darenka Plombir", "Dirol Dondurma Nanə"
    # çərəz/çips rəfində başqa qrupun sözü çox vaxt daddır ("Soğan Xama Halqaları", "Kolbasa dadlı suxari"): əvvəl adda çərəz növü axtarılır
    if pc in _SNACK and nc not in _SNACK:
        alt = _ncat(name, _SNACK)
        if alt[0] != "diger" and alt[1] not in _AMBIG: nc, kw = alt
        elif _snack_flavor(nc, kw, n): return pc
    # qida yolunda meyvə/ət sözü dad və ya içlikdir: "Tofita Çiyələk" > Şirniyyat, "Hinduşka Sendviç" > Un məmulatları
    if (nc in _PRODUCE and CAT2GROUP[pc] in ("sirniyyat", "hazir", "sud", "bakaliya", "corek")) or (CAT2GROUP[nc] == "et" and CAT2GROUP[pc] == "corek"): return pc
    # "Balıq Konservi" + "Ton balıq" -> konserv; qarışıq "Konserva və dəniz məhsulları" + "Hisə verilmiş skumbriya" -> balıq
    if (pc in _PROCESSED and nc in _PROCESSED[pc] and not (gen and any(CAT2GROUP[a] == CAT2GROUP[nc] for a in alts - {pc}))
            and not (CAT2GROUP[nc] == "yag_sous" and _LIQUID.search(n))): return pc   # "Günəbaxan yağı 1 l" konserv deyil
    if gp == "usaq" and CAT2GROUP[nc] == "gigiyena" and (pc == "usaq_baxim" or _KID.search(n)): return "usaq_baxim"   # "Uşaq şampunu"
    # uşaq rəfi özü uşaq əlamətidir: sıyıq, körpə brendi, yaş ("6 ay", "6+") olan qida uşaq qidası qalır ("Kabrita Sıyıq Yulaf 6+")
    if pc == "usaq_qida" and (_KID.search(n) or _BABY.search(n) or _PORRIDGE.search(n)) and (
            CAT2GROUP[nc] in ("sirniyyat", "bakaliya", "sud", "meyve", "sebze", "hazir") or (CAT2GROUP[nc] == "iceckiler" and nc not in ("su", "qazli_su"))): return pc
    if kw in _FLAVOR_KW and pc not in ("sokolad", "konfet") and _has_kw(pc, n): return pc   # "Milla Karamel Sırok" > Sıroklar
    if nc in alts and kw not in _AMBIG: return nc   # "Çay və Kofe" + "Qara Çay" -> çay
    if kw == "kakao" and CAT2GROUP[pc] in ("sirniyyat", "sud"): return pc   # "Eti Tutku Kakao", "Sirok Kakao" — dad sözüdür
    grp = CAT2GROUP[nc] == CAT2GROUP[pc]
    # ad yolun növünü də deyir ("Halva konfet" > Halva). Hamısını tutan yol (məişət, digər) yalnız başqa qrupa qarşı:
    # "Keramika çərəzlik" > Mətbəx, amma "Zibil torbası" > Məişət -> zibil; "Dondurulmuş toyuq" isə toyuqdur
    catch = pc == "mesis" or pc.endswith("_diger")
    if not gen and pc != "usaq_qida" and not (catch and grp) and (pc != "dondurulmus" or CAT2GROUP[nc] != "et") and _has_kw(pc, n): return pc
    if grp and CAT2GROUP[pc] != "oyuncaq" and kw not in _WEAK_KW and (kw not in _FLAVOR_KW or pc in ("sokolad", "konfet")): return nc   # eyni qrupda adın aydın növ sözü daha dəqiqdir
    same = bool(_grps(nc) & {g for c in alts | {pc} for g in _grps(c)})
    if gen or pc.endswith("_diger"):   # ümumi kateqoriya: ad dəqiqləşdirir (çoxmənalı söz başqa qrupa aparmır)
        return pc if kw in _AMBIG and not same else nc
    if pc in _WEAK: return pc if kw in _AMBIG or (kw in _BRAND and same) else nc
    return pc

# ── Ad təmizliyi və dublikatlar ──────────────────────────────────────────
_LET = re.compile(r"[A-Za-zÀ-ɏƏəЀ-ӿ]")
_WRD = re.compile(r"[A-Za-zÀ-ɏƏəЀ-ӿ]+")
_UNIT_N = re.compile(r"(?<=\d)(\s?)(Gr|Ml|Kq|Kg|Qr|Lt|L|Q|G|Cm|Sm|Mm|M|Əd|Ed|Li|Lu|Lü|Lı)\b")

def _decaps(n):
    """Tam BÖYÜK hərfli ad normal yazılır: "DR.MILK KAUNAS XAMA 20% 350 GR" -> "Dr.Milk Kaunas Xama 20% 350 gr".
    Hər söz böyük hərflə başlayır (İ/I düzgün), rəqəmdən sonrakı vahid kiçik hərflə. Qarışıq yazılmış adlara toxunulmur."""
    chk = re.sub(r"(?i)(?<=\d)\s?(?:ml|gr|g|kg|kq|l|lt|qr|q|pcs|pc|ədəd|əd|ed|cm|mm|sm|m)\b", "", n)   # OBA: "KLAR MAYE, 500 ml"
    letters = "".join(_LET.findall(chk))
    if len(letters) < 5 or letters != letters.upper(): return n
    n = _WRD.sub(lambda m: m.group()[0] + _low(m.group()[1:]), n)
    return _UNIT_N.sub(lambda m: m.group(1) + m.group(2).lower(), n)

def clean_name(n):
    """Artıq boşluq, vergül/nöqtədən əvvəlki boşluq və sonda qalan vergül/defis atılır, TAM BÖYÜK hərfli ad normal yazılır:
    "FAIRY LIMON MAYE QABYUYAN , 750 ml" -> "Fairy Limon Maye Qabyuyan, 750 ml"."""
    n = _decaps(re.sub(r"\s+", " ", str(n)).strip())
    n = re.sub(r"\s+\d{12,14}$", "", n)   # sonda qalan ştrix-kod (EAN) ada aid deyil
    n = re.sub(r"\s+([,.;:!?)%])", r"\1", n)
    n = re.sub(r"\(\s+", "(", n)
    return re.sub(r"[\s,;:\-]+$", "", n) or n

def name_key(n):
    """Dublikat açarı: diakritiksiz, yalnız hərf/rəqəm; rəqəmlər arasındakı nöqtə qalır (1.5 L ≠ 15 L).
    "Vernel 1.44 L Lale" = "Vernel 1,44 L Lalə", "Dtj 750ml" = "Dtj  750 ml"."""
    k = re.sub(r"(\d)[.,](?=\d)", r"\1.", _f(n))
    return re.sub(r"\.(?!\d)|(?<!\d)\.|[^\w.]|_", "", k)

def _pref(it):
    """Dublikatlardan hansı qalır: yoxlanmış (arxiv olmayan), mağazanın öz qiyməti, sonra ucuz olan (sayt da kartda ucuzu göstərir)."""
    p = it.get("price", it.get("wolt_price"))
    return (bool(it.get("stale")), "price" not in it, p if isinstance(p, (int, float)) else 1e9)

def dedupe(items):
    """Eyni mağaza + kateqoriyada yalnız yazılışı fərqli təkrarlar bir qeyd olur (ilk rastlaşdığı yerdə)."""
    best = {}
    for it in items:
        k = name_key(it["name"]) or it["name"]
        if k not in best or _pref(it) < _pref(best[k]): best[k] = it
    return list(best.values())

# ── "Digər"-ə düşən məhsullar: ad yalnız brenddir ("Rafaello 70 Q", "Kent Nanotek") və ya mağaza kateqoriya verməyib ──
# Qayda yalnız "diger"-dəki məhsullara tətbiq olunur (qalan təsnifata təsir etmir). Sıra: qəti açar sözlər (qeyri-qida),
# brend səsverməsi (eyni brendin başqa məhsulları hansı kateqoriyadadır), yumşaq açar sözlər, məhsul sözü səsverməsi.
_OTHER_HARD = [(re.compile(r), c) for r, c in (   # c=None: "Digər"də qalsın (səsvermə səhv yerə aparırdı)
    (r"buz kub", None),
    (r"\bqapaq\b|sixaca|filt(?:i)?r|katric|komur|skewer|\bsis\b|lanc ?boks|caydan|pencere band|izolent|uzadici|ayirici|borulu|termos"
     r"|\bkamp\b|cadir|yuxu tulum|mecmeyi|tepsi|\bkasa\b", "mesis"),
    (r"dixlofos|tuz ruhu|tibtrap|sican|tarakan", "temizlik"),
    (r"bloknot|pozan\b|\bdefter", "dereterlik"),
    (r"\bit kendir|\btasma\b|gezdirme qayis", "heyvan_diger"),
    (r"skuter|futbol|voleybol|\btopu\b|\bparty\b", "oyuncaq"),
    (r"\bvuse\b|\btustu\b", "siqaret"),
)]
_OTHER_SOFT = [(re.compile(r), c) for r, c in (
    (r"(?:ciy|cig) kofte|yarpaq sarma|blincik|pelmen|dusbere|xinkal|kartof pure", "hazir_yemek"),
    (r"\bvanil", "istiot"),
    (r"dadlandirici|stevia", "sekerqum"),
    (r"seledoc|siyenk|matias|skumbri", "baliq"),
    (r"midye|krab|krevet|krivet|kalamar", "deniz"),
    (r"kinoa|quinoa", "bakliyyat"),
    (r"raf+a[e]?l+o", "konfet"),
    (r"m&ms|milky way|\btwi?x\b|\btwlx\b", "sokolad"),
    (r"(?:cocktail|koktail|kokteyl).*\d\s*ml\b", "likor"),
    (r"oxidant|oksidant", "sac_boya"),
)]
_OTHER_SKIP = {"x", "st", "s", "u", "k", "m", "h", "p", "b", "l", "su", "km", "sh", "yeni", "new", "aksiya"}
_OTHER_STOP = {"dadi", "dadli", "ile", "sade", "qutu", "banka", "suse", "kicik", "boyuk", "plastik", "paket", "karton", "mix",
               "assorti", "classic", "klassik", "extra", "premium", "super", "gold", "silver", "blue", "white", "black", "red",
               "qirmizi", "yasil", "sari", "qara", "mavi"}

def _owords(n):
    w = [t for t in re.split(r"[^a-z0-9&]+", _f(n)) if t]
    while w and (w[0] in _OTHER_SKIP or len(w[0]) < 2 or w[0].isdigit()): w = w[1:]   # Bazarstore təchizatçı kodları: "X S.u Kasa"
    return w

def reassign_other(data):
    """"diger"-dəki məhsulları mümkün olduqda düzgün kateqoriyaya köçürür; köçənlərin sayını qaytarır."""
    cats = data.get("categories", {})
    if "diger" not in cats: return 0
    from collections import Counter, defaultdict
    b1, b2, tw = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for cid, c in cats.items():
        if cid == "diger" or cid not in CATEGORIES: continue
        for items in c["stores"].values():
            for it in items:
                w = _owords(it["name"])
                if w and len(w[0]) >= 3:
                    b1[w[0]][cid] += 1
                    if len(w) > 1: b2[" ".join(w[:2])][cid] += 1
                for t in set(w):
                    if len(t) >= 4 and t.isalpha() and t not in _OTHER_STOP: tw[t][cid] += 1
    def best(cnt, mn, share):
        if not cnt: return None
        cid, k = cnt.most_common(1)[0]
        return cid if k >= mn and k / sum(cnt.values()) >= share else None
    def where(name):
        f = _f(name)
        for rx, cid in _OTHER_HARD:
            if rx.search(f): return cid
        w = _owords(name)
        if w and len(w[0]) >= 3:
            cid = (len(w) > 1 and best(b2.get(" ".join(w[:2])), 2, 0.7)) or best(b1.get(w[0]), 3, 0.7)
            if cid: return cid
        for rx, cid in _OTHER_SOFT:
            if rx.search(f): return cid
        cands = [(tw[t].most_common(1)[0][1] / sum(tw[t].values()), sum(tw[t].values()), t) for t in set(w) if t in tw]
        for sh, n, t in sorted(cands, reverse=True):
            if n >= 5 and sh >= 0.8: return tw[t].most_common(1)[0][0]
        return None
    have = {(s, name_key(it["name"])) for cid, c in cats.items() if cid != "diger" for s, l in c["stores"].items() for it in l}
    moved = 0
    for store, items in list(cats["diger"]["stores"].items()):
        keep = []
        for it in items:
            if (store, name_key(it["name"])) in have: moved += 1; continue   # mağaza eyni məhsulu başqa kateqoriyada da verir
            cid = where(it["name"])
            if cid and cid in cats:
                cats[cid]["stores"].setdefault(store, []).append(it); moved += 1
            else:
                keep.append(it)
        cats["diger"]["stores"][store] = keep
    return moved

def tidy(data):
    """Bütün mağazalar: adlar təmizlənir, dublikatlar birləşir, köhnə şəkil linkləri silinir (sayt şəkil göstərmir)."""
    for c in data.get("categories", {}).values():
        for s, items in c.get("stores", {}).items():
            for it in items:
                it.pop("img", None)
                it["name"] = clean_name(it["name"])
            c["stores"][s] = dedupe(items)

# ── Öz sayt ↔ Wolt: eyni məhsul (ad sözləri + ÖLÇÜ) ─────────────────────────
_SZ = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kq|kg|qr|gr|q|g|ml|lt|litr|l)(?![a-z])")
_SZU = {"kq": ("w", 1000), "kg": ("w", 1000), "qr": ("w", 1), "gr": ("w", 1), "q": ("w", 1), "g": ("w", 1),
        "ml": ("v", 1), "lt": ("v", 1000), "litr": ("v", 1000), "l": ("v", 1000)}

def _parse(name):
    """(sözlər, ölçülər): diakritiksiz ("GUNEBAXAN YAGI" = "Günəbaxan yağı"); ölçü q/ml-ə çevrilir (0.5 L = 500 ml)."""
    t = _f(name)
    sz = set()
    for m in _SZ.finditer(t):
        fam, mul = _SZU[m.group(2)]
        sz.add((fam, round(float(m.group(1).replace(",", ".")) * mul)))
    words = {_stem(w) for w in re.findall(r"[a-z0-9]+(?:\.\d+)?", _SZ.sub(" ", t))}
    return words, sz

def _stem(w):
    """Sadə şəkilçi: yağı = yağ, sabunu = sabun, kremaları = krema (yalnız müqayisə üçün)."""
    return re.sub(r"(?:lari|leri|lar|ler|si|su|i|u)$", "", w) if len(w) > 4 and not w[0].isdigit() else w

def sim(a, b, w=None):
    """Ad oxşarlığı 0..1: ortaq sözlərin çəkisi / uzun adın sözlərinin çəkisi (w: söz -> çəki; nadir söz ağır, yoxdursa hamısı 1).
    0: ölçülər fərqlidir (1 L ≠ 0.5 L), hər iki adda fərqli rəqəm (18 yaş ≠ 12 yaş, 1+1 ≠ 4 ədəd)
    və ya hər iki adda o birində olmayan söz var (dad/rəng/növ)."""
    (wa, sa), (wb, sb) = (a if isinstance(a, tuple) else _parse(a)), (b if isinstance(b, tuple) else _parse(b))
    if not wa or not wb or (sa and sb and not sa & sb): return 0
    na, nb = {t for t in wa if t[0].isdigit()}, {t for t in wb if t[0].isdigit()}
    if na and nb and na != nb: return 0
    if {t for t in wa - wb if len(t) > 2 and not t[0].isdigit()} and {t for t in wb - wa if len(t) > 2 and not t[0].isdigit()}:
        return 0   # hər iki adda qarşılıqsız söz: adətən fərqli dad/rəng/növ (Limon ≠ Alma, Yaşıl ≠ Qara)
    f = (lambda S: sum(w.get(t, 1) for t in S)) if w else len
    return f(wa & wb) / max(f(wa), f(wb))

def empty_data():
    return {
        "last_updated": "",
        "stores": ALL_STORES,
        "groups": GROUPS,
        "categories": {
            cid: {"name": info["name"], "stores": {s: [] for s in ALL_STORES}}
            for cid, info in CATEGORIES.items()
        }
    }

# ── OBA ──────────────────────────────────────────────────────────────────

_OBA_CARD = re.compile(
    r'<h3[^>]*>([^<]+)</h3>.*?<p class="color-mako[^>]*>([^<]*)</p>.*?'
    r'<span class="fs-lg-24 fs-20 lh-24 fw-400">([\d.,]+)</span>', re.S)
OBA_STEP = 24

def _oba_cards(html):
    """(ad, kateqoriya, qiymət) — kart "<!-- Product card -->" ilə ayrılır."""
    from html import unescape
    out = []
    for chunk in html.split("<!-- Product card -->")[1:]:
        m = _OBA_CARD.search(chunk)
        if not m: continue
        out.append((unescape(m.group(1)).strip(), unescape(m.group(2)).strip(), m.group(3)))
    return out

def scrape_oba():
    """oba.az/products/ — server tərəfindən render olunan HTML, ?start= ilə səhifələmə."""
    ses = _session()
    ses.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124",
                        "Accept-Language": "az"})
    ses.headers.pop("Content-Type", None)

    def page(start):
        try:
            r = ses.get("https://oba.az/products/", params={"start": start} if start else None, timeout=30)
            return _oba_cards(r.text) if r.status_code == 200 else []
        except Exception:
            return []

    results = {c: [] for c in CATEGORIES}
    seen, total, start, empty = set(), 0, 0, 0
    print("  [OBA] oba.az/products/ …", end="", flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        while start < 60000 and empty < 1:
            offsets = [start + i * OBA_STEP for i in range(8)]
            new_in_batch = 0
            for cards in ex.map(page, offsets):
                for name, ocat, raw in cards:
                    price = clean_price(raw)
                    key = (name.lower(), price)
                    if not name or price is None or key in seen: continue
                    seen.add(key); total += 1; new_in_batch += 1
                    cat = classify(name, ocat)
                    if cat: results[cat].append({"name": name, "price": price})
            if new_in_batch == 0: empty += 1
            start += 8 * OBA_STEP
            print(f" {total}", end="", flush=True)
    print(f"\n  [OBA] ✓ {total} məhsul")
    return results if total else None

# ── ARAZ — arazmarket.az API ─────────────────────────────────────────────
ARAZ_API = "https://b7x9kq.arazmarket.az/api"

def _araz_price(p):
    """Rəfdəki faktiki qiymət: endirim varsa endirimli, yoxsa adi qiymət."""
    if p.get("is_discount") and p.get("discount_price"):
        v = clean_price(p.get("discount_price"))
        if v: return v
    return clean_price(p.get("sales_price"))

def scrape_araz():
    """Araz-ın öz API-si. Səhifələmə etibarsızdır (səhifələr arasında təkrar/itkin məhsullar), ona görə
    hər ana kateqoriya (alt kateqoriyaları da əhatə edir) per_page=5000 ilə BİR sorğuda çəkilir.
    Uğursuz olarsa None qaytarır (Wolt-a keçilir)."""
    ses = _session()
    ses.headers.update({"Accept": "application/json", "Origin": "https://arazmarket.az",
                        "Referer": "https://arazmarket.az/", "Accept-Language": "az"})
    try:
        r = ses.get(f"{ARAZ_API}/categories", timeout=40)
        r.raise_for_status()
        tops = [(n["id"], n.get("title") or "") for n in r.json().get("data") or []]
    except Exception as e:
        print(f"  [Araz] ✗ kateqoriyalar alınmadı: {e}")
        return None
    print(f"  [Araz] {len(tops)} ana kateqoriya", flush=True)

    def get(top):
        cid, title = top
        for attempt in range(3):
            try:
                r = ses.get(f"{ARAZ_API}/products/category/{cid}", params={"page": 1, "per_page": 5000}, timeout=180)
                if r.status_code == 200:
                    return title, (r.json().get("data") or {})
            except Exception:
                pass
            time.sleep(3 * (attempt + 1))
        return title, None

    results = {c: [] for c in CATEGORIES}
    seen, failed = set(), []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for title, d in ex.map(get, tops):
            if d is None: failed.append(title); continue
            if int((d.get("pagination") or {}).get("last_page") or 1) > 1:
                print(f"  [Araz] ⚠ {title}: bir səhifəyə sığmadı", flush=True)
            for p in d.get("products") or []:
                pid, name, price = p.get("id"), (p.get("title") or "").strip(), _araz_price(p)
                if pid in seen or not name or price is None: continue
                seen.add(pid)
                cat = classify(name, f"{title} > {p.get('category_title') or ''}")
                e = {"name": name, "price": price}
                rp = clean_price(p.get("sales_price"))
                if p.get("is_discount") and rp and rp > price: e["rp"] = rp   # adi qiymət (yalnız birləşdirmə üçün, yazılmır)
                results[cat].append(e)
    total = len(seen)
    print(f"  [Araz] ✓ {total} məhsul (arazmarket.az)" + (f"; alınmadı: {failed}" if failed else ""), flush=True)
    return results if total else None

# ── BAZARSTORE — bazarstore.az (nopCommerce, HTML) ───────────────────────
def _title(name):
    """"ALISHAAN BASMATI DÜYÜ 2 KQ" -> "Alishaan Basmati Düyü 2 Kq" (İ/I düzgün)."""
    return " ".join(w[:1].upper() + _low(w[1:]) if w[:1].isalpha() else _low(w) for w in name.split())

def scrape_bazarstore_flat():
    """"Ehtiyat üsul: "Bütün məhsullar" siyahısı (1 səhifə = 10 məhsul), orderby=5 (ada görə) ilə sabit sıralama."""
    import html as _html
    ses = _session()
    ses.headers.pop("Content-Type", None)
    ses.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "az"})
    url = "https://bazarstore.az/b%C3%BCt%C3%BCn-m%C9%99hsullar"
    item_rx = re.compile(r'class="product-item" data-productid="(\d+)" data-bzdl-item=\'([^\']*)\'(.*?)</div>\s*</div>\s*</div>', re.S)

    def page(p):
        for attempt in range(4):
            try:
                r = ses.get(url, params={"orderby": 5, "pagenumber": p}, timeout=60)
                if r.status_code == 200: return r.text
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        return None

    first = page(1)
    if not first:
        print("  [Bazarstore] ✗ saytdan cavab yoxdur")
        return None
    last = max([int(x) for x in re.findall(r'data-page="(\d+)"', first)] or [1])
    print(f"  [Bazarstore] {last} səhifə", flush=True)
    results = {c: [] for c in CATEGORIES}
    seen, failed = set(), 0
    def ingest(h):
        n = 0
        for pid, j, body in item_rx.findall(h):
            if pid in seen: continue
            try: d = json.loads(_html.unescape(j))
            except Exception: continue
            name = _html.unescape(d.get("item_name") or "").strip()
            price = clean_price(d.get("price"))
            if not name or price is None or name.replace(" ", "").isdigit(): continue   # adı yalnız kod olan məhsullar
            seen.add(pid); n += 1
            results[classify(name, d.get("item_category") or "")].append({"name": _title(name), "price": price})
        return n
    ingest(first)
    with ThreadPoolExecutor(max_workers=16) as ex:
        for h in ex.map(page, range(2, last + 1)):
            if h is None: failed += 1; continue
            ingest(h)
    total = len(seen)
    print(f"  [Bazarstore] ✓ {total} məhsul" + (f"; {failed} səhifə alınmadı" if failed else ""), flush=True)
    return results if total else None

def _bazar_menu(html_text):
    """Baş səhifənin 3 səviyyəli menyusundan [(url, "Kök > Alt > Yarpaq")] çıxarır."""
    from html.parser import HTMLParser
    import html as _html
    class P(HTMLParser):
        def __init__(self):
            super().__init__(); self.depth = 0; self.stack = []; self.cur = None; self.names = {}; self.out = []; self.in_menu = False
        def handle_starttag(self, tag, attrs):
            a = dict(attrs); cls = a.get("class") or ""
            if tag == "ul" and "mega-menu" in cls: self.in_menu = True
            if not self.in_menu: return
            if tag == "ul": self.stack.append("sub" if "sublist" in cls else "ul"); self.depth += 1 if "sublist" in cls else 0
            if tag == "a" and a.get("href", "").startswith("/"):
                self.cur = {"href": a["href"], "level": self.depth, "last": "lastLevelCategory" in cls, "sub": "with-subcategories" in cls, "text": ""}
        def handle_endtag(self, tag):
            if not self.in_menu: return
            if tag == "ul" and self.stack:
                if self.stack.pop() == "sub": self.depth -= 1
            if tag == "a" and self.cur:
                c = self.cur; self.cur = None
                t = _html.unescape(re.sub(r"[^\w\s,&.()/-]", "", c["text"])).strip()
                self.names[c["level"]] = t
                for k in [k for k in self.names if k > c["level"]]: del self.names[k]
                if c["last"] or not c["sub"]:
                    path = " > ".join(self.names[k] for k in sorted(self.names) if k <= c["level"])
                    self.out.append((c["href"], path))
        def handle_data(self, data):
            if self.cur is not None: self.cur["text"] += data
    p = P(); p.feed(html_text)
    seen, res = set(), []
    for u, path in p.out:
        if u not in seen and not u.startswith("/blog"): seen.add(u); res.append((u, path))
    return res

def scrape_bazarstore():
    """Kateqoriya menyusunu gəzir: hər yarpaq kateqoriya səhifəsi (10 məhsul/səhifə) + kateqoriya yolu ilə təsnif.
    Menyu alınmasa "Bütün məhsullar" siyahısına (kateqoriyasız) qayıdır."""
    import html as _html
    ses = _session()
    ses.headers.pop("Content-Type", None)
    ses.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "az"})
    base = "https://bazarstore.az"
    try:
        home = ses.get(base + "/", timeout=60).text
        leaves = _bazar_menu(home)
    except Exception as e:
        print(f"  [Bazarstore] ✗ menyu alınmadı: {e}"); leaves = []
    if len(leaves) < 20:
        print("  [Bazarstore] menyu tapılmadı → ümumi siyahı"); return scrape_bazarstore_flat()
    print(f"  [Bazarstore] {len(leaves)} kateqoriya", flush=True)
    item_rx = re.compile(r'class="product-item" data-productid="(\d+)" data-bzdl-item=\'([^\']*)\'(.*?)</div>\s*</div>\s*</div>', re.S)

    def page(job):
        url, path, p = job
        for attempt in range(4):
            try:
                r = ses.get(base + url, params={"orderby": 5, "pagenumber": p} if p > 1 else {"orderby": 5}, timeout=60)
                if r.status_code == 200: return path, r.text
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        return path, None

    results = {c: [] for c in CATEGORIES}
    seen, failed = set(), 0
    def ingest(path, h):
        new = 0
        for pid, j, body in item_rx.findall(h):
            if pid in seen: continue
            try: d = json.loads(_html.unescape(j))
            except Exception: continue
            name = _html.unescape(d.get("item_name") or "").strip()
            price = clean_price(d.get("price"))
            if not name or price is None or name.replace(" ", "").isdigit(): continue
            seen.add(pid); new += 1
            results[classify(name, path)].append({"name": _title(name), "price": price})
        return new
    # kateqoriyalar çox üst-üstə düşür: növbəti səhifə yalnız əvvəlki səhifə yeni məhsul verən kateqoriyalar üçün çəkilir
    with ThreadPoolExecutor(max_workers=24) as ex:
        firsts = list(ex.map(page, [(u, pth, 1) for u, pth in leaves]))
        active = []
        for (u, pth), (_, h) in zip(leaves, firsts):
            if h is None: failed += 1; continue
            n = ingest(pth, h)
            last = max([int(x) for x in re.findall(r'data-page="(\d+)"', h)] or [1])
            if n > 0 and last > 1: active.append((u, pth, last))
        pg, requests_n = 2, len(leaves)
        while active and pg < 200:
            jobs = [(u, pth, pg) for u, pth, last in active if pg <= last]
            requests_n += len(jobs)
            nxt = []
            for (u, pth, pg_), (_, h) in zip(jobs, ex.map(page, jobs)):
                if h is None: failed += 1; continue
                if ingest(pth, h) > 0:
                    nxt.append(next(x for x in active if x[0] == u))
            active = nxt; pg += 1
        print(f"  [Bazarstore] {requests_n} sorğu", flush=True)
        # tamlıq: heç bir kateqoriyada tapılmayan məhsullar "Bütün məhsullar" siyahısından (kateqoriyasız, ad üzrə təsnif)
        flat = "/b%C3%BCt%C3%BCn-m%C9%99hsullar"
        _, h1 = page((flat, "", 1))
        if h1:
            ingest("", h1)
            lastp = max([int(x) for x in re.findall(r'data-page="(\d+)"', h1)] or [1])
            before = len(seen)
            for _, h in ex.map(page, [(flat, "", pg) for pg in range(2, lastp + 1)]):
                if h is None: failed += 1; continue
                ingest("", h)
            print(f"  [Bazarstore] ümumi siyahıdan əlavə {len(seen) - before} məhsul", flush=True)
    total = len(seen)
    print(f"  [Bazarstore] ✓ {total} məhsul" + (f"; {failed} səhifə alınmadı" if failed else ""), flush=True)
    return results if total else None

# ── WOLT ─────────────────────────────────────────────────────────────────
WOLT_HEADS = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
    "Content-Type":"application/json",
    "Origin":"https://wolt.com",
    "Referer":"https://wolt.com/",
}

def _session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    ses = requests.Session()
    retry = Retry(total=3, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=None)
    ses.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    ses.headers.update(WOLT_HEADS)
    return ses

def _wolt_url(slug):
    return (f"https://consumer-api.wolt.com/consumer-api/consumer-assortment"
            f"/v1/venues/slug/{slug}/assortment/items/search?language=az")

# Yalnız Wolt-da olan endirim kateqoriyaları ("🎉Wolta Özəl Xüsusi Endirimlər🎉", "Wolt Specials"):
# bu endirim mağazanın rəfində yoxdur, ona görə həmin məhsullar (adi kateqoriyada da olsalar) götürülmür.
_WOLT_DEAL = re.compile(_f(r"wolta? ?(özəl|ozel|özel|special|eksklüziv|exclusive)|(?<!\w)wolt deal"))

def _wolt_price(item):
    for k in ("price", "baseprice", "unit_price"):
        v = item.get(k)
        if isinstance(v, dict): v = v.get("amount") or v.get("value")
        if isinstance(v, (int, float)) and v > 0:
            return round(v / 100, 2)
    return None

def _wolt_weight(item):
    """Çəkiyə görə satılan "ədəd" məhsulda bir ədədin təxmini çəkisi (qram): sell_by_weight_config.grams_per_step.
    input_type="grams" olanlarda (meyvə-tərəvəz) parça çəkisi yoxdur, qiymət 1 kq üçün qalır."""
    c = item.get("sell_by_weight_config")
    if isinstance(c, dict) and c.get("input_type") == "number_of_items":
        g = c.get("grams_per_step")
        if isinstance(g, (int, float)) and g > 0:
            return round(g)
    return None

def _wolt_entry(item, path=""):
    """Wolt məhsul obyektindən (ad, kateqoriya, yazı) çıxarır; uyğun deyilsə None."""
    name = item.get("name", "")
    if isinstance(name, dict): name = name.get("az") or name.get("en") or ""
    name = re.sub(r"\s+", " ", name).strip()   # ad olduğu kimi (yalnız artıq boşluqlar)
    price = _wolt_price(item)
    if not name or price is None or price >= 999: return None
    e = {"name": name, "wolt_price": price}
    wt = _wolt_weight(item)
    if wt: e["wt"] = wt
    g = item.get("barcode_gtin")   # ştrix-kod: yalnız məhsul şəkli üçün (scrapers/off_images.py "im"-ə çevirir və silir)
    if isinstance(g, str) and re.fullmatch(r"\d{8,14}", g): e["gtin"] = g
    return classify(name, path), e

def _wolt_base(slug):
    return f"https://consumer-api.wolt.com/consumer-api/consumer-assortment/v1/venues/slug/{slug}/assortment"

def _wolt_pick_venue(ses, store, probe):
    """İşləyən filialı tapır (müvəqqəti blok üçün 3 cəhd). probe(slug) -> True/False."""
    for attempt in range(3):
        for slug in wolt_slugs(store):
            try:
                if probe(slug):
                    print(f"  [Wolt/{store}] filial: {slug}")
                    return slug
                print(f"  [Wolt/{store}] {slug}: cavab yoxdur")
            except Exception as e:
                print(f"  [Wolt/{store}] {slug}: {type(e).__name__}")
        time.sleep(10 * (attempt + 1))
    return None

def scrape_wolt_full(store, slug=None):
    """Filialın BÜTÜN kataloqu: kateqoriya ağacı -> hər yarpaq kateqoriya (səhifələmə ilə).
    Açar söz axtarışından çox məhsul verir. Uğursuz olarsa None."""
    ses = _session()
    def probe(slug):
        r = ses.get(_wolt_base(slug), params={"language": "az"}, timeout=30)
        return r.status_code == 200 and bool(r.json().get("categories"))
    if slug:   # konkret filial (çoxfilialli rejim): 3 cəhd
        ok = False
        for attempt in range(3):
            try:
                ok = probe(slug)
            except Exception as e:
                print(f"  [Wolt/{store}] {slug}: {type(e).__name__}")
            if ok: break
            time.sleep(8 * (attempt + 1))
        if not ok: return None
        print(f"  [Wolt/{store}] filial: {slug}")
    else:
        slug = _wolt_pick_venue(ses, store, probe)
        if not slug: return None
    base = _wolt_base(slug)
    tree = ses.get(base, params={"language": "az"}, timeout=30).json()["categories"]
    leaves = []   # (slug, "Üst > Alt")
    def walk(nodes, trail=""):
        for c in nodes:
            t = f"{trail} > {c.get('name','')}" if trail else c.get("name", "")
            if c.get("subcategories"): walk(c["subcategories"], t)
            elif c.get("slug"): leaves.append((c["slug"], t))
    walk(tree)

    failed = []   # alınmayan səhifələr (limit/şəbəkə); səssizcə itməsin
    def fetch(leaf):
        cs, trail = leaf
        out, tok = [], None
        for _ in range(100):
            params = {"language": "az"}
            if tok: params["page_token"] = tok
            d = None
            for attempt in range(4):
                try:
                    r = ses.get(f"{base}/categories/slug/{cs}", params=params, timeout=30)
                    if r.status_code == 200:
                        d = r.json(); break
                    status = r.status_code
                except Exception as e:
                    status = type(e).__name__
                time.sleep(2 * (attempt + 1))
            if d is None:
                failed.append((cs, status)); break
            out += d.get("items") or []
            tok = (d.get("metadata") or {}).get("next_page_token")
            if not tok: break
        return trail, out

    results = {c: [] for c in CATEGORIES}
    seen = set()
    deal_ids = set()   # Wolt-özəl endirimdəki məhsullar: götürülmür (eyni məhsul adi kateqoriyada da olur)
    def is_deal(trail): return bool(_WOLT_DEAL.search(_f(trail)))
    def collect(trail, items):
        for item in items:
            uid = item.get("id") or item.get("name")
            if uid in seen or uid in deal_ids: continue
            seen.add(uid)
            r = _wolt_entry(item, trail)
            if r: results[r[0]].append(r[1])
    with ThreadPoolExecutor(max_workers=8) as ex:
        fetched = list(ex.map(fetch, leaves))
    for trail, items in fetched:
        if is_deal(trail): deal_ids.update(it.get("id") or it.get("name") for it in items)
    for trail, items in fetched:
        collect(trail, items)

    # Wolt GitHub IP-lərinə 429 verir: alınmayan kateqoriyalar bir-bir, uzun fasilə ilə təkrar yoxlanır
    if failed:
        bad = {cs for cs, _ in failed}
        todo = [lf for lf in leaves if lf[0] in bad]
        failed.clear()
        for rnd in range(3):
            time.sleep(15 * (rnd + 1))
            still = []
            for lf in todo:
                before = len(failed)
                trail, items = fetch(lf)
                if len(failed) > before: still.append(lf)
                else: collect(trail, items)
                time.sleep(1)
            failed.clear()
            todo = still
            if not todo: break
        failed.extend((lf[0], "təkrar uğursuz") for lf in todo)
    total = sum(len(v) for v in results.values())
    print(f"  [Wolt/{store}] tam kataloq: {len(leaves)} kateqoriya, {total} məhsul"
          + (f"; Wolt-özəl endirimli {len(deal_ids)} məhsul çıxarıldı" if deal_ids else "")
          + (f"; {len(failed)} sorğu alınmadı {sorted({str(f[1]) for f in failed})}" if failed else ""), flush=True)
    return results if total else None

# Qiymətin mənbə üsulu (tək filial / filiallar üzrə median). Üsul dəyişən gün qiymət fərqləri
# real qiymət dəyişikliyi deyil, ona görə həmin gün dəyişiklik nişanı və tarixçə yazılmır.
WOLT_SRC = {}
# Üsul versiyası: v2 = Wolt-özəl endirimli məhsullar çıxarılır.
WOLT_SRC_VER = "v2"

def scrape_wolt_multi(store):
    """WOLT_BRANCHES-dəki bütün filialların tam kataloqu: ad üzrə birləşdirilir, qiymət = filiallar üzrə median.
    Heç bir filial alınmasa None."""
    import statistics
    slugs = [x.strip() for x in os.environ.get("WOLT_BRANCHES_" + store.upper(), "").split(",") if x.strip()] \
        or WOLT_BRANCHES.get(store)
    if not slugs: return None
    merged, ok, t0 = {}, 0, time.time()
    for slug in slugs:
        res = scrape_wolt_full(store, slug)
        if not res:
            print(f"  [Wolt/{store}] ✗ {slug} alınmadı", flush=True)
            continue
        ok += 1
        before = len(merged)
        for cid, items in res.items():
            for e in items:
                k = name_key(e["name"]) or e["name"]   # "Dtj 750ml" = "Dtj  750 ml": filiallarda yazılışı fərqli eyni məhsul birləşir
                m = merged.get(k)
                if m is None:
                    merged[k] = {"cid": cid, "p": [e["wolt_price"]], "e": dict(e)}
                else:
                    m["p"].append(e["wolt_price"])
                    if "wt" not in m["e"] and e.get("wt"): m["e"]["wt"] = e["wt"]
                    if "gtin" not in m["e"] and e.get("gtin"): m["e"]["gtin"] = e["gtin"]
        print(f"  [Wolt/{store}] {slug}: +{len(merged) - before} yeni (cəmi {len(merged)}); {round(time.time() - t0)} san", flush=True)
        time.sleep(5)
    if not ok: return None
    results = {c: [] for c in CATEGORIES}
    for m in merged.values():
        e = m["e"]; e["wolt_price"] = round(statistics.median_low(m["p"]), 2)
        results[m["cid"]].append(e)
    print(f"  [Wolt/{store}] {ok}/{len(slugs)} filial, {len(merged)} məhsul", flush=True)
    WOLT_SRC[store] = "multi-" + WOLT_SRC_VER
    return results

def scrape_wolt(store):
    """Əvvəl tam kataloq; alınmasa açar söz axtarışı (köhnə üsul)."""
    full = scrape_wolt_multi(store) or scrape_wolt_full(store)
    if full: return full
    print(f"  [Wolt/{store}] tam kataloq alınmadı → açar söz axtarışı")
    ses = _session()
    def probe(slug):
        r = ses.post(_wolt_url(slug), json={"q": "süd"}, timeout=15)
        return r.status_code == 200 and r.json().get("items") is not None
    slug = _wolt_pick_venue(ses, store, probe)
    if not slug:
        print(f"  [Wolt/{store}] ✗ heç bir filial cavab vermədi (WOLT_SLUG_{store.upper()} ilə düzgün slug verin)")
        return None   # None = uğursuz, boş nəticə ilə qarışdırılmasın
    url = _wolt_url(slug)
    queries = sorted({kw.strip() for info in CATEGORIES.values() for kw in info["kw"]})

    def run(q):
        try:
            r = ses.post(url, json={"q": q}, timeout=20)
            return r.json().get("items") or [] if r.status_code == 200 else []
        except Exception:
            return []

    results = {c: [] for c in CATEGORIES}
    seen = set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for items in ex.map(run, queries):
            for item in items:
                r = _wolt_entry(item)
                if not r: continue
                uid = r[1]["name"].lower().strip()
                if uid in seen: continue
                seen.add(uid)
                results[r[0]].append(r[1])
    total = sum(len(v) for v in results.values())
    print(f"  [Wolt/{store}] {total} məhsul")
    return results if total else None

# ── BİRLƏŞDİRMƏ ──────────────────────────────────────────────────────────
def merge_own_wolt(own_list, wolt_list):
    """Öz sayt siyahısı əsasdır; eyni məhsulun Wolt qiyməti `wolt_price` kimi əlavə olunur, qalan Wolt məhsulları ayrıca.
    Eyni məhsul: ölçü eyni (hər iki adda varsa), rəqəmlər ziddiyyətsiz, qiymət 1.6 dəfədən az fərqli və
    çəkili ad oxşarlığı >= 0.6 (ölçü yalnız bir adda: >= 0.8, heç birində: >= 0.7). Söz çəkisi = log(1 + N / tezlik):
    "Prezident", "Chivas" kimi nadir sözlər "yağ", "süd"-dən ağırdır. Hər Wolt məhsulu ən çox bir öz məhsula bağlanır
    (ən oxşar cütlər əvvəl). Əvvəllər ölçü yoxlanmırdı: "Süd 1 L" Wolt-un "Süd 0.5 L"-i ilə birləşir, o Wolt məhsulu siyahıdan düşürdü.
    Böyük aksiya (öz qiymət adi qiymətin `rp` yarısı və ya daha az): mağaza saytındakı aksiya çox vaxt onlayn sifarişə aiddir,
    rəfdə qiymət fərqli olur (Araz "Avokado əd": saytda 3.49 → 0.99, kassada 1.99). Eyni məhsulun Wolt qiyməti varsa
    öz qiymət götürülmür, yalnız Wolt qiyməti qalır (saytda W ilə). Qiymət yoxlaması adi qiymətlə də aparılır."""
    import math
    own_p = [_parse(it["name"]) for it in own_list]
    wolt_p = [_parse(w["name"]) for w in wolt_list]
    df = {}
    for ws, _ in own_p + wolt_p:
        for t in ws: df[t] = df.get(t, 0) + 1
    n = len(own_p) + len(wolt_p)
    wt = {t: math.log(1 + n / c) for t, c in df.items()}
    idx = {}
    for j, (ws, _) in enumerate(wolt_p):
        for t in ws: idx.setdefault(t, []).append(j)
    pairs = []
    for i, (ws, sz) in enumerate(own_p):
        cand = set()
        for t in ws: cand.update(idx.get(t, ()))
        p = own_list[i]["price"]; hi = max(p, own_list[i].get("rp") or 0)   # aksiyalıda: aksiya ilə adi qiymət arası
        for j in cand:
            q = wolt_list[j]["wolt_price"]
            if p <= 0 or q <= 0 or q > 1.6 * hi or q * 1.6 < p: continue
            s = sim(own_p[i], wolt_p[j], wt)
            osz = wolt_p[j][1]
            need = 0.6 if sz and osz else 0.7 if not sz and not osz else 0.8
            if s >= need: pairs.append((-s, i, j))
    pairs.sort()
    match, used = {}, set()
    for _, i, j in pairs:
        if i not in match and j not in used: match[i] = j; used.add(j)
    merged = []
    for i, item in enumerate(own_list):
        entry = {"name": item["name"], "price": item["price"]}
        j = match.get(i)
        if j is not None:
            w = wolt_list[j]
            if abs(w["wolt_price"] - item["price"]) > 0.005: entry["wolt_price"] = w["wolt_price"]
            if w.get("wt"): entry["wt"] = w["wt"]
            if w.get("gtin"): entry["gtin"] = w["gtin"]
            if item.get("rp") and item["price"] <= 0.5 * item["rp"] and "wolt_price" in entry:
                del entry["price"]   # 50%+ aksiya: Wolt qiyməti göstərilir
        merged.append(entry)
    for j, w in enumerate(wolt_list):   # yalnız Wolt-da olanlar
        if j not in used:
            merged.append({k: w[k] for k in ("name", "wolt_price", "wt", "gtin") if k in w})
    return merged

# ── Qiymət dəyişikliyi: məhsulda "pp" (əvvəlki qiymət) + "pd" (dəyişmə tarixi); tam tarixçə data/history.json-da ───────
def _hk(store, name):
    """Qısa açar (index.html-dəki hk() ilə eyni): FNV-1a + djb2, 32 bit hər biri."""
    h1, h2 = 0x811c9dc5, 5381
    for b in f"{store}|{name}".encode("utf-8"):
        h1 = ((h1 ^ b) * 0x01000193) & 0xffffffff
        h2 = ((h2 * 33) ^ b) & 0xffffffff
    return f"{h1:08x}{h2:08x}"

def _eff(it):
    p = it.get("price", it.get("wolt_price"))
    return None if p is None else round(float(p), 2)

def _iso(dmy):
    """'15.10.2026 07:26' -> '2026-10-15'"""
    try: return datetime.strptime(dmy.split()[0], "%d.%m.%Y").strftime("%Y-%m-%d")
    except Exception: return None

def track_changes(store, data, hist):
    """Yeni qiymətləri mağazanın əvvəlki qiymətləri ilə müqayisə edir (apply_to_data əvvəlki məlumatı əvəz etməzdən əvvəl çağırılır)."""
    return {clean_name(it["name"]): it for c in data["categories"].values() for it in c["stores"].get(store, [])}

def _real_change(a, b):
    """İki qiymət arasındakı fərq real dəyişiklik sayılırmı: 2 dəfədən çox fərq adətən data səhvi və ya aksiyanın mənbə
    dəyişikliyidir (Araz "Avokado əd": saytda 0.99 → Wolt 1.99), "↑ 101%" nişanı yanıldıcıdır."""
    return a > 0 and b > 0 and max(a, b) <= 2 * min(a, b)

def mark_changes(old, items, store, hist, today, old_day):
    for it in items:
        p = _eff(it); o = old.get(it["name"])
        if p is None or o is None: continue
        if ("price" in it) != ("price" in o): continue   # mənbə dəyişib (öz sayt ↔ Wolt): qiymət dəyişikliyi deyil
        op = _eff(o)
        if op is not None and abs(op - p) > 0.004 and not _real_change(op, p): continue
        if op is not None and abs(op - p) > 0.004:
            it["pp"], it["pd"] = op, today
            if hist is not None and old_day:
                k = _hk(store, it["name"])
                lst = hist.setdefault(k, [[old_day, op]])
                if lst[-1][0] == today: lst[-1][1] = p
                elif lst[-1][1] != p: lst.append([today, p])
                del lst[:-40]
        elif o.get("pp") is not None and o.get("pd") and _real_change(o["pp"], p) and (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(o["pd"], "%Y-%m-%d")).days <= 14:
            it["pp"], it["pd"] = o["pp"], o["pd"]   # yaxın vaxtda dəyişib: nişan qalır

def apply_to_data(own_res, wolt_res, store, data, hist=None, wolt_on=True):
    own_res, wolt_res = own_res or {}, wolt_res or {}
    if not any(own_res.values()) and not any(wolt_res.values()):
        print(f"  [{store}] ⚠ nəticə boşdur — köhnə qiymətlər saxlanıldı")
        return False
    wolt_only = store in WOLT_ONLY
    old = track_changes(store, data, hist)
    old_n = len(old)
    new_n = sum(len(v) for v in own_res.values()) + sum(len(v) for v in wolt_res.values())
    if old_n >= 200 and new_n < 0.4 * old_n:   # natamam nəticə əvvəlki etibarlı datanı əvəz etməsin
        print(f"  [{store}] ⚠ nəticə kəskin azalıb ({old_n} → {new_n}) — köhnə qiymətlər saxlanıldı")
        return False
    # Öz saytı olan mağazada (Araz, OBA) Wolt qiyməti yalnız Wolt-da olan məhsullarda göstərilir: üsul dəyişəndə
    # yalnız onların nişanı buraxılır, öz sayt qiymətlərinin dəyişikliyi adi qaydada qeyd olunur.
    src = WOLT_SRC.get(store, "single-" + WOLT_SRC_VER) if wolt_only or any(wolt_res.values()) else None
    prev_src = (data.get("meta", {}).get(store) or {}).get("src", "single")
    if src and src != prev_src and store in data.get("meta", {}):
        print(f"  [{store}] qiymət mənbəyi dəyişdi ({prev_src} → {src}): bu dəfə Wolt qiymətlərinə dəyişiklik nişanı qoyulmur")
        old = {} if wolt_only else {k: v for k, v in old.items() if "price" in v}
    src = src or (prev_src if prev_src != "single" else None)   # Wolt bu dəfə alınmayıbsa əvvəlki üsul yaddaşda qalır
    today = now().strftime("%Y-%m-%d")
    old_day = _iso((data.get("meta", {}).get(store) or {}).get("updated", "")) or _iso(data.get("last_updated", ""))
    for cid in CATEGORIES:
        if wolt_only:
            items = [{k: w[k] for k in ("name", "wolt_price", "wt", "gtin") if k in w}
                     for w in wolt_res.get(cid,[])]
        else:
            items = merge_own_wolt(own_res.get(cid,[]), wolt_res.get(cid,[]))
        for it in items: it["name"] = clean_name(it["name"])
        items = dedupe(items)
        mark_changes(old, items, store, hist, today, old_day)
        if not wolt_on and not wolt_only:   # Wolt söndürülüb: köhnə Wolt-only məhsullar silinmir, "arxiv" kimi işarələnir
            have = {it["name"] for it in items}
            for it in data["categories"][cid]["stores"].get(store, []):
                if "price" not in it and it.get("wolt_price") is not None and it["name"] not in have:
                    items.append({**it, "stale": True})
        data["categories"][cid]["stores"][store] = items
    data.setdefault("meta", {})[store] = {
        "updated": now().strftime("%d.%m.%Y %H:%M"),
        "own": sum(len(v) for v in own_res.values()),
        "wolt": sum(len(v) for v in wolt_res.values()),
    }
    if src: data["meta"][store]["src"] = src
    data["meta"][store].update(source_meta(store, wolt_on))
    data["meta"][store]["last_success"] = now().strftime("%Y-%m-%dT%H:%M:%S")
    return True

def mark_stale(store, data):
    """Wolt söndürülüb və başqa mənbə yoxdur: mövcud məhsullar silinmir, amma yenidən yoxlanmadığı işarələnir."""
    n = 0
    for c in data["categories"].values():
        for it in c["stores"].get(store, []):
            if not it.get("stale"): it["stale"] = True; n += 1
    m = data.setdefault("meta", {}).setdefault(store, {})
    m.update(source_meta(store, False))
    m.setdefault("last_success", None)
    print(f"  [{store}] Wolt söndürülüb: {n} məhsul 'arxiv' işarələndi (silinmədi)")

# ── MAIN ─────────────────────────────────────────────────────────────────
STORE_KEYS = {s.lower(): s for s in ALL_STORES}   # --store açarı -> mağaza adı

def _save(data, out):
    data["groups"] = GROUPS
    reassign_other(data)
    data["last_updated"] = now().strftime("%d.%m.%Y %H:%M")
    ok, errs = validate_prices(data)
    if not ok:   # səhv/natamam data əvvəlki etibarlı faylın yerinə yazılmır
        print("  ⚠ prices.json YAZILMADI (yoxlama uğursuz):", errs[:3]); return False
    atomic_write_json(data, out)
    return True

def _save_hist(hist, path):
    """90 gündən köhnə son qeydli açarlar atılır."""
    cut = (now() - timedelta(days=90)).strftime("%Y-%m-%d")
    h = {k: v for k, v in hist.items() if v and v[-1][0] >= cut}
    atomic_write_json({"h": h}, path)

def recategorize(data):
    """Mövcud məhsulları yenidən təsnif edir (şəbəkə tələb olunmur)."""
    old = data.get("categories", {})
    new = empty_data()["categories"]
    seen = set()
    RENAMED = {"gigiyena": "beden_baximi", "ayran": "kefir", "spirtli": "likor", "kola": "kola", "ketcup": "ketcup"}   # silinmiş kateqoriya -> yeni
    for oid, c in old.items():
        for store, items in c["stores"].items():
            for it in items:
                cid = assign_cat(it["name"])
                if cid == "diger":   # mağaza kateqoriyası artıq saxlanmır: köhnə təyinatı itirmə
                    cid = RENAMED.get(oid, oid) if RENAMED.get(oid, oid) in CATEGORIES else "diger"
                key = (store, cid, it["name"].lower())
                if key not in seen:
                    seen.add(key)
                    new[cid]["stores"].setdefault(store, []).append(it)
    data["categories"] = new
    data["groups"] = GROUPS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recategorize", action="store_true")
    ap.add_argument("--store", choices=list(STORE_KEYS) + ["all"], default="all")
    ap.add_argument("--wolt-only",  action="store_true")
    ap.add_argument("--own-only",   action="store_true")
    ap.add_argument("--no-wolt",    action="store_true", help="Wolt sorğuları göndərilmir (WOLT_ENABLED=0 ilə eyni)")
    ap.add_argument("--out", default="../data/prices.json")
    args = ap.parse_args()

    out = (Path(__file__).parent / args.out).resolve()
    if out.exists():
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        data["stores"] = ALL_STORES
        # köhnə (artıq istifadə olunmayan) kateqoriyaları at: onlarda köhnəlmiş qiymətlər qalır
        if not args.recategorize:   # recategorize köhnə kateqoriyaları özü yenidən paylayır
            data["categories"] = {k: v for k, v in data["categories"].items() if k in CATEGORIES}
        for cid, info in CATEGORIES.items():
            if cid not in data["categories"]:
                data["categories"][cid] = {"name":info["name"],"stores":{s:[] for s in ALL_STORES}}
    else:
        data = empty_data()
    tidy(data)   # köhnə datada qalmış təkrarlar / şəkil linkləri (mağaza bu dəfə yenilənməsə də)

    if args.recategorize:
        recategorize(data)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print("✅  Yenidən təsnif edildi:", out)
        return

    hist_path = out.parent / "history.json"
    hist = {}
    if hist_path.exists():
        try:
            hist = json.load(open(hist_path, encoding="utf-8")).get("h", {})
        except Exception:
            hist = {}

    targets = list(STORE_KEYS) if args.store == "all" else [args.store]

    for t in targets:
        sname = STORE_KEYS[t]
        print(f"\n{'─'*50}\n  {sname}\n{'─'*50}")
        own_res, wolt_res = {}, {}

        # Öz mənbə (Bravo və Neptun üçün yoxdur — yalnız Wolt)
        if not args.wolt_only:
            if sname == "OBA":
                own_res = scrape_oba()
            elif sname == "Araz":
                own_res = scrape_araz() or {}
            elif sname == "Bazarstore":
                own_res = scrape_bazarstore() or {}

        # Wolt
        wolt_on = wolt_enabled(sname) and not args.no_wolt
        if not args.own_only and sname != "Bazarstore":   # Bazarstore Wolt-da yoxdur
            if wolt_on:
                wolt_res = scrape_wolt(sname)
            else:
                print(f"  [{sname}] Wolt söndürülüb: sorğu göndərilmir, köhnə məlumat saxlanılır")

        if not wolt_on and not any(own_res.values()) and sname in WOLT_ONLY:
            mark_stale(sname, data)
        else:
            apply_to_data(own_res, wolt_res, sname, data, hist, wolt_on)
        _save(data, out)   # timeout olarsa əvvəlki mağazaların nəticəsi itməsin
        _save_hist(hist, hist_path)

    data["groups"] = GROUPS
    data["last_updated"] = now().strftime("%d.%m.%Y %H:%M")
    _save(data, out)
    print(f"\n✅  Saxlandı: {out}  ({out.stat().st_size//1024} KB)")
    print("\n📊  Nəticə:")
    for s in ALL_STORES:
        own_c  = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(s,[]) if "price" in p)
        wolt_c = sum(1 for c in data["categories"].values()
                     for p in c["stores"].get(s,[]) if "wolt_price" in p)
        print(f"   {s:10} → öz: {own_c:5}  |  Wolt: {wolt_c:5}")

if __name__ == "__main__":
    main()
