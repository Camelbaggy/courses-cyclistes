# Avancement du projet (point de reprise)

Dernière mise à jour : 17 novembre 2026, 2 h UTC. À lire avec `CLAUDE.md` (règles, architecture), `docs/PLAN_ENCYCLOPEDIE.md`
(plan et étapes), `docs/PLAN_ARCHIVES.md`, `docs/SPEC.md` (schémas) et `docs/recherche/` (sondes et décisions).

## Où on en est

**Site : encyclopédie à la Liquipedia** (https://camelbaggy.github.io/courses-cyclistes/), étapes R1 et R2 du plan faites :
- Menu Accueil · Courses · Équipes · Coureurs · Classements (barre en bas sur mobile), recherche globale, une page par route,
  gabarit d'article (fil d'Ariane, infobox, onglets, navbox). Accueil = portail.
- Articles coureur (portrait, palmarès, saisons, grands tours, classement UCI, frise « Équipes » simplifiée), épreuve (palmarès
  UCI + historique Wikidata depuis l'origine, records), édition (podium, participants, pays), équipe (lignée Wikidata avec
  sélecteur de saison, ou équipe-saison seule ; effectif, mouvements, palmarès, grands tours, historique des noms).
- Participants d'une course : cartes d'équipe repliables à la Liquipedia (interrupteur « Effectifs »).
- **Maillots WorldDB** (saison 2025, accord des auteurs, crédit « WorldDB », sources dans le dépôt privé `maillots-pcm`) :
  - équipes : 174 équipes 2025 reliées par code UCI, affichées sur toute la période où l'équipe garde le même nom et le même code
    (participants + infobox de l'article d'équipe) ;
  - maillots distinctifs : 71 courses, toutes leurs dénominations (bloc « Maillots » des fiches de course, infobox des épreuves) ;
  - sélections nationales : tenues des équipes nationales (les fichiers « champion » de WorldDB ne sont PAS des maillots de champion).

