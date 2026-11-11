# Profondeur des archives UCI DataRide (hommes élite, route)

Date : 11 novembre 2026, depuis GitHub Actions (run 43070241185, workflow `essais.yml`, `tools/essais/essai_archives.py`, commit `[essai:archives]`). Un seul passage : 197 requêtes en 388 s, pause de 2 s sur `dataride.uci.org` (rythme « archives »), User-Agent de `netutil`. Saisons sondées : 2023, 2018, 2013, 2008 (une par tranche de `docs/PLAN_ARCHIVES.md`). Rien n'est écrit dans `data/`. Journal brut : non versionné (copie locale de session).

Requêtes par endpoint : `Competitions/` 111, `Results/` 41, `Events/` 15, `Races/` 9, `GetRestrictedResultsDisciplineSeasons/` 6, `RankingsDiscipline/` 4, `GetRankingMoments/` 3, `ObjectRankings/` 3, plus 5 pages pour les conditions d'utilisation.

## Verdict

- DataRide expose des saisons route de **1921 à 2027** (96 entrées), mais des courses hommes élite **seulement à partir de 2009** : 2005 à 2008 ne contiennent que 2 courses (championnats du monde en ligne et contre-la-montre), 2004 et avant : 0.
- De **2009 à 2026**, la couverture est dense : 216 à 473 courses par saison (2020, saison Covid : 216), avec Tour de France, monuments et championnats du monde présents sur les trois saisons sondées de cette période.
- Pour les courses témoins lues (grand tour, classique, course française .1) : classements complets, dates de naissance, nationalité et équipe présentes à 100 % des lignes, sur 2023, 2018 et 2013. **Dossards absents sur 2013** (0 sur tous les classements lus).
- Classement UCI : World Ranking disponible en 2023 et 2018 ; en 2013 seul le « UCI WorldTour Ranking » (228 lignes) est listé en individuel ; 2008 : aucun classement.
- Conditions d'utilisation : rien trouvé dans l'iframe ni sur uci.org (404 sur deux URL testées) ; voir la section dédiée.

## Saisons disponibles

Saisons avant 2005 : toutes à 0 course hommes élite (1921 à 2004, `id` de 163 à 376, bornes = année civile). Tableau des saisons contenant des courses (premier objet : `total` du `Competitions` hommes élite, tous types de course confondus) :

| Année | Id | Bornes | Courses | Première course (date) |
|---|---|---|---|---|
| 2005 | 367 | 2004-10-01 → 2005-09-30 | 2 | Championnats du monde route, ME IRR (2005-09-25) |
| 2006 | 252 | 2005-10-01 → 2006-09-30 | 2 | idem (2006-09-24) |
| 2007 | 177 | 2006-10-01 → 2007-09-30 | 2 | idem (2007-09-30) |
| 2008 | 186 | 2007-10-01 → 2008-09-30 | 2 | idem (2008-09-28) |
| 2009 | 80 | 2008-10-16 → 2009-10-15 | 373 | Giro del Piemonte (2009-10-15) |
| 2010 | 81 | 2009-10-16 → 2010-10-15 | 372 | Giro del Piemonte (2010-10-14) |
| 2011 | 82 | 2010-10-16 → 2011-10-15 | 387 | Il Lombardia (2011-10-15) |
| 2012 | 83 | 2011-10-17 → 2012-10-14 | 365 | Tour de Vendée (2012-10-14) |
| 2013 | 84 | 2012-10-22 → 2013-10-21 | 357 | Japan Cup Cycle Road Race (2013-10-20) |
| 2014 | 85 | 2013-10-22 → 2014-10-21 | 361 | Japan Cup Cycle Road Race (2014-10-19) |
| 2015 | 7 | 2015-01-01 → 2015-12-31 | 386 | Challenge des phosphates-Grand prix de Khouribga (2015-12-17) |
| 2016 | 15 | 2016-01-01 → 2016-10-23 | 437 | Japan Cup Cycle Road Race (2016-10-23) |
| 2017 | 19 | 2016-10-24 → 2017-10-25 | 455 | Japan Cup Cycle Road Race (2017-10-22) |
| 2018 | 89 | 2017-10-25 → 2018-10-21 | 442 | Japan Cup Cycle Road Race (2018-10-21) |
| 2019 | 132 | 2018-10-22 → 2019-10-22 | 470 | Japan Cup Cycle Road Race (2019-10-20) |
| 2020 | 145 | 2019-10-23 → 2020-11-10 | 216 | National Road Championships - Israel (ITT) (2020-11-06) |
| 2021 | 150 | 2020-11-11 → 2021-10-31 | 349 | National Road Championships - Indonesia (2021-10-25) |
| 2022 | 159 | 2021-11-01 → 2022-10-18 | 409 | Veneto Classic (2022-10-16) |
| 2023 | 414 | 2022-10-19 → 2023-10-17 | 472 | Japan Cup Cycle Road Race (2023-10-15) |
| 2024 | 432 | 2023-10-18 → 2024-10-20 | 446 | Utsunomiya Japan Cup Road Race (2024-10-20) |
| 2025 | 444 | 2024-10-21 → 2025-10-19 | 445 | Veneto Classic (2025-10-19) |
| 2026 | 464 | 2025-10-20 → 2026-10-18 | 473 | Veneto Classic (2026-10-18) |
| 2027 | 477 | 2026-10-19 → 2027-10-17 | 6 | Tour de Okinawa (2026-11-08) |

