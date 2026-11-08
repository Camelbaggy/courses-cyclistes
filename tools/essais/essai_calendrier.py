#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau du calendrier prévisionnel : Wikipédia anglaise + française (wikipedia_cal.py) et manches FDJ de la LNC.
today = date du jour : saisons today.year et (à partir d'octobre) today.year + 1. Affiche, par page (EN / FR) et par
catégorie, le nombre de courses lues, l'union dédoublonnée, les courses françaises à venir, les 10 prochaines ProSeries,
les lignes incomplètes, les contrôles de dates connues et la recherche de doublons EN / FR."""
import collections
import datetime
import re
import sys

sys.path.insert(0, ".")
import lnc  # noqa: E402
import netutil  # noqa: E402
import selection  # noqa: E402
import wikipedia_cal as wc  # noqa: E402

TODAY = datetime.date.today()
CHAMPS = ("name", "country", "flag", "uci_class", "category", "start_date", "end_date")
# (motif du nom, début, fin) : dates connues de la saison 2027 (à compléter au fil des publications officielles)
DATES_CONNUES = [("Tour Down Under", "2027-01-19", "2027-01-24"), ("^Tour de France$", "2027-07-02", "2027-07-25")]


def cats(cs):
    return dict(collections.Counter(c["category"] or "?" for c in cs))


def diag_pages(annee):
    print(f"\n#### Pages {annee}")
    en, fr = wc.fetch_pages(annee), wc.fetch_pages_fr(annee)
    for lang, pages, modeles in (("EN", en, wc.CALENDAR_PAGES + list(wc.CHAMP_PAGES)), ("FR", fr, wc.CALENDAR_PAGES_FR)):
        for m in modeles:
            t = m.format(y=annee)
            print(f"  {lang} {'OK ' if pages.get(t) else 'ABS'} {t}" + (f" ({len(pages[t])} car.)" if pages.get(t) else ""))
    for lang, pages, modeles in (("EN", en, wc.CALENDAR_PAGES), ("FR", fr, wc.CALENDAR_PAGES_FR)):
        for m in modeles:
            t = m.format(y=annee)
            if not pages.get(t):
                continue
            tabs = wc.parse_tables(pages[t])
            print(f"\n--- {lang} {t} : {len(tabs)} tableaux ---")
            for k, tab in enumerate(tabs[:25]):
                print(f"  [{k}] sections={tab['headings']} en-têtes={tab['headers']} lignes={len(tab['rows'])}")
            for k, tab in enumerate(tabs[:2]):
                for cells in tab["rows"][:3]:
                    print(f"    brut[{k}] : {[c[:70] for c in cells]}")
            if not tabs:
                print("  (aucun tableau) début :", pages[t][:600].replace("\n", " | "))
    return en, fr


def compte_par_page(annee, en, fr):
    print(f"\n#### Courses lues par page et catégorie ({annee})")
    pe, pf = wc.parse_pages(annee, en), wc.parse_pages_fr(annee, fr)
    for lang, par_page in (("EN", pe), ("FR", pf)):
        for titre, cs in par_page.items():
            print(f"  {lang} {titre} : {len(cs)} courses, catégories {cats(cs)}, classes "
                  f"{dict(collections.Counter(c['uci_class'] or '?' for c in cs))}")
            print("     sans pays :", [c["name"] for c in cs if not c["country"]][:15])
            for c in cs[:3]:
                print("     ex.", c)
    return pe, pf


def doublons_en_fr(pe, pf):
    """Même course dans les deux langues : doit être fusionnée par list_calendar. Affiche les paires et les restes."""
    en = [c for cs in pe.values() for c in cs]
    fr = [c for cs in pf.values() for c in cs]
    paires, fr_seules = 0, []
    for f in fr:
        if any(wc._jours_proches(e["start_date"], f["start_date"]) and selection._noms_proches(e["name"], f["name"])
               for e in en):
            paires += 1
        else:
            fr_seules.append(f)
    print(f"  {len(en)} lignes EN, {len(fr)} lignes FR : {paires} FR retrouvées en EN (par nom proche), "
          f"{len(fr_seules)} FR sans équivalent de nom en EN")
    for f in fr_seules[:25]:
        meme = [e["name"] for e in en if (e["start_date"], e["end_date"], e["country"], e["uci_class"])
                == (f["start_date"], f["end_date"], f["country"], f["uci_class"]) and f["country"]]
        print(f"    FR seule : {f['start_date']} {f['uci_class']} {f['country']} {f['name']}"
              + (f"  ~ même clé en EN : {meme}" if meme else ""))


def verifie_doublons(liste, etiquette):
    """Après fusion : aucune paire de courses à ± 1 jour avec des noms proches, ni même clé dates/pays/classe."""
    bad = []
    for i, a in enumerate(liste):
        for b in liste[i + 1:]:
            if wc._jours_proches(a["start_date"], b["start_date"]) and (
                    selection._noms_proches(a["name"], b["name"])
                    or (wc._cle_exacte(a) and wc._cle_exacte(a) == wc._cle_exacte(b))):
                bad.append((a["name"], b["name"], a["start_date"]))
    print(f"  {etiquette} : {len(bad)} doublons restants" + (f" -> {bad[:15]}" if bad else " OK"))


def main():
    print(f"today = {TODAY}")
    annees = [TODAY.year] + ([TODAY.year + 1] if TODAY.month >= 10 else [])
    toutes_par_annee = {}
    for annee in annees:
        en, fr = diag_pages(annee)
        pe, pf = compte_par_page(annee, en, fr)
        print(f"\n#### Doublons EN / FR ({annee})")
        doublons_en_fr(pe, pf)
        toutes = wc.list_calendar(annee)
        toutes_par_annee[annee] = toutes
        print(f"\n  Union dédoublonnée {annee} : {len(toutes)} courses ; catégories {cats(toutes)} ; "
              f"sources {dict(collections.Counter(c['source'] for c in toutes))}")
        print("  Par pays (top 12) :", collections.Counter(c["country"] or "?" for c in toutes).most_common(12))
        verifie_doublons(toutes, f"union {annee}")
        print("  Contrôles de dates connues :")
        for motif, d, f in DATES_CONNUES:
            if not d.startswith(str(annee)):
                continue
            trouve = [c for c in toutes if re.search(motif, c["name"], re.I)]
            print(f"    {motif} : {[(c['start_date'], c['end_date'], c['source']) for c in trouve]} attendu {(d, f)} ->",
                  "OK" if any((c["start_date"], c["end_date"]) == (d, f) for c in trouve) else "ÉCART")
        inc = [c for c in toutes if any(c.get(k) is None for k in CHAMPS)]
        print(f"  Lignes incomplètes (union {annee}) : {len(inc)} sur {len(toutes)}")
        for c in inc[:40]:
            print("    manque", [k for k in CHAMPS if c.get(k) is None], c)

    print("\n#### LNC FDJ United Series")
    for a in annees:
        f = lnc.get_fdj_calendar(a)
        print(f"  {a} : {len(f)} manches", [(r['date'], r['name']) for r in f][:20])

    print(f"\n#### list_upcoming(today={TODAY})")
    up = wc.list_upcoming(TODAY)
    print(f"{len(up)} courses suivies à venir ; catégories {cats(up)} ; "
          f"sources {dict(collections.Counter(c['source'] for c in up))}")
    verifie_doublons(up, "suivies à venir")
    print("Courses françaises à venir (pays FRA) :")
    for c in up:
        if c["country"] == "FRA":
            print(f"  {c['start_date']} → {c['end_date']} {c['category']:6} {str(c['uci_class']):7} {c['name']} [{c['source']}]")
    print("10 prochaines ProSeries :")
    for c in [c for c in up if c["category"] == "Pro"][:10]:
        print(f"  {c['start_date']} → {c['end_date']} {str(c['uci_class']):7} {str(c['country']):4} {c['name']} [{c['source']}]")
    print("20 prochaines (toutes catégories) :")
    for c in up[:20]:
        print(f"  {c['start_date']} → {c['end_date']} {c['category']:6} {str(c['uci_class']):7} {str(c['country']):4} {c['name']}")
    print("Championnats / FDJ :")
    for c in up:
        if c["category"] in ("Champ.", "FDJ"):
            print(f"  {c['start_date']} → {c['end_date']} {c['category']:6} {str(c['uci_class']):6} {c['country']} {c['name']} [{c['source']}]")
    print("Lignes incomplètes parmi les suivies :")
    for c in up:
        if any(c.get(k) is None for k in CHAMPS):
            print("  manque", [k for k in CHAMPS if c.get(k) is None], c["name"], c["start_date"], c["source"])
    print(f"\nRequêtes Wikipédia (API, EN + FR) : {wc.REQUESTS}")


if __name__ == "__main__":
    main()
