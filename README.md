# 🛒 QİYMƏTMÜQAYİSƏ

Azərbaycan supermarketlərindəki ərzaq qiymətlərini müqayisə edən sayt.

## Fayllar

```
qiymet-project/
├── index.html              ← Saytın özü
├── data/
│   └── prices.json         ← Qiymətlər (scraper tərəfindən yenilənir)
├── scrapers/
│   └── scraper.py          ← Python scraper
├── requirements.txt        ← Python asılılıqları
└── .github/workflows/
    └── scrape.yml          ← Avtomatik gündəlik scrape
```

## Necə işləyir?

1. GitHub Actions hər gün saat 06:00-da (Bakı vaxtı) `scraper.py`-ı işlədir
2. Scraper Bravo, Neptun, Araz, OBA saytlarından qiymətləri toplayır
3. `data/prices.json` faylını yeniləyir
4. `index.html` bu JSON-dan oxuyaraq cədvəli göstərir

## Quraşdırma addımları

### 1. GitHub hesabı açın
→ github.com

### 2. Yeni repo yaradın
→ "qiymet-muqayise" adı ilə

### 3. Bu faylları yükləyin
→ Bütün faylları repo-ya əlavə edin

### 4. GitHub Pages aktivləşdirin
→ Settings → Pages → Source: main branch → / (root)
→ Saytınız: https://ADINIZ.github.io/qiymet-muqayise

### 5. Hazırdır! 
Scraper hər gün avtomatik işləyəcək.

## Qiymət mənbələri və etibarlılıq
- Mağazanın öz saytından/API-dən alınan qiymət (`price`) həmişə Wolt qiymətindən (`wolt_price`) üstün tutulur.
- Cədvəldə Wolt qiymətləri <sup>W</sup> ilə işarələnir (Wolt qiyməti rəf qiymətindən bir qədər yüksək ola bilər).
- Scrape boş nəticə qaytararsa, köhnə qiymətlər silinmir (`meta` bölməsində hər mağazanın son yenilənmə vaxtı var).
- Wolt filialının slug-ı dəyişibsə, mühit dəyişəni ilə verin: `WOLT_SLUG_NEPTUN=neptun-supermarket-...` (vergüllə bir neçə).

## Mağazalar
- **Bravo** → birmarket.az
- **Neptun** → neptun.az  
- **OBA** → oba.az

## Yeni mağaza əlavə etmək
`scraper.py` faylında `SCRAPERS` lüğətinə yeni scrape funksiyası əlavə edin.
