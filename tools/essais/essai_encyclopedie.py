#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau E0 de l'encyclopédie (docs/PLAN_ENCYCLOPEDIE.md §2, §5, §7) : sources d'identité des équipes et des
coureurs, délai de publication du classement UCI, couverture Wikidata et Wikipédia. Lecture seule, rien n'est écrit.

Lancement CI : commit contenant `[essai:encyclopedie]` sur une branche ccr-*. Durée visée : < 20 min (budget global
19 min, budget par partie ; une partie qui dépasse son budget s'arrête proprement et passe à la suivante).

Parties (chacune isolée par try/except) :
  1. DataRide `TeamCode` du classement individuel (2019, 2022, 2025, 2026, saison courante) : table par saison, lignées.
  2. Classements par équipes UCI (rankingTypeId=3) : liste, clés brutes, 5 lignes.
  3. Une ligne brute de `Results` (toutes les clés) : identifiant d'équipe ou de coureur non utilisé ?
  4. Délai de mise à jour du classement : `GetRankingMoments` croisé avec la fin des courses 1.UWT / 2.UWT.
  5. Wikidata : propriétés utiles, correspondance de 40 coureurs, 10 lignées d'équipes.
  6. Wikipédia multilingue : longueur des introductions (fr en es it nl de) pour 5 coureurs et 4 équipes.

Politesse : User-Agent honnête de netutil (descriptif, URL du projet, pas d'e-mail), une requête par seconde au plus
et par hôte (netutil.DEFAULT_DELAY = 1,2 s), `maxlag=5` sur les API MediaWiki / Wikidata, une seule tentative par
requête Wikimedia (pas d'insistance sur un 429 : netutil abandonne l'hôte). Aucun contournement.
"""
import datetime
import json
import re
import statistics
import sys
import time
import traceback
import urllib.parse
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, ".")
import netutil  # noqa: E402
import uci  # noqa: E402

FIN_GLOBAL = time.time() + 19 * 60
LIMITES = {1: 200, 2: 100, 3: 100, 4: 200, 5: 420, 6: 120}   # secondes par partie
_fin_partie = [FIN_GLOBAL]
SYNTH: List[Tuple[int, str]] = []
RESUME: Dict[int, str] = {}
REQ: Counter = Counter()
JOURS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]

_orig_fetch = netutil.fetch_text


def _compte(url, *a, **k):
    REQ[urllib.parse.urlparse(url).netloc] += 1
    return _orig_fetch(url, *a, **k)


netutil.fetch_text = _compte


def ok() -> bool:
    return time.time() < min(FIN_GLOBAL, _fin_partie[0])


def titre(s: str) -> None:
    print(f"\n{'#' * 8} {s}", flush=True)


def synth(n: int, texte: str) -> None:
    SYNTH.append((n, texte))
    print(f"   >> {texte}", flush=True)


def court(x: Any, n: int = 300) -> str:
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"


def jour(iso: Optional[str]) -> str:
    try:
        return JOURS[datetime.date.fromisoformat(iso).weekday()]
    except (TypeError, ValueError):
        return "?"


# ---------------------------------------------------------------------------------------------------------------
# DataRide : saisons, classements
# ---------------------------------------------------------------------------------------------------------------
_SAISONS: Dict[int, int] = {}
_CLASSEMENTS: Dict[int, List[Dict[str, Any]]] = {}
_INDIV: Dict[int, Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]] = {}


def saison_id(annee: int) -> Optional[int]:
    if not _SAISONS:
        rep = netutil.fetch_json(f"{uci.BASE}/iframe/GetRestrictedResultsDisciplineSeasons/?disciplineId={uci.DISCIPLINE_ROUTE}",
                                 raw_name="enc_saisons")
        for s in rep if isinstance(rep, list) else []:
            if isinstance(s, dict) and s.get("Year") and s.get("Id"):
                _SAISONS[s["Year"]] = s["Id"]
    return _SAISONS.get(annee)


def classements(sid: int) -> List[Dict[str, Any]]:
    if sid not in _CLASSEMENTS:
        try:
            _CLASSEMENTS[sid] = uci_ranking_list(sid)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] list_rankings({sid}) : {e}")
            _CLASSEMENTS[sid] = []
    return _CLASSEMENTS[sid]


def uci_ranking_list(sid: int) -> List[Dict[str, Any]]:
    import uci_ranking
    return uci_ranking.list_rankings(sid)


def lignes_classement(sid: int, cl: Dict[str, Any], type_id: int, max_lignes: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
    """Lignes BRUTES (toutes les clés DataRide) d'un classement ; `max_lignes` = une seule page de cette taille."""
    filtres = [("RaceTypeId", 0), ("CategoryId", uci.CATEGORY_MEN_ELITE), ("SeasonId", sid), ("MomentId", cl["moment_id"])]
    extra = dict(rankingId=cl["id"], disciplineId=uci.DISCIPLINE_ROUTE, rankingTypeId=type_id)
    if max_lignes:
        rep = uci._post("/iframe/ObjectRankings/", uci._kendo(max_lignes, 0, filtres, None, **extra), f"enc_rk_{sid}_{cl['id']}")
        return rep.get("data") if isinstance(rep, dict) else None
    return uci._liste_paginee("/iframe/ObjectRankings/", filtres, None, taille=1000, nom=f"enc_rk_{sid}_{cl['id']}", **extra)


def individuel(annee: int) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """(entrée de classement, lignes brutes) du classement individuel de la saison : World Ranking si présent."""
    if annee in _INDIV:
        return _INDIV[annee]
    res: Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]] = (None, [])
    sid = saison_id(annee)
    if sid is not None:
        lst = [r for r in classements(sid) if r["type_id"] == 1 and r["id"] is not None]
        choix = [r for r in lst if r["group_id"] == 1] or lst
        if choix:
            lignes = lignes_classement(sid, choix[0], 1)
            res = (choix[0], lignes or [])
        else:
            print(f"[INFO] saison {annee} : aucun classement individuel ({[(r['group_id'], r['type_id']) for r in classements(sid)][:10]})")
    _INDIV[annee] = res
    return res


# ===============================================================================================================
# Partie 1 : TeamCode
# ===============================================================================================================
LIGNEES = {
    "Quick-Step": r"QUICK", "Jumbo / Visma": r"JUMBO|VISMA", "Lotto": r"LOTTO", "DSM / Sunweb / Picnic": r"DSM|SUNWEB|PICNIC",
    "UAE": r"\bUAE\b", "Groupama-FDJ": r"FDJ|GROUPAMA", "AG2R / Decathlon": r"AG2R|DECATHLON|CITRO",
    "Movistar": r"MOVISTAR", "Cofidis": r"COFIDIS", "Israel": r"ISRAEL|PREMIER TECH|\bNSN\b",
}