Constats : la colonne « Première course » est la première ligne renvoyée avec le tri `StartDate asc` demandé ; ce sont en fait les **dernières** courses de chaque saison (Japan Cup, Veneto Classic…) : le tri de la requête à une ligne n'est pas appliqué comme attendu (sans conséquence pour le décompte `total`). Les bornes ne sont pas homogènes : année civile avant 2005 et en 2015 (2015-01-01 → 2015-12-31), 1er octobre → 30 septembre de 2005 à 2008, mi-octobre → mi-octobre ensuite (2016 : 2016-01-01 → 2016-10-23). Certaines années sont absentes de la liste (1939 à 1945, 1960, 1963, 1972, 1981).

## Saisons sondées

### 2023 (id 414) : 472 courses

- Classes : CN 109, 1.2 93, 2.2 69, 1.1 60, 1.Pro 33, 2.1 29, 2.Pro 24, 1.UWT 20, 2.UWT 15, CRTP 5, CC 5, JR 4, CRT 3, JC 1, CM 1, N/A 1.
- Catégories actuelles (`selection.categorie_classe`) : .2 162, **None 129**, .1 89, Pro 57, WT 35.
- Classes non reconnues : CC (5, ex. UEC Road European Championships 2023, Asian Road Cycling Championships), CM (1, 2023 UCI Cycling World Championships - Road), CN (109, ex. National Road Championships - Switzerland (ITT), - Cuba, - Tunisia), CRT (3, ex. Oita Ikoinomichi Criterium), CRTP (5, ex. Japan Cup Criterium, Bay Crits), JC (1, Asian Games Hangzhou Cycling - Road), JR (4, ex. Jeux de la Francophonie, South East Asian Games), N/A (1, Championnats d'Europe des Grimpeurs 2023).
- En France : 60 (1.1 18, 2.2 11, 1.2 8, 1.Pro 8, 2.1 7, 2.UWT 3, 1.UWT 2, 2.Pro 2, CN 1). Dates vides 0, pays vide 1.
- Sélection actuelle (sans FDJ) : 143 (Pro 57, WT 35, .1 25, .2 19, Champ. 7).
- Présents : Tour de France (2.UWT, 2023-07-01), La Vuelta Ciclista a España (2.UWT), Milano-Sanremo, Ronde van Vlaanderen, Paris-Roubaix, Liège-Bastogne-Liège, Il Lombardia (tous 1.UWT), championnat d'Europe des grimpeurs. Giro d'Italia : non vérifié (voir anomalies). Championnats nationaux : classe CN (109), dont 1 seul en France ; le motif « Championnat|National Championships » n'a affiché que 2 exemples (champ. d'Europe des grimpeurs, Moldavie).

