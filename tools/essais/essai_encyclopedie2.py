#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau E0 bis de l'encyclopédie : second passage, SANS SPARQL (query.wikidata.org a échoué au premier).
Lecture seule, rien n'est écrit. Réutilise (import) les accès DataRide et le client d'API de essai_encyclopedie.py.

Lancement CI : commit contenant `[essai:encyclopedie2]` sur une branche ccr-*. Budget global 14 min.

Parties (chacune isolée par try/except) :
  A. `TeamId` du classement individuel DataRide (2019, 2022, 2025, 2026, 2027) : table (TeamId, TeamCode, TeamName,
     coureurs) ; stabilité du TeamId des 10 lignées ; un même TeamId porte-t-il des noms différents ? est-il réutilisé
     pour une autre entité (noms sans mot commun ET peu de coureurs communs) ? un nom <-> un seul TeamId ?
  B. Wikidata coureurs par l'API de recherche (CirrusSearch `haswbstatement:P11020=<UciId>`, sinon nom + occupation
     cycliste + date de naissance vérifiée au jour près) pour les 40 coureurs de l'échantillon ; couverture des champs.
  C. Wikidata équipes : `haswbstatement:P1998=<code UCI>` pour tous les codes des 10 lignées ; P31, P1998 daté, P5138,
     P1448, P1365/P1366, sitelinks ; une chaîne « code UCI d'une saison -> élément équipe stable » est-elle constructible ?

