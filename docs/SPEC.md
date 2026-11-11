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

`{"notified": ["uci-76380:F", "uci-76012:3", …], "last_run": "…"}` — clé `<race_id>:<stage_number|F>`.

### 4.4 `data/archives/` (saisons passées, mode archives)

Écrit uniquement par `python run_pipeline.py --archive SAISONS` (`collector.run_archive`, workflow `archives.yml`) ;
ne touche jamais aux fichiers de 4.1 à 4.3, sauf la rotation décrite ci-dessous (suppression des fichiers d'une saison migrée).

- `data/archives/index.json` : `{"generated_at", "seasons": [{"season", "complete", "races", "size_bytes"}]}`, saisons
  triées par ordre décroissant.
- `data/archives/<année>/` : `races/uci-<id>.json` (même schéma que 4.2, `season` = année, résumés toujours
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
  rotation. Fonction pure `collector.saisons_a_archiver(seasons_dispo, index_par_saison, today)`. Effets : (1)
  `write_season_indexes` (update.yml) ne liste plus S dans `seasons.json.available` et ne réécrit plus ses
  `index-S.json` / `riders-S.json` ; (2) `collector.migrer_saisons_anciennes` (début de `run_archive`, archives.yml
  seulement, jamais update.yml qui n'a pas `data/archives/`) compacte chaque course de S dans `archives/<S>/races/`
  (sans écraser une course déjà archivée ; les résumés d'origine sont conservés), écrit `index.json` (archive, complete),
  `ranking.json` + `riders.json` de fin de saison, `state.json` `{"complete": true, "top10_checked": {}}`, et
  seulement ensuite supprime `data/races/<id>.json`, `data/index-S.json`, `data/riders-S.json`. Log
  `[ROTATION] saison S -> archives (N courses)`. archives.yml commit `data/` (suppressions incluses).
- **`data/archives/editions.json`** (écrit par `collector.write_archives_index`, donc à chaque passage d'`archives.yml`, seulement
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
- **`data/archives/carrieres/<lettre>.json`** (lettre = première lettre a-z du `rider_id`, sinon `_`) : `{"<rider_id>": {"name",
  "nationality", "flag", "birth_date" (saison la plus récente), "seasons": {"<année>": {"team", "stats" (wins, podiums, top10,
  race_days, races, gc_wins, dnf : ceux présents), "uci_rank" (rang au classement de fin de saison, absent si non classé),
  "results" (victoires et podiums seulement, récents d'abord : date, race_id, label, classification, rank, + stage_number et
  race (nom) s'ils existent)}}}}`, saisons décroissantes, calculé à partir des `riders.json` des saisons d'archive.
  `carrieres/index.json` : `{"alias", "lettres"}` (la page ne demande que les lettres présentes). Rapprochement par `rider_id`
  exact (slug + date de naissance) ; **`alias_coureurs.json`** (racine, `{}` au départ, manuel) `{"rider_id source": "rider_id
  canonique"}`, jamais deviné ; si l'alias ferait figurer deux fois le même coureur la même saison, il est ignoré pour cette
  saison (`[WARN]`, rien n'est fusionné). Les fichiers de lettre sans coureur sont supprimés (données dérivées).
- La page lit `archives/index.json` (liste des saisons, `complete`) à l'ouverture de l'onglet Archives, puis
  `archives/<année>/index.json`, `ranking.json` (si `complete`), et `races/<id>.json` / `riders.json` à la demande.
  `editions.json` est lu à l'ouverture d'une fiche course (encart « Éditions précédentes »), `carrieres/index.json` puis un
  seul `carrieres/<lettre>.json` à l'ouverture de l'onglet « Carrière » d'une fiche coureur.

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

- Onglet **Archives** (5e) : menu déroulant des saisons archivées (« 2023 (collecte en cours) » si `complete` est faux),
  encart « Classement UCI de fin de saison » (top 10), « Victoires françaises », liste des courses avec les mêmes filtres
  de catégorie que le Calendrier ; fiches course et coureur issues de `archives/<année>/`.
- Fiche course : encart repliable **Éditions précédentes** (sous le tableau), chargé sans bloquer la fiche, absent s'il n'y a
  aucune autre édition : éditions archivées (`editions.json`) + courses de même clé des saisons du Calendrier
  (`index-<année>.json`) ; année, vainqueur et meilleur Français (liens coureur lus dans la saison de l'édition), lien vers la
  fiche de l'édition.
- Fiche coureur : onglets **Saison** (fiche de la saison du contexte) et **Carrière** (tableau par saison : équipe, victoires,
  podiums, top 10, jours de course, rang UCI de fin de saison ; palmarès victoires/podiums replié par saison ; saisons du
  Calendrier ajoutées en tête si le même `rider_id` figure dans `riders-<année>.json`, leur rang UCI étant marqué `*` : classement
  le plus récent, pas de fin de saison). Aucune donnée : « Pas d'archives pour ce coureur ».
- Onglets : **Récents** (cartes `latest` : course, étape, vainqueur, meilleur Français, résumé IA) ·
  **Calendrier** (courses de la saison groupées par mois, filtre par catégorie WT / Pro / FDJ / .1 / .2 / Champ.,
  statut, vainqueur ; à venir en grisé) · **FDJ United Series** (classement + manches) · **Français**
  (victoires françaises de la saison).
- Fiche course (au clic) : en-tête (classe, pays, dates), sélecteur d'étape, résumé IA, carte parcours (si
  `route`), sous-onglets Étape / Général / Points / Montagne / Jeunes / Équipes / Abandons, coureurs français
  surlignés + filtre « Français seulement », porteurs de maillots.
- Formatage : temps `h:mm:ss`, écarts `+m:ss`, « m.t. » pour un écart nul hors premier.
- Toute donnée insérée dans le HTML passe par `esc()`. Drapeaux flagcdn.com.

## 7. Planification et notification

Workflow `update.yml` : toutes les heures de 13 h à 22 h UTC + 6 h UTC (rattrapage), commit de `data/` sur `main`.
Push ntfy seulement si de nouveaux résultats de courses suivies sont apparus depuis le dernier passage
(une seule notification par passage, regroupant les nouveautés ; clés dans `state.json`).
Secrets : `GEMINI_API_KEY`, `NTFY_TOPIC` ; variable `DASHBOARD_URL`.
