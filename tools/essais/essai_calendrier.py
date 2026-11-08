#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau du calendrier prévisionnel : Wikipédia (wikipedia_cal.py) + manches FDJ de la LNC (lnc.get_fdj_calendar).
today = 2026-11-08 : saisons 2026 et 2027 ; détail par page et par catégorie pour 2027."""
import collections
import datetime
import re
import sys

sys.path.insert(0, ".")
import lnc  # noqa: E402
import netutil  # noqa: E402
import wikipedia_cal as wc  # noqa: E402

TODAY = datetime.date(2026, 11, 8)
HOTES = collections.Counter()
_fetch_text = netutil.fetch_text


def _compte(url, *a, **k):
    HOTES[netutil.urllib.parse.urlparse(url).netloc] += 1
    return _fetch_text(url, *a, **k)


netutil.fetch_text = _compte


def diag_pages(annee):
    pages = wc.fetch_pages(annee)
    print(f"\n#### Pages Wikipédia {annee} obtenues : {len(pages)} / {len(wc.CALENDAR_PAGES) + len(wc.CHAMP_PAGES)}")
    for titre in [p.format(y=annee) for p in wc.CALENDAR_PAGES + list(wc.CHAMP_PAGES)]:
        wt = pages.get(titre)
        print(f"  {'OK ' if wt else 'ABS'} {titre}" + (f" ({len(wt)} car.)" if wt else ""))
    for titre in [p.format(y=annee) for p in wc.CALENDAR_PAGES]:
        wt = pages.get(titre)
        if not wt:
            continue
        tabs = wc.parse_tables(wt)
        print(f"\n--- {titre} : {len(tabs)} tableaux ---")
        for k, t in enumerate(tabs[:40]):
            print(f"  [{k}] sections={t['headings']} en-têtes={t['headers']} lignes={len(t['rows'])}")
        for k, t in enumerate(tabs[:2]):
            for cells in t["rows"][:3]:
                print(f"    brut[{k}] : {[c[:70] for c in cells]}")
    for titre in [p.format(y=annee) for p in wc.CHAMP_PAGES]:
        if pages.get(titre):
            print(f"\n--- début de {titre} ---\n{pages[titre][:900]}")
    return pages


def main():
    annee = 2027
    pages = diag_pages(annee)
    par_page = wc.parse_pages(annee, pages)
    print(f"\n#### Courses par page et catégorie ({annee})")
    for titre, cs in par_page.items():
        cats = collections.Counter(c["category"] or "?" for c in cs)
        print(f"  {titre} : {len(cs)} courses, par catégorie {dict(cats)}")
        for c in cs[:3]:
            print("     ex.", c)
    toutes = wc.list_calendar(annee)
    print(f"\nTotal {annee} dédoublonné : {len(toutes)} ; par catégorie {dict(collections.Counter(c['category'] or '?' for c in toutes))}")
    print("Par pays (top 12) :", collections.Counter(c["country"] or "?" for c in toutes).most_common(12))

    print("\n#### Contrôles de dates connues")
    def cherche(motif):
        return [c for c in toutes if re.search(motif, c["name"], re.I)]
    for motif, att in [("Tour Down Under", ("2027-01-19", "2027-01-24")), ("^Tour de France$", ("2027-07-02", "2027-07-25"))]:
        trouve = cherche(motif)
        print(f"  {motif} : {[(c['start_date'], c['end_date']) for c in trouve]} attendu {att} ->",
              "OK" if any((c["start_date"], c["end_date"]) == att for c in trouve) else "ÉCART")

    print("\n#### LNC FDJ United Series")
    for a in (2026, 2027):
        f = lnc.get_fdj_calendar(a)
        print(f"  {a} : {len(f)} manches", [(r['date'], r['name']) for r in f][:20])
    diag_lnc()

    print(f"\n#### list_upcoming(today={TODAY})")
    up = wc.list_upcoming(TODAY)
    print(f"{len(up)} courses suivies à venir ; par catégorie {dict(collections.Counter(c['category'] for c in up))}")
    print("20 prochaines :")
    for c in up[:20]:
        print(f"  {c['start_date']} → {c['end_date']} {c['category']:6} {str(c['uci_class']):7} {str(c['country']):4} {c['name']}")
    print("Françaises (pays FRA) :")
    for c in up:
        if c["country"] == "FRA":
            print(f"  {c['start_date']} {c['category']:6} {str(c['uci_class']):7} {c['name']}")
    print("Championnats / FDJ :")
    for c in up:
        if c["category"] in ("Champ.", "FDJ"):
            print(f"  {c['start_date']} → {c['end_date']} {c['category']:6} {str(c['uci_class']):6} {c['country']} {c['name']} [{c['source']}]")
    champs = ("name", "country", "flag", "uci_class", "category", "start_date", "end_date")
    print("Lignes incomplètes (calendrier brut 2027) :")
    inc = [c for c in toutes if any(c.get(k) is None for k in champs)]
    for c in inc[:40]:
        print("  manque", [k for k in champs if c.get(k) is None], c)
    print(f"  ({len(inc)} incomplètes sur {len(toutes)})")
    print("Lignes incomplètes parmi les suivies :", [c['name'] for c in up if any(c.get(k) is None for k in champs)][:30])
    print(f"\nRequêtes Wikipédia (API) : {wc.REQUESTS} ; requêtes HTTP par hôte : {dict(HOTES)}")


def diag_lnc():
    """Où la LNC publie-t-elle son calendrier ? robots.txt, liens du site, lignes de la page FDJ United Series."""
    rob = netutil.fetch_text(lnc.BASE + "/robots.txt") or ""
    print("  robots.txt Disallow :", re.findall(r"(?im)^disallow:\s*(\S+)", rob)[:40])
    for chemin in ["/fdj-united-series"] + [p for p in lnc.CALENDAR_PATHS if p != "/fdj-united-series"]:
        page = netutil.fetch_text(lnc.BASE + chemin)
        print(f"  {chemin} : {'absent' if not page else str(len(page)) + ' car.'}")
        if not page:
            continue
        liens = sorted(set(re.findall(r'href="([^"#]+)"', page)))
        print("    liens utiles :", [l for l in liens if re.search(r"calend|agenda|course|saison|resultat|fdj|2027|2026", l, re.I)][:40])
        lignes = lnc._lignes(page)
        autour = [i for i, l in enumerate(lignes) if re.search(r"2027|calendrier|prochaine", l, re.I)]
        for i in autour[:12]:
            print("    ~", lignes[max(0, i - 1):i + 3])


if __name__ == "__main__":
    main()
