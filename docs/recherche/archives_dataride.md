# Profondeur des archives UCI DataRide (hommes élite, route)

Date : 11 novembre 2026, depuis GitHub Actions (run 43070241185, workflow `essais.yml`, `tools/essais/essai_archives.py`, commit `[essai:archives]`). Un seul passage : 197 requêtes en 388 s, pause de 2 s sur `dataride.uci.org` (rythme « archives »), User-Agent de `netutil`. Saisons sondées : 2023, 2018, 2013, 2008 (une par tranche de `docs/PLAN_ARCHIVES.md`). Rien n'est écrit dans `data/`. Journal brut : non versionné (copie locale de session).

**Second passage** : run GitHub Actions 43071836929 (même workflow et même script, avec en plus le motif « Giro d.Italia » et, pour les grands tours, le décompte des lignes « sans statut ni valeur » avec rang et `ResultValue` brut `_rv`). Saisons sondées : 2010, 2009, 2013 (2013 relue). 101 requêtes en 200 s (étape « Essais demandés » : 3 min 20 s), pause de 2 s sur `dataride.uci.org`. Par endpoint : `Results/` 52, `Events/` 15, `Competitions/` 12, `Races/` 9, `GetRestrictedResultsDisciplineSeasons/` 4, `RankingsDiscipline/` 3, `GetRankingMoments/` 3, `ObjectRankings/` 3. Codes Irm vus : DNF 232, DSQ 72, OTL 54. Aucun `[ECHEC]` ni `[WARN]`. Journal enregistré en session : `sonde_archives_log2.txt` (scratchpad, non versionné). Les sections 2010, 2009, « Lignes sans statut ni valeur » et les mises à jour du plan en découlent ; le reste du rapport est inchangé.

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
- Présents : **Giro d'Italia (2.UWT, ITA, 2013-05-04, relevé au second passage)**, Tour de France (2.UWT, 2013-06-29), Vuelta a España, Milano-Sanremo, Ronde van Vlaanderen, Paris-Roubaix, Liège-Bastogne-Liège, Il Lombardia, championnats du monde (3 épreuves).

### 2010 (id 81) : 372 courses

- Classes : 2.2 97, 1.2 87, 1.1 84, 2.1 37, **1.HC 16, 2.HC 15**, CPE 8, CC 8, AU1 7, **2.CH 5, 1.CH 5**, CM 2, MNM 1. Aucune classe CN, UWT ni Pro.
- Catégories actuelles : .2 184, .1 121, **None 67** ; ni « WT » ni « Pro ».
- Classes non reconnues : 1.CH (5 : Liège-Bastogne-Liège, La Flèche Wallonne, Paris-Roubaix, Milano-Sanremo, Giro di Lombardia), 2.CH (5 : Vuelta a España, Tour de France, Giro d'Italia, Tirreno-Adriatico, Paris-Nice), 1.HC (16, ex. Giro del Piemonte, Paris-Tours, Giro dell'Emilia, Tour de Vendée, GP de Fourmies, Paris-Bruxelles), 2.HC (15, ex. Vuelta a Burgos, Post Danmark Rundt, Tour de Wallonie, Tour of Qinghai Lake, Österreich-Rundfahrt, Tour de Luxembourg), CPE (8, ex. Eneco Tour, Tour de Pologne, Tour de Suisse, Critérium du Dauphiné, Tour de Romandie, Vuelta al País Vasco), AU1 (7, ex. GP de Montréal, GP de Québec, GP Ouest-France Plouay, Vattenfall Cyclassics, San Sebastián, Amstel Gold Race), MNM (1, Ronde van Vlaanderen), CC (8, championnats panaméricains / asiatiques / d'Océanie / d'Afrique en ligne et c.l.m.), CM (2, championnats du monde IRR et ITT, Australie).
- En France : 66 (1.1 17, 2.2 16, 1.2 12, 2.1 11, 1.HC 3, 2.CH 2, 2.HC 2, AU1 1, CPE 1, 1.CH 1). Dates vides 0, pays vide 1.
- Sélection actuelle (sans FDJ) : 66 (.1 28, .2 28, Champ. 10).
- Présents : **Giro d'Italia (2.CH, ITA, 2010-05-08)**, Tour de France (2.CH, FRA, 2010-07-03), Vuelta a España (2.CH, 2010-08-28), Milano-Sanremo (1.CH), Ronde van Vlaanderen (MNM), Paris-Roubaix (1.CH), Liège-Bastogne-Liège (1.CH), championnats du monde (CM, 2). **Lombardia** : seule l'édition « Giro di Lombardia » datée **2009-10-17** (1.CH) figure dans la saison 2010 (bornes 2009-10-16 → 2010-10-15) ; « Piccolo Giro di Lombardia » (1.2) n'est pas le monument. Championnats nationaux : aucun (pas de classe CN).