### 2018 (id 89) : 442 courses

- Classes : 2.2 78, 1.2 77, CN 77, 1.1 69, 2.1 47, **1.HC 24, 2.HC 21**, 1.UWT 20, 2.UWT 17, JR 5, CC 5, CM 1, JC 1.
- Catégories actuelles : .2 155, **None 134**, .1 116, WT 37 ; aucune « Pro ».
- Classes non reconnues : 1.HC (24, ex. Japan Cup Cycle Road Race, Gran Piemonte, Milano-Torino, Tre Valli Varesine, Paris - Tours Elite), 2.HC (21, ex. Ovo Energy Tour of Britain, Vuelta a Burgos, Arctic Race of Norway, PostNord Danmark Rundt), CC (5), CM (1, Championnats du Monde Route UCI), CN (77), JC (1), JR (5, ex. Mediterranean Games, 2018 Commonwealth Games).
- En France : 59 (1.1 20, 2.2 12, 2.1 9, 1.2 8, 1.HC 3, 2.UWT 3, 1.UWT 2, CN 1, 2.HC 1). Dates vides 0, pays vide 1.
- Sélection actuelle : 93 (WT 37, .1 29, .2 20, Champ. 7).
- Présents : Tour de France (2.UWT, 2018-07-07), Vuelta, Milano-Sanremo, Ronde van Vlaanderen, Paris-Roubaix, Liège-Bastogne-Liège, Il Lombardia, championnats du monde (CM, Autriche, 2018-09-23).

### 2013 (id 84) : 357 courses

- Classes : 1.2 95, 2.2 75, 1.1 73, 2.1 39, **2.HC 19, 1.HC 14**, 2.UWT 14, 1.UWT 14, CC 9, CM 3, JR 2. **Aucune classe CN** : les championnats nationaux n'apparaissent pas dans la liste.
- Catégories actuelles : .2 170, .1 112, None 47, WT 28.
- Classes non reconnues : 1.HC (14, ex. Japan Cup, Paris - Tours Elite, Giro dell'Emilia, Tour de Vendée, Milano-Torino, GP de Fourmies), 2.HC (19, ex. USA Pro Challenge, Vuelta a Burgos, Post Danmark Rundt, Tour de Wallonie, Tour of Qinghai Lake, Österreich-Rundfahrt), CC (9, championnats panaméricains / asiatiques / d'Océanie en ligne et c.l.m.), CM (3, championnats du monde IRR / ITT / TTT, Italie), JR (2, Mersin Mediterranean Games).
- En France : 63 (1.1 21, 2.2 15, 2.1 9, 1.2 8, 1.HC 3, 2.UWT 3, 1.UWT 2, 2.HC 2). Dates vides 0, pays vide 1.
- Sélection actuelle : 93 (.1 30, WT 28, .2 23, Champ. 12).
- Présents : Tour de France (2.UWT, 2013-06-29), Vuelta a España, Milano-Sanremo, Ronde van Vlaanderen, Paris-Roubaix, Liège-Bastogne-Liège, Il Lombardia, championnats du monde (3 épreuves).

### 2008 (id 186) : 2 courses

- Classes : CM 2 (Championnats du Monde Route, ME IRR, 2008-09-28 ; ME ITT, 2008-09-25, Italie). Aucune autre course, aucun grand tour, aucun monument, aucune course en France.
- Aucune lecture de course témoin ni de grand tour n'a été faite (rien à trouver). Aucun classement UCI.

## Courses témoins

Grand tour : Tour de France, lecture partielle (1re étape, dernière étape, classement final) ; classique : Paris-Roubaix ; course française .1 : Chrono des Nations. Tableau des classements présents (nombre de lignes) :

