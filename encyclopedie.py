#!/usr/bin/env python3
"""Encyclopédie du cyclisme (étape E1a) : fichiers d'entités générés à partir des archives et du Calendrier.

`construire(archives_dir, data_dir)` lit TOUTES les saisons connues :
- archives : `<archives_dir>/<année>/races/*.json` (+ `riders.json`, `ranking.json`) ;
- Calendrier : `<data_dir>/races/*.json` (saison = champ `season`, à défaut `index-<année>.json`), `riders-<année>.json`,
  `ranking.json` ;
et écrit dans `<archives_dir>/entites/` (JSON compact, seulement si le contenu change, ordre déterministe) :

    coureurs/<lettre>.json     {rider_id: fiche}           lettre = 1re lettre a-z du rider_id canonique, sinon « _ »
    equipes/<année>.json       {id d'équipe-saison: fiche} + equipes/index.json (liste compacte) + equipes/lignees.json (QID -> lignée Wikidata)
    courses/<lettre>.json      {clé d'édition: fiche}      lettre = 1re lettre a-z de la clé, sinon « _ »
    coureurs_historiques/<NN>.json  {« wd-Q… »: fiche légère}  coureurs d'avant nos données (palmarès Wikidata) ; NN = 2 derniers chiffres du QID
    saisons/<année>.json       statistiques de la saison
    pays.json                  par code ISO3 (UCI / CIO)
    recherche/<lettre>.json    entrées de recherche indexées par la 1re lettre de CHAQUE mot du libellé
    index.json                 compteurs, saisons couvertes, sources, limites

Schéma détaillé : docs/SPEC.md §4.4. Règles (zéro hallucination) :
- tout vient des fiches de course ; seules valeurs dérivées : sommes, comptages, tris (calculs déterministes) ;
- une clé absente reste absente (jamais de valeur de substitution) ; `code_uci` d'une équipe-saison = `TeamCode` UNIQUE des coureurs classés
  de la saison dont le libellé d'équipe a le même slug (plusieurs codes : absent + anomalie) ;
  `historique` des courses, `palmares_historique` des coureurs et `coureurs_historiques/` viennent du cache `entites/historique/` (module
  historique : palmarès Wikidata, statuts ok / non_attribue / conflit / inconnu, jamais tranchés) et ne couvrent QUE les années absentes de nos éditions UCI ; `lignee` (QID Wikidata), `wikidata` d'un
  coureur et `equipes/lignees.json` viennent du CACHE `entites/wikidata/` (module wikidata, E1b : rapprochements stricts, jamais devinés) ;
- identités : `rider_id` exact + `alias_coureurs.json` (même règle de contradiction que `collector.construire_carrieres`) ;
  courses : `collector.cle_edition` + `alias_courses.json` ; jamais de rapprochement flou ;
- les statistiques d'une saison sont recalculées course par course avec les fonctions de `riders.py` (mêmes
  définitions que `riders.json`, dont elles sont vérifiées en fin de génération : voir `rapport["coherence"]`).

Traitement course par course : une fiche de course (≈ 100 Ko) est chargée, réduite à ce qui est utile, puis libérée.
Seuls les cumuls (coureurs, équipes de la saison en cours de traitement, courses) restent en mémoire.

    python encyclopedie.py --test
    python encyclopedie.py <archives_dir> <data_dir> [--sortie DIR]
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import collector
import historique
import netutil
import riders
import uci
import wikidata

TOP = 30                          # saisons : taille des classements (équipes, coureurs)
TOP_PAYS = 10                     # pays : meilleurs coureurs
FINAUX_PODIUM = 3

# --------------------------------------------------------------------------- grands tours
# Clés d'édition EXACTES (collector.cle_edition après alias) des trois grands tours ; jamais de motif flou : « Tour de
# France Saitama Criterium » (autre clé, course d'un jour) n'en fait pas partie. Les deux premières variantes de la
# Vuelta sont celles présentes dans editions.json (le nom UCI a changé de casse, pas de clé) ; les suivantes sont des
# graphies plausibles, absentes des données actuelles (listées pour les saisons 2011-2018 en cours de collecte).
GRANDS_TOURS = {
    "tour": ("tour de france|FRA",),
    "giro": ("giro d italia|ITA",),
    "vuelta": ("la vuelta ciclista a espana|ESP", "vuelta a espana|ESP", "la vuelta a espana|ESP"),
}
# Classes UCI d'un grand tour (2.UWT depuis 2015 ; les autres libellés historiques de DataRide par prudence).
CLASSES_GRAND_TOUR = ("2.UWT", "2.WT", "2.HC", "2.HIS", "2.CH")
_GT_PAR_CLE = {cle: gt for gt, cles in GRANDS_TOURS.items() for cle in cles}

# --------------------------------------------------------------------------- pays
# code UCI / CIO -> (nom français, nom anglais tel que l'UCI l'écrit dans les libellés d'équipe, autres graphies).
# Sert à (1) afficher un nom, (2) reconnaître une SÉLECTION NATIONALE : libellé d'équipe égal (normalisé) au nom du pays
# de TOUS ses coureurs de la saison. Un code absent de la table reste affiché par son code seul.
PAYS_NOMS: Dict[str, Tuple[str, ...]] = {
    "AFG": ("Afghanistan", "Afghanistan"), "AIA": ("Anguilla", "Anguilla"), "ALB": ("Albanie", "Albania"),
    "ALG": ("Algérie", "Algeria"), "AND": ("Andorre", "Andorra"), "ANG": ("Angola", "Angola"),
    "ANT": ("Antigua-et-Barbuda", "Antigua and Barbuda"), "ARG": ("Argentine", "Argentina"),
    "ARM": ("Arménie", "Armenia"), "ARU": ("Aruba", "Aruba"), "AUS": ("Australie", "Australia"),
    "AUT": ("Autriche", "Austria"), "AZE": ("Azerbaïdjan", "Azerbaijan"), "BAH": ("Bahamas", "Bahamas"),
    "BAN": ("Bangladesh", "Bangladesh"), "BAR": ("Barbade", "Barbados"), "BDI": ("Burundi", "Burundi"),
    "BEL": ("Belgique", "Belgium"), "BEN": ("Bénin", "Benin"), "BER": ("Bermudes", "Bermuda"),
    "BHU": ("Bhoutan", "Bhutan"), "BIH": ("Bosnie-Herzégovine", "Bosnia and Herzegovina"),
    "BIZ": ("Belize", "Belize"), "BLR": ("Biélorussie", "Belarus"), "BOL": ("Bolivie", "Bolivia"),
    "BOT": ("Botswana", "Botswana"), "BRA": ("Brésil", "Brazil"), "BRN": ("Bahreïn", "Bahrain"),
    "BRU": ("Brunei", "Brunei"), "BUL": ("Bulgarie", "Bulgaria"), "BUR": ("Burkina Faso", "Burkina Faso"),
    "CAM": ("Cambodge", "Cambodia"), "CAN": ("Canada", "Canada"), "CAY": ("Îles Caïmans", "Cayman Islands"),
    "CGO": ("Congo", "Congo", "Republic of the Congo"), "CHA": ("Tchad", "Chad"), "CHI": ("Chili", "Chile"),
    "CHN": ("Chine", "China"), "CIV": ("Côte d'Ivoire", "Cote D'ivoire", "Ivory Coast"),
    "CMR": ("Cameroun", "Cameroon"), "COD": ("RD Congo", "DRC Congo", "Democratic Republic of the Congo"),
    "COL": ("Colombie", "Colombia"), "COM": ("Comores", "Comoros"), "CPV": ("Cap-Vert", "Cape Verde"),
    "CRC": ("Costa Rica", "Costa Rica"), "CRO": ("Croatie", "Croatia"), "CUB": ("Cuba", "Cuba"),
    "CUR": ("Curaçao", "Curacao"), "CYP": ("Chypre", "Cyprus"), "CZE": ("Tchéquie", "Czechia", "Czech Republic"),
    "DEN": ("Danemark", "Denmark"), "DJI": ("Djibouti", "Djibouti"), "DMA": ("Dominique", "Dominica"),
    "DOM": ("République dominicaine", "Dominican Republic"), "ECU": ("Équateur", "Ecuador"),
    "EGY": ("Égypte", "Egypt"), "ERI": ("Érythrée", "Eritrea"), "ESA": ("Salvador", "El Salvador"),
    "ESP": ("Espagne", "Spain"), "EST": ("Estonie", "Estonia"), "ETH": ("Éthiopie", "Ethiopia"),
    "FIJ": ("Fidji", "Fiji"), "FIN": ("Finlande", "Finland"), "FRA": ("France", "France"),
    "GAB": ("Gabon", "Gabon"), "GAM": ("Gambie", "Gambia"), "GBR": ("Grande-Bretagne", "Great Britain"),
    "GEO": ("Géorgie", "Georgia"), "GER": ("Allemagne", "Germany"), "GHA": ("Ghana", "Ghana"),
    "GRE": ("Grèce", "Greece"), "GRN": ("Grenade", "Grenada"), "GUA": ("Guatemala", "Guatemala"),
    "GUI": ("Guinée", "Guinea"), "GUM": ("Guam", "Guam"), "GUY": ("Guyana", "Guyana"), "HAI": ("Haïti", "Haiti"),
    "HKG": ("Hong Kong", "Hong Kong, China", "Hong Kong"), "HON": ("Honduras", "Honduras"),
    "HUN": ("Hongrie", "Hungary"), "INA": ("Indonésie", "Indonesia"), "IND": ("Inde", "India"),
    "IRI": ("Iran", "Iran"), "IRL": ("Irlande", "Ireland"), "IRQ": ("Irak", "Iraq"), "ISL": ("Islande", "Iceland"),
    "ISR": ("Israël", "Israel"), "ITA": ("Italie", "Italy"), "IVB": ("Îles Vierges britanniques", "British Virgin Islands"),
    "JAM": ("Jamaïque", "Jamaica"), "JOR": ("Jordanie", "Jordan"), "JPN": ("Japon", "Japan"),
    "KAZ": ("Kazakhstan", "Kazakhstan"), "KEN": ("Kenya", "Kenya"), "KGZ": ("Kirghizistan", "Kyrgyzstan"),
    "KOR": ("Corée du Sud", "Korea", "South Korea"), "KOS": ("Kosovo", "Kosovo"), "KSA": ("Arabie saoudite", "Saudi Arabia"),
    "KUW": ("Koweït", "Kuwait"), "LAO": ("Laos", "Laos"), "LAT": ("Lettonie", "Latvia"),
    "LBA": ("Libye", "Libya"), "LBN": ("Liban", "Lebanon"), "LBR": ("Libéria", "Liberia"), "LCA": ("Sainte-Lucie", "Saint Lucia"),
    "LES": ("Lesotho", "Lesotho"), "LIE": ("Liechtenstein", "Liechtenstein"), "LTU": ("Lituanie", "Lithuania"),
    "LUX": ("Luxembourg", "Luxembourg"), "MAC": ("Macao", "Macao, China", "Macau"), "MAD": ("Madagascar", "Madagascar"),
    "MAR": ("Maroc", "Morocco"), "MAS": ("Malaisie", "Malaysia"), "MDA": ("Moldavie", "Moldova"),
    "MEX": ("Mexique", "Mexico"), "MGL": ("Mongolie", "Mongolia"), "MKD": ("Macédoine du Nord", "North Macedonia"),
    "MLI": ("Mali", "Mali"), "MLT": ("Malte", "Malta"), "MNE": ("Monténégro", "Montenegro"), "MON": ("Monaco", "Monaco"),
    "MOZ": ("Mozambique", "Mozambique"), "MRI": ("Maurice", "Mauritius"), "MYA": ("Birmanie", "Myanmar"),
    "NAM": ("Namibie", "Namibia"), "NCA": ("Nicaragua", "Nicaragua"), "NED": ("Pays-Bas", "Netherlands"),
    "NEP": ("Népal", "Nepal"), "NGR": ("Nigeria", "Nigeria"), "NIG": ("Niger", "Niger"), "NOR": ("Norvège", "Norway"),
    "NZL": ("Nouvelle-Zélande", "New Zealand"), "OMA": ("Oman", "Oman"), "PAK": ("Pakistan", "Pakistan"),
    "PAN": ("Panama", "Panama"), "PAR": ("Paraguay", "Paraguay"), "PER": ("Pérou", "Peru"), "PHI": ("Philippines", "Philippines"),
    "PLE": ("Palestine", "Palestine"), "PNG": ("Papouasie-Nouvelle-Guinée", "Papua New Guinea"), "POL": ("Pologne", "Poland"),
    "POR": ("Portugal", "Portugal"), "PRK": ("Corée du Nord", "North Korea"), "PUR": ("Porto Rico", "Puerto Rico"),
    "QAT": ("Qatar", "Qatar"), "REF": ("Équipe des réfugiés", "Refugee Team"), "ROU": ("Roumanie", "Romania"),
    "RSA": ("Afrique du Sud", "South Africa"), "RUS": ("Russie", "Russia"), "RWA": ("Rwanda", "Rwanda"),
    "SEN": ("Sénégal", "Senegal"), "SEY": ("Seychelles", "Seychelles"), "SIN": ("Singapour", "Singapore"),
    "SLE": ("Sierra Leone", "Sierra Leone"), "SLO": ("Slovénie", "Slovenia"), "SMR": ("Saint-Marin", "San Marino"),
    "SOM": ("Somalie", "Somalia"), "SRB": ("Serbie", "Serbia"), "SRI": ("Sri Lanka", "Sri Lanka"),
    "STP": ("Sao Tomé-et-Principe", "Sao Tome and Principe"), "SUD": ("Soudan", "Sudan"), "SUI": ("Suisse", "Switzerland"),
    "SUR": ("Suriname", "Suriname"), "SVK": ("Slovaquie", "Slovakia"), "SWE": ("Suède", "Sweden"),
    "SXM": ("Saint-Martin (partie néerlandaise)", "Sint Maarten"), "SYR": ("Syrie", "Syria"),
    "TAN": ("Tanzanie", "Tanzania"), "THA": ("Thaïlande", "Thailand"), "TJK": ("Tadjikistan", "Tajikistan"),
    "TKM": ("Turkménistan", "Turkmenistan"), "TOG": ("Togo", "Togo"), "TPE": ("Taïwan", "Chinese Taipei"),
    "TTO": ("Trinité-et-Tobago", "Trinidad and Tobago"), "TUN": ("Tunisie", "Tunisia"), "TUR": ("Turquie", "Türkiye", "Turkey"),
    "UAE": ("Émirats arabes unis", "United Arab Emirates", "UAE"), "UGA": ("Ouganda", "Uganda"), "UKR": ("Ukraine", "Ukraine"),
    "URU": ("Uruguay", "Uruguay"), "USA": ("États-Unis", "United States", "USA"), "UZB": ("Ouzbékistan", "Uzbekistan"),
    "VAT": ("Vatican", "Vatican City"), "GBS": ("Guinée-Bissau", "Guinea-Bissau"), "GEQ": ("Guinée équatoriale", "Equatorial Guinea"),
    "MAW": ("Malawi", "Malawi"), "PLW": ("Palaos", "Palau"), "SSD": ("Soudan du Sud", "South Sudan"), "VEN": ("Venezuela", "Venezuela"), "VIE": ("Viêt Nam", "Vietnam"),
    "VIN": ("Saint-Vincent-et-les-Grenadines", "Saint Vincent and the Grenadines"), "ZAM": ("Zambie", "Zambia"),
    "ZIM": ("Zimbabwe", "Zimbabwe"),
}
# nom de pays normalisé (netutil.normalize) -> codes qui le portent (anglais UCI, graphies et noms français)
_PAYS_PAR_NOM: Dict[str, Set[str]] = {}
for _code, _noms in PAYS_NOMS.items():
    for _n in _noms:
        _PAYS_PAR_NOM.setdefault(netutil.normalize(_n), set()).add(_code)

# Classements annexes pris en compte pour le palmarès : tous ceux de riders._agreger (étape + finaux).
ABANDONS = riders.STATUTS_ABANDON


# --------------------------------------------------------------------------- utilitaires

def _lettre(txt: Optional[str]) -> str:
    c = (txt or "")[:1]
    return c if "a" <= c <= "z" else "_"


def _sans_vide(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _est_nationale(libelle: str, nationalites: Iterable[Optional[str]]) -> Optional[str]:
    """Code pays si `libelle` est une SÉLECTION NATIONALE, sinon None. Règle (documentée, testée) : le libellé,
    normalisé, est le nom (anglais UCI, français ou graphie connue) d'un pays ET tous les coureurs qui le portent cette
    saison ont la nationalité correspondante. Un club dont le nom ressemble à un pays mais qui aligne d'autres
    nationalités n'est donc pas une sélection ; un libellé sans table de nom reste une équipe de marque (jamais deviné)."""
    codes = _PAYS_PAR_NOM.get(netutil.normalize(libelle))
    nats = set(nationalites)
    if not codes or len(nats) != 1:
        return None
    nat = next(iter(nats))
    return nat if nat in codes else None


