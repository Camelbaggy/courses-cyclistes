# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

Dashboard mobile des courses cyclistes sur route, hommes élite, centré sur les coureurs français : collecte des
résultats officiels → résumés IA → `data/` (JSON) → page statique GitHub Pages → push ntfy après chaque étape ou
course. Contrat détaillé (schéma JSON, interfaces des modules, règles de sélection) : `docs/SPEC.md`. Recherches et
sondes sur les sources : `docs/recherche/`. Tout est en français : interface, logs, messages de commit, commentaires.

**Règle cardinale : zéro hallucination.** Classements, temps, écarts, dossards, nationalités, parcours viennent des
sources. Seules valeurs dérivées (écarts recalculés, meilleur Français, maillots, mouvements au général) : calculs
déterministes. Un champ absent reste `null` / vide. Les résumés ne décrivent un scénario (échappée, sprint, chute…)
que si un récit d'article le rapporte ; un contrôle déterministe l'impose (`agents_flash.check_numbers`).

## Commandes

Python 3 bibliothèque standard uniquement ; la CI tourne en **Python 3.11** (pas de syntaxe 3.12+).

```bash
python run_pipeline.py --no-notify                    # saison en cours, sans push
python run_pipeline.py --season 2026 --only Roubaix   # une course
python tools/inspect_data.py data                     # résumé lisible des données produites
python uci.py && python selection.py && python wikipedia_cal.py && python riders.py --test   # tests locaux (assert)
AI_BUDGET_SECONDS=0 python tools/essais/essai_ia.py   # dossier, repli, notification sur tools/fixtures_ia
python tools/apercu.py <dossier> [--data tools/fixtures/data] [--sombre]   # captures 390 px (Playwright), dossier obligatoire
ARCHIVES_DIR=/tmp/arch python run_pipeline.py --archive 2023 --max-races 5  # mode archives (sans ARCHIVES_DIR : data/archives/, à supprimer ensuite)
python collector.py --test                            # tests locaux de compact_race (sans réseau)
python encyclopedie.py --test                         # tests locaux des fichiers entites/ (sans réseau)
python wikidata.py --test                             # tests locaux Wikidata / Commons (réponses simulées)
python run_pipeline.py --wikidata --budget-min 300    # cache Wikidata (ARCHIVES_DIR/entites/wikidata/ SEUL) ; --entites reconstruit entites/ à la main
python -m py_compile *.py tools/*/*.py                # contrôle statique
```

