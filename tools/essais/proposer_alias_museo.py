#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Propositions d'alias Museo (jamais écrites dans alias_museo.json : à valider une à une par le propriétaire).

(a) épreuves WT / Pro de notre index sans clé exacte chez Museo -> course(s) Museo candidate(s) (nom proche, même pays, active 2005-2008) ;
(b) championnats -> ids Museo candidats.
Preuve (`preuve: true`) : vainqueur de l'albo Museo concordant (`wikidata.nom_concorde`) avec une RÉFÉRENCE LIÉE À NOTRE ÉPREUVE PAR SA CLÉ
(Wikidata `historique/editions`, ou calendrier CQ Ranking dont la clé exacte (cle_museo + alias_courses) est celle de l'épreuve) sur >= 2 années
de 2005-2008. Concordance avec un vainqueur CQ de MÊME DATE ET MÊME PAYS (sans lien de clé : `indice_cq`) : `preuve: true` (`preuve_type: date_pays_cq`) seulement si
le nom de la course est aussi proche (score >= 0,9 : nom normalisé ou indice de nom d'époque) ; sinon `preuve: false`.
Réseau : une page d'albo par candidate (UA et pause de museo.py, cache gzip dans --cache).

    python tools/essais/proposer_alias_museo.py --archives DIR_ARCHIVES --cache DOSSIER --sortie docs/recherche/museo_alias_proposes.json
"""
import argparse
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import collector  # noqa: E402
import museo  # noqa: E402
import netutil  # noqa: E402
import wikidata  # noqa: E402

GENERIQUES = {"tour", "classic", "grand", "prix", "cycliste", "gp", "de", "du", "des", "la", "le", "les", "van", "het", "der", "den", "di",
              "del", "della", "gran", "premio", "ronde", "race", "cycling", "international", "internationale", "men", "elite", "me", "a",
              "en", "em", "bicicleta", "and", "the", "of", "city", "citta", "koers", "rund", "um", "giro", "volta", "vuelta"}
INDICES = {   # noms d'époque / autres noms, pour PRÉSÉLECTIONNER des candidates (jamais une preuve : la preuve = vainqueurs concordants)
    "omloop het nieuwsblad": ["het volk"], "eschborn": ["henninger"], "cyclassics": ["hew", "cyclassics"], "brabantse": ["brabanconne"],
    "donostia": ["san sebastian"], "dauphine": ["dauphine"], "e3": ["e3", "harelbeke"], "kbc driedaagse": ["panne"],
    "driedaagse": ["panne"], "lombardia": ["lombardia"], "plouay": ["plouay"], "petronas": ["langkawi"],
    "munsterland": ["munsterland"], "dutch food valley": ["veenendaal"], "danmark rundt": ["danmark"], "kanton aargau": ["aargau"],
    "canton d argovie": ["aargau"], "parijs brusssel": ["bruxelles", "brussel"], "brabantse": ["brabantse", "brabanconne"],
    "dwars door vlaanderen": ["dwars door vlaanderen"], "finanzplatz eschborn": ["eschborn"], "clasica ciclista san sebastian": ["sebastian"], "wevelgem": ["wevelgem"], "kuurne": ["kuurne"],
}


def jetons(cle):
    return [t for t in cle.rsplit("|", 1)[0].split() if t not in GENERIQUES and len(t) >= 3]


def score(a, b):
    ja, jb = set(jetons(a)), set(jetons(b))
    j = len(ja & jb) / len(ja | jb) if ja and jb else 0.0
    r = difflib.SequenceMatcher(None, a.rsplit("|", 1)[0], b.rsplit("|", 1)[0]).ratio()
    return max(j, r if r >= 0.75 else 0.0), j


def vainqueur_cq(arch, an, entree):
    d = museo._lire_json(os.path.join(arch, "sources", "cqranking", "courses", str(an), "%s.json" % entree.get("id")), None)
    if not isinstance(d, dict) or not d.get("lignes"):
        return None
    l = d["lignes"][0]
    nom = (d.get("noms") or {}).get(str(l[1]))
    return nom if l[0] == 1 and nom else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archives", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--max-requetes", type=int, default=400)
    a = ap.parse_args()
    arch = a.archives
    os.makedirs(a.cache, exist_ok=True)
    reg = museo._lire_json(os.path.join(arch, "sources", "museo", "courses.json"), {})["courses"]
    index = museo.charger_index_epreuves(arch)
    ac = collector.charger_alias(os.path.join(museo.RACINE, "alias_courses.json"))
    cal = museo.charger_calendriers_cq(arch, ac)
    # calendrier CQ complet (championnats compris) par (pays, date) pour l'indice « même date »
    par_date = {}
    for f in sorted(os.listdir(os.path.join(arch, "sources", "cqranking", "calendrier"))):
        d = museo._lire_json(os.path.join(arch, "sources", "cqranking", "calendrier", f), {})
        for m in d.get("mois", {}).values():
            for x in m["courses"]:
                par_date.setdefault((x.get("pays"), x.get("debut")), []).append((d["annee"], x))
    # Wikidata : clé -> {année : nom du vainqueur}
    wd_coureurs = museo._lire_json(os.path.join(arch, "entites", "historique", "coureurs.json"), {})
    wd = {}
    ed_dir = os.path.join(arch, "entites", "historique", "editions")
    for f in os.listdir(ed_dir):
        for k, eds in museo._lire_json(os.path.join(ed_dir, f), {}).items():
            for e in eds:
                q = e.get("vainqueur")
                if q and e.get("statut") == "ok" and 2005 <= e["annee"] <= 2008 and wd_coureurs.get(q, {}).get("nom"):
                    wd.setdefault(gp_(k), {})[e["annee"]] = wd_coureurs[q]["nom"]
    deja = set()          # clés d'index déjà couvertes + ids Museo déjà rattachés (règle 2) : rien à proposer pour eux
    deja_ids = set()
    for cid, c in reg.items():
        k = museo.cle_museo(c.get("nom"), c.get("pays"))
        ck = ac.get(k, k)
        if c.get("sexe") != "F" and k and index.get(ck, {}).get("cat") in museo.CLASSES_INDEX:
            deja.add(ck)
            deja_ids.add(cid)
    sess = museo.Session(a.cache, 0, a.max_requetes)
    albos = {}

    def albo(cid):
        if cid not in albos:
            c = reg[cid]
            p = sess.page("/content/corse/corsa/%s-%s/index.html" % (cid, c["slug"]), mettre_en_cache=True)
            albos[cid] = museo.lire_albo(p) if p else None
        return albos[cid]

    def comparer(cid, cle, refs_cle, pays):
        """années concordantes : (exactes par clé, indice même date + même pays)."""
        al = albo(cid)
        out = {"annees": {}, "exact": [], "indice_cq": []}
        if not al:
            return out
        for e in al["editions"]:
            an = e["annee"]
            if not 2005 <= an <= 2008 or not e.get("vainqueur"):
                continue
            v = e["vainqueur"]["nom"]
            ligne = {"museo": v, "date": e.get("date")}
            refs = refs_cle.get(an, [])
            if refs:
                ligne["reference"] = refs
            if refs and wikidata.nom_concorde(v, refs):
                out["exact"].append(an)
            for (an2, x) in par_date.get((pays, e.get("date")), []):
                w = vainqueur_cq(arch, an2, x) if an2 == an else None
                if w and wikidata.nom_concorde(v, [w]):
                    out["indice_cq"].append(an)
                    ligne["cq_meme_date"] = {"nom": x["nom"], "vainqueur": w}
            out["annees"][str(an)] = ligne
        return out

    def refs_epreuve(cle):
        refs = {}
        for an, nom in wd.get(cle, {}).items():
            refs.setdefault(an, []).append(nom)
        for an, d in cal.items():
            for x in d.get(cle, []):
                w = vainqueur_cq(arch, an, x)
                if w:
                    refs.setdefault(an, []).append(w)
        return refs

    # (a) épreuves WT / Pro sans clé exacte
    props = {}
    sans = []
    for cle, e in sorted(index.items()):
        if e.get("cat") not in ("WT", "Pro") or cle in deja:
            continue
        existait = bool(wd.get(cle)) or e.get("h") or any(cle in cal.get(y, {}) for y in cal)
        pays = cle.rsplit("|", 1)[1]
        cands = []
        for cid, c in reg.items():
            if cid in deja_ids or c.get("sexe") == "F" or "debut" not in c or c["debut"] > 2008 or c["fin"] < 2005 or c.get("pays") != pays:
                continue
            kc = museo.cle_museo(c["nom"], c.get("pays"))
            s, j = score(cle, kc)
            nom_cle = cle.rsplit("|", 1)[0]
            ind = any(h in nom_cle and any(w in kc for w in ws) for h, ws in INDICES.items())
            if s >= 0.5 or ind:
                cands.append((max(s, 0.9 if ind else 0), cid, kc))
        cands.sort(key=lambda t: (-t[0], t[2]))
        if not cands:
            sans.append(cle)
            continue
        if not existait and not any(t[0] >= 0.9 for t in cands):
            cands = cands[:1]          # aucune trace d'une édition avant 2009 : une seule candidate (nom proche), sans référence = sans preuve
        refs = refs_epreuve(cle)
        for s, cid, kc in cands[:2]:
            r = comparer(cid, cle, refs, reg[cid].get("pays"))
            p = props.setdefault(cid, {"museo_id": cid, "museo_nom": reg[cid]["nom"], "pays": reg[cid].get("pays"),
                                       "annees_museo": [reg[cid]["debut"], reg[cid]["fin"]], "cles": []})
            p["cles"].append({"cle": cle, "classe_actuelle": e["cat"], "saisons": e.get("s"), "score_nom": round(s, 2),
                              "references": sorted(refs), "annees_concordantes": r["exact"], "annees_indice_cq": r["indice_cq"],
                              "preuve": len(r["exact"]) >= 2 or (s >= 0.9 and len(r["indice_cq"]) >= 2),
                              "preuve_type": "cle" if len(r["exact"]) >= 2 else ("date_pays_cq" if s >= 0.9 and len(r["indice_cq"]) >= 2 else None),
                              "vainqueurs": r["annees"]})
    # (b) championnats : ids Museo connus, preuve par les classes officielles du calendrier CQ (WCRR, NC* France, CC)
    champ = []
    CIBLES = {"2634": ("Championnats du monde route (élite, en ligne)", None, "WCRR"),
              "34548": ("Jeux olympiques, course en ligne", None, None),
              "20739": ("Championnats de France route (élite)", "FRA", "NC"),
              "180623": ("Championnats d'Afrique, course en ligne", None, "CC"),
              "176524": ("Championnats d'Asie, course en ligne", None, "CC"),
              "233912": ("Championnats d'Océanie, course en ligne", None, "CC"),
              "58073": ("Championnats panaméricains, course en ligne", None, "CC")}
    for cid, (lib, pays, cat) in CIBLES.items():
        if cid not in reg:
            continue
        al = albo(cid)
        ann = {}
        conc = []
        for e in (al or {}).get("editions", []):
            an = e["annee"]
            if not 2005 <= an <= 2008 or not e.get("vainqueur"):
                continue
            v = e["vainqueur"]["nom"]
            ligne = {"museo": v, "date": e.get("date")}
            if cat:
                for ps in par_date.values():
                    for (an2, x) in ps:
                        if an2 != an or x.get("debut") != e.get("date") or not (x.get("categorie") or "").startswith(cat):
                            continue
                        if pays and x.get("pays") != pays:
                            continue
                        if cat != "WCRR" and "R.R." not in x["nom"]:
                            continue
                        w = vainqueur_cq(arch, an, x)
                        if w and wikidata.nom_concorde(v, [w]):
                            conc.append(an)
                            ligne["cq"] = {"nom": x["nom"], "categorie": x["categorie"], "vainqueur": w}
            ann[str(an)] = ligne
        champ.append({"museo_id": cid, "museo_nom": reg[cid]["nom"], "libelle": lib, "annees_museo": [reg[cid]["debut"], reg[cid]["fin"]],
                      "annees_concordantes": sorted(set(conc)), "preuve": len(set(conc)) >= 2, "vainqueurs": ann})
    sortie = {"produit_par": "tools/essais/proposer_alias_museo.py", "regle_preuve": "vainqueurs concordants sur >= 2 années 2005-2008 avec une référence "
              "liée à l'épreuve par sa clé (Wikidata, CQ) ; championnats : classe officielle CQ (WCRR / NC / CC) à la même date",
              "epreuves": sorted(props.values(), key=lambda p: (not any(c["preuve"] for c in p["cles"]), p["museo_nom"])),
              "championnats": champ, "epreuves_sans_candidate": sans, "requetes": sess.requetes}
    museo._ecrire_json(a.sortie, sortie)
    print("propositions : %d courses Museo, dont %d avec preuve ; championnats %d (preuve %d) ; sans candidate %d ; %d requêtes"
          % (len(props), sum(1 for p in props.values() if any(c["preuve"] for c in p["cles"])), len(champ),
             sum(1 for c in champ if c["preuve"]), len(sans), sess.requetes))


def gp_(k):
    return museo.gp(k)


if __name__ == "__main__":
    main()