def _dk(race: Dict[str, Any]) -> Tuple[str, str]:
    return (race.get("start_date") or "", race.get("id") or "")


def _classement_podium(race: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lignes classées (rang 1..3, sans statut) du classement qui désigne le vainqueur d'une édition : général final
    d'une course par étapes terminée, classement de la course pour un jour. Rien d'autre (pas de classement annexe)."""
    if race.get("status") not in (None, "finished"):
        return []
    if race.get("race_type") == "stage_race":
        rows = riders._classements_finaux(race).get("gc") or []
    else:
        et = riders._etapes(race)
        rows = riders._classement_course(race, et[-1]) if et else []
    sel = [r for r in rows if r.get("rank") is not None and r.get("status") is None and 1 <= r["rank"] <= FINAUX_PODIUM]
    return sorted(sel, key=lambda r: (r["rank"], r.get("rider_id") or ""))


def _ref_podium(refs: Dict[str, Any], rid: str, rang: int) -> Dict[str, Any]:
    ref = refs.get(rid) or {}
    return _sans_vide({"rank": rang, "id": rid, "name": ref.get("name"), "nat": ref.get("nationality"),
                       "flag": ref.get("flag"), "team": ref.get("team")})


def _statuts_abandon(race: Dict[str, Any]) -> Dict[str, str]:
    """rider_id -> statut (DNF, OTL, DSQ) du premier abandon constaté sur une étape (course par étapes)."""
    out: Dict[str, str] = {}
    for et in riders._etapes(race):
        for r in ((et.get("results") or {}).get("stage") or []):
            if r.get("status") in ABANDONS and r.get("rider_id") and r["rider_id"] not in out:
                out[r["rider_id"]] = r["status"]
    return out


def _grand_tour(cle: Optional[str], race: Dict[str, Any]) -> Optional[str]:
    """'tour' | 'giro' | 'vuelta' si la course (clé d'édition après alias) est un grand tour : clé EXACTE de GRANDS_TOURS,
    course par étapes terminée, classe de CLASSES_GRAND_TOUR."""
    gt = _GT_PAR_CLE.get(cle or "")
    if gt and race.get("race_type") == "stage_race" and race.get("uci_class") in CLASSES_GRAND_TOUR \
            and race.get("status") in (None, "finished"):
        return gt
    return None


# --------------------------------------------------------------------------- lecture des sources

def _annee(nom: str) -> Optional[int]:
    return int(nom) if nom.isdigit() and len(nom) == 4 else None


def lister_sources(archives_dir: str, data_dir: str) -> Tuple[Dict[int, Dict[str, Any]], int]:
    """({saison: {"races": [chemins], "archive": bool, "riders": chemin|None, "ranking": chemin|None, "etat": dict}}, inconnues) :
    chemins des fiches de course d'une saison (archives d'abord ; une course de même identifiant dans le Calendrier est
    ignorée), de son `riders*.json` et de son classement UCI. Les fiches du Calendrier sont rangées par `season`
    (à défaut : `index-<année>.json` qui la liste ; sans saison connue, fiche ignorée et comptée dans `inconnues`)."""
    out: Dict[int, Dict[str, Any]] = {}
    if os.path.isdir(archives_dir):
        for nom in sorted(os.listdir(archives_dir)):
            an = _annee(nom)
            dossier = os.path.join(archives_dir, nom)
            if an is None or not os.path.isdir(dossier):
                continue
            rdir = os.path.join(dossier, "races")
            fichiers = sorted(os.path.join(rdir, f) for f in os.listdir(rdir) if f.endswith(".json")) if os.path.isdir(rdir) else []
            rk = os.path.join(dossier, "ranking.json")
            rd = os.path.join(dossier, "riders.json")
            out[an] = {"races": fichiers, "archive": True, "riders": rd if os.path.exists(rd) else None,
                       "ranking": rk if os.path.exists(rk) else None,
                       "etat": collector._load(os.path.join(dossier, "state.json"), {}) or {}}
    # Calendrier
    par_index: Dict[str, int] = {}
    if os.path.isdir(data_dir):
        for f in sorted(os.listdir(data_dir)):
            m = re.fullmatch(r"index-(\d{4})\.json", f)
            if m:
                ix = collector._load(os.path.join(data_dir, f), {}) or {}
                for r in ix.get("races") or []:
                    if r.get("id"):
                        par_index.setdefault(r["id"], int(m.group(1)))
    rdir = os.path.join(data_dir, "races")
    inconnues = 0
    if os.path.isdir(rdir):
        deja = {os.path.basename(p) for s in out.values() for p in s["races"]}
        for f in sorted(os.listdir(rdir)):
            if not f.endswith(".json") or f in deja:
                continue
            rid = f[:-5]
            an = par_index.get(rid)
            if an is None:
                an = (collector._load(os.path.join(rdir, f), {}) or {}).get("season")
            if not isinstance(an, int):
                inconnues += 1
                continue
            s = out.setdefault(an, {"races": [], "archive": False, "riders": None, "ranking": None, "etat": {}})
            s["races"].append(os.path.join(rdir, f))
    for an, s in out.items():
        if not s["riders"]:
            p = os.path.join(data_dir, f"riders-{an}.json")
            s["riders"] = p if os.path.exists(p) else None
        if not s["ranking"]:
            p = os.path.join(data_dir, "ranking.json")
            rk = collector._load(p, None) if os.path.exists(p) else None
            if rk and rk.get("season") == an:       # classement du jour : seulement pour la saison qu'il désigne
                s["ranking"] = p
    return out, inconnues


# --------------------------------------------------------------------------- cumul d'une saison

class _Saison:
    """Cumuls d'une saison pendant la lecture de ses fiches (identifiants BRUTS : l'alias s'applique à la fin)."""

    def __init__(self, annee: int):
        self.annee = annee
        self.coureurs: Dict[str, Dict[str, Any]] = {}
        self.palmares: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        self.grands_tours: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        self.editions: List[Dict[str, Any]] = []          # un par course terminée
        self.categories: collections.Counter = collections.Counter()
        self.en_cours = 0
        self.courses_total = 0
        # équipes : slug -> {"libelles": Counter, "eff": {rid: [jours, victoires, généraux]}, "victoires": [], "gt": {gt: meilleur}}
        self.equipes: Dict[str, Dict[str, Any]] = {}
        self.sans_cle = 0
        self.sans_equipe = 0
        self.gt_vus: List[Dict[str, Any]] = []
        self.corrections: Dict[str, Dict[str, Dict[str, str]]] = {}     # rid brut -> {champ: {uci, source}} (corrections_coureurs.json)

    def equipe(self, libelle: str) -> Optional[Dict[str, Any]]:
        slug = netutil.slugify(libelle)
        if not slug:
            return None
        e = self.equipes.get(slug)
        if e is None:
            e = self.equipes[slug] = {"libelles": collections.Counter(), "eff": {}, "victoires": [], "gt": {}}
        e["libelles"][libelle] += 1
        return e


def _fusionner_ids(race: Dict[str, Any], fus: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Fusion « même saison » explicite (`_fusion_meme_saison`) : dans cette fiche, l'identifiant source devient l'identifiant canonique
    (clés de `riders`, `id` des refs, `rider_id` des lignes) ; les cumuls de la saison réunissent donc les deux identifiants (stats,
    palmarès, équipes). Si les deux identifiants figurent dans la même course, rien n'est changé (double comptage possible : `[WARN]`)
    et la règle de contradiction s'applique ensuite. Retourne (fiche, {source: canonique} effectivement appliqués)."""
    refs = race.get("riders") or {}
    actifs: Dict[str, str] = {}
    for src, canon in fus.items():
        if src in refs:
            if canon in refs:
                print(f"[WARN] encyclopédie : fusion « {src} » -> « {canon} » ignorée dans {race.get('id')} (les deux figurent dans la course)")
            else:
                actifs[src] = canon
    if not actifs:
        return race, {}

    def tr(o: Any, parent: Optional[str] = None) -> Any:
        if isinstance(o, dict):
            return {(actifs.get(k, k) if parent == "riders" else k):
                    (actifs.get(v, v) if k in ("rider_id", "id") and isinstance(v, str) else tr(v, k)) for k, v in o.items()}
        if isinstance(o, list):
            return [tr(x, parent) for x in o]
        return o
    return tr(race), actifs


def _traiter_course(S: _Saison, race: Dict[str, Any], alias_courses: Dict[str, str], fus: Optional[Dict[str, str]] = None) -> None:
    """Réduit une fiche de course et l'ajoute aux cumuls de la saison."""
    refs = race.get("riders") or {}
    corr = uci.corrections_coureurs()
    if corr and any(rid in corr for rid in refs):
        # erreurs de source documentées : les fiches d'archive déjà écrites gardent la valeur UCI, l'entité porte la valeur corrigée
        refs = dict(refs)
        for rid in [r for r in refs if r in corr]:
            refs[rid] = dict(refs[rid])
            for c in uci.corriger_ref(rid, refs[rid]):
                S.corrections.setdefault(rid, {})[c["champ"]] = {"uci": c["uci"], "source": c["source"]}
        race = dict(race, riders=refs)
    if fus:
        race, actifs = _fusionner_ids(race, fus)
        refs = race.get("riders") or {}
        S.corrections = {actifs.get(k, k): v for k, v in S.corrections.items()}      # clés = identifiants après fusion
    dk = _dk(race)
    fini = race.get("status") in (None, "finished")
    S.courses_total += 1
    if fini:
        S.categories[race.get("category") or "?"] += 1
    else:
        S.en_cours += 1
    cle = collector.cle_edition(race.get("name"), race.get("country"))
    cle = alias_courses.get(cle, cle) if cle else None
    if not cle:
        S.sans_cle += 1
    agg = riders._agreger([race])
    meta_pal = {"season": S.annee, "race_id": race.get("id"), "course": cle, "category": race.get("category"),
                "uci_class": race.get("uci_class")}
    for rid, f in agg.items():
        a = S.coureurs.get(rid)
        if a is None:
            a = S.coureurs[rid] = {"stats": collections.Counter(), "_dk": None, "equipes": {}}
        plus_recent = a["_dk"] is None or dk >= a["_dk"]      # la fiche la plus récente l'emporte, sans effacer par du vide
        for k in ("name", "nationality", "flag", "birth_date", "team"):
            if f.get(k) and (plus_recent or not a.get(k)):
                a[k] = f[k]
        if plus_recent:
            a["_dk"] = dk
        for k, v in f["stats"].items():
            a["stats"][k] += v
        eq = None
        if f.get("team"):
            a["equipes"][f["team"]] = min(dk, a["equipes"].get(f["team"], dk))
            eq = S.equipe(f["team"])
        elif f["stats"].get("race_days"):
            S.sans_equipe += 1
        if eq is not None:
            c = eq["eff"].setdefault(rid, [0, 0, 0])
            c[0] += f["stats"].get("race_days", 0)
            c[1] += f["stats"].get("wins", 0)
            c[2] += f["stats"].get("gc_wins", 0)
        for x in f["results"]:
            if x["rank"] > 3:
                continue
            S.palmares[rid].append(_sans_vide(dict(
                date=x["date"], race_id=meta_pal["race_id"], course=cle, label=x["label"],
                classification=x["classification"], rank=x["rank"], category=meta_pal["category"],
                uci_class=meta_pal["uci_class"], season=S.annee)))
            if eq is not None and x["rank"] == 1 and x["classification"] in ("stage", "gc"):
                eq["victoires"].append(_sans_vide({"date": x["date"], "race_id": race.get("id"), "course": cle,
                                                   "label": x["label"], "classification": x["classification"],
                                                   "rider_id": rid}))
    if not fini:
        return
    # édition : podium + meilleur Français
    podium = [_ref_podium(refs, r["rider_id"], r["rank"]) for r in _classement_podium(race) if r.get("rider_id")]
    bf = race.get("best_french") or {}
    best = None
    if bf.get("rider"):
        br = bf["rider"]
        best = _sans_vide({"id": br.get("id"), "name": br.get("name"), "flag": br.get("flag"), "rank": bf.get("rank"),
                           "classification": bf.get("classification")})
    S.editions.append({"cle": cle, "nom": race.get("name"), "pays": race.get("country"), "flag": race.get("flag"),
                       "classe": race.get("uci_class"), "type": race.get("race_type"),
                       "edition": _sans_vide({"season": S.annee, "race_id": race.get("id"),
                                              "start_date": race.get("start_date"), "end_date": race.get("end_date"),
                                              "podium": podium or None, "best_french": best})})
    gt = _grand_tour(cle, race)
    if gt:
        rows = riders._classements_finaux(race).get("gc") or []
        abandons = _statuts_abandon(race)
        classes = set()
        for r in rows:
            rid = r.get("rider_id")
            if not rid:
                continue
            classes.add(rid)
            if r.get("rank") is not None and r.get("status") is None:
                S.grands_tours[rid].append({"season": S.annee, "course": gt, "race_id": race.get("id"), "rank": r["rank"]})
                eq = S.equipes.get(netutil.slugify((refs.get(rid) or {}).get("team") or ""))
                if eq is not None:
                    best_gt = eq["gt"].get(gt)
                    if best_gt is None or (r["rank"], rid) < (best_gt["rank"], best_gt["rider_id"]):
                        eq["gt"][gt] = {"rank": r["rank"], "rider_id": rid, "race_id": race.get("id")}
            elif r.get("status"):
                S.grands_tours[rid].append({"season": S.annee, "course": gt, "race_id": race.get("id"), "status": r["status"]})
        for rid, st in abandons.items():     # partants non classés au général final : abandon constaté sur une étape
            if rid not in classes:
                S.grands_tours[rid].append({"season": S.annee, "course": gt, "race_id": race.get("id"), "status": st})
        S.gt_vus.append({"course": gt, "race_id": race.get("id"), "name": race.get("name"), "cle": cle})


# --------------------------------------------------------------------------- fin de saison

def _mapping_alias(S: _Saison, alias: Dict[str, str], avertir: List[str]) -> Dict[str, str]:
    """Identifiant canonique de chaque coureur de la saison. Même règle que collector.construire_carrieres : identifiants
    canoniques d'abord ; un alias qui ferait figurer deux fois le même coureur la même saison est ignoré (rien fusionné)."""
    vus: Dict[str, str] = {}
    mapping: Dict[str, str] = {}
    for rid in sorted(S.coureurs, key=lambda k: (k in alias, k)):
        cid = alias.get(rid, rid)
        if cid in vus:
            avertir.append(f"alias « {rid} » -> « {cid} » ignoré en {S.annee} (le coureur canonique y figure déjà)")
            cid = rid
            if cid in vus:
                continue
        vus[cid] = rid
        mapping[rid] = cid
    return mapping


def _uci_saison(S: _Saison, src: Dict[str, Any]) -> Tuple[Dict[str, Tuple[Optional[int], Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """({rid brut: (rang, points)}, méta du classement, riders.json lu). Priorité à `riders.json` / `riders-<année>.json`
    (c'est ce qu'affichent les fiches actuelles), sinon rapprochement du `ranking.json` de la saison avec
    `riders._rapprocher` ; sinon rien (absent)."""
    rj = collector._load(src["riders"], None) if src.get("riders") else None
    if rj and isinstance(rj.get("riders"), dict):
        res = {rid: (f.get("uci_rank"), f.get("uci_points")) for rid, f in rj["riders"].items() if f.get("uci_rank") is not None}
        if res or not src.get("ranking"):
            return res, (rj.get("ranking") or None), rj
    rk = collector._load(src["ranking"], None) if src.get("ranking") else None
    if rk and rk.get("rows"):
        fiches = {rid: {"name": a.get("name"), "nationality": a.get("nationality"), "birth_date": a.get("birth_date")}
                  for rid, a in S.coureurs.items()}
        riders._rapprocher(fiches, rk)
        res = {rid: (f.get("uci_rank"), f.get("uci_points")) for rid, f in fiches.items() if f.get("uci_rank") is not None}
        return res, {"name": rk.get("name"), "date": rk.get("date"), "source": rk.get("source")}, rj
    return {}, None, rj


# --------------------------------------------------------------------------- construction

def _codes_equipes(src: Dict[str, Any]) -> Dict[str, Set[str]]:
    """{slug du libellé d'équipe: {TeamCode}} des coureurs classés du classement UCI de la saison (même normalisation que l'id d'équipe-saison)."""
    rk = collector._load(src["ranking"], None) if src.get("ranking") else None
    out: Dict[str, Set[str]] = {}
    for r in (rk.get("rows") if isinstance(rk, dict) else None) or []:
        slug = netutil.slugify(r.get("team") or "")
        code = str(r.get("team_code") or "").strip()
        if slug and code:
            out.setdefault(slug, set()).add(code)
    return out


def construire(archives_dir: str, data_dir: str, sortie: Optional[str] = None, now: Optional[str] = None,
               alias_coureurs: Optional[Dict[str, str]] = None, alias_courses: Optional[Dict[str, str]] = None,
               verbose: bool = True, wikidata_dir: Optional[str] = None, fusions: Optional[Iterable[str]] = None,
               historique_dir: Optional[str] = None) -> Dict[str, Any]:
    """Génère `sortie` (défaut `<archives_dir>/entites`). Retourne un rapport (compteurs, tailles, anomalies).
    `wikidata_dir` : cache Wikidata lu (défaut `<sortie>/wikidata`) ; `historique_dir` : cache de l'historique (palmarès Wikidata, module
    `historique`) lu (défaut `<sortie>/historique`)."""
    t0 = time.time()
    sortie = sortie or os.path.join(archives_dir, "entites")
    WD = wikidata.charger_cache(wikidata_dir or os.path.join(sortie, "wikidata"))
    HIST = historique.charger_cache(historique_dir or os.path.join(sortie, "historique"))
    LIGNEES_EQ: Dict[str, List[Tuple[int, str]]] = {}      # QID de lignée -> [(saison, id d'équipe-saison)]
    ar = collector.charger_alias(collector.ALIAS_COUREURS) if alias_coureurs is None else alias_coureurs
    ac = collector.charger_alias(collector.ALIAS_COURSES) if alias_courses is None else alias_courses
    if fusions is None and alias_coureurs is None:
        fusions = collector.charger_fusions(collector.ALIAS_COUREURS)
    fus = collector.fusions_valides(ar, fusions)      # fusions « même saison » explicitement autorisées
    now = now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sources, inconnues = lister_sources(archives_dir, data_dir)
    annees = sorted(sources)

    COUR: Dict[str, Dict[str, Any]] = {}
    COURSES: Dict[str, Dict[str, Any]] = {}
    PAYS: Dict[str, Dict[str, Any]] = {}
    EQ_RECH: Dict[str, Dict[str, Any]] = {}          # slug du libellé -> entrée de recherche
    EQ_INDEX: List[Dict[str, Any]] = []
    anomalies: Dict[str, Any] = collections.defaultdict(list)
    rapport: Dict[str, Any] = {"saisons": annees, "inconnues": inconnues}
    gt_par_saison: Dict[int, List[str]] = {}
    coherence = {"coureurs_compares": 0, "ecarts": 0, "exemples": []}
    HISTORIQUE: Dict[str, Dict[str, int]] = {}      # rider_id canonique -> {date: rang UCI} (instantanés E1c)
    equipes_ecrites: Set[str] = set()
    saisons_ecrites: Set[str] = set()
    equipes_total = 0
    nationales = 0
    editions_total = 0
    fichiers_ecrits = 0

    def ecrire(chemin: str, data: Any, ignore: Tuple[str, ...] = ()) -> None:
        nonlocal fichiers_ecrits
        fichiers_ecrits += bool(_ecrire_si_change(chemin, data, ignore))

    for an in annees:
        src = sources[an]
        S = _Saison(an)
        vus: Set[str] = set()
        for chemin in src["races"]:
            race = collector._load(chemin, None)
            if not race or not race.get("id") or race["id"] in vus:
                continue
            vus.add(race["id"])
            _traiter_course(S, race, ac, fus)
            del race
        avert: List[str] = []
        mapping = _mapping_alias(S, ar, avert)
        brut_de = {c: r for r, c in mapping.items()}
        for w in avert:
            print(f"[WARN] encyclopédie : {w}")
        anomalies["alias_ignores"].extend(avert)
        uci_res, uci_meta, rj = _uci_saison(S, src)
        codes_saison = _codes_equipes(src)
        cm = lambda rid: mapping.get(rid, rid)   # noqa: E731
        instantanes = _lire_instantanes(archives_dir, an, lambda rid, d, rang: HISTORIQUE.setdefault(cm(rid), {}).__setitem__(d, rang))

        # cohérence avec riders.json (mêmes définitions : stats identiques attendues)
        if rj and isinstance(rj.get("riders"), dict):
            for rid, f in rj["riders"].items():
                a = S.coureurs.get(rid)
                if a is None:
                    continue
                coherence["coureurs_compares"] += 1
                mine = {k: v for k, v in a["stats"].items() if v}
                if mine != {k: v for k, v in (f.get("stats") or {}).items() if v}:
                    coherence["ecarts"] += 1
                    if len(coherence["exemples"]) < 5:
                        coherence["exemples"].append({"saison": an, "id": rid, "encyclopedie": mine, "riders_json": f.get("stats")})

        # ---- équipes-saisons
        equipes: Dict[str, Dict[str, Any]] = {}
        slug_vers_id: Dict[str, str] = {}
        slug_nationale: Dict[str, str] = {}
        slug_nom: Dict[str, str] = {}
        for slug, e in S.equipes.items():
            nom = sorted(e["libelles"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            tid = f"{slug}-{an}"
            slug_vers_id[slug] = tid
            eff: Dict[str, List[int]] = {}
            for rid, v in e["eff"].items():
                c = eff.setdefault(cm(rid), [0, 0, 0])
                for i in range(3):
                    c[i] += v[i]
            nats = [S.coureurs[r]["nationality"] if r in S.coureurs else None for r in e["eff"]]
            nat = _est_nationale(nom, nats)
            effectif = sorted(
                ({"rider_id": cid, **_sans_vide({"name": S.coureurs[brut_de.get(cid, cid)].get("name"),
                                                  "flag": S.coureurs[brut_de.get(cid, cid)].get("flag")}),
                  "jours": v[0], "wins": v[1]} for cid, v in eff.items()),
                key=lambda x: (-x["jours"], -x["wins"], x.get("name") or "", x["rider_id"]))
            vict = [dict(v, rider_id=cm(v["rider_id"])) for v in e["victoires"]]
            vict.sort(key=lambda v: (v["date"], v["race_id"], v["classification"], v["rider_id"]), reverse=True)
            fiche = {"name": nom, "season": an}
            slug_nom[slug] = nom
            if nat:
                fiche["nationale"] = True
                fiche["pays"] = nat
                slug_nationale[slug] = nat
            elif len(codes_saison.get(slug) or ()) == 1:
                fiche["code_uci"] = next(iter(codes_saison[slug]))
            elif codes_saison.get(slug):
                anomalies["code_uci_multiple"].append(f"{an} {nom} {sorted(codes_saison[slug])}")
            lig = (WD["equipes"].get(tid) or {}).get("qid")
            if lig:
                fiche["lignee"] = lig
                LIGNEES_EQ.setdefault(lig, []).append((an, tid))
            fiche["effectif"] = effectif
            fiche["victoires"] = vict
            if e["gt"]:
                fiche["grands_tours"] = {gt: dict(v, rider_id=cm(v["rider_id"])) for gt, v in sorted(e["gt"].items())}
            fiche["totaux"] = {"wins": sum(v[1] for v in eff.values()), "gc_wins": sum(v[2] for v in eff.values()),
                               "riders": len(eff), "jours": sum(v[0] for v in eff.values())}
            if len(e["libelles"]) > 1:
                fiche["libelles"] = sorted(e["libelles"])     # variantes de casse / ponctuation fusionnées (même slug)
                anomalies["equipes_libelles_fusionnes"].append(f"{an} {sorted(e['libelles'])}")
            equipes[tid] = fiche
            nationales += bool(nat)
            # recherche (regroupée par libellé : slug sans année)
            ent = EQ_RECH.get(slug)
            if ent is None:
                ent = EQ_RECH[slug] = {"n": nom, "t": "e", "id": tid, "y": [an, an]}
            else:                    # saisons traitées par année croissante : la plus récente donne le libellé et l'id
                ent["y"][1] = an
                ent["n"], ent["id"] = nom, tid
            if nat:
                ent["nat"] = True
                code_flag = _drapeau_pays(S, nat)
                if code_flag:
                    ent["f"] = code_flag
            EQ_INDEX.append(_sans_vide({"id": tid, "name": nom, "season": an, "wins": fiche["totaux"]["wins"],
                                        "riders": fiche["totaux"]["riders"], "nationale": True if nat else None,
                                        "lignee": lig}))
        equipes = dict(sorted(equipes.items()))
        equipes_total += len(equipes)
        ecrire(os.path.join(sortie, "equipes", f"{an}.json"), equipes)
        equipes_ecrites.add(f"{an}.json")
        id_equipe_de = lambda label: slug_vers_id.get(netutil.slugify(label or ""))   # noqa: E731

        # ---- coureurs
        wins_par_pays: collections.Counter = collections.Counter()
        wins_fr = 0
        top_coureurs: List[Tuple[int, str, str, Optional[str]]] = []
        pays_saison: Dict[str, Dict[str, int]] = {}
        for rid, a in S.coureurs.items():
            cid = cm(rid)
            c = COUR.get(cid)
            if c is None:
                c = COUR[cid] = {"saisons": {}, "palmares": [], "grands_tours": [], "_stats": collections.Counter()}
            for k in ("name", "nationality", "flag", "birth_date"):
                if a.get(k):
                    c[k] = a[k]
            for champ, v in sorted(S.corrections.get(rid, {}).items()):
                lst = c.setdefault("corrections", [])
                if not any(x["champ"] == champ for x in lst):
                    lst.append({"champ": champ, "uci": v["uci"], "source": v["source"]})
            s: Dict[str, Any] = {}
            if a["equipes"]:
                # équipe principale = équipe de marque (pas une sélection nationale) aux plus nombreux jours de course
                # de la saison (égalité : la plus récente) ; sélection seulement si c'est la seule équipe connue
                par_slug: Dict[str, List[Any]] = {}
                for label, d0 in a["equipes"].items():
                    sl = netutil.slugify(label)
                    par_slug.setdefault(sl, []).append(d0)
                cands = [(S.equipes[sl]["eff"].get(rid, [0])[0], max(ds), sl) for sl, ds in par_slug.items() if sl in S.equipes]
                pool = [c for c in cands if c[2] not in slug_nationale] or cands
                if pool:
                    sl = max(pool)[2]
                    s["team"] = slug_nom[sl]
                    s["equipe"] = slug_vers_id[sl]
                    if len(cands) > 1:      # plusieurs équipes la même saison (transfert, sélection nationale) : toutes, par ordre d'apparition
                        s["equipes"] = [slug_vers_id[c[2]] for c in sorted(cands, key=lambda c: (min(par_slug[c[2]]), c[2]))]
            stats = {k: v for k, v in a["stats"].items() if v}
            if stats:
                s["stats"] = stats
            rk = uci_res.get(rid)
            if rk:
                s["uci_rank"], pts = rk
                if pts is not None:
                    s["uci_points"] = pts
            c["saisons"][str(an)] = s
            c["palmares"].extend(S.palmares.get(rid, ()))
            c["grands_tours"].extend(S.grands_tours.get(rid, ()))
            for k in ("wins", "podiums", "gc_wins"):
                c["_stats"][k] += a["stats"].get(k, 0)
            nat = a.get("nationality")
            if nat:
                p = pays_saison.setdefault(nat, {"coureurs": 0, "victoires": 0, "podiums": 0})
                p["coureurs"] += 1
                p["victoires"] += a["stats"].get("wins", 0)
                p["podiums"] += a["stats"].get("podiums", 0)
                wins_par_pays[nat] += a["stats"].get("wins", 0)
                if nat == "FRA":
                    wins_fr += a["stats"].get("wins", 0)
            if a["stats"].get("wins"):
                top_coureurs.append((a["stats"]["wins"], a.get("name") or "", cid, nat))
            if not a.get("birth_date"):
                anomalies["sans_date_naissance"].append(cid)
            if not a.get("nationality"):
                anomalies["sans_nationalite"].append(cid)
        for nat, p in pays_saison.items():
            P = PAYS.setdefault(nat, {"saisons": {}, "flags": collections.Counter(), "wins": {}})
            P["saisons"][str(an)] = p
        for rid, a in S.coureurs.items():
            nat = a.get("nationality")
            if nat:
                if a.get("flag"):
                    PAYS[nat]["flags"][a["flag"]] += 1
                if a["stats"].get("wins"):
                    PAYS[nat]["wins"][cm(rid)] = PAYS[nat]["wins"].get(cm(rid), 0) + a["stats"]["wins"]

        # ---- courses (éditions)
        for ed in S.editions:
            cle = ed["cle"]
            e = dict(ed["edition"])
            if e.get("podium"):
                e["podium"] = [dict(p, id=cm(p["id"])) for p in e["podium"]]
            if e.get("best_french") and e["best_french"].get("id"):
                e["best_french"] = dict(e["best_french"], id=cm(e["best_french"]["id"]))
            editions_total += 1
            if not cle:
                anomalies["editions_sans_cle"].append(f"{an} {ed['nom']!r} {ed['pays']!r}")
                continue
            C = COURSES.setdefault(cle, {"noms": {}, "pays": cle.rsplit("|", 1)[1], "flag": None, "classes": {},
                                          "type": None, "_type_an": 0, "editions": []})
            C["noms"].setdefault(ed["nom"], set()).add(an)
            if ed.get("flag") and not C["flag"]:
                C["flag"] = ed["flag"]
            if ed.get("classe"):
                C["classes"].setdefault(str(an), ed["classe"])
            if ed.get("type") and an >= C["_type_an"]:
                C["type"], C["_type_an"] = ed["type"], an
            C["editions"].append(e)

        # ---- fichier de saison
        gt_par_saison[an] = sorted(g["course"] + ":" + str(g["race_id"]) for g in S.gt_vus)
        equipes_top = sorted(((f["totaux"]["wins"], f["name"], tid) for tid, f in equipes.items() if f["totaux"]["wins"]),
                             key=lambda t: (-t[0], t[1], t[2]))[:TOP]
        top_coureurs.sort(key=lambda t: (-t[0], t[1], t[2]))
        saison = {"season": an,
                  "courses": {"total": S.courses_total - S.en_cours,
                              "par_categorie": dict(sorted(S.categories.items())),
                              **({"en_cours": S.en_cours} if S.en_cours else {})},
                  "victoires_par_pays": dict(sorted(((k, v) for k, v in wins_par_pays.items() if v), key=lambda kv: (-kv[1], kv[0]))),
                  "victoires_par_equipe": [{"id": tid, "name": n, "wins": w} for w, n, tid in equipes_top],
                  "coureurs_victorieux": [_sans_vide({"id": cid, "name": n or None, "nat": nat, "wins": w})
                                          for w, n, cid, nat in top_coureurs[:TOP]],
                  "victoires_francaises": wins_fr,
                  "classement_uci": _sans_vide({"present": bool(uci_meta), "name": (uci_meta or {}).get("name"),
                                                "date": (uci_meta or {}).get("date"),
                                                "final": True if (src["archive"] and uci_meta and src.get("etat", {}).get("complete")) else None,
                                                "classes": len(uci_res) or None}),
                  "instantanes_uci": instantanes or None,
                  "complete": True if src.get("etat", {}).get("complete") else None,
                  "source": "archives" if src["archive"] else "calendrier"}
        saison = _sans_vide(saison)
        ecrire(os.path.join(sortie, "saisons", f"{an}.json"), saison)
        saisons_ecrites.add(f"{an}.json")
        if S.sans_cle:
            anomalies["courses_sans_cle"].append(f"{an} : {S.sans_cle}")
        if S.sans_equipe:
            anomalies["rows_sans_equipe"].append(f"{an} : {S.sans_equipe}")
        if verbose:
            print(f"[ENCYCLOPEDIE] {an} : {S.courses_total} course(s), {len(S.coureurs)} coureur(s), {len(equipes)} équipe(s)")
        del S

    # ---- historique (palmarès Wikidata des années absentes de nos éditions UCI) : fusionné avant l'écriture des coureurs et des courses
    H: Dict[str, Any] = historique.appliquer_historique(HIST, COURSES, COUR, ar, WD["coureurs"], now[:10]) if HIST["editions"] else \
        {"par_cle": {}, "attaches": {}, "legers": {}, "recherche": [], "rapport": {}}
    rapport["historique"] = H["rapport"]

    # ---- finalisation des coureurs
    ordre_class = {"gc": 0, "stage": 1, "points": 2, "mountain": 3, "youth": 4}
    lettres: Dict[str, Dict[str, Any]] = {}
    for cid in sorted(COUR):
        c = COUR[cid]
        st = c.pop("_stats")
        c["palmares"].sort(key=lambda x: (x["date"], x["race_id"], -ordre_class.get(x["classification"], 9), -x["rank"]), reverse=True)
        c["grands_tours"].sort(key=lambda x: (x["season"], x["course"]), reverse=True)
        c["saisons"] = dict(sorted(c["saisons"].items(), reverse=True))
        c["totaux"] = {"wins": st["wins"], "podiums": st["podiums"], "gc_wins": st["gc_wins"], "seasons": len(c["saisons"])}
        for k in ("palmares", "grands_tours"):
            if not c[k]:
                del c[k]
        hist = HISTORIQUE.get(cid)
        if hist:
            c["historique_uci"] = [[d, hist[d]] for d in sorted(hist)]
        if cid in H["attaches"]:
            c["palmares_historique"] = H["attaches"][cid]            # années absentes de nos données UCI ; source Wikidata (QID de l'édition)
            c["palmares_historique_source"] = "wikidata"
        wd = wikidata.fiche_wikidata(WD["coureurs"].get(cid), WD["images"])
        if wd:
            c["wikidata"] = wd
        out = {k: c[k] for k in ("name", "nationality", "flag", "birth_date") if k in c}
        out.update({k: v for k, v in c.items() if k not in out})
        lettres.setdefault(_lettre(cid), {})[cid] = out
    for lettre, contenu in sorted(lettres.items()):
        ecrire(os.path.join(sortie, "coureurs", f"{lettre}.json"), contenu)
    _nettoyer(os.path.join(sortie, "coureurs"), {f"{l}.json" for l in lettres})

    # ---- coureurs historiques (légers) : fichier d'après les deux derniers chiffres du QID (« wd-Q123456 » -> 56.json)
    legers_fichiers: Dict[str, Dict[str, Any]] = {}
    for wid, fiche in H["legers"].items():
        legers_fichiers.setdefault(historique.fichier_leger(wid), {})[wid] = fiche
    for nom, contenu in sorted(legers_fichiers.items()):
        ecrire(os.path.join(sortie, "coureurs_historiques", f"{nom}.json"), contenu)
    _nettoyer(os.path.join(sortie, "coureurs_historiques"), {f"{n}.json" for n in legers_fichiers})

    # ---- finalisation des équipes (index)
    EQ_INDEX.sort(key=lambda t: (-t["season"], t["name"], t["id"]))
    ecrire(os.path.join(sortie, "equipes", "index.json"), EQ_INDEX)
    # lignées Wikidata : seulement celles qui portent au moins une équipe-saison rapprochée (preuve dans le cache)
    lignees_out: Dict[str, Any] = {}
    for qid in sorted(LIGNEES_EQ):
        eqs = sorted(LIGNEES_EQ[qid], reverse=True)
        lignees_out[qid] = dict(wikidata.fiche_lignee(WD["lignees"].get(qid), WD["images"]),
                                equipes=[t for _a, t in eqs], saisons=[min(a for a, _ in eqs), max(a for a, _ in eqs)])
    ecrire(os.path.join(sortie, "equipes", "lignees.json"), lignees_out)
    _nettoyer(os.path.join(sortie, "equipes"), equipes_ecrites | {"index.json", "lignees.json"})
    _nettoyer(os.path.join(sortie, "saisons"), saisons_ecrites)

    # ---- finalisation des courses
    lettres_c: Dict[str, Dict[str, Any]] = {}
    for cle in sorted(COURSES):
        C = COURSES[cle]
        eds = sorted(C["editions"], key=lambda e: (e["season"], e.get("start_date") or "", e.get("race_id") or ""), reverse=True)
        vict_coureur: collections.Counter = collections.Counter()
        noms_coureur: Dict[str, str] = {}
        vict_pays: collections.Counter = collections.Counter()
        for e in eds:
            for p in e.get("podium") or []:
                if p["rank"] == 1:
                    vict_coureur[p["id"]] += 1
                    noms_coureur[p["id"]] = p.get("name") or ""
                    if p.get("nat"):
                        vict_pays[p["nat"]] += 1
        fiche = {"noms": {n: sorted(s) for n, s in sorted(C["noms"].items())}, "pays": C["pays"]}
        if C["flag"]:
            fiche["flag"] = C["flag"]
        fiche["classes"] = dict(sorted(C["classes"].items(), reverse=True))
        if C["type"]:
            fiche["type"] = C["type"]
        fiche["editions"] = eds
        fiche["records"] = {
            "victoires_par_coureur": [_sans_vide({"id": rid, "name": noms_coureur[rid] or None, "wins": n})
                                       for rid, n in sorted(vict_coureur.items(), key=lambda kv: (-kv[1], noms_coureur[kv[0]], kv[0])) if n >= 2],
            "victoires_par_pays": dict(sorted(vict_pays.items(), key=lambda kv: (-kv[1], kv[0])))}
        hc = H["par_cle"].get(cle)
        if hc:
            fiche["historique"] = hc["historique"]               # statut : ok | non_attribue | conflit | inconnu (jamais tranché), source_qid = élément Wikidata
            fiche["historique_info"] = hc["info"]
            fiche["records_historique"] = hc["records"]          # UCI + historique, années couvertes mentionnées
        lettres_c.setdefault(_lettre(cle), {})[cle] = fiche
    for lettre, contenu in sorted(lettres_c.items()):
        ecrire(os.path.join(sortie, "courses", f"{lettre}.json"), contenu)
    _nettoyer(os.path.join(sortie, "courses"), {f"{l}.json" for l in lettres_c})

    # ---- pays
    pays_out: Dict[str, Any] = {}
    for code in sorted(PAYS):
        P = PAYS[code]
        meilleurs = sorted(P["wins"].items(), key=lambda kv: (-kv[1], (COUR[kv[0]].get("name") or ""), kv[0]))[:TOP_PAYS]
        flag = (sorted(P["flags"].items(), key=lambda kv: (-kv[1], kv[0])) or [(netutil.flag_code(code), 0)])[0][0]
        nom = PAYS_NOMS.get(code)
        pays_out[code] = _sans_vide({
            "nom": nom[0] if nom else None, "flag": flag,
            "saisons": dict(sorted(P["saisons"].items(), reverse=True)),
            "meilleurs": [_sans_vide({"id": rid, "name": COUR[rid].get("name"), "wins": n}) for rid, n in meilleurs] or None})
        if code not in PAYS_NOMS:
            anomalies["pays_sans_nom"].append(code)
    ecrire(os.path.join(sortie, "pays.json"), pays_out)

    # ---- recherche
    recherche: Dict[str, List[Dict[str, Any]]] = {}

    def indexer(ent: Dict[str, Any]) -> None:
        mots = netutil.normalize(ent["n"]).split()
        for l in sorted({_lettre(m) for m in mots if len(m) >= 2}):
            recherche.setdefault(l, []).append(ent)

    for cid, c in COUR.items():
        if not c.get("name"):
            continue
        ys = sorted(int(y) for y in c["saisons"])
        indexer(_sans_vide({"n": c["name"], "t": "c", "id": cid, "f": c.get("flag"), "y": [ys[0], ys[-1]]}))
    for ent in EQ_RECH.values():
        indexer(ent)
    for qid, lg in lignees_out.items():
        if lg.get("libelle"):
            indexer({"n": lg["libelle"], "t": "l", "id": qid, "y": lg["saisons"]})
    for ent in H["recherche"]:
        indexer(ent)
    for cle, C in COURSES.items():
        dernier = max(C["noms"].items(), key=lambda kv: (max(kv[1]), kv[0]))
        ys = sorted({y for s in C["noms"].values() for y in s})
        indexer(_sans_vide({"n": dernier[0], "t": "r", "id": cle, "f": C.get("flag"), "y": [ys[0], ys[-1]]}))
    for l, lst in sorted(recherche.items()):
        lst.sort(key=lambda e: (netutil.normalize(e["n"]), e["t"], e["id"]))
        ecrire(os.path.join(sortie, "recherche", f"{l}.json"), lst)
    _nettoyer(os.path.join(sortie, "recherche"), {f"{l}.json" for l in recherche})

    # ---- index.json
    sources_txt = []
    arch = [a for a in annees if sources[a]["archive"]]
    cal = [a for a in annees if not sources[a]["archive"]]
    if arch:
        sources_txt.append(f"archives : saisons {arch[0]}-{arch[-1]} ({len(arch)})")
    if cal:
        sources_txt.append("calendrier : saisons " + ", ".join(str(a) for a in cal))
    index = {"generated_at": now,
             "compteurs": {"coureurs": len(COUR), "equipes_saisons": equipes_total,
                           "equipes_nationales": nationales, "courses": len(COURSES), "editions": editions_total,
                           "saisons": len(annees), "pays": len(pays_out),
                           "lignees": len(lignees_out), "coureurs_wikidata": sum(1 for c in COUR.values() if c.get("wikidata")),
                           "coureurs_historiques": len(H["legers"]), "editions_historiques": H["rapport"].get("editions_historiques", 0)},
             "saisons": annees, "saisons_archives": arch, "saisons_calendrier": cal,
             "grands_tours_par_saison": {str(a): gt_par_saison.get(a, []) for a in annees},
             "sources": sources_txt,
             "limites": ["historique des épreuves (avant nos données UCI) : vainqueur et podium depuis Wikidata seul, séries prouvées (series_historiques.json), "
                         "statuts non_attribue / conflit conservés sans être tranchés",
                         "pas d'historique du classement UCI (E1c)",
                         "Wikidata : rapprochements stricts seulement (coureur : nom + date de naissance exacte ; équipe : code UCI + période + nom), "
                         "couverture partielle selon le cache entites/wikidata/ ; code_uci seulement si les coureurs classés de la saison portent un code unique"]}
    ecrire(os.path.join(sortie, "index.json"), index, ignore=("generated_at",))

    rapport.update({
        "duree_s": round(time.time() - t0, 1), "compteurs": index["compteurs"], "fichiers_modifies": fichiers_ecrits,
        "coherence": coherence, "grands_tours_par_saison": gt_par_saison, "anomalies": {k: v for k, v in anomalies.items() if v},
        "tailles": taille_entites(sortie), "inconnues": inconnues})
    # doublons possibles : même nom normalisé et même nationalité, identifiants différents (JAMAIS fusionnés)
    groupes: Dict[Tuple, List[str]] = collections.defaultdict(list)
    for cid, c in COUR.items():
        if c.get("name"):
            groupes[(riders._nom_cle(c["name"]), c.get("nationality"))].append(cid)
    dup = sorted(sorted(v) for v in groupes.values() if len(v) > 1)
    if dup:
        rapport["anomalies"]["doublons_possibles"] = dup
    if verbose:
        print(f"[ENCYCLOPEDIE] {index['compteurs']} en {rapport['duree_s']} s ; {fichiers_ecrits} fichier(s) écrit(s)"
              f" ; cohérence riders.json : {coherence['ecarts']} écart(s) sur {coherence['coureurs_compares']}")
    return rapport


def _drapeau_pays(S: _Saison, code: str) -> Optional[str]:
    c = collections.Counter(a.get("flag") for a in S.coureurs.values() if a.get("nationality") == code and a.get("flag"))
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if c else netutil.flag_code(code)


def _lire_instantanes(archives_dir: str, annee: int, ajouter: Any) -> List[Dict[str, Any]]:
    """Instantanés du classement UCI d'une saison (`<archives_dir>/entites/classements/<année>/`, écrits par
    `collector.collecter_classements`, jamais par `construire`). Appelle `ajouter(rider_id brut, date, rang)` pour chaque ligne portant
    un rider_id et renvoie la liste [{date, raisons}] des instantanés lus (celle de index.json, restreinte aux fichiers lisibles)."""
    dossier = os.path.join(archives_dir, "entites", "classements", str(annee))
    index = collector._load(os.path.join(dossier, "index.json"), None)
    if not isinstance(index, list):
        return []
    lus = []
    for e in index:
        fiche = collector._load(os.path.join(dossier, str(e.get("fichier") or "")), None) if isinstance(e, dict) else None
        if not isinstance(fiche, dict) or not fiche.get("date"):
            continue
        for lg in fiche.get("lignes") or []:
            if isinstance(lg, list) and len(lg) >= 2 and lg[1] and isinstance(lg[0], int):
                ajouter(lg[1], fiche["date"], lg[0])
        lus.append({"date": fiche["date"], "raisons": e.get("raisons") or fiche.get("raisons") or []})
    return sorted(lus, key=lambda x: x["date"])


def _ecrire_si_change(chemin: str, data: Any, ignore: Tuple[str, ...] = ()) -> bool:
    """Comme collector._dump_if_changed, y compris pour une liste (index des équipes, recherche)."""
    if isinstance(data, dict):
        return collector._dump_if_changed(chemin, data, ignore=ignore)
    if collector._load(chemin, None) == data:
        return False
    collector._dump(chemin, data)
    return True


def _nettoyer(dossier: str, garder: Set[str]) -> None:
    """Supprime les fichiers .json devenus inutiles (données dérivées)."""
    if os.path.isdir(dossier):
        for f in os.listdir(dossier):
            if f.endswith(".json") and f not in garder:
                os.remove(os.path.join(dossier, f))


def taille_entites(sortie: str) -> Dict[str, int]:
    """Octets par sous-dossier de `sortie` (+ « total » et « fichiers »)."""
    tailles: Dict[str, int] = {}
    total = n = 0
    for racine, _, fichiers in os.walk(sortie):
        for f in fichiers:
            t = os.path.getsize(os.path.join(racine, f))
            sous = os.path.relpath(racine, sortie)
            tailles[sous if sous != "." else "(racine)"] = tailles.get(sous if sous != "." else "(racine)", 0) + t
            total += t
            n += 1
    tailles["total"] = total
    tailles["fichiers"] = n
    return dict(sorted(tailles.items()))


# --------------------------------------------------------------------------- tests

def _ligne(rid: str, rank: Optional[int], status: Optional[str] = None) -> Dict[str, Any]:
    return {"rank": rank, "status": status, "bib": None, "rider_id": rid, "time_s": None, "gap_s": None,
            "points": None, "bonus_s": None, "penalty_s": None, "uci_points": None}


def _course_test(cid: str, nom: str, pays: str, classe: str, cat: str, typ: str, debut: str, coureurs: Dict[str, Tuple],
                 stages: List[Tuple[Optional[int], str, List[Dict[str, Any]]]], final: Optional[Dict[str, Any]] = None,
                 statut: str = "finished", fin: Optional[str] = None) -> Dict[str, Any]:
    """Fiche de course minimale. coureurs : {rider_id: (nom, nationalité, flag, équipe, naissance)}."""
    return {"id": cid, "name": nom, "country": pays, "flag": pays[:2].lower(), "uci_class": classe, "category": cat,
            "race_type": typ, "start_date": debut, "end_date": fin or debut, "status": statut,
            "season": int(debut[:4]),
            "riders": {r: _sans_vide({"id": r, "name": v[0], "nationality": v[1], "flag": v[2], "is_french": v[1] == "FRA",
                                       "team": v[3], "birth_date": v[4]}) for r, v in coureurs.items()},
            "stages": [{"number": n, "date": d, "name": "Course" if n is None else f"Étape {n}", "results": {"stage": rows}}
                       for n, d, rows in stages],
            "final": final}


def _tests() -> None:
    import shutil

    # --- sélections nationales : règle documentée
    assert _est_nationale("France", ["FRA", "FRA"]) == "FRA"
    assert _est_nationale("France", ["FRA", "BEL"]) is None            # nom de pays mais coureurs d'autres nationalités
    assert _est_nationale("Great Britain", ["GBR"]) == "GBR" and _est_nationale("Hong Kong, China", ["HKG"]) == "HKG"
    assert _est_nationale("Cote D'ivoire", ["CIV"]) == "CIV" and _est_nationale("Türkiye", ["TUR"]) == "TUR"
    assert _est_nationale("Luxembourg Cycling Club", ["LUX"]) is None  # club : pas un nom de pays
    assert _est_nationale("Groupama - FDJ", ["FRA"]) is None and _est_nationale("Mula", ["INA"]) is None
    assert _est_nationale("Georgia", ["USA"]) is None                  # nom de pays, mauvaise nationalité
    assert _est_nationale("France", []) is None
    # --- grands tours : clés exactes, jamais de motif flou
    for nom, pays, gt in (("Tour de France", "FRA", "tour"), ("Giro d'Italia", "ITA", "giro"),
                          ("La Vuelta Ciclista a España", "ESP", "vuelta"), ("La Vuelta ciclista a España", "ESP", "vuelta")):
        cle = collector.cle_edition(nom, pays)
        assert _grand_tour(cle, {"race_type": "stage_race", "uci_class": "2.UWT", "status": "finished"}) == gt, nom
    fiche_gt = {"race_type": "stage_race", "uci_class": "2.UWT", "status": "finished"}
    saitama = collector.cle_edition("Tour de France Saitama Criterium", "JPN")
    assert _grand_tour(saitama, dict(fiche_gt, race_type="one_day", uci_class="1.1")) is None
    assert _grand_tour(saitama, fiche_gt) is None                      # même avec la classe : la clé n'est pas exacte
    assert _grand_tour("tour de france|FRA", dict(fiche_gt, uci_class="2.2")) is None
    assert _grand_tour("tour de france|FRA", dict(fiche_gt, status="in_progress")) is None
    assert _grand_tour(collector.cle_edition("Tour de France Femmes", "FRA"), fiche_gt) is None
    assert _grand_tour(collector.cle_edition("Giro Ciclistico d'Italia", "ITA"), fiche_gt) is None
    assert _lettre("abc") == "a" and _lettre("1x") == "_" and _lettre(None) == "_"

    P = lambda n, nat, eq, naiss: (n, nat, nat[:2].lower(), eq, naiss)   # noqa: E731
    dup, durand, lopez, martin, mart2 = ("dupont-jean-20000101", "durand-luc-19950505", "lopez-ana-19990909",
                                         "martin-paul-19990505", "gilet-nom-19900101")
    brut = "dupont-jean-2000"                       # même personne, orthographe sans jour : alias manuel
    alias_cr = {brut: dup}
    c_dup = P("Jean Dupont", "FRA", "Équipe A", "2000-01-01")
    c_dur = P("Luc Durand", "BEL", "Equipe A", "1995-05-05")           # même équipe, sans accent : même slug
    c_lop = P("Ana Lopez", "ESP", "Belgium", "1999-09-09")             # libellé « pays » mais coureurs ESP + BEL
    c_mar = P("Paul Martin", "FRA", "France", "1999-05-05")            # sélection nationale (tous FRA)
    c_gil = P("Nom Gilet", "FRA", "France", "1990-01-01")
    c_bel = P("Luc Durand", "BEL", "Belgium", "1995-05-05")

    def gc(*ids):
        return {"gc": [_ligne(r, i + 1) for i, r in enumerate(ids)]}
    tmp = tempfile.mkdtemp(prefix="encyclo_")
    try:
        A, D, OUT = (os.path.join(tmp, x) for x in ("archives", "data", "sortie"))
        os.makedirs(os.path.join(D, "races"))
        # 2023 : Tour de France (dup sous son identifiant BRUT), Saitama, faux Giro (2.1), championnat avec la sélection
        r1 = _course_test("uci-1", "Tour de France", "FRA", "2.UWT", "WT", "stage_race", "2023-07-01",
                          {brut: P("Jean Dupont", "FRA", "Équipe A", "2000-01-01"), durand: c_dur, lopez: c_lop, martin: c_mar},
                          [(1, "2023-07-01", [_ligne(durand, 1), _ligne(brut, 2), _ligne(martin, None, "DNF")]),
                           (2, "2023-07-02", [_ligne(brut, 1), _ligne(durand, 2), _ligne(lopez, 3)])],
                          gc(brut, durand, lopez), fin="2023-07-02")
        r2 = _course_test("uci-2", "Tour de France Saitama Criterium", "JPN", "1.1", ".1", "one_day", "2023-11-05",
                          {durand: c_dur}, [(None, "2023-11-05", [_ligne(durand, 1)])])
        r3 = _course_test("uci-3", "Giro d'Italia", "ITA", "2.1", ".1", "stage_race", "2023-05-01",
                          {durand: c_dur}, [(1, "2023-05-01", [_ligne(durand, 1)])], gc(durand))
        r4 = _course_test("uci-4", "Championnats nationaux", "FRA", "CN", "Champ.", "one_day", "2023-06-25",
                          {martin: c_mar, mart2: c_gil}, [(None, "2023-06-25", [_ligne(martin, 1), _ligne(mart2, 2)])])
        # 2024 : l'alias est CONTRADICTOIRE (les deux identifiants figurent) ; Tour de France gagné par dup (canonique)
        r5 = _course_test("uci-5", "Tour de France", "FRA", "2.UWT", "WT", "stage_race", "2024-07-01",
                          {dup: c_dup, durand: c_bel, brut: P("Jean Dupont", "FRA", "Équipe A", "2000-01-01")},
                          [(1, "2024-07-01", [_ligne(dup, 1), _ligne(durand, 2), _ligne(brut, 3)])], gc(dup, durand, brut))
        r6 = _course_test("uci-6", "Grand Prix Test", "BEL", "1.1", ".1", "one_day", "2024-03-01",
                          {durand: c_bel}, [(None, "2024-03-01", [_ligne(durand, 1)])])
        for an, courses, complet in ((2023, [r1, r2, r3, r4], True), (2024, [r5, r6], True)):
            for c in courses:
                collector._dump(os.path.join(A, str(an), "races", c["id"] + ".json"), c)
            collector._dump(os.path.join(A, str(an), "state.json"), {"complete": complet})
        ranking24 = {"name": "UCI World Ranking", "date": "2024-10-14", "source": "x", "rows": [
            {"rank": 3, "rider": "DUPONT Jean", "birth_date": "2000-01-01", "nationality": "FRA", "team": "Équipe A", "points": 321.5,
             "team_code": "EQA"},
            {"rank": 90, "rider": "INCONNU Zed", "birth_date": "1980-01-01", "nationality": "FRA", "team": "Equipe A", "points": 1, "team_code": "EQA"},
            {"rank": 91, "rider": "INCONNU Yan", "birth_date": "1981-01-01", "nationality": "FRA", "team": "Autre", "points": 1, "team_code": None}]}
        collector._dump(os.path.join(A, "2024", "ranking.json"), ranking24)
        collector._dump(os.path.join(A, "2024", "riders.json"), riders.build_riders([r5, r6], ranking24, season=2024))
        collector._dump(os.path.join(A, "2023", "riders.json"), riders.build_riders([r1, r2, r3, r4], None, season=2023))
        # Calendrier : saison 2025, course en cours (pas une édition), course finie ; classement du jour (sans riders-2025.json)
        r7 = _course_test("uci-7", "Tour de France", "FRA", "2.UWT", "WT", "stage_race", "2025-07-05",
                          {dup: c_dup, durand: c_bel}, [(1, "2025-07-05", [_ligne(dup, 1), _ligne(durand, 2)])],
                          None, statut="in_progress")
        r8 = _course_test("uci-8", "Grand Prix Test", "BEL", "1.1", ".1", "one_day", "2025-03-01",
                          {dup: c_dup, durand: c_bel}, [(None, "2025-03-01", [_ligne(durand, 1), _ligne(dup, 2)])])
        for c in (r7, r8):
            collector._dump(os.path.join(D, "races", c["id"] + ".json"), c)
        collector._dump(os.path.join(D, "index-2025.json"), {"races": [{"id": "uci-7"}, {"id": "uci-8"}]})
        collector._dump(os.path.join(D, "ranking.json"), {"name": "UCI World Ranking", "date": "2025-11-10", "source": "x",
                                                          "season": 2025, "rows": [{"rank": 7, "rider": "DURAND Luc", "birth_date": "1995-05-05",
                                                                                    "nationality": "BEL", "points": 99},
                                                                                   {"rank": 80, "rider": "ZED Un", "birth_date": "1980-01-01", "team": "Équipe A", "team_code": "A1"},
                                                                                   {"rank": 81, "rider": "ZED Deux", "birth_date": "1981-01-01", "team": "EQUIPE A", "team_code": "A2"}]})
        # cache Wikidata simulé (écrit par wikidata.run_wikidata en production)
        wdc = os.path.join(OUT, "wikidata")
        collector._dump(os.path.join(wdc, "coureurs.json"), {
            dup: {"qid": "Q9001", "verifie": "2026-11-01", "lieu": {"qid": "Q9100", "libelle": "Test-sur-Mer"}, "taille": 1.8, "image": "A.jpg",
                  "sitelinks": {"fr": "Jean Dupont"}, "equipes": [{"qid": "Q8001", "debut": "2019", "precision_debut": "annee"}]},
            durand: {"qid": None, "verifie": "2026-11-01", "raison": "aucune"}})
        collector._dump(os.path.join(wdc, "images.json"), {
            "A.jpg": {"url": "https://x.example/a.jpg", "page": "https://x.example/p", "auteur": "Auteur", "licence": "CC0", "verifie": "2026-11-01"},
            "L.svg": {"url": "https://x.example/l.svg", "page": "https://x.example/lp", "licence": "Public domain", "verifie": "2026-11-01"}})   # licence sans lien
        collector._dump(os.path.join(wdc, "equipes.json"), {
            "equipe-a-2024": {"qid": "Q8001", "preuve": "p", "verifie": "2026-11-01"}, "equipe-a-2025": {"qid": "Q8001", "preuve": "p", "verifie": "2026-11-01"},
            "belgium-2025": {"qid": None, "raison": "aucune", "verifie": "2026-11-01"}})
        collector._dump(os.path.join(wdc, "lignees.json"), {"Q8001": {"libelle": "Équipe Alpha (lignée)", "noms": [{"nom": "Equipe A", "debut": "2019"}],
                                                                   "logo": "L.svg", "verifie": "2026-11-01"}})
        # historique du classement UCI (E1c) : instantanés écrits par collector.collecter_classements ; alias appliqués saison par saison
        cl = os.path.join(A, "entites", "classements")
        collector._dump(os.path.join(cl, "2023", "2023-06-06.json"), {"date": "2023-06-06", "nom": "UCI World Ranking", "moment_id": 1, "raisons": ["après Tour"],
                                                                      "lignes": [[3, brut, 120.5, "EQA"], [8, durand, 80, None], [9, None, 70, None]]})
        collector._dump(os.path.join(cl, "2023", "index.json"), [{"date": "2023-06-06", "raisons": ["fin de mois", "après Tour"], "fichier": "2023-06-06.json"},
                                                                 {"date": "2023-07-04", "raisons": ["fin de mois"], "fichier": "2023-07-04.json"}])   # fichier absent : ignoré
        collector._dump(os.path.join(cl, "2024", "2024-03-05.json"), {"date": "2024-03-05", "nom": "UCI World Ranking", "moment_id": 2, "raisons": ["fin de mois"],
                                                                      "lignes": [[5, dup, 100, "EQA"], [9, durand, 60, None], [12, "inconnu-zz-19900101", 50, None]]})
        collector._dump(os.path.join(cl, "2024", "2024-02-06.json"), {"date": "2024-02-06", "nom": "UCI World Ranking", "moment_id": 3, "raisons": ["fin de mois"],
                                                                      "lignes": [[7, dup, 90, "EQA"], [4, brut, 95, None]]})
        collector._dump(os.path.join(cl, "2024", "index.json"), [{"date": "2024-02-06", "raisons": ["fin de mois"], "fichier": "2024-02-06.json"},
                                                                 {"date": "2024-03-05", "raisons": ["fin de mois"], "fichier": "2024-03-05.json"}])
        rap = construire(A, D, OUT, now="2026-01-01T00:00:00Z", alias_coureurs=alias_cr, alias_courses={}, verbose=False)
        L = lambda p: collector._load(os.path.join(OUT, p), None)   # noqa: E731
        assert rap["saisons"] == [2023, 2024, 2025] and rap["inconnues"] == 0
        assert rap["coherence"]["ecarts"] == 0 and rap["coherence"]["coureurs_compares"] >= 6, rap["coherence"]
        # grands tours : 1 par saison finie, ni Saitama ni faux Giro, pas la course en cours
        assert rap["grands_tours_par_saison"] == {2023: ["tour:uci-1"], 2024: ["tour:uci-5"], 2025: []}, rap["grands_tours_par_saison"]
        # alias : en 2023 l'identifiant brut devient canonique ; en 2024 contradiction -> brut conservé à part (rien fusionné)
        cd = L("coureurs/d.json")
        assert dup in cd
        d = cd[dup]
        assert d["historique_uci"] == [["2023-06-06", 3], ["2024-02-06", 7], ["2024-03-05", 5]], d["historique_uci"]   # trié ; 2023 : brut -> canonique
        assert cd[brut]["historique_uci"] == [["2024-02-06", 4]]                                                         # 2024 : contradiction, rien fusionné
        assert L("coureurs/d.json")[durand]["historique_uci"] == [["2023-06-06", 8], ["2024-03-05", 9]]
        assert "historique_uci" not in L("coureurs/m.json")[next(iter(L("coureurs/m.json")))]       # coureur sans instantané : champ absent
        assert L("saisons/2023.json")["instantanes_uci"] == [{"date": "2023-06-06", "raisons": ["fin de mois", "après Tour"]}]
        assert [e["date"] for e in L("saisons/2024.json")["instantanes_uci"]] == ["2024-02-06", "2024-03-05"] and "instantanes_uci" not in L("saisons/2025.json")
        assert set(d["saisons"]) == {"2025", "2024", "2023"} and list(d["saisons"]) == ["2025", "2024", "2023"]
        assert brut in cd and list(cd[brut]["saisons"]) == ["2024"]       # contradiction 2024 : identifiant brut non fusionné
        assert any("ignoré en 2024" in w for w in rap["anomalies"]["alias_ignores"])
        # palmarès (victoires + podiums) et grands tours du coureur canonique
        gt = {(x["season"], x["course"]): x for x in d["grands_tours"]}
        assert gt[(2023, "tour")]["rank"] == 1 and gt[(2024, "tour")]["rank"] == 1 and len(d["grands_tours"]) == 2
        p0 = d["palmares"][0]
        assert p0["season"] == 2025 and p0["rank"] == 1 and p0["race_id"] == "uci-7" and p0["label"] == "Étape 1"   # étape d'une course en cours
        p1 = d["palmares"][1]
        assert p1["race_id"] == "uci-8" and p1["rank"] == 2 and p1["course"] == "grand prix test|BEL" and p1["category"] == ".1"
        assert [x["date"] for x in d["palmares"]] == sorted((x["date"] for x in d["palmares"]), reverse=True)
        assert d["totaux"] == {"wins": 3, "podiums": 5, "gc_wins": 2, "seasons": 3}, d["totaux"]
        # classement UCI : riders.json (2024), ranking.json du jour (2025, rapprochement par nom/date)
        assert d["saisons"]["2024"]["uci_rank"] == 3 and d["saisons"]["2024"]["uci_points"] == 321.5
        assert "uci_rank" not in d["saisons"]["2025"]
        du = cd[durand]
        assert du["saisons"]["2025"]["uci_rank"] == 7 and "uci_rank" not in du["saisons"]["2024"]
        # équipes : slug sans accent -> « Équipe A » et « Equipe A » fusionnées ; sélection nationale marquée, « Belgium » non
        e23 = L("equipes/2023.json")
        assert set(e23) == {"equipe-a-2023", "belgium-2023", "france-2023"}, set(e23)
        assert e23["france-2023"]["nationale"] is True and e23["france-2023"]["pays"] == "FRA"
        assert "nationale" not in e23["belgium-2023"] and "nationale" not in e23["equipe-a-2023"]
        assert e23["equipe-a-2023"]["libelles"] == ["Equipe A", "Équipe A"]
        eff = {x["rider_id"]: x for x in e23["equipe-a-2023"]["effectif"]}
        assert eff[dup]["jours"] == 2 and eff[durand]["wins"] == 3 and eff[durand]["jours"] == 4, eff   # étape 1 + Saitama + faux Giro
        assert e23["equipe-a-2023"]["totaux"]["gc_wins"] == 2 and e23["equipe-a-2023"]["grands_tours"]["tour"]["rank"] == 1
        assert "code_uci" not in e23["equipe-a-2023"] and "lignee" not in e23["equipe-a-2023"]      # 2023 : pas de classement, pas de cache
        # code UCI : slug identique (« Équipe A » / « Equipe A »), code unique ; plusieurs codes (Équipe A 2025) : absent + anomalie
        e24, e25 = L("equipes/2024.json"), L("equipes/2025.json")
        assert e24["equipe-a-2024"]["code_uci"] == "EQA" and "code_uci" not in e24["belgium-2024"], e24
        assert "code_uci" not in e25["equipe-a-2025"] and any("A1" in x and "A2" in x for x in rap["anomalies"]["code_uci_multiple"])
        assert "code_uci" not in e24.get("autre-2024", {})                                              # TeamCode vide : absent
        # Wikidata : lignée et fiche coureur lues dans le cache (null : rien) ; logo sans licence lisible : absent
        assert e24["equipe-a-2024"]["lignee"] == "Q8001" and e25["equipe-a-2025"]["lignee"] == "Q8001" and "lignee" not in e25["belgium-2025"]
        lg = L("equipes/lignees.json")
        assert lg == {"Q8001": {"libelle": "Équipe Alpha (lignée)", "noms": [{"nom": "Equipe A", "debut": "2019"}],
                                "equipes": ["equipe-a-2025", "equipe-a-2024"], "saisons": [2024, 2025],
                                "logo": {"url": "https://x.example/l.svg", "page": "https://x.example/lp", "licence": "Public domain"}}}, lg   # sans licence_url
        wd = cd[dup]["wikidata"]
        assert wd["qid"] == "Q9001" and wd["lieu"]["libelle"] == "Test-sur-Mer" and wd["taille"] == 1.8 and wd["wikipedia"] == {"fr": "Jean Dupont"}
        assert wd["image"] == {"url": "https://x.example/a.jpg", "page": "https://x.example/p", "auteur": "Auteur", "licence": "CC0"}
        assert "wikidata" not in cd[durand] and rap["compteurs"]["lignees"] == 1 and rap["compteurs"]["coureurs_wikidata"] == 1
        assert any(e["t"] == "l" and e["id"] == "Q8001" and e["y"] == [2024, 2025] for e in L("recherche/l.json"))
        assert d["saisons"]["2023"]["equipe"] == "equipe-a-2023" and d["saisons"]["2023"]["team"] in ("Equipe A", "Équipe A")
        # un coureur dans la sélection nationale ET dans un club : équipe principale = le club (pas la sélection)
        assert L("coureurs/m.json")[martin]["saisons"]["2023"]["equipe"] == "france-2023"   # seule équipe connue
        idx = L("equipes/index.json")
        assert idx == sorted(idx, key=lambda t: (-t["season"], t["name"], t["id"])) and any(t.get("nationale") for t in idx)
        # courses : Tour de France 2023-2025 (la course en cours 2025 n'est pas une édition), records
        cc = L("courses/t.json")["tour de france|FRA"]
        assert [e["season"] for e in cc["editions"]] == [2024, 2023] and cc["noms"] == {"Tour de France": [2023, 2024]}
        assert [p["id"] for p in cc["editions"][0]["podium"]] == [dup, durand, brut]
        assert cc["records"]["victoires_par_coureur"] == [{"id": dup, "name": "Jean Dupont", "wins": 2}]   # alias 2023 + canonique 2024
        assert cc["records"]["victoires_par_pays"] == {"FRA": 2} and cc["classes"] == {"2024": "2.UWT", "2023": "2.UWT"}
        gp = L("courses/g.json")["grand prix test|BEL"]
        assert [e["season"] for e in gp["editions"]] == [2025, 2024]
        assert gp["records"]["victoires_par_coureur"] == [{"id": durand, "name": "Luc Durand", "wins": 2}]
        assert "tour de france saitama criterium|JPN" in L("courses/t.json")
        # saisons, pays
        s23 = L("saisons/2023.json")
        assert s23["courses"] == {"total": 4, "par_categorie": {".1": 2, "Champ.": 1, "WT": 1}} and s23["victoires_francaises"] == 2
        assert s23["source"] == "archives" and L("saisons/2025.json")["source"] == "calendrier"
        assert L("saisons/2025.json")["courses"]["en_cours"] == 1 and L("saisons/2025.json")["classement_uci"]["present"] is True
        assert L("saisons/2024.json")["classement_uci"]["final"] is True
        py = L("pays.json")
        assert py["FRA"]["nom"] == "France" and py["FRA"]["saisons"]["2023"]["coureurs"] == 3 and py["BEL"]["meilleurs"][0]["id"] == durand
        # recherche : 1re lettre de CHAQUE mot (≥ 2 lettres)
        rj = [e["n"] for e in L("recherche/j.json")], [e["n"] for e in L("recherche/d.json")]
        assert "Jean Dupont" in rj[0] and "Jean Dupont" in rj[1] and "Tour de France" in rj[1]   # « de » -> d
        assert {e["t"] for e in L("recherche/t.json")} >= {"r"} and any(e["t"] == "e" for e in L("recherche/e.json"))
        assert all(set(e) <= {"n", "t", "id", "f", "y", "nat"} for lst in (L("recherche/d.json"),) for e in lst)
        ix = L("index.json")
        assert ix["compteurs"]["editions"] == rap["compteurs"]["editions"] == 8 - 1 and ix["saisons_calendrier"] == [2025]
        # déterminisme et écriture seulement si changement
        avant = {}
        for racine, _, fs in os.walk(OUT):
            for f in fs:
                avant[os.path.join(racine, f)] = open(os.path.join(racine, f), "rb").read()
        rap2 = construire(A, D, OUT, now="2027-01-01T00:00:00Z", alias_coureurs=alias_cr, alias_courses={}, verbose=False)
        apres = {}
        for racine, _, fs in os.walk(OUT):
            for f in fs:
                apres[os.path.join(racine, f)] = open(os.path.join(racine, f), "rb").read()
        assert rap2["fichiers_modifies"] == 0 and avant == apres, "la deuxième génération doit être identique (aucune réécriture)"
        # historique (cache Wikidata de palmarès) : années absentes de nos éditions UCI seulement, coureurs légers, palmarès rattaché, records séparés
        collector._dump(os.path.join(OUT, "historique", "editions", "t.json"), {"tour de france|FRA": [
            {"annee": 1903, "qid": "Q101", "vainqueur": "Q1", "podium": [{"rang": 1, "qid": "Q1"}, {"rang": 2, "qid": "Q2"}], "statut": "ok",
             "wikipedia": {"fr": "Tour de France 1903"}, "verifie": "2026-11-16"},
            {"annee": 1999, "qid": "Q102", "podium": [{"rang": 2, "qid": "Q2"}], "statut": "non_attribue", "detail": {"p2321": ["Q1"]}, "verifie": "2026-11-16"},
            {"annee": 2023, "qid": "Q103", "vainqueur": "Q1", "podium": [{"rang": 1, "qid": "Q1"}], "statut": "ok", "verifie": "2026-11-16"}]})
        collector._dump(os.path.join(OUT, "historique", "coureurs.json"), {
            "Q1": {"nom": "Eddy Test", "nationalite": "BEL", "naissance": "1945-06-17", "naissance_precision": "jour", "verifie": "2026-11-16"},
            "Q2": {"nom": "Jean Dupont", "rider_id": brut, "verifie": "2026-11-16"}})
        rap_h = construire(A, D, OUT, now="2026-01-01T00:00:00Z", alias_coureurs=alias_cr, alias_courses={}, verbose=False)
        cc = L("courses/t.json")["tour de france|FRA"]
        assert [h["annee"] for h in cc["historique"]] == [1999, 1903], cc["historique"]            # 2023 : déjà dans nos éditions UCI
        h1903 = cc["historique"][1]
        assert h1903["vainqueur"] == "wd-Q1" and h1903["source_qid"] == "Q101" and h1903["podium"][1]["id"] == dup, h1903        # Q2 rattaché à dup (alias)
        assert cc["historique"][0]["statut"] == "non_attribue" and cc["historique"][0]["detail"]["p2321"] == [{"id": "wd-Q1", "name": "Eddy Test", "nat": "BEL", "flag": "be"}]
        assert cc["historique_info"] == {"source": "wikidata", "annees": [1903, 1999], "editions": 2}
        assert cc["records"]["victoires_par_coureur"] == [{"id": dup, "name": "Jean Dupont", "wins": 2}]                # records UCI inchangés
        assert cc["records_historique"]["annees_couvertes"] == [1903, 2024] and cc["records_historique"]["non_attribuees"] == 1
        assert {"id": "wd-Q1", "name": "Eddy Test", "wins": 1} not in cc["records_historique"]["victoires_par_coureur"]       # 1 victoire : sous le seuil
        lg = L("coureurs_historiques/01.json")["wd-Q1"]
        assert lg["name"] == "Eddy Test" and lg["birth_date"] == "1945-06-17" and lg["totaux"] == {"wins": 1, "podiums": 1} and lg["source"] == "wikidata", lg
        assert L("coureurs/d.json")[dup]["palmares_historique"] == [{"annee": 1999, "course": "tour de france|FRA", "rang": 2, "source_qid": "Q102"},
                                                                   {"annee": 1903, "course": "tour de france|FRA", "rang": 2, "source_qid": "Q101"}]
        assert L("coureurs/d.json")[dup]["palmares_historique_source"] == "wikidata" and "palmares_historique" not in L("coureurs/m.json")[martin]
        assert {"n": "Eddy Test", "t": "c", "id": "wd-Q1", "f": "be", "y": [1903, 1903]} in L("recherche/e.json")
        assert L("index.json")["compteurs"]["coureurs_historiques"] == 1 and rap_h["historique"]["editions_historiques"] == 2
        shutil.rmtree(os.path.join(OUT, "historique"))
        construire(A, D, OUT, now="2026-01-01T00:00:00Z", alias_coureurs=alias_cr, alias_courses={}, verbose=False)
        assert not os.path.exists(os.path.join(OUT, "coureurs_historiques", "01.json")) and "historique" not in L("courses/t.json")["tour de france|FRA"]
        # fichier devenu inutile : supprimé
        collector._dump(os.path.join(OUT, "coureurs", "zz.json"), {"x": 1})
        os.remove(os.path.join(A, "2023", "races", "uci-4.json"))
        construire(A, D, OUT, now="2026-01-01T00:00:00Z", alias_coureurs=alias_cr, alias_courses={}, verbose=False)
        assert not os.path.exists(os.path.join(OUT, "coureurs", "zz.json"))
        # sommes par course = agrégation de la saison entière (même définitions que riders.json)
        tout = riders._agreger([r1, r2, r3, r4])
        assert {k: v for k, v in tout[durand]["stats"].items() if v} == L("coureurs/d.json")[durand]["saisons"]["2023"]["stats"]
        # alias de courses : une clé source rejoint la clé canonique
        construire(A, D, OUT, now="2026-01-01T00:00:00Z", alias_coureurs=alias_cr,
                   alias_courses={"grand prix test|BEL": "gp test|BEL"}, verbose=False)
        assert "gp test|BEL" in L("courses/g.json") and "grand prix test|BEL" not in L("courses/g.json")
        # jeu d'essai du dépôt (tools/fixtures) : génération complète sans erreur
        fx = os.path.join(collector.RACINE, "tools", "fixtures", "data")
        if os.path.isdir(os.path.join(fx, "archives")):
            sortie_fx = os.path.join(tmp, "fx")
            rf = construire(os.path.join(fx, "archives"), fx, sortie_fx, verbose=False, alias_coureurs={}, alias_courses={},
                            wikidata_dir=os.path.join(fx, "archives", "entites", "wikidata"))
            assert rf["compteurs"]["coureurs"] > 0 and rf["compteurs"]["editions"] > 0, rf
            assert rf["compteurs"]["lignees"] == 1 and rf["compteurs"]["coureurs_wikidata"] == 1, rf["compteurs"]   # cache fictif de tools/fixtures   # (riders-2027.json du jeu d'essai est fictif : pas de contrôle de cohérence)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # --- corrections de source documentées (corrections_coureurs.json) : valeur corrigée dans l'entité, rider_id inchangé
    tmp2 = tempfile.mkdtemp(prefix="encyclo_corr_")
    avant = uci._CORRECTIONS
    try:
        A2, D2, O2 = (os.path.join(tmp2, x) for x in ("archives", "data", "sortie"))
        os.makedirs(os.path.join(D2, "races"))
        dec, ok = "decale-ana-20000105", "ok-bob-19990101"
        src = {"valeur": "2000-06-01", "uci": "2000-01-05", "source": "Wikidata Q1 (P569)", "date": "2026-11-16"}
        nat = {"valeur": "RSA", "uci": "CHN", "source": "Wikidata Q2 (P27)", "date": "2026-11-16"}
        uci._CORRECTIONS = {dec: {"birth_date": src, "nationality": nat}}
        rc = _course_test("uci-c1", "Course Test", "BEL", "1.1", ".1", "one_day", "2024-03-01",
                          {dec: ("Ana Decale", "CHN", "cn", "Équipe C", "2000-01-05"), ok: ("Bob Ok", "FRA", "fr", "Équipe C", "1999-01-01")},
                          [(None, "2024-03-01", [_ligne(dec, 1), _ligne(ok, 2)])])
        collector._dump(os.path.join(A2, "2024", "races", "uci-c1.json"), rc)
        collector._dump(os.path.join(A2, "2024", "state.json"), {"complete": True})
        construire(A2, D2, O2, now="2026-01-01T00:00:00Z", alias_coureurs={}, alias_courses={}, verbose=False)
        ent = collector._load(os.path.join(O2, "coureurs", "d.json"), {})[dec]        # même clé d'entité : le rider_id n'a pas changé
        assert ent["birth_date"] == "2000-06-01" and ent["nationality"] == "RSA" and ent["flag"] == "za", ent
        assert ent["corrections"] == [{"champ": "birth_date", "uci": "2000-01-05", "source": "Wikidata Q1 (P569)"},
                                      {"champ": "nationality", "uci": "CHN", "source": "Wikidata Q2 (P27)"}], ent
        assert "corrections" not in collector._load(os.path.join(O2, "coureurs", "o.json"), {})[ok]
        assert collector._load(os.path.join(O2, "saisons", "2024.json"), {})["victoires_par_pays"] == {"RSA": 1}
        assert "RSA" in collector._load(os.path.join(O2, "pays.json"), {}) and "CHN" not in collector._load(os.path.join(O2, "pays.json"), {})
        assert collector._load(os.path.join(A2, "2024", "races", "uci-c1.json"), {})["riders"][dec]["nationality"] == "CHN"   # fiche d'archive intacte
    finally:
        uci._CORRECTIONS = avant
        shutil.rmtree(tmp2, ignore_errors=True)
    # --- fusion « même saison » explicite (_fusion_meme_saison) : réunion sans double comptage, refus par défaut
    tmp3 = tempfile.mkdtemp(prefix="encyclo_fus_")
    try:
        A3, D3, O3 = (os.path.join(tmp3, x) for x in ("archives", "data", "sortie"))
        os.makedirs(os.path.join(D3, "races"))
        can, src = "fusion-ana-marie-20000101", "fusion-ana-20000101"
        pc, ps = ("Ana Marie Fusion", "FRA", "fr", "Équipe C", "2000-01-01"), ("Ana Fusion", "FRA", "fr", "Équipe S", "2000-01-01")
        rs = [_course_test("uci-f1", "Course F1", "BEL", "1.1", ".1", "one_day", "2024-03-01", {src: ps}, [(None, "2024-03-01", [_ligne(src, 1)])]),
              _course_test("uci-f2", "Course F2", "BEL", "1.1", ".1", "one_day", "2024-03-08", {src: ps}, [(None, "2024-03-08", [_ligne(src, 1)])]),
              _course_test("uci-f3", "Course F3", "BEL", "1.1", ".1", "one_day", "2024-03-15", {can: pc}, [(None, "2024-03-15", [_ligne(can, 1)])]),
              # course où les DEUX identifiants figurent : jamais fusionnés (double comptage possible)
              _course_test("uci-f4", "Course F4", "BEL", "1.1", ".1", "one_day", "2024-03-22", {can: pc, src: ps},
                           [(None, "2024-03-22", [_ligne(can, 2), _ligne(src, 3)])])]
        for c in rs[:3]:
            collector._dump(os.path.join(A3, "2024", "races", c["id"] + ".json"), c)
        collector._dump(os.path.join(A3, "2024", "state.json"), {"complete": True})
        L3 = lambda o: collector._load(os.path.join(o, "coureurs", "f.json"), {})      # noqa: E731
        construire(A3, D3, O3, now="2026-01-01T00:00:00Z", alias_coureurs={src: can}, alias_courses={}, verbose=False)      # par défaut : refus
        assert set(L3(O3)) == {can, src} and L3(O3)[can]["totaux"]["wins"] == 1, set(L3(O3))
        construire(A3, D3, O3, now="2026-01-01T00:00:00Z", alias_coureurs={src: can}, alias_courses={}, verbose=False, fusions=[src])
        e = L3(O3)
        assert set(e) == {can}, set(e)
        s24 = e[can]["saisons"]["2024"]
        assert s24["stats"]["wins"] == 3 and s24["stats"]["race_days"] == 3 and s24["equipe"] == "equipe-s-2024", s24     # équipe principale = plus de jours
        assert s24["equipes"] == ["equipe-s-2024", "equipe-c-2024"] and e[can]["totaux"]["wins"] == 3
        assert len(e[can]["palmares"]) == 3 and {p["race_id"] for p in e[can]["palmares"]} == {"uci-f1", "uci-f2", "uci-f3"}
        # une course avec les deux identifiants : fusion ignorée dans cette course, aucun double comptage, rien d'écrasé
        collector._dump(os.path.join(A3, "2024", "races", "uci-f4.json"), rs[3])
        construire(A3, D3, O3, now="2026-01-01T00:00:00Z", alias_coureurs={src: can}, alias_courses={}, verbose=False, fusions=[src])
        e = L3(O3)
        assert set(e) == {can, src} and e[can]["saisons"]["2024"]["stats"]["wins"] == 3 and e[can]["saisons"]["2024"]["stats"]["race_days"] == 4 \
            and e[src]["saisons"]["2024"]["stats"]["race_days"] == 1 and e[src]["totaux"]["wins"] == 0      # f4 : chaque identifiant compte une fois
        r, _ = _fusionner_ids(rs[3], {src: can})
        assert r is rs[3]
        r, ap = _fusionner_ids(rs[0], {src: can})
        assert ap == {src: can} and list(r["riders"]) == [can] and r["riders"][can]["id"] == can \
            and r["stages"][0]["results"]["stage"][0]["rider_id"] == can and rs[0]["riders"][src]["id"] == src
    finally:
        shutil.rmtree(tmp3, ignore_errors=True)
    print("[OK] encyclopedie.py : tests locaux réussis")


def _memoire_mo() -> float:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except ImportError:      # pragma: no cover (Windows)
        return 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description="Génère les fichiers d'entités de l'encyclopédie (entites/)")
    ap.add_argument("archives_dir", nargs="?", help="dossier des archives (<année>/races/…)")
    ap.add_argument("data_dir", nargs="?", help="dossier data/ du dépôt principal (Calendrier)")
    ap.add_argument("--sortie", default=None, help="défaut : <archives_dir>/entites")
    ap.add_argument("--test", action="store_true", help="tests locaux uniquement")
    args = ap.parse_args()
    if args.test or not (args.archives_dir and args.data_dir):
        _tests()
        if args.test:
            return
        ap.error("archives_dir et data_dir sont obligatoires")
    rap = construire(args.archives_dir, args.data_dir, args.sortie)
    coh = rap["coherence"]
    print(json.dumps({"duree_s": rap["duree_s"], "compteurs": rap["compteurs"], "tailles": rap["tailles"],
                      "fichiers_modifies": rap["fichiers_modifies"],
                      "coherence_riders_json": {"compares": coh["coureurs_compares"], "ecarts": coh["ecarts"]}},
                     ensure_ascii=False, indent=1))
    print(f"mémoire max : {_memoire_mo():.0f} Mo")
    for k, v in rap["anomalies"].items():
        print(f"anomalie {k} : {len(v)} (ex. {v[:3]})")


if __name__ == "__main__":
    main()
