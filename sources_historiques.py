#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pont d'ingestion des archives historiques pré-2009 (`sources/bdd_pre2009/`) pour `encyclopedie.py`.

Lit `<archives_dir>/sources/bdd_pre2009/` (généré par `export_vers_encyclopedie.py`) :
- `manifest.json`
- `courses.json`
- `coureurs.json`
- `equipes.json`
- `editions/<slug>/<year>.json` (strictement `year <= 2008`)

Règles impératives (zéro hallucination) :
- 100 % bibliothèque standard Python 3.11.
- Rapprochement STRICT des épreuves via `collector.cle_edition(nom, pays)` + `alias_courses.json`.
- Rapprochement STRICT des coureurs :
  1. Identifiants externes Wikidata (`entites/wikidata/coureurs.json` champ `ids`, ou `ids_inverse.json` avec `statut == "ok"`) ;
  2. Correspondance exacte nom normalisé (`riders._nom_cle`) + date de naissance complète (ou année unique sans contradiction) ;
  3. Sinon création d'une entité historique dédiée `hist-*` (jamais de fusion floue d'homonymes).
- Normalisation des codes pays d'époque via `pays.pays_ligne()` / `pays.pays_normalise()` / `pays.code_valide()`.
- Conservation multi-sources avec mention explicite du crédit sur chaque édition, palmarès et dans `index.json`.