def partie1() -> None:
    annees = [2019, 2022, 2025, 2026]
    cour = uci.season_for(datetime.date.today())
    if cour and cour not in annees:
        annees.append(cour)
    par_saison: Dict[int, List[Dict[str, Any]]] = {}
    for a in annees:
        if not ok():
            print("[BUDGET] partie 1 interrompue")
            break
        cl, lignes = individuel(a)
        if not lignes:
            print(f"\n-- saison {a} : classement individuel indisponible")
            continue
        par_saison[a] = lignes
        print(f"\n-- saison {a} : {cl['group_name']!r} (id {cl['id']}), {len(lignes)} lignes ; clés d'une ligne : {sorted(lignes[0].keys())}")
        paires = Counter((str(lg.get("TeamCode") or "").strip(), " ".join(str(lg.get("TeamName") or "").split())) for lg in lignes)
        sans_code = sum(n for (c, _), n in paires.items() if not c)
        sans_nom = sum(n for (_, nm), n in paires.items() if not nm)
        codes = {c for c, _ in paires if c}
        noms = {nm for _, nm in paires if nm}
        c2n: Dict[str, set] = defaultdict(set)
        n2c: Dict[str, set] = defaultdict(set)
        for (c, nm) in paires:
            if c and nm:
                c2n[c].add(nm)
                n2c[nm].add(c)
        print(f"   lignes sans TeamCode {sans_code} ({100 * sans_code // len(lignes)} %), sans TeamName {sans_nom} ; {len(codes)} codes, {len(noms)} noms ;"
              f" codes à plusieurs noms {sum(1 for v in c2n.values() if len(v) > 1)} ; noms à plusieurs codes {sum(1 for v in n2c.values() if len(v) > 1)}")
        print("   TeamCode | TeamName | coureurs (équipes avec >= 5 coureurs classés, max 70 lignes)")
        grosses = sorted([(c, nm, n) for (c, nm), n in paires.items() if n >= 5], key=lambda t: (t[0] or "~", t[1]))
        for c, nm, n in grosses[:70]:
            print(f"   {c or '-':<6} | {nm[:48]:<48} | {n}")
        if len(grosses) > 70:
            print(f"   … {len(grosses) - 70} autres équipes")
    if not par_saison:
        raise RuntimeError("aucun classement lu")

    # --- lignées connues
    print("\n-- Lignées : code(s) par saison (code dominant ; nom UCI correspondant)")
    stables = 0
    for lignee, motif in LIGNEES.items():
        domin: Dict[int, str] = {}
        lignes_aff = []
        for a, lignes in par_saison.items():
            c = Counter((str(lg.get("TeamCode") or "").strip(), " ".join(str(lg.get("TeamName") or "").split()))
                        for lg in lignes if re.search(motif, str(lg.get("TeamName") or "").upper()))
            if not c:
                lignes_aff.append(f"{a}: (absente)")
                continue
            (code, nom), n = c.most_common(1)[0]
            domin[a] = code
            autres = [f"{cd or '-'}/{nm[:20]}x{k}" for (cd, nm), k in c.most_common(3)[1:]]
            lignes_aff.append(f"{a}: {code or '-'} «{nom[:34]}» x{n}" + (f" (+ {', '.join(autres)})" if autres else ""))
        stable = len(set(domin.values())) == 1 and len(domin) >= 2
        stables += stable
        print(f"   {lignee:<22} {'STABLE' if stable else 'VARIE ' if len(domin) >= 2 else '?     '} | " + " | ".join(lignes_aff))
    synth(1, f"lignées à code dominant identique sur toutes les saisons où elles existent : {stables}/{len(LIGNEES)}")

    # --- stabilité générale : un même code garde-t-il son sens quand le nom change ?
    codes_saison: Dict[str, Dict[int, str]] = defaultdict(dict)
    for a, lignes in par_saison.items():
        for lg in lignes:
            c, nm = str(lg.get("TeamCode") or "").strip(), " ".join(str(lg.get("TeamName") or "").split())
            if c and nm:
                codes_saison[c].setdefault(a, nm)
    multi = {c: v for c, v in codes_saison.items() if len(v) >= 2}
    change = {c: v for c, v in multi.items() if len(set(v.values())) > 1}
    print(f"\n-- Codes présents sur >= 2 saisons : {len(multi)} ; dont le nom change : {len(change)} (exemples, 15 max)")
    for c, v in list(change.items())[:15]:
        print(f"   {c}: " + " -> ".join(f"{a}:{nm[:28]}" for a, nm in sorted(v.items())))
    synth(1, f"{len(multi)} codes vus sur >= 2 saisons parmi {len(codes_saison)} ; {len(change)} changent de nom (code stable malgré le nom, ou code réattribué : voir exemples)")


# ===============================================================================================================
# Partie 2 : classements par équipes
# ===============================================================================================================
def partie2() -> None:
    sid = saison_id(2025)
    if sid is None:
        raise RuntimeError("saison 2025 introuvable")
    # Entrées brutes de RankingsDiscipline : clés d'un classement (pour repérer pays / catégorie d'équipe éventuels)
    filtres = [("RaceTypeId", 0), ("CategoryId", uci.CATEGORY_MEN_ELITE), ("SeasonId", sid)]
    brut = uci._post("/iframe/RankingsDiscipline/", uci._kendo(100, 0, filtres, None, disciplineId=uci.DISCIPLINE_ROUTE), "enc_rd")
    groupes = brut.get("data") if isinstance(brut, dict) else brut
    if isinstance(groupes, list) and groupes and isinstance(groupes[0], dict):
        g = groupes[0]
        print("clés d'un groupe :", sorted(g.keys()))
        r0 = (g.get("Rankings") or [{}])[0]
        print("clés d'un classement :", sorted(r0.keys()))
        aperc = r0.get("ObjectRankings") or []
        if aperc:
            print("aperçu intégré dans RankingsDiscipline (1re ligne) :", court(aperc[0], 400))
    lst = classements(sid)
    equipes = [r for r in lst if r["type_id"] == 3]
    print(f"\nSaison 2025 : {len(lst)} classements, dont {len(equipes)} par équipes (type 3) :")
    for r in equipes:
        print(f"   groupe {r['group_id']} {r['group_name']!r} ; classement id {r['id']} {r['name']!r} ; moment {r['moment_id']}")
    print("types présents :", dict(Counter(r["type_id"] for r in lst)))
    if not equipes:
        synth(2, "aucun classement par équipes listé pour 2025")
        return
    cl = next((r for r in equipes if r["group_id"] == 1), equipes[0])
    lignes = lignes_classement(sid, cl, 3)
    if not lignes:
        raise RuntimeError(f"classement équipes {cl['id']} vide ou illisible")
    print(f"\nClassement lu : {cl['name']!r} ({len(lignes)} lignes). Clés brutes d'une ligne : {sorted(lignes[0].keys())}")
    print("Ligne brute 1 :", court(lignes[0], 700))
    print("5 premières lignes :")
    for lg in lignes[:5]:
        print("  ", court(lg, 420))
    cles = set().union(*[set(lg.keys()) for lg in lignes])
    interessantes = sorted(k for k in cles if re.search(r"code|country|nation|categ|class|type|iso|flag|team", k, re.I))
    print("clés pouvant porter un code, un pays ou une catégorie :", interessantes)
    for k in interessantes:
        vals = Counter(str(lg.get(k)).strip() for lg in lignes)
        print(f"   {k}: {len(vals)} valeurs distinctes ; fréquentes : {vals.most_common(6)}")
    synth(2, f"classement équipes 2025 : {len(lignes)} lignes ; clés {sorted(cles)}")
    # même classement les saisons précédentes : disponible ?
    for a in (2019, 2022):
        if not ok():
            break
        s = saison_id(a)
        if s is None:
            continue
        eq = [r for r in classements(s) if r["type_id"] == 3]
        if eq:
            ech = lignes_classement(s, eq[0], 3, max_lignes=3) or []
            print(f"saison {a} : {len(eq)} classements équipes ; échantillon : {[ (l.get('TeamName'), l.get('TeamCode')) for l in ech]}")
        else:
            print(f"saison {a} : aucun classement par équipes")


