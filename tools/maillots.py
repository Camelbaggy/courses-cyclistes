#!/usr/bin/env python3
"""Maillots WorldDB (textures Pro Cycling Manager, accord des auteurs) -> `maillots/` publié avec le site.

Les textures d'origine (1200x826, gabarit unique : devant à gauche 134..452 x 0..455, dos à droite, manches en haut, cuissard en bas)
restent dans le dépôt PRIVÉ Camelbaggy/maillots-pcm ; ce script n'en publie qu'une vue de face du buste (sans manches ni cuissard),
en petit (WebP). Il demande Pillow (outil manuel, hors pipeline : la bibliothèque standard ne lit pas le PNG).

    python tools/maillots.py "<dossier Maillots cyclistes>" <equipes/<saison>.json> [--saison 2025] [--sortie maillots]

Fichiers source : `<code>_maillot.png` (équipes, code UCI en minuscules), `<ISO3>_maillot_champion.png` (champions nationaux),
`races/<nom>_maillot_<type>.png` (maillots distinctifs des courses, types time / points / mountain / young…).
Sortie : `equipes/<CODE>.webp`, `nations/<ISO3>.webp`, `courses/<nom>_<type>.webp` et `index.json` :
  {"source": "WorldDB", "saison", "equipes": {CODE: {"nom"?, "slug"?}}, "nations": [ISO3…], "courses": {nom: [types…]}}
`nom` / `slug` = libellé de l'équipe-saison de la saison des maillots portant ce code UCI (unique), à défaut `NOMS_MANUELS`. La page
affiche le maillot d'une équipe-saison de N'IMPORTE QUELLE saison si son libellé a le même slug (même dénomination) et que son
code UCI, quand il est connu, est le même (règle du propriétaire : toute la période de dénomination, tant que le code ne change pas).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netutil  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:                     # outil manuel : Pillow requis
    Image = ImageDraw = None

# Codes dont l'équipe-saison n'a pas de code UCI unique dans nos données (anomalie `code_uci_multiple`), validés par le propriétaire.
NOMS_MANUELS = {"GFC": "Groupama-FDJ"}   # GFC = WorldTeam, CGF = équipe continentale (16/11/2026)

ZONE_AVANT = (134, 0, 452, 400)          # panneau avant, coupé avant le bas du maillot
SILHOUETTE = [(100, 0), (159, 28), (218, 0), (276, 14), (292, 34), (288, 110), (296, 170), (306, 400), (12, 400), (22, 170),
              (30, 110), (26, 34), (42, 14)]
HAUTEUR = 96                             # px (affiché à 34 px dans la liste, plus grand plus tard)
SUR = 4


def buste(chemin):
    src = Image.open(chemin).convert("RGBA")
    if src.size != (1200, 826):
        raise ValueError(f"gabarit inattendu {src.size}")
    p = src.crop(ZONE_AVANT)
    m = Image.new("L", (p.width * SUR, p.height * SUR), 0)
    ImageDraw.Draw(m).polygon([(x * SUR, y * SUR) for x, y in SILHOUETTE], fill=255)
    p.putalpha(m.resize(p.size, Image.LANCZOS))
    p = p.crop(p.getbbox())
    return p.resize((round(p.width * HAUTEUR / p.height), HAUTEUR), Image.LANCZOS)


def ecrire(im, chemin):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    im.save(chemin, "WEBP", quality=82, method=6)


def noms_par_code(equipes):
    par = {}
    for e in equipes.values():
        c = e.get("code_uci")
        if c and not e.get("nationale"):
            par.setdefault(c, set()).add(e["name"])
    out = {c: next(iter(n)) for c, n in par.items() if len(n) == 1}
    out.update(NOMS_MANUELS)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source")
    ap.add_argument("equipes", help="entites/equipes/<saison>.json de la saison des maillots")
    ap.add_argument("--saison", type=int, default=2025)
    ap.add_argument("--sortie", default="maillots")
    a = ap.parse_args()
    if Image is None:
        sys.exit("Pillow requis (pip install pillow)")
    with open(a.equipes, encoding="utf-8") as f:
        noms = noms_par_code(json.load(f))
    idx = {"source": "WorldDB", "saison": a.saison, "equipes": {}, "nations": [], "courses": {}}
    erreurs = []
    for nom in sorted(os.listdir(a.source)):
        chemin = os.path.join(a.source, nom)
        m_eq = re.fullmatch(r"([a-z0-9]{3})_maillot\.png", nom)
        m_na = re.fullmatch(r"([A-Z]{3})_maillot_champion\.png", nom)
        try:
            if m_eq:
                code = m_eq.group(1).upper()
                ecrire(buste(chemin), os.path.join(a.sortie, "equipes", f"{code}.webp"))
                n = noms.get(code)
                idx["equipes"][code] = {"nom": n, "slug": netutil.slugify(n)} if n else {}
            elif m_na:
                ecrire(buste(chemin), os.path.join(a.sortie, "nations", f"{m_na.group(1)}.webp"))
                idx["nations"].append(m_na.group(1))
        except Exception as e:  # noqa: BLE001
            erreurs.append(f"{nom} : {e}")
    dossier_courses = os.path.join(a.source, "races")
    for nom in sorted(os.listdir(dossier_courses)) if os.path.isdir(dossier_courses) else []:
        m = re.fullmatch(r"([a-z0-9]+)_maillot_([a-z]+)\.png", nom)
        if not m:
            continue
        try:
            ecrire(buste(os.path.join(dossier_courses, nom)), os.path.join(a.sortie, "courses", f"{m.group(1)}_{m.group(2)}.webp"))
            idx["courses"].setdefault(m.group(1), []).append(m.group(2))
        except Exception as e:  # noqa: BLE001
            erreurs.append(f"races/{nom} : {e}")
    with open(os.path.join(a.sortie, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    relies = sum(1 for v in idx["equipes"].values() if v)
    print(f"[MAILLOTS] {len(idx['equipes'])} équipes ({relies} reliées à une équipe-saison {a.saison}), {len(idx['nations'])} nations, "
          f"{sum(len(v) for v in idx['courses'].values())} maillots de {len(idx['courses'])} courses ; {len(erreurs)} erreur(s)")
    for e in erreurs:
        print("  [WARN]", e)


if __name__ == "__main__":
    main()
