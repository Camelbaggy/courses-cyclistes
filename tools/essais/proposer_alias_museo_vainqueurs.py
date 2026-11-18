#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preuve d'alias Museo par les vainqueurs 2009-2025 (complète proposer_alias_museo.py, qui prouve par 2005-2008).

La page albo Museo d'une course donne le vainqueur de TOUTES les éditions, y compris après 2008 ; nos éditions UCI (`entites/courses/<lettre>.json`)
donnent le vainqueur (rang 1 du podium) de chaque édition 2009-2025. Pour une clé d'épreuve et une course Museo candidate :
  - année concordante = vainqueurs Museo et UCI de la même année civile (`start_date`) qui se recoupent (`wikidata.nom_concorde`, ordre des mots indifférent) ;
  - année discordante = les deux côtés ont un vainqueur cette année-là et aucun ne concorde ;
  - preuve (`type: "vainqueurs_2009_2025"`) = au moins 2 années concordantes ET aucune discordance (une discordance expliquée est listée à part,
    avec son explication, et ne compte pas : explication manuelle consignée dans EXPLICATIONS ci-dessous).
Pour les épreuves de l'index sans candidate (ou sans preuve), cherche des candidates dans la liste complète des courses Museo : même pays, recouvrement de
mots non génériques ou nom proche, années d'existence compatibles avec nos éditions 2009-2025 ; lit les albos nécessaires (cache gzip, UA et pause de museo.py).
Ne modifie JAMAIS alias_museo.json.

    python tools/essais/proposer_alias_museo_vainqueurs.py --archives DIR --cache DOSSIER --entree docs/recherche/museo_alias_proposes.json [--sec]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import museo  # noqa: E402
import netutil  # noqa: E402
import proposer_alias_museo as pam  # noqa: E402
import wikidata  # noqa: E402

# (id Museo, clé d'épreuve, année) -> explication d'une discordance, vérifiée à la main (vide au départ : rien n'est expliqué d'office)
EXPLICATIONS = {}
AN0, AN1 = 2009, 2025


def vainqueurs_uci(archives):
    """{clé : {année civile : [noms du vainqueur]}} d'après entites/courses (rang 1 du podium de chaque édition)."""
    out = {}
    dossier = os.path.join(archives, "entites", "courses")
    for f in sorted(os.listdir(dossier)):
        if f == "index.json":
            continue
        d = museo._lire_json(os.path.join(dossier, f), {})
        for k, v in d.items():
            for e in v.get("editions", []):
                an = int((e.get("start_date") or "0000")[:4]) or e.get("season")
                if not an or not AN0 <= an <= AN1:
                    continue
                for p in e.get("podium") or []:
                    if p.get("rank") == 1 and p.get("name"):
                        out.setdefault(museo.gp(k), {}).setdefault(an, []).append({"nom": p["name"], "date": e.get("start_date")})
    return out


def vainqueurs_museo(albo):
    out = {}
    for e in (albo or {}).get("editions", []):
        if AN0 <= e["annee"] <= AN1 and e.get("vainqueur"):
            out.setdefault(e["annee"], []).append({"nom": e["vainqueur"]["nom"], "date": e.get("date")})
    return out


def variante_de_nom(a, b):
    """Même coureur écrit autrement (Thomas / Tom Pidcock, Izagirre / Izaguirre Insausti, Rob / Robert Power) : au moins un mot de >= 4 lettres commun ET
    même initiale du premier mot (prénom). Explication d'une discordance, jamais une concordance (ne compte pas dans la preuve)."""
    ta, tb = netutil.normalize(a).split(), netutil.normalize(b).split()
    return bool(ta and tb and ta[0][0] == tb[0][0] and any(len(t) >= 4 for t in set(ta) & set(tb)))


def comparer(cid, cle, mus, uci):
    conc, disc, expl, mem_date = [], {}, {}, 0
    for an in sorted(set(mus) & set(uci)):
        noms_u = [x["nom"] for x in uci[an]]
        if any(wikidata.nom_concorde(m["nom"], noms_u) for m in mus[an]):
            conc.append(an)
            if any(m.get("date") and m["date"] == u.get("date") for m in mus[an] for u in uci[an]):
                mem_date += 1
        else:
            if any(variante_de_nom(m["nom"], u) for m in mus[an] for u in noms_u):
                expl[str(an)] = {"museo": [m["nom"] for m in mus[an]], "uci": noms_u, "date_museo": mus[an][0].get("date"),
                                 "date_uci": uci[an][0].get("date"), "explication": "variante de nom (mot commun de >= 4 lettres, même initiale du prénom)"}
                continue
            info = {"museo": [m["nom"] for m in mus[an]], "uci": noms_u, "date_museo": mus[an][0].get("date"), "date_uci": uci[an][0].get("date")}
            if (cid, cle, an) in EXPLICATIONS:
                info["explication"] = EXPLICATIONS[(cid, cle, an)]
                expl[str(an)] = info
            else:
                disc[str(an)] = info
    return {"type": "vainqueurs_2009_2025", "annees_concordantes": conc, "annees_discordantes": disc, "annees_discordantes_expliquees": expl,
            "annees_meme_date": mem_date, "annees_uci": sorted(uci), "annees_museo": sorted(mus),
            "annees_comparables": len(set(mus) & set(uci)),
            "preuve": len(conc) >= 2 and not disc}