Politesse : User-Agent honnête de netutil, ≤ 1 requête/s et par hôte (netutil.DEFAULT_DELAY), `maxlag=5`, une seule
tentative par requête Wikimedia (un 429 abandonne l'hôte). Aucun contournement.
"""
import datetime
import json
import os
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, ".")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netutil  # noqa: E402
import essai_encyclopedie as e1  # noqa: E402  (accès DataRide, client MediaWiki, échantillon, lignées)

FIN_GLOBAL = time.time() + 14 * 60
LIMITES = {"A": 300, "B": 360, "C": 240}   # secondes par partie
_fin_partie = [FIN_GLOBAL]
SYNTH: List[Tuple[str, str]] = []
RESUME: Dict[str, str] = {}
ANNEES = [2019, 2022, 2025, 2026, 2027]
STOP = {"TEAM", "CYCLING", "CLUB", "PRO", "THE", "DE", "DEL", "DI", "LA", "LE", "DES", "BY", "AND", "ET", "PRO", "CT", "CC", "RACING"}


def ok() -> bool:
    return time.time() < min(FIN_GLOBAL, _fin_partie[0])


def titre(s: str) -> None:
    print(f"\n{'#' * 8} {s}", flush=True)


def synth(p: str, texte: str) -> None:
    SYNTH.append((p, texte))
    print(f"   >> {texte}", flush=True)


def court(x: Any, n: int = 300) -> str:
    return e1.court(x, n)


def pct(a: int, b: int) -> str:
    return f"{a}/{b}" + (f" ({100 * a // b} %)" if b else "")


# ===============================================================================================================
# Partie A : TeamId
# ===============================================================================================================
A_CODES: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))   # lignée -> code -> {saisons} (code dominant)


def _ligne(lg: Dict[str, Any]) -> Tuple[str, str, str, str]:
    tid = str(lg.get("TeamId") or "").strip()
    if tid in ("0", "None"):
        tid = ""
    code = str(lg.get("TeamCode") or "").strip()
    nom = " ".join(str(lg.get("TeamName") or "").split())
    uid = str(lg.get("UciId") or "").strip()
    return tid, code, nom, uid


def _jetons(nom: str) -> frozenset:
    return frozenset(t for t in netutil.normalize(nom).upper().split() if t not in STOP and len(t) > 2)


def partieA() -> None:
    par_saison: Dict[int, List[Tuple[str, str, str, str]]] = {}
    for a in ANNEES:
        if not ok():
            print("[BUDGET] partie A interrompue")
            break
        cl, lignes = e1.individuel(a)
        if not lignes:
            print(f"\n-- saison {a} : classement individuel indisponible")
            continue
        par_saison[a] = [_ligne(lg) for lg in lignes]
    if not par_saison:
        raise RuntimeError("aucun classement lu")

    # --- tables par saison
    for a, lg in par_saison.items():
        sans_id = sum(1 for t, *_ in lg if not t)
        sans_code = sum(1 for _t, c, *_ in lg if not c)
        t_et_c = sum(1 for t, c, *_ in lg if bool(t) != bool(c))
        trip = Counter((t, c, n) for t, c, n, _u in lg if t or c or n)
        id2n: Dict[str, set] = defaultdict(set)
        n2id: Dict[str, set] = defaultdict(set)
        id2c: Dict[str, set] = defaultdict(set)
        for (t, c, n) in trip:
            if t and n:
                id2n[t].add(n)
                n2id[n].add(t)
            if t and c:
                id2c[t].add(c)
        print(f"\n-- saison {a} : {len(lg)} lignes ; sans TeamId {pct(sans_id, len(lg))} ; sans TeamCode {sans_code} ; "
              f"TeamId présent XOR TeamCode présent : {t_et_c} ; {len({t for t, *_ in lg if t})} TeamId distincts")
        print(f"   un TeamId -> plusieurs noms (dans la saison) : {sum(1 for v in id2n.values() if len(v) > 1)} ; un nom -> plusieurs TeamId : "
              f"{sum(1 for v in n2id.values() if len(v) > 1)} ; un TeamId -> plusieurs codes : {sum(1 for v in id2c.values() if len(v) > 1)}")
        for t, v in [(t, v) for t, v in id2n.items() if len(v) > 1][:5]:
            print(f"      TeamId {t} porte {sorted(v)}")
        for n, v in [(n, v) for n, v in n2id.items() if len(v) > 1][:5]:
            print(f"      nom «{n}» porté par les TeamId {sorted(v)}")
        print("   TeamId | TeamCode | TeamName | coureurs  (équipes >= 5 coureurs classés, 90 lignes max)")
        grosses = sorted([(t, c, n, k) for (t, c, n), k in trip.items() if k >= 5], key=lambda x: (x[2], x[0]))
        for t, c, n, k in grosses[:90]:
            print(f"   {t or '-':<8} | {c or '-':<5} | {n[:50]:<50} | {k}")
        if len(grosses) > 90:
            print(f"   … {len(grosses) - 90} autres équipes")
        bilan_n2id = sum(1 for v in n2id.values() if len(v) > 1)
        synth("A", f"saison {a} : sans TeamId {pct(sans_id, len(lg))} ; nom -> plusieurs TeamId : {bilan_n2id} ; TeamId -> plusieurs noms : "
                   f"{sum(1 for v in id2n.values() if len(v) > 1)}")

    # --- les 10 lignées
    print("\n-- Lignées : TeamId dominant par saison (équipes dont le nom correspond au motif de la lignée)")
    stables = 0
    for lignee, motif in e1.LIGNEES.items():
        dom: Dict[int, Tuple[str, str, str, int]] = {}
        for a, lg in par_saison.items():
            c = Counter((t, cd, n) for t, cd, n, _u in lg if re.search(motif, n.upper()))
            if not c:
                continue
            ids = Counter()
            for (t, _cd, _n), k in c.items():
                ids[t] += k
            tdom = ids.most_common(1)[0][0]
            (t, cd, n), k = max(((x, k) for x, k in c.items() if x[0] == tdom), key=lambda z: z[1])
            dom[a] = (t, cd, n, ids[tdom])
            if cd:
                A_CODES[lignee][cd].add(a)
        suite = " | ".join(f"{a}: id={t or '-'} {cd or '-'} «{n[:26]}» x{k}" for a, (t, cd, n, k) in dom.items())
        ids_vus = {t for t, *_ in dom.values()}
        stable = len(dom) >= 2 and len(ids_vus) == 1 and "" not in ids_vus
        stables += stable
        etat = "STABLE" if stable else ("VARIE " if len(dom) >= 2 else "?     ")
        codes_vus = {cd for _t, cd, *_ in dom.values()}
        print(f"   {lignee:<22} {etat} (TeamId distincts {len(ids_vus)}, codes distincts {len(codes_vus)}) | {suite or '(absente)'}")
    synth("A", f"lignées dont le TeamId dominant est identique sur toutes les saisons présentes : {stables}/{len(e1.LIGNEES)}")

    # --- TeamId à travers les saisons
    ident: Dict[str, Dict[int, Tuple[str, str]]] = defaultdict(dict)     # tid -> saison -> (nom dominant, code dominant)
    riders: Dict[str, Dict[int, set]] = defaultdict(lambda: defaultdict(set))
    for a, lg in par_saison.items():
        cnt: Dict[str, Counter] = defaultdict(Counter)
        for t, c, n, u in lg:
            if t and n:
                cnt[t][(n, c)] += 1
            if t and u:
                riders[t][a].add(u)
        for t, c in cnt.items():
            ident[t][a] = c.most_common(1)[0][0]
    multi = {t: v for t, v in ident.items() if len(v) >= 2}
    change = {t: v for t, v in multi.items() if len({n for n, _c in v.values()}) > 1}
    code_change = {t: v for t, v in multi.items() if len({c for _n, c in v.values() if c}) > 1}
    print(f"\n-- TeamId présents sur >= 2 saisons : {len(multi)} (sur {len(ident)}) ; nom dominant différent d'une saison à l'autre : {len(change)} ; "
          f"code dominant différent : {len(code_change)}")
    print("   exemples de TeamId aux noms changeants (20 max) : TeamId: saison:nom[code] (coureurs communs avec la saison précédente listée)")
    for t, v in list(change.items())[:20]:
        parts = []
        prec = None
        for a in sorted(v):
            n, c = v[a]
            comm = len(riders[t][a] & riders[t][prec]) if prec is not None else None
            parts.append(f"{a}:{n[:30]}[{c or '-'}]" + (f" ({comm} comm.)" if comm is not None else ""))
            prec = a
        print(f"   {t}: " + " -> ".join(parts))

    # --- réutilisation : noms consécutifs sans mot commun
    suspects = []
    for t, v in multi.items():
        ans = sorted(v)
        for a1, a2 in zip(ans, ans[1:]):
            j1, j2 = _jetons(v[a1][0]), _jetons(v[a2][0])
            if j1 and j2 and not (j1 & j2):
                r1, r2 = riders[t][a1], riders[t][a2]
                suspects.append((t, a1, a2, v[a1][0], v[a2][0], len(r1 & r2), len(r1), len(r2)))
    faibles = [s for s in suspects if s[5] <= 0.2 * min(s[6], s[7] or 1)]
    print(f"\n-- Réutilisation possible d'un TeamId (noms consécutifs sans mot commun) : {len(suspects)} paires ; dont <= 20 % de coureurs communs : {len(faibles)}")
    print("   (sans mot commun mais beaucoup de coureurs communs = changement de nom du même effectif ; peu de coureurs communs = vraie réutilisation probable)")
    for t, a1, a2, n1, n2, comm, s1, s2 in sorted(suspects, key=lambda s: s[5])[:10]:
        print(f"   {t}: {a1} «{n1[:34]}» ({s1} coureurs) -> {a2} «{n2[:34]}» ({s2}) ; coureurs communs {comm}")
    synth("A", f"TeamId sur >= 2 saisons : {len(multi)} ; nom qui change {len(change)} ; paires sans mot commun {len(suspects)} dont peu de coureurs communs (réutilisation probable) {len(faibles)}")

    # --- le code est-il moins stable que le TeamId ?
    c2ids: Dict[str, set] = defaultdict(set)
    for a, lg in par_saison.items():
        for t, c, _n, _u in lg:
            if t and c:
                c2ids[c].add(t)
    reutil = {c: v for c, v in c2ids.items() if len(v) > 1}
    print(f"\n-- TeamCode associé à plusieurs TeamId (toutes saisons) : {len(reutil)} (sur {len(c2ids)} codes) ; exemples :")
    for c, v in list(reutil.items())[:8]:
        print(f"   {c}: TeamId {sorted(v)} -> " + " ; ".join(f"{t}={'/'.join(sorted({n for n, cd in ident.get(t, {}).values() if cd == c}))[:40]}" for t in sorted(v)))
    synth("A", f"codes liés à plusieurs TeamId : {len(reutil)}/{len(c2ids)} ; TeamId dont le code change : {len(code_change)}/{len(multi)}")


# ===============================================================================================================
# Accès Wikidata (API, sans SPARQL)
# ===============================================================================================================
ENT: Dict[str, Dict[str, Any]] = {}      # entités complètes (claims, sitelinks, labels)
LAB: Dict[str, str] = {}                 # QID -> libellé fr/en
WIKIS = ["frwiki", "enwiki", "eswiki", "itwiki", "nlwiki", "dewiki"]
_echecs = [0]


def wd(**p: Any) -> Optional[Dict[str, Any]]:
    if "www.wikidata.org" in netutil._blocked_hosts:
        raise RuntimeError("hôte www.wikidata.org abandonné par netutil (403/429/challenge)")
    rep = e1.api(e1.WD_API, **p)
    if not isinstance(rep, dict) or "error" in rep:
        _echecs[0] += 1
        print(f"[WARN] requête Wikidata échouée ({p.get('action')}/{p.get('list') or ''}) : {court(rep, 160)}")
        if _echecs[0] >= 8:
            raise RuntimeError("trop d'échecs Wikidata consécutifs")
        return None
    _echecs[0] = 0
    return rep


def recherche(requete: str, limite: int = 10) -> Optional[List[str]]:
    rep = wd(action="query", list="search", srsearch=requete, srlimit=limite, srnamespace=0)
    if rep is None:
        return None
    return [r["title"] for r in (rep.get("query") or {}).get("search", []) if r.get("title")]


def libelle_de(e: Dict[str, Any], q: str) -> str:
    lab = e.get("labels") or {}
    return (lab.get("fr") or lab.get("en") or {}).get("value") or q


def ent_full(qids: List[str]) -> None:
    manque = [q for q in dict.fromkeys(qids) if q not in ENT]
    for i in range(0, len(manque), 50):
        if not ok():
            print("[BUDGET] lecture d'entités interrompue")
            return
        lot = manque[i:i + 50]
        rep = wd(action="wbgetentities", ids="|".join(lot), props="claims|sitelinks|labels", languages="fr|en", sitefilter="|".join(WIKIS))
        for q, e in ((rep or {}).get("entities") or {}).items():
            if isinstance(e, dict) and "missing" not in e:
                ENT[q] = e
                LAB[q] = libelle_de(e, q)


def lab(qids: List[str]) -> None:
    manque = [q for q in dict.fromkeys(qids) if q and q not in LAB]
    for i in range(0, len(manque), 50):
        if not ok():
            return
        rep = wd(action="wbgetentities", ids="|".join(manque[i:i + 50]), props="labels", languages="fr|en")
        for q, e in ((rep or {}).get("entities") or {}).items():
            if isinstance(e, dict):
                LAB[q] = libelle_de(e, q)


def claims(q: str, p: str) -> List[Dict[str, Any]]:
    return ((ENT.get(q) or {}).get("claims") or {}).get(p, [])


def c_id(c: Dict[str, Any]) -> Optional[str]:
    v = (c.get("mainsnak") or {}).get("datavalue", {}).get("value")
    return v.get("id") if isinstance(v, dict) else None


def c_val(c: Dict[str, Any]) -> Any:
    return (c.get("mainsnak") or {}).get("datavalue", {}).get("value")


def c_time(c: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    v = c_val(c)
    if isinstance(v, dict) and v.get("time"):
        return v["time"], int(v.get("precision") or 0)
    return None


def q_times(c: Dict[str, Any], p: str) -> List[Optional[Tuple[str, int]]]:
    out: List[Optional[Tuple[str, int]]] = []
    for s in (c.get("qualifiers") or {}).get(p, []):
        v = (s.get("datavalue") or {}).get("value")
        out.append((v["time"], int(v.get("precision") or 0)) if isinstance(v, dict) and v.get("time") else None)
    return out


def fmt_t(t: Optional[Tuple[str, int]]) -> str:
    if not t:
        return "?"
    s = t[0].lstrip("+")
    return {9: s[:4], 10: s[:7]}.get(t[1], s[:10])


def dates_q(c: Dict[str, Any]) -> str:
    d, f = q_times(c, "P580"), q_times(c, "P582")
    if not d and not f:
        return ""
    return f"[{fmt_t(d[0]) if d else '…'}→{fmt_t(f[0]) if f else '…'}]"


# ===============================================================================================================
# Partie B : coureurs
# ===============================================================================================================
def nom_affichage(nom_uci: str) -> str:
    """« VAN DER POEL Mathieu » -> « Mathieu Van Der Poel »."""
    jet = nom_uci.split()
    i = 0
    while i < len(jet) - 1 and jet[i] == jet[i].upper():
        i += 1
    return " ".join(jet[i:] + [j.title() for j in jet[:i]])


def date_ok(q: str, jour: str) -> bool:
    return any(t and t[0].lstrip("+")[:10] == jour and t[1] >= 11 for t in (c_time(c) for c in claims(q, "P569")))


def partieB() -> None:
    # --- occupation « cycliste sur route »
    OCC = "Q2309784"
    ent_full([OCC])
    lab_occ = (ENT.get(OCC) or {}).get("labels") or {}
    print(f"-- {OCC} : en={((lab_occ.get('en') or {}).get('value'))!r} fr={((lab_occ.get('fr') or {}).get('value'))!r}")
    if not re.search(r"cycl", json.dumps(lab_occ, ensure_ascii=False), re.I):
        rep = wd(action="wbsearchentities", search="road cyclist", language="en", uselang="en", type="item", limit=7)
        cand = (rep or {}).get("search", [])
        print(f"   [WARN] libellé inattendu pour {OCC} ; candidats : " + " | ".join(f"{r.get('id')} {r.get('label')!r} ({court(r.get('description') or '', 40)})" for r in cand))
        pick = next((r["id"] for r in cand if re.search(r"cycl", r.get("label") or "", re.I)), None)
        if pick:
            OCC = pick
            print(f"   occupation retenue : {OCC}")
    # --- échantillon et UciId
    lignes = e1.individuel(2025)[1]
    par_uid = {str(lg.get("UciId")): lg for lg in lignes if lg.get("UciId")}
    print(f"-- classement 2025 DataRide : {len(lignes)} lignes, {len(par_uid)} UciId")
    riders: List[Dict[str, Any]] = []
    dans_classement = 0
    for nom, naiss, uid, nat, rang, groupe in e1.ECHANTILLON:
        lg = par_uid.get(str(uid))
        if lg:
            dans_classement += 1
            nai = str(lg.get("BirthDate") or "")[:10]
            if nai and nai != naiss:
                print(f"   [WARN] {nom} : date de naissance du classement {nai} != échantillon {naiss}")
        riders.append(dict(nom=nom, naiss=naiss, uid=str(uid), nat=nat, rang=rang, groupe=groupe, aff=nom_affichage(nom)))
    print(f"-- échantillon : {len(riders)} coureurs ; UciId retrouvé dans le classement 2025 : {pct(dans_classement, len(riders))} (sinon UciId repris de l'échantillon, lu dans ranking.json 2025 des archives au premier essai)")

    # --- recherches
    for r in riders:
        if not ok():
            print("[BUDGET] recherches de coureurs interrompues")
            break
        r["h_uid"] = recherche(f"haswbstatement:P11020={r['uid']}", 5)
        if r["h_uid"]:
            continue
        r["h_nom"] = recherche(f"{r['aff']} haswbstatement:P106={OCC}", 10)
        if not r["h_nom"]:
            r["h_libre"] = recherche(r["aff"], 10)
    ent_full([q for r in riders for k in ("h_uid", "h_nom", "h_libre") for q in (r.get(k) or [])])

    # --- évaluation
    stats: Counter = Counter()
    for r in riders:
        r["q"], r["methode"] = None, None
        if "h_uid" not in r:
            r["statut"] = "non testé (budget)"
        elif r["h_uid"]:
            if len(r["h_uid"]) == 1:
                r["statut"], r["q"], r["methode"] = "UciId", r["h_uid"][0], "UciId"
            else:
                r["statut"] = "ambigu (UciId multiple)"
        else:
            c1 = [q for q in r.get("h_nom") or [] if date_ok(q, r["naiss"])]
            c2 = [q for q in r.get("h_libre") or [] if date_ok(q, r["naiss"])] if not c1 else []
            if len(c1) == 1:
                r["statut"], r["q"], r["methode"] = "nom+date", c1[0], "nom+date (occupation)"
            elif len(c2) == 1:
                r["statut"], r["q"], r["methode"] = "nom+date", c2[0], "nom+date (sans filtre)"
            elif len(c1) > 1 or len(c2) > 1:
                r["statut"] = "ambigu (nom+date)"
            else:
                autres = len(r.get("h_nom") or []) + len(r.get("h_libre") or [])
                r["statut"] = "absent" + (f" ({autres} candidats, date différente)" if autres else " (aucun candidat)")
        stats[r["statut"].split(" (")[0]] += 1
    methodes = Counter(r["methode"] for r in riders if r["methode"])

    # --- P11020 et couverture
    trouves = [r for r in riders if r["q"]]
    lieux = []
    for r in trouves:
        e = ENT.get(r["q"]) or {}
        for c in claims(r["q"], "P19"):
            if c_id(c):
                lieux.append(c_id(c))
    lab(lieux)
    cpt: Counter = Counter()
    prec_d: Counter = Counter()
    prec_f: Counter = Counter()
    n54_tot = n54_deb = n54_fin = 0
    print("\n   rang coureur | méthode | QID | P11020 vs UciId | naissance | lieu fr | taille | image | wikis (fr en es it nl de) | P54 (début/fin)")
    for r in riders:
        q = r["q"]
        if not q:
            print(f"   {r['rang']:>4} {r['nom'][:26]:<26} -> {r['statut']}")
            continue
        p11 = [str(c_val(c)) for c in claims(q, "P11020")]
        p11s = "égal" if r["uid"] in p11 else ("DIFFÉRENT " + ",".join(p11)[:30] if p11 else "absent")
        cpt["p11020_" + p11s.split()[0]] += 1
        dok = date_ok(q, r["naiss"])
        cpt["date_ok"] += dok
        lieu = [LAB.get(c_id(c), "?") for c in claims(q, "P19") if c_id(c)]
        taille = [c_val(c).get("amount") for c in claims(q, "P2048") if isinstance(c_val(c), dict)]
        img = bool(claims(q, "P18"))
        sl = (ENT.get(q) or {}).get("sitelinks") or {}
        p54 = claims(q, "P54")
        deb = sum(1 for c in p54 if q_times(c, "P580"))
        fin = sum(1 for c in p54 if q_times(c, "P582"))
        for c in p54:
            for t in q_times(c, "P580"):
                prec_d[t[1] if t else "?"] += 1
            for t in q_times(c, "P582"):
                prec_f[t[1] if t else "?"] += 1
        n54_tot += len(p54)
        n54_deb += deb
        n54_fin += fin
        cpt["lieu"] += bool(lieu)
        cpt["taille"] += bool(taille)
        cpt["image"] += img
        cpt["p54"] += bool(p54)
        cpt["p54_deb"] += deb > 0
        for w in WIKIS:
            cpt[w] += w in sl
        print(f"   {r['rang']:>4} {r['nom'][:26]:<26} | {r['methode'][:12]:<12} | {q:<10} | {p11s:<10} | {'ok' if dok else 'KO'} | {','.join(lieu)[:22]:<22} | "
              f"{','.join(taille)[:6]:<6} | {'oui' if img else 'non'} | {''.join('x' if w in sl else '.' for w in WIKIS)} | {len(p54)}({deb}/{fin})")
    n = len(trouves)
    print(f"\n   -> trouvés {n}/{len(riders)} ; statuts {dict(stats)} ; méthodes {dict(methodes)}")
    print(f"   P11020 : {dict((k, v) for k, v in cpt.items() if k.startswith('p11020_'))} ; date de naissance exacte (précision jour) {cpt['date_ok']}/{n}")
    print(f"   P54 : {n54_tot} entrées sur {cpt['p54']} coureurs ; avec début (P580) {n54_deb}, avec fin (P582) {n54_fin} ; précision début {dict(prec_d)} fin {dict(prec_f)} (9 année, 10 mois, 11 jour)")
    for g in ("top20", "fra", "alea"):
        sous = [r for r in riders if r["groupe"] == g]
        print(f"   groupe {g} : trouvés {sum(1 for r in sous if r['q'])}/{len(sous)} ; par UciId {sum(1 for r in sous if r['methode'] == 'UciId')}")
    # exemples P54
    ex = trouves[:3] + [r for r in trouves if r["groupe"] == "fra"][:1]
    equipes = [c_id(c) for r in ex for c in claims(r["q"], "P54") if c_id(c)]
    lab(equipes)
    for r in ex:
        print(f"   exemple P54 de {r['nom']} ({r['q']}) :")
        for c in sorted(claims(r["q"], "P54"), key=lambda c: fmt_t((q_times(c, "P580") or [None])[0]))[:10]:
            print(f"      {LAB.get(c_id(c), '?')} {dates_q(c) or '[sans dates]'}")
    ab = {k: v for k, v in stats.items()}
    synth("B", f"{len(riders)} coureurs : trouvés par UciId {stats['UciId']}, par nom+date {stats['nom+date']} "
               f"(avec filtre occupation {methodes['nom+date (occupation)']}, sans {methodes['nom+date (sans filtre)']}), ambigus {stats['ambigu']}, absents {stats['absent']} ; détail {ab}")
    synth("B", f"sur {n} trouvés : P11020 {dict((k[7:], v) for k, v in cpt.items() if k.startswith('p11020_'))} ; P19 fr {cpt['lieu']}, P2048 {cpt['taille']}, P18 {cpt['image']}, "
               f"P54 {cpt['p54']} (début daté {cpt['p54_deb']} ; entrées {n54_tot}, début {n54_deb}, fin {n54_fin}) ; sitelinks " + ", ".join(f"{w[:2]} {cpt[w]}" for w in WIKIS))


# ===============================================================================================================
# Partie C : équipes
# ===============================================================================================================
STATIQUE = {   # codes cités dans la consigne, ajoutés à ceux lus dans la partie A
    "Quick-Step": ["DQT", "QST", "SOQ"], "Jumbo / Visma": ["TJV", "TVL"], "Lotto": ["LTS", "LOT", "LOI"],
    "DSM / Sunweb / Picnic": ["SUN", "DSM", "TPP"], "UAE": ["UAD", "UEX"], "Groupama-FDJ": ["GFC"],
    "AG2R / Decathlon": ["ALM", "ACT", "DAT", "DCT"], "Movistar": ["MOV"], "Cofidis": ["COF"],
    "Israel": ["ICA", "IPT", "APT", "NSN"], "à vérifier (TotalEnergies, Arkéa…)": ["TEN", "ARK"],
}


class UF:
    def __init__(self) -> None:
        self.p: Dict[str, str] = {}

    def f(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def u(self, a: str, b: str) -> None:
        self.p[self.f(a)] = self.f(b)


def decrire(q: str) -> str:
    e = ENT.get(q)
    if not e:
        return f"{q} (non lu)"
    p31 = [LAB.get(c_id(c), "?") for c in claims(q, "P31") if c_id(c)]
    p1998 = [f"{c_val(c)}{dates_q(c)}" for c in claims(q, "P1998")]
    parents = [LAB.get(c_id(c), "?") + f"({c_id(c)})" for c in claims(q, "P5138") if c_id(c)]
    noms = [f"{(c_val(c) or {}).get('text', '?')}{dates_q(c)}" for c in claims(q, "P1448") if isinstance(c_val(c), dict)]
    prec = [LAB.get(c_id(c), "?") for c in claims(q, "P1365") if c_id(c)]
    suiv = [LAB.get(c_id(c), "?") for c in claims(q, "P1366") if c_id(c)]
    sl = sorted(k[:-4] for k in (e.get("sitelinks") or {}))
    return (f"{q} «{LAB.get(q, q)}» P31={p31} P1998={p1998} parent(P5138)={parents or '-'} P1448({len(noms)})={court(noms[:4], 160)} "
            f"remplace(P1365)={prec or '-'} remplacé par(P1366)={suiv or '-'} wikis={sl}")


def partieC() -> None:
    code_lignees: Dict[str, List[str]] = defaultdict(list)
    for lignee, d in A_CODES.items():
        for code in d:
            code_lignees[code].append(lignee)
    for lignee, codes in STATIQUE.items():
        for code in codes:
            if lignee not in code_lignees[code]:
                code_lignees[code].append(lignee)
    if not A_CODES:
        print("[INFO] partie A sans résultat : seuls les codes de la consigne sont utilisés")
    codes = list(code_lignees)
    print(f"-- {len(codes)} codes UCI à rechercher : {codes}")
    items_code: Dict[str, Optional[List[str]]] = {}
    for code in codes:
        if not ok():
            print("[BUDGET] recherches de codes interrompues")
            break
        items_code[code] = recherche(f"haswbstatement:P1998={code}", 20)
    tous = [q for v in items_code.values() for q in (v or [])]
    ent_full(tous)
    # une génération de plus : cibles de P5138 / P1365 / P1366
    cibles = [c_id(c) for q in tous for p in ("P5138", "P1365", "P1366") for c in claims(q, p) if c_id(c)]
    ent_full([q for q in cibles if q])
    refs = [c_id(c) for q in list(ENT) for p in ("P31", "P5138", "P1365", "P1366") for c in claims(q, p) if c_id(c)]
    lab([q for q in refs if q])

    # --- détail par code
    cnt = Counter()
    print("\n   (saisons = saisons où le code est le code dominant d'une lignée, partie A)")
    for code in codes:
        v = items_code.get(code)
        sais = sorted({a for l in A_CODES.values() for cd, s in l.items() if cd == code for a in s})
        print(f"\n   * {code} [{', '.join(code_lignees[code])[:60]}] saisons {sais or '-'} : " + ("recherche échouée" if v is None else f"{len(v)} élément(s)"))
        if v is None:
            cnt["echec"] += 1
            continue
        cnt["n=0" if not v else ("n=1" if len(v) == 1 else "n>1")] += 1
        for q in v:
            print(f"       - {decrire(q)}")

    # --- chaîne code -> élément stable
    uf = UF()
    for q in ENT:
        uf.f(q)
        for p in ("P5138", "P1365", "P1366"):
            for c in claims(q, p):
                if c_id(c):
                    uf.u(q, c_id(c))
    print("\n-- Chaîne « code UCI -> élément équipe stable » par lignée")
    print("   (stable = parent P5138 de l'élément s'il existe, sinon l'élément lui-même ; composante = éléments reliés par P5138 / P1365 / P1366)")
    constructibles = 0
    for lignee in list(e1.LIGNEES) + [l for l in STATIQUE if l not in e1.LIGNEES]:
        cs = [c for c in codes if lignee in code_lignees[c] and (lignee in STATIQUE or lignee in A_CODES)]
        sans, avec = [], []
        stables, comps = set(), set()
        for c in cs:
            v = items_code.get(c)
            if not v:
                sans.append(c)
                continue
            avec.append(c)
            for q in v:
                par = [c_id(x) for x in claims(q, "P5138") if c_id(x)]
                stables.add(par[0] if par else q)
                comps.add(uf.f(q))
        verdict = "CHAÎNE OK" if avec and not sans and len(stables) == 1 else ("COMPOSANTE UNIQUE" if avec and not sans and len(comps) == 1 else
                                                                              "PARTIEL" if avec else "AUCUN ÉLÉMENT")
        constructibles += verdict in ("CHAÎNE OK", "COMPOSANTE UNIQUE")
        print(f"   {lignee:<34} {verdict:<18} codes avec élément {avec} ; sans élément {sans} ; éléments stables distincts {len(stables)} "
              f"({', '.join(LAB.get(s, s) for s in sorted(stables))[:90]}) ; composantes {len(comps)}")
    synth("C", f"codes : {len(codes)} testés ; résultats par code {dict(cnt)} ; éléments lus {len(ENT)}")
    synth("C", f"lignées dont tous les codes mènent à un élément stable unique (ou à une composante unique) : {constructibles}/{len(STATIQUE)}")
    nbp = sum(1 for q in tous if claims(q, "P5138"))
    nbd = sum(1 for q in set(tous) for c in claims(q, "P1998") if c.get("qualifiers"))
    synth("C", f"parmi {len(set(tous))} éléments trouvés : {nbp} avec P5138 (saison d'équipe), {nbd} déclarations P1998 avec qualificatifs de dates")


PARTIES = {"A": ("TeamId DataRide", partieA), "B": ("Wikidata coureurs (recherche)", partieB), "C": ("Wikidata équipes (recherche)", partieC)}


def main() -> None:
    t0 = time.time()
    print(f"Essai encyclopédie E0 bis - {datetime.date.today()} - UA : {netutil.USER_AGENT}")
    for n, (nom, fn) in PARTIES.items():
        titre(f"PARTIE {n} : {nom}")
        if time.time() >= FIN_GLOBAL:
            RESUME[n] = "non lancée (budget global épuisé)"
            print("[BUDGET] partie ignorée")
            continue
        _fin_partie[0] = time.time() + LIMITES[n]
        _echecs[0] = 0
        t1 = time.time()
        try:
            fn()
            RESUME[n] = f"terminée en {time.time() - t1:.0f} s" + ("" if ok() else " (budget de la partie dépassé : sortie partielle)")
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
    print(f"\nRequêtes par hôte : {dict(e1.REQ)} ; durée totale {time.time() - t0:.0f} s ; hôtes abandonnés : {sorted(netutil._blocked_hosts) or 'aucun'}")


if __name__ == "__main__":
    main()