`AI_BUDGET_SECONDS=0` ou pas de `GEMINI_API_KEY` : résumés de repli déterministes. Attention : `python riders.py`
sans `--test` écrit un fichier dans `data/` (à supprimer, `data/` n'est écrit que par le pipeline).

### Tester sur de vraies données

Le conteneur de développement n'a pas accès aux sources ; GitHub Actions oui. Sur une branche `ccr-*` :
- commit contenant `[essai:<nom>]` → `tools/essais/essai_<nom>.py` (workflow `essais.yml`, sans commit) ;
- commit contenant `[pipeline]` → pipeline complet, données **committées sur la branche**
  (`pipeline_branche.yml` ; options `[avec-ia]`, `[saison:2026]`, `[max:N]`) ; puis `git pull` et
  `tools/inspect_data.py` / `tools/apercu.py --data data` en local.
Pour tester le collecteur complet sans committer de données : `[essai:collecte]` (travaille sur une copie de `data/`).
Lire les logs avec les outils GitHub MCP. `update.yml` (horaire, 13 h–22 h UTC + 6 h 41) commit `data/` sur `main` :
une branche de travail se retrouve vite derrière `main` ; ne pas committer `data/` à la main sur `main`. Une PR
fusionnée ne doit pas être réutilisée : repartir de `origin/main` et ouvrir une nouvelle PR.
Claude peut fusionner lui-même ses PR (outils GitHub MCP) une fois le travail vérifié (contrôles locaux, essais
ou logs CI concluants), sans attendre de validation.
Déléguer à des agents Sonnet (outil Agent, `model: "sonnet"`) les tâches opérationnelles (lecture de logs, essais,
contrôles), l'écriture de code et la rédaction de fichiers ; garder la conception et la vérification finale.

## Architecture

```
run_pipeline.py ── collector.py ─┬ uci.py        source principale : DataRide (résultats, classes, saisons)
                                 ├ selection.py  courses suivies (classe, FDJ, France, Français top 10)
                                 ├ lnc.py        FDJ United Series (ex-Coupe de France)
                                 ├ aso.py        enrichissement ASO (bonifs, équipes, parcours, récits)
                                 ├ directvelo.py récits des courses françaises (Crawl-delay 10 s)
                                 ├ cyclingnews.py récits (RSS, ~3 jours de profondeur)
                                 ├ wikipedia_cal.py calendrier à venir (Wikipédia EN + FR « UCI ProSeries {année} »…, fusionnés) + LNC
                                 ├ encyclopedie.py entités de l'encyclopédie (coureurs, équipes-saisons, courses, saisons, pays, recherche) -> ARCHIVES_DIR/entites/
                                 ├ wikidata.py   Wikidata + Commons (QID coureurs, lignées d'équipes, images sous licence) -> ARCHIVES_DIR/entites/wikidata/ (cache)
                                 ├ riders.py     fiches coureurs (palmarès de la saison, 3 meilleurs résultats par points UCI)
                                 ├ uci_ranking.py classement UCI (pages iframe publiques DataRide, une fois par jour ; moments et instantanés historiques, E1c)
                                 └ agents_flash.py dossier factuel → Gemini rédacteur → contrôleur, repli
                 └ notify.py (ntfy)
run_pipeline.py --archive 2011-2025 ── collector.run_archive (lancé depuis le dépôt d'archives : rotation calendrier -> archives, puis saisons passées -> ARCHIVES_DIR, voir ci-dessous)
netutil.py : HTTP poli commun (pause par hôte, UA honnête, abandon d'un hôte sur 403/429/challenge)
index.html : page unique (CSS + JS inline)
```

Fichiers publiés (`data/`, écrits uniquement par le pipeline ; schéma : `docs/SPEC.md` §4) : `seasons.json`
(`current`, `available`), `index-<année>.json` par saison (`index.json` = saison courante), `races/<id>.json`
(`uci-<CompetitionId>`, communs à toutes les saisons, champ `season`), `riders-<année>.json`, `ranking.json`,
`state.json` (interne). Tout fichier n'est réécrit que si son contenu change (hors horodatage) : pas de commit vide.

- **Archives** (dépôt dédié **Camelbaggy/courses-cyclistes-archives**, public, GitHub Pages sur main / racine,
  `https://camelbaggy.github.io/courses-cyclistes-archives/data/archives/` ; `docs/PLAN_ARCHIVES.md`, `docs/SPEC.md` §4.4).
  Les archives (saisons passées) ne sont plus dans ce dépôt (`data/archives/` n'existe plus ici, hors le jeu fictif
  `tools/fixtures/data/archives/`). Ce dépôt garde tout le **code** et la doc ; l'autre ne contient que des données
  générées (son CLAUDE.md le rappelle). `run_pipeline.py --archive SAISONS` (`collector.run_archive`) collecte les saisons
  passées de la plus récente à la plus ancienne, sans ASO, récits ni Gemini (résumés de repli), pas de notification, pause
  de 2 s sur DataRide. Fichiers compactés (`compact_race` : clés null supprimées, annexes limitées au top 30 sauf dernière
  étape) dans `ARCHIVES_DIR/<année>/` (`races/`, `index.json`, `riders.json`, `ranking.json`, `state.json`) ;
  `collector.ARCHIVES_DIR` = variable d'environnement `ARCHIVES_DIR`, sinon `data/archives/` du dossier courant (essais
  locaux). Les alias (`alias_courses.json`, `alias_coureurs.json`) se lisent à côté du code (`RACINE`), pas du cwd. Une
  saison `complete` n'est jamais recollectée en entier (aucune requête, sauf révision des temps ci-dessous).
  **Workflow `archives.yml` : dans le dépôt d'archives** (plus ici). Cron nocturne `23 0-5 * * *`, entrée `saisons`,
  variable `ARCHIVES_SAISONS`, défaut **2011-2025** (run_archive ignore les saisons complètes : T2 2016-2020 se termine, puis T3
  2011-2015 enchaîne ; une relance automatique sans saisons saisies repart du défaut), groupe `archives-data`, `cancel-in-progress: false`. Il checkout le dépôt d'archives dans
  `archives/` et ce dépôt (main) dans `code/`, puis lance
  `cd code && ARCHIVES_DIR=$GITHUB_WORKSPACE/archives/data/archives python run_pipeline.py --archive "$SAISONS" --budget-min 50`
  (le `data/` de `code/` n'est lu que pour la rotation ; le workflow prend le code de `main` : fusionner ici avant de relancer là-bas) et commit `data/` du dépôt d'archives (boucle de 5 essais
  `pull --rebase -X theirs` + `push`, attente aléatoire 5-20 s, échec explicite). **Auto-relance** : après le commit, si
  une saison demandée n'est pas `complete` (`archives/data/archives/<année>/state.json`, `parse_saisons` importé de
  `code/`), le workflow se relance (`gh workflow run`, `permissions: actions: write`) sauf entre 11 h et 23 h UTC (créneau
  d'`update.yml` : limite la charge sur DataRide pendant les courses) et si le passage n'a rien changé (pas de boucle sans
  progrès) ; le cron n'est qu'une amorce (GitHub le saute souvent). Budget 50 min (timeout 60). **Recollecte ciblée** :
  `collector.archive_a_recollecter` rouvre une course
  archivée dont un classement `stage` / `gc` (étape route ou CLM individuel, ou final) a une ligne classée sans `time_s`,
  une seule fois (marque `_temps_v` = `TEMPS_VERSION`, 3 aujourd'hui ; l'incrémenter si `parse_duree` ou la lecture des
  statuts change). **Révision des saisons complètes** : `run_archive` parcourt en local les fiches d'une saison `complete`
  (`a_reviser_saison` : `_temps_v` < `TEMPS_VERSION` ET `archive_a_recollecter`) ; aucune requête s'il n'y en a pas ; sinon
  chaque fiche est recollectée (`comp_depuis_fiche`, même catégorie / raison / saison, marquée `_temps_v` même si des valeurs
  restent illisibles : pas de boucle), puis `index.json` réécrit ; `riders.json` / `ranking.json` inchangés, la saison reste
  `complete` ; budget et `--max-races` respectés ; log `[ARCHIVES] <année> : révision des temps, N course(s) recollectée(s)`.
  Une recollecte incomplète laisse la fiche telle quelle. La révision ne déclenche pas l'auto-relance (qui ne regarde que
  les saisons non complètes) : le cron nocturne la poursuit. Les courses du Calendrier (`data/races`) profitent des
  nouveaux formats par la recollecte normale (≤ 3 jours après la fin) ; l'historique de la saison courante n'est pas recollecté. **Formats de temps** (`uci.parse_duree`) : `H:MM:SS`, `MM:SS.cc`, `SS`,
  `04h54'18''` (apostrophes droites ou ’ ′, `"` ″ pour les secondes), `54'18''`, `18''`, `H M S` séparés par des
  espaces (`3 15  6`), `H.MM.SS` / `H,MM,SS` / `H;MM;SS` (un seul séparateur homogène, MM et SS sur 2 chiffres),
  `4h35'42` (sans marque finale), `6'01''620` (millièmes), guillemets / apostrophes parasites autour d'un `H:MM:SS`
  (`16:46:00"`, `'03:55:33`) ; minutes et secondes < 60 ; tout autre format (`4::37:02`, `0:44:53:984`, `4:57:265`…) reste `None` (compté, une ligne de synthèse par course). **Statuts dans ResultValue** : si `Irm` est vide et que `ResultValue` vaut
  (casse et espaces ignorés) un code de `IRM_STATUTS` (DNF, DNS, OTL, DSQ, LAP…), c'est le statut (ni temps ni illisible) ;
  `REC` / `REL` : rang conservé, pas de temps. **Push d'`update.yml`** : boucle de 5 essais `pull --rebase -X theirs` +
  `push`, attente aléatoire 5-20 s, échec explicite ; checkout complet (plus de sparse-checkout : ce dépôt n'a plus
  d'archives). Essai réseau : `[essai:archives_collecte]`. `selection.py` range `1.HC`/`2.HC`
  en Pro et les classes 2009-2010 (`1.CH`, `2.CH`, `CPE`, `AU1`, `MNM`) en WT (libellé `uci_class` inchangé).
- **Rotation calendrier -> archives** (scindée entre les deux dépôts) : une saison S quitte le Calendrier
  (`seasons.json.available`) quand S+1 est terminée, soit quand la date du jour dépasse de plus de 14 jours la fin de la
  dernière course (`end_date`, à défaut `start_date`, des courses et des `upcoming` de `data/index-<S+1>.json`) ; une
  course à venir future, un index de S+1 absent ou vide : pas de rotation (exemple : 2026 part ~2 semaines après la
  dernière course de 2027). Règle pure `collector.saisons_a_archiver`, utilisée par les deux côtés :
  (a) **dépôt d'archives** : `collector.migrer_saisons_anciennes` (début de `run_archive`, donc par archives.yml, qui lit le
  `data/` de `code/` en lecture seule) écrit l'archive de S (courses compactées, `index.json`, classement de fin de saison,
  `riders.json`, `state.json` complete) et **ne supprime plus rien** dans `data/` (une suppression faite là-bas ne serait
  jamais poussée) ; une saison déjà migrée est ignorée ensuite ; (b) **ce dépôt** : `write_season_indexes` (update.yml)
  ne liste plus S ni ne la réécrit, puis, s'il reste des fichiers de S, lit **une fois par passage** l'index public
  `collector.ARCHIVES_INDEX_URL` (`https://raw.githubusercontent.com/Camelbaggy/courses-cyclistes-archives/main/data/archives/index.json`,
  `charger_index_archives`, échec réseau = rien supprimé) et `collector.retirer_saisons_archivees` supprime
  `data/races/<id>.json`, `data/index-<S>.json`, `data/riders-<S>.json` seulement si S y figure avec `complete: true`
  (log `[ROTATION] saison S archivée dans courses-cyclistes-archives : fichiers retirés de data/`). Tests sans réseau
  (index injecté) dans `collector.py --test`. Une saison reste donc quelques passages dans `data/` après sa sortie du
  Calendrier, le temps que l'archive soit publiée.