def raison_non_preuve(r):
    if r["preuve"]:
        return None
    if r["annees_discordantes"]:
        return "discordance (%d année(s))" % len(r["annees_discordantes"])
    if not r["annees_uci"]:
        return "aucune édition UCI 2009-2025 avec vainqueur"
    if r["annees_comparables"] < 2:
        return "moins de 2 années comparables (%d)" % r["annees_comparables"]
    return "moins de 2 années concordantes"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archives", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--entree", required=True)
    ap.add_argument("--max-requetes", type=int, default=400)
    ap.add_argument("--sec", action="store_true", help="n'écrit rien, liste seulement les candidates trouvées")
    ap.add_argument("--max-cand", type=int, default=3, help="candidates lues par épreuve sans candidate")
    a = ap.parse_args()
    arch = a.archives
    os.makedirs(a.cache, exist_ok=True)
    prop = museo._lire_json(a.entree, {})
    reg = museo._lire_json(os.path.join(arch, "sources", "museo", "courses.json"), {})["courses"]
    index = museo.charger_index_epreuves(arch)
    uci = vainqueurs_uci(arch)
    sess = museo.Session(a.cache, 0, a.max_requetes)
    albos = {}

    def albo(cid):
        if cid not in albos:
            c = reg[cid]
            p = sess.page("/content/corse/corsa/%s-%s/index.html" % (cid, c["slug"]), mettre_en_cache=True)
            albos[cid] = museo.lire_albo(p) if p else None
        return albos[cid]

    # 1. candidates existantes (38 courses Museo) : preuve 2009-2025 pour chaque clé
    for p in prop["epreuves"]:
        mus = vainqueurs_museo(albo(p["museo_id"]))
        for c in p["cles"]:
            r = comparer(p["museo_id"], c["cle"], mus, uci.get(c["cle"], {}))
            r["raison_non_preuve"] = raison_non_preuve(r)
            c["preuve_2009_2025"] = r
    # 2. épreuves sans candidate : recherche dans toute la liste Museo
    deja_ids = {p["museo_id"] for p in prop["epreuves"]}
    deja_ids |= {c["museo_id"] for c in prop.get("championnats", [])}
    pris = {k: set() for k in prop["epreuves_sans_candidate"]}
    nouvelles = []
    for cle in prop["epreuves_sans_candidate"]:
        e = index.get(cle, {})
        pays = cle.rsplit("|", 1)[1]
        ys = sorted(uci.get(cle, {}))
        lo, hi = (min(ys), max(ys)) if ys else (e.get("s", [AN0, AN1])[0], e.get("s", [AN0, AN1])[-1])
        cands = []
        deja = []
        for cid, c in reg.items():
            if c.get("sexe") == "F" or c.get("pays") != pays or "debut" not in c or c["fin"] < lo or c["debut"] > hi:
                continue
            if cid in deja_ids:       # course Museo déjà proposée pour une autre clé d'index (autre dénomination) : signalée, jamais relue ici
                kc = museo.cle_museo(c["nom"], c.get("pays"))
                s, j = pam.score(cle, kc)
                if s >= 0.5 or j > 0:
                    deja.append({"museo_id": cid, "museo_nom": c["nom"], "score_nom": round(max(s, j), 2)})
                continue
            kc = museo.cle_museo(c["nom"], c.get("pays"))
            s, j = pam.score(cle, kc)
            nom_cle = cle.rsplit("|", 1)[0]
            ind = any(h in nom_cle and any(w in kc for w in ws) for h, ws in pam.INDICES.items())
            if s >= 0.5 or j > 0 or ind:
                cands.append((max(s, 0.9 if ind else 0, j), cid, kc))
        cands.sort(key=lambda t: (-t[0], t[2]))
        nouvelles.append({"cle": cle, "classe_actuelle": e.get("cat"), "saisons": e.get("s"), "annees_uci_2009_2025": ys,
                          "candidates_trouvees": [{"museo_id": cid, "museo_nom": reg[cid]["nom"], "score_nom": round(s, 2)} for s, cid, kc in cands],
                          "deja_proposees_autre_cle": sorted(deja, key=lambda x: -x["score_nom"])[:3], "lues": []})
        if a.sec:
            print("%-60s uci=%s  cands=%s" % (cle, (ys[0], ys[-1], len(ys)) if ys else "-", [(cid, reg[cid]["nom"], round(s, 2)) for s, cid, _ in cands[:6]]))
            continue
        for s, cid, kc in cands[:a.max_cand]:
            mus = vainqueurs_museo(albo(cid))
            r = comparer(cid, cle, mus, uci.get(cle, {}))
            r["raison_non_preuve"] = raison_non_preuve(r)
            nouvelles[-1]["lues"].append({"museo_id": cid, "museo_nom": reg[cid]["nom"], "pays": reg[cid].get("pays"),
                                          "annees_museo_existence": [reg[cid]["debut"], reg[cid]["fin"]], "score_nom": round(s, 2),
                                          "preuve_2009_2025": r})
    if a.sec:
        return 0
    prop["epreuves_sans_candidate_2009_2025"] = nouvelles
    prop["regle_preuve_2009_2025"] = ("type vainqueurs_2009_2025 : >= 2 années 2009-2025 dont le vainqueur Museo (albo) = vainqueur UCI de notre édition (nom_concorde, "
                                      "ordre des mots indifférent) ET aucune année discordante non expliquée")
    prop["requetes_2009_2025"] = sess.requetes + prop.get("requetes_2009_2025_anterieures", 0)
    # bilan : une ligne par couple (course Museo, clé d'épreuve) prouvé, avec les ambiguïtés (une clé prouvée par plusieurs courses Museo
    # aux années concordantes qui se recoupent, ou une course Museo prouvée pour plusieurs clés)
    lignes = []
    for p in prop["epreuves"]:
        for c in p["cles"]:
            r = c["preuve_2009_2025"]
            lignes.append({"museo_id": p["museo_id"], "museo_nom": p["museo_nom"], "cle": c["cle"], "classe_actuelle": c.get("classe_actuelle"),
                           "origine": "candidate_2005_2008", "preuve_2005_2008": c["preuve"], "preuve": r["preuve"], "type": r["type"],
                           "annees_concordantes": r["annees_concordantes"], "annees_discordantes": sorted(r["annees_discordantes"]),
                           "annees_variantes_de_nom": sorted(r["annees_discordantes_expliquees"]), "raison_non_preuve": r["raison_non_preuve"]})
    for n in nouvelles:
        for l in n["lues"]:
            r = l["preuve_2009_2025"]
            lignes.append({"museo_id": l["museo_id"], "museo_nom": l["museo_nom"], "cle": n["cle"], "classe_actuelle": n["classe_actuelle"],
                           "origine": "recherche_2009_2025", "preuve_2005_2008": None, "preuve": r["preuve"], "type": r["type"],
                           "annees_concordantes": r["annees_concordantes"], "annees_discordantes": sorted(r["annees_discordantes"]),
                           "annees_variantes_de_nom": sorted(r["annees_discordantes_expliquees"]), "raison_non_preuve": r["raison_non_preuve"]})
    par_cle, par_id = {}, {}
    for l in lignes:
        if l["preuve"]:
            par_cle.setdefault(l["cle"], []).append(l["museo_id"])
            par_id.setdefault(l["museo_id"], []).append(l["cle"])
    for l in lignes:
        l["ambigu_cle_plusieurs_courses_museo"] = l["preuve"] and len(set(par_cle[l["cle"]])) > 1
        l["museo_prouvee_pour_plusieurs_cles"] = l["preuve"] and len(set(par_id[l["museo_id"]])) > 1
    prop["bilan_2009_2025"] = lignes
    museo._ecrire_json(a.entree, prop)
    n_ok = sum(1 for p in prop["epreuves"] for c in p["cles"] if c["preuve_2009_2025"]["preuve"])
    n_new = sum(1 for n in nouvelles if any(l["preuve_2009_2025"]["preuve"] for l in n["lues"]))
    print("candidates existantes : %d clés prouvées (2009-2025) ; sans candidate : %d / %d épreuves avec une candidate prouvée ; %d requêtes"
          % (n_ok, n_new, len(nouvelles), sess.requetes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