# ===============================================================================================================
# Partie 3 : ligne brute de Results
# ===============================================================================================================
def _cles_lues(*fichiers: str) -> set:
    cles = set()
    for f in fichiers:
        try:
            with open(f, encoding="utf-8") as h:
                cles |= set(re.findall(r"""\.get\(\s*["'](\w+)["']""", h.read()))
        except OSError:
            pass
    return cles


def _resultats(event_id: Any, n: int = 200) -> List[Dict[str, Any]]:
    rep = uci._post("/iframe/Results/", uci._kendo(n, 0, None, None, disciplineId=uci.DISCIPLINE_ROUTE, eventId=event_id), f"enc_res_{event_id}")
    return [d for d in (rep.get("data") if isinstance(rep, dict) else None) or [] if isinstance(d, dict)]


def _events(race_id: Any) -> List[Dict[str, Any]]:
    rep = uci._post("/iframe/Events/", {"disciplineId": uci.DISCIPLINE_ROUTE, "raceId": race_id}, f"enc_ev_{race_id}")
    return rep if isinstance(rep, list) else []


def analyser_lignes(lignes: List[Dict[str, Any]], etiquette: str, lues: set) -> None:
    if not lignes:
        print(f"[INFO] {etiquette} : aucune ligne")
        return
    print(f"\n-- {etiquette} : {len(lignes)} lignes lues. LIGNE BRUTE COMPLÈTE (toutes les clés) :")
    for k in sorted(lignes[0]):
        print(f"     {k} = {court(lignes[0][k], 160)}")
    comptes = Counter()
    for lg in lignes:
        for k, v in lg.items():
            if v not in (None, "", 0, False):
                comptes[k] += 1
    print(f"   clés non vides (sur {len(lignes)} lignes) : " + ", ".join(f"{k}:{comptes.get(k, 0)}" for k in sorted(lignes[0])))
    non_lues = [k for k in sorted(set().union(*[set(lg) for lg in lignes])) if k not in lues]
    print(f"   clés jamais lues par uci.py / uci_ranking.py : {non_lues}")
    ident = [k for k in non_lues if re.search(r"id|code|uci|team|rider|licen", k, re.I)]
    print(f"   parmi elles, candidates (identifiant / code) : {ident}")
    synth(3, f"{etiquette} : clés inutilisées {non_lues}")


def partie3() -> None:
    sid = saison_id(2025)
    if sid is None:
        raise RuntimeError("saison 2025 introuvable")
    comps = uci.list_competitions(sid)
    lues = _cles_lues("uci.py", "uci_ranking.py")
    print(f"{len(comps)} compétitions 2025 ; {len(lues)} clés lues par uci.py / uci_ranking.py")
    uwt1 = next((c for c in comps if c["uci_class"] == "1.UWT"), None)
    uwt2 = next((c for c in comps if c["uci_class"] == "2.UWT"), None)
    # course d'un jour
    if uwt1:
        print(f"\nCourse d'un jour : {uwt1['name']} ({uwt1['uci_class']}, {uwt1['start_date']})")
        races = uci._liste_paginee("/iframe/Races/", taille=100, nom="enc_races1", competitionId=uwt1["competition_id"], disciplineId=uci.DISCIPLINE_ROUTE) or []
        if races:
            evs = _events(races[0].get("Id"))
            print("   events :", [e.get("EventName") for e in evs][:8])
            if evs:
                analyser_lignes(_resultats(evs[0].get("EventId")), f"Results de {uwt1['name']} / {evs[0].get('EventName')}", lues)
    # course par étapes : classement par équipes (clé teams) s'il existe
    if uwt2 and ok():
        print(f"\nCourse par étapes : {uwt2['name']} ({uwt2['start_date']})")
        races = uci._liste_paginee("/iframe/Races/", taille=100, nom="enc_races2", competitionId=uwt2["competition_id"], disciplineId=uci.DISCIPLINE_ROUTE) or []
        print("   étapes :", [r.get("RaceName") for r in races][:6])
        cible = next((r for r in races if str(r.get("RaceCode") or "").upper() == "F"), races[0] if races else None)
        if cible:
            evs = _events(cible.get("Id"))
            print("   events :", [e.get("EventName") for e in evs][:10])
            eq = next((e for e in evs if (uci.event_key(e.get("EventName"))[0] == "teams")), None)
            if eq:
                analyser_lignes(_resultats(eq.get("EventId"), 60), f"Results {uwt2['name']} / {eq.get('EventName')} (par équipes)", lues)
            else:
                print("   pas d'event par équipes dans cette étape/classement final")
                if evs:
                    analyser_lignes(_resultats(evs[0].get("EventId"), 60), f"Results {uwt2['name']} / {evs[0].get('EventName')}", lues)


# ===============================================================================================================
# Partie 4 : délai de mise à jour du classement
# ===============================================================================================================
def dates_de(m: Dict[str, Any]) -> List[str]:
    sortie = []
    for v in m.values():
        s = str(v)
        if "/Date(" in s:
            d = uci._date_iso(s)
            if d:
                sortie.append(d)
        for jj, mm, aaaa in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", s):
            try:
                sortie.append(datetime.date(int(aaaa), int(mm), int(jj)).isoformat())
            except ValueError:
                pass
        sortie += re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", s)
    return sorted(set(sortie))