- **Encyclopédie, socle de données (E1a, `encyclopedie.py`, `docs/PLAN_ENCYCLOPEDIE.md`)** : `collector.write_archives_index`
  (donc chaque passage d'archives.yml, qui a les archives ET le `data/` du dépôt principal) appelle `write_entites` ->
  `encyclopedie.construire(ARCHIVES_DIR, DATA_DIR)` (échec journalisé, jamais bloquant). Lit TOUTES les saisons (archives +
  Calendrier), course par course (~120 Mo de mémoire, ~8 s pour 2019-2027), applique `alias_coureurs.json` / `alias_courses.json` et
  écrit `ARCHIVES_DIR/entites/` (`_dump_if_changed`, ordre déterministe, fichiers devenus inutiles supprimés) :
  `coureurs/<lettre>.json`, `equipes/<année>.json` + `equipes/index.json`, `courses/<lettre>.json`, `saisons/<année>.json`,
  `pays.json`, `recherche/<lettre>.json`, `index.json` (schéma : `docs/SPEC.md` §4.5). Points à préserver : statistiques par saison
  recalculées avec `riders._agreger` course par course (mêmes définitions que `riders.json`, qui peut être en retard sur les fiches après
  une révision des temps : `rapport["coherence"]`) ; équipe-saison = `<slug du libellé>-<année>` (casse / accents / ponctuation fusionnés) ;
  sélection nationale = libellé égal au nom d'un pays (`PAYS_NOMS`) ET tous ses coureurs de la saison de ce pays (`_est_nationale`) ;
  équipe principale d'un coureur = équipe de marque aux plus nombreux jours de course ; grands tours = clés d'édition EXACTES
  (`GRANDS_TOURS`, `CLASSES_GRAND_TOUR`), jamais de motif flou ; `code_uci` d'une équipe-saison = `TeamCode` unique des coureurs classés de la saison au même libellé (slug), plusieurs codes : absent + anomalie `code_uci_multiple`. Tests :
  `python encyclopedie.py --test` ; génération manuelle : `python encyclopedie.py <archives_dir> <data_dir> [--sortie DIR]` (jamais dans un
  dépôt de données hors workflow). Le jeu fictif `tools/fixtures/data/archives/entites/` est produit par `generer_archives.py`.
- **Encyclopédie, Wikidata (E1b, `wikidata.py`)** : `uci_ranking._normaliser` conserve `team_code` ; `run_archive` relit UNE FOIS le classement de fin
  de chaque saison `complete` dont `ranking.json` n'a aucune clé `team_code` (`collector.relire_classement`, ranking.json seul réécrit, riders.json
  intact, `team_code_relu` dans state.json, log `[ARCHIVES] <année> : classement relu (codes d'équipe)`, budget respecté).
  `python run_pipeline.py --wikidata --budget-min N` (workflow DÉDIÉ du dépôt d'archives, ~300 min au premier remplissage puis hebdomadaire) lance
  `wikidata.run_wikidata` : équipes (≤ 50 % du budget), lignées, puis coureurs du plus notable au moins notable ; n'écrit QUE
  `ARCHIVES_DIR/entites/wikidata/` (`coureurs`, `equipes`, `lignees`, `images`, `libelles` .json, cache écrit tous les 200 coureurs et à chaque lot
  d'équipes : un timeout ne perd rien, reprise immédiate) et n'appelle PAS `write_entites` (`--entites` le fait à la main ; sinon c'est le passage
  nocturne d'archives.yml qui reconstruit `entites/` en lisant le cache). 1 requête/s par hôte (wikidata.org, commons.wikimedia.org), 1 recherche par
  coureur + `wbgetentities` / Commons par lots de 50, pas de `maxlag`, abandon de l'hôte sur 403/429 (`HoteAbandonne`, cache conservé). Règles de
  rapprochement (strictes, voir la docstring) : coureur = UN SEUL candidat vérifié (date de naissance P569 à précision jour ÉGALE + nom concordant
  + occupation cycliste P106 = Q2309784 ou sous-classe P279), sans date de naissance jamais rapproché ; équipe-saison = code P1998 daté contenant la
  saison + nom P1448 daté ou élément saison de l'année concordant + un seul parent ; sinon `null` (re-tenté après 60 jours ; correspondances
  re-vérifiées après 180 jours) ou `alias_equipes.json` (manuel, `{"id équipe-saison": "QID"}`). Image : licence Commons lisible obligatoire.
  **Précisions du 1er passage réel** : le cache coureurs garde `naissance` (P569, AAAA-MM-JJ ; les anciennes entrées sans ce champ restent valides) ;
  équipes : filtre des classes P31 féminines (women / féminin / femmes), puis désambiguïsation « développement / réserve / U23 / continental »
  seulement si exactement un parent de premier niveau (WorldTeam / ProTeam) reste, sinon `ambigu` ; `preuve` = `code+nom` (+ `detail` lisible) ou
  `code+periode` (plus faible : UN SEUL parent porte le code sur une période à borne explicite, nom non concordant ; jamais utilisée si plusieurs
  parents `code+nom` restent) ; `regle` = `REGLE_EQUIPES` (2) dans chaque entrée : une entrée `null` sans `regle` ou de version plus ancienne est
  re-tentée au passage suivant (incrémenter `REGLE_EQUIPES` quand les règles changent) ; journal `[WIKIDATA] en cours : X/Y coureurs, Z requêtes, T min`
  toutes les 5 min + synthèse avec requêtes/min ; licences sans lien (« Public domain ») conservées (`licence` sans `licence_url`).
  `encyclopedie.construire` lit le cache (champ `wikidata` des coureurs, `lignee` des équipes-saisons, `equipes/lignees.json`, entrées de recherche
  `t: "l"`). Jeu fictif : `tools/fixtures/generer_archives.py` (`entites/wikidata/`). Non testé en réel : voir PLAN_ENCYCLOPEDIE (E1b).
- **Encyclopédie, historique du classement UCI (E1c, `uci_ranking` + `collector.collecter_classements`)** : `run_archive` appelle, APRÈS la collecte
  des courses et avec le budget restant (pas avec `--only`), `collecter_classements(saisons demandées + saisons du Calendrier `data/seasons.json`)`, de
  la plus récente à la plus ancienne. Par saison : `uci_ranking.contexte_classement` (World Ranking, à défaut « WorldTour Ranking » groupe 3 : saisons
  anciennes), `list_moments` (`GetRankingMoments`, entrée « Most Recent » Id 0 ignorée, moments postérieurs à aujourd'hui écartés), puis
  `choisir_instantanes` (fonction PURE : dernier moment de chaque mois civil FINI + premier moment STRICTEMENT postérieur à la fin de chaque course
  WorldTour, `selection.categorie_classe == "WT"` ; dimanche -> mardi suivant, mardi -> mardi d'après ; raisons « fin de mois » / « après <course> »).
  Liste des courses : `<année>/index.json` d'archive COMPLET, sinon `data/index-<année>.json`, sinon DataRide. Stockage
  `ARCHIVES_DIR/entites/classements/<année>/<AAAA-MM-JJ>.json` = `{date, nom, moment_id, raisons, lignes: [[rang, rider_id, points, team_code]]}` (500 premières
  lignes + tous les FRA au-delà ; `rider_id` = `uci_ranking.rider_key`, null sans date de naissance) + `index.json` `[{date, raisons, fichier}]` (liste des
  fichiers présents ; seul lui suit les raisons si elles changent) + `etat.json` `{complet: true}` (saison close depuis > 7 j, liste des courses d'archive
  ou DataRide, ou > 30 j via le Calendrier, tout écrit : plus AUCUNE requête). **Un instantané écrit n'est jamais relu ni réécrit** (instantanés récents
  d'abord, budget vérifié avant chaque lecture, reprise au passage suivant). Journal `[CLASSEMENT] <année> : N instantanés écrits, M restants`. Une saison
  en cours coûte ~3 requêtes de cadrage + 4 par nouvel instantané ; le premier remplissage (~1 600 requêtes, ~12 Mo) s'étale sur plusieurs passages nocturnes
  (l'auto-relance d'archives.yml ne regarde que les saisons non `complete` : le cron nocturne termine l'historique). `encyclopedie.construire` lit ces
  fichiers (jamais ne les écrit) : champ `historique_uci` `[[date, rang]]` trié des coureurs (alias appliqués saison par saison) et `instantanes_uci` des
  `saisons/<année>.json`. Essai réseau : `[essai:classement_historique]` (forme exacte de `GetRankingMoments` à confirmer au premier passage réel).
- **Éditions et carrières** (`write_archives_index`, donc chaque passage d'archives.yml, `_dump_if_changed`) :
  `editions.json` (dans `ARCHIVES_DIR` ; éditions d'une même course, clé = `collector.cle_edition(nom, pays)` : minuscules, sans accents ni
  ponctuation ni année / numéro d'édition, + `|PAYS` ; rapprochement EXACT, jamais flou) et `carrieres/<lettre>.json`
  + `carrieres/index.json` (saisons d'un coureur, par `rider_id` exact). Alias MANUELS à la racine de CE dépôt (code) : `alias_courses.json`
  (`{"clé": "clé canonique"}`, changements de nom de course) et `alias_coureurs.json` (`{"rider_id": "rider_id canonique"}`), `{}` au
  départ, jamais devinés (une modification se publie au passage d'archives.yml suivant). `cleEdition` (index.html) DOIT rester alignée avec `cle_edition` ; tests dans `collector.py --test`.
- `data/races/<id>.json` sont conservés d'un passage à l'autre ; seules les courses nouvelles, en cours, terminées
  depuis ≤ 3 jours ou incomplètes sont recollectées. `data/state.json` : étapes déjà notifiées (`<race_id>:<n|F>`),
  décisions « Français dans le top 10 » des .1/.2 étrangères (mémorisées, sondées une seule fois).
- Budget de temps (`--budget-min`, 40 min par défaut) : au-delà, la collecte s'arrête proprement (courses les plus
  récentes traitées d'abord) et reprend au passage suivant. Le premier rattrapage d'une saison prend ~3 passages.
- Saison : bornes officielles UCI (`uci.season_bounds` / `season_for`). Intersaison (nouvelle saison commencée sans
  course WT / Pro / FDJ courue, novembre-janvier) : la saison précédente reste `current`, la nouvelle est aussi
  collectée et proposée dans le Calendrier. Courses à venir réparties par saison. Aucune action au changement d'année.
- Gemini seulement pour les étapes des 3 derniers jours ; repli déterministe pour l'historique. Pas de push pour
  un rattrapage (nouveautés de plus de 2 jours).

## Sources : règles et pièges vérifiés

- **Exclues** : ProCyclingStats et FirstCycling (CGU/robots.txt interdisent, Cloudflare). Ne pas les réintroduire.
  Aucun contournement anti-robot (pas de faux navigateur, pas de jeton récupéré dans une page).
- **ASO et DirectVélo** : accord du propriétaire du projet. Respecter quand même robots.txt (ASO interdit `/api`,
  `/graphql`, `/*/ajax`) et le Crawl-delay de DirectVélo.
- **UCI DataRide** (`dataride.uci.org/iframe/...`) : `Competitions` exige les 3 filtres Kendo (RaceTypeId,
  CategoryId=22 hommes élite, SeasonId) sinon page HTML d'erreur en HTTP 200 ; ne liste que les courses **déjà
  courues** (pas de calendrier à venir) ; saison UCI = mi-octobre → mi-octobre (2026 = id 464, 2027 = 477).
  `ResultValue` hétérogène : « +0 »/« +00 »/« s.t. » = même temps que la ligne **précédente**. Pas d'identifiant
  coureur : `rider_id` = slug du nom + date de naissance. Pas de classement par équipes ni de villes d'étape.
  La dernière étape n'a souvent que « Stage Classification » : gc/points/… recopiés du classement final.
- Classement UCI : `RankingsDiscipline` + `ObjectRankings` (mêmes filtres Kendo obligatoires, 1000 lignes par page,
  date de naissance présente → rapprochement fiable avec `rider_id`). Recalculé le mardi par l'UCI.
- Le calendrier prévisionnel d'uci.org passe par une API privée (jeton Bearer dans la page) : **ne pas l'utiliser**.
  cyclingflash.com : challenge Cloudflare sur tout le site (même robots.txt) : écarté. Calendrier à venir =
  Wikipédia (crédit CC BY-SA en pied de page) ; les pages ProSeries / Europe Tour de la saison suivante n'existent
  souvent qu'à partir de l'hiver : le calendrier se remplit tout seul quand elles paraissent.
- Sites ASO : seule l'édition courante est servie (le Tour passe à l'année suivante dès l'automne) ;
  `aso.match_race` vérifie l'année.
- Cyclingnews RSS : texte intégral donné à l'IA uniquement, jamais republié.

## Interface (`index.html`)

Page autonome sans dépendance, thème sombre unique (comme le dashboard des Coupes d'Europe), drapeaux flagcdn.com ;
toute donnée insérée passe par `esc()`. Mobile ~390 px. Onglets : Récents · Calendrier (un sous-onglet par saison de
`seasons.json.available`, Résultats / À venir, filtres de catégorie) · Classements (UCI, FDJ Series) · Français
(triés par rang UCI, 3 meilleurs résultats) · Archives (menu déroulant des saisons de `index.json` du dépôt d'archives, lien
`?archive=AAAA`, chargement paresseux : classement UCI de fin de saison, victoires françaises, liste des courses ;
fiche course lue dans `<année>/races/` des archives (encart repliable « Éditions précédentes » : `editions.json` + saisons du Calendrier), fiche
  coureur : nouvelle fiche E2, voir ci-dessous ; jamais de repli
vers une autre saison d'archive pour l'onglet Saison ; les clés null sont absentes des archives, la page traite absent = null ; anciennes classes
HC / CH / CPE / AU1 / MNM : libellé d'origine + info-bulle d'équivalence). Routes : fiche course `#course/<id>/<étape|F>`, coureur `#coureur/<id>`, recherche `#recherche/<texte>` (les `#equipe`, `#saison`… viendront avec E3-E5). `?data=<dossier relatif>`
change le dossier de données (`tools/fixtures/data` : jeu fictif, deux saisons + `archives/` fictives, régénérables par `tools/fixtures/generer_archives.py`) ; `?saison=AAAA`. **Base des archives** (`BASE_ARCHIVES`) : `?archives=<url https ou dossier relatif>` s'il est donné ; sinon, si `?data=` est donné (jeu d'essai), `<data>/archives` en local ; sinon `https://camelbaggy.github.io/courses-cyclistes-archives/data/archives` (GitHub Pages, `Access-Control-Allow-Origin: *`, fetch cross-origin, `cache: no-cache`). Toute lecture d'archive passe par `chargerArchive(chemin)` (chemin relatif aux archives ; `charger` route aussi les chemins `archives/…`) ; site injoignable : message « Le site des archives est injoignable » + bouton Réessayer. Vérifier le rendu
avec `tools/apercu.py` (option `--nav` sur les données réelles) après toute modification.

### Design et composants (E2, plan encyclopédie)

Jetons CSS sur `:root` (thème sombre unique, ne pas coder de couleur en dur) : surfaces `--bg` / `--s1` / `--s2` / `--s3`, bordure `--line`, texte `--tx` / `--tx2` / `--tx3`,
accent `--accent`, catégories `--c-wt` / `--c-pro` / `--c-fdj` / `--c-1` / `--c-2` / `--c-ch` (badges `cat-WT`, `cat-1`…, texte blanc, contraste AA), maillots `--jaune`…, espacements `--sp1..6`
(4/8/12/16/24/32), rayons `--r1` 8 / `--r2` 14, ombres `--sh1/2`, `--bar-h` (barre des fiches). Les anciens noms (`--card`, `--elev`, `--border`, `--muted`…) sont des alias. Chiffres tabulaires dans les tableaux.
Composants (fonctions JS + classes) : `htmlHero` / `.hero` (photo ronde ou initiales, crédit, puces, `.facts`), `htmlTuiles` / `.kpis` (2 colonnes à 390 px, une valeur absente = pas de tuile),
`htmlOnglets` / `.subtabs.sticky` (défilables, collants sous la barre), `htmlTableau` / `.tbl-wrap` (défilement horizontal, 1re colonne figée), `.res` (résultat en carte), `sparkRang` (SVG, rang 1 en haut),
`squeletteCoureur` / `.sk` (chargement), `htmlVide` / `.vide`, badges `catBadge`. À 880 px et plus, la fiche coureur passe en deux colonnes (infobox `.rside` à droite, collante).
**Recherche globale** : icône dans l'en-tête, panneau plein écran `#search`, route `#recherche/<texte>` (la saisie met le hash à jour par `replaceState`) ; `normIdx` = `netutil.normalize` (à garder alignée),
fichier `entites/recherche/<lettre>.json` de la 1re lettre du mot le plus long, mis en cache ; chaque mot saisi doit être préfixe d'un mot du libellé ; groupes Coureurs / Équipes et lignées / Courses
(8 par groupe) ; flèches + Entrée ; coureur -> `#coureur/<id>`, course -> dernière édition `#course/<race_id>` (E3 : page série) ; équipes et lignées : texte non cliquable (E4).
**Fiche coureur** (`construireCoureur`) : `entites/coureurs/<lettre>.json` (alias de `carrieres/index.json` si l'id est un alias), `riders-<année>.json` du Calendrier fusionnés par `fusionCalendrier`
(seulement si plus récents que `entites/index.json.generated_at`, ou saison absente : rang UCI marqué `*`), `entites/pays.json`, `entites/courses/<lettre>.json` (noms des courses du palmarès) et la fiche
de la saison du contexte (`data-rctx`, onglet « Saison en cours » / « Saison AAAA », absent si non publiée). Onglets affichés seulement s'ils ont des données : Aperçu · Palmarès · Saisons ·
Grands tours · Classement UCI · Parcours (équipes de nos données + frise Wikidata P54 à la précision de la source) · Saison. Photo : `wikidata.image` avec auteur / licence liés à la page Commons ;
aucune ligne pour une valeur absente. `tools/apercu.py` couvre fiche (chaque onglet), recherche, 1024 px.
