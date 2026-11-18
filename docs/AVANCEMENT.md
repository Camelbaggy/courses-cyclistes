# Avancement du projet (point de reprise)

Dernière mise à jour : 18 novembre 2026, fin de session. À lire avec `CLAUDE.md` (règles, architecture), `docs/PLAN_ENCYCLOPEDIE.md`
(plan et étapes), `docs/PLAN_ARCHIVES.md`, `docs/SPEC.md` (schémas) et `docs/recherche/` (sondes et décisions).

## POINT DE REPRISE (18/11/2026, fin de session) : à lire en premier

### Chantiers en cours au moment de la coupure
1. **Saison sportive = année civile : FAIT (PR #75, 18/11)**. Dans l'encyclopédie, une course compte pour l'année de sa `start_date` (Lombardia
   2010 -> 2010) ; stockage par saison UCI inchangé ; `riders.json` / `ranking.json` / `state.json` liés à leur dossier. Publié au prochain passage
   d'archives : vérifier `#epreuve/…lombardia…` (édition 2010 = Gilbert) et la fiche de Gilbert. Limites connues : onglet « Saison » de la fiche
   coureur encore par saison UCI ; fil d'Ariane d'une édition reportée -> liste Courses de son année (qui ne la contient pas) ; jeu fictif
   (`tools/fixtures/generer_archives.py`) non régénéré (contient encore une saison 2027).
