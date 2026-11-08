#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calendrier prévisionnel (courses À VENIR) hommes élite, lu sur Wikipédia (API MediaWiki).

Contenu de Wikipédia sous licence CC BY-SA 4.0 : l'interface doit créditer « Wikipédia » (lien vers la licence).
Étiquette de l'API (mediawiki.org/wiki/API:Etiquette) : User-Agent honnête de `netutil`, requêtes séquentielles
(une seule requête par année : toutes les pages demandées d'un coup via `titles=A|B|C`), `maxlag=5`, reprise
après une pause si le serveur est chargé.

Pages anglaises lues pour l'année Y : « Y UCI World Tour », « Y UCI ProSeries », « Y UCI Europe Tour » (calendriers),
« Y UCI Road World Championships », « Y European Road Championships », « Y French National Road Race Championships »
(championnats : dates seulement). Une page absente est ignorée sans erreur.

Hommes élite uniquement : on ne garde que les classes 1/2.UWT, 1/2.Pro, 1/2.1 et 1/2.2 ; sont exclues les classes
U23 (2.2U, 1.2U), les Coupes des nations U23 (1.Ncup, 2.Ncup), les juniors (MJ) et tout ce qui évoque les femmes.
Le parseur est heuristique (les tableaux Wikipédia n'ont pas de format imposé) : une ligne dont un champ manque
reste dans la liste avec ce champ à None, jamais complété par une valeur inventée.
"""

import datetime
import html
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import netutil
import selection

API = "https://en.wikipedia.org/w/api.php"
MAXLAG = 5
REQUESTS = 0                                   # nombre de requêtes API émises (essai de conformité)

CALENDAR_PAGES = ["{y} UCI World Tour", "{y} UCI ProSeries", "{y} UCI Europe Tour"]
CHAMP_PAGES = {
    "{y} UCI Road World Championships": ("CM", "Championnats du monde sur route", None),
    "{y} European Road Championships": ("CC", "Championnats d'Europe sur route", None),
    "{y} UEC European Road Championships": ("CC", "Championnats d'Europe sur route", None),
    "{y} French National Road Race Championships": ("CN", "Championnats de France sur route", "FRA"),
    "{y} French National Road Championships": ("CN", "Championnats de France sur route", "FRA"),
}
PAGE_DEFAULT_CLASS = {"UCI World Tour": "UWT", "UCI ProSeries": "Pro"}

_cache: Dict[int, Dict[str, str]] = {}

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
          "nov": 11, "dec": 12}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_D = r"(\d{1,2})(?:st|nd|rd|th)?"
_Y = r"(?:,?\s*(20\d\d))?"
_DATE_PATTERNS = [
    ("dm-dm", re.compile(rf"\b{_D}\s+{_MON}{_Y}\s*-\s*{_D}\s+{_MON}{_Y}\b", re.I)),
    ("d-dm", re.compile(rf"\b{_D}\s*-\s*{_D}\s+{_MON}{_Y}\b", re.I)),
    ("md-md", re.compile(rf"\b{_MON}\s+{_D}{_Y}\s*-\s*{_MON}\s+{_D}{_Y}\b", re.I)),
    ("md-d", re.compile(rf"\b{_MON}\s+{_D}\s*-\s*{_D}{_Y}\b", re.I)),
    ("dm", re.compile(rf"\b{_D}\s+{_MON}{_Y}\b", re.I)),
    ("md", re.compile(rf"\b{_MON}\s+{_D}{_Y}\b", re.I)),
]

# Nom de pays (anglais) -> code CIO/UCI à 3 lettres.
COUNTRY_NAMES = {
    "france": "FRA", "belgium": "BEL", "netherlands": "NED", "the netherlands": "NED", "germany": "GER",
    "switzerland": "SUI", "spain": "ESP", "italy": "ITA", "united kingdom": "GBR", "great britain": "GBR",
    "england": "GBR", "scotland": "GBR", "wales": "GBR", "denmark": "DEN", "norway": "NOR", "sweden": "SWE",
    "finland": "FIN", "portugal": "POR", "austria": "AUT", "poland": "POL", "czech republic": "CZE",
    "czechia": "CZE", "slovakia": "SVK", "slovenia": "SLO", "croatia": "CRO", "hungary": "HUN", "romania": "ROU",
    "bulgaria": "BUL", "serbia": "SRB", "turkey": "TUR", "türkiye": "TUR", "turkiye": "TUR", "greece": "GRE",
    "ireland": "IRL", "luxembourg": "LUX", "lithuania": "LTU", "latvia": "LVA", "estonia": "EST", "ukraine": "UKR",
    "belarus": "BLR", "russia": "RUS", "israel": "ISR", "monaco": "MON", "andorra": "AND", "cyprus": "CYP",
    "malta": "MLT", "georgia": "GEO", "armenia": "ARM", "azerbaijan": "AZE", "kazakhstan": "KAZ",
    "bosnia and herzegovina": "BIH", "north macedonia": "MKD", "albania": "ALB", "montenegro": "MNE",
    "kosovo": "KOS", "iceland": "ISL", "morocco": "MAR", "algeria": "ALG", "tunisia": "TUN", "egypt": "EGY",
    "rwanda": "RWA", "south africa": "RSA", "united arab emirates": "UAE", "oman": "OMA", "saudi arabia": "KSA",
    "qatar": "QAT", "australia": "AUS", "new zealand": "NZL", "china": "CHN", "japan": "JPN", "south korea": "KOR",
    "taiwan": "TPE", "thailand": "THA", "indonesia": "INA", "united states": "USA", "canada": "CAN",
    "mexico": "MEX", "argentina": "ARG", "brazil": "BRA", "colombia": "COL", "chile": "CHI", "ecuador": "ECU",
    "uruguay": "URU", "costa rica": "CRC", "cuba": "CUB", "eritrea": "ERI", "ethiopia": "ETH", "malaysia": "MAS",
    "turkmenistan": "TKM", "uzbekistan": "UZB", "iran": "IRN", "india": "IND", "kenya": "KEN",
}
_ISO2_TO_CODE: Dict[str, str] = {}
for _c, _f in netutil.FLAG_CODES.items():
    _ISO2_TO_CODE.setdefault(_f, _c)


# ---------------------------------------------------------------------------------------------- API MediaWiki
def _api(params: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Une requête API (séquentielle, maxlag=5). Reprend après pause si le serveur répond « maxlag »."""
    global REQUESTS
    import urllib.parse
    qs = urllib.parse.urlencode(dict(params, format="json", formatversion="2", maxlag=str(MAXLAG)))
    for essai in range(3):
        REQUESTS += 1
        data = netutil.fetch_json(f"{API}?{qs}", retries=2)
        if not isinstance(data, dict):
            return None
        err = data.get("error")
        if isinstance(err, dict) and err.get("code") == "maxlag":
            print(f"[WARN] Wikipédia : serveur chargé (maxlag), nouvel essai dans {5 * (essai + 1)} s")
            time.sleep(5 * (essai + 1))
            continue
        if err:
            print(f"[WARN] Wikipédia : erreur API {err.get('code')}")
            return None
        return data
    return None


def _wikitexts(titles: List[str]) -> Dict[str, str]:
    """Wikitexte des pages existantes (clé = titre demandé), en UNE requête ; repli page par page si elle échoue."""
    def une_requete(lot: List[str]) -> Optional[Dict[str, str]]:
        data = _api({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                     "redirects": "1", "titles": "|".join(lot)})
        if data is None:
            return None
        q = data.get("query") or {}
        vers_final = {t: t for t in lot}
        for lien in (q.get("normalized") or []) + (q.get("redirects") or []):
            for t, f in list(vers_final.items()):
                if f == lien.get("from"):
                    vers_final[t] = lien.get("to")
        par_titre = {}
        for p in q.get("pages") or []:
            if p.get("missing") or not p.get("revisions"):
                continue
            slot = (p["revisions"][0].get("slots") or {}).get("main") or {}
            if slot.get("content"):
                par_titre[p.get("title")] = slot["content"]
        return {t: par_titre[f] for t, f in vers_final.items() if f in par_titre}

    res = une_requete(titles)
    if res is None:
        res = {}
        for t in titles:
            res.update(une_requete([t]) or {})
    return res


def fetch_pages(year: int) -> Dict[str, str]:
    """Wikitexte des pages de l'année (titre demandé -> wikitexte), mémorisés pour le passage."""
    if year not in _cache:
        titres = [p.format(y=year) for p in CALENDAR_PAGES] + [p.format(y=year) for p in CHAMP_PAGES]
        _cache[year] = _wikitexts(titres)
    return _cache[year]


# ---------------------------------------------------------------------------------------------- texte / wikitexte
def _split_top(s: str, seps: Tuple[str, ...]) -> List[str]:
    """Découpe sur les séparateurs situés hors [[…]] et {{…}}."""
    out, cur, depth, i = [], [], 0, 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            cur.append(two)
            i += 2
        elif two in ("]]", "}}"):
            depth = max(0, depth - 1)
            cur.append(two)
            i += 2
        elif depth == 0 and two in seps:
            out.append("".join(cur))
            cur = []
            i += 2
        else:
            cur.append(s[i])
            i += 1
    out.append("".join(cur))
    return out


def _strip_attrs(cell: str) -> str:
    """« rowspan=2 | texte » -> « texte » (la barre d'attributs hors liens/modèles)."""
    parts, depth, i = None, 0, 0
    while i < len(cell):
        two = cell[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            i += 2
        elif two in ("]]", "}}"):
            depth = max(0, depth - 1)
            i += 2
        elif cell[i] == "|" and depth == 0:
            parts = (cell[:i], cell[i + 1:])
            break
        else:
            i += 1
    if parts and "=" in parts[0]:
        return parts[1].strip()
    return cell.strip()


_FLAG_TPL = re.compile(r"\{\{\s*(?:flag\w*|ioc\w*|fis)\s*\|[^{}]*\}\}", re.I)


def _plain(s: str) -> str:
    """Wikitexte -> texte brut (liens réduits à leur libellé, modèles de drapeau supprimés, autres modèles dépliés)."""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = _FLAG_TPL.sub(" ", s)
    s = re.sub(r"\{\{\s*[A-Z]{3}\s*\}\}", " ", s)
    s = re.sub(r"\[\[\s*(?:File|Image|Fichier):[^\]]*\]\]", " ", s, flags=re.I)
    for _ in range(3):
        s = re.sub(r"\{\{\s*[^{}|]*\|([^{}]*)\}\}", lambda m: m.group(1).split("|")[-1].split("=")[-1], s)
    s = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("'''", "").replace("''", "")
    return " ".join(html.unescape(s).replace("\xa0", " ").split())


def _nom_course(raw: str) -> Optional[str]:
    """Nom de la course : libellé du premier lien non-fichier, sinon texte brut ; sans année en tête ni suffixe."""
    sans = re.sub(r"\[\[\s*(?:File|Image|Fichier):[^\]]*\]\]", " ", raw, flags=re.I)
    sans = _FLAG_TPL.sub(" ", sans)
    m = re.search(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]", sans)
    nom = None
    if m:
        nom = (m.group(2) or m.group(1)).strip()
        nom = re.sub(r"\s*\((?:race|cycling race|cycle race)\)$", "", nom, flags=re.I)
    if not nom:
        nom = _plain(sans)
    nom = re.sub(r"^20\d\d\s+", "", _plain(nom)).strip(" -–,;")
    return nom or None


def country_code(valeur: str) -> Optional[str]:
    v = (valeur or "").strip()
    if not v:
        return None
    if re.fullmatch(r"[A-Za-z]{3}", v) and v.upper() in netutil.FLAG_CODES:
        return v.upper()
    if v.lower() in COUNTRY_NAMES:
        return COUNTRY_NAMES[v.lower()]
    if re.fullmatch(r"[A-Z]{3}", v):
        return v
    if v.lower() in _ISO2_TO_CODE:
        return _ISO2_TO_CODE[v.lower()]
    return None


_FLAG_VALUE = re.compile(r"\{\{\s*(?:flag\w*|ioc\w*|fis)\s*\|\s*([^|{}]+)", re.I)


def pays_dans(raw: str) -> Optional[str]:
    """Premier pays trouvé dans un fragment de wikitexte : modèle de drapeau, {{FRA}}, fichier « Flag of X.svg »."""
    for m in _FLAG_VALUE.finditer(raw or ""):
        code = country_code(m.group(1))
        if code:
            return code
    m = re.search(r"\{\{\s*([A-Z]{3})\s*\}\}", raw or "")
    if m:
        return m.group(1)
    m = re.search(r"Flag of ([A-Za-z .'ü-]+?)\.(?:svg|png)", raw or "")
    if m:
        return country_code(m.group(1).replace("the ", "") if m.group(1).startswith("the ") else m.group(1))
    return None


def _pays_texte(raw: str) -> Optional[str]:
    """Pays écrit en toutes lettres (« France », « [[Belgium]] ») dans un fragment sans drapeau."""
    txt = _plain(raw)
    code = country_code(txt)
    if code:
        return code
    for part in re.split(r"[,/;]| and ", txt):
        code = country_code(part.strip())
        if code:
            return code
    return None


# ---------------------------------------------------------------------------------------------- dates
def parse_dates(texte: str, annee: int) -> Optional[Tuple[str, str]]:
    """« 19–24 January », « 31 Jan – 2 Feb », « January 19–24, 2027 », « 30 March » -> (début, fin) ISO, ou None."""
    t = _plain(texte)
    t = re.sub(r"\s*(?:[–—−‒-]|&ndash;|\bto\b)\s*", "-", t, flags=re.I)
    for kind, rx in _DATE_PATTERNS:
        m = rx.search(t)
        if not m:
            continue
        g = m.groups()
        try:
            if kind == "dm-dm":
                d1, m1, y1, d2, m2, y2 = g
            elif kind == "d-dm":
                d1, d2, m1, y1 = g
                m2, y2 = m1, y1
            elif kind == "md-md":
                m1, d1, y1, m2, d2, y2 = g
            elif kind == "md-d":
                m1, d1, d2, y1 = g
                m2, y2 = m1, y1
            elif kind == "dm":
                d1, m1, y1 = g
                d2, m2, y2 = d1, m1, y1
            else:
                m1, d1, y1 = g
                d2, m2, y2 = d1, m1, y1
            a1 = int(y1 or y2 or annee)
            a2 = int(y2 or y1 or annee)
            debut = datetime.date(a1, MONTHS[m1[:3].lower()], int(d1))
            fin = datetime.date(a2, MONTHS[m2[:3].lower()], int(d2))
            if fin < debut and not (y1 or y2):
                fin = fin.replace(year=fin.year + 1)
            if fin < debut:
                continue
            return debut.isoformat(), fin.isoformat()
        except (ValueError, KeyError):
            continue
    return None


# ---------------------------------------------------------------------------------------------- tableaux
def parse_tables(wikitexte: str) -> List[Dict[str, Any]]:
    """Tableaux `{| … |}` : {"headings": [titres de section], "headers": [noms de colonnes en minuscules],
    "rows": [[cellules brutes]]}. Les lignes uniquement composées de « ! » sont des en-têtes (la première donne
    les noms de colonnes) ; un « ! » dans une ligne de données est une cellule ordinaire."""
    wt = re.sub(r"<!--.*?-->", "", wikitexte, flags=re.S)
    wt = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", wt, flags=re.S | re.I)
    titres: List[Tuple[int, str]] = []
    tables: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    row: Optional[Dict[str, Any]] = None
    prof = 0

    def clore_table() -> None:
        entetes = [r["cells"] for r in cur["_lignes"] if r["bang"] and r["bang"] == len(r["cells"])]
        cur["headers"] = [_plain(c).lower() for c in entetes[0]] if entetes else []
        cur["rows"] = [r["cells"] for r in cur["_lignes"] if r["cells"] and r["bang"] != len(r["cells"])]
        del cur["_lignes"]
        tables.append(cur)

    for line in wt.splitlines():
        s = line.strip()
        m = re.match(r"^(={2,6})\s*(.*?)\s*\1\s*$", s)
        if m and prof == 0:
            niv = len(m.group(1))
            titres = [t for t in titres if t[0] < niv] + [(niv, _plain(m.group(2)))]
            continue
        if s.startswith("{|"):
            prof += 1
            if prof == 1:
                cur = {"headings": [t[1] for t in titres], "_lignes": []}
                row = None
            continue
        if cur is None:
            continue
        if s.startswith("|}"):
            prof -= 1
            if prof == 0:
                clore_table()
                cur = None
            continue
        if prof > 1 or s.startswith("|+"):
            continue
        if s.startswith("|-"):
            row = None
        elif s[:1] in ("|", "!"):
            bang = s[0] == "!"
            cellules = [_strip_attrs(c) for c in _split_top(s[1:], ("||", "!!") if bang else ("||",))]
            if row is None:
                row = {"cells": [], "bang": 0}
                cur["_lignes"].append(row)
            row["cells"].extend(cellules)
            row["bang"] += len(cellules) if bang else 0
        elif row is not None and row["cells"] and s:
            row["cells"][-1] += " " + s
    return tables


# ---------------------------------------------------------------------------------------------- lignes -> courses
_CLASSE_RX = re.compile(r"^[12]\.(?:UWT|Pro|HC|Ncup|\d[A-Z]*|MJ\w*|WWT|W\w*)$", re.I)
_CLASSE_PARTOUT = re.compile(r"\b([12])\.(UWT|Pro)\b", re.I)
_CLASSES_HOMMES = {"UWT", "PRO", "1", "2"}                    # suffixes retenus (hommes élite)
CODES_CHAMP = {"CN", "CC", "CM", "WC"}


def _norm_classe(txt: str) -> Optional[str]:
    """Texte -> classe UCI normalisée (« 2.uwt » -> « 2.UWT »), « CN »/« CC »/« CM », ou None."""
    t = _plain(txt).replace(" ", "")
    if t.upper() in CODES_CHAMP:
        return t.upper()
    if _CLASSE_RX.match(t):
        a, b = t.split(".", 1)
        return f"{a}.{'UWT' if b.upper() == 'UWT' else 'Pro' if b.upper() == 'PRO' else b.upper() if not b.isdigit() else b}"
    m = _CLASSE_PARTOUT.search(txt)
    if m:
        return f"{m.group(1)}.{'UWT' if m.group(2).upper() == 'UWT' else 'Pro'}"
    return None


def classe_hommes_elite(classe: Optional[str]) -> bool:
    """Vrai pour 1/2.UWT, 1/2.Pro, 1/2.1, 1/2.2 ; faux pour 2.2U, 1.Ncup, MJ, WWT…"""
    if not classe or "." not in classe:
        return classe in CODES_CHAMP
    return classe.split(".", 1)[1].upper() in _CLASSES_HOMMES


def _index_colonne(headers: List[str], *mots: str) -> Optional[int]:
    for i, h in enumerate(headers):
        if any(mot in h for mot in mots):
            return i
    return None


def ligne_vers_course(cells: List[str], headers: List[str], annee: int, classe_defaut: Optional[str],
                      indice_section: str = "") -> Optional[Dict[str, Any]]:
    """Une ligne de tableau -> UpcomingRace (sans category/flag), ou None si ce n'est pas une ligne de course
    (pas de date ou pas de nom). Champs introuvables : None."""
    brut = " ".join(cells)
    bas = brut.lower()
    if "women" in bas or "cancel" in bas or "postponed" in bas:
        return None
    n = len(cells)
    hd = headers if len(headers) == n else []
    i_date = _index_colonne(hd, "date")
    dates = parse_dates(cells[i_date], annee) if i_date is not None else None
    if dates is None:
        i_date = None
        for i, c in enumerate(cells):
            dates = parse_dates(c, annee)
            if dates:
                i_date = i
                break
    if dates is None:
        return None
    i_course = _index_colonne(hd, "race", "name", "event", "competition")
    if i_course is None or i_course == i_date:
        i_course = None
        for i, c in enumerate(cells):
            txt = _plain(c)
            if i == i_date or not re.search(r"[A-Za-zÀ-ÿ]{3}", txt) or _norm_classe(c) or country_code(txt):
                continue
            i_course = i
            break
    if i_course is None:
        return None
    nom = _nom_course(cells[i_course])
    if not nom:
        return None
    # classe : colonne dédiée, sinon cellule qui est une classe, sinon titre de section, sinon défaut de la page
    classe = None
    i_cl = _index_colonne(hd, "class", "category", "rank", "type")
    if i_cl is not None:
        classe = _norm_classe(cells[i_cl])
    if classe is None:
        for i, c in enumerate(cells):
            if i not in (i_date, i_course) and _norm_classe(c):
                classe = _norm_classe(c)
                break
    if classe is None and indice_section:
        m = re.search(r"\b([12])\.(UWT|Pro|1|2)\b", indice_section, re.I)
        if m:
            classe = _norm_classe(f"{m.group(1)}.{m.group(2)}")
    if classe is None and classe_defaut:
        un_jour = dates[0] == dates[1]
        classe = f"{'1' if un_jour else '2'}.{classe_defaut}"
    # pays : drapeau dans la cellule du nom, puis colonne pays/lieu, puis premier drapeau de la ligne
    pays = pays_dans(cells[i_course])
    if pays is None:
        i_p = _index_colonne(hd, "country", "location", "venue", "nation", "host")
        if i_p is not None:
            pays = pays_dans(cells[i_p]) or _pays_texte(cells[i_p])
    if pays is None:
        pays = pays_dans(" ".join(c for i, c in enumerate(cells) if i != i_date))
    return {"name": nom, "country": pays, "flag": netutil.flag_code(pays), "uci_class": classe,
            "category": selection.categorie_classe(classe or "") if classe and "." in classe else None,
            "start_date": dates[0], "end_date": dates[1], "source": "wikipedia"}


def parse_calendar_page(titre: str, wikitexte: str, annee: int) -> List[Dict[str, Any]]:
    """Courses hommes élite d'une page de calendrier (World Tour / ProSeries / Europe Tour)."""
    base = re.sub(r"^\d{4}\s+", "", titre)
    defaut = PAGE_DEFAULT_CLASS.get(base)
    courses: List[Dict[str, Any]] = []
    for tab in parse_tables(wikitexte):
        sections = " / ".join(tab["headings"])
        if re.search(r"women|junior|under.?23|\bu23\b|youth|mixed", sections, re.I):
            continue
        for cells in tab["rows"]:
            c = ligne_vers_course(cells, tab["headers"], annee, defaut, tab["headings"][-1] if tab["headings"] else "")
            if not c:
                continue
            if c["uci_class"] and not classe_hommes_elite(c["uci_class"]):
                continue
            courses.append(c)
    return courses


def parse_championship_page(wikitexte: str, annee: int, classe: str, nom: str,
                            pays_force: Optional[str]) -> List[Dict[str, Any]]:
    """Championnats : dates (et pays d'accueil si on le lit) depuis l'infobox ou, à défaut, le début de l'article."""
    wt = re.sub(r"<!--.*?-->", "", wikitexte, flags=re.S)
    boite = wt[:6000]
    dates = None
    for m in re.finditer(r"\|\s*(?:dates?|start_?date|date_?held)\s*=\s*([^\n]*(?:\n(?!\s*\|)[^\n]*)?)", boite, re.I):
        dates = parse_dates(m.group(1), annee)
        if dates:
            break
    if dates is None:
        dates = parse_dates(_plain(wt[:3000]), annee)
    if dates is None:
        return []
    pays = pays_force
    if pays is None:
        for m in re.finditer(r"\|\s*(?:location|host\w*|venue|city|country)\s*=\s*([^\n]*)", boite, re.I):
            pays = pays_dans(m.group(1)) or _pays_texte(m.group(1))
            if pays:
                break
    if pays is None:
        pays = pays_dans(boite)
    return [{"name": nom, "country": pays, "flag": netutil.flag_code(pays), "uci_class": classe,
             "category": "Champ.", "start_date": dates[0], "end_date": dates[1], "source": "wikipedia"}]


def parse_pages(annee: int, pages: Dict[str, str]) -> Dict[str, List[Dict[str, Any]]]:
    """titre -> courses, pour les pages obtenues (ordre : World Tour, ProSeries, Europe Tour, championnats)."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for modele in CALENDAR_PAGES:
        t = modele.format(y=annee)
        if t in pages:
            out[t] = parse_calendar_page(t, pages[t], annee)
    for modele, (classe, nom, pays) in CHAMP_PAGES.items():
        t = modele.format(y=annee)
        if t in pages:
            out[t] = parse_championship_page(pages[t], annee, classe, nom, pays)
    return out


def list_calendar(year: int) -> List[Dict[str, Any]]:
    """Calendrier hommes élite de l'année (UpcomingRace, `source` = « wikipedia »), toutes catégories confondues ;
    liste vide si Wikipédia est injoignable ou n'a pas encore la page."""
    try:
        pages = fetch_pages(year)
    except Exception as e:  # le calendrier n'est jamais bloquant
        print(f"[WARN] Wikipédia : calendrier {year} illisible : {e}")
        return []
    tout: List[Dict[str, Any]] = []
    for courses in parse_pages(year, pages).values():
        tout.extend(courses)
    return _dedoublonner(tout)


# ---------------------------------------------------------------------------------------------- dédoublonnage / sélection
_RANG = {"WT": 0, "Pro": 1, ".1": 2, ".2": 3, "Champ.": 4}


def _dedoublonner(courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Même course (nom normalisé identique ou très proche, même date de début) : on garde la mieux renseignée
    (classe la plus haute, puis celle qui a un pays)."""
    def cle(c: Dict[str, Any]) -> Tuple[int, int]:
        return _RANG.get(c.get("category") or "", 9), 0 if c.get("country") else 1

    gardees: List[Dict[str, Any]] = []
    for c in sorted(courses, key=cle):
        for g in gardees:
            if g["start_date"] == c["start_date"] and (
                    netutil.normalize(g["name"]) == netutil.normalize(c["name"])
                    or selection._noms_proches(g["name"], c["name"])):
                for champ in ("country", "flag", "uci_class", "category"):
                    if g.get(champ) is None and c.get(champ) is not None:
                        g[champ] = c[champ]
                break
        else:
            gardees.append(dict(c))
    return sorted(gardees, key=lambda c: (c["start_date"], c["name"]))


def list_upcoming(today: datetime.date) -> List[Dict[str, Any]]:
    """Courses suivies (SPEC §3) dont le début est après `today` : WT / Pro, .1 / .2 en France, championnats
    (CN en France, CC, CM) et manches FDJ United Series (catégorie « FDJ », sauf WT / Pro qui gardent leur rang
    comme dans `selection.classer`). Saisons today.year et, à partir d'octobre, today.year + 1. Triées par date."""
    import lnc
    annees = [today.year] + ([today.year + 1] if today.month >= 10 else [])
    iso = today.isoformat()
    fdj: List[Dict[str, Any]] = []
    calendrier: List[Dict[str, Any]] = []
    for a in annees:
        calendrier.extend(list_calendar(a))
        try:
            fdj.extend(lnc.get_fdj_calendar(a))
        except Exception as e:
            print(f"[WARN] LNC : calendrier {a} illisible : {e}")
    fdj = [r for r in fdj if r.get("date") and r["date"] > iso]
    sortie: List[Dict[str, Any]] = []
    for c in calendrier:
        if c["start_date"] <= iso:
            continue
        r = selection.classer(c, fdj)
        if r:
            sortie.append(dict(c, category=r[0]))
    for m in fdj:                                   # manches FDJ absentes de Wikipédia
        proche = {"name": m["name"], "start_date": m["date"], "end_date": m["date"]}
        if not any(s["category"] == "FDJ" and selection.match_fdj(s, [m]) for s in sortie) \
                and not any(selection.match_fdj(dict(proche), [m]) and s["start_date"] <= m["date"] <= s["end_date"]
                            and selection._noms_proches(s["name"], m["name"]) for s in sortie):
            sortie.append({"name": m["name"], "country": None, "flag": None, "uci_class": None, "category": "FDJ",
                           "start_date": m["date"], "end_date": m["date"], "source": "lnc"})
    return sorted(_dedoublonner(sortie), key=lambda c: (c["start_date"], c["name"]))


# ---------------------------------------------------------------------------------------------- tests locaux
def _tests() -> None:
    assert parse_dates("19–24 January", 2027) == ("2027-01-19", "2027-01-24")
    assert parse_dates("2 July – 25 July", 2027) == ("2027-07-02", "2027-07-25")
    assert parse_dates("31 Jan – 2 Feb", 2027) == ("2027-01-31", "2027-02-02")
    assert parse_dates("March 5–10, 2027", 2027) == ("2027-03-05", "2027-03-10")
    assert parse_dates("30 March", 2027) == ("2027-03-30", "2027-03-30")
    assert parse_dates("Paris–Roubaix", 2027) is None
    assert country_code("France") == "FRA" and country_code("FRA") == "FRA" and country_code("fr") == "FRA"
    assert _norm_classe("2.uwt") == "2.UWT" and _norm_classe("[[UCI World Tour|1.UWT]]") == "1.UWT"
    assert _norm_classe("1.1") == "1.1" and _norm_classe("2.2U") == "2.2U" and _norm_classe("Paris") is None
    assert classe_hommes_elite("2.Pro") and classe_hommes_elite("1.2") and not classe_hommes_elite("2.2U") \
        and not classe_hommes_elite("1.Ncup") and not classe_hommes_elite("1.WWT")
    wt = """{| class="wikitable sortable"
|-
! Date !! Race !! Country !! Class
|-
| 19–24 January || {{flagicon|AUS}} [[2027 Tour Down Under|Tour Down Under]] || [[Australia]] || 2.UWT
|-
| 2–25 July
| {{flagicon|FRA}} [[Tour de France]]
| France
| 2.UWT
|-
! scope=row | 14 February
| rowspan=1 | {{flagicon|FRA}} [[Grand Prix de la Marseillaise]]
| 1.1
|-
| 3 March || {{flagicon|BEL}} [[Women's Race]] || 1.WWT
|}
== 2.2U ==
{| class="wikitable"
|-
! Date !! Race !! Class
|-
| 1 May || {{flagicon|FRA}} [[Course U23]] || 2.2U
|}
"""
    cs = parse_calendar_page("2027 UCI Europe Tour", wt, 2027)
    noms = {c["name"]: c for c in cs}
    assert set(noms) == {"Tour Down Under", "Tour de France", "Grand Prix de la Marseillaise"}, noms.keys()
    assert noms["Tour Down Under"]["country"] == "AUS" and noms["Tour Down Under"]["category"] == "WT"
    assert noms["Tour de France"]["start_date"] == "2027-07-02" and noms["Tour de France"]["end_date"] == "2027-07-25"
    assert noms["Grand Prix de la Marseillaise"]["uci_class"] == "1.1" and noms["Grand Prix de la Marseillaise"]["flag"] == "fr"
    wt2 = "{|\n|-\n! Race !! Date\n|-\n| {{flagicon|ITA}} [[Strade Bianche]] || 6 March\n|-\n| [[Tour of X]] || 3–8 March\n|}"
    cs = parse_calendar_page("2027 UCI World Tour", wt2, 2027)
    assert [(c["name"], c["uci_class"]) for c in cs] == [("Strade Bianche", "1.UWT"), ("Tour of X", "2.UWT")], cs
    ch = parse_championship_page("{{Infobox\n| date = 19–26 September 2027\n| location = {{flagicon|FRA}} [[Haute-Savoie]]\n}}",
                                 2027, "CM", "Championnats du monde sur route", None)
    assert ch[0]["start_date"] == "2027-09-19" and ch[0]["country"] == "FRA", ch
    d = _dedoublonner([{"name": "Tour de Foo", "start_date": "2027-03-01", "end_date": "2027-03-01", "category": ".1", "country": None},
                       {"name": "Tour de Foo", "start_date": "2027-03-01", "end_date": "2027-03-01", "category": "Pro", "country": "FRA"}])
    assert len(d) == 1 and d[0]["category"] == "Pro"
    print("[OK] wikipedia_cal.py : tests locaux réussis")


if __name__ == "__main__":
    _tests()