Tests : python sources_historiques.py --test
"""
import collections
import os
import re
import sys
import tempfile
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import collector
import netutil
import pays
import riders
import selection

ANNEE_MAX_PRE2009 = 2008

CREDITS_SOURCES: Dict[str, str] = {
    "pcs": "ProCyclingStats",
    "firstcycling": "FirstCycling",
    "letour_dataset": "Le Tour Dataset",
    "preflib_00043": "PrefLib 00043",
    "vuelta_open": "Vuelta Open Data",
    "thesports": "the-sports.org",
    "museo": "Museo del Ciclismo",
    "cqranking": "CQ Ranking",
    "mdc": "Mémoire du Cyclisme",
    "clics": "Clics sur le cyclisme",
}

_SYNONYMES_PAYS: Dict[str, str] = {
    "DDR": "GDR",
    "RFA": "FRG",
    "FDR": "FRG",
    "CSI": "EUN",
    "SOV": "URS",
    "SUN": "URS",
    "CSK": "TCH",
    "DEU": "GER",
    "NLD": "NED",
    "CHE": "SUI",
    "DNK": "DEN",
    "PRT": "POR",
    "ZAF": "RSA",
    "HRV": "CRO",
    "SVN": "SLO",
    "BGR": "BUL",
    "GRC": "GRE",
    "SPA": "ESP",
    "SWI": "SUI",
    "MAL": "MAS",
    "SCO": "GBR",
    "URS": "URS",
    "GDR": "GDR",
    "FRG": "FRG",
}

_EXT_ID_CLES = ("pcs", "firstcycling", "cq", "thesports", "mdc", "uci")

_ISO2_VERS_ISO3: Dict[str, str] = {}
for _iso3, _iso2 in netutil.FLAG_CODES.items():
    _ISO2_VERS_ISO3.setdefault(_iso2.upper(), _iso3)
_ISO2_VERS_ISO3.update({
    "SI": "SLO",
    "TG": "TOG",
    "UK": "GBR",
    "SU": "URS",
    "DD": "GDR",
})


def credit_source(code: str) -> str:
    """Libellé officiel à afficher pour une source donnée."""
    c = (code or "").strip().lower()
    return CREDITS_SOURCES.get(c, code or "")


def _sans_vide(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def normaliser_pays(
    ligne_ou_code: Any,
    source: Optional[str] = None,
    annee: Optional[int] = None,
    inconnus: Optional[Dict[str, int]] = None,
) -> Optional[str]:
    """Normalise un code pays brut ou une ligne d'époque vers un code canonique (existant ou disparu).

    Utilise `pays.pays_ligne()` / `pays.pays_normalise()` pour les sources déclarées dans `pays.SOURCES`,
    puis les codes valides (dont `URS`, `GDR`, `FRG`, `TCH`, `YUG`, `SCG`, `EUN`) et synonymes non ambigus.
    """
    src = (source or "").strip().lower()
    if isinstance(ligne_ou_code, dict):
        if src in pays.SOURCES:
            res = pays.pays_ligne(src, ligne_ou_code, annee)
            if res:
                return res
        brut = (
            ligne_ou_code.get("nat_site")
            or ligne_ou_code.get("pays_site")
            or ligne_ou_code.get("nationality")
            or ligne_ou_code.get("nat")
            or ligne_ou_code.get("country")
            or ligne_ou_code.get("pays")
        )
    else:
        brut = ligne_ou_code
    if not brut or not isinstance(brut, str):
        return None
    brut_s = brut.strip()
    if not brut_s:
        return None
    if src in pays.SOURCES:
        res = pays.pays_normalise(brut_s, src, annee)
        if res:
            return res
    haut = brut_s.upper()
    if haut == "TCH":
        return "CZE" if (annee is not None and annee > 1992) else "TCH"
    if len(haut) == 2:
        if haut == "CS":
            return "CZE" if (annee is not None and annee > 1992) else "TCH"
        if haut in _ISO2_VERS_ISO3:
            return _ISO2_VERS_ISO3[haut]
    if pays.code_valide(haut):
        return haut
    if haut in _SYNONYMES_PAYS:
        cible = _SYNONYMES_PAYS[haut]
        if pays.code_valide(cible):
            return cible
    for s_fallback in ("museo", "thesports", "cqranking", "clics"):
        res = pays.pays_normalise(brut_s, s_fallback, annee)
        if res:
            return res
    import encyclopedie
    codes_nom = encyclopedie._PAYS_PAR_NOM.get(netutil.normalize(brut_s))
    if codes_nom and len(codes_nom) == 1:
        return next(iter(codes_nom))
    if inconnus is not None:
        pays.compter_inconnu(inconnus, brut_s)
    return None


def dossier_bdd_pre2009(archives_dir: str, bdd_dir: Optional[str] = None) -> str:
    """Chemin du dossier `sources/bdd_pre2009/`."""
    return bdd_dir or os.path.join(archives_dir, "sources", "bdd_pre2009")


def _charger_table_entites(chemin: str, cles_id: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    """Charge un fichier JSON (dict `{id: obj}` ou list `[obj, ...]`) indexé par identifiant."""
    brut = collector._load(chemin, None)
    if isinstance(brut, dict):
        return {str(k): v for k, v in brut.items() if isinstance(v, dict)}
    if isinstance(brut, list):
        out: Dict[str, Dict[str, Any]] = {}
        for item in brut:
            if not isinstance(item, dict):
                continue
            for k in cles_id:
                val = item.get(k)
                if val is not None and str(val).strip():
                    out[str(val).strip()] = item
                    break
        return out
    return {}


def _normaliser_date(val: Any) -> Tuple[Optional[str], Optional[str]]:
    """Extrait `(date_complete, annee_4c)` depuis une date ISO ou partielle."""
    if not val or not isinstance(val, str):
        return None, None
    s = val.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s, s[:4]
    m = re.match(r"^(\d{4})", s)
    if m:
        return None, m.group(1)
    return None, None


class IndexCoureurs:
    """Index de rapprochement strict des coureurs (Wikidata IDs + nom normalisé & naissance)."""

    def __init__(
        self,
        cour: Dict[str, Dict[str, Any]],
        wd: Dict[str, Dict[str, Any]],
        alias_coureurs: Dict[str, str],
    ) -> None:
        self.cour = cour
        self.par_ext: Dict[Tuple[str, str], Set[str]] = collections.defaultdict(set)
        self.par_qid: Dict[str, Set[str]] = collections.defaultdict(set)
        self.par_nom_date: Dict[Tuple[Tuple[str, ...], str], Set[str]] = collections.defaultdict(set)
        self.par_nom_an: Dict[Tuple[Tuple[str, ...], str], Set[str]] = collections.defaultdict(set)
        self.resolus: Dict[str, str] = {}

        for cid, c in cour.items():
            nom = c.get("name") or ""
            cle_nom = riders._nom_cle(nom) if nom else ()
            if not cle_nom:
                continue
            d_comp, an = _normaliser_date(c.get("birth_date"))
            if d_comp:
                self.par_nom_date[(cle_nom, d_comp)].add(cid)
            if an:
                self.par_nom_an[(cle_nom, an)].add(cid)

        wd_coureurs = wd.get("coureurs") or {}
        for rid_brut, ent in wd_coureurs.items():
            if not isinstance(ent, dict):
                continue
            cid = alias_coureurs.get(rid_brut, rid_brut)
            if cid not in cour:
                continue
            qid = ent.get("qid")
            if isinstance(qid, str) and qid:
                self.par_qid[qid].add(cid)
            ids = ent.get("ids") or {}
            if isinstance(ids, dict):
                for src_k in _EXT_ID_CLES:
                    vals = ids.get(src_k)
                    if isinstance(vals, str):
                        vals = [vals]
                    if isinstance(vals, list):
                        for v in vals:
                            vs = str(v).strip().lower()
                            if vs:
                                self.par_ext[(src_k, vs)].add(cid)

        ids_inverse = wd.get("ids_inverse") or {}
        for src_k, entries in ids_inverse.items():
            if not isinstance(entries, dict):
                continue
            src_norm = "cq" if src_k == "cq" else ("thesports" if src_k == "thesports" else src_k)
            for ext_val, info in entries.items():
                if not isinstance(info, dict) or info.get("statut") != "ok":
                    continue
                qid = info.get("qid")
                cids = self.par_qid.get(qid) if qid else None
                if cids and len(cids) == 1:
                    self.par_ext[(src_norm, str(ext_val).strip().lower())].update(cids)

    def _enregistrer_dans_index(self, cid: str, nom: str, d_comp: Optional[str], an: Optional[str]) -> None:
        cle_nom = riders._nom_cle(nom) if nom else ()
        if not cle_nom:
            return
        if d_comp:
            self.par_nom_date[(cle_nom, d_comp)].add(cid)
        if an:
            self.par_nom_an[(cle_nom, an)].add(cid)

    def resoudre(
        self,
        hist_id: Optional[str],
        info: Dict[str, Any],
        source: str,
        nat: Optional[str],
    ) -> Tuple[str, bool]:
        """Résout un coureur pré-2009 vers un `cid` existant ou crée un `hist-*` dédié.

        Retourne `(cid, rapproche_existant)`.
        """
        cle_cache = str(hist_id or "").strip()
        if cle_cache and cle_cache in self.resolus:
            cid = self.resolus[cle_cache]
            return cid, not cid.startswith("hist-")

        cands_ext: Set[str] = set()
        qid = info.get("qid")
        if isinstance(qid, str) and qid in self.par_qid:
            cands_ext.update(self.par_qid[qid])
        ids = info.get("ids") if isinstance(info.get("ids"), dict) else {}
        for src_k in _EXT_ID_CLES:
            v = ids.get(src_k) or info.get(f"{src_k}_id")
            if v is None:
                continue
            vals = v if isinstance(v, list) else [v]
            for item in vals:
                vs = str(item).strip().lower()
                if vs and (src_k, vs) in self.par_ext:
                    cands_ext.update(self.par_ext[(src_k, vs)])
        if len(cands_ext) == 1:
            cid = next(iter(cands_ext))
            if cle_cache:
                self.resolus[cle_cache] = cid
            return cid, True

        nom = (info.get("name") or info.get("nom") or "").strip()
        d_comp, an = _normaliser_date(info.get("birth_date") or info.get("naissance"))
        if not an and info.get("birth_year"):
            y_str = str(info["birth_year"]).strip()
            if re.fullmatch(r"\d{4}", y_str):
                an = y_str
        cle_nom = riders._nom_cle(nom) if nom else ()

        if cle_nom and d_comp:
            cands_date = self.par_nom_date.get((cle_nom, d_comp))
            if cands_date and len(cands_date) == 1:
                cid = next(iter(cands_date))
                if cle_cache:
                    self.resolus[cle_cache] = cid
                return cid, True
        elif cle_nom and an:
            cands_an = self.par_nom_an.get((cle_nom, an))
            if cands_an and len(cands_an) == 1:
                cid = next(iter(cands_an))
                nat_ex = (self.cour.get(cid) or {}).get("nationality")
                # Pas de fusion si nationalités connues contradictoires (hors pays disparu)
                if not (nat and nat_ex and nat != nat_ex and not pays.est_historique(nat) and not pays.est_historique(nat_ex)):
                    if cle_cache:
                        self.resolus[cle_cache] = cid
                    return cid, True

        # Aucun rapprochement strict certain : création d'une entité historique dédiée
        base_slug = netutil.slugify(cle_cache) if cle_cache else ""
        if base_slug.startswith("hist-"):
            base_slug = base_slug[5:]
        if not base_slug:
            base_slug = netutil.slugify(nom) or "coureur"
            if d_comp:
                base_slug = f"{base_slug}-{d_comp.replace('-', '')}"
            elif an:
                base_slug = f"{base_slug}-{an}"
        cid = f"hist-{base_slug}"
        suffix = 2
        while cid in self.cour and cid not in self.resolus.values():
            cid = f"hist-{base_slug}-{suffix}"
            suffix += 1
        if cle_cache:
            self.resolus[cle_cache] = cid
        self._enregistrer_dans_index(cid, nom, d_comp, an)
        return cid, False


def _extraire_sources(ed: Dict[str, Any], course_meta: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Extrait `(source_principale, toutes_sources)` en conservant les identifiants exacts."""
    brute_list = ed.get("sources") or course_meta.get("sources")
    src_prim = (ed.get("source") or course_meta.get("source") or "").strip().lower()
    srcs: List[str] = []
    if src_prim:
        srcs.append(src_prim)
    if isinstance(brute_list, list):
        for s in brute_list:
            ss = str(s).strip().lower()
            if ss and ss not in srcs:
                srcs.append(ss)
    if not srcs:
        srcs = ["bdd_pre2009"]
    return srcs[0], srcs


