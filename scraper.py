name: Scrape Prices Daily

on:
  schedule:
    - cron: '0 2 * * *'   # hər gün saat 06:00 Bakı vaxtı
  workflow_dispatch:        # əl ilə də işlədə bilərsiniz

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Python quraşdır
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Asılılıqları yüklə
        run: pip install requests beautifulsoup4

      - name: Scraper işlət
        run: python scrapers/scraper.py

      - name: Nəticəni GitHub-a yüklə
        run: |
          git config user.name "Price Bot"
          git config user.email "bot@qiymet.az"
          git add data/prices.json
          git diff --staged --quiet || git commit -m "💰 Qiymətlər yeniləndi: $(date +'%d.%m.%Y %H:%M')"
          git push
