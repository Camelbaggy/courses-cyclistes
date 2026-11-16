# Avancement du projet (point de reprise)

Dernière mise à jour : 16 novembre 2026. À lire avec `CLAUDE.md` (règles, architecture), `docs/PLAN_ENCYCLOPEDIE.md`
(plan et étapes), `docs/PLAN_ARCHIVES.md`, `docs/SPEC.md` (schémas) et `docs/recherche/` (sondes et décisions).

## Où on en est

**Le site est devenu une encyclopédie à la Liquipedia** (https://camelbaggy.github.io/courses-cyclistes/) :
- Menu Accueil · Courses · Équipes · Coureurs · Classements (barre en bas sur mobile), recherche globale, vraies pages par
  route, gabarit d'article (fil d'Ariane, infobox, onglets, navbox). Accueil = portail (derniers résultats, à venir, top 10
  UCI, Français à la une, « ce jour-là »).
- Articles coureur (portrait cadré sur le visage, palmarès, saisons, grands tours, classement UCI, parcours), épreuve
  (palmarès UCI + historique Wikidata depuis l'origine, records), édition (podium, participants, pays).
- **En cours (R2b, branche `ccr-6eb51b68-vzkhg2`, non fusionné)** : articles d'équipe (`#equipe/<QID>` lignée et
  `#equipe/<id équipe-saison>`), équipes cliquables partout, miroir JS de `netutil.slugify`, et **frise « Équipes » de la
  fiche coureur simplifiée** demandée par le propriétaire : une ligne par équipe « Nom · 2019–2022 », années seulement,
  sources fusionnées (périodes Wikidata + nos saisons), sélections nationales à part. Agent interrompu (limite d'API) : travail partiel committé sur la branche, à reprendre et vérifier (captures 390/1024 px,
  Movistar `#equipe/Q6175`, Merlier onglet Parcours) puis PR + fusion.

**Données** (dépôt d'archives `Camelbaggy/courses-cyclistes-archives`, Pages) :
- Saisons UCI archivées : 2018-2025 complètes, 2017 partielle, 2016 puis T3 2011-2015 à venir (archives.yml nocturne,
  défaut 2011-2025, relance automatique hors 11 h-23 h UTC). Calendrier : 2026, 2027.
- `entites/` régénéré à chaque passage d'archives : coureurs, équipes-saisons, lignées, épreuves, saisons, pays, recherche,
  index des listes, historique UCI (instantanés fin de mois + après chaque course WT ; 8 min réservées par passage).
- Wikidata (`wikidata.yml`, dimanche + manuel) : 7 508 coureurs rapprochés, 969 équipes-saisons rattachées ; règle
  équipes v3 (équipes féminines écartées : Cofidis 2022-2024 sera re-vérifié au prochain passage). Historique des
  épreuves (`--historique`) : 39 séries prouvées, 3 017 éditions, coureurs historiques `wd-Q…`.
- Corrections documentées : `corrections_coureurs.json` (7 dates, 2 nationalités) ; alias : `alias_coureurs.json`
  (9 doublons dont 5 fusions même saison), `alias_courses.json` (18 libellés renommés, preuve Wikidata).

## Décisions du propriétaire à retenir

- Zéro hallucination ; corrections de source seulement avec source citée et validation.
- Tout le peloton ; Wikipédia en source de texte principale (plusieurs langues), Gemini en dernier recours ; textes courts.
- Design moderne, mobile d'abord, thème sombre ; **simplicité** : pas de lignes redondantes (« Dans nos données »
  supprimé), pas de liens en doublon (« Toutes les éditions » sous le palmarès supprimé), listes simples.
- Claude fusionne lui-même ses PR après vérification ; code et opérations délégués à des agents Sonnet.
- Environnement « dashboards-sport » : accès web libre.
- WorldDB (base PCM) : contrôle croisé seulement, jamais publiée, gardée hors des dépôts.
- cyclingdb.com : réutilisation interdite sans autorisation écrite ; demande rédigée (à envoyer par le propriétaire).

## Prochaines étapes

1. Finir R2b (voir ci-dessus) et fusionner.
2. R3 : pages Saison (`#saison/<année>`), navbox partout, finitions ; « ce jour-là » plus riche.
3. Textes d'introduction Wikipédia (fr d'abord, synthèse multilingue courte) pour coureurs, équipes, épreuves.
4. Étendre l'historique Wikidata aux ~150 autres épreuves suivies (`historique.py --proposer`, même preuve).
5. Lignées d'équipes manquantes (ex. Groupama-FDJ seulement 2018 rattachée) : re-vérification Wikidata v3, puis
   propositions d'équivalences (outil `tools/audit_worlddb.py`, `equipes_propositions.md`) à faire valider.
6. Doublons de coureurs restants (`doublons_possibles` dans le rapport d'`encyclopedie`, ex. Aranburu) : vérifier puis alias.
7. Surveiller `update.yml` (GitHub saute des crons) avant la reprise des courses ; relance automatique si besoin.

## Suivi automatique

- Bilan programmé le 17/11 à 11 h 20 UTC (avancement archives, contrôle des vainqueurs 2016-2017, instantanés UCI,
  re-vérification Cofidis, historique dans `entites/index.json`).
