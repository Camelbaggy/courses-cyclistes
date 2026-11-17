#!/usr/bin/env python3
"""Table des maillots d'équipes PCM Mod (https://pcmmod.com, « Real Jerseys »), saison par saison -> maillots/pcmmod.json.

Accord des administrateurs de PCM Mod (obtenu par le propriétaire, 17/11/2026) pour lire leurs pages par programme et afficher leurs images
directement depuis leur site (rien n'est téléchargé ni republié ici : seule la table nom / code UCI -> identifiant d'image est stockée).
Crédit affiché : « PCM Mod ». Une page par saison (hommes), une requête toutes les 2 s, identifiant honnête (netutil).

    python tools/pcmmod.py [--saisons 2011-2027] [--sortie maillots/pcmmod]

Sortie (un petit fichier par saison, lu par la page à la demande) : `<sortie>/<année>.json` = [[nom, code UCI | null, slug du nom,
identifiant d'image], …] et `<sortie>/index.json` = {"source": "PCM Mod", "genere", "image": "https://pcmmod.com/img/backup_graph_element/{id}.png",
"saisons": [années]}.
Sections gardées : route (World Tour, Pro Team, Continental, Amateur) ; VTT et cyclo-cross écartés. Une saison illisible garde ses
entrées précédentes (fichier existant) : un échec réseau n'efface rien.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netutil  # noqa: E402
from run_pipeline import parse_saisons  # noqa: E402

URL = "https://pcmmod.com/jersey/realsteams.php?year={annee}&is_femin=0"
IMAGE = "https://pcmmod.com/img/backup_graph_element/{id}.png"
SECTIONS_ROUTE = {"World Tour", "Pro Team", "Continental", "Amateur"}
PAUSE_S = 2.0


def lire_saison(texte):
    """[{n, c, s, i, niv}] des équipes d'une page « Real Jerseys » (fonction pure)."""
    out = []
    # découpe par section (<h2 id="World Tour" …>) puis par maillot (<div class="peloton" title="Nom [CODE]"> … setBackupGraphElement(this, ID))
    morceaux = re.split(r'<h2 id="([^"]*)"', texte)
    for i in range(1, len(morceaux) - 1, 2):
        section, corps = morceaux[i].strip(), morceaux[i + 1]
        if section not in SECTIONS_ROUTE:
            continue
        for titre, ident in re.findall(r'class="peloton" title="([^"]*)".*?setBackupGraphElement\(this,\s*(\d+)\)', corps, re.S):
            titre = html.unescape(titre).strip()
            m = re.fullmatch(r"(.*?)\s*\[([A-Za-z0-9]{2,5})\]", titre)
            nom, code = (m.group(1).strip(), m.group(2).upper()) if m else (titre, None)
            if nom:
                out.append({"n": nom, "c": code, "s": netutil.slugify(nom), "i": int(ident), "niv": section})
    return out


def _tests():
    page = ('<h2 id="World Tour" class="x">World Tour</h2><div class="peloton" title="Ag2r La Mondiale [ALM]"><a><img '
            'onerror="setBackupGraphElement(this, 10381)"></a></div><div class="peloton" title="Bora &amp; Co"><img '
            'onerror="setBackupGraphElement(this, 7)"></div><h2 id="VTT">VTT</h2><div class="peloton" title="Vtt [VTT]"><img '
            'onerror="setBackupGraphElement(this, 9)"></div>')
    r = lire_saison(page)
    assert r == [{"n": "Ag2r La Mondiale", "c": "ALM", "s": "ag2r-la-mondiale", "i": 10381, "niv": "World Tour"},
                 {"n": "Bora & Co", "c": None, "s": "bora-co", "i": 7, "niv": "World Tour"}], r
    print("[OK] pcmmod.py : tests locaux réussis")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--saisons", default="2011-2027")
    ap.add_argument("--sortie", default=os.path.join("maillots", "pcmmod"))
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        _tests()
        return
    os.makedirs(a.sortie, exist_ok=True)
    try:
        with open(os.path.join(a.sortie, "index.json"), encoding="utf-8") as f:
            deja = [str(x) for x in json.load(f).get("saisons") or []]
    except (OSError, ValueError):
        deja = []
    ancien = {y: 1 for y in deja}
    saisons = {}
    for k, annee in enumerate(parse_saisons(a.saisons)):
        if k:
            time.sleep(PAUSE_S)
        texte = netutil.fetch_text(URL.format(annee=annee))
        equipes = lire_saison(texte or "")
        if not equipes:
            print(f"[WARN] [PCMMOD] {annee} : page illisible ou vide, fichier précédent conservé" if str(annee) in ancien else f"[PCMMOD] {annee} : aucune page")
            continue
        saisons[str(annee)] = len(equipes)
        lignes = [[e["n"], e["c"], e["s"], e["i"]] for e in sorted(equipes, key=lambda e: (e["s"], e["i"]))]
        with open(os.path.join(a.sortie, f"{annee}.json"), "w", encoding="utf-8") as f:
            json.dump(lignes, f, ensure_ascii=False, separators=(",", ":"))
        niveaux = {}
        for e in equipes:
            niveaux[e["niv"]] = niveaux.get(e["niv"], 0) + 1
        print(f"[PCMMOD] {annee} : {len(equipes)} maillots {niveaux}")
    toutes = sorted({int(y) for y in list(ancien) + list(saisons)})
    with open(os.path.join(a.sortie, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"source": "PCM Mod", "genere": dt.date.today().isoformat(), "image": IMAGE, "saisons": toutes}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[PCMMOD] {sum(saisons.values())} maillots lus, {len(toutes)} saisons -> {a.sortie}")


if __name__ == "__main__":
    main()