**Données** (dépôt d'archives `Camelbaggy/courses-cyclistes-archives`, Pages) :
- Saisons UCI archivées : 2018-2025 complètes, 2017 partielle (122 courses), puis 2016 et 2011-2015 à venir (archives.yml nocturne,
  défaut 2011-2025, relance automatique hors 11 h-23 h UTC). Calendrier : 2026, 2027.
- `entites/` régénéré à chaque passage d'archives (15 727 coureurs, 2 898 équipes-saisons, 328 lignées, 589 épreuves, historique UCI).
- Wikidata (`wikidata.yml`, dimanche + manuel) : 8 380 coureurs rapprochés, 969 équipes-saisons rattachées. Historique des épreuves :
  39 séries prouvées, 2 639 éditions historiques, 2 199 coureurs historiques `wd-Q…`.
- Alias : `alias_courses.json` 56 libellés (18 + 38 le 17/11 pour 32 courses renommées, tous prouvés par une série Wikidata commune et
  des vainqueurs concordants : Saudi Tour -> AlUla Tour, Tour of Britain / OVO / Lloyds, Route du Sud -> Occitanie… ;
  `docs/recherche/historique_avant_2009.md` §11) ; `alias_coureurs.json` 9 doublons ; `alias_coureurs_wikidata.json` 1 rapprochement
  manuel (Cepeda) ; `corrections_coureurs.json` 7 dates, 2 nationalités.
- Rapprochement des noms Wikidata v2 (ß / ø / æ…, second prénom d'un seul côté) : les 6 954 coureurs non reliés seront re-tentés.

## Publication (vérifiée le 17/11 à 3 h 20 UTC)

Passage d'archives lancé à la main à 2 h 12 UTC (les crons de 0 h 23 et 1 h 23 avaient été sautés) : succès, puis relance automatique (en
chaîne jour et nuit pendant l'intersaison). Publiés : articles de lignée (Movistar `#equipe/Q6175`), épreuves regroupées (AlUla Tour
2020-2026, Tour of Britain 2017-2026), 19 logos ; 2017 passe de 122 à 159 courses. En attente du passage suivant (code fusionné après le
début du passage n° 14) : `codes_uci` et `renommee` des équipes-saisons (maillots des équipes renommées en cours de saison).
Passage Wikidata (règle des noms v2, Cepeda) lancé à la main à 2 h 15 UTC : suivi programmé vers 6 h 15 UTC.

## Intersaison (décision du 17/11/2026)

Pas de course avant mi-janvier : la collecte des archives restantes (2017 partielle, 2016, 2011-2015) tourne aussi en journée pour être
finie avant la reprise, puis l'UCI n'est plus sollicitée pour les archives. Automatique (`collector.periode_de_courses`) : la restriction
11 h-23 h UTC revient seule dès qu'une course du Calendrier est à 3 jours près (Tour Down Under le 19/01/2027 : dès le 16/01).

## Décisions du propriétaire à retenir

- Zéro hallucination ; corrections de source seulement avec source citée et validation.
- Tout le peloton ; Wikipédia en source de texte principale (plusieurs langues), Gemini en dernier recours ; textes courts.
- Design moderne, mobile d'abord, thème sombre ; **simplicité** : pas de lignes redondantes, pas de liens en doublon, listes simples.
- Claude fusionne lui-même ses PR après vérification.
- Environnement « dashboards-sport » : accès web libre (mais Wikimedia limite souvent l'IP du conteneur : sondes via GitHub Actions).
- WorldDB (base PCM) : contrôle croisé seulement, jamais publiée, gardée hors des dépôts. Exception : les maillots (buste, crédit
  « WorldDB », accord des auteurs), sources dans le dépôt privé `maillots-pcm`.
- Maillots : toute la période de dénomination d'une équipe tant que le code UCI ne change pas ; maillots distinctifs conservés quand la
  course change de nom ; buste seul (sans manches ni cuissard).
- cyclingdb.com : réutilisation interdite sans autorisation écrite ; demande rédigée (à envoyer par le propriétaire).

## Prochaines étapes

1. Après le passage d'archives : vérifier Movistar `#equipe/Q6175`, une épreuve regroupée (AlUla Tour, Tour of Britain), les logos.
2. Après le prochain `wikidata.yml` : nombre de coureurs nouvellement reliés, contrôle d'un échantillon (aucun faux positif), Cepeda.
3. R3 : pages Saison (`#saison/<année>`), navbox partout, finitions ; « ce jour-là » plus riche.
4. Textes d'introduction Wikipédia (fr d'abord, synthèse multilingue courte) pour coureurs, équipes, épreuves.
5. Étendre l'historique Wikidata aux ~150 autres épreuves suivies (`historique.py --proposer`, même preuve).
6. Lignées d'équipes manquantes (ex. Groupama-FDJ) : re-vérification Wikidata v3, puis propositions d'équivalences à faire valider.
7. Doublons de coureurs restants (`doublons_possibles` du rapport d'`encyclopedie`, ex. Aranburu) : vérifier puis alias.
8. Maillots PCM Mod : équipes (maillot de chaque saison, 95 % des équipes-saisons 2017-2025, avec codes multiples et changements de nom
   en cours de saison publiés au prochain passage d'archives), sélections nationales, maillots distinctifs de 142 courses (chaque année).
   Table manuelle `maillots/pcmmod/manuel.json` (43 cas) : 96,7 % des équipes-saisons 2017-2026, 99,7 % des jours de course.
   À relancer `tools/pcmmod.py` quand 2027 sera publiée chez eux (puis compléter la table manuelle si besoin).
9. Surveiller `update.yml` (GitHub saute des crons) avant la reprise des courses.
10. Veille (`veille.yml`, dépôt d'archives, depuis le 17/11) : vérifier qu'elle relance bien les nuits sautées ; si elle est elle-même trop
    souvent sautée, passer à l'option 2 (tâche programmée côté Claude, accord du propriétaire).

## Suivi automatique

- Bilan programmé le 17/11 à 11 h 20 UTC (avancement archives, contrôle des vainqueurs 2016-2017, instantanés UCI,
  re-vérification Cofidis, historique dans `entites/index.json`).