2. **Sources d'avant 2009 : 4 accords obtenus par le propriétaire le 18/11** (à reporter dans CLAUDE.md « Sources » s'ils n'y sont pas) :
   - **the-sports.org** (Vincent Duplessy) : collecteur `thesports.py` (PR #69, #71), workflow `thesports.yml` du dépôt d'archives (PR #8),
     **collecte en cours** (`data/archives/sources/thesports/`, `etat.json` : 152 courses découvertes au 1er passage, ~5 400 éditions puis
     ~fiches coureurs restantes ; auto-relance). Étape 2 à faire : rattachement des courses (nom identique validé d'office ; à soumettre :
     Paris-Nice, Tirreno, Pays basque, Dauphiné, Paris-Camembert et les renommages ; proposition `docs/recherche/thesports_courses_proposees.json`),
     des coureurs (nom + date de naissance de la fiche du site), mondiaux (page multi-courses : garder la course en ligne élite) ; étape 3 :
     affichage (pages d'épreuve / édition / coureur) avec crédit « the-sports.org ».
   - **Mémoire du Cyclisme : étape 1 FAITE** (`mdc.py`, PR #74, `docs/recherche/mdc_collecte.md`) ; **collecte en cours** (`mdc.yml` du dépôt
     d'archives, PR #9, `data/archives/sources/mdc/`, auto-relance ; 2 261 courses, ~16 000-32 000 pages de classements estimées, 3,2 s / page).
     Ni date de naissance ni identifiant de coureur. À trancher : codes pays historiques `Hon`, `Tch`, `Rfa`, `Urs`, `Rda` (laissés vides).
   - **CQ Ranking : étape 1 FAITE** (`cqranking.py`, PR #77, `docs/recherche/cqranking_collecte.md`) ; **collecte en cours** (`cqranking.yml`, PR #10
     du dépôt d'archives, `data/archives/sources/cqranking/`, auto-relance ; ~28 h estimées). Résultats 1999-2008 (places à points CQ), fiches
     coureurs avec date de naissance (56/56) et ID UCI (62 %) : 16/16 concordants avec Wikidata. Classes anciennes (`1.4`, `1.5`, `CDM`) à rattacher.
   - **Museo del Ciclismo : étape 1 FAITE** (`museo.py`, PR #79, `docs/recherche/museo_collecte.md`) ; **collecte en cours** (`museo.yml`, PR #11
     du dépôt d'archives, `museo.py --suivies` = courses de `series_historiques.json` seulement, ~1 h 40 ; auto-relance). Le site ne distingue pas
     pros / amateurs par course : élargir la sélection (`--cles`) est une décision à prendre. 5 807 courses hommes (Italie 2 248, France 844) ;
     classements souvent complets, sans équipe ; fiches coureurs : naissance (31/31 = Wikidata) et équipes par année. Vainqueurs 20/20 = Wikidata.
     Codes pays historiques (CSI, DDR, LAT, TCH, URS) à tabler ; écart vide en fin de tableau jamais interprété.
   - **Étape 2 commune aux 4 sources** (à concevoir) : rattachement des courses (clés d'édition, alias), des coureurs (nom + date de naissance ;
     CQ Ranking et Museo donnent les dates, the-sports aussi par fiche, Mémoire du Cyclisme non), priorité entre sources en cas de désaccord
     (garder toutes les valeurs, jamais trancher), puis étape 3 : affichage avec crédit de chaque source.
   - **FirstCycling** : accord, mais pages de données derrière un défi Cloudflare (essais `essai_firstcycling*`, même un vrai navigateur sans
     déguisement échoue depuis GitHub Actions) : il faut que les administrateurs ajoutent une règle d'exception (en-tête secret), une clé d'API
     ou un export. **ProCyclingStats** : même blocage (défi sur tout le site ; robots.txt `Allow: /`, CGU interdisaient la reprise).
   - Écartés / sans suite : siteducyclisme.com (robots `Disallow: /` délibéré), cyclebase.nl (`Disallow: /`), bases PCM (données de jeu),
     CyclingRanking (compilation, `Crawl-Delay: 20`). Analyse du rapport Gemini du 18/11 : FirstCycling / CycleBase / Site du Cyclisme
     annoncés « sans protection » à tort ; seule vraie nouveauté : le nouveau site de Mémoire du Cyclisme.
3. **Archives 2009-2010 (T4)** : défaut d'`archives.yml` = 2009-2025 (PR #7 du dépôt d'archives). 2010 complète (185 courses), 2009 en cours
   (auto-relance). Ensuite : rattachement manuel des équipes 2009-2010 sans code UCI (classement WorldTour limité aux WorldTeams, comme
   2012-2014 : proposer par continuité d'effectif, faire valider).

### Incident du 18/11 après-midi (corrigé, PR #81)
the-sports.org a répondu 503 (erreur Cloudflare ordinaire) au 2e passage : pris pour un défi anti-robot, site abandonné, relance arrêtée.
Corrigé (503 = erreur passagère sauf marqueur explicite ; arrêt net si site abandonné ; pause 3 s). Mémoire du Cyclisme : plantage
`KeyError: 'affiche'` corrigé. À 17 h UTC : the-sports 4 497 éditions restantes (5 370 avant), Mémoire du Cyclisme 2 009 courses + 150 éditions
restantes, CQ Ranking 3 737 pages + 5 450 fiches, Museo 82 éditions + 4 911 fiches. Vérifier que les quatre auto-relances continuent
(`etat.json` de chaque `data/archives/sources/<source>/`) ; une relance s'arrête si un passage ne change rien ou plante (relancer à la main).

### Fait le 17-18/11
- **Refonte du site** (PR #55 à #61, `docs/REDESIGN.md`) : thème clair + sombre, composants Liquipedia modernisés, navigation (recherche
  d'en-tête, retour mobile, sous-navigation), accueil, fiche de course, fiche coureur, articles d'équipe, pages d'épreuve. **Reste : pages de
  liste** (Équipes, Coureurs, Classements, Courses, Recherche) ; titres « Derniers résultats marquants » à harmoniser.
- **Archives 2011-2025 complètes** ; sondage des vainqueurs contre Wikidata 2011-2015 (grands tours + 5 monuments) : 40/40 conformes.
  Championnat de France absent avant 2016 (limite DataRide). À regarder : `winner` vide dans l'index 2011 pour la Vuelta 2011 (le `final.gc`
  donne Froome, Cobo déclassé).
- **Équipes** : `data/ranking-<S>.json` (classement de fin de saison des saisons terminées encore au Calendrier, PR #62) et rang UCI des
  `riders-<S>.json` (PR #63) ; `alias_equipes.json` 85 entrées validées (PR #64-68 : 2026, Cofidis 2012-2026, Groupama-FDJ 2012-2026,
  Movistar 2015-2016, 45 équipes 2012-2014) ; lignée reprise par l'équipe renommée en cours de saison (`_heriter_lignees_renommees`, 43 cas ;
  à surveiller : Fundación Orbea 2020 -> Euskaltel-Euskadi). Correctif : coureur 2010 sans nationalité qui bloquait toute reconstruction
  d'`entites/` (PR #70). `entites/` du 18/11 : 26 063 coureurs, 5 223 équipes-saisons, 418 lignées, 871 épreuves ; Wikidata : 2 165 équipes-saisons
  rattachées sur 2 340, 11 311 coureurs.

### À faire ensuite (ordre suggéré)
1. Finir les chantiers ci-dessus (saison civile, collecteurs MDC / CQ / Museo, étape 2-3 des sources d'avant 2009).
2. **update.yml** : crons très souvent sautés (3 passages en 24 h au lieu de 11 le 17-18/11) : mettre une veille (modèle `veille.yml`) ou une
   tâche programmée **avant la reprise des courses (19/01/2027)**.
3. Refonte des pages de liste.
4. Bilan quotidien : la tâche programmée « Bilan archives » s'est arrêtée (sa condition, 2011-2025 complète, est remplie) ; en recréer une
   si le propriétaire le souhaite (2009, the-sports, nouveaux collecteurs).

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
- Saisons UCI archivées : 2016-2025 complètes (2017 : 199 courses, 2016 : 204 ; vainqueurs des grands tours, monuments et championnat de
  France 2016-2017 contrôlés : 18 sur 18 conformes), 2015 en cours (153 courses), puis 2014-2011 (archives.yml enchaîné jour et nuit en
  intersaison, ~25 passages le 17/11). Calendrier : 2026, 2027.
- Historique du classement UCI : 462 instantanés (2011-2027, 23 à 34 par saison ; 2015 en cours).
- `entites/` régénéré à chaque passage d'archives (19 079 coureurs, 3 592 équipes-saisons, 359 lignées, 664 épreuves, historique UCI ;
  17/11 11 h UTC : les 9 167 coureurs Wikidata publiés, dont Andersen, Großschartner, Hansen, Cepeda).
- Wikidata (`wikidata.yml`, dimanche + manuel) : 9 171 coureurs rapprochés (+787 le 17/11 avec la règle des noms v2), 1 505 équipes-saisons
  rattachées. Historique des épreuves :
  39 séries prouvées, 2 639 éditions historiques, 2 199 coureurs historiques `wd-Q…`.
- Alias : `alias_courses.json` 56 libellés (18 + 38 le 17/11 pour 32 courses renommées, tous prouvés par une série Wikidata commune et
  des vainqueurs concordants : Saudi Tour -> AlUla Tour, Tour of Britain / OVO / Lloyds, Route du Sud -> Occitanie… ;
  `docs/recherche/historique_avant_2009.md` §11) ; `alias_coureurs.json` 9 doublons ; `alias_coureurs_wikidata.json` 1 rapprochement
  manuel (Cepeda) ; `corrections_coureurs.json` 7 dates, 2 nationalités.
- Rapprochement des noms Wikidata v2 (ß / ø / æ…, second prénom d'un seul côté) : passage du 17/11 (6 h 20-9 h 20 UTC, 10 861 requêtes),
  +787 coureurs reliés, aucun perdu. Contrôle : Andersen (Q17428009), Großschartner (Q1403486), Hansen (Q108855164), Cepeda (Q21093468,
  alias) ; dates de naissance toutes égales aux nôtres (7 écarts = dates déjà corrigées dans `corrections_coureurs.json`) ; 4 noms sans mot
  commun avec l'article Wikipédia, mais concordants via les alias Wikidata (Anwar Azis, Bakırcı, Bizaye Tesfu, Tavera).

## Publication (vérifiée le 17/11 à 3 h 20 UTC)

Passage d'archives lancé à la main à 2 h 12 UTC (les crons de 0 h 23 et 1 h 23 avaient été sautés) : succès, puis relance automatique (en
chaîne jour et nuit pendant l'intersaison). Publiés : articles de lignée (Movistar `#equipe/Q6175`), épreuves regroupées (AlUla Tour
2020-2026, Tour of Britain 2017-2026), 19 logos ; 2017 passe de 122 à 159 courses. En attente du passage suivant (code fusionné après le
début du passage n° 14) : `codes_uci` et `renommee` des équipes-saisons (maillots des équipes renommées en cours de saison).
Passage Wikidata (règle des noms v2, Cepeda) lancé à la main à 2 h 15 UTC : échec après 11 min (la liste des coureurs lisait le nouvel
annuaire `coureurs/index.json`, une liste, comme un fichier de lettre ; même défaut dans `historique.py` pour `courses/index.json`). Corrigé le
17/11 (PR #51, test ajouté), passage relancé à 6 h 20 UTC : succès. Publication sur le site au passage d'archives suivant (reconstruction d'`entites/`).

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
2. Après le passage d'archives qui suit : vérifier sur le site les fiches d'Andersen, Großschartner, Hansen et Cepeda (photo, parcours).
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

- Bilan du 17/11 fait. Cofidis 2022-2024 : l'ancien rattachement erroné à l'équipe féminine a disparu (règle v3), mais aucune équipe masculine
  n'est trouvée (`aucune`) : à traiter avec les lignées manquantes (étape 6). Historique des épreuves : 2 574 éditions, 2 158 coureurs `wd-Q…`
  (baisse normale : 2016-2017 sont désormais couvertes par nos données UCI). `update.yml` : cron de 6 h 41 sauté (sans effet en intersaison).
- Prochain bilan le 18/11 à 11 h 20 UTC (2015-2011, contrôles des vainqueurs, lignées manquantes).
