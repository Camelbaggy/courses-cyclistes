#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UCI DataRide : colonne vertébrale du dashboard (liste des courses, étapes, classements, abandons).

Endpoints « iframe » publics (voir docs/recherche/sonde_uci.md) : saisons, Competitions, Races, Events, Results.
Toutes les valeurs viennent de l'UCI ; les seules valeurs calculées sont les temps / écarts recalculés
(temps du premier + écart, ou temps - temps du premier), toujours en secondes entières (tronquées).
Aucune fonction ne lève d'exception vers l'appelant : en cas d'échec, `[WARN]` + `None` / `[]`.

Contrat : docs/SPEC.md §4 et §5. `python uci.py` exécute les tests locaux de parsing (sans réseau).
"""

import datetime
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import netutil

BASE = "https://dataride.uci.org"
DISCIPLINE_ROUTE = 10
CATEGORY_MEN_ELITE = 22
PAGE_SIZE = 200  # le serveur plafonne peut-être : la pagination suit len(data), pas la taille demandée
_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/iframe/Results/10/"}

# Journal des libellés d'events rencontrés : (EventName, portée, clé) -> nombre (lu par l'essai et le rapport)
EVENTS_VUS: Counter = Counter()
IRM_VUS: Counter = Counter()
GARDER_BRUT = False  # diagnostic (essais) : ajoute `_rv` (ResultValue brut) à chaque Row ; jamais activé en production

# Code Irm UCI -> statut du schéma (SPEC §4.2). None = pas de statut (le coureur garde son rang).
IRM_STATUTS = {"DNF": "DNF", "ABD": "DNF", "DNS": "DNS", "OTL": "OTL", "OVL": "OTL", "LAP": "OTL",
               "DSQ": "DSQ", "DOP": "DSQ", "DNQ": "DNQ"}
IRM_SANS_STATUT = {"REC", "REL"}  # déclassements / relégations : le rang est conservé

CLES_TEMPS = ("stage", "gc", "youth", "teams")
CLES_POINTS = ("points", "mountain", "combativity")
TOUTES_CLES = ("stage", "gc", "points", "mountain", "youth", "teams", "combativity")


# --------------------------------------------------------------------------------------------------
# Utilitaires de format
# --------------------------------------------------------------------------------------------------

def _date_iso(valeur: Any) -> Optional[str]:
    """`/Date(1775944800000)/` (ms UTC, minuit heure de Paris) -> '2026-04-12'. +3 h : couvre l'heure d'été et d'hiver."""
    m = re.search(r"-?\d+", str(valeur or ""))
    if not m:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(int(m.group()) / 1000 + 3 * 3600, datetime.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return dt.date().isoformat()


PARTICULES = {"van", "von", "der", "den", "de", "del", "della", "di", "da", "dos", "du", "la", "le", "ten", "ter"}
_MOTS_COURTS = {"pro", "new", "one", "top", "bike", "cup"}  # mots ordinaires de <= 3 lettres (pas des sigles)
_SIGLES_MINUSCULES = {"a", "de", "du", "des", "la", "le", "et", "of", "the", "and", "van", "der", "den", "di", "da", "del", "by"}


def _est_majuscule(mot: str) -> bool:
    return any(c.isalpha() for c in mot) and mot == mot.upper()


def _titre_mot(mot: str) -> str:
    morceaux = re.split(r"([-'’])", mot)
    sortie = []
    for p in morceaux:
        if len(p) > 3 and p.upper().startswith("MC") and p == p.upper():
            sortie.append("Mc" + p[2:].capitalize())
        else:
            sortie.append(p.capitalize() if p not in ("-", "'", "’") else p)
    return "".join(sortie)


def split_name(display: str) -> Tuple[str, str]:
    """« VAN DER POEL Mathieu » -> ('Mathieu', 'Van der Poel'). Le nom de famille est la partie en majuscules.
    Sans partie en majuscules (ou tout en majuscules), le nom est rendu tel quel avec prénom vide."""
    mots = (display or "").split()
    i = 0
    while i < len(mots) and _est_majuscule(mots[i]):
        i += 1
    famille, prenom = mots[:i], mots[i:]
    if not famille:
        return "", " ".join(mots)
    fam = []
    for k, m in enumerate(famille):
        fam.append(m.lower() if k > 0 and m.lower() in PARTICULES else _titre_mot(m))
    return " ".join(prenom), " ".join(fam)


def display_name(display: str) -> str:
    prenom, nom = split_name(display)
    return f"{prenom} {nom}".strip()


def team_name(raw: Optional[str]) -> Optional[str]:
    """Casse lisible : « UAE TEAM EMIRATES XRG » -> « UAE Team Emirates XRG » (sigles <= 3 lettres et mots avec
    chiffre conservés ; un nom déjà en casse mixte n'est pas touché)."""
    txt = " ".join((raw or "").split())
    if not txt:
        return None
    if txt != txt.upper():
        return txt
    sortie = []
    for k, mot in enumerate(txt.split(" ")):
        def un(m: str) -> str:
            lettres = re.sub(r"[^A-Za-zÀ-ÿ]", "", m)
            if any(ch.isdigit() for ch in m):
                return m
            if m.lower() in _SIGLES_MINUSCULES and k > 0:
                return m.lower()
            if len(lettres) <= 3 and lettres and m.lower() not in _MOTS_COURTS:
                return m
            return "-".join(p.capitalize() if len(re.sub(r"[^A-Za-zÀ-ÿ]", "", p)) > 3 or p.lower() in _MOTS_COURTS else p
                            for p in m.split("-"))
        sortie.append(un(mot))
    return " ".join(sortie)


def _nation(brut: Any) -> Optional[str]:
    m = re.search(r"[A-Za-z]{3}", str(brut or ""))
    return m.group().upper() if m else None


def _entier(valeur: Any) -> Optional[int]:
    m = re.search(r"\d+", str(valeur if valeur is not None else ""))
    return int(m.group()) if m else None


def _nombre(valeur: Any) -> Optional[float]:
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    m = re.match(r"^\s*([-+]?\d+(?:[.,]\d+)?)", str(valeur))
    return float(m.group(1).replace(",", ".")) if m else None


def _nombre_propre(x: Optional[float]) -> Optional[Any]:
    if x is None:
        return None
    return int(x) if float(x).is_integer() else round(x, 2)


_RE_DUREE = re.compile(r"^(\d+(?::\d{1,2}){0,2})(?:[.,](\d+))?$")


def parse_duree(texte: str) -> Optional[float]:
    """« 73:56:26 » -> 266186 ; « 28:16.61 » -> 1696.61 ; « 13 » -> 13 ; « 6:26 » -> 386 (secondes, sans signe)."""
    m = _RE_DUREE.match((texte or "").strip())
    if not m:
        return None
    total = 0
    for p in m.group(1).split(":"):
        total = total * 60 + int(p)
    if m.group(2):
        total += float("0." + m.group(2))
    return float(total)


_MEME_TEMPS = {"s.t.", "st", "s.t", "m.t.", "mt", "m.t", "same time", "id", "id."}


# --------------------------------------------------------------------------------------------------
# Normalisation des lignes
# --------------------------------------------------------------------------------------------------

def rider_ref(ligne: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    """Ligne de Results -> (rider_id, RiderRef + birth_date). (None, {}) si le coureur n'a pas de nom."""
    brut = " ".join(str(ligne.get("DisplayName") or "").split())
    if not brut:
        return None, {}
    naissance = _date_iso(ligne.get("BirthDate"))
    rid = netutil.slugify(brut) + (("-" + naissance.replace("-", "")) if naissance else "")
    nation = _nation(ligne.get("NationName"))
    flag = (str(ligne.get("FlagCode") or "").strip().lower() or None) or netutil.flag_code(nation)
    ref = {"id": rid, "name": display_name(brut), "nationality": nation, "flag": flag,
           "is_french": nation == "FRA", "team": team_name(ligne.get("TeamName")), "birth_date": naissance}
    return rid, ref


def _statut(ligne: Dict[str, Any]) -> Optional[str]:
    irm = str(ligne.get("Irm") or "").strip().upper()
    if not irm:
        return None
    IRM_VUS[irm] += 1
    if irm in IRM_STATUTS:
        return IRM_STATUTS[irm]
    if irm not in IRM_SANS_STATUT:
        print(f"[INFO] UCI : code Irm inconnu {irm!r} (ligne conservée sans statut)")
    return None


def _rang(ligne: Dict[str, Any]) -> Optional[int]:
    r = ligne.get("RankNumber")
    if isinstance(r, int) and not isinstance(r, bool):
        return r
    txt = str(ligne.get("Rank") or "").strip()
    return int(txt) if txt.isdigit() else None


def _ordre(ligne: Dict[str, Any]) -> Tuple[int, int]:
    so = ligne.get("SortOrder")
    rang = _rang(ligne)
    return (0, so) if isinstance(so, int) else (1, rang if rang is not None else 10 ** 9)


class _Temps:
    """Convertit les ResultValue d'un classement au temps : temps absolu du premier, écarts « +0:12 », « s.t. »."""

    def __init__(self) -> None:
        self.premier: Optional[int] = None  # temps du premier en secondes entières
        self.prec_temps: Optional[int] = None
        self.prec_ecart: Optional[int] = None

    def convertir(self, valeur: Any) -> Tuple[Optional[int], Optional[int]]:
        txt = str(valeur).strip() if valeur is not None else ""
        if not txt:
            return None, None
        bas = txt.lower()
        if bas in _MEME_TEMPS:
            if self.prec_temps is None and self.prec_ecart is None:
                return None, None
            return self.prec_temps, self.prec_ecart
        if txt.startswith("+") or txt.startswith("-"):
            d = parse_duree(txt[1:].strip())
            if d is None:
                print(f"[INFO] UCI : écart illisible {txt!r}")
                return None, None
            ecart = int(d)
            temps = self.premier + ecart if self.premier is not None else None
        else:
            d = parse_duree(txt)
            if d is None:
                print(f"[INFO] UCI : temps illisible {txt!r}")
                return None, None
            t = int(d)
            if self.premier is None:
                self.premier = t
                temps, ecart = t, 0
            elif t < self.premier:  # inférieur au temps du premier : c'est un écart sans signe
                temps, ecart = self.premier + t, t
            else:
                temps, ecart = t, t - self.premier
            self.prec_temps, self.prec_ecart = temps, ecart
            return temps, ecart
        self.prec_temps, self.prec_ecart = temps, ecart
        return temps, ecart


def normalize_rows(lignes: List[Dict[str, Any]], cle: str, riders: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lignes brutes `Results` -> liste de `Row` (SPEC §4.2) ; alimente `riders`. Ordre UCI (SortOrder)."""
    temps = _Temps()
    sortie: List[Dict[str, Any]] = []
    for lg in sorted(lignes, key=_ordre):
        rid, ref = rider_ref(lg)
        if rid is None:
            continue
        riders.setdefault(rid, ref)
        statut = _statut(lg)
        row = {"rank": None if statut else _rang(lg), "status": statut, "bib": _entier(lg.get("Bib")),
               "rider_id": rid, "time_s": None, "gap_s": None, "points": None, "bonus_s": None,
               "penalty_s": None, "uci_points": None}
        pcr = lg.get("PointPcR")
        if isinstance(pcr, (int, float)) and pcr:
            row["uci_points"] = _nombre_propre(float(pcr))
        valeur = lg.get("ResultValue")
        if statut is None:
            if cle in CLES_POINTS:
                row["points"] = _nombre_propre(_nombre(valeur))
            else:
                row["time_s"], row["gap_s"] = temps.convertir(valeur)
        if GARDER_BRUT:
            row["_rv"] = valeur
        sortie.append(row)
    return sortie


def normalize_team_rows(lignes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lignes brutes d'un classement par équipes -> `TeamRow`."""
    temps = _Temps()
    sortie = []
    for lg in sorted(lignes, key=_ordre):
        nom = team_name(lg.get("TeamName")) or team_name(lg.get("DisplayName"))
        if not nom:
            continue
        statut = _statut(lg)
        t, g = (None, None) if statut else temps.convertir(lg.get("ResultValue"))
        sortie.append({"rank": None if statut else _rang(lg), "team": nom, "nationality": _nation(lg.get("NationName")),
                       "time_s": t, "gap_s": g})
    return sortie


# --------------------------------------------------------------------------------------------------
# Appels réseau
# --------------------------------------------------------------------------------------------------

def _kendo(page_taille: int, skip: int, filtres: Optional[List[Tuple[str, Any]]] = None,
           tri: Optional[Tuple[str, str]] = None, **extra: Any) -> List[Tuple[str, Any]]:
    champs: List[Tuple[str, Any]] = [("take", page_taille), ("skip", skip), ("page", skip // page_taille + 1),
                                     ("pageSize", page_taille)]
    if tri:
        champs += [("sort[0][field]", tri[0]), ("sort[0][dir]", tri[1])]
    if filtres:
        champs.append(("filter[logic]", "and"))
        for n, (champ, val) in enumerate(filtres):
            champs += [(f"filter[filters][{n}][field]", champ), (f"filter[filters][{n}][operator]", "eq"),
                       (f"filter[filters][{n}][value]", val)]
    champs += list(extra.items())
    return champs


def _post(chemin: str, champs: Any, nom: str = "") -> Optional[Any]:
    """POST poli ; une page HTML d'erreur (HTTP 200) est détectée par netutil (réponse non JSON) -> nouvel essai."""
    for essai in (1, 2):
        rep = netutil.post_form_json(BASE + chemin, champs, headers=_HEADERS, retries=2, raw_name=nom)
        if rep is not None:
            return rep
        if essai == 1:
            print(f"[WARN] UCI : {chemin} sans réponse JSON exploitable, nouvel essai")
    return None


def _liste_paginee(chemin: str, filtres: Optional[List[Tuple[str, Any]]] = None, tri: Optional[Tuple[str, str]] = None,
                   taille: int = PAGE_SIZE, nom: str = "", **extra: Any) -> Optional[List[Dict[str, Any]]]:
    """Parcourt une grille Kendo (`{"data": [...], "total": N}`) ; None si la première page échoue."""
    sortie: List[Dict[str, Any]] = []
    total = None
    for _ in range(100):
        rep = _post(chemin, _kendo(taille, len(sortie), filtres, tri, **extra), f"{nom}_{len(sortie)}")
        if not isinstance(rep, dict) or not isinstance(rep.get("data"), list):
            if not sortie:
                return None
            print(f"[WARN] UCI : {chemin} interrompu après {len(sortie)} lignes")
            return sortie
        data = rep["data"]
        total = rep.get("total", total)
        sortie += [d for d in data if isinstance(d, dict)]
        if not data or (isinstance(total, int) and len(sortie) >= total):
            break
    return sortie


def get_season_id(year: int) -> Optional[int]:
    saisons = netutil.fetch_json(f"{BASE}/iframe/GetRestrictedResultsDisciplineSeasons/?disciplineId={DISCIPLINE_ROUTE}",
                                 raw_name="uci_saisons")
    if not isinstance(saisons, list):
        print("[WARN] UCI : liste des saisons indisponible")
        return None
    for s in saisons:
        if isinstance(s, dict) and s.get("Year") == year:
            return s.get("Id")
    print(f"[WARN] UCI : saison {year} introuvable")
    return None


def list_competitions(season_id: int) -> List[Dict[str, Any]]:
    """Courses hommes élite courues ou en cours (la liste DataRide ne contient pas les courses à venir)."""
    # Les trois filtres sont obligatoires, sinon l'UCI répond une page HTML d'erreur avec HTTP 200.
    filtres = [("RaceTypeId", 0), ("CategoryId", CATEGORY_MEN_ELITE), ("SeasonId", season_id)]
    brutes = _liste_paginee("/iframe/Competitions/", filtres, ("StartDate", "asc"), taille=100,
                            nom=f"uci_competitions_{season_id}", disciplineId=DISCIPLINE_ROUTE)
    if brutes is None:
        print(f"[WARN] UCI : liste des compétitions de la saison {season_id} indisponible")
        return []
    sortie, vus = [], set()
    for c in brutes:
        cid = c.get("CompetitionId")
        if cid is None or cid in vus:
            continue
        vus.add(cid)
        pays = str(c.get("CountryIsoCode3") or "").strip().upper() or None
        debut = _date_iso(c.get("StartDate"))
        sortie.append({"competition_id": cid, "name": " ".join(str(c.get("CompetitionName") or "").split()),
                       "country": pays, "flag": (str(c.get("FlagCode") or "").strip().lower() or netutil.flag_code(pays)),
                       "uci_class": str(c.get("ClassCode") or "").strip(), "start_date": debut,
                       "end_date": _date_iso(c.get("EndDate")) or debut})
    return sortie


def list_upcoming(year: int) -> List[Dict[str, Any]]:
    """Calendrier prévisionnel : voir docs/recherche/calendrier_uci.md. [] tant qu'aucune source exploitable."""
    return []


# --------------------------------------------------------------------------------------------------
# Course complète
# --------------------------------------------------------------------------------------------------

def event_key(nom: str) -> Tuple[Optional[str], str]:
    """Libellé d'event UCI -> (clé de classement, portée). Portée « overall » (cumulé, ou résultat de la course) ou
    « stage » (variante calculée sur la seule étape : points / montagne / jeunes / équipes de l'étape)."""
    n = " ".join((nom or "").lower().split())
    portee_etape = n.startswith("stage ")
    if "youth" in n or "young" in n:
        base = "youth"
    elif "mountain" in n or "climb" in n:
        base = "mountain"
    elif "point" in n or "sprint" in n:
        base = "points"
    elif "team" in n:
        base = "teams"
    elif "combativ" in n or "aggress" in n:
        base = "combativity"
    elif "general" in n:
        return "gc", "overall"
    elif n in ("stage classification", "stage", "classification", "result", "results", "final classification"):
        return "stage", "overall"
    else:
        return None, "overall"
    return base, ("stage" if portee_etape else "overall")


def _numero_etape(nom: str) -> Tuple[Optional[int], str]:
    n = (nom or "").strip()
    if re.match(r"^prologue\b", n, re.I):
        return 0, "Prologue"
    m = re.match(r"^stage\s+(\d+)\s*([a-z])?\b", n, re.I)
    if m:
        suffixe = (m.group(2) or "").lower()
        return int(m.group(1)), f"Étape {m.group(1)}{suffixe}"
    return None, n


_TYPES_ETAPE = {"IRR": "road", "ITT": "itt", "TTT": "ttt"}


def _classements_event(ev: Dict[str, Any], cle: str, riders: Dict[str, Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    eid = ev.get("EventId")
    lignes = _liste_paginee("/iframe/Results/", taille=PAGE_SIZE, nom=f"uci_results_{eid}",
                            disciplineId=DISCIPLINE_ROUTE, eventId=eid)
    if lignes is None:
        return None
    # Un event « par équipes » (contre-la-montre par équipes) liste quand même des coureurs : on regarde les lignes.
    if cle == "teams" or not any(str(l.get("DisplayName") or "").strip() for l in lignes):
        return normalize_team_rows(lignes)
    return normalize_rows(lignes, cle, riders)


def _event_vers_classements(race_label: str, events: Any, one_day_final: bool, riders: Dict[str, Dict[str, Any]],
                            complet: List[bool]) -> Dict[str, List[Dict[str, Any]]]:
    """Récupère les classements d'un Race (étape ou Final Classification) en associant chaque Event à une clé."""
    res: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(events, list):
        return res
    for ev in events:
        nom = ev.get("EventName")
        cle, portee = event_key(nom)
        if cle == "gc" and one_day_final:
            cle = "stage"
        EVENTS_VUS[(nom, portee, cle)] += 1
        if cle is None:
            print(f"[INFO] UCI : EventName non reconnu {nom!r} ({race_label}), ignoré")
            continue
        if portee == "stage":
            continue  # variante de la seule étape : pas de clé dans le schéma (jamais substituée au cumulé)
        if cle in res:
            print(f"[INFO] UCI : deuxième event pour la clé {cle!r} ({nom!r}, {race_label}), ignoré")
            continue
        rows = _classements_event(ev, cle, riders)
        if rows is None:
            complet[0] = False
            print(f"[WARN] UCI : classement {nom!r} indisponible ({race_label})")
            continue
        res[cle] = rows
    return res


def _vide(res: Dict[str, List[Any]]) -> bool:
    return not any(res.get(k) for k in res)


def get_race(competition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Races -> Events -> Results d'une compétition. Renvoie
    {"stages", "final", "riders", "race_type", "stages_total": None, "complete"} ou None si Races est indisponible.
    Course d'un jour : une seule étape (number None) dont `results.stage` est le résultat ; `final` désigne alors le
    même dictionnaire de classements. `complete` est False si un classement n'a pas pu être lu (ne pas figer en cache)."""
    cid = competition.get("competition_id")
    nom_course = competition.get("name") or str(cid)
    races = _liste_paginee("/iframe/Races/", taille=100, nom=f"uci_races_{cid}", competitionId=cid,
                           disciplineId=DISCIPLINE_ROUTE)
    if races is None:
        print(f"[WARN] UCI : étapes de {nom_course} indisponibles")
        return None
    final_rec = [r for r in races if str(r.get("RaceCode") or "").upper() == "F" or
                 str(r.get("RaceName") or "").strip().lower() == "final classification"]
    autres = [r for r in races if r not in final_rec]
    un_jour = not autres or (len(autres) == 1 and not final_rec and _numero_etape(autres[0].get("RaceName"))[0] is None)
    riders: Dict[str, Dict[str, Any]] = {}
    complet = [True]

    stages: List[Dict[str, Any]] = []
    candidats = autres if autres else final_rec[:1]
    for r in candidats:
        numero, libelle = _numero_etape(r.get("RaceName"))
        if un_jour:
            numero, libelle = None, "Course"
        elif numero is None:
            print(f"[INFO] UCI : nom d'étape non reconnu {r.get('RaceName')!r} ({nom_course})")
        type_code = str(r.get("RaceTypeCode") or "").upper()
        if type_code not in _TYPES_ETAPE:
            print(f"[INFO] UCI : RaceTypeCode inconnu {type_code!r} ({nom_course}, {libelle}), traité comme route")
        events = _post("/iframe/Events/", {"disciplineId": DISCIPLINE_ROUTE, "raceId": r.get("Id")}, f"uci_events_{r.get('Id')}")
        if not isinstance(events, list):
            complet[0] = False
            print(f"[WARN] UCI : events de {nom_course} / {libelle} indisponibles")
            continue
        res = _event_vers_classements(f"{nom_course} / {libelle}", events, un_jour, riders, complet)
        if _vide(res):
            print(f"[INFO] UCI : {nom_course} / {libelle} sans résultat publié, ignorée")
            continue
        stages.append({"number": numero, "date": _date_iso(r.get("StartDate")), "name": libelle,
                       "start": (r.get("StartLocation") or "").strip() or None,
                       "finish": (r.get("EndLocation") or "").strip() or None,
                       "type": _TYPES_ETAPE.get(type_code, "road"), "results": res})

    # Numéros manquants (nom non reconnu) : ordre chronologique, sans inventer de libellé
    stages.sort(key=lambda s: (s["number"] is None, s["number"] if s["number"] is not None else 0, s["date"] or ""))

    final = None
    if un_jour:
        final = stages[0]["results"] if stages else None
    elif final_rec:
        events = _post("/iframe/Events/", {"disciplineId": DISCIPLINE_ROUTE, "raceId": final_rec[0].get("Id")},
                       f"uci_events_{final_rec[0].get('Id')}")
        if isinstance(events, list):
            fin = _event_vers_classements(f"{nom_course} / classement final", events, False, riders, complet)
            final = fin if not _vide(fin) else None
        else:
            complet[0] = False
            print(f"[WARN] UCI : events du classement final de {nom_course} indisponibles")

    # Dernière étape : l'UCI ne publie souvent que « Stage Classification » ; les classements cumulés de cette étape
    # sont par définition le classement final -> copiés depuis `final` uniquement pour les clés absentes.
    if final and not un_jour and stages:
        derniere = stages[-1]["results"]
        manquantes = [k for k in ("gc", "points", "mountain", "youth", "teams") if final.get(k) and not derniere.get(k)]
        for k in manquantes:
            derniere[k] = final[k]
        if manquantes:
            print(f"[INFO] UCI : {nom_course} / dernière étape : {manquantes} repris du classement final")

    return {"stages": stages, "final": final, "riders": riders, "race_type": "one_day" if un_jour else "stage_race",
            "stages_total": None, "complete": complet[0]}


# --------------------------------------------------------------------------------------------------
# Tests locaux (sans réseau) : python uci.py
# --------------------------------------------------------------------------------------------------

def _tests() -> None:
    # Durées
    assert parse_duree("5:16:52") == 5 * 3600 + 16 * 60 + 52
    assert parse_duree("73:56:26") == 73 * 3600 + 56 * 60 + 26
    assert abs(parse_duree("28:16.61") - 1696.61) < 1e-6
    assert parse_duree("13") == 13 and parse_duree("6:26") == 386 and parse_duree("00") == 0
    assert parse_duree("abc") is None and parse_duree("") is None
    # Dates
    assert _date_iso("/Date(1775944800000)/") == "2026-04-12"
    assert _date_iso("/Date(906328800000)/") == "1998-09-21"
    assert _date_iso(None) is None
    # Noms
    assert display_name("POGAČAR Tadej") == "Tadej Pogačar"
    assert display_name("VAN DER POEL Mathieu") == "Mathieu Van der Poel"
    assert display_name("DE LIE Arnaud") == "Arnaud De Lie"
    assert display_name("O'CONNOR Ben") == "Ben O'Connor"
    assert display_name("LAPORTE Christophe") == "Christophe Laporte"
    assert display_name("DUMOULIN Samuel") == "Samuel Dumoulin"
    assert display_name("GAUDU David") == "David Gaudu"
    assert display_name("MARTIN Guillaume") == "Guillaume Martin"
    assert display_name("Rider Only") == "Rider Only"
    assert split_name("SOLO") == ("", "Solo")
    assert team_name("UAE TEAM EMIRATES XRG") == "UAE Team Emirates XRG"
    assert team_name("GROUPAMA-FDJ UNITED") == "Groupama-FDJ United"
    assert team_name("TEAM VISMA | LEASE A BIKE") == "Team Visma | Lease a Bike"
    assert team_name("DECATHLON CMA CGM TEAM") == "Decathlon CMA CGM Team"
    assert team_name("COFIDIS") == "Cofidis"
    assert team_name("Q36.5 PRO CYCLING TEAM") == "Q36.5 Pro Cycling Team"
    assert team_name("") is None and team_name(None) is None
    assert _nation("FRA       ") == "FRA" and _nation(None) is None
    # Libellés d'events
    assert event_key("Stage Classification") == ("stage", "overall")
    assert event_key("Stage General Classification") == ("gc", "overall")
    assert event_key("General Classification") == ("gc", "overall")
    assert event_key("Points Classification") == ("points", "overall")
    assert event_key("Overall Points Classification") == ("points", "overall")
    assert event_key("Stage Points Classification") == ("points", "stage")
    assert event_key("Mountain Classification") == ("mountain", "overall")
    assert event_key("Stage Youth Classification") == ("youth", "stage")
    assert event_key("Overall Youth Classification") == ("youth", "overall")
    assert event_key("Team Classification") == ("teams", "overall")
    assert event_key("Bidule") == (None, "overall")
    assert _numero_etape("Stage 21") == (21, "Étape 21") and _numero_etape("Prologue") == (0, "Prologue")
    assert _numero_etape("Stage 3b") == (3, "Étape 3b") and _numero_etape("Final Classification")[0] is None

    def L(rang, nom, valeur, irm=None, nation="FRA       ", bib="1", pcr=None, so=None):
        return {"Rank": str(rang) if rang else "", "RankNumber": rang, "SortOrder": so or rang or 999, "Bib": bib,
                "DisplayName": nom, "BirthDate": "/Date(906328800000)/", "NationName": nation, "FlagCode": "fr",
                "TeamName": "COFIDIS", "ResultValue": valeur, "PointPcR": pcr, "Irm": irm}

    # Temps absolu du premier + écarts + même temps
    riders: Dict[str, Any] = {}
    rows = normalize_rows([L(1, "AAA Bob", "5:16:52", pcr=500.0), L(2, "BBB Cy", "+00"), L(3, "CCC Di", "+13"),
                           L(4, "DDD Ed", "s.t."), L(5, "EEE Fy", "+1:02:03"), L(6, "FFF Gi", "m.t."),
                           L(None, "GGG Hu", None, irm="DNF", so=7), L(None, "HHH Iv", None, irm="DNS", so=8)], "stage", riders)
    assert [r["time_s"] for r in rows[:6]] == [19012, 19012, 19025, 19025, 19012 + 3723, 19012 + 3723]
    assert [r["gap_s"] for r in rows[:6]] == [0, 0, 13, 13, 3723, 3723]
    assert rows[0]["uci_points"] == 500 and rows[1]["uci_points"] is None
    assert rows[6]["status"] == "DNF" and rows[6]["rank"] is None and rows[6]["time_s"] is None
    assert rows[7]["status"] == "DNS" and rows[0]["bib"] == 1 and rows[0]["rider_id"] == "aaa-bob-19980921"
    assert riders["aaa-bob-19980921"]["name"] == "Bob Aaa" and riders["aaa-bob-19980921"]["is_french"]
    # Tous temps absolus (contre-la-montre, fractions)
    rows = normalize_rows([L(1, "AAA Bob", "28:16.61"), L(2, "BBB Cy", "28:30.10"), L(3, "CCC Di", "29:00.99")], "stage", {})
    assert [r["time_s"] for r in rows] == [1696, 1710, 1740] and [r["gap_s"] for r in rows] == [0, 14, 44]
    # Écarts avec fraction, premier écart sans premier temps
    rows = normalize_rows([L(1, "AAA Bob", "+0:12.5"), L(2, "BBB Cy", "+1:00")], "gc", {})
    assert rows[0]["gap_s"] == 12 and rows[0]["time_s"] is None and rows[1]["gap_s"] == 60
    # Points / montagne
    rows = normalize_rows([L(1, "AAA Bob", "559"), L(2, "BBB Cy", "12.5"), L(3, "CCC Di", None)], "points", {})
    assert [r["points"] for r in rows] == [559, 12.5, None] and rows[0]["time_s"] is None
    # Statuts Irm
    rows = normalize_rows([L(None, "A B", None, irm="OTL", so=1), L(None, "C D", None, irm="ABD", so=2),
                           L(5, "E F", "+3", irm="REL", so=3)], "stage", {})
    assert [r["status"] for r in rows] == ["OTL", "DNF", None] and rows[2]["rank"] == 5
    # Lignes sans nom ignorées, tri par SortOrder
    rows = normalize_rows([L(2, "BBB Cy", "+5", so=2), L(1, "AAA Bob", "1:00:00", so=1), {"DisplayName": ""}], "stage", {})
    assert [r["rank"] for r in rows] == [1, 2]
    # Équipes
    eq = normalize_team_rows([{"Rank": "1", "RankNumber": 1, "SortOrder": 1, "TeamName": "UAE TEAM EMIRATES XRG",
                               "NationName": "UAE", "ResultValue": "3:00:00"},
                              {"Rank": "2", "RankNumber": 2, "SortOrder": 2, "TeamName": "COFIDIS", "ResultValue": "+0:12"}])
    assert eq[0]["time_s"] == 10800 and eq[1]["gap_s"] == 12 and eq[1]["time_s"] == 10812 and eq[0]["nationality"] == "UAE"
    # Paramètres Kendo : trois filtres + pagination
    ch = dict(_kendo(100, 200, [("RaceTypeId", 0), ("CategoryId", 22), ("SeasonId", 464)], ("StartDate", "asc"), disciplineId=10))
    assert ch["page"] == 3 and ch["skip"] == 200 and ch["filter[filters][2][field]"] == "SeasonId"
    print("[OK] uci.py : tests locaux réussis")


if __name__ == "__main__":
    _tests()
