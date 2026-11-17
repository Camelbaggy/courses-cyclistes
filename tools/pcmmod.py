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
URL_NATIONS = "https://pcmmod.com/jersey/realsnations.php?year={annee}&is_femin=0"
URL_COURSES = "https://pcmmod.com/jersey/leaders.php?year={annee}&is_femin=0"
TYPES_COURSE = {"Time": "gc", "Points": "points", "Mountain": "mountain", "Youth": "youth"}   # type PCM Mod -> classement
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


def lire_nations(texte):
    """[[nom du pays, code drapeau (ISO alpha-2, comme flagcdn), id d'image]] de la page « Real National Jerseys » (fonction pure)."""
    out = []
    for nom, _num, ident, drapeau in re.findall(r'<a title="([^"]*)" href="nation\.php\?id=(\d+)"[^>]*class="blackbox">\s*<img[^>]*'
                                                r'setBackupGraphElement\(this,\s*(\d+)\).*?flags/48x48/([a-z-]+)\.png', texte, re.S):
        out.append([html.unescape(nom).strip(), drapeau, int(ident)])
    return out


def lire_courses(texte):
    """[[id de course PCM Mod, nom de la course, classement (gc / points / mountain / youth), id d'image]] de la page des maillots
    distinctifs (fonction pure) ; les types inconnus (équipes, combativité…) sont écartés."""
    out = []
    blocs = re.split(r'<a href="/race/race\.php\?id=(\d+)&(?:amp;)?year=\d+"', texte)
    for i in range(1, len(blocs) - 1, 2):
        rid, corps = int(blocs[i]), blocs[i + 1].split("</a>")[0]
        for titre, ident in re.findall(r'class="peloton" title="([^"]*)".*?setBackupGraphElement\(this,\s*(\d+)\)', corps, re.S):
            titre = html.unescape(titre).strip()
            nom, _, ty = titre.rpartition(" ")
            if ty in TYPES_COURSE and nom:
                out.append([rid, nom, TYPES_COURSE[ty], int(ident)])
    return out


