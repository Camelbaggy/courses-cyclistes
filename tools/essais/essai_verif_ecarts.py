#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : vérification, sur Wikidata (et titres Wikipédia), d'écarts repérés par un contrôle croisé (tools/audit_worlddb.py).
Lecture seule, rien n'est écrit. Lancement CI : commit contenant `[essai:verif_ecarts]` sur une branche ccr-*.

Entrée : `tools/essais/verif_ecarts.json` = {"coureurs": [{rider_id, nom, naissance (AAAA-MM-JJ), nationalite (code), controles}],
"vainqueurs": [{race_id, saison, course, vainqueur}]} : NOS valeurs seulement, aucune donnée issue d'une base tierce.

  1. Coureurs : recherche Wikidata « nom + occupation cycliste » (règles de wikidata.py), candidats au nom concordant avec leur
     P569 (date, précision) et P27 (nationalité). Verdicts : « notre date confirmée » / « date Wikidata différente : AAAA-MM-JJ » /
     « précision insuffisante » (P569 à l'année ou au mois) / « non trouvé / ambigu ».
  2. Vainqueurs : élément Wikidata de l'édition (recherche « <course> <année> », libellé contenant l'année et la plupart des mots
     du nom), vainqueur (P1346, qualificatifs affichés), titres des articles Wikipédia fr / en. Verdicts : « notre vainqueur
     confirmé » / « contredit » / « indéterminé ».
