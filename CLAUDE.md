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
python tools/apercu.py <dossier> [--data tools/fixtures/data] [--sombre]   # captures 390 px (Playwright)
python run_pipeline.py --archive 2023 --max-races 5  # mode archives (écrit dans data/archives/ : à supprimer ensuite)
python collector.py --test                            # tests locaux de compact_race (sans réseau)
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
                                 ├ riders.py     fiches coureurs (palmarès de la saison, 3 meilleurs résultats par points UCI)
                                 ├ uci_ranking.py classement UCI (pages iframe publiques DataRide, une fois par jour)
                                 └ agents_flash.py dossier factuel → Gemini rédacteur → contrôleur, repli
                 └ notify.py (ntfy)
run_pipeline.py --archive 2021-2025 ── collector.run_archive (saisons passées -> data/archives/, voir ci-dessous)
netutil.py : HTTP poli commun (pause par hôte, UA honnête, abandon d'un hôte sur 403/429/challenge)
index.html : page unique (CSS + JS inline)
```

Fichiers publiés (`data/`, écrits uniquement par le pipeline ; schéma : `docs/SPEC.md` §4) : `seasons.json`
(`current`, `available`), `index-<année>.json` par saison (`index.json` = saison courante), `races/<id>.json`
(`uci-<CompetitionId>`, communs à toutes les saisons, champ `season`), `riders-<année>.json`, `ranking.json`,
`state.json` (interne). Tout fichier n'est réécrit que si son contenu change (hors horodatage) : pas de commit vide.

- **Archives** (`data/archives/`, `docs/PLAN_ARCHIVES.md`, `docs/SPEC.md` §4.4) : `run_pipeline.py --archive SAISONS`
  (`collector.run_archive`) collecte les saisons passées de la plus récente à la plus ancienne, sans ASO, récits ni
  Gemini (résumés de repli), pas de notification, pause de 2 s sur DataRide. Fichiers compactés (`compact_race` :
  clés null supprimées, annexes limitées au top 30 sauf dernière étape) dans `data/archives/<année>/` (`races/`,
  `index.json`, `riders.json`, `ranking.json`, `state.json`) ; une saison `complete` n'est plus jamais recollectée
  (aucune requête). Workflow `archives.yml` (cron nocturne `23 0-5 * * *`, entrée `saisons`, variable
  `ARCHIVES_SAISONS`, défaut 2021-2025, même groupe de concurrence que `update.yml`, commit de `data/archives/`
  seulement). `update.yml` fait un checkout partiel (sparse-checkout non-cone sans `data/archives/`) : ne jamais y
  écrire ni y committer d'archives. Essai réseau : `[essai:archives_collecte]`. `selection.py` range `1.HC`/`2.HC`
  en Pro et les classes 2009-2010 (`1.CH`, `2.CH`, `CPE`, `AU1`, `MNM`) en WT (libellé `uci_class` inchangé).
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
toute donnée insérée passe par `esc()`. Mobile ~390 px. Onglets : Récents · Calendrier (un sous-onglet par saison,
Résultats / À venir, filtres de catégorie) · Classements (UCI, FDJ Series) · Français (triés par rang UCI, 3
meilleurs résultats). Fiches course `#course/<id>/<étape|F>` et coureur `#coureur/<id>`. `?data=<dossier relatif>`
change le dossier de données (`tools/fixtures/data` : jeu fictif, deux saisons) ; `?saison=AAAA`. Vérifier le rendu
avec `tools/apercu.py` (option `--nav` sur les données réelles) après toute modification.
