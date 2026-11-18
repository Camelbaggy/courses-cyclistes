# Spécification : Dashboard des courses cyclistes (hommes élite, focus français)

Version 1, 8 novembre 2026. Ce document est le **contrat** entre les modules : schéma des données, interfaces
Python, règles de sélection. Toute modification de schéma passe par le chef de projet.

## 1. Objectif

Équivalent cyclisme du dashboard Coupes d'Europe : après chaque étape ou course suivie, collecte des résultats
officiels → résumés IA → fichiers JSON → page statique mobile (GitHub Pages) → push ntfy.
Tout en français (interface, logs, commits, commentaires). Python 3.11, bibliothèque standard uniquement.

**Règle cardinale : zéro hallucination.** Classements, temps, écarts, dossards, nationalités viennent des sources.
Les seules valeurs dérivées (écarts recalculés, meilleur Français, porteurs de maillots, mouvements au général)
sont calculées de façon déterministe. Un champ absent reste `null` / vide.

## 2. Sources (validées par sondes depuis GitHub Actions, voir `docs/recherche/`)

| Source | Rôle | Module |
|---|---|---|
| UCI DataRide (`dataride.uci.org/iframe/...`, JSON public) | **colonne vertébrale** : liste des courses de la saison avec classe UCI, étapes, tous les classements, abandons | `uci.py` |
| uci.org calendrier (à confirmer) | courses **à venir** (onglet Calendrier) | `uci.py` |
| ASO (letour.fr, paris-nice.fr, paris-roubaix.fr, …) — **accord obtenu par le propriétaire du projet** | enrichissement des courses ASO : bonifications, pénalités, classement par équipes, distance / type / D+ / cols / secteurs pavés, articles de récit (entrée IA) | `aso.py` |
| DirectVélo — **accord obtenu** (Crawl-delay 10 s à respecter) | articles de récit des courses françaises (entrée IA), repli de classement pour une course française absente d'UCI | `directvelo.py` |
| LNC (lncpro.fr/resultats/<slug>) | classement général FDJ United Series (ex-Coupe de France), liste des manches | `lnc.py` |
| Cyclingnews RSS (`cyclingnews.com/feeds.xml`, texte intégral) | entrée IA uniquement, **jamais republié** | `cyclingnews.py` |
| Open-Meteo | (v2, hors périmètre v1) | — |

Exclues : ProCyclingStats, FirstCycling (CGU/robots.txt), L'Équipe (403), ESPN (pas de cyclisme).
RCS (Giro, Sanremo…) : CGU non lues → seulement via UCI en v1.

Politesse réseau (toutes sources) : User-Agent honnête `courses-cyclistes/1.0 (+https://github.com/Camelbaggy/courses-cyclistes)`,
pause minimale par hôte (1,2 s ; 10,5 s pour DirectVélo), respect de robots.txt, aucun contournement anti-robot :
un challenge / 403 / 429 → abandon de la source pour ce passage, log `[WARN]`, champ vide.

## 3. Sélection des courses (`selection.py`)

Saison UCI hommes élite (CategoryId 22). Une course est **suivie** si :
1. classe `1.UWT`, `2.UWT`, `1.Pro`, `2.Pro` → catégorie `WT` / `Pro` ;
2. manche FDJ United Series (liste LNC, rapprochement par nom normalisé + date) → catégorie `FDJ` ;
3. classe `1.1`, `2.1`, `1.2`, `2.2` (et variantes `2.2U`, `1.2U`, `Ncup`) disputée en France (`CountryIsoCode3 == "FRA"`) → `.1` / `.2` ;
4. même classe hors de France **si un coureur français termine dans les 10 premiers** (classement final pour une
   course d'un jour, classement d'étape ou général final pour une course par étapes) → `.1` / `.2`, avec
   `selection_reason = "francais_top10"` ;
5. championnats : `CN` de France uniquement, `CC` (Europe), `CM`/`WC` (Monde) → `Champ.`.
Les clubs / coureurs français : nationalité `FRA` uniquement (aucune liste de noms). Équipe française :
pas de champ fiable en v1 → non utilisé.

## 4. Fichiers produits (publiés sur GitHub Pages)

Le volume d'une saison complète est trop gros pour un fichier unique : **un index + un fichier par course**.
Les fichiers de course sont conservés dans le dépôt d'un passage à l'autre ; le pipeline ne recollecte que les
courses en cours ou terminées depuis moins de 3 jours (plus les nouvelles).

```
data/index.json               index léger, lu au chargement de la page
data/races/<race_id>.json      détail d'une course, chargé à l'ouverture
data/seasons.json              {"current": 2026, "available": [2026, 2025]} — sélecteur de saison de la page
data/index-<année>.json        index de chaque saison (même schéma ; index.json = saison courante)
data/state.json                état interne (clés déjà notifiées, horodatages) — non lu par la page
data/ranking-<année>.json     classement UCI de fin de saison d'une saison terminée encore au Calendrier (schéma de ranking.json, `season` = année ; écrit une fois
                               avec `team_code` par `collector.classements_fin_calendrier`, immuable, retiré à la rotation ; lu par l'encyclopédie seulement)
```

### 4.1 `data/index.json`

```jsonc
{
  "generated_at": "2026-07-26T19:42:00Z",
  "season": 2026,
  "races": [ RaceSummary, ... ],            // toutes les courses suivies de la saison, triées par date
  "upcoming": [ UpcomingRace, ... ],        // courses à venir (peut être vide)
  "latest": [ LatestItem, ... ],            // 20 derniers résultats (étapes ou courses), plus récent d'abord
  "fdj_united_series": {                    // null si indisponible
    "source": "lnc", "updated": "2026-10-04",
    "individual": [ {"rank": 1, "rider": "…", "team": "…", "points": 312} ],
    "races": [ {"name": "…", "date": "2026-02-01", "race_id": "uci-76001" | null} ]
  },
  "french_wins": [ {"date": "…", "race_id": "…", "stage_number": 3 | null, "rider": "…", "rider_id": "…", "race_name": "…", "label": "Étape 3"} ],
  "notification": { "send": true, "title": "…", "message": "…" }   // construit par le pipeline
}
```

`RaceSummary` :
```jsonc
{
  "id": "uci-76380",                        // "uci-<CompetitionId>"
  "name": "Paris-Roubaix Hauts-de-France",
  "country": "FRA", "flag": "fr",
  "uci_class": "1.UWT", "category": "WT",   // WT | Pro | FDJ | .1 | .2 | Champ.
  "race_type": "one_day",                   // one_day | stage_race
  "start_date": "2026-04-12", "end_date": "2026-04-12",
  "status": "finished",                     // finished | in_progress
  "stages_done": 1, "stages_total": 1 | null,
  "selection_reason": "classe",             // classe | fdj | france | francais_top10 | championnat
  "winner": RiderRef | null,                // vainqueur final (ou leader actuel si in_progress -> "leader")
  "leader": RiderRef | null,
  "best_french": {"rider": RiderRef, "rank": 4, "classification": "gc"} | null,
  "sources": ["uci", "aso"]
}
```