# Maillots distinctifs : identifiant de course PCM Mod -> clés d'épreuve de NOS données (toutes les dénominations de la même course ; les alias
# d'alias_courses.json sont ajoutés automatiquement). Table MANUELLE, établie le 17/11/2026 à partir des noms PCM Mod et de nos épreuves, cas sûrs
# seulement : courses espoirs, homonymes (Tour Colombia ≠ Vuelta a Colombia) et rapprochements douteux écartés. PCM Mod identifie une course par
# un numéro stable à travers ses changements de nom (Dauphiné / Tour Auvergne-Rhône-Alpes = 12) ; leur page donne les maillots de CHAQUE année.
COURSES_PCM = {
    1: ["tour de france|FRA"], 2: ["la vuelta ciclista a espana|ESP"], 3: ["giro d italia|ITA"], 4: ["baloise belgium tour|BEL"],
    5: ["tour de l ain|FRA"], 6: ["tour des alpes maritimes et du var|FRA", "tour des alpes maritimes|FRA", "tour cycliste international du haut var|FRA",
                                 "tour cycliste international du haut var matin|FRA"],
    7: ["santos tour down under|AUS"], 8: ["paris nice|FRA"], 9: ["abu dhabi tour|UAE", "uae tour|UAE"],
    10: ["tour de la provence|FRA"], 11: ["etoile de besseges tour du gard|FRA"], 12: ["criterium du dauphine|FRA"],
    15: ["volta ciclista a catalunya|ESP"], 16: ["arctic race of norway|NOR"], 17: ["tour of britain|GBR"], 19: ["tour de romandie|SUI"],
    20: ["tirreno adriatico|ITA"], 21: ["volta ao algarve em bicicleta|POR"], 22: ["itzulia basque country|ESP"], 23: ["tour de suisse|SUI"],
    24: ["tour de pologne|POL"], 25: ["renewi tour|BEL"], 26: ["gree tour of guangxi|CHN"], 27: ["zlm tour|NED"],
    28: ["presidential cycling tour of turkiye|TUR", "56 presidential cycling tour of turkey|TUR"], 29: ["tour of the alps|ITA"],
    30: ["amgen tour of california|USA"], 32: ["tour of norway|NOR"],
    33: ["int osterreich rundfahrt tour of austria|AUT", "tour of austria|AUT"], 34: ["postnord danmark rundt tour of denmark|DEN"],
    36: ["tour of oman|OMA"], 37: ["tour de yorkshire|GBR"], 38: ["tour poitou charentes en nouvelle aquitaine|FRA"],
    39: ["voo tour de wallonie|BEL", "ethias tour de wallonie|BEL"], 40: ["tour de hongrie|HUN"], 41: ["baltic chain tour|EST"],
    42: ["tour de normandie|FRA"], 43: ["istarsko proljece istrian spring trophy|CRO"], 44: ["circuit des ardennes|FRA"],
    45: ["tour of mersin|TUR"], 46: ["tour of slovenia|SLO"], 47: ["volta a portugal em bicicleta|POR"], 49: ["dubai tour|UAE"],
    50: ["giro della regione friuli venezia giulia|ITA", "57 giro della regione friuli venezia giulia|ITA", "56 giro della regione friuli venezia giulia|ITA"],
    51: ["okolo slovenska tour de slovaquie|SVK"], 52: ["turul romaniei|ROU"], 53: ["4 jours de dunkerque grand prix des hauts de france|FRA"],
    54: ["cro race|CRO"], 55: ["volta a la comunitat valenciana|ESP"], 57: ["tour international des zibans|ALG"],
    58: ["la tropicale amissa bongo|GAB"], 59: ["vuelta a san juan internacional|ARG", "vuelta a san juan internacional 36 edicion|ARG"],
    60: ["tour of antalya|TUR"], 63: ["tour of mevlana|TUR"], 65: ["sibiu cycling tour|ROU"], 66: ["deutschland tour|GER"],
    67: ["tour alsace|FRA"], 68: ["le tour de bretagne cycliste|FRA"], 69: ["region pays de la loire tour|FRA"], 70: ["tour du loir et cher|FRA"],
    71: ["alpes isere tour|FRA"], 72: ["adriatica ionica race sulle rotte della serenissima|ITA"], 74: ["the larry h miller tour of utah|USA"],
    75: ["herald sun tour|AUS", "jayco herald sun tour|AUS"], 76: ["tour du limousin nouvelle aquitaine|FRA"], 78: ["petronas le tour de langkawi|MAS"],
    79: ["la route d occitanie la depeche du midi|FRA"], 82: ["vuelta asturias julio alvarez mendo|ESP"],
    88: ["vuelta a la region de murcia costa calida|ESP"], 91: ["o gran camino the historical route|ESP"], 92: ["alula tour|KSA"],
    93: ["volta ao alentejo|POR"], 94: ["tour du rwanda|RWA"], 95: ["vuelta independencia nacional rep dom|DOM"],
    98: ["boucles de la mayenne credit mutuel|FRA"], 100: ["tour colombia 2 1|COL"],
    102: ["the princess maha chakri sirindhorn s cup tour of thailand|THA"], 103: ["tour du maroc|MAR"],
    104: ["grande premio internacional beiras e serra da estrela|POR"], 107: ["belgrade banjaluka|BIH"], 108: ["fleche du sud|LUX"],
    109: ["a travers les hauts de france|FRA", "a travers les hauts de france trophee paris arras tour|FRA"], 110: ["tour of albania|ALB"],
    113: ["tour de kumano|JPN"], 114: ["cycling tour of bihor bellotto|ROU"], 115: ["ronde de l oise|FRA"], 116: ["tour de beauce|CAN"],
    117: ["oberosterreichrundfahrt|AUT", "oberosterreich rundfahrt|AUT"], 118: ["kreiz breizh elites|FRA"], 119: ["cambodia bay cycling tour|CAM"],
    122: ["international tour of rhodes|GRE"], 124: ["vuelta a burgos|ESP"], 125: ["vuelta a andalucia ruta ciclista del sol|ESP"],
    126: ["vuelta aragon|ESP"], 127: ["tour of japan|JPN"], 128: ["vuelta ciclista comunidad de madrid|ESP"],
    129: ["in the footsteps of the romans|BUL", "cup doltcini in the footsteps of the romans|BUL", "in the steps of romans|BUL"],
    130: ["tour of bulgaria|BUL"], 131: ["cycling tour of szeklerland|ROU"], 132: ["le tour de savoie mont blanc|FRA"],
    133: ["giro di sicilia tour of sicily|ITA"], 134: ["skoda tour de luxembourg|LUX"], 135: ["czech tour|CZE"], 137: ["tour d eure et loir|FRA"],
    139: ["course cycliste de solidarnosc et des champions olympiques|POL"], 140: ["olympia s tour|NED"], 142: ["colorado classic|USA"],
    144: ["tour of qinghai lake|CHN"], 145: ["settimana internazionale coppi e bartali|ITA"],
    169: ["60 vuelta ciclistica internacional a guatemala|GUA"], 170: ["tour of estonia|EST"], 179: ["tour of sharjah|UAE"],
    211: ["visit south aegean islands|GRE"], 331: ["tour de taiwan|TPE"], 400: ["tour du benin|BEN"], 406: ["tour of hainan|CHN"],
    411: ["new zealand cycle classic|NZL"], 471: ["tour of huangshan|CHN"], 482: ["dookoła mazowsza|POL"], 515: ["tour of kosovo|KOS"],
    519: ["tour of poyang lake|CHN"], 615: ["trans himalaya cycling race|CHN"], 617: ["tour of istanbul|TUR"], 648: ["tour of taihu lake|CHN"],
    670: ["gp internacional torres vedras trofeu joaquim agostinho|POR"], 984: ["tour de banyuwangi ijen|INA", "international tour de banyuwangi ijen|INA"],
    1008: ["tour of salalah|OMA"], 1013: ["tour du cameroun|CMR"], 1053: ["grand prix chantal biya|CMR"], 1065: ["tour of shanghai|CHN"],
    1090: ["tour de gyeongnam|KOR"], 1105: ["tour of route salvation|TUR", "tour of routhe salvation|TUR"], 1106: ["il giro d abruzzo|ITA"],
    1338: ["okolo jiznich cech tour of south bohemia|CZE"], 1397: ["volta ciclistica de santa catarina|BRA"], 1403: ["tour of iran azarbaijan|IRI"],
    1406: ["tour de kyushu|JPN"], 1409: ["tour cycliste international de la guadeloupe|FRA"], 1426: ["nibc tour of holland|NED"],
    1427: ["pune grand tour|IND"], 1470: ["tour of mentougou|CHN", "tour of mentougou international road cycling race|CHN"], 1479: ["tour de serbie|SRB"],
}