Les verdicts ne sont que des signaux : une date ou un vainqueur Wikidata n'est lui-même pas une preuve officielle (voir la source
UCI ou l'article cité). Politesse : User-Agent honnête de netutil, 1 requête/s par hôte, pas de `maxlag`, abandon d'un hôte sur
403/429 (règles de wikidata.py). Durée visée < 12 min (budget global 14 min). Hors réseau : `python tools/essais/essai_verif_ecarts.py --test`."""
import json
import os
import re
import sys
import time
import traceback
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, ".")
import netutil  # noqa: E402
import wikidata  # noqa: E402
from wikidata import (Api, HoteAbandonne, Sousclasses, est_cycliste, jetons, libelle_langue, lire_entites,  # noqa: E402
                      nom_concorde, noms_entite, parse_temps, qid_de, recherche, requetes_coureur, revendications, valeur)

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verif_ecarts.json")
BUDGET_S = 14 * 60
FIN = time.monotonic() + BUDGET_S
WIKIS = {"fr": "https://fr.wikipedia.org/w/api.php", "en": "https://en.wikipedia.org/w/api.php"}
MOTS_VIDES = {"the", "de", "du", "des", "la", "le", "les", "of", "and", "et", "a", "d", "l"}
SYNTH: Counter = Counter()


def hors_budget() -> bool:
    return time.monotonic() > FIN


def date_p569(e: Dict[str, Any]) -> List[Tuple[str, int]]:
    return [t for t in (parse_temps(valeur(c)) for c in revendications(e, "P569")) if t]


def libelles_de(api: Api, qids: List[str], memo: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    manque = [q for q in dict.fromkeys(qids) if q and q not in memo]
    for q, e in lire_entites(api, manque, "labels", "fr|en").items():
        memo[q] = libelle_langue(e)
    return memo


def verdict_naissance(notre: str, candidats: List[Dict[str, Any]]) -> str:
    """candidats : [{qid, dates: [(AAAA-MM-JJ, précision)]}] déjà filtrés (nom concordant, cycliste)."""
    if not candidats:
        return "non trouvé / ambigu (aucun candidat vérifié)"
    jour = [(c["qid"], t[0]) for c in candidats for t in c["dates"] if t[1] >= 11]
    if any(d == notre for _, d in jour):
        return "notre date confirmée" + (f" (parmi {len(candidats)} homonymes)" if len(candidats) > 1 else "")
    autres = sorted({d for _, d in jour})
    if len(candidats) == 1 and len(autres) == 1:
        return f"date Wikidata différente : {autres[0]}"
    if not jour:
        precis = sorted({f"{t[0][:4]}" + ("" if t[1] <= 9 else t[0][4:7]) for c in candidats for t in c["dates"]})
        return "précision insuffisante" + (f" : {', '.join(precis)}" if precis else " : pas de P569")
    return "non trouvé / ambigu (" + ", ".join(f"{q} {d}" for q, d in jour) + ")"


def verifier_coureur(api: Api, sous: Sousclasses, memo: Dict[str, Optional[str]], c: Dict[str, Any]) -> str:
    ids: List[str] = []
    for typ, texte in requetes_coureur(c["nom"]):
        r = recherche(api, wikidata._texte_requete(typ, texte), 10)
        ids += [q for q in (r or []) if q not in ids]
        if r:
            break
    ents = lire_entites(api, ids, "claims|labels|aliases")
    valides = []
    for q in ids:
        e = ents.get(q)
        if e and nom_concorde(c["nom"], noms_entite(e)) and est_cycliste(e, sous):
            valides.append({"qid": q, "dates": date_p569(e), "pays": [x for x in (qid_de(p) for p in revendications(e, "P27")) if x], "e": e})
    libelles_de(api, [p for v in valides for p in v["pays"]], memo)
    for v in valides:
        d = ", ".join(f"{t[0]} (précision {'jour' if t[1] >= 11 else 'mois' if t[1] == 10 else 'année'})" for t in v["dates"]) or "pas de P569"
        print(f"    candidat {v['qid']} « {libelle_langue(v['e']) or '?'} » : naissance {d} ; nationalité {', '.join(memo.get(p) or p for p in v['pays']) or '-'}")
    if not valides and ids:
        print(f"    {len(ids)} résultat(s) de recherche, aucun au nom concordant et cycliste")
    return verdict_naissance(c["naissance"] or "", valides)


def run_coureurs(api: Api, liste: List[Dict[str, Any]]) -> None:
    print(f"\n=== Coureurs ({len(liste)}) ===")
    if not wikidata.verifier_occupation(api):
        print("[WARN] occupation cycliste non vérifiée : partie ignorée")
        return
    sous, memo = Sousclasses(api), {}
    for i, c in enumerate(liste, 1):
        if hors_budget():
            print(f"[BUDGET] arrêt au coureur {i - 1}/{len(liste)}")
            SYNTH["coureurs non traités (budget)"] += len(liste) - i + 1
            return
        print(f"[{i}/{len(liste)}] {c['rider_id']} — {c['nom']} — notre date {c['naissance']} — notre nationalité {c['nationalite']} — contrôle {'+'.join(c['controles'])}")
        try:
            v = verifier_coureur(api, sous, memo, c)
        except HoteAbandonne:
            raise
        except Exception:  # noqa: BLE001 : un coureur en échec n'arrête pas les suivants
            traceback.print_exc()
            v = "non trouvé / ambigu (erreur)"
        print(f"    VERDICT : {v}")
        SYNTH["coureur : " + re.split(r" [:(]", v)[0]] += 1


def mots_course(nom: str) -> List[str]:
    return [j for j in jetons(nom) if j not in MOTS_VIDES and not j.isdigit() and len(j) > 2]


def elements_edition(e: Dict[str, Any], nom: str, annee: int) -> bool:
    """Libellé ou alias (n'importe quelle langue) contenant l'année et la plupart des mots du nom de course."""
    mots = mots_course(nom)
    for n in noms_entite(e):
        j = set(jetons(n))
        if str(annee) in j and mots and sum(1 for m in mots if m in j) / len(mots) >= 0.6:
            return True
    return False


def verifier_edition(api: Api, memo: Dict[str, Optional[str]], v: Dict[str, Any]) -> str:
    nom, an = v["course"], v["saison"]
    requetes = [f"{nom} {an}"]
    court = " ".join(mots_course(nom)[:4])
    if court and court != nom:
        requetes.append(f"{court} {an}")
    trouves: Dict[str, Dict[str, Any]] = {}
    for texte in requetes:
        ids = recherche(api, texte, 10) or []
        ents = lire_entites(api, ids, "claims|labels|aliases|sitelinks")
        trouves = {q: e for q, e in ents.items() if e and elements_edition(e, nom, an)}
        print(f"    recherche « {texte} » : {len(ids)} résultat(s), {len(trouves)} élément(s) d'édition retenu(s)")
        if trouves:
            break
    gagnants_nous = []
    for q, e in trouves.items():
        sl = wikidata.sitelinks(e)
        print(f"    élément {q} « {libelle_langue(e) or '?'} » ; articles : fr « {sl.get('fr', '-')} » ; en « {sl.get('en', '-')} »")
        cs = revendications(e, "P1346")
        if not cs:
            print("      pas de vainqueur (P1346) sur cet élément")
            continue
        pers = [qid_de(c) for c in cs if qid_de(c)]
        qual = {}
        for c in cs:
            for prop, snaks in (c.get("qualifiers") or {}).items():
                qual.setdefault(qid_de(c) or "?", []).extend(((s.get("datavalue") or {}).get("value") or {}).get("id", "") for s in snaks if isinstance((s.get("datavalue") or {}).get("value"), dict))
        persons = lire_entites(api, pers, "labels|aliases")
        libelles_de(api, [x for xs in qual.values() for x in xs if re.fullmatch(r"Q\d+", x)], memo)
        for p in pers:
            ep = persons.get(p)
            ok = bool(ep) and nom_concorde(v["vainqueur"], noms_entite(ep))
            ql = ", ".join(memo.get(x) or x for x in qual.get(p, []))
            print(f"      P1346 {p} « {libelle_langue(ep) or '?'} »" + (f" [qualificatifs : {ql}]" if ql else "") + (" = notre vainqueur" if ok else ""))
            gagnants_nous.append(ok)
    if not trouves:
        for lg, base in WIKIS.items():
            rep = api.appel(base, action="query", list="search", srsearch=f"{nom} {an}", srlimit=3)
            titres = [r.get("title") for r in ((rep or {}).get("query") or {}).get("search", [])]
            print(f"    Wikipédia {lg} (recherche, titres) : {titres or '-'}")
        return "indéterminé (élément Wikidata de l'édition introuvable)"
    if any(gagnants_nous):
        return "notre vainqueur confirmé"
    if gagnants_nous:
        return "notre vainqueur contredit (Wikidata donne un autre vainqueur, comparer à la source officielle)"
    return "indéterminé (pas de P1346 sur l'élément)"


def run_vainqueurs(api: Api, liste: List[Dict[str, Any]]) -> None:
    print(f"\n=== Vainqueurs en désaccord ({len(liste)}) ===")
    memo: Dict[str, Optional[str]] = {}
    for i, v in enumerate(liste, 1):
        if hors_budget():
            print(f"[BUDGET] arrêt à l'édition {i - 1}/{len(liste)}")
            SYNTH["éditions non traitées (budget)"] += len(liste) - i + 1
            return
        print(f"[{i}/{len(liste)}] {v['race_id']} — {v['course']} {v['saison']} — notre vainqueur : {v['vainqueur']}")
        try:
            r = verifier_edition(api, memo, v)
        except HoteAbandonne:
            raise
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            r = "indéterminé (erreur)"
        print(f"    VERDICT : {r}")
        SYNTH["édition : " + re.split(r" [(]", r)[0]] += 1


def main() -> int:
    t0 = time.monotonic()
    with open(FICHIER, encoding="utf-8") as f:
        data = json.load(f)
    wikidata.preparer_reseau()
    for h in ("fr.wikipedia.org", "en.wikipedia.org"):
        netutil.HOST_DELAYS[h] = 1.0
    api = Api()
    try:
        run_coureurs(api, data.get("coureurs") or [])
        run_vainqueurs(api, data.get("vainqueurs") or [])
    except HoteAbandonne as e:
        print(f"[ABANDON] hôte refusé ou trop d'échecs : {e} ; synthèse partielle")
    print("\n=== Synthèse ===")
    for k, n in sorted(SYNTH.items()):
        print(f"  {k} : {n}")
    nc, nv = len(data.get("coureurs") or []), len(data.get("vainqueurs") or [])
    print(f"  entrée : {nc} coureurs, {nv} éditions ; {api.requetes} requêtes en {(time.monotonic() - t0) / 60:.1f} min")
    return 0


def _test() -> None:
    assert verdict_naissance("1996-01-01", [{"qid": "Q1", "dates": [("1996-01-01", 11)]}]) == "notre date confirmée"
    assert verdict_naissance("1996-01-01", [{"qid": "Q1", "dates": [("1996-01-02", 11)]}]) == "date Wikidata différente : 1996-01-02"
    assert verdict_naissance("1996-01-01", []).startswith("non trouvé")
    assert verdict_naissance("1996-01-01", [{"qid": "Q1", "dates": [("1996-01-01", 9)]}]).startswith("précision insuffisante")
    assert verdict_naissance("1996-01-01", [{"qid": "Q1", "dates": [("1996-02-02", 11)]}, {"qid": "Q2", "dates": [("1996-03-03", 11)]}]).startswith("non trouvé / ambigu")
    e = {"labels": {"fr": {"value": "Circuit des Ardennes 2023"}}}
    assert elements_edition(e, "Circuit des Ardennes", 2023) and not elements_edition(e, "Circuit des Ardennes", 2022)
    assert not elements_edition({"labels": {"en": {"value": "Tour de France 2023"}}}, "Tour de Wallonie", 2023)
    print("[OK] essai_verif_ecarts --test")


if __name__ == "__main__":
    if "--test" in sys.argv[1:]:
        _test()
        sys.exit(0)
    sys.exit(main())