`RiderRef` : `{"id": "pogacar-tadej-19980921", "name": "Tadej Pogačar", "nationality": "SLO", "flag": "si", "is_french": false, "team": "UAE Team Emirates XRG"}`
- `id` = slug ASCII du nom UCI (« NOM Prénom » → `nom-prenom`) + date de naissance `AAAAMMJJ` (pas d'identifiant UCI).
- `name` affiché « Prénom Nom » (UCI donne « NOM Prénom » : le nom de famille est la partie en majuscules).
- `team` : casse lisible (UCI renvoie en majuscules ; conversion en casse titre, sigles ≤ 3 lettres conservés).

`LatestItem` : `{"race_id", "race_name", "stage_number": 3 | null, "date", "label": "Étape 3 · Nice → Auron" | "Course", "winner": RiderRef, "best_french": {...} | null, "ai_summary": "…" | null}`

`UpcomingRace` : `{"name", "country", "flag", "uci_class", "category", "start_date", "end_date"}`

### 4.2 `data/races/<race_id>.json`

```jsonc
{
  ...RaceSummary,                            // mêmes champs que dans l'index
  "stages": [ Stage, ... ],                  // course d'un jour : une seule entrée, number = null
  "final": Classifications | null,           // classements finaux (UCI « Final Classification ») si terminée
  "riders": { "<rider_id>": RiderRef + {"birth_date": "1998-09-21"} },
  "updated_at": "…"
}
```

`Stage` :
```jsonc
{
  "number": 3 | null,                        // null pour une course d'un jour ; prologue = 0
  "date": "2026-03-10",
  "name": "Étape 3",                         // libellé UCI traduit (« Stage 3 » -> « Étape 3 », « Prologue »)
  "start": "Nice" | null, "finish": "Auron" | null,
  "type": "itt" | "ttt" | "road",            // d'après RaceTypeCode UCI (ITT / TTT / IRR)
  "route": {                                  // null si aucune source (jamais inventé)
    "distance_km": 172.4, "elevation_m": 3600, "profile": "montagne" | "plat" | "vallonné" | "accidenté" | "clm" | null,
    "climbs": [ {"name": "Col de la Couillole", "km": 154.0, "category": "1", "altitude_m": 1678, "length_km": 15.7, "gradient_pct": 7.1} ],
    "cobbles": [ {"name": "Trouée d'Arenberg", "km": 162.4, "length_km": 2.3, "difficulty": 5} ],
    "source": "aso"
  },
  "results": Classifications,
  "ai_summary": "…" | null,
  "summary_source": "gemini" | "fallback" | null,
  "french_highlights": [ {"rider": RiderRef, "stage_rank": 4, "gc_rank": 12, "gc_gap_s": 95} ]
}
```

`Classifications` (chaque clé absente ou `[]` si la source ne la fournit pas) :
```jsonc
{
  "stage":    [ Row ],       // classement de l'étape / de la course d'un jour (inclut DNF/DNS en fin)
  "gc":       [ Row ],       // général après l'étape
  "points":   [ Row ],
  "mountain": [ Row ],
  "youth":    [ Row ],
  "teams":    [ TeamRow ],
  "combativity": [ Row ]
}
```

`Row` :
```jsonc
{
  "rank": 1 | null,                          // null si DNF/DNS/OTL/DSQ
  "status": null | "DNF" | "DNS" | "OTL" | "DSQ" | "DNQ",
  "bib": 11 | null,
  "rider_id": "pogacar-tadej-19980921",      // clé dans "riders"
  "time_s": 15153 | null,                    // temps total en secondes (classements au temps)
  "gap_s": 0 | null,                         // écart au premier, secondes
  "points": 50 | null,                       // classements aux points / montagne
  "bonus_s": 10 | null, "penalty_s": 0 | null,
  "uci_points": 125 | null
}
```
`TeamRow` : `{"rank", "team", "nationality" | null, "time_s", "gap_s"}`.

Conventions : temps et écarts **toujours en secondes entières** dans le JSON (la page formate). Dates ISO
`AAAA-MM-JJ`. Les valeurs UCI `ResultValue` hétérogènes (temps absolu pour le premier, écart « +0:12 » ou
« s.t. » pour les suivants, points) sont normalisées dans `uci.py`.

### 4.3 `data/state.json`

`{"notified": ["uci-76380:F", "uci-76012:3", …], "last_run": "…"}` — clé `<race_id>:<identifiant d'étape|F>`. **Identifiant d'étape** (`uci.ref_etape`) = `<number><suffixe>` : « 3a » / « 3b » pour deux demi-étapes d'un même jour (suffixe lu dans `name`, « Étape 3b », comme `uci.cle_tri_etape`), « 3 » sans suffixe (identique à l'ancienne clé : aucune renotification), « F » pour le final. Aucun champ ajouté aux fichiers : `index.html` le recalcule depuis `name` / `label` (`refEtape` / `refLibelle`) ; routes `#course/<id>/3b` ; `#course/<id>/3` ouvre l'étape sans suffixe, sinon la première demi-étape ; `prev_stages` du collecteur est indexé par cet identifiant.

### 4.4 Archives (saisons passées, dépôt `courses-cyclistes-archives`)

Les archives vivent dans le dépôt **Camelbaggy/courses-cyclistes-archives** (GitHub Pages ; fichiers servis sous
`https://camelbaggy.github.io/courses-cyclistes-archives/data/archives/`), pas dans ce dépôt. Chemins ci-dessous relatifs à
`data/archives/` de ce dépôt-là (`collector.ARCHIVES_DIR`, variable d'environnement `ARCHIVES_DIR`). Écrites uniquement par
`python run_pipeline.py --archive SAISONS` (`collector.run_archive`, workflow `archives.yml` du dépôt d'archives, qui
checkout ce dépôt dans `code/`) ; ne touchent jamais aux fichiers de 4.1 à 4.3 de ce dépôt-ci (la suppression des fichiers
d'une saison archivée est faite par `update.yml`, voir la rotation ci-dessous).

- `index.json` : `{"generated_at", "seasons": [{"season", "complete", "races", "size_bytes"}]}`, saisons
  triées par ordre décroissant.
- `<année>/` : `races/uci-<id>.json` (même schéma que 4.2, `season` = année, résumés toujours
  `summary_source: "fallback"`), `index.json` (même schéma que 4.1, `upcoming` vide, `fdj_united_series` null, plus
  `"archive": true` et `"complete"`), `riders.json` (schéma des fiches coureurs, calculé à la date de fin de saison),
  `ranking.json` (classement UCI de fin de saison : World Ranking, à défaut « WorldTour Ranking » ; absent si aucun
  classement n'est disponible), `state.json` (`{"complete", "top10_checked": {id: bool}}`).
- **Compactage** (`collector.compact_race`) : toute clé à `null` est supprimée des lignes de classement et des fiches
  `riders` (la page traite absent = `null`) ; les classements annexes (toutes clés sauf `stage` et `gc`) sont limités
  aux 30 premières lignes (`ANNEX_TOP`) pour chaque étape sauf la dernière ; `final` reste complet ; les clés internes
  `_aso_done` sont retirées ; `_complete` est conservé.
- Une saison `complete` (parcourue entièrement, sans arrêt sur budget, et close selon les bornes UCI) n'est plus
  jamais recollectée. Sélection : `selection.select(comps, [])` (sans manche FDJ / Coupe de France historique), plus
  sondage « Français dans le top 10 » des .1 / .2 étrangères.

- **Rotation calendrier -> archives** : une saison S de `seasons.json.available` est à archiver quand S+1 est
  terminée : date du jour > fin de la dernière course de S+1 + 14 jours (max des `end_date`, à défaut `start_date`, des
  `races` et `upcoming` de `data/index-<S+1>.json`). Course à venir encore future, index de S+1 absent ou vide : pas de
  rotation. Fonction pure `collector.saisons_a_archiver(seasons_dispo, index_par_saison, today)`. Effets, répartis sur les
  deux dépôts : (1) `write_season_indexes` (update.yml, dépôt principal) ne liste plus S dans
  `seasons.json.available` et ne réécrit plus ses `index-S.json` / `riders-S.json` ; (2) `collector.migrer_saisons_anciennes`
  (début de `run_archive`, workflow du dépôt d'archives, qui lit le `data/` du dépôt principal checkouté en lecture seule)
  compacte chaque course de S dans `<S>/races/` (sans écraser une course déjà archivée ; les résumés d'origine sont
  conservés), écrit `index.json` (archive, complete), `ranking.json` + `riders.json` de fin de saison, `state.json`
  `{"complete": true, "top10_checked": {}}` ; **elle ne supprime rien** dans `data/`. Log `[ROTATION] saison S -> archives
  (N courses)` ; (3) le dépôt principal retire ensuite lui-même ses fichiers : `write_season_indexes` lit, une fois par
  passage et seulement s'il reste des fichiers de S, l'index public `collector.ARCHIVES_INDEX_URL`
  (`https://raw.githubusercontent.com/Camelbaggy/courses-cyclistes-archives/main/data/archives/index.json`) ; si S y figure
  avec `complete: true`, `collector.retirer_saisons_archivees` supprime `data/races/<id>.json` de S, `data/index-S.json`,
  `data/riders-S.json` (log `[ROTATION] saison S archivée dans courses-cyclistes-archives : fichiers retirés de data/`) ;
  index illisible ou saison non complète : rien n'est supprimé.
- **`editions.json`** (écrit par `collector.write_archives_index`, donc à chaque passage d'`archives.yml`, seulement
  s'il change) : `{"generated_at", "alias", "courses": {<clé>: [{"season", "race_id", "name", "uci_class", "category",
  "race_type", "start_date", "winner" (RiderRef réduit : id, name, nationality, flag, is_french), "best_french"
  ({rider, rank, classification} | null)}, …]}}`, saison décroissante ; courses `in_progress` exclues. **Clé d'édition** =
  `collector.cle_edition(nom, pays)` : nom en minuscules, sans accents, ponctuation (tirets, apostrophes…) remplacée par une
  espace, sans année (1900-2099) ni numéro d'édition isolé (`107e`, `3rd`), espaces normalisées, + `|PAYS` (ISO3) ; nom ou
  pays vide : pas de clé. Rapprochement EXACT sur cette clé, jamais flou (« Tour de France » ≠ « Tour de France Saitama
  Criterium », pays différent = autre course). **`alias_courses.json`** (racine du dépôt, `{}` au départ, édité à la main) :
  `{"clé source": "clé canonique"}` pour les changements de nom (sponsors) ; un seul niveau (pas de chaînage), jamais
  deviné ; recopié dans `editions.json.alias`. La page applique la même normalisation (`cleEdition` de index.html, **doit
  rester alignée** avec `cle_edition`).
- **`carrieres/<lettre>.json`** (lettre = première lettre a-z du `rider_id`, sinon `_`) : `{"<rider_id>": {"name",
  "nationality", "flag", "birth_date" (saison la plus récente), "seasons": {"<année>": {"team", "stats" (wins, podiums, top10,
  race_days, races, gc_wins, dnf : ceux présents), "uci_rank" (rang au classement de fin de saison, absent si non classé),
  "results" (victoires et podiums seulement, récents d'abord : date, race_id, label, classification, rank, + stage_number et
  race (nom) s'ils existent)}}}}`, saisons décroissantes, calculé à partir des `riders.json` des saisons d'archive.
  `carrieres/index.json` : `{"alias", "lettres"}` (la page ne demande que les lettres présentes). Rapprochement par `rider_id`
  exact (slug + date de naissance) ; **`alias_coureurs.json`** (racine, `{}` au départ, manuel) `{"rider_id source": "rider_id
  canonique"}`, jamais deviné ; si l'alias ferait figurer deux fois le même coureur la même saison, il est ignoré pour cette
  saison (`[WARN]`, rien n'est fusionné), SAUF si la source figure dans la clé **`_fusion_meme_saison`** du même fichier (liste de rider_id sources
  dont l'alias est aussi déclaré ; valeur non textuelle donc ignorée par `charger_alias`) : les deux identifiants de la saison sont alors réunis
  (entités : réécriture de l'identifiant dans chaque fiche de course avant cumul, donc stats, palmarès et équipes réunis, équipe principale = plus de
  jours, `equipes` liste les deux ; carrières : stats sommées, résultats réunis). Une course où les deux identifiants figurent n'est jamais fusionnée
  (`[WARN]`, aucun double comptage). Les fichiers de lettre sans coureur sont supprimés (données dérivées).
- La page lit `index.json` du dépôt d'archives (liste des saisons, `complete` ; base `BASE_ARCHIVES` : `?archives=`, sinon `<data>/archives` avec `?data=`, sinon l'URL publique du dépôt d'archives, voir CLAUDE.md) à l'ouverture de l'onglet Archives, puis
  `<année>/index.json`, `ranking.json` (si `complete`), et `races/<id>.json` / `riders.json` à la demande.
  `editions.json` est lu à l'ouverture d'une fiche course (encart « Éditions précédentes »), `carrieres/index.json` puis un
  seul `carrieres/<lettre>.json` à l'ouverture de l'onglet « Carrière » d'une fiche coureur.

### 4.5 Entités de l'encyclopédie (`entites/`, dépôt d'archives)

Générées par `encyclopedie.construire(archives_dir, data_dir)` (appelée à la fin de `collector.write_archives_index`, donc à chaque
passage d'archives.yml) dans `<archives_dir>/entites/`. Elles couvrent TOUTES les saisons : archives (`<année>/races/`,
`riders.json`, `ranking.json`) et Calendrier (`data/races/*.json` classées par `season`, `riders-<année>.json`, `ranking.json` si son
champ `season` désigne la saison). Une course présente dans les deux est lue dans les archives. Identités : `rider_id` exact +
`alias_coureurs.json` (règle de contradiction de `construire_carrieres`), courses : `cle_edition` + `alias_courses.json`. Clés à
`null` absentes ; JSON compact, trié ; écriture seulement si le contenu change ; fichiers devenus inutiles supprimés.

**Saison sportive = année civile de la date de la course** (décision du 18/11/2026), pas la saison UCI (mi-octobre -> mi-octobre : DataRide range
des courses de fin d'année dans la saison suivante, ex. Giro di Lombardia du 16/10/2010 dans l'archive 2011). Toute entité par saison (`season`
des éditions, palmarès, `saisons` des coureurs, équipes-saisons `<slug>-<année>`, `saisons/<année>.json`, `grands_tours`) suit l'année de
`start_date` (à défaut `end_date`) lue dans l'`index.json` de la saison ; date absente ou à plus d'un an de la saison de rangement : saison du
dossier (`collector.annee_course`). Le STOCKAGE ne change pas (dossiers d'archive par saison UCI, `data/`, rotation). `riders.json`, `ranking.json`
(rang UCI de fin de saison) et `state.json` restent associés à la saison UCI de leur dossier : `uci_rank` d'une saison sportive = celui du dossier
du même numéro (une saison qui n'existe que par report, sans dossier, n'a pas de rang). `editions.json` et `carrieres/` suivent la même règle
(`collector._reports_saison` retire / ajoute les statistiques et résultats des courses reportées). Les pages `saisons/<année>.json` comptent donc
les courses de l'année civile ; la page Courses reste découpée par fichiers (saison UCI).

- **`coureurs/<lettre>.json`** (lettre = 1re lettre a-z du `rider_id` canonique, sinon `_`) : `{rider_id: {"name", "nationality",
  "flag", "birth_date" (saison la plus récente), "saisons": {"<année>" (décroissantes): {"team" (nom de l'équipe-saison principale :
  équipe de marque aux plus nombreux jours de course ; une sélection nationale seulement si c'est la seule), "equipe" (id d'équipe-saison),
  "equipes" (tous les ids de la saison, par ordre d'apparition, si plusieurs), "stats" (wins, podiums, top10, race_days, races, gc_wins, dnf :
  ceux non nuls ; définitions de riders.py), "uci_rank", "uci_points" (de `riders*.json`, à défaut rapprochement avec `ranking.json`)}},
  "palmares": [victoires et podiums (rang 1-3) des classements d'étape / de course d'un jour et des classements finaux, récents d'abord :
  {"date", "season", "race_id", "course" (clé d'édition), "label", "classification" (stage|gc|points|mountain|youth), "rank", "category",
  "uci_class"}], "grands_tours": [{"season", "course": "tour"|"giro"|"vuelta", "race_id", "rank"} ou {…, "status": "DNF"|"OTL"|"DSQ"} (abandon
  constaté sur une étape, absent du général final)], "totaux": {"wins", "podiums", "gc_wins", "seasons"}, "historique_uci"? [[date, rang]] (E1c, trié par date, tous les instantanés où le coureur
  figure ; absent sans instantané), "corrections"? [{"champ": "birth_date"|"nationality", "uci": valeur UCI d'origine, "source": "Wikidata Qxxx (P569|P27)"}]
  (erreurs de source documentées, voir ci-dessous ; absent sans correction)}}`. `palmares` et `grands_tours`
  absents si vides. Les étapes d'une course en cours comptent (comme `riders.json`) ; ses classements généraux provisoires non.
- **Corrections de source documentées** (`corrections_coureurs.json`, racine, manuel) : `{"<rider_id>": {"birth_date"|"nationality": {"valeur",
  "uci" (valeur UCI d'origine), "source" ("Wikidata Qxxx (P569|P27)"), "date" (de la décision), "note"}}}`. Le `rider_id` NE CHANGE PAS (clé stable : slug
  + date UCI). La valeur corrigée est appliquée à l'affichage : `uci.rider_ref` (collecte en cours et nouvelles archives : `birth_date`, `nationality`,
  `flag` recalculé par `netutil.flag_code`, `is_french`), `encyclopedie.construire` (entités coureurs, pays, saisons, podiums d'éditions) et
  `collector.construire_carrieres`. Une correction n'est appliquée que si la valeur courante est celle de l'UCI d'origine (ou déjà corrigée : idempotent) ;
  si l'UCI a changé, `[WARN]` et rien n'est appliqué. Entrée invalide (champ inconnu, source absente, date / code pays mal formé, `uci` incohérent avec
  le `rider_id`) : ignorée avec `[WARN]`. Les fiches de course d'archive déjà écrites gardent la valeur UCI dans leurs `riders` (l'interface lit en
  priorité l'entité coureur pour la fiche coureur ; la fiche de course affiche la valeur UCI tant qu'elle n'est pas recollectée). Le rapprochement
  Wikidata (`wikidata.lister_coureurs`) lit la date de naissance des entités, donc la date corrigée.
- **Grands tours** (`encyclopedie.GRANDS_TOURS`) : clés d'édition EXACTES `tour de france|FRA`, `giro d italia|ITA`, `la vuelta ciclista a
  espana|ESP` (+ graphies `vuelta a espana|ESP`, `la vuelta a espana|ESP`, absentes des données actuelles), course par étapes terminée de
  classe 2.UWT / 2.WT / 2.HC / 2.HIS / 2.CH ; jamais de motif flou (« Tour de France Saitama Criterium », « Giro Ciclistico d'Italia »,
  « Tour de France Femmes » ne sont pas des grands tours). Trois par saison complète (vérifié 2019-2026).
- **`equipes/<année>.json`** : `{id: {"name" (libellé le plus fréquent), "season", "nationale": true + "pays" (ISO3) pour une sélection nationale,
  "effectif": [{"rider_id", "name", "flag", "jours" (jours de course, définition de `race_days`), "wins"}] (jours décroissants),
  "victoires": [{"date", "race_id", "course", "label", "classification" (stage|gc), "rider_id"}] (récentes d'abord),
  "grands_tours": {"tour"|"giro"|"vuelta": {"rank", "rider_id", "race_id"}} (meilleur classement final de l'équipe), "totaux": {"wins" (étapes et
  courses d'un jour), "gc_wins", "riders", "jours"}, "libelles": [variantes fusionnées, si plusieurs]}}`. **Équipe-saison** : id =
  `<slug du libellé>-<année>` (`netutil.slugify` : sans accents, ponctuation et casse), le libellé est celui de la fiche de course où le
  coureur a couru (pas le dernier de la saison). **Sélection nationale** (`_est_nationale`) : libellé normalisé égal au nom d'un pays de
  `PAYS_NOMS` (anglais UCI, français, graphies connues) ET tous les coureurs qui le portent cette saison ont la nationalité de ce pays ; un club
  qui aligne d'autres nationalités ou dont le nom n'est pas dans la table reste une équipe de marque. **`code_uci`** (E1b) : `TeamCode` UNIQUE des
  coureurs classés de la saison (`ranking.json`, clé `team_code`) dont le libellé d'équipe a le même slug que l'id ; plusieurs codes : absent
  (anomalie `code_uci_multiple`) ; jamais pour une sélection nationale. **`lignee`** (QID Wikidata) : si `wikidata/equipes.json` la prouve
  (voir ci-dessous). `equipes/index.json` : liste `[{"id", "name", "season", "wins",
  "riders", "nationale"?, "lignee"?, "cat"?, "pays"?}]` triée saison décroissante puis nom ; `cat` (« WT » WorldTeam, « Pro » ProTeam / Professional
  Continental, « Cont » Continental) vient des classes P31 de la lignée Wikidata (`lignees.json`) et n'est donné QUE si la lignée ne porte qu'un
  niveau (P31 n'est pas daté : une lignée Continental puis ProTeam porte les deux, `cat` absent, voir `lignees_index.json` `cats`) ; groupes sportifs,
  clubs, équipes féminines : jamais de `cat` ; `pays` = code ISO3 : celui des coureurs pour une sélection nationale, sinon le P17 de la lignée
  (si son libellé français correspond à un seul code de `PAYS_NOMS`) ; sans lignée, ni `cat` ni `pays`. **`equipes/lignees_index.json`** (index
  compact des lignées) : `{QID: {"n" (libellé Wikidata, à défaut nom de l'équipe-saison la plus récente), "s": [première, dernière saison], "eq": [ids
  d'équipes-saisons, récentes d'abord], "logo"? ({url, page, auteur?, licence, licence_url?} : logo Wikidata P154 à licence Commons lisible), "logo_depuis"?
  (année de début du nom actuel P1448 sans fin : la liste des participants n'affiche le logo, non daté, que pour les saisons >= cette année ; absent = jamais),
  "cat"? (niveau unique), "cats"? (plusieurs niveaux, ordre WT, Pro, Cont ; « cat la plus récente » n'est pas
  établissable sans P31 daté), "pays"? (ISO3), "pays_nom"? (libellé français P17)}}`. **`equipes/lignees.json`** : `{QID: {"libelle", "noms": [{"nom", "debut",
  "fin"}] (P1448, datés à la précision de la source : année, mois ou jour), "codes": [{"code", "debut", "fin"}] (P1998), "pays": {"qid", "libelle"},
  "classes": [libellés P31], "sitelinks": {fr, en, es, it, nl, de: titre}, "logo": {"url", "page", "auteur", "licence", "licence_url"} (seulement avec
  licence lisible), "equipes": [ids d'équipes-saisons, récentes d'abord], "saisons": [première, dernière]}}`, uniquement les lignées portant au moins
  une équipe-saison rapprochée.
  **R2a, données des articles d'équipe** :
  - `equipes/<année>.json` (17/11/2026) : **`codes_uci`** (`[code, …]` triés) quand les coureurs classés de la saison portent PLUSIEURS codes (`code_uci` reste
    absent) ; **`renommee`** (id) pour une équipe-saison SANS code : équipe-saison de la même saison au même effectif (>= 5 coureurs communs et >= 60 % de
    son effectif ; changement de nom en cours de saison, ex. Bora - Hansgrohe -> Red Bull - Bora - Hansgrohe 2024). Servent au maillot de la saison.
  - `equipes/<année>.json` : chaque équipe-saison gagne **`meme_nom`** (`[id, …]`, années croissantes) = ids des AUTRES saisons portant EXACTEMENT le même
    slug de libellé (id = `<slug>-<année>`) : aucune preuve de continuité (deux équipes homonymes peuvent n'avoir rien de commun), l'interface l'affiche
    « même nom en … » ; absent s'il n'y en a pas (sélections nationales comprises). **`mouvements`** `{"arrivees": [rider_id], "departs": [rider_id]}`
    seulement si l'équipe-saison de l'année précédente (année − 1) au même slug existe ET que les deux portent la même lignée Wikidata ; sinon absent.
  - `coureurs/<lettre>.json` : la saison d'un coureur porte déjà `equipe` (et `equipes`) = ids d'équipes-saisons ; ils existent TOUS dans
    `equipes/<année>.json` de la même saison (sélections nationales comprises ; vérifié par `encyclopedie.py --test` et sur les archives réelles : 37 790
    références, 0 inconnue). Nouveau : **`lignee`** (QID) dans la saison du coureur quand l'équipe-saison principale (`equipe`) en a une
    (toujours égal à `equipes/<année>.json[equipe].lignee`).
  - `equipes/index.json` : la clé du QID est **`lignee`** (déjà présente, inchangée ; pas de clé `l`) ; `lignees_index.json` et `lignees.json` inchangés.
  - **`equipes/lignees/<QID>.json`** (un fichier par lignée de `lignees.json`, ~10 Ko en moyenne, 91 Ko au maximum, 3,3 Mo au total sur les archives
    2017-2026) : `{"qid", "nom" (libellé Wikidata, à défaut libellé de l'équipe-saison la plus récente), "noms": [{"nom", "debut", "fin"?}] (P1448 daté,
    précision de la source), "codes": [{"code", "debut", "fin"?}] (P1998), "pays"? (ISO3, seulement si le P17 correspond à un seul code de `PAYS_NOMS`),
    "pays_nom"? (libellé P17), "cats"? (niveaux P31 distincts, ordre WT, Pro, Cont ; P31 n'est pas daté), "sitelinks"? `{langue: titre}` (fr, en, es, it,
    nl, de), "logo"? `{url, page, auteur?, licence, licence_url?}` (licence lisible seulement),
    "saisons": {"<année>": {"id" (équipe-saison), "libelle", "code_uci"?, "effectif": [{"rider_id", "n"?, "f"?, "jours", "v"}] (jours décroissants,
    `n` nom, `f` drapeau, `v` victoires), "victoires": [{"date", "race_id", "course", "label", "classification" (stage|gc), "rider_id"}] (récentes
    d'abord), "grands_tours"? `{tour|giro|vuelta: {rank, rider_id, race_id}}`, "totaux": {wins, gc_wins, riders, jours}, "autres"? [ids]}}` (années
    décroissantes ; contenu STRICTEMENT repris de `equipes/<année>.json`, sans second calcul ; `autres` = autres équipes-saisons de la même lignée la
    même année si Wikidata en rattache plusieurs : la plus active est détaillée, aucune sur les archives actuelles),
    "mouvements": {"<année>": {"arrivees": [rider_id], "departs": [rider_id], "depuis": <année précédente présente>}}` (années décroissantes ; une entrée
    par saison de la lignée SAUF la plus ancienne ; comparaison de l'effectif de deux saisons CONSÉCUTIVES PRÉSENTES dans la lignée, `depuis` > année − 1
    quand une saison manque dans nos données : **constatés dans nos données, à la saison près ; un coureur peut avoir couru peu de jours, ou ne pas
    figurer dans nos classements ; ce n'est pas un transfert officiel** ; les doublons de rider_id non fusionnés apparaissent comme départ + arrivée),
    "totaux_lignee": {"saisons": [première, dernière], "victoires" (somme des `totaux.wins`), "coureurs" (rider_id distincts), "grands_tours_gagnes"
    (nombre de classements généraux de grand tour de rang 1 de l'équipe)}}`. Clés absentes = pas de donnée. Les équipes-saisons sans lignée n'ont pas de
    fichier de lignée (tout est dans `equipes/<année>.json`).
  - **Id d'équipe-saison à partir d'un libellé brut** (miroir JS pour les lignes de résultats qui n'ont que le libellé d'équipe) : `id = slugify(libellé) +
    "-" + année de la saison`. `netutil.slugify(nom)` = `normalize(nom).replace(" ", "-")` ; `normalize` : (1) `unicodedata.normalize("NFKD", nom or "")` ;
    (2) encodage ASCII avec `ignore` : tout caractère non ASCII restant est SUPPRIMÉ (les accents se décomposent en lettre + diacritique, le diacritique
    tombe ; mais **ł, ß, ø, æ, đ, œ… n'ont pas de décomposition et disparaissent** : « Perła » -> « pera », « OßWALD » -> « owald »), tirets
    typographiques compris (– — : supprimés ; les espaces voisins font le séparateur) ; (3) minuscules ; (4) toute suite de caractères hors `[a-z0-9]`
    (espaces, `|`, `&`, `'`, `.`, `/`, `:`, tirets…) devient UN espace ; (5) trim + espaces multiples réduits ; (6) espaces -> `-`. Attention à l'ORDRE : le
    passage en ASCII précède le remplacement par des espaces, donc un caractère non ASCII sans décomposition n'est PAS un séparateur (« Pauwels Sauzen –
    Bingoal » : le tiret demi-cadratin, supprimé, laisse les deux espaces voisins -> un seul séparateur ; « Perła » reste collé). Chaîne vide ou sans
    caractère alphanumérique -> `""`. Le libellé utilisé est celui de la ligne de résultat (variantes de casse / ponctuation d'une même équipe ->
    même slug) ; la saison est celle de la fiche de course. Couples réels (constante `encyclopedie.COUPLES_SLUG`, testés par `encyclopedie.py --test`) :

    | libellé | slug |
    |---|---|
    | `Groupama - FDJ` | `groupama-fdj` |
    | `Arkea-B&B Hotels` | `arkea-b-b-hotels` |
    | `Team Dauner D&DQ \| Akkon` | `team-dauner-d-dq-akkon` |
    | `Amore E Vita \| P:` | `amore-e-vita-p` |
    | `Canel's - Java` | `canel-s-java` |
    | `Akros - Excelsior - Thömus` | `akros-excelsior-thomus` |
    | `Aviludo - Louletano - Loulé` | `aviludo-louletano-loule` |
    | `7ELEVEN Cliqq - AIR21 by Roadbike Philippines` | `7eleven-cliqq-air21-by-roadbike-philippines` |
    | `AP Hotels & Resorts /tavira/ SC Farense` | `ap-hotels-resorts-tavira-sc-farense` |
    | `Pauwels Sauzen – Bingoal` (U+2013) | `pauwels-sauzen-bingoal` |
    | `Lubelskie Perła Polski` | `lubelskie-pera-polski` |
    | `RAD-NET OßWALD` | `rad-net-owald` |
    | `Heizomat RAD-Net.de` | `heizomat-rad-net-de` |

    Un libellé dont le slug donne un id absent de `equipes/<année>.json` (équipe sans classement collecté cette saison) : pas de lien.
- **`coureurs/index.json`** (liste de tous les coureurs, rider_id canoniques, triée par `id`, ~2,2 Mo / ~0,5 Mo gzip sur 2017-2026) :
  `[{"id", "n" (nom), "f"? (code drapeau), "nat"? (ISO3), "eq"? (libellé de l'équipe principale de la dernière saison du coureur), "eqid"? (id d'équipe-saison),
  "s": [première, dernière saison], "v" (victoires totales), "p" (podiums), "uci"? (meilleur rang UCI de fin de saison, `uci_rank` des saisons),
  "fr"? (true si FRA), "act"? (true si présent dans la saison la plus récente des données), "photo"? (true si image Wikidata sous licence lisible)}]`.
  Coureurs sans nom réel (vide ou ponctuation seule) exclus ; coureurs historiques (`wd-Q…`) non inclus.
- **`courses/index.json`** (liste des épreuves, triée par clé, ~0,15 Mo) : `[{"k" (clé d'édition), "n" (nom le plus récent), "pays", "f"?, "cl"? (classe UCI la
  plus récente), "cat"? (`selection.categorie_classe(cl)` : WT, Pro, .1, .2), "type"? (`one_day` / `stage_race`), "s": [première, dernière saison UCI],
  "h"? (première année de l'historique Wikidata, si présent), "ed" (nombre d'éditions UCI), "der": {"saison", "race_id", "vainqueur"?: {"id", "nom"?}}
  (dernière édition terminée)}]`.
- **`courses/<lettre>.json`** (lettre = 1re lettre a-z de la clé, sinon `_`) : `{clé d'édition: {"noms": {variante: [saisons]}, "pays", "flag",
  "classes": {année: uci_class}, "type", "editions": [{"season", "race_id", "start_date", "end_date", "podium": [{"rank", "id", "name", "nat",
  "flag", "team"}] (rangs 1-3 du général final, ou du classement d'un jour), "best_french": {"id", "name", "flag", "rank", "classification"}}]
  (saison décroissante ; courses en cours exclues), "records": {"victoires_par_coureur": [{"id", "name", "wins"}] (≥ 2), "victoires_par_pays":
  {ISO3: n}}}}` ; victoire = rang 1 du podium. Une course sans nom ou sans pays n'a pas de clé : absente (comptée dans les anomalies).
- **`saisons/<année>.json`** : `{"season", "courses": {"total" (terminées), "par_categorie", "en_cours"?}, "victoires_par_pays" (étapes et courses
  d'un jour, par nationalité du vainqueur), "victoires_par_equipe" (top 30), "coureurs_victorieux" (top 30 : id, name, nat, wins),
  "victoires_francaises" (nombre de victoires de coureurs FRA), "classement_uci": {"present", "name", "date", "final" (archive complète), "classes"},
  "instantanes_uci"? [{"date", "raisons"}] (instantanés du classement UCI disponibles, voir ci-dessous), "complete"?, "source": "archives"|"calendrier"}`.
- **`classements/<année>/`** (E1c, écrit par `collector.collecter_classements`, JAMAIS par `encyclopedie.construire`, qui le lit) : historique du classement
  UCI individuel (World Ranking, à défaut « WorldTour Ranking » des saisons anciennes). `<AAAA-MM-JJ>.json` : `{"date", "nom", "moment_id", "raisons": ["fin de
  mois" | "après <nom de course>"], "lignes": [[rang, rider_id | null, points | null, team_code | null]]}` (top 500 + tous les coureurs FRA au-delà ; les ex aequo
  partagent le rang ; `rider_id` = nom UCI + date de naissance, null sans date) ; **immuable** (jamais relu ni réécrit). `index.json` : `[{"date", "raisons",
  "fichier"}]` des instantanés présents (les raisons y sont tenues à jour). `etat.json` : `{"complet": true, "groupe", "source"}` quand la saison est close et
  intégralement collectée. Choix : dernier moment de chaque mois civil fini + premier moment strictement postérieur à la fin de chaque course WorldTour
  (délai de publication : le classement est calculé le mardi). Estimations (docs/PLAN_ENCYCLOPEDIE.md §7) : ~30-35 instantanés, ~1 Mo et ~140 requêtes par saison
  moderne ; ~25 instantanés, ~0,3 Mo et ~30 requêtes par saison ancienne (WorldTour Ranking, ~250 lignes).
- **`pays.json`** : `{ISO3: {"nom" (français, si dans `PAYS_NOMS`), "flag", "saisons": {année: {"coureurs", "victoires", "podiums"}}, "meilleurs": [{"id",
  "name", "wins"}] (top 10 sur toutes les saisons)}}`.
- **`recherche/<lettre>.json`** : liste triée d'entrées `{"n" (libellé), "t": "c" (coureur) | "e" (équipe, regroupée par libellé : id = la saison la
  plus récente) | "r" (course : id = clé d'édition), "id", "f" (drapeau), "y": [première, dernière saison], "nat"?: true (sélection nationale)}`,
  présentes sous la 1re lettre normalisée (a-z, sinon `_`) de CHAQUE mot du libellé d'au moins 2 lettres (recherche par mot).
- **`index.json`** : `{"generated_at", "compteurs": {coureurs, equipes_saisons, equipes_nationales, courses, editions, saisons, pays}, "saisons",
  "saisons_archives", "saisons_calendrier", "grands_tours_par_saison", "sources", "limites"}`.
- **Champ `wikidata` d'un coureur** (E1b, absent sans rapprochement strict) : `{"qid", "lieu": {"qid", "libelle"}, "taille" (m), "image": {"url"
  (vignette 320 px Commons), "page", "auteur"?, "licence", "licence_url"?} (absente sans licence lisible), "wikipedia": {langue: titre}, "equipes_wd": [{"qid",
  "libelle"?, "debut"?, "fin"?, "precision_debut"?, "precision_fin"? ("annee" | "mois" | "jour")}] (P54, début tel que Wikidata le donne)}`. `index.json`
  gagne les compteurs `lignees` et `coureurs_wikidata`.
- **Cache Wikidata** `entites/wikidata/` (écrit par `wikidata.run_wikidata` seul, jamais par `construire`) : `coureurs.json` `{rider_id canonique:
  {"qid": QID|null, "verifie": AAAA-MM-JJ, "raison"? (null : aucune | ambigu), "lieu", "taille", "image" (nom de fichier Commons), "sitelinks", "equipes"}}` ;
  `images.json` `{fichier: {"url", "page", "auteur"?, "licence", "licence_url"?, "verifie"} | {"url": null, "raison": absent | licence, "verifie"}}` ;
  `equipes.json` `{id d'équipe-saison: {"qid", "preuve", "verifie"} | {"qid": null, "raison", "verifie"}}` (`preuve` = « P1998 <code> [période] ; P1448 « nom »
  » ou « saison « libellé » », ou `alias`) ; `lignees.json` `{QID: {libelle, noms, codes, pays, classes, sitelinks, logo (nom de fichier), verifie}}` ;
  `libelles.json` `{QID: libellé fr, sinon en}`. Rapprochement coureur : un seul candidat vérifié (P569 jour égale, nom concordant, occupation P106 =
  Q2309784 ou sous-classe) ; équipe : P1998 daté contenant la saison + nom officiel P1448 daté (ou élément saison de l'année) concordant + un seul
  parent ; `alias_equipes.json` (racine du code) `{"id équipe-saison": "QID"}` pour le reste. Re-vérification 180 jours, `null` re-tenté après 60.
- **Historique des épreuves (palmarès Wikidata, `historique.py`)** : avant (et entre) nos données UCI, vainqueur et podium de TOUTES les éditions des séries retenues,
  depuis Wikidata seul (CC0). Séries : `series_historiques.json` (racine du code, `{clé d'édition (collector.cle_edition, après alias): {"qid" (série), "preuve":
  {"regle", "annees" (2019-2025 où le vainqueur Wikidata = le nôtre), "comparees", "discordantes", "verifie"}, "conteneur"? true}}`) ; refus à part dans
  `series_historiques_refusees.json` (`{clé: {"qid", "raison": preuve_insuffisante | moins_de_2_editions_2019_2025 | lecture_incomplete | ambigu | aucune_candidate,
  …}}`). **Preuve** : au moins 2 années 2019-2025 pour lesquelles Wikidata et nos données n'ont chacun qu'UNE édition, et le vainqueur Wikidata (statut `ok`) est notre
  vainqueur (cache `entites/wikidata/coureurs.json` rider_id -> QID, qui tranche s'il existe ; sinon date de naissance P569 à précision jour égale à celle de notre
  `rider_id` ET nom concordant). Plusieurs clés (noms successifs d'une épreuve) peuvent désigner la même série. **Cache** `entites/historique/` (écrit par
  `historique.run_historique` seul, série par série, reprenable) : `editions/<lettre>.json` `{clé: [{"annee", "qid" (élément de l'édition), "date"? (précision de
  la source : AAAA, AAAA-MM ou AAAA-MM-JJ), "annee_source"? "libelle" (année lue dans le libellé, sans date), "qid_conteneur"?, "vainqueur"? (QID, seulement si
  statut `ok`), "podium": [{"rang", "qid"}] (P1346 + P2501 ; rang 1 seulement si `ok`), "statut": ok | non_attribue | conflit | inconnu, "detail"?
  {"p1346": [QID], "p2321": [QID] (rang 1 du classement), "ignores": [QID non humains], "raison", "parts"}, "wikipedia"? {fr, en, es, it, nl, de: titre},
  "verifie"}]}` (trié par année ; les valeurs en désaccord sont gardées toutes, jamais tranchées : « non attribué » = P1346 rang 1 = Q66666778, ex. Tour de France
  1999-2005 ; conflit = plusieurs rang 1 ou P1346 ≠ P2321) ; `coureurs.json` `{QID humain: {"nom" (fr, sinon en, sinon autre langue), "naissance"?, "naissance_precision"?
  (jour | mois | annee), "deces"?, "deces_precision"?, "nationalite"? (code CIO via P984 du pays P27 : texte, ou liste si plusieurs), "wikipedia"?, "rider_id"?
  (nôtre, par le cache Wikidata ou rapprochement strict nom + date exacte unique), "verifie"}}` ; `pays.json`, `non_personnes.json` (équipes ignorées), `etat.json`
  (`{QID de série: {"verifie", "editions", "cles"}}`). Re-vérification d'une série (et de ses coureurs) après 180 jours. **Dans les entités** (`encyclopedie.construire`
  lit ce cache ; rien n'est écrit sans lui) : `courses/<lettre>.json` gagne `"historique": [{"annee", "date"?, "vainqueur"? (id : rider_id canonique ou `wd-<QID>`),
  "podium": [{"rang", "id", "name", "nat"?, "flag"?}], "statut", "detail"? {"p1346"|"p2321": [{id, name, …}], "ignores", "raison"}, "source_qid", "wikipedia"?}]`
  (récents d'abord) pour les SEULES années absentes de nos éditions UCI (clé ou clé sœur désignant la même série), `"historique_info"` `{"source": "wikidata",
  "annees": [min, max], "editions"}` et `"records_historique"` `{"annees_couvertes": [min, max] (UCI + historique), "editions_avec_vainqueur", "victoires_par_coureur"
  [{id, name, wins}] (≥ 2), "victoires_par_pays" (nationalité unique seulement), "victoires_pays_indeterminees"?, "non_attribuees"?, "conflits"?}` (records UCI inchangés dans
  `records`) ; `coureurs/<lettre>.json` : `"palmares_historique": [{"annee", "course", "rang", "source_qid", "date"?}]` + `"palmares_historique_source": "wikidata"` pour
  un coureur rattaché ; `coureurs_historiques/<NN>.json` (NN = deux derniers chiffres du QID, « wd-Q12345 » -> `45.json`, déterminé par l'identifiant seul)
  `{"wd-<QID>": {"name", "nationality"? (code ou liste), "flag"?, "birth_date"?, "birth_precision"?, "death_date"?, "death_precision"?, "wikidata": {"qid",
  "wikipedia"}, "source": "wikidata", "palmares_historique": [...], "totaux": {"wins", "podiums" (rangs 1-3)}}}` pour les coureurs d'un podium ou d'un détail qui
  ne sont pas dans nos données ; recherche : entrées `{"t": "c", "id": "wd-Q…"}` ; `index.json` : compteurs `coureurs_historiques`, `editions_historiques`.
  Règles de lecture Wikidata : docs/recherche/historique_avant_2009.md §9.
- Mesure (archives 2019-2025 + Calendrier 2026-2027, 15 nov. 2026) : 13 180 coureurs, 2 310 équipes-saisons, 524 courses, 1 503 éditions ;
  18,9 Mo (coureurs 10,6 ; équipes 4,1 ; recherche 3,1 ; courses 1,0) ; ~8 s, ~120 Mo de mémoire.

## 5. Interfaces Python (contrat entre modules)

Tous les modules utilisent `netutil.py` (`fetch_text`, `fetch_json`, `post_form_json`, pause par hôte, cache
disque optionnel `--save-raw`). Aucun module ne lève d'exception vers le collecteur : en cas d'échec il logge
`[WARN]` et renvoie `None` / `[]`.

`uci.py`
- `get_season_id(year) -> int | None`
- `list_competitions(season_id) -> list[dict]` : courses hommes élite courues/en cours, normalisées
  `{"competition_id", "name", "country", "flag", "uci_class", "start_date", "end_date"}`.
- `list_upcoming(year) -> list[UpcomingRace]` (calendrier prévisionnel ; `[]` si non disponible).
- `get_race(competition) -> dict` : `{"stages": [Stage sans route/ai_summary], "final": Classifications | None,
  "riders": {...}, "race_type", "stages_total": None}` — toutes les étapes publiées, tous les classements.

`aso.py` : `match_race(name, start_date) -> dict | None` (site + slug ASO si la course est ASO),
`enrich_stage(aso_ref, stage_number, stage: Stage) -> None` (complète `route`, `bonus_s`/`penalty_s`, `teams`
manquants, en rapprochant par dossard puis nom ; ne remplace jamais une valeur UCI par une valeur différente :
divergence → log `[DIVERGENCE]`), `get_story(aso_ref, stage_number) -> str | None` (texte brut d'article).

`directvelo.py` : `find_story(race_name, date) -> str | None`.

`lnc.py` : `get_fdj_united_series() -> dict | None` (bloc `fdj_united_series` de l'index).

`cyclingnews.py` : `fetch_items() -> list[{"title", "date", "categories", "text"}]`,
`find_story(items, race_name, date, stage_number) -> str | None`.

`selection.py` : `select(competitions, fdj_races) -> list[(competition, category, reason)]` et
`french_top10(race) -> bool`.

`agents_flash.py` : `build_stage_dossier(race, stage_index, stories: list[str]) -> str`,
`summarize_stage(race, stage_index, stories) -> (texte, source)` — rédacteur Gemini Flash + contrôleur
Flash-Lite, repli déterministe, budget `AI_BUDGET_SECONDS`, comme le projet foot. 3 à 5 phrases, en français,
centré sur la course puis sur les Français. Les textes `stories` (articles) servent de contexte narratif ; tout
chiffre (rang, écart, temps) du résumé doit figurer dans la partie factuelle du dossier (contrôle).

`notify.py` : `send(index_path)` publie `index.json["notification"]` sur ntfy (JSON POST, comme le foot).

`collector.py` / `run_pipeline.py` : orchestration (chef de projet).

## 6. Interface (`index.html`, page unique sans dépendance, mobile ~390 px)

Encyclopédie à routes (hash), thème sombre ; détail du routeur, des pages et du gabarit d'article : CLAUDE.md « Interface ».

- Navigation : en-tête (marque, recherche, menu horizontal ≥ 880 px) et barre du bas sur mobile : **Accueil · Courses · Équipes · Coureurs · Classements**.
- Routes : `#/` · `#courses[/<année>|/epreuves]` · `#epreuve/<clé>` · `#course/<race_id>[/<étape|F>]` · `#equipes[/<année>]` · `#coureurs` · `#coureur/<id>` · `#classements[/uci[/<année>]|/fdj]` · `#recherche/<texte>`.
- **Accueil** : courses en cours, derniers résultats (`latest`), courses à venir (`upcoming` des saisons du Calendrier), top 10 UCI (`ranking.json`), Français à la une (`french_wins`),
  « Ce jour-là » (`entites/courses/`), compteurs (`entites/index.json`).
- **Courses** : toutes les saisons (Calendrier + `archives/index.json`) ; Résultats / À venir (Calendrier seulement) avec filtres de catégorie ; Épreuves (`entites/courses/index.json`, filtres catégorie, pays, recherche).
- **Équipes** (R1) : `entites/equipes/index.json`, une ligne par équipe-saison (nom, pays, catégorie, victoires, coureurs), sans article. **Coureurs** : `entites/coureurs/index.json` (annuaire filtrable) + vue Français (`riders-<année>.json`).
- **Classements** : UCI actuel (`ranking.json`), fin de saison (`<année>/ranking.json`), instantanés (`entites/classements/<année>/`, noms par `coureurs/index.json`) ; FDJ United Series.
- **Articles** (gabarit commun) : fil d'Ariane, titre, infobox, onglets, navbox repliable. Édition : podium, navigation précédente / suivante, sélecteur d'étape, résumé, parcours, classements, participants, pays.
  Épreuve : tuiles, Palmarès · Records · Historique. Coureur : tuiles, Aperçu · Palmarès · Saisons · Grands tours · Classement UCI · Parcours · Saison. Valeur absente : ligne absente.
- Formatage : temps `h:mm:ss`, écarts `+m:ss`, « m.t. » pour un écart nul hors premier. Toute donnée insérée dans le HTML passe par `esc()`. Drapeaux flagcdn.com.

## 7. Planification et notification

Workflow `update.yml` : toutes les heures de 13 h à 22 h UTC + 6 h UTC (rattrapage), commit de `data/` sur `main`.
Push ntfy seulement si de nouveaux résultats de courses suivies sont apparus depuis le dernier passage
(une seule notification par passage, regroupant les nouveautés ; clés dans `state.json`).
Secrets : `GEMINI_API_KEY`, `NTFY_TOPIC` ; variable `DASHBOARD_URL`.