def moments(annee: int) -> List[Tuple[str, Dict[str, Any]]]:
    sid = saison_id(annee)
    cl, _ = (None, [])
    if sid is None:
        return []
    lst = [r for r in classements(sid) if r["type_id"] == 1 and r["group_id"] == 1 and r["id"] is not None]
    if not lst:
        print(f"[INFO] saison {annee} : pas de World Ranking")
        return []
    cl = lst[0]
    rep = netutil.fetch_json(f"{uci.BASE}/iframe/GetRankingMoments/?disciplineId={uci.DISCIPLINE_ROUTE}&disciplineSeasonId={sid}&rankingId={cl['id']}",
                             retries=2, raw_name=f"enc_mom_{annee}")
    if not isinstance(rep, list):
        print(f"[WARN] moments {annee} indisponibles : {court(rep, 150)}")
        return []
    print(f"\n-- Moments du World Ranking {annee} (rankingId {cl['id']}) : {len(rep)} entrées ; 2 premières brutes : {court(rep[:2], 400)}")
    sortie = []
    for m in rep:
        if isinstance(m, dict):
            ds = dates_de(m)
            if ds:
                sortie.append((ds[-1], m))
    sortie.sort(key=lambda t: t[0])
    print(f"   {len(sortie)} moments datés ; du {sortie[0][0] if sortie else '?'} au {sortie[-1][0] if sortie else '?'}")
    sem = Counter(jour(d) for d, _ in sortie)
    print(f"   jours de la semaine des moments : {dict(sem)}")
    print("   10 derniers :", ", ".join(f"{d} ({jour(d)})" for d, _ in sortie[-10:]))
    return sortie