| Saison | Course | Étape 1 | Dernière étape | Classement final |
|---|---|---|---|---|
| 2023 | Tour de France (22 races dont « Final Classification ») | gc 175, youth 31, points 30, stage 176 (DNF 1), mountain 10 | stage 150 | points 123, gc 150, mountain 65, youth 27 |
| 2018 | Tour de France | mountain 1, youth 29, gc 176 (DSQ 1), stage 176, points 26 | stage 145 (DSQ 1) | mountain 63, youth 24, gc 145, points 124 |
| 2013 | Tour de France | stage 198, points 29, youth 35, gc 198, mountain 1 ; events aussi « Stage Combativity » | stage 170, points 146, youth 29, mountain 74, gc 169 | gc 198, points 146, combativity 1, youth 29, mountain 74 |

- **Par équipes** : aucun classement par équipes n'apparaît dans les `events` lus des trois grands tours. Les types d'épreuve sont donnés par `Races` : contre-la-montre par équipes (TTT) à l'étape 3 en 2018 et à l'étape 4 en 2013 ; ITT à l'étape 16 en 2023, 20 en 2018, 11 et 17 en 2013. Le log ne montre pas si des classements d'étape TTT par équipe existent.
- **Abandons** : statuts `DNF`, `OTL`, `DSQ` présents (codes Irm vus sur toute la sonde : DNF 178, OTL 16, DSQ 8). Tour de France 2023 étape 1 : DNF 1 ; Paris-Roubaix : 2023 OTL 3 / DNF 37, 2018 OTL 12 / DNF 62, 2013 OTL 1 / DSQ 2 / DNF 77.
- **Dates de naissance, nationalité, équipe** : 100 % des lignes sur toutes les lignes lues en 2023, 2018 et 2013. Seule exception : équipe 20 sur 21 au Chrono des Nations 2023.
- **Dossards** : 100 % en 2023 et 2018 ; **0 sur toutes les lignes en 2013** (tous classements du Tour, Paris-Roubaix, Chrono des Nations).
- **Temps / points** : couverts pour toutes les lignes classées ; les coureurs non classés (DNF, OTL) n'en ont pas (Paris-Roubaix : 135 sur 175 en 2023, 101 sur 175 en 2018, 118 sur 198 en 2013).
- **Points UCI** : présents (ex. Paris-Roubaix 60 lignes en 2023 et 2018, 10 en 2013 ; Tour de France classement final gc : 60 en 2023, 59 en 2018, 20 en 2013) .
- **Lieux d'étape** : `StartLocation` / `EndLocation` vides (« lieux de la 1re :  -> None ») sur les trois grands tours ; départ / arrivée vides aussi pour Paris-Roubaix et Chrono des Nations (`None->None`).
- **Paris-Roubaix** (type one_day, complet, 1 étape, 175 / 175 / 198 coureurs, JSON 97 / 98 / 111 Ko) : vainqueurs lus Van der Poel (2023), Sagan (2018), Cancellara (2013). Français classés : 13 (2023), 29 (2018), 35 (2013) ; `french_top10` : True en 2023, **False en 2018**, True en 2013.
- **Chrono des Nations** (21 / 29 / 23 coureurs, JSON 11 / 16 / 12 Ko) : vainqueurs Tarling (2023), Toft Madsen (2018, type itt), Tony Martin (2013, type itt) ; `french_top10` True les trois fois.
- Tour de France, classement final (gc, 1er) : Vingegaard (2023), Thomas (2018), Froome (2013).

## Classement UCI

`RankingsDiscipline` par saison (classements individuels type 1 listés par la sonde) :