### 2009 (id 80) : 373 courses

- Classes : 2.2 94, 1.2 91, 1.1 82, 2.1 42, **1.HC 16, 2.HC 15**, CPE 8, CC 8, **2.CH 5**, AU1 5, **1.CH 4**, CM 2, MNM 1. Aucune classe CN, UWT ni Pro.
- Catégories actuelles : .2 185, .1 124, **None 64**.
- Classes non reconnues : 1.CH (4 : Liège-Bastogne-Liège, La Flèche Wallonne, Paris-Roubaix, Milano-Sanremo), 2.CH (5 : Vuelta, Tour de France, Giro d'Italia, Tirreno-Adriatico, Paris-Nice), 1.HC (16), 2.HC (15, ex. Tour of Missouri, Vuelta a Burgos, Volta a Portugal, Post Danmark Rundt), CPE (8, ex. Eneco Tour, Tour de Pologne, Tour de Suisse, Dauphiné Libéré, Volta a Catalunya, Tour de Romandie), AU1 (5, ex. GP Ouest-France Plouay, Vattenfall Cyclassics, San Sebastián, Amstel Gold Race, Gent-Wevelgem), MNM (1), CC (8), CM (2, Suisse).
- En France : 68 (1.1 18, 2.2 17, 1.2 13, 2.1 11, 1.HC 2, 2.CH 2, 2.HC 2, AU1 1, CPE 1, 1.CH 1). Dates vides 0, pays vide 1.
- Sélection actuelle (sans FDJ) : 69 (.2 30, .1 29, Champ. 10).
- Présents : **Giro d'Italia (2.CH, ITA, 2009-05-09)**, Tour de France (2.CH, 2009-07-04), Vuelta a España (2.CH, 2009-08-29), Milano-Sanremo (1.CH), Ronde van Vlaanderen (MNM), Paris-Roubaix (1.CH), Liège-Bastogne-Liège (1.CH), championnats du monde (CM, 2). **Lombardia : absent** (motif sans résultat ; l'édition d'octobre 2009 est datée 2009-10-17, donc dans la saison 2010). Championnats nationaux : aucun.

### 2008 (id 186) : 2 courses

- Classes : CM 2 (Championnats du Monde Route, ME IRR, 2008-09-28 ; ME ITT, 2008-09-25, Italie). Aucune autre course, aucun grand tour, aucun monument, aucune course en France.
- Aucune lecture de course témoin ni de grand tour n'a été faite (rien à trouver). Aucun classement UCI.

## Courses témoins

Grand tour : Tour de France, lecture partielle (1re étape, dernière étape, classement final) ; classique : Paris-Roubaix ; course française .1 : Chrono des Nations. Tableau des classements présents (nombre de lignes) :

| Saison | Course | Étape 1 | Dernière étape | Classement final |
|---|---|---|---|---|
| 2023 | Tour de France (22 races dont « Final Classification ») | gc 175, youth 31, points 30, stage 176 (DNF 1), mountain 10 | stage 150 | points 123, gc 150, mountain 65, youth 27 |
| 2018 | Tour de France | mountain 1, youth 29, gc 176 (DSQ 1), stage 176, points 26 | stage 145 (DSQ 1) | mountain 63, youth 24, gc 145, points 124 |
| 2010 | Tour de France (22 races dont « Final Classification », prologue ITT + 20 étapes) | prologue : stage 197 (DSQ 3), points 10, gc 197 (DSQ 3), youth 38 | étape 20 : stage 170 (DSQ 3), points 156, mountain 87, gc 170 (DSQ 4), combativity 1, youth 32 | gc 197 (DSQ 4), points 156, combativity 1, mountain 87, youth 32 |
| 2009 | Tour de France (22 races dont « Final Classification », 21 étapes, TTT étape 4) | étape 1 (ITT) : stage 180 (DSQ 4), points 10, gc 180, mountain 3, youth 37 | étape 21 : stage 156 (DSQ 4), points 125, gc 156 (DSQ 5), mountain 87, combativity 1 (DSQ), youth 33 | mountain 87, points 125, combativity 1, youth 33, gc 180 (DSQ 5) |
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
- Tour de France, classement final (gc, 1er) : Vingegaard (2023), Thomas (2018), Froome (2013), **A. Schleck (2010), Contador (2009)** tels que renvoyés par DataRide.

Constats des saisons 2010 et 2009 (second passage) :

- **Dossards : 0 sur toutes les lignes lues** (Tour de France, Paris-Roubaix, Paris-Bourges), comme en 2013.
- **Dates de naissance et nationalité : 100 %** des lignes lues. **Équipe** : 100 % sur le Tour et Paris-Roubaix 2010 (193 / 193), mais **179 / 187** à Paris-Roubaix 2009, **85 / 92** à Paris-Bourges 2010 et **100 / 106** à Paris-Bourges 2009.
- **Points UCI** : 5 sur les classements d'étape du Tour, 19 (2010) et 20 (2009) sur le gc final, 10 à Paris-Roubaix (2010 et 2009), 7 à Paris-Bourges (2010 et 2009).
- **Abandons** : statuts DSQ sur les classements du Tour (DSQ 4 au gc final 2010, 5 en 2009). Paris-Roubaix 2010 : OTL 34 / DSQ 1 / DNF 85 sur 193 coureurs, 73 lignes avec temps ; 2009 : OTL 19 / DSQ 1 / DNF 69 sur 187, 98 lignes avec temps. Paris-Bourges 2010 et 2009 : aucun statut, temps sur toutes les lignes (92 et 106). Voir la section « Lignes sans statut ni valeur » pour les abandons du Tour.
- **Lieux d'étape** : `StartLocation` / `EndLocation` vides (« -> None ») sur le Tour 2010 et 2009 ; `None->None` pour Paris-Roubaix et Paris-Bourges.
- **Paris-Roubaix** (1.CH, one_day, complet, 193 / 187 coureurs, JSON 114 / 110 Ko) : vainqueurs Cancellara (2010), Boonen (2009) ; Français classés 38 (2010), 42 (2009) ; `french_top10` True les deux fois.
- **Paris-Bourges** (1.1, one_day, complet, 92 / 106 coureurs, JSON 54 / 62 Ko) : vainqueurs Ravard (2010), Greipel (2009) ; Français classés 38 (2010), 53 (2009) ; `french_top10` True.
- **Classement du mountain 2009** : les rangs affichés pour le top 3 sont 1, 3, 4 (le rang 2 n'apparaît pas dans les trois premières lignes du log) ; non expliqué par le log. Le `combativity` 2009 est un coureur disqualifié (Pellizotti, rang `None`, statut DSQ).
- **Tour de France 2009** : type TTT à l'étape 4 ; 2010 : ITT au prologue et à l'étape 19.

## Classement UCI

`RankingsDiscipline` par saison (classements individuels type 1 listés par la sonde) :

- **2023** : 20 classements au total ; individuels : World Ranking (groupe 1, id 1), One Day Race World Ranking (152, id 237), Stage Race World Ranking (153, id 236), tours Africa / America / Asia / Europe / Oceania (groupes 7 à 11, ids 2 à 6). Moments de World Ranking : 53 (« Most Recent Ranking », 17/10/2023 … 25/10/2022), hebdomadaires. Top 5 du 17/10/2023 (3312 lignes) : Pogačar 7695,86 ; Vingegaard Hansen 6304,07 ; Evenepoel 5611,71 ; Roglič 5603,36 ; Van Aert 4762,0.
- **2018** : 19 classements ; individuels : World Ranking (1), « WorldTour Ranking - Ends 2018 » (groupe 3, id 7), tours continentaux (7 à 11). Moments : 54 (21/10/2018 … 29/10/2017). Top 5 du World Ranking le 21/10/2018 (3272 lignes) : Valverde 4168 ; Yates Simon Philip 3160 ; Viviani 3106 ; Sagan 3092 ; Alaphilippe 2991,12.
- **2013** : 17 classements ; individuels : « WorldTour Ranking - Ends 2018 » (groupe 3, id 7) et tours continentaux (7 à 11). **Pas de World Ranking.** Moments du WorldTour Ranking : 28 (15/10/2013 … 27/01/2013). Top 5 du 15/10/2013 (228 lignes) : Rodriguez Oliver 607 ; Froome 587 ; Valverde 540 ; Sagan 491 ; Nibali 482.
- **2010** : 17 classements ; individuels : « WorldTour Ranking - Ends 2018 » (groupe 3, id 7) et tours continentaux (groupes 7 à 11, ids 2 à 6). **Pas de World Ranking.** Moments : 23 (« Most Recent Ranking », 18/10/2010 … 25/01/2010). Top 5 du 18/10/2010 (278 lignes) : Rodriguez Oliver 561 ; Gilbert 437 ; Sanchez Luis Leon 413 ; Evans 390 ; Nibali 390.
- **2009** : 17 classements, même structure (groupe 3 id 7 + tours continentaux), pas de World Ranking. Moments : 23 (19/10/2009 … 26/01/2009). Top 5 du 19/10/2009 (267 lignes) : Contador 527 ; Valverde 483 ; Sanchez Gonzalez 357 ; A. Schleck 334 ; Evans 333.
- **2008** : 0 classement.
- Date de naissance présente sur les 5 lignes lues de chaque classement ; `ComputationDate` = date de fin de saison (2023-10-17, 2018-10-21, 2013-10-15, 2010-10-18, 2009-10-19), c'est-à-dire le dernier moment, pas le 18 octobre de la saison.
- Non mesuré dans cet essai : taux de dates de naissance sur la totalité des lignes d'un classement archivé, mise en correspondance des `rider_id` avec les résultats de course.

## Lignes sans statut ni valeur (abandons non codés)

Le script compte, pour les classements de grand tour lus, les lignes sans statut Irm, sans temps et sans points, avec leur rang et le `ResultValue` brut (`_rv`).

| Saison | Classement | Lignes | Sans statut ni valeur | Rang | `_rv` | Lignes avec temps | Statuts |
|---|---|---|---|---|---|---|---|
| 2013 | Tour, final gc | 198 | 29 | `None` (5 premiers vus) | `''` | 169 | aucun |
| 2013 | Tour, final combativity | 1 | 1 | 1 | `''` | 0 | aucun |
| 2010 | Tour, final gc | 197 | 27 | `None` (5 premiers vus) | `''` | 166 | DSQ 4 |
| 2010 | Tour, étape 20, combativity | 1 | 1 | 1 | `''` | 0 | aucun |
| 2010 | Tour, final combativity | 1 | 1 | 1 | `''` | 0 | aucun |
| 2009 | Tour, final gc | 180 | 24 | `None` (5 premiers vus) | `''` | 151 | DSQ 5 |

Observations (aucune ligne sans statut ni valeur n'est apparue dans les autres classements lus : étapes, points, montagne, jeunes) :

- Les lignes du gc final concernées ont toutes un **rang `None` et un `_rv` vide**. Le compte est cohérent avec les lignes restantes : 2013, 198 − 169 = 29 ; 2010, 197 − 4 DSQ − 27 = 166 lignes avec temps ; 2009, 180 − 5 DSQ − 24 = 151. Le gc du dernier jour compte 169 lignes en 2013 (nombre d'arrivants), 170 en 2010 et 156 en 2009, soit moins que le gc final.
- Interprétation prudente : ce sont probablement des **coureurs ayant quitté la course sans code Irm** (abandons, non-partants, hors délai non codés), présents dans le gc final car ils figurent au départ. Le log ne le démontre pas : il ne montre ni les noms, ni l'étape de sortie, ni le statut éventuel dans les classements d'étape. À vérifier sur ces lignes avant de les afficher comme « abandon ».
- En 2013 les statuts du Tour sont vides (`statuts {}`) alors que Paris-Roubaix 2013 porte DNF 77 / DSQ 2 / OTL 1 : le codage Irm existe donc en 2013 pour les classiques mais, dans ce log, pas pour les abandons du Tour au gc final.
- Les lignes de `combativity` avec rang 1 et `_rv` vide sont des **classements d'un seul coureur** (prix de la combativité) : ce n'est pas un abandon ; le code doit les distinguer.
- Pour 2023 et 2018, ce décompte n'a pas été mesuré par ce passage.

## Giro d'Italia

Le motif « Giro d.Italia » donne : **2013** présent (2.UWT, ITA, 2013-05-04), **2010** présent (2.CH, ITA, 2010-05-08), **2009** présent (2.CH, ITA, 2009-05-09), une ligne par saison. Les étapes du Giro n'ont pas été lues ; seule la présence dans la liste des courses est établie. 2023 et 2018 : non vérifié (motif absent du premier passage).

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
| T4 | 2005 → 2010 | 2, 2, 2, 2, 373, 372 | 2005 à 2008 : championnats du monde seulement ; 2009 et 2010 lues au second passage : classes CH / CPE / AU1 / MNM / HC, dossards 0, pas de CN, pas de World Ranking (WorldTour Ranking 267 et 278 lignes), Giro, Tour, Vuelta, monuments (sauf Lombardia 2009, décalé en saison 2010) et monde présents |

Le plan dit « T4 : 2005 → 2010 » ; en pratique T4 = 2009 et 2010 seulement, désormais lues.

### Adaptations de `selection.py`

- `categorie_classe` ne reconnaît ni `1.HC` ni `2.HC` : à mapper vers « Pro » (45 courses en 2018, 33 en 2013), libellé d'origine conservé (point déjà prévu au plan §3).
- Classes nouvelles à traiter explicitement (reconnues ou ignorées) : `CN` (championnats nationaux : 109 en 2023, 77 en 2018, absente en 2013), `CC` (championnats continentaux), `CM` (monde), `JR` / `JC` (jeux), `CRT` / `CRTP` (critériums, 2023), `N/A` (1 en 2023).
- La sélection actuelle fait entrer dans « Champ. » : 7 en 2023, 7 en 2018, 12 en 2013, 2 en 2008. Ces nombres correspondent à CC + CM + 1 CN en France en 2023 et 2018, à CC + CM en 2013 (déduction par recoupement des effectifs, le log n'affiche pas la règle).
- Sans mapping HC, la sélection de 2018 (93) et de 2013 (93) ne comprend aucune course « Pro », alors que 2023 en compte 57.
- Dossards absents en 2013 : le code doit tolérer `bib` vide.
- Lieux d'étape vides pour toutes les saisons lues (déjà connu pour la saison courante).
- 2018 : `french_top10` False pour Paris-Roubaix avec 29 Français classés ; à regarder si la règle « Français dans le top 10 » ne concerne que les .1 / .2 étrangères (cas non pertinent pour un UWT).
- Classement UCI archivé : prévoir le groupe « WorldTour Ranking - Ends 2018 » (groupe 3, id 7) pour 2013 car le World Ranking (groupe 1) n'y existe pas ; vérifier l'année d'apparition du World Ranking (présent en 2018, absent en 2013 ; années intermédiaires non sondées).

- Anciennes classes vues en 2009 et 2010, absentes de `categorie_classe` : `1.CH` (monuments : Milano-Sanremo, Roubaix, Liège, Flèche Wallonne, Lombardia), `2.CH` (Tour, Giro, Vuelta, Tirreno-Adriatico, Paris-Nice), `CPE` (Eneco, Pologne, Suisse, Dauphiné, Romandie, Pays Basque / Catalunya), `AU1` (Amstel, Plouay, San Sebastián, Vattenfall, Montréal / Québec, Gent-Wevelgem), `MNM` (Ronde van Vlaanderen), plus HC et CC / CM. Soit 64 à 67 courses « None » par saison ; la sélection actuelle donne seulement 66 (2010) et 69 (2009), sans aucun grand tour ni monument. Le choix de la catégorie cible (WT / Pro) reste à trancher.
- Les bornes de saison (16 octobre → 15 octobre) placent le Lombardia d'octobre dans la saison suivante (2009-10-17 listé en 2010) : la fiche « Lombardia 2009 » est dans la saison 2010.
- Aucun statut Irm sur les abandons du Tour (gc final) : le code ne doit pas déduire un abandon de l'absence de statut sans règle explicite (voir section dédiée).

### Décision proposée sur T3 et T4

- **T3 (2011 → 2015) : engager**, avec ces limites : pas de dossards, pas de World Ranking (WorldTour Ranking à 228 lignes à la place), classes HC à mapper. Justification : 357 à 387 courses par saison, grands tours, monuments et championnats du monde présents (2013), naissance / nationalité / équipe à 100 %, abandons présents.
- **T4 : ne retenir que 2009 et 2010, après T3, avec les mêmes limites que T3 en plus marquées** (sonde faite au second passage). Pour : 372 et 373 courses, 66 et 68 en France ; Giro, Tour, Vuelta, monuments (hors Lombardia 2009 décalé) et championnats du monde présents ; naissance et nationalité à 100 % des lignes lues, classements de grand tour complets (gc, points, montagne, jeunes, combativité) avec 22 races par Tour ; Paris-Roubaix et Paris-Bourges lisibles en entier (JSON 54 à 114 Ko) ; points UCI présents ; classement WorldTour Ranking disponible (23 moments, 267 et 278 lignes). Contre : dossards 0 ; équipe incomplète sur certaines courses (179 / 187, 85 / 92, 100 / 106) ; 5 anciennes classes à mapper (CH, CPE, AU1, MNM, HC) et 64 à 67 courses sans catégorie actuelle ; 24 à 29 lignes d'abandons non codés au gc final du Tour ; pas de World Ranking ; pas de CN ; lieux d'étape vides. Aucun de ces points n'est bloquant pour un affichage « résultats d'archive » si le code tolère `bib` / équipe vides et traite les lignes `rang None` explicitement ; T4 est la tranche la plus éloignée de la saison courante et la plus lacunaire des tranches lues, d'où la priorité la plus basse. À engager seulement si le volume de requêtes (environ 400 courses × plusieurs requêtes par course, 2 s de pause) reste acceptable ; 2005 → 2008 : ne pas collecter (2 courses de championnat du monde, aucun focus français).
- T1 et T2 : rien dans la sonde ne s'oppose à la collecte ; 2020 sera une saison réduite (216 courses).
- Conditions d'utilisation : la sonde n'a rien trouvé qui interdise la collecte, mais n'a pas non plus trouvé de texte qui l'autorise explicitement ; à trancher par le propriétaire du projet avant une collecte de volume (environ 20 saisons × 400 courses).
