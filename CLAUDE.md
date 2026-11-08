# CLAUDE.md

Guide pour Claude Code dans ce dépôt.

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
python uci.py && python selection.py                  # tests locaux sans réseau (assert)
AI_BUDGET_SECONDS=0 python tools/essais/essai_ia.py   # dossier, repli, notification sur tools/fixtures_ia
python tools/apercu.py <dossier> [--data tools/fixtures/data] [--sombre]   # captures 390 px (Playwright)
python -m py_compile *.py tools/*/*.py                # contrôle statique
```

`AI_BUDGET_SECONDS=0` ou pas de `GEMINI_API_KEY` : résumés de repli déterministes.

### Tester sur de vraies données

Le conteneur de développement n'a pas accès aux sources ; GitHub Actions oui. Sur une branche `ccr-*` :
- commit contenant `[essai:<nom>]` → `tools/essais/essai_<nom>.py` (workflow `essais.yml`, sans commit) ;
- commit contenant `[pipeline]` → pipeline complet, données **committées sur la branche**
  (`pipeline_branche.yml` ; options `[avec-ia]`, `[saison:2026]`, `[max:N]`) ; puis `git pull` et
  `tools/inspect_data.py` / `tools/apercu.py --data data` en local.
Lire les logs avec les outils GitHub MCP. `update.yml` (horaire, 13 h–22 h UTC + 6 h 41) commit `data/` sur `main` :
une branche de travail se retrouve vite derrière `main` ; ne pas committer `data/` à la main sur `main`.

## Architecture

```
run_pipeline.py ── collector.py ─┬ uci.py        source principale : DataRide (résultats, classes, saisons)
                                 ├ selection.py  courses suivies (classe, FDJ, France, Français top 10)
                                 ├ lnc.py        FDJ United Series (ex-Coupe de France)
                                 ├ aso.py        enrichissement ASO (bonifs, équipes, parcours, récits)
                                 ├ directvelo.py récits des courses françaises (Crawl-delay 10 s)
                                 ├ cyclingnews.py récits (RSS, ~3 jours de profondeur)
                                 └ agents_flash.py dossier factuel → Gemini rédacteur → contrôleur, repli
                 └ notify.py (ntfy)
netutil.py : HTTP poli commun (pause par hôte, UA honnête, abandon d'un hôte sur 403/429/challenge)
index.html : page unique (CSS + JS inline), lit data/index.json puis data/races/<id>.json
```

- `data/races/<id>.json` sont conservés d'un passage à l'autre ; seules les courses nouvelles, en cours, terminées
  depuis ≤ 3 jours ou incomplètes sont recollectées. `data/state.json` : étapes déjà notifiées (`<race_id>:<n|F>`),
  décisions « Français dans le top 10 » des .1/.2 étrangères (mémorisées, sondées une seule fois).
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
- Le calendrier prévisionnel d'uci.org passe par une API privée (jeton Bearer dans la page) : **ne pas l'utiliser**.
- Sites ASO : seule l'édition courante est servie (le Tour passe à l'année suivante dès l'automne) ;
  `aso.match_race` vérifie l'année.
- Cyclingnews RSS : texte intégral donné à l'IA uniquement, jamais republié.

## Interface (`index.html`)

Page autonome sans dépendance (drapeaux flagcdn.com) ; toute donnée insérée passe par `esc()`. Mobile ~390 px.
`?data=<dossier relatif>` change le dossier de données (`tools/fixtures/data` : jeu fictif). Hash
`#course/<id>/<étape|F>`. Vérifier le rendu avec `tools/apercu.py` après toute modification.
