#!/usr/bin/env python3
"""Sonde : détail des 7 groupes de courses renommées NON prouvés (essai alias_courses du 17/11/2026).

(1) Discordances : pour chaque année discordante, NOTRE vainqueur (rider_id, nom) et celui de Wikidata (élément d'édition, QID, libellé,
naissance P569, et rider_id rapproché par le cache wikidata/coureurs.json s'il existe). (2) Aucune série trouvée : recherche élargie
(wbsearchentities fr / en / langue du pays, libellés + descriptions) et, pour chaque candidate « course cycliste », concordance par clé.
Lecture seule ; résultat imprimé dans les logs.
"""
import datetime as dt
import json
import os
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "tools")
import collector  # noqa: E402
import historique  # noqa: E402
import wikidata  # noqa: E402
from essais.essai_alias_courses import telecharger  # noqa: E402

DISCORDANCES = {  # série -> clés
    "Q1537748": ["tour du loir et cher|FRA", "tour du loir et cher e provost|FRA"],
    "Q1264773": ["tour of magnificent qinghai|CHN", "tour of qinghai lake|CHN"],
    "Q930866": ["presidential cycling tour of turkiye|TUR", "presidential cycling tour of turkey|TUR"],
    "Q111185909": ["visit south aegean islands|GRE", "south aegean tour|GRE"],
}
SANS_SERIE = {
    "4joursdunkerque": (["4 jours de dunkerque grand prix des hauts de france|FRA", "4 jours de dunkerque tour du nord pas de calais|FRA"],
                        ["Quatre Jours de Dunkerque", "4 Jours de Dunkerque", "Four Days of Dunkirk"], "fr"),
    "routelimousin": (["tour du limousin nouvelle aquitaine|FRA", "tour du limousin|FRA"], ["Tour du Limousin"], "fr"),
    "thailand": (["the princess maha chakri sirindhorn s cup tour of thailand|THA", "the princess maha chakri sirindhorns cup tour of thailand|THA",
                  "the princess maha chackri sirindhorn s cup tour of thailand|THA"], ["Tour of Thailand", "Tour de Thaïlande"], "th"),
    "aegean": (["visit south aegean islands|GRE", "south aegean tour|GRE"], ["Visit South Aegean Islands", "South Aegean Tour", "Tour of South Aegean"], "el"),
}


def main():
    alias = collector.charger_alias(collector.ALIAS_COURSES)
    tmp = tempfile.mkdtemp()
    ent = os.path.join(tmp, "entites")
    cles = {alias.get(k, k) for v in DISCORDANCES.values() for k in v} | {alias.get(k, k) for v in SANS_SERIE.values() for k in v[0]}
    telecharger(ent, [f"courses/{l}.json" for l in sorted({historique._lettre(k) for k in cles})] + ["wikidata/coureurs.json"])
    historique.ANNEES_PREUVE = (1900, 2100)
    ctx = historique.Ctx(historique.creer_api(), historique.Cache(os.path.join(ent, "historique")), ent, dt.date.today(), 25)
    nos = historique.nos_vainqueurs(ent)
    qid_vers_rider = {v.get("qid"): r for r, v in ctx.wd_coureurs().items() if v.get("qid")}
    out = {"discordances": {}, "sans_serie": {}}
    for q, ks in DISCORDANCES.items():
        brut = historique.lire_editions(ctx, q) or []
        for k in ks:
            k = alias.get(k, k)
            p = historique.preuve_serie(ctx, brut, nos.get(k) or {})
            for an in p["discordances"]:
                eds = [b for b in brut if b["annee"] == an]
                wq = [x for b in eds for x in b["rangs"][1]]
                ents = wikidata.lire_entites(ctx.api, wq, "claims|labels", "fr|en")
                out["discordances"][f"{k} {an}"] = {
                    "nous": nos[k][an], "edition_wd": [b["qid"] for b in eds],
                    "wikidata": [{"qid": x, "nom": (ents.get(x) or {}).get("labels", {}).get("fr", (ents.get(x) or {}).get("labels", {}).get("en", {})).get("value"),
                                  "naissance": wikidata.naissance_jour(ents.get(x)), "rider_id_rapproche": qid_vers_rider.get(x)} for x in wq]}
    for w, (ks, noms, lang) in SANS_SERIE.items():
        res = {}
        for lg in ("fr", "en", lang):
            for n in noms:
                rep = ctx.api.appel(historique.WD_API, action="wbsearchentities", search=n, language=lg, uselang="fr", limit=10, type="item")
                for x in (rep or {}).get("search", []):
                    res.setdefault(x["id"], {"label": x.get("label"), "description": x.get("description")})
        ents = wikidata.lire_entites(ctx.api, list(res), "claims", "fr")
        cands = {}
        for q, info in res.items():
            classes = [c for c in (wikidata.qid_de(r) for r in wikidata.revendications(ents.get(q), "P31")) if c]
            info["P31"] = classes
            if any(ctx.sous().est(c) for c in classes):
                brut = historique.lire_editions(ctx, q) or []
                info["editions"] = len(brut)
                cands[q] = {alias.get(k, k): historique.preuve_serie(ctx, brut, nos.get(alias.get(k, k)) or {}) for k in ks}
        out["sans_serie"][w] = {"recherche": res, "concordance": cands}
        print(f"[DETAIL] {w} : {len(res)} résultat(s), {len(cands)} course(s) cycliste(s)", flush=True)
    print("[DETAIL] RESULTATS " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
