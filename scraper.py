#!/usr/bin/env python3
"""
scraper_local.py — Génère prices.json depuis le PDF Physionomie BVMT
Usage: python3 scraper_local.py <fichier.pdf>
       python3 scraper_local.py    ← télécharge le PDF du jour automatiquement

Résultat: prices.json dans le même dossier que ce script
Dans l'app: Param → Mettre à jour les prix → charger prices.json
"""
import sys, json, re, os
from datetime import datetime
from collections import defaultdict

try:
    import pdfplumber
except ImportError:
    os.system(f"{sys.executable} -m pip install pdfplumber pillow -q")
    import pdfplumber

NAME_MAP = {
    'LAND OR': "LAND'OR", 'TUNISIE LEASING ET FACTORING': 'TUNISIE LEASING F',
    'SPDIT - SICAF': 'SPDIT-SICAF', 'EURO CYCLES': 'EURO-CYCLES',
    'BTE (ADP)': 'BTE', 'SAH LILAS': 'SAH',
    'WIFACK INTERNATIONAL BANK': 'WIFACK INT BANK',
}
PDF_COMPANIES = [
    "BIAT","ATTIJARI BANK","AMEN BANK","BT","BNA","UIB","UBCI","STB","BH BANK","ATB","WIFACK INT BANK","BTE",
    "POULINA GP HOLDING","SFBT","DELICE HOLDING","LAND'OR","ARTES","ENNAKL AUTOMOBILES","CITY CARS",
    "SMART TUNISIE","MAGASIN GENERAL","MONOPRIX","SOTUMAG","STA","UADH","CELLCOM",
    "STAR","TUNIS RE","ASTREE","BNA ASSURANCES","ASSUR MAGHREBIA","ASSU MAGHREBIA VIE","BH ASSURANCE",
    "TUNISIE LEASING F","SPDIT-SICAF","ATL","CIL","ATTIJARI LEASING","HANNIBAL LEASE","BEST LEASE",
    "PLAC. TSIE-SICAF","TUNINVEST-SICAR","BH LEASING","ONE TECH HOLDING","SOTUVER","SIAME",
    "SAH","EURO-CYCLES","ATELIER MEUBLE INT","OFFICEPLAST","NEW BODY LINE",
    "CARTHAGE CEMENT","MPBS","SOTEMAIL","SITS","SIMPAR","SOMOCER","CIMENTS DE BIZERTE","ESSOUKNA","SANIMED",
    "TPR","SOTIPAPIER","AIR LIQUIDE TSIE","ICF","ALKIMIA","UNIMED","SIPHAT",
    "TAWASOL GP HOLDING","SOTETEL","SOTRAPIL","ASSAD","STIP","TELNET HOLDING","AETECH","TUNISAIR"
]

def norm(s):
    return s.upper().replace(' ','').replace('-','').replace("'",'').replace('.','')

def match_company(raw):
    raw = raw.strip()
    if raw in NAME_MAP: return NAME_MAP[raw]
    rn = norm(raw)
    for c in PDF_COMPANIES:
        if norm(c) == rn: return c
    for c in PDF_COMPANIES:
        cn = norm(c)
        if len(cn) > 3 and (cn in rn or rn in cn): return c
    return None

def parse_pdf(pdf_path):
    prices, variations = {}, {}

    with pdfplumber.open(pdf_path) as pdf:
        # ── TUNINDEX: texte brut page 2 ──
        text2 = pdf.pages[1].extract_text() or ''
        for m in re.findall(r'(1[3-9]\s*\d{3}[,\.]\d{2,3})', text2):
            v = float(m.replace(' ','').replace(',','.'))
            if 13000 < v < 20000:
                prices['TUNINDEX'] = round(v, 2)
                break

        # ── Page de données: cache le texte avant de comparer ──
        data_page = pdf.pages[5]  # page 6 par défaut
        for i, page in enumerate(pdf.pages):
            cached_text = page.extract_text() or ''
            if 'Clôture' in cached_text and 'BIAT' in cached_text and 'SFBT' in cached_text:
                data_page = page
                break

        # ── Extraction par position X ──
        words = data_page.extract_words(x_tolerance=3, y_tolerance=3)
        lines = defaultdict(list)
        for w in words:
            lines[round(w['top'])].append((w['x0'], w['text']))

        # X exact de Clôture
        x_cloture = 1135.0
        for y in sorted(lines.keys()):
            items = sorted(lines[y])
            texts = [t for _,t in items]
            if 'Clôture' in texts:
                for x, t in items:
                    if t == 'Clôture':
                        x_cloture = x
                        break
                break

        x_var = x_cloture + 55.0

        for y in sorted(lines.keys()):
            items = sorted(lines[y])
            texts = [t for _,t in items]
            if not texts: continue

            name_parts = []
            for t in texts:
                if t.startswith('TN') and len(t) > 8: break
                if re.match(r'^[\d,%]+$', t): break
                name_parts.append(t)

            company = match_company(' '.join(name_parts))
            if not company or company in prices: continue

            price = vari = None
            for x, t in items:
                if abs(x - x_cloture) <= 20 and price is None:
                    try:
                        v = float(t.replace(',','.'))
                        if 0.001 < v < 10000: price = round(v, 3)
                    except: pass
                if abs(x - x_var) <= 25 and vari is None:
                    try:
                        v = float(t.replace(',','.').replace('%',''))
                        if -20 <= v <= 20: vari = round(v, 2)
                    except: pass

            if price is not None:
                prices[company] = price
                if vari is not None: variations[company] = vari

    return prices, variations

def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not pdf_path:
        import urllib.request
        # Essayer aujourd'hui et les 3 jours précédents (weekend/férié)
        from datetime import timedelta
        downloaded = False
        for delta in range(4):
            d = (datetime.now() - timedelta(days=delta)).strftime('%Y%m%d')
            url = f"https://www.bvmt.com.tn/sites/default/files/physionomies/pdf/physionomie_boursiere_{d}.pdf"
            try:
                pdf_path = f"physionomie_boursiere_{d}.pdf"
                print(f"Téléchargement: {url}")
                urllib.request.urlretrieve(url, pdf_path)
                downloaded = True
                break
            except Exception as e:
                print(f"  Pas disponible: {d}")
        if not downloaded:
            print("Aucun PDF disponible les 4 derniers jours")
            sys.exit(1)

    if not os.path.exists(pdf_path):
        print(f"Fichier introuvable: {pdf_path}")
        sys.exit(1)

    print(f"Lecture: {pdf_path}")
    prices, variations = parse_pdf(pdf_path)

    n = len(prices) - (1 if 'TUNINDEX' in prices else 0)
    print(f"{n} sociétés + TUNINDEX={prices.get('TUNINDEX','non trouvé')}")
    for c in ["BIAT","BT","AMEN BANK","SFBT","SOTUVER"]:
        print(f"  {c}: {prices.get(c,'?')} ({variations.get(c,'?')}%)")

    missing = [c for c in PDF_COMPANIES if c not in prices]
    if missing: print(f"Manquants ({len(missing)}): {missing}")

    out = 'prices.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({
            "updated_at": datetime.now().strftime('%Y-%m-%d'),
            "source": os.path.basename(pdf_path),
            "count": len(prices),
            "prices": prices,
            "variations": variations
        }, f, ensure_ascii=False, indent=2)

    print(f"\nSauvegarde: {out}")
    print("Dans l'app: Param → Mettre à jour les prix → charger prices.json")

if __name__ == '__main__':
    main()