- **2023** : 20 classements au total ; individuels : World Ranking (groupe 1, id 1), One Day Race World Ranking (152, id 237), Stage Race World Ranking (153, id 236), tours Africa / America / Asia / Europe / Oceania (groupes 7 à 11, ids 2 à 6). Moments de World Ranking : 53 (« Most Recent Ranking », 17/10/2023 … 25/10/2022), hebdomadaires. Top 5 du 17/10/2023 (3312 lignes) : Pogačar 7695,86 ; Vingegaard Hansen 6304,07 ; Evenepoel 5611,71 ; Roglič 5603,36 ; Van Aert 4762,0.
- **2018** : 19 classements ; individuels : World Ranking (1), « WorldTour Ranking - Ends 2018 » (groupe 3, id 7), tours continentaux (7 à 11). Moments : 54 (21/10/2018 … 29/10/2017). Top 5 du World Ranking le 21/10/2018 (3272 lignes) : Valverde 4168 ; Yates Simon Philip 3160 ; Viviani 3106 ; Sagan 3092 ; Alaphilippe 2991,12.
- **2013** : 17 classements ; individuels : « WorldTour Ranking - Ends 2018 » (groupe 3, id 7) et tours continentaux (7 à 11). **Pas de World Ranking.** Moments du WorldTour Ranking : 28 (15/10/2013 … 27/01/2013). Top 5 du 15/10/2013 (228 lignes) : Rodriguez Oliver 607 ; Froome 587 ; Valverde 540 ; Sagan 491 ; Nibali 482.
- **2008** : 0 classement.
- Date de naissance présente sur les 5 lignes lues de chaque classement ; `ComputationDate` = date de fin de saison (2023-10-17, 2018-10-21, 2013-10-15), c'est-à-dire le dernier moment, pas le 18 octobre de la saison.
- Non mesuré dans cet essai : taux de dates de naissance sur la totalité des lignes d'un classement archivé, mise en correspondance des `rider_id` avec les résultats de course.

## Conditions d'utilisation

Ce que la sonde a trouvé :

- `https://dataride.uci.org/` : 3579 octets, **aucun lien juridique** (motifs term, legal, condition, privacy, cgu, disclaimer, mention). `https://dataride.uci.org/iframe/Results/10/` : 87 462 octets, aucun lien juridique ; aucun extrait ne correspond aux mots « terms », « conditions », « copyright », « © », « reproduc », « licen » (rien d'affiché).
- `https://www.uci.org/terms-of-use` : `[WARN] HTTP 404`. `https://www.uci.org/legal-notice` : `[WARN] HTTP 404`.
- `https://dataride.uci.ch/robots.txt` (domaine `.ch`, non `.org`) : 1248 octets. Seul extrait affiché (mot « permission ») : « …you may not collect content for the # corresponding use. # (c) If the website operator does not include a content signal for a # corresponding use, the website operator neither grants nor restricts # permission via content signal with respect to the corresponding use. # The content signals and their meanings are: # search: building a search index and providing search results (e.g., returning # hyperlinks and short excerpts from your website's contents). Se… » : il s'agit du texte type des « content signals » ajoutés par Cloudflare. Les règles `User-agent` / `Disallow` / `Content-Signal` du fichier ne figurent pas dans le log.
- Le robots.txt de `dataride.uci.org` lui-même n'a pas été lu dans cet essai (déjà couvert par `sonde_uci.md`).

Conclusion factuelle : la sonde n'a trouvé aucune condition d'utilisation propre à DataRide ; elle n'a rien lu qui autorise ou interdise une collecte d'archives. Les règles déjà documentées (`sonde_uci.md` : robots.txt sans interdiction, attribution « Source : UCI DataRide » recommandée) restent la seule base ; la lecture de conditions écrites n'a pas abouti et reste à faire autrement (ex. lecture de la mention légale d'uci.org depuis un navigateur).

## Échecs et avertissements