def table_epreuves(chemin_index):
    """{clé d'édition BRUTE: id PCM} (toutes les dénominations + sources d'alias) et {clé canonique: id PCM} ; erreurs (clés inconnues)."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import collector
    with open(chemin_index, encoding="utf-8") as f:
        connues = {c["k"] for c in json.load(f)}
    alias = collector.charger_alias(collector.ALIAS_COURSES)
    brut, canon, erreurs = {}, {}, []
    for rid, cles in sorted(COURSES_PCM.items()):
        for k in cles:
            if k not in connues and k not in alias:
                erreurs.append(f"clé inconnue pour la course PCM {rid} : {k}")
                continue
            c = alias.get(k, k)
            for b in [k, c] + [s for s, v in alias.items() if v == c]:
                if brut.get(b, rid) != rid:
                    erreurs.append(f"clé {b} reliée à deux courses PCM : {brut[b]} et {rid}")
                brut[b] = rid
            canon[c] = rid
    return brut, canon, erreurs


def _tests():
    page = ('<h2 id="World Tour" class="x">World Tour</h2><div class="peloton" title="Ag2r La Mondiale [ALM]"><a><img '
            'onerror="setBackupGraphElement(this, 10381)"></a></div><div class="peloton" title="Bora &amp; Co"><img '
            'onerror="setBackupGraphElement(this, 7)"></div><h2 id="VTT">VTT</h2><div class="peloton" title="Vtt [VTT]"><img '
            'onerror="setBackupGraphElement(this, 9)"></div>')
    nat = ('<a title="Andorra" href="nation.php?id=20" style="w" class="blackbox"> <img onerror="setBackupGraphElement(this, 126433)" src=x />'
           ' <h3><span class="country-flag"><img src="https://pcmmod.com/img/flags/48x48/ad.png" /></span>Andorra </h3> </a>')
    assert lire_nations(nat) == [["Andorra", "ad", 126433]], lire_nations(nat)
    cou = ('<a href="/race/race.php?id=1&year=2026" class="blackbox"><div class="peloton" title="Tour de France Time"><img '
           'onerror="setBackupGraphElement(this, 170414)"></div><div class="peloton" title="Tour de France Team"><img '
           'onerror="setBackupGraphElement(this, 5)"></div></a><a href="/race/race.php?id=12&amp;year=2026" class="blackbox"><div class="peloton" '
           'title="Giro d\'Italia Youth"><img onerror="setBackupGraphElement(this, 7)"></div></a>')
    assert lire_courses(cou) == [[1, "Tour de France", "gc", 170414], [12, "Giro d'Italia", "youth", 7]], lire_courses(cou)
    r = lire_saison(page)
    assert r == [{"n": "Ag2r La Mondiale", "c": "ALM", "s": "ag2r-la-mondiale", "i": 10381, "niv": "World Tour"},
                 {"n": "Bora & Co", "c": None, "s": "bora-co", "i": 7, "niv": "World Tour"}], r
    print("[OK] pcmmod.py : tests locaux réussis")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--saisons", default="2011-2027")
    ap.add_argument("--sortie", default=os.path.join("maillots", "pcmmod"))
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--epreuves", help="entites/courses/index.json : écrit seulement <sortie>/epreuves.json (table manuelle COURSES_PCM)")
    a = ap.parse_args()
    if a.test:
        _tests()
        return
    if a.epreuves:
        brut, canon, erreurs = table_epreuves(a.epreuves)
        # maillots les plus récents de chaque course reliée (infobox de la page épreuve) : {id PCM: [année, {classement: id d'image}]}
        dernier = {}
        dossier = os.path.join(a.sortie, "courses")
        for f in sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []:
            if not f[:-5].isdigit():
                continue
            annee = int(f[:-5])
            with open(os.path.join(dossier, f), encoding="utf-8") as fh:
                for rid, _nom, cl, ident in json.load(fh):
                    if rid in COURSES_PCM and (str(rid) not in dernier or dernier[str(rid)][0] <= annee):
                        if str(rid) not in dernier or dernier[str(rid)][0] < annee:
                            dernier[str(rid)] = [annee, {}]
                        dernier[str(rid)][1][cl] = ident
        with open(os.path.join(a.sortie, "epreuves.json"), "w", encoding="utf-8") as f:
            json.dump({"brut": brut, "canon": canon, "dernier": dernier}, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        print(f"[PCMMOD] épreuves : {len(COURSES_PCM)} courses PCM, {len(brut)} clés d'édition, {len(canon)} épreuves ; {len(erreurs)} erreur(s)")
        for e in erreurs:
            print("  [WARN]", e)
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
    # maillots distinctifs : un fichier par saison (`courses/<année>.json`)
    # la page des nations ne dépend pas de l'année (tenues actuelles) : un seul fichier `nations.json`
    time.sleep(PAUSE_S)
    nations = lire_nations(netutil.fetch_text(URL_NATIONS.format(annee=max(parse_saisons(a.saisons)))) or "")
    if nations:
        with open(os.path.join(a.sortie, "nations.json"), "w", encoding="utf-8") as f:
            json.dump(nations, f, ensure_ascii=False, separators=(",", ":"))
        print(f"[PCMMOD] nations : {len(nations)} tenues")
    rubriques = {"nations": bool(nations) or os.path.exists(os.path.join(a.sortie, "nations.json"))}
    for nom, url, lire in (("courses", URL_COURSES, lire_courses),):
        d = os.path.join(a.sortie, nom)
        os.makedirs(d, exist_ok=True)
        lues = sorted(int(f[:-5]) for f in os.listdir(d) if f[:-5].isdigit())
        for annee in parse_saisons(a.saisons):
            time.sleep(PAUSE_S)
            lignes = lire(netutil.fetch_text(url.format(annee=annee)) or "")
            if not lignes:
                print(f"[PCMMOD] {nom} {annee} : page vide ou illisible (fichier précédent conservé s'il existe)")
                continue
            with open(os.path.join(d, f"{annee}.json"), "w", encoding="utf-8") as f:
                json.dump(lignes, f, ensure_ascii=False, separators=(",", ":"))
            lues = sorted(set(lues) | {annee})
            print(f"[PCMMOD] {nom} {annee} : {len(lignes)} maillots")
        rubriques[nom] = lues
    with open(os.path.join(a.sortie, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"source": "PCM Mod", "genere": dt.date.today().isoformat(), "image": IMAGE, "saisons": toutes,
                   "nations": rubriques["nations"], "courses": rubriques.get("courses", [])}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[PCMMOD] {sum(saisons.values())} maillots lus, {len(toutes)} saisons -> {a.sortie}")


if __name__ == "__main__":
    main()