def partie4() -> None:
    tous: List[str] = []
    for a in (2025, 2026, 2027):
        if not ok():
            break
        tous += [d for d, _ in moments(a)]
    tous = sorted(set(tous))
    if not tous:
        raise RuntimeError("aucun moment daté")
    ecarts_moments = [(datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days for a, b in zip(tous, tous[1:])]
    print(f"\n{len(tous)} moments distincts (2025-2027) ; écart entre moments consécutifs : {dict(Counter(ecarts_moments).most_common(6))}")
    courses: List[Dict[str, Any]] = []
    for a in (2025, 2026):
        sid = saison_id(a)
        if sid is not None and ok():
            courses += [c for c in uci.list_competitions(sid) if c["uci_class"] in ("1.UWT", "2.UWT") and c["end_date"]]
    courses.sort(key=lambda c: c["end_date"])
    print(f"{len(courses)} courses 1.UWT / 2.UWT (2025 + 2026)")
    print("   course | classe | fin (jour) | 1er moment postérieur (jour) | délai j")
    delais, par_an, meme_jour = [], defaultdict(list), 0
    for c in courses:
        fin = c["end_date"]
        suiv = next((d for d in tous if d > fin), None)
        if fin in tous:
            meme_jour += 1
        if suiv is None:
            continue
        dl = (datetime.date.fromisoformat(suiv) - datetime.date.fromisoformat(fin)).days
        delais.append(dl)
        par_an[fin[:4]].append(dl)
        if len(delais) <= 60:
            print(f"   {c['name'][:36]:<36} | {c['uci_class']} | {fin} ({jour(fin)}) | {suiv} ({jour(suiv)}) | {dl}")
    if len(delais) > 60:
        print(f"   … {len(delais) - 60} autres courses non affichées")
    if not delais:
        raise RuntimeError("aucun croisement course / moment")
    jours_pub = Counter(jour(d) for d in tous)
    med = statistics.median(delais)
    synth(4, f"{len(tous)} moments ; jour de publication habituel {jours_pub.most_common(2)} ; délai médian fin de course -> 1er moment suivant : {med} j "
             f"(min {min(delais)}, max {max(delais)}, répartition {dict(sorted(Counter(delais).items()))}) ; courses dont la fin coïncide avec un moment : {meme_jour}")
    print("   (la date d'un moment est la date de calcul du classement : la publication réelle peut être plus tardive)")


# ===============================================================================================================
# Wikimedia : accès
# ===============================================================================================================
WD_API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
WIKIS = ["fr", "en", "es", "it", "nl", "de", "be"]
CANDIDATES: Dict[str, str] = {}      # propriétés d'identifiant trouvées par libellé : {Pnnn: libellé}


def api(url_base: str, **params: Any) -> Optional[Any]:
    params.setdefault("format", "json")
    params.setdefault("maxlag", "5")
    url = url_base + "?" + urllib.parse.urlencode(params)
    for _ in range(2):
        rep = netutil.fetch_json(url, retries=1)
        if isinstance(rep, dict) and isinstance(rep.get("error"), dict) and rep["error"].get("code") == "maxlag":
            print("[INFO] maxlag : pause de 6 s")
            time.sleep(6)
            continue
        return rep
    return None


def sparql(requete: str) -> Optional[List[Dict[str, str]]]:
    url = SPARQL + "?" + urllib.parse.urlencode({"query": requete, "format": "json"})
    rep = netutil.fetch_json(url, retries=1)
    if not isinstance(rep, dict) or "results" not in rep:
        return None
    return [{k: v.get("value", "") for k, v in b.items()} for b in rep["results"].get("bindings", [])]


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def jetons(nom: str) -> frozenset:
    return frozenset(netutil.normalize(nom).split())


# ===============================================================================================================
# Partie 5 : Wikidata
# ===============================================================================================================
def trouver_proprietes() -> None:
    print("-- (a) Propriétés par libellé (wbsearchentities type=property)")
    termes = ["UCI", "UCI rider ID", "UCI team code", "ProCyclingStats", "FirstCycling", "cycling archives", "CQ Ranking"]
    for t in termes:
        if not ok():
            break
        rep = api(WD_API, action="wbsearchentities", search=t, language="en", uselang="en", type="property", limit=10)
        res = rep.get("search", []) if isinstance(rep, dict) else []
        print(f"   « {t} » : " + (" ; ".join(f"{r.get('id')} {r.get('label')!r} ({court(r.get('description') or '', 60)})" for r in res) or "aucun résultat"))
        for r in res:
            texte = f"{r.get('label') or ''} {r.get('description') or ''}"
            if re.search(r"cycl|\bUCI\b|ProCyclingStats|FirstCycling", texte, re.I) and re.search(r"\bID\b|code|identifier|rider|team|person|cyclist", texte, re.I):
                CANDIDATES[r["id"]] = r.get("label") or ""
    print(f"   -> propriétés retenues comme candidates : {CANDIDATES}")
    ids = "|".join(["P569", "P19", "P2048", "P18", "P54", "P580", "P582", "P1448", "P1365", "P1366", "P5138"])
    rep = api(WD_API, action="wbgetentities", ids=ids, props="labels|descriptions", languages="en")
    if isinstance(rep, dict):
        print("   propriétés utilisées plus bas (vérification du sens) :")
        for pid, e in (rep.get("entities") or {}).items():
            print(f"     {pid} = {((e.get('labels') or {}).get('en') or {}).get('value')!r} : {court(((e.get('descriptions') or {}).get('en') or {}).get('value') or '', 90)}")
    uci_props = [p for p, lab in CANDIDATES.items() if re.search(r"\bUCI\b", lab) and re.search(r"rider|ID|person|cyclist|athlete", lab, re.I)]
    for p in uci_props[:2]:
        if not ok():
            break
        ech = sparql(f"SELECT ?p ?v WHERE {{ ?p wdt:{p} ?v }} LIMIT 5")
        print(f"   exemples de valeurs de {p} ({CANDIDATES[p]}) : {court(ech, 300) if ech is not None else 'requête échouée'}")


ECHANTILLON = [   # (nom UCI brut, naissance, uci_id, nationalité, rang 2025, groupe) — ranking.json 2025 des archives
    ('POGAČAR Tadej', '1998-09-21', 10014972740, 'SLO', 1, 'top20'),
    ('VINGEGAARD HANSEN Jonas', '1996-12-10', 10011208231, 'DEN', 2, 'top20'),
    ('DEL TORO Isaac', '2003-11-27', 10089274841, 'MEX', 3, 'top20'),
    ('PEDERSEN Mads', '1995-12-18', 10008689564, 'DEN', 4, 'top20'),
    ('ALMEIDA Joao', '1998-08-05', 10010784057, 'POR', 5, 'top20'),
    ('EVENEPOEL Remco', '2000-01-25', 10058736615, 'BEL', 6, 'top20'),
    ('PIDCOCK Tom', '1999-07-30', 10010977552, 'GBR', 7, 'top20'),
    ('VAN DER POEL Mathieu', '1995-01-19', 10007946203, 'NED', 8, 'top20'),
    ('ONLEY Oscar', '2002-10-13', 10064124155, 'GBR', 9, 'top20'),
    ('VAN AERT Wout', '1994-09-15', 10007585986, 'BEL', 10, 'top20'),
    ('DE LIE Arnaud', '2002-03-16', 10049023578, 'BEL', 11, 'top20'),
    ('CICCONE Giulio', '1994-12-20', 10009709175, 'ITA', 12, 'top20'),
    ('HEALY Ben', '2000-09-11', 10023507528, 'IRL', 13, 'top20'),
    ('AYUSO Juan', '2002-09-16', 10041514162, 'ESP', 14, 'top20'),
    ('LIPOWITZ Florian', '2000-09-21', 10098806507, 'GER', 15, 'top20'),
    ('VAUQUELIN Kévin', '2001-04-26', 10067207644, 'FRA', 16, 'top20'),
    ('PHILIPSEN Jasper', '1998-03-02', 10014827543, 'BEL', 17, 'top20'),
    ('SCARONI Christian', '1997-10-16', 10014401955, 'ITA', 18, 'top20'),
    ('MAGNIER Paul', '2004-04-14', 10068571102, 'FRA', 19, 'top20'),
    ('VINE Jay', '1995-11-16', 10014868969, 'AUS', 20, 'top20'),
    ('MARTINEZ Lenny Sydney', '2003-07-11', 10073681180, 'FRA', 31, 'fra'),
    ('GODON Dorian', '1996-05-25', 10011235311, 'FRA', 76, 'fra'),
    ('MARTIN GUYONNET Guillaume', '1993-06-09', 10007517076, 'FRA', 116, 'fra'),
    ('ARMIRAIL Bruno', '1994-04-11', 10009162642, 'FRA', 145, 'fra'),
    ('RONDEL Mathys', '2003-09-23', 10081960940, 'FRA', 173, 'fra'),
    ('DELBOVE Joris', '2000-07-15', 10023571081, 'FRA', 225, 'fra'),
    ('GUERIN Alexis', '1992-06-06', 10008853353, 'FRA', 262, 'fra'),
    ('BRAZ AFONSO Clément', '1999-11-08', 10027617395, 'FRA', 319, 'fra'),
    ('PAGE Hugo', '2001-07-24', 10068070237, 'FRA', 415, 'fra'),
    ('GUERNALEC Thibault', '1997-07-31', 10010202259, 'FRA', 466, 'fra'),
    ('TRÆEN Torstein', '1995-07-16', 10009893576, 'NOR', 146, 'alea'),
    ('BARGUIL Warren', '1991-10-28', 10007856677, 'FRA', 356, 'alea'),
    ('GHEBREIGZABHIER Amanuel', '1994-08-17', 10009583883, 'ERI', 545, 'alea'),
    ('ERIKSSON Lucas', '1996-04-10', 10009421411, 'SWE', 555, 'alea'),
    ('POLITT Nils', '1994-03-06', 10008722607, 'GER', 693, 'alea'),
    ('VALJAVEC Erazem', '2006-08-18', 10017620537, 'SLO', 902, 'alea'),
    ('DUJARDIN Sandy', '1997-05-29', 10009412317, 'FRA', 129, 'alea'),
    ('GONZÁLEZ RIVERA Abner', '2000-10-09', 10056423971, 'PUR', 930, 'alea'),
    ('LAFAY Victor', '1996-01-17', 10013629692, 'FRA', 255, 'alea'),
    ('NEAVES Jadian', '2006-03-28', 10138790008, 'TTO', 930, 'alea'),
]


def _candidats_date(naissance: str) -> Optional[Dict[str, set]]:
    """{QID: {libellés et alias, toutes langues}} des cyclistes nés ce jour-là (occupation dont le libellé anglais contient « cycl »)."""
    d = datetime.date.fromisoformat(naissance)
    d1 = d + datetime.timedelta(days=1)
    corps = (f'?p wdt:P569 ?b . FILTER(?b >= "{d}T00:00:00Z"^^xsd:dateTime && ?b < "{d1}T00:00:00Z"^^xsd:dateTime)\n'
             f'  ?p wdt:P106 ?o . ?o rdfs:label ?ol . FILTER(LANG(?ol) = "en" && CONTAINS(LCASE(STR(?ol)), "cycl"))\n'
             f'  {{ ?p rdfs:label ?l }} UNION {{ ?p skos:altLabel ?l }}')
    lignes = sparql("SELECT ?p ?l WHERE {\n  hint:Query hint:optimizer \"None\" .\n  " + corps + "\n} LIMIT 3000")
    if lignes is None:
        lignes = sparql("SELECT ?p ?l WHERE {\n  " + corps + "\n} LIMIT 3000")   # repli sans indication d'optimiseur
    if lignes is None:
        return None
    res: Dict[str, set] = defaultdict(set)
    for r in lignes:
        res[qid(r["p"])].add(r["l"])
    return res


def _niveau(uci_nom: str, libelles: set) -> int:
    """2 = jetons identiques (ordre indifférent) ; 1 = jetons du libellé inclus dans ceux du nom UCI (>= 2 jetons) ; 0 = non."""
    ju = jetons(uci_nom)
    meilleur = 0
    for lb in libelles:
        jl = jetons(lb)
        if jl and jl == ju:
            return 2
        if len(jl) >= 2 and jl <= ju:
            meilleur = 1
    return meilleur


def valeurs_sparql(qids: List[str]) -> str:
    return " ".join(f"wd:{q}" for q in qids)


def partie5() -> None:
    trouver_proprietes()
    if not ok():
        return
    # ---- (b) coureurs
    print(f"\n-- (b) Correspondance de {len(ECHANTILLON)} coureurs (date de naissance + cycliste + nom ; puis identifiant UCI)")
    resultat: Dict[str, Dict[str, Any]] = {}
    stats = Counter()
    for nom, naissance, uid, nat, rang, groupe in ECHANTILLON:
        if not ok():
            print("[BUDGET] correspondance interrompue")
            break
        cand = _candidats_date(naissance)
        if cand is None:
            stats["requete_echouee"] += 1
            resultat[nom] = {"statut": "échec requête", "q": None}
            if stats["requete_echouee"] >= 3 and stats["requete_echouee"] == sum(stats.values()):
                print("[WARN] 3 échecs consécutifs de SPARQL : correspondance abandonnée (service indisponible, bloqué ou requête rejetée)")
                break
            continue
        niv = {q: _niveau(nom, labs) for q, labs in cand.items()}
        exacts = [q for q, n in niv.items() if n == 2]
        partiels = [q for q, n in niv.items() if n == 1]
        if len(exacts) == 1:
            statut, q = "exact", exacts[0]
        elif len(exacts) > 1:
            statut, q = "ambigu", exacts[0]
        elif len(partiels) == 1:
            statut, q = "partiel", partiels[0]
        elif len(partiels) > 1:
            statut, q = "ambigu", partiels[0]
        elif cand:
            statut, q = "date seule", None
        else:
            statut, q = "absent", None
        stats[statut] += 1
        autre = ""
        if statut == "date seule":
            autre = " ; cyclistes nés ce jour : " + court([sorted(v)[:2] for v in cand.values()], 120)
        resultat[nom] = {"statut": statut, "q": q, "cand": exacts + partiels, "uid": uid, "groupe": groupe}
        print(f"   {rang:>4} {nom[:26]:<26} {naissance} {nat} {groupe:<5} -> {statut:<10} {q or ''} {(sorted(cand[q])[0] if q else '')[:28]}{autre}")
    n_ok = stats["exact"] + stats["partiel"] + stats["ambigu"]
    synth(5, f"correspondance date+nom (cyclistes) : {dict(stats)} sur {sum(stats.values())} ; exacte unique {stats['exact']}, partielle {stats['partiel']}, ambiguë {stats['ambigu']}")
    for g in ("top20", "fra", "alea"):
        sous = [v for k, v in resultat.items() if v.get("groupe") == g]
        if sous:
            print(f"   groupe {g} : trouvés {sum(1 for v in sous if v['statut'] in ('exact', 'partiel', 'ambigu'))}/{len(sous)}")
    # identifiant UCI
    uci_props = [p for p, lab in CANDIDATES.items() if re.search(r"\bUCI\b", lab) and re.search(r"rider|ID|person|cyclist|athlete", lab, re.I)]
    par_uci: Dict[str, str] = {}
    for p in uci_props[:3]:
        if not ok():
            break
        vals = " ".join(f'"{u}"' for _n, _d, u, *_ in ECHANTILLON)
        lignes = sparql(f"SELECT ?p ?v WHERE {{ VALUES ?v {{ {vals} }} ?p wdt:{p} ?v }}")
        print(f"   recherche par {p} ({CANDIDATES[p]}) : " + (f"{len(lignes)} éléments" if lignes is not None else "requête échouée (valeurs de type non texte ?)"))
        for r in lignes or []:
            par_uci[r["v"]] = qid(r["p"])
    if uci_props:
        accord = sum(1 for nom, _d, u, *_ in ECHANTILLON if str(u) in par_uci and resultat.get(nom, {}).get("q") == par_uci[str(u)])
        diff = [(nom, par_uci[str(u)], resultat.get(nom, {}).get("q")) for nom, _d, u, *_ in ECHANTILLON
                if str(u) in par_uci and resultat.get(nom, {}).get("q") not in (None, par_uci[str(u)])]
        synth(5, f"identifiant UCI présent dans Wikidata pour {len(par_uci)}/{len(ECHANTILLON)} coureurs ; accord avec la méthode date+nom : {accord} ; désaccords : {diff[:5]}")
    else:
        synth(5, "aucune propriété d'identifiant UCI de coureur trouvée par libellé")
    for nom, _d, u, *_ in ECHANTILLON:                       # éléments trouvés seulement par l'identifiant UCI
        if str(u) in par_uci and resultat.get(nom, {}).get("q") is None:
            resultat[nom] = dict(resultat.get(nom, {}), q=par_uci[str(u)], statut="via UCI")

    # détails des trouvés
    trouves = sorted({v["q"] for v in resultat.values() if v.get("q")})
    if trouves and ok():
        detail_coureurs(trouves, resultat)
    if ok():
        print("\n-- (c) Équipes")
        equipes_wikidata()


def detail_coureurs(trouves: List[str], resultat: Dict[str, Dict[str, Any]]) -> None:
    vals = valeurs_sparql(trouves)
    noms = {v["q"]: k for k, v in resultat.items() if v.get("q")}
    info: Dict[str, Dict[str, Any]] = {q: {"lieu": set(), "taille": set(), "image": False, "wikis": set(), "p54": []} for q in trouves}
    a = sparql(f'SELECT ?p ?lieuL ?taille ?img WHERE {{ VALUES ?p {{ {vals} }} OPTIONAL {{ ?p wdt:P19 ?lieu . ?lieu rdfs:label ?lieuL . FILTER(LANG(?lieuL)="fr") }} '
               f'OPTIONAL {{ ?p wdt:P2048 ?taille }} OPTIONAL {{ ?p wdt:P18 ?img }} }}')
    for r in a or []:
        e = info[qid(r["p"])]
        if r.get("lieuL"):
            e["lieu"].add(r["lieuL"])
        if r.get("taille"):
            e["taille"].add(r["taille"])
        if r.get("img"):
            e["image"] = True
    print(f"   requête lieu/taille/image : {'échec' if a is None else str(len(a)) + ' lignes'}")
    sites = ", ".join(f"<https://{w}.wikipedia.org/>" for w in WIKIS)
    b = sparql(f"SELECT ?p ?site WHERE {{ VALUES ?p {{ {vals} }} ?s schema:about ?p ; schema:isPartOf ?site . FILTER(?site IN ({sites})) }}")
    for r in b or []:
        info[qid(r["p"])]["wikis"].add(re.search(r"//(\w+)\.wikipedia", r["site"]).group(1))
    print(f"   requête sitelinks : {'échec' if b is None else str(len(b)) + ' liens'}")
    c = sparql(f'SELECT ?p ?teamL ?d ?f ?prec WHERE {{ VALUES ?p {{ {vals} }} ?p p:P54 ?st . ?st ps:P54 ?team . ?team rdfs:label ?teamL . FILTER(LANG(?teamL)="en") '
               f'OPTIONAL {{ ?st pq:P580 ?d . OPTIONAL {{ ?st pqv:P580 ?sv . ?sv wikibase:timePrecision ?prec }} }} OPTIONAL {{ ?st pq:P582 ?f }} }}')
    for r in c or []:
        info[qid(r["p"])]["p54"].append((r["teamL"], (r.get("d") or "")[:10], (r.get("f") or "")[:10], r.get("prec", "")))
    print(f"   requête P54 : {'échec' if c is None else str(len(c)) + ' déclarations'}")
    print("   coureur | QID | lieu naissance | taille | image | wikis (fr en es it nl de be) | P54 (avec début)")
    cpt = Counter()
    for q in trouves:
        e = info[q]
        n54 = len(e["p54"])
        n54d = sum(1 for t in e["p54"] if t[1])
        cpt["lieu"] += bool(e["lieu"])
        cpt["taille"] += bool(e["taille"])
        cpt["image"] += e["image"]
        cpt["p54"] += n54 > 0
        cpt["p54_dates"] += n54d > 0
        for w in WIKIS:
            cpt["wiki_" + w] += w in e["wikis"]
        print(f"   {noms.get(q, '?')[:24]:<24} {q:<10} {','.join(sorted(e['lieu']))[:20]:<20} {','.join(sorted(e['taille']))[:6]:<6} {'oui' if e['image'] else 'non'} "
              f"{''.join(('x' if w in e['wikis'] else '.') for w in WIKIS)} {n54}({n54d})")
    n = len(trouves)
    synth(5, f"sur {n} coureurs trouvés : lieu de naissance {cpt['lieu']}, taille {cpt['taille']}, image {cpt['image']}, P54 {cpt['p54']} (avec dates {cpt['p54_dates']}) ; "
             + ", ".join(f"{w} {cpt['wiki_' + w]}" for w in WIKIS))
    precs = Counter(t[3] for e in info.values() for t in e["p54"] if t[1])
    print(f"   précision des dates de début P54 (9 = année, 10 = mois, 11 = jour) : {dict(precs)}")
    for q in trouves[:3]:
        print(f"   exemple P54 de {noms.get(q)} ({q}) :")
        for t in sorted(info[q]["p54"], key=lambda t: t[1])[:10]:
            print(f"      {t[1] or '?':<10} -> {t[2] or '?':<10} {t[0]} (précision début {t[3] or '?'})")


EQUIPES = {   # lignée -> termes de recherche (le premier résultat dont la description parle de cyclisme est retenu)
    "Movistar": "Movistar Team", "Quick-Step": "Soudal Quick-Step", "Visma": "Team Visma Lease a Bike", "Lotto": "Lotto Cycling Team",
    "Groupama-FDJ": "Groupama-FDJ", "Decathlon AG2R": "Decathlon AG2R La Mondiale Team", "Cofidis": "Cofidis (cycling team)",
    "TotalEnergies": "Team TotalEnergies", "Arkéa": "Arkéa-B&B Hotels", "Israel": "Israel-Premier Tech",
}


def choisir(terme: str, langue: str = "en", motif: str = r"cycl") -> Tuple[Optional[str], List[str]]:
    rep = api(WD_API, action="wbsearchentities", search=terme, language=langue, uselang=langue, type="item", limit=7)
    res = rep.get("search", []) if isinstance(rep, dict) else []
    liste = [f"{r.get('id')} {r.get('label')!r} ({court(r.get('description') or '', 50)})" for r in res]
    pick = next((r["id"] for r in res if re.search(motif, f"{r.get('description') or ''}", re.I)), None)
    return pick, liste


def equipes_wikidata() -> None:
    codes = [p for p, lab in CANDIDATES.items() if re.search(r"team", lab, re.I) and re.search(r"code|ID", lab, re.I)]
    print(f"   propriétés de code d'équipe candidates : {codes}")
    sites = ", ".join(f"<https://{w}.wikipedia.org/>" for w in WIKIS)
    trouvees = 0
    for lignee, terme in EQUIPES.items():
        if not ok():
            print("[BUDGET] équipes interrompues")
            break
        q, liste = choisir(terme)
        print(f"\n   * {lignee} : recherche « {terme} » -> retenu {q} ; candidats : {' | '.join(liste[:4])}")
        if not q:
            continue
        trouvees += 1
        chaine = sparql(f'SELECT ?x ?xl ?sens WHERE {{ {{ wd:{q} wdt:P1365+ ?x . BIND("remplace" AS ?sens) }} UNION {{ wd:{q} wdt:P1366+ ?x . BIND("remplacé par" AS ?sens) }} '
                        f'OPTIONAL {{ ?x rdfs:label ?xl . FILTER(LANG(?xl)="en") }} }}')
        if chaine is None:
            print("     chaîne P1365/P1366 : requête échouée")
        else:
            av = [f"{qid(r['x'])} {r.get('xl', '?')}" for r in chaine if r["sens"] == "remplace"]
            ap = [f"{qid(r['x'])} {r.get('xl', '?')}" for r in chaine if r["sens"] == "remplacé par"]
            print(f"     remplace (antérieurs) : {court(av, 400) if av else 'aucun'}")
            print(f"     remplacé par (suivants) : {court(ap, 400) if ap else 'aucun'}")
        noms = sparql(f'SELECT ?n ?d ?f WHERE {{ wd:{q} p:P1448 ?st . ?st ps:P1448 ?n . OPTIONAL {{ ?st pq:P580 ?d }} OPTIONAL {{ ?st pq:P582 ?f }} }}')
        if noms is not None:
            print(f"     noms officiels P1448 ({len(noms)}) : " + court([(r['n'], r.get('d', '')[:10], r.get('f', '')[:10]) for r in noms[:6]], 420))
        saisons = sparql(f'SELECT ?s ?sl WHERE {{ ?s wdt:P5138 wd:{q} . OPTIONAL {{ ?s rdfs:label ?sl . FILTER(LANG(?sl)="en") }} }} LIMIT 60')
        if saisons is not None:
            print(f"     éléments « saison d'équipe » (P5138) : {len(saisons)} ; ex. {[r.get('sl', qid(r['s'])) for r in saisons[:5]]}")
        liens = sparql(f"SELECT ?site WHERE {{ ?s schema:about wd:{q} ; schema:isPartOf ?site . FILTER(?site IN ({sites})) }}")
        if liens is not None:
            langs = sorted(re.search(r"//(\w+)[.]wikipedia", r["site"]).group(1) for r in liens)
            print(f"     articles Wikipédia ({len(liens)}/{len(WIKIS)}) : {langs}")
        if codes:
            opt = " ".join(f"OPTIONAL {{ wd:{q} wdt:{p} ?c{i} }}" for i, p in enumerate(codes[:3]))
            cs = sparql(f"SELECT * WHERE {{ {opt} }}")
            print(f"     codes via {codes[:3]} : {court(cs, 200) if cs is not None else 'échec'}")
    synth(5, f"équipes : élément trouvé pour {trouvees}/{len(EQUIPES)} lignées (détails ci-dessus : chaîne remplace/remplacé par, P1448 daté, P5138)")


# ===============================================================================================================
# Partie 6 : Wikipédia multilingue
# ===============================================================================================================
LANGUES = ["fr", "en", "es", "it", "nl", "de"]
ENTITES = [("coureur", "Tadej Pogačar"), ("coureur", "Remco Evenepoel"), ("coureur", "Mathieu van der Poel"),
           ("coureur FR", "Julian Alaphilippe"), ("coureur FR", "Valentin Madouas"),
           ("équipe", "Movistar Team"), ("équipe", "Soudal Quick-Step"), ("équipe", "Groupama-FDJ"), ("équipe", "Lotto Dstny")]


def partie6() -> None:
    resolus: List[Tuple[str, str, Optional[str]]] = []
    for genre, nom in ENTITES:
        if not ok():
            break
        q, liste = choisir(nom)
        print(f"   {genre:<10} {nom:<22} -> {q}   (candidats : {' | '.join(liste[:2])})")
        resolus.append((genre, nom, q))
    qids = [q for _g, _n, q in resolus if q]
    if not qids:
        raise RuntimeError("aucune entité résolue")
    rep = api(WD_API, action="wbgetentities", ids="|".join(qids), props="sitelinks", sitefilter="|".join(l + "wiki" for l in LANGUES))
    liens: Dict[str, Dict[str, str]] = {}
    for q, e in ((rep or {}).get("entities") or {}).items() if isinstance(rep, dict) else []:
        liens[q] = {k[:-4]: v.get("title") for k, v in (e.get("sitelinks") or {}).items()}
    textes: Dict[Tuple[str, str], str] = {}
    for lg in LANGUES:
        if not ok():
            print("[BUDGET] extraits interrompus")
            break
        titres = [liens.get(q, {}).get(lg) for q in qids]
        titres = [t for t in titres if t]
        if not titres:
            continue
        r = api(f"https://{lg}.wikipedia.org/w/api.php", action="query", prop="extracts", exintro=1, explaintext=1, exlimit="max", redirects=1,
                titles="|".join(titres))
        pages = ((r or {}).get("query") or {}).get("pages") or {} if isinstance(r, dict) else {}
        par_titre = {p.get("title"): p.get("extract") or "" for p in pages.values() if isinstance(p, dict)}
        for q in qids:
            t = liens.get(q, {}).get(lg)
            if t in par_titre:
                textes[(q, lg)] = par_titre[t]
    print("\n   entité | longueur de l'introduction (caractères) par langue")
    gagnante = Counter()
    longueurs: Dict[str, List[int]] = defaultdict(list)
    for genre, nom, q in resolus:
        if not q:
            print(f"   {nom} : introuvable")
            continue
        lens = {lg: len(textes.get((q, lg), "")) for lg in LANGUES}
        print(f"   {nom[:24]:<24} " + "  ".join(f"{lg} {lens[lg]:>5}" for lg in LANGUES))
        for lg, n in lens.items():
            if n:
                longueurs[lg].append(n)
        if any(lens.values()):
            best = max(lens, key=lambda k: lens[k])
            gagnante[best] += 1
            print(f"      plus longue : {best} -> {court(textes[(q, best)].replace(chr(10), ' '), 200)}")
    moy = {lg: (sum(v) // len(v) if v else 0) for lg, v in longueurs.items()}
    synth(6, f"introduction la plus longue par langue : {dict(gagnante)} ; longueur moyenne {moy} ; présence {{{', '.join(f'{lg}: {len(v)}/{len(qids)}' for lg, v in longueurs.items())}}}")


# ===============================================================================================================
PARTIES = {1: ("TeamCode DataRide", partie1), 2: ("classements par équipes", partie2), 3: ("ligne brute de Results", partie3),
           4: ("délai de mise à jour du classement", partie4), 5: ("Wikidata", partie5), 6: ("Wikipédia multilingue", partie6)}


def main() -> None:
    t0 = time.time()
    print(f"Essai encyclopédie E0 - {datetime.date.today()} - UA : {netutil.USER_AGENT}")
    for n, (nom, fn) in PARTIES.items():
        titre(f"PARTIE {n} : {nom}")
        if time.time() >= FIN_GLOBAL:
            RESUME[n] = "non lancée (budget global épuisé)"
            print("[BUDGET] partie ignorée")
            continue
        _fin_partie[0] = time.time() + LIMITES[n]
        t1 = time.time()
        try:
            fn()
            RESUME[n] = f"terminée en {time.time() - t1:.0f} s" + (" (budget de la partie dépassé : sortie partielle)" if not ok() else "")
        except Exception as e:  # noqa: BLE001 — chaque partie est isolée
            RESUME[n] = f"[ECHEC] {type(e).__name__}: {e}"
            print(f"[ECHEC] partie {n} : {type(e).__name__}: {e}")
            traceback.print_exc(limit=3, file=sys.stdout)
    titre("SYNTHÈSE")
    for n, (nom, _fn) in PARTIES.items():
        print(f"Partie {n} ({nom}) : {RESUME.get(n, '?')}")
        for m, t in SYNTH:
            if m == n:
                print(f"     - {t}")
    print(f"\nRequêtes par hôte : {dict(REQ)} ; durée totale {time.time() - t0:.0f} s ; hôtes abandonnés : {sorted(netutil._blocked_hosts) or 'aucun'}")


if __name__ == "__main__":
    main()