def _extraire_lignes_classement(ed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrait le classement général / d'un jour d'une édition pré-2009."""
    final = ed.get("final")
    if isinstance(final, dict) and isinstance(final.get("gc"), list):
        return [r for r in final["gc"] if isinstance(r, dict)]
    for cle in ("gc", "results", "classement", "podium"):
        val = ed.get(cle)
        if isinstance(val, list) and val:
            return [r for r in val if isinstance(r, dict)]
    stages = ed.get("stages")
    if isinstance(stages, list) and stages:
        last = stages[-1]
        if isinstance(last, dict):
            res = last.get("results") or {}
            if isinstance(res, dict):
                rows = res.get("gc") or res.get("stage")
                if isinstance(rows, list):
                    return [r for r in rows if isinstance(r, dict)]
    return []


def _editions_par_dossier(bdd: str) -> List[Tuple[str, int, str]]:
    """Liste triée `(slug_course, annee, chemin)` des fichiers dans `editions/<slug>/<year>.json`."""
    ed_root = os.path.join(bdd, "editions")
    if not os.path.isdir(ed_root):
        return []
    out: List[Tuple[str, int, str]] = []
    for slug in sorted(os.listdir(ed_root)):
        sdir = os.path.join(ed_root, slug)
        if not os.path.isdir(sdir):
            continue
        for fname in sorted(os.listdir(sdir)):
            m = re.fullmatch(r"(\d{4})\.json", fname)
            if m:
                out.append((slug, int(m.group(1)), os.path.join(sdir, fname)))
    return out


def appliquer_bdd_pre2009(
    archives_dir: str,
    cour: Dict[str, Dict[str, Any]],
    courses: Dict[str, Dict[str, Any]],
    pays_agg: Dict[str, Dict[str, Any]],
    eq_par_an: Dict[int, Dict[str, Dict[str, Any]]],
    eq_index: List[Dict[str, Any]],
    eq_index_by_id: Dict[str, Dict[str, Any]],
    eq_rech: Dict[str, Dict[str, Any]],
    wd: Dict[str, Dict[str, Any]],
    alias_coureurs: Dict[str, str],
    alias_courses: Dict[str, str],
    equipes_ecrites: Optional[Set[str]] = None,
    bdd_dir: Optional[str] = None,
    est_nationale_fn: Optional[Callable[[str, Iterable[Optional[str]]], Optional[str]]] = None,
    gt_par_cle: Optional[Dict[str, str]] = None,
    editions_dir: Optional[str] = None,
    ecrire_fn: Optional[Callable[[str, Any], None]] = None,
) -> Dict[str, Any]:
    """Ingère `<archives_dir>/sources/bdd_pre2009/` (`year <= 2008`) dans les structures d'`encyclopedie.py`."""
    bdd = dossier_bdd_pre2009(archives_dir, bdd_dir)
    rapport_vide: Dict[str, Any] = {
        "present": False,
        "editions_ajoutees": 0,
        "coureurs_ajoutes": 0,
        "coureurs_rapproches": 0,
        "equipes_ajoutees": 0,
        "nationales_ajoutees": 0,
        "annees": [],
        "sources": [],
        "credits": [],
        "editions_ignorees": 0,
        "courses_sans_cle": 0,
        "pays_inconnus": {},
        "editions_ecrites": {},
    }
    if not os.path.isdir(bdd):
        return rapport_vide
    fichiers_ed = _editions_par_dossier(bdd)
    if not fichiers_ed and not os.path.exists(os.path.join(bdd, "manifest.json")):
        return rapport_vide

    courses_meta = _charger_table_entites(os.path.join(bdd, "courses.json"), ("slug", "id"))
    coureurs_meta = _charger_table_entites(os.path.join(bdd, "coureurs.json"), ("id", "rider_id"))
    equipes_meta = _charger_table_entites(os.path.join(bdd, "equipes.json"), ("id", "slug"))

    idx = IndexCoureurs(cour, wd, alias_coureurs)
    inconnus: Dict[str, int] = {}
    sources_vues: Set[str] = set()
    annees_vues: Set[int] = set()
    coureurs_nouveaux: Set[str] = set()
    coureurs_rapproches: Set[str] = set()
    editions_ajoutees = 0
    editions_ignorees = 0
    courses_sans_cle = 0
    equipes_ajoutees = 0
    nationales_ajoutees = 0
    editions_ecrites: Dict[str, Set[str]] = collections.defaultdict(set)

    # Cumuls d'équipes et pays pré-2009 par année : {an: {slug: ...}}
    eq_cumul: Dict[int, Dict[str, Dict[str, Any]]] = collections.defaultdict(dict)
    pays_saison_cumul: Dict[int, Dict[str, Dict[str, int]]] = collections.defaultdict(dict)

    # Années déjà couvertes par les fiches UCI pour chaque clé d'épreuve
    annees_uci: Dict[str, Set[int]] = {}
    for cle_c, obj_c in courses.items():
        annees_uci[cle_c] = {int(e["season"]) for e in obj_c.get("editions") or [] if e.get("season") is not None}

    for slug, an, chemin in fichiers_ed:
        if an > ANNEE_MAX_PRE2009:
            editions_ignorees += 1
            continue
        ed = collector._load(chemin, None)
        if not isinstance(ed, dict):
            continue
        c_meta = courses_meta.get(slug) or {}
        source_prim, sources_ed = _extraire_sources(ed, c_meta)

        nom_course = (ed.get("name") or c_meta.get("name") or slug.replace("-", " ")).strip()
        pays_brut = ed.get("country") or c_meta.get("country") or ed.get("pays") or c_meta.get("pays")
        pays_code = normaliser_pays(pays_brut, source_prim, an, inconnus)
        cle_brute = collector.cle_edition(nom_course, pays_code)
        cle = alias_courses.get(cle_brute, cle_brute) if cle_brute else None
        if not cle:
            courses_sans_cle += 1
            continue

        if an in annees_uci.get(cle, set()):
            editions_ignorees += 1
            continue

        sources_vues.update(sources_ed)
        annees_vues.add(an)
        editions_ajoutees += 1

        race_id = str(ed.get("race_id") or ed.get("id") or f"hist-{slug}-{an}")
        start_date = ed.get("start_date") or ed.get("date") or f"{an}-01-01"
        end_date = ed.get("end_date") or start_date
        uci_class = ed.get("uci_class") or c_meta.get("uci_class")
        category = ed.get("category") or c_meta.get("category") or (selection.categorie_classe(uci_class) if uci_class else None)
        race_type = ed.get("race_type") or c_meta.get("race_type") or ("stage_race" if ed.get("stages") else "one_day")
        est_gt = gt_par_cle.get(cle) if gt_par_cle and race_type == "stage_race" else None

        refs_ed = ed.get("riders") if isinstance(ed.get("riders"), dict) else {}
        lignes = _extraire_lignes_classement(ed)

        podium: List[Dict[str, Any]] = []
        best_french: Optional[Dict[str, Any]] = None
        classes_vus: Set[str] = set()
        riders_fiche: Dict[str, Dict[str, Any]] = {}
        rows_norm: List[Dict[str, Any]] = []

        for row in lignes:
            rang = row.get("rank")
            if rang is None:
                continue
            try:
                rang_int = int(rang)
            except (TypeError, ValueError):
                continue
            status = row.get("status")
            if status is not None or rang_int < 1:
                continue

            rid_brut = row.get("rider_id") or row.get("id")
            info_c: Dict[str, Any] = {}
            if rid_brut and str(rid_brut) in coureurs_meta:
                info_c.update(coureurs_meta[str(rid_brut)])
            if rid_brut and str(rid_brut) in refs_ed and isinstance(refs_ed[str(rid_brut)], dict):
                info_c.update(refs_ed[str(rid_brut)])
            for k in ("name", "nom", "birth_date", "naissance", "birth_year", "nationality", "nat", "nat_site", "team", "team_id", "ids", "qid"):
                if row.get(k) is not None and k not in info_c:
                    info_c[k] = row[k]

            nat = normaliser_pays(info_c, source_prim, an, inconnus)
            flag = pays.drapeau(nat) if nat else None
            cid, est_rapproche = idx.resoudre(str(rid_brut) if rid_brut else None, info_c, source_prim, nat)
            if est_rapproche:
                coureurs_rapproches.add(cid)
            else:
                coureurs_nouveaux.add(cid)

            nom_c = (info_c.get("name") or info_c.get("nom") or str(rid_brut or cid)).strip()
            d_comp, _ = _normaliser_date(info_c.get("birth_date") or info_c.get("naissance"))
            eq_nom = info_c.get("team")
            if not eq_nom and info_c.get("team_id") and str(info_c["team_id"]) in equipes_meta:
                eq_nom = equipes_meta[str(info_c["team_id"])].get("name")
            eq_nom = eq_nom.strip() if isinstance(eq_nom, str) and eq_nom.strip() else None

            c_obj = cour.get(cid)
            if c_obj is None:
                c_obj = cour[cid] = {"saisons": {}, "palmares": [], "grands_tours": [], "_stats": collections.Counter()}
                if nom_c:
                    c_obj["name"] = nom_c
                if nat:
                    c_obj["nationality"] = nat
                if flag:
                    c_obj["flag"] = flag
                if d_comp:
                    c_obj["birth_date"] = d_comp
            else:
                if not c_obj.get("name") and nom_c:
                    c_obj["name"] = nom_c
                if not c_obj.get("nationality") and nat:
                    c_obj["nationality"] = nat
                if not c_obj.get("flag") and flag:
                    c_obj["flag"] = flag
                if not c_obj.get("birth_date") and d_comp:
                    c_obj["birth_date"] = d_comp

            riders_fiche[cid] = _sans_vide({
                "id": cid,
                "name": c_obj.get("name") or nom_c,
                "nationality": nat,
                "flag": flag,
                "is_french": True if nat == "FRA" else None,
                "team": eq_nom,
            })
            row_out: Dict[str, Any] = {"rank": rang_int, "rider_id": cid}
            for k_opt in ("time_s", "gap_s", "points", "bonus_s", "penalty_s", "uci_points", "bib"):
                if row.get(k_opt) is not None:
                    row_out[k_opt] = row[k_opt]
            rows_norm.append(row_out)

            s_str = str(an)
            s_obj = c_obj["saisons"].setdefault(s_str, {"stats": {"wins": 0, "podiums": 0, "top10": 0, "races": 0, "gc_wins": 0}})
            st_s = s_obj.setdefault("stats", {})
            if cid not in classes_vus:
                classes_vus.add(cid)
                st_s["races"] = st_s.get("races", 0) + 1
                st_s["race_days"] = st_s.get("race_days", 0) + 1
                if rang_int == 1:
                    st_s["wins"] = st_s.get("wins", 0) + 1
                    c_obj["_stats"]["wins"] += 1
                    if race_type == "stage_race":
                        st_s["gc_wins"] = st_s.get("gc_wins", 0) + 1
                        c_obj["_stats"]["gc_wins"] += 1
                if rang_int <= 3:
                    st_s["podiums"] = st_s.get("podiums", 0) + 1
                    c_obj["_stats"]["podiums"] += 1
                if rang_int <= 10:
                    st_s["top10"] = st_s.get("top10", 0) + 1

            if rang_int <= 3:
                classif = "gc" if race_type == "stage_race" else "stage"
                label = "Classement général" if race_type == "stage_race" else "Course"
                p_item = _sans_vide({
                    "date": end_date,
                    "season": an,
                    "race_id": race_id,
                    "course": cle,
                    "label": label,
                    "classification": classif,
                    "rank": rang_int,
                    "category": category,
                    "uci_class": uci_class,
                    "source": source_prim,
                    "sources": sources_ed if len(sources_ed) > 1 else None,
                })
                c_obj["palmares"].append(p_item)
                podium.append(_sans_vide({
                    "rank": rang_int,
                    "id": cid,
                    "name": c_obj.get("name") or nom_c,
                    "nat": nat,
                    "flag": flag,
                    "team": eq_nom,
                }))

            if est_gt:
                c_obj["grands_tours"].append({"season": an, "course": est_gt, "race_id": race_id, "rank": rang_int})

            if nat == "FRA" and best_french is None:
                best_french = _sans_vide({
                    "id": cid,
                    "name": c_obj.get("name") or nom_c,
                    "flag": flag,
                    "rank": rang_int,
                    "classification": "gc" if race_type == "stage_race" else "stage",
                })

            if nat:
                ps = pays_saison_cumul[an].setdefault(nat, {"coureurs": set(), "victoires": 0, "podiums": 0, "flags": collections.Counter(), "wins_c": collections.Counter()})
                ps["coureurs"].add(cid)
                if flag:
                    ps["flags"][flag] += 1
                if rang_int == 1:
                    ps["victoires"] += 1
                    ps["wins_c"][cid] += 1
                if rang_int <= 3:
                    ps["podiums"] += 1

            if eq_nom:
                eq_slug = netutil.slugify(eq_nom)
                if eq_slug:
                    eq_tid = f"{eq_slug}-{an}"
                    if not s_obj.get("equipe"):
                        s_obj["team"] = eq_nom
                        s_obj["equipe"] = eq_tid
                    eqs_list = s_obj.setdefault("equipes", [])
                    if eq_tid not in eqs_list:
                        eqs_list.append(eq_tid)
                    eq_e = eq_cumul[an].setdefault(eq_slug, {
                        "libelles": collections.Counter(),
                        "eff": {},
                        "victoires": [],
                        "gt": {},
                        "nats": set(),
                        "sources": set(),
                    })
                    eq_e["libelles"][eq_nom] += 1
                    eq_e["sources"].update(sources_ed)
                    if nat:
                        eq_e["nats"].add(nat)
                    eff_c = eq_e["eff"].setdefault(cid, [0, 0, 0])
                    eff_c[0] += 1
                    if rang_int == 1:
                        eff_c[1] += 1
                        if race_type == "stage_race":
                            eff_c[2] += 1
                        eq_e["victoires"].append(_sans_vide({
                            "date": end_date,
                            "race_id": race_id,
                            "course": cle,
                            "label": "Classement général" if race_type == "stage_race" else "Course",
                            "classification": "gc" if race_type == "stage_race" else "stage",
                            "rider_id": cid,
                        }))
                    if est_gt:
                        best_gt = eq_e["gt"].get(est_gt)
                        if best_gt is None or (rang_int, cid) < (best_gt["rank"], best_gt["rider_id"]):
                            eq_e["gt"][est_gt] = {"rank": rang_int, "rider_id": cid, "race_id": race_id}

        # Enregistrement dans COURSES
        c_pays = cle.rsplit("|", 1)[1]
        C_ent = courses.setdefault(cle, {
            "noms": {},
            "pays": c_pays,
            "flag": pays.drapeau(c_pays),
            "classes": {},
            "type": None,
            "_type_an": 0,
            "editions": [],
        })
        C_ent["noms"].setdefault(nom_course, set()).add(an)
        if not C_ent["flag"]:
            C_ent["flag"] = pays.drapeau(c_pays)
        if uci_class:
            C_ent["classes"].setdefault(str(an), uci_class)
        if race_type and an >= C_ent["_type_an"]:
            C_ent["type"], C_ent["_type_an"] = race_type, an
        podium.sort(key=lambda p: (p["rank"], p.get("id") or ""))
        rows_norm.sort(key=lambda r: (r["rank"], r["rider_id"]))
        C_ent["editions"].append(_sans_vide({
            "season": an,
            "race_id": race_id,
            "start_date": start_date,
            "end_date": end_date,
            "podium": podium or None,
            "best_french": best_french,
            "source": source_prim,
            "sources": sources_ed if len(sources_ed) > 1 else None,
            "bdd_slug": slug,
        }))
        if editions_dir:
            fiche_ed: Dict[str, Any] = _sans_vide({
                "id": race_id,
                "name": nom_course,
                "country": pays_code,
                "flag": pays.drapeau(pays_code) if pays_code else None,
                "season": an,
                "start_date": start_date,
                "end_date": end_date,
                "race_type": race_type,
                "uci_class": uci_class,
                "category": category,
                "status": "finished",
                "source": source_prim,
                "sources": sources_ed if len(sources_ed) > 1 else None,
                "bdd_slug": slug,
                "riders": riders_fiche,
            })
            if race_type == "stage_race":
                fiche_ed["final"] = {"gc": rows_norm}
                if isinstance(ed.get("stages"), list) and ed["stages"]:
                    fiche_ed["stages_done"] = len(ed["stages"])
            else:
                fiche_ed["stages"] = [{
                    "number": None,
                    "date": start_date,
                    "name": "Course",
                    "results": {"stage": rows_norm},
                }]
            safe_race_id = re.sub(r"[\\/]+", "-", race_id)
            fname = f"{safe_race_id}.json"
            an_str = str(an)
            editions_ecrites[an_str].add(fname)
            chemin_ed = os.path.join(editions_dir, an_str, fname)
            if ecrire_fn is not None:
                ecrire_fn(chemin_ed, fiche_ed)
            else:
                collector._dump_if_changed(chemin_ed, fiche_ed, ignore=())

    # Consolidation des pays pré-2009 dans PAYS
    for an, par_nat in pays_saison_cumul.items():
        for nat, ps in par_nat.items():
            P = pays_agg.setdefault(nat, {"saisons": {}, "flags": collections.Counter(), "wins": {}})
            P["saisons"][str(an)] = {
                "coureurs": len(ps["coureurs"]),
                "victoires": ps["victoires"],
                "podiums": ps["podiums"],
            }
            P["flags"].update(ps["flags"])
            for cid, w in ps["wins_c"].items():
                P["wins"][cid] = P["wins"].get(cid, 0) + w

    # Consolidation des équipes pré-2009 dans EQ_PAR_AN, EQ_INDEX, EQ_RECH
    wd_equipes = wd.get("equipes") or {}
    for an, par_slug in sorted(eq_cumul.items()):
        equipes_an = eq_par_an.setdefault(an, {})
        for eq_slug, eq_e in sorted(par_slug.items()):
            tid = f"{eq_slug}-{an}"
            if tid in equipes_an:
                continue
            nom = sorted(eq_e["libelles"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            nat_eq = est_nationale_fn(nom, eq_e["nats"]) if est_nationale_fn else None
            effectif = sorted(
                (
                    _sans_vide({
                        "rider_id": cid,
                        "name": (cour.get(cid) or {}).get("name"),
                        "flag": (cour.get(cid) or {}).get("flag"),
                        "jours": v[0],
                        "wins": v[1],
                    })
                    for cid, v in eq_e["eff"].items()
                ),
                key=lambda x: (-x["jours"], -x["wins"], x.get("name") or "", x["rider_id"]),
            )
            vict = sorted(eq_e["victoires"], key=lambda v: (v["date"], v["race_id"], v["classification"], v["rider_id"]), reverse=True)
            lig = (wd_equipes.get(tid) or {}).get("qid")
            srcs_eq = sorted(eq_e["sources"])
            fiche = _sans_vide({
                "name": nom,
                "season": an,
                "nationale": True if nat_eq else None,
                "pays": nat_eq,
                "lignee": lig,
                "effectif": effectif,
                "victoires": vict,
                "grands_tours": eq_e["gt"] or None,
                "totaux": {
                    "wins": sum(v[1] for v in eq_e["eff"].values()),
                    "gc_wins": sum(v[2] for v in eq_e["eff"].values()),
                    "riders": len(eq_e["eff"]),
                    "jours": sum(v[0] for v in eq_e["eff"].values()),
                },
                "source": srcs_eq[0] if len(srcs_eq) == 1 else None,
                "sources": srcs_eq if len(srcs_eq) > 1 else None,
            })
            equipes_an[tid] = fiche
            equipes_ajoutees += 1
            if nat_eq:
                nationales_ajoutees += 1
            if equipes_ecrites is not None:
                equipes_ecrites.add(f"{an}.json")

            ent_idx = _sans_vide({
                "id": tid,
                "name": nom,
                "season": an,
                "wins": fiche["totaux"]["wins"],
                "riders": fiche["totaux"]["riders"],
                "nationale": True if nat_eq else None,
                "pays": nat_eq,
                "lignee": lig,
            })
            eq_index.append(ent_idx)
            eq_index_by_id[tid] = ent_idx

            ent_r = eq_rech.get(eq_slug)
            if ent_r is None:
                ent_r = eq_rech[eq_slug] = {"n": nom, "t": "e", "id": tid, "y": [an, an]}
                if nat_eq:
                    ent_r["nat"] = True
                    f_eq = pays.drapeau(nat_eq)
                    if f_eq:
                        ent_r["f"] = f_eq
            else:
                ent_r["y"][0] = min(ent_r["y"][0], an)
                if an > ent_r["y"][1]:
                    ent_r["y"][1] = an
                    ent_r["n"], ent_r["id"] = nom, tid

    # Nettoyage des stats nulles dans les saisons ajoutées
    for cid in coureurs_nouveaux | coureurs_rapproches:
        c_obj = cour.get(cid)
        if not c_obj:
            continue
        for s_obj in c_obj.get("saisons", {}).values():
            st = s_obj.get("stats")
            if isinstance(st, dict):
                s_obj["stats"] = {k: v for k, v in st.items() if v}

    srcs_triees = sorted(sources_vues)
    credits = [credit_source(s) for s in srcs_triees]
    return {
        "present": True,
        "editions_ajoutees": editions_ajoutees,
        "coureurs_ajoutes": len(coureurs_nouveaux),
        "coureurs_rapproches": len(coureurs_rapproches),
        "equipes_ajoutees": equipes_ajoutees,
        "nationales_ajoutees": nationales_ajoutees,
        "annees": sorted(annees_vues),
        "sources": srcs_triees,
        "credits": credits,
        "editions_ignorees": editions_ignorees,
        "courses_sans_cle": courses_sans_cle,
        "pays_inconnus": inconnus,
        "editions_ecrites": {k: sorted(v) for k, v in sorted(editions_ecrites.items())},
    }


# --------------------------------------------------------------------------- tests

def _tests() -> None:
    import encyclopedie

    # 1. Normalisation pays d'époque
    assert normaliser_pays("URS", "pcs", 1985) == "URS"
    assert normaliser_pays("GDR", "letour_dataset", 1988) == "GDR"
    assert normaliser_pays("FRG", "firstcycling", 1989) == "FRG"
    assert normaliser_pays("RFA", "pcs", 1985) == "FRG"
    assert normaliser_pays("TCH", "museo", 1991) == "TCH"
    assert normaliser_pays("TCH", "museo", 1995) == "CZE"
    assert normaliser_pays("BE", "pcs", 2008) == "BEL"
    assert normaliser_pays("FR", "pcs", 1981) == "FRA"
    assert normaliser_pays("IT", "pcs", 1981) == "ITA"
    assert normaliser_pays("ES", "pcs", 1981) == "ESP"
    assert normaliser_pays("NL", "pcs", 1981) == "NED"
    assert normaliser_pays("CH", "pcs", 1981) == "SUI"
    assert normaliser_pays("CS", "pcs", 1990) == "TCH"
    assert normaliser_pays("CS", "pcs", 1995) == "CZE"
    assert normaliser_pays("Belgium", "pcs", 2008) == "BEL"
    assert normaliser_pays("France", "pcs", 1981) == "FRA"
    assert normaliser_pays("Italy", "pcs", 1981) == "ITA"
    assert normaliser_pays("Spain", "pcs", 1981) == "ESP"
    inc: Dict[str, int] = {}
    assert normaliser_pays("ZZZ", "pcs", 1990, inc) is None and inc == {"ZZZ": 1}

    # 1b. Rapprochement des clés canoniques des grandes épreuves
    alias_c = collector.charger_alias(collector.ALIAS_COURSES)
    for nom_t, pays_t, canon_t in (
        ("Omloop Het Nieuwsblad", "BEL", "omloop het nieuwsblad elite|BEL"),
        ("Paris - Roubaix", "FRA", "paris roubaix|FRA"),
        ("Tour de France", "FRA", "tour de france|FRA"),
        ("Giro d'Italia", "ITA", "giro d italia|ITA"),
        ("Vuelta a España", "ESP", "la vuelta ciclista a espana|ESP"),
        ("Milano-Sanremo", "ITA", "milano sanremo|ITA"),
        ("Ronde van Vlaanderen", "BEL", "ronde van vlaanderen tour des flandres|BEL"),
        ("Liège - Bastogne - Liège", "BEL", "liege bastogne liege|BEL"),
        ("Giro di Lombardia", "ITA", "il lombardia|ITA"),
    ):
        k_t = collector.cle_edition(nom_t, pays_t)
        assert alias_c.get(k_t, k_t) == canon_t, (nom_t, k_t, alias_c.get(k_t, k_t))

    # 2. Jeu de test complet bdd_pre2009 + encyclopedie.construire()
    with tempfile.TemporaryDirectory(prefix="src_hist_") as tmp:
        arch = os.path.join(tmp, "archives")
        data = os.path.join(tmp, "data")
        out = os.path.join(tmp, "entites")
        bdd = os.path.join(arch, "sources", "bdd_pre2009")
        os.makedirs(os.path.join(data, "races"), exist_ok=True)
        os.makedirs(os.path.join(arch, "2020", "races"), exist_ok=True)

        # Une course UCI récente (2020) avec un coureur connu ayant un ID externe pcs + un autre par nom+naissance
        rid_pcs = "hinault-bernard-19541114"
        rid_date = "merckx-eddy-19450617"
        race_2020 = {
            "id": "uci-2020-1",
            "name": "Critérium du Dauphiné",
            "country": "FRA",
            "flag": "fr",
            "uci_class": "2.UWT",
            "category": "WT",
            "race_type": "stage_race",
            "start_date": "2020-08-12",
            "end_date": "2020-08-16",
            "status": "finished",
            "season": 2020,
            "riders": {
                rid_pcs: {"id": rid_pcs, "name": "Bernard Hinault", "nationality": "FRA", "flag": "fr", "birth_date": "1954-11-14", "team": "Équipe Moderne"},
                rid_date: {"id": rid_date, "name": "Eddy Merckx", "nationality": "BEL", "flag": "be", "birth_date": "1945-06-17", "team": "Équipe Moderne"},
            },
            "stages": [{"number": 1, "date": "2020-08-12", "name": "Étape 1", "results": {"stage": [{"rank": 1, "rider_id": rid_pcs}]}}],
            "final": {"gc": [{"rank": 1, "rider_id": rid_pcs}, {"rank": 2, "rider_id": rid_date}]},
        }
        collector._dump(os.path.join(arch, "2020", "races", "uci-2020-1.json"), race_2020)
        collector._dump(os.path.join(arch, "2020", "state.json"), {"complete": True})

        # Cache Wikidata avec IDs externes pour Bernard Hinault
        wd_dir = os.path.join(out, "wikidata")
        collector._dump(os.path.join(wd_dir, "coureurs.json"), {
            rid_pcs: {"qid": "Q220987", "verifie": "2026-11-01", "ids": {"pcs": ["bernard-hinault"], "firstcycling": ["123"]}},
        })

        # Cache historique Wikidata : 2008 (Omloop), 1981 & 1955 (Paris-Roubaix)
        hist_dir = os.path.join(out, "historique")
        collector._dump(os.path.join(hist_dir, "coureurs.json"), {
            "Q1001": {"nom": "Philippe Gilbert", "nationalite": "BEL"},
            "Q1002": {"nom": "Bernard Hinault", "nationalite": "FRA", "rider_id": rid_pcs},
            "Q1003": {"nom": "Louison Bobet", "nationalite": "FRA"},
        })
        collector._dump(os.path.join(hist_dir, "editions", "o.json"), {
            "omloop het nieuwsblad elite|BEL": [
                {"annee": 2008, "qid": "Q5008", "vainqueur": "Q1001", "podium": [{"rang": 1, "qid": "Q1001"}], "statut": "ok", "verifie": "2026-11-16"},
            ],
        })
        collector._dump(os.path.join(hist_dir, "editions", "p.json"), {
            "paris roubaix|FRA": [
                {"annee": 1981, "qid": "Q5981", "vainqueur": "Q1002", "podium": [{"rang": 1, "qid": "Q1002"}], "statut": "ok", "verifie": "2026-11-16"},
                {"annee": 1955, "qid": "Q5955", "vainqueur": "Q1003", "podium": [{"rang": 1, "qid": "Q1003"}], "statut": "ok", "verifie": "2026-11-16"},
            ],
        })

        # bdd_pre2009
        collector._dump(os.path.join(bdd, "manifest.json"), {"version": 1, "sources": ["pcs", "letour_dataset", "preflib_00043", "vuelta_open", "firstcycling"]})
        collector._dump(os.path.join(bdd, "courses.json"), {
            "dauphine": {"slug": "dauphine", "name": "Critérium du Dauphiné Libéré", "country": "FRA", "race_type": "stage_race", "uci_class": "2.HC"},
            "het-volk": {"slug": "het-volk", "name": "Het Volk", "country": "BEL", "race_type": "one_day", "uci_class": "1.HC"},
            "plouay": {"slug": "plouay", "name": "Grand Prix de Plouay", "country": "FRA", "race_type": "one_day", "uci_class": "1.HC"},
        })
        collector._dump(os.path.join(bdd, "coureurs.json"), {
            "c_hinault": {"id": "c_hinault", "name": "B. Hinault", "nationality": "FRA", "ids": {"pcs": "bernard-hinault"}},
            "c_merckx": {"id": "c_merckx", "name": "MERCKX Eddy", "nationality": "BEL", "birth_date": "1945-06-17"},
            "c_homo1": {"id": "c_homo1", "name": "Bernard Hinault", "nationality": "FRA", "birth_date": "1970-01-01"},  # homonyme autre date -> JAMAIS fusionné
            "c_urs": {"id": "c_urs", "name": "Serguei Soukhoroutchenkov", "nationality": "URS", "birth_year": 1956},
        })
        collector._dump(os.path.join(bdd, "equipes.json"), {
            "renault": {"id": "renault", "name": "Renault-Elf-Gitane"},
        })

        # Édition 1981 Dauphiné (source: pcs)
        collector._dump(os.path.join(bdd, "editions", "dauphine", "1981.json"), {
            "race_id": "pcs-dauphine-1981",
            "name": "Critérium du Dauphiné Libéré",
            "country": "FRA",
            "start_date": "1981-05-25",
            "end_date": "1981-06-01",
            "source": "pcs",
            "sources": ["pcs", "letour_dataset"],
            "gc": [
                {"rank": 1, "rider_id": "c_hinault", "team": "Renault-Elf-Gitane"},
                {"rank": 2, "rider_id": "c_urs", "team": "URSS"},
                {"rank": 3, "rider_id": "c_homo1", "team": "Peugeot"},
            ],
        })
        # Édition 1971 Het Volk (source: firstcycling)
        collector._dump(os.path.join(bdd, "editions", "het-volk", "1971.json"), {
            "race_id": "fc-het-volk-1971",
            "name": "Het Volk",
            "country": "BEL",
            "start_date": "1971-03-06",
            "source": "firstcycling",
            "results": [
                {"rank": 1, "rider_id": "c_merckx", "team": "Molteni"},
            ],
        })
        # Édition 2008 Omloop Het Nieuwsblad (country ISO-2 BE) -> doit masquer l'entrée Wikidata 2008
        collector._dump(os.path.join(bdd, "editions", "omloop-het-nieuwsblad", "2008.json"), {
            "race_id": "pre2009-omloop-het-nieuwsblad-2008",
            "name": "Omloop Het Nieuwsblad",
            "country": "BE",
            "start_date": "2008-03-01",
            "source": "pcs",
            "results": [
                {"rank": 1, "rider_id": "c_merckx", "team": "Française des Jeux"},
            ],
        })
        # Édition 1981 Paris-Roubaix -> doit masquer Wikidata 1981, tout en laissant 1955 en WD
        collector._dump(os.path.join(bdd, "editions", "paris-roubaix", "1981.json"), {
            "race_id": "pre2009-paris-roubaix-1981",
            "name": "Paris - Roubaix",
            "country": "FRA",
            "start_date": "1981-04-12",
            "source": "pcs",
            "results": [
                {"rank": 1, "rider_id": "c_hinault", "team": "Renault-Elf-Gitane"},
            ],
        })
        # Édition 2009 (> 2008) -> doit être ignorée
        collector._dump(os.path.join(bdd, "editions", "plouay", "2009.json"), {
            "race_id": "plouay-2009",
            "name": "Grand Prix de Plouay",
            "country": "FRA",
            "start_date": "2009-08-23",
            "source": "preflib_00043",
            "results": [{"rank": 1, "rider_id": "c_homo1"}],
        })

        rap = encyclopedie.construire(arch, data, out, now="2026-11-23T00:00:00Z", alias_coureurs={}, alias_courses=alias_c, verbose=False)

        b = rap["bdd_pre2009"]
        assert b["present"] is True, b
        assert b["editions_ajoutees"] == 4 and b["editions_ignorees"] == 1, b
        assert b["sources"] == ["firstcycling", "letour_dataset", "pcs"], b
        assert b["credits"] == ["FirstCycling", "Le Tour Dataset", "ProCyclingStats"], b

        # Épreuve rapprochée par alias_courses.json + crédits conservés
        dauph = collector._load(os.path.join(out, "courses", "c.json"), {})["criterium du dauphine|FRA"]
        eds_d = {e["season"]: e for e in dauph["editions"]}
        assert 2020 in eds_d and 1981 in eds_d, eds_d
        assert eds_d[1981]["source"] == "pcs" and eds_d[1981]["sources"] == ["pcs", "letour_dataset"]
        assert eds_d[1981]["podium"][0]["id"] == rid_pcs

        het = collector._load(os.path.join(out, "courses", "o.json"), {})["omloop het nieuwsblad elite|BEL"]
        eds_het = {e["season"]: e for e in het["editions"]}
        assert 1971 in eds_het and 2008 in eds_het, eds_het
        assert eds_het[1971]["source"] == "firstcycling"
        assert eds_het[2008]["race_id"] == "pre2009-omloop-het-nieuwsblad-2008"
        assert eds_het[2008]["bdd_slug"] == "omloop-het-nieuwsblad"
        assert "historique" not in het, het.get("historique")  # 2008 couvert par bdd_pre2009 -> pas de badge WD

        pr = collector._load(os.path.join(out, "courses", "p.json"), {})["paris roubaix|FRA"]
        eds_pr = {e["season"]: e for e in pr["editions"]}
        assert 1981 in eds_pr and eds_pr[1981]["race_id"] == "pre2009-paris-roubaix-1981"
        assert [h["annee"] for h in pr.get("historique") or []] == [1955], pr.get("historique")  # 1981 exclu de WD, 1955 conservé en WD

        # Fiches d'édition complètes générées dans entites/editions_pre2009/
        f_omloop_2008 = collector._load(os.path.join(out, "editions_pre2009", "2008", "pre2009-omloop-het-nieuwsblad-2008.json"), {})
        assert f_omloop_2008["id"] == "pre2009-omloop-het-nieuwsblad-2008" and f_omloop_2008["country"] == "BEL"
        assert f_omloop_2008["stages"][0]["results"]["stage"][0]["rider_id"] == rid_date
        assert rid_date in f_omloop_2008["riders"]

        f_pr_1981 = collector._load(os.path.join(out, "editions_pre2009", "1981", "pre2009-paris-roubaix-1981.json"), {})
        assert f_pr_1981["id"] == "pre2009-paris-roubaix-1981"
        assert f_pr_1981["stages"][0]["results"]["stage"][0]["rider_id"] == rid_pcs

        assert "bretagne classic ouest france|FRA" not in collector._load(os.path.join(out, "courses", "b.json"), {})

        # Rapprochement coureurs : Hinault par ID pcs, Merckx par nom+naissance, homonyme NON fusionné, coureur URS conservé en h-urs
        ch = collector._load(os.path.join(out, "coureurs", "h.json"), {})
        assert rid_pcs in ch and "1981" in ch[rid_pcs]["saisons"]
        assert any(p.get("source") == "pcs" and p["season"] == 1981 for p in ch[rid_pcs]["palmares"])
        # Homonyme 1970-01-01 non fusionné avec 1954-11-14
        assert "hist-c-homo1" in ch and "1981" in ch["hist-c-homo1"]["saisons"]
        assert ch["hist-c-homo1"]["birth_date"] == "1970-01-01"

        cm = collector._load(os.path.join(out, "coureurs", "m.json"), {})
        assert "1971" in cm[rid_date]["saisons"]

        c_urs = ch["hist-c-urs"]
        assert c_urs["nationality"] == "URS" and c_urs["flag"] == "h-urs"

        # Crédits dans index.json
        ix = collector._load(os.path.join(out, "index.json"), {})
        assert ix["sources_historiques"] == ["FirstCycling", "Le Tour Dataset", "ProCyclingStats"], ix
        assert any("ProCyclingStats" in s for s in ix["sources"]), ix["sources"]

        # Idempotence au second passage
        rap2 = encyclopedie.construire(arch, data, out, now="2026-11-24T00:00:00Z", alias_coureurs={}, alias_courses=alias_c, verbose=False)
        assert rap2["fichiers_modifies"] == 0, rap2["fichiers_modifies"]

    print("sources_historiques.py : tests OK")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _tests()
    else:
        print(__doc__)