- `[WARN] HTTP 404` sur `https://www.uci.org/terms-of-use` et `https://www.uci.org/legal-notice` (voir ci-dessus).
- Aucun `[ECHEC]` produit par la sonde (la ligne `[ECHEC] essai_$nom` du log n'est que le texte du script du workflow, non exécuté). Le job est terminé en succès (étape « Essais demandés » : 6 min 29 s).
- Aucun `[INFO]` dans le log.
- Avertissement du runner (sans effet) : Node.js 20 déprécié pour `actions/checkout@v4` et `actions/setup-python@v5`.

## Conséquences pour le plan

### Couverture par tranche (courses hommes élite par saison, tous types)

| Tranche | Saisons | Courses par saison | Observé |
|---|---|---|---|
| T1 | 2021 → 2025 | 349, 409, 472, 446, 445 | 2023 sondée : classes actuelles (UWT, Pro, .1, .2, CN), World Ranking, dossards, 3 courses témoins complètes |
| T2 | 2016 → 2020 | 437, 455, 442, 470, 216 | 2018 sondée : HC à la place de Pro, World Ranking présent, dossards présents. 2020 : 216 courses seulement |
| T3 | 2011 → 2015 | 387, 365, 357, 361, 386 | 2013 sondée : HC, pas de CN, dossards absents, pas de World Ranking (WorldTour Ranking seul, 228 lignes). 2015 aux bornes année civile |
| T4 | 2005 → 2010 | 2, 2, 2, 2, 373, 372 | 2005 à 2008 : championnats du monde seulement ; 2009 et 2010 : 373 et 372 courses, non lues |

Le plan dit « T4 : 2005 → 2010 » ; en pratique T4 = 2009 et 2010 seulement.

### Adaptations de `selection.py`

- `categorie_classe` ne reconnaît ni `1.HC` ni `2.HC` : à mapper vers « Pro » (45 courses en 2018, 33 en 2013), libellé d'origine conservé (point déjà prévu au plan §3).
- Classes nouvelles à traiter explicitement (reconnues ou ignorées) : `CN` (championnats nationaux : 109 en 2023, 77 en 2018, absente en 2013), `CC` (championnats continentaux), `CM` (monde), `JR` / `JC` (jeux), `CRT` / `CRTP` (critériums, 2023), `N/A` (1 en 2023).
- La sélection actuelle fait entrer dans « Champ. » : 7 en 2023, 7 en 2018, 12 en 2013, 2 en 2008. Ces nombres correspondent à CC + CM + 1 CN en France en 2023 et 2018, à CC + CM en 2013 (déduction par recoupement des effectifs, le log n'affiche pas la règle).
- Sans mapping HC, la sélection de 2018 (93) et de 2013 (93) ne comprend aucune course « Pro », alors que 2023 en compte 57.
- Dossards absents en 2013 : le code doit tolérer `bib` vide.
- Lieux d'étape vides pour toutes les saisons lues (déjà connu pour la saison courante).
- 2018 : `french_top10` False pour Paris-Roubaix avec 29 Français classés ; à regarder si la règle « Français dans le top 10 » ne concerne que les .1 / .2 étrangères (cas non pertinent pour un UWT).
- Classement UCI archivé : prévoir le groupe « WorldTour Ranking - Ends 2018 » (groupe 3, id 7) pour 2013 car le World Ranking (groupe 1) n'y existe pas ; vérifier l'année d'apparition du World Ranking (présent en 2018, absent en 2013 ; années intermédiaires non sondées).

### Décision proposée sur T3 et T4

- **T3 (2011 → 2015) : engager**, avec ces limites : pas de dossards, pas de World Ranking (WorldTour Ranking à 228 lignes à la place), classes HC à mapper. Justification : 357 à 387 courses par saison, grands tours, monuments et championnats du monde présents (2013), naissance / nationalité / équipe à 100 %, abandons présents.
- **T4 : ne retenir que 2009 et 2010** (373 et 372 courses). 2005 à 2008 se réduisent à 2 courses (monde) : pas d'archive utile pour le focus français. Avant d'engager 2009 et 2010, **une sonde supplémentaire est nécessaire** : l'essai n'a lu aucune course de ces deux saisons (le plan prévoyait 2008, qui est vide) ; relancer avec `[annees:2010,2009]` (le script accepte `[annees:...]`).
- T1 et T2 : rien dans la sonde ne s'oppose à la collecte ; 2020 sera une saison réduite (216 courses).
- Conditions d'utilisation : la sonde n'a rien trouvé qui interdise la collecte, mais n'a pas non plus trouvé de texte qui l'autorise explicitement ; à trancher par le propriétaire du projet avant une collecte de volume (environ 20 saisons × 400 courses).
