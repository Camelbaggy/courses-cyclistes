# CyclingRanking (cyclingranking.com) : étude de source (étape 0, sans collecteur)

Sonde du **19/11/2026**, depuis le conteneur de développement. Aucun code de collecte écrit : ce document propose `cyclingranking.py`
(étape 1, à écrire après validation). Pages réelles allégées : `tools/fixtures/cyclingranking/` (12 fichiers, 216 Ko). Réseau : **35 requêtes**
(robots.txt x2, 33 pages), **21 s entre deux requêtes** (Crawl-Delay 20 + marge), aucune page demandée deux fois (cache local), aucun échec,
toutes en HTTP 200. Les mesures de concordance sont reproductibles hors réseau avec les pages mises en cache et les fichiers déjà publiés
dans `courses-cyclistes-archives` (`sources/museo/courses.json`, `sources/mdc/courses.json`, `sources/cqranking/calendrier/`,
`entites/historique/`) ; la sélection Museo est celle de `python museo.py --preparer-selection` (hors réseau).

## Accord et politesse

- Accord du site obtenu par le propriétaire le **19/11/2026** : lecture par programme ET affichage des données, crédit « CyclingRanking »
  (auteur du site : Stephan van Uijtregt, page `/sources`). Le site se présente comme un **classement personnel** (« Ranking of the best pro
  cyclists since 1869 ») construit sur 25 ans de dépouillement : revues (Velo, Wielerjaarboek…), livres, **Mémoire du Cyclisme, Museo del
  Ciclismo, CQ Ranking, ProCyclingStats, De Wielersite**, archives de presse. C'est donc une **compilation** : elle ne remplace pas nos sources,
  elle les recoupe et ajoute un jugement de niveau des courses (étoiles) et des équipes par résultat.
- `robots.txt` (19/11/2026) : bloc `User-agent: *` = `Crawl-Delay: 20`, `Disallow: /cyclist`, `/riders/search`, `/teams/search`, `/races/search`,
  `/*?highlight=*`, `/*&highlight=*`. Les blocs nommés (meta-externalagent, AhrefsBot, Googlebot à 5 s…) ne nous concernent pas. **Le
  Crawl-Delay de 20 s reste déclaré malgré l'accord : on le respecte** (`PAUSE_S` = 21). Aucun chemin interdit n'est utile : `/rider/<id>/…`
  (singulier) n'est PAS `/cyclist…` ; ne jamais suivre les liens `?highlight=` (présents dans les listes), ni les `…/search`.
- User-Agent `courses-cyclistes (accord CyclingRanking)` ; pas de challenge anti-robot rencontré (site ASP.NET MVC, pages rendues côté serveur,
  aucun JavaScript nécessaire, pas de jeton) ; 3 essais par page, abandon de l'hôte sur 403 / 429 / challenge (`netutil`) ; une page de 1,7 Mo
  (`/races`) a répondu en une requête.
- Licence des textes : les **biographies** des fiches coureurs sont recopiées de Wikipédia (« source - Wikipedia ») : ne pas les reprendre (CC BY-SA,
  hors accord) ; seuls les faits (dates, résultats, classes) sont lus.

## Architecture et URL (toutes lues dans les pages, aucune devinée sauf la pagination et l'année)

| Niveau | URL | Contenu |
|---|---|---|
| Accueil | `/` | menu : classements coureurs / équipes / pays (`/riders/overall`, `/riders/<année>`, `/teams/<année>`, `/countries/<année>`), `/races`, `/races/<année>`, directeurs sportifs, managers |
| **Vue d'ensemble des courses** | `/races` | **une seule page de 1,7 Mo : 2 036 séries de courses** (groupées par pays, 76 pays + « World »), nom, **étoiles 0-5**, première et dernière année, lien `/races/<slug>/history` ; filtres pays / étoiles (côté navigateur) |
| **Calendrier annuel** | `/races/<année>` (1869-2026, 158 pages ; liens « année précédente / suivante » et liste des années dans la page) | tableau par mois : **date** (`jj/mm` ou `jj/mm - jj/mm`), **pays** (drapeau + titre en anglais), **nom**, lien « stages » si course par étapes, **vainqueur** (lien `/rider/<id>/…`, drapeau), **étoiles** et, entre parenthèses derrière le nom, un **code de catégorie** (voir plus bas) ; 7 courses en 1869, 23 en 1900, 84 en 1910, 101 en 1950, 119 en 1995, 173 en 2005 |
| Historique d'une série | `/races/<slug>/history` | « 123 Editions (1896 - 2026) » : **année, vainqueur, 2e, 3e** de toutes les éditions (lien vers chaque édition) + étoiles de la série |
| Page d'édition | `/races/<année>/<slug>` | en-tête (nom + année, **n-ième édition**, départ - arrivée, km, date ; pour un grand tour : « General Classification », dates de début et de fin) + **classement** : rang, coureur (drapeau pays + `rider id`), **équipe** (lien `/teams/<année>/<id>/<slug>`), temps / écart ; badge de catégorie (`CdM` = Coupe du Monde, `SPP` = Super Prestige Pernod, `CDC` = Challenge Desgrange-Colombo) + étoiles |
| Étapes | `/races/<année>/<slug>/stages` puis `…/stages/stage-<n>` (`stage-8a`, `stage-P`…) | liste (date, libellé « Stage 2. Saint-Amand-Montrond - Roanne », vainqueur, distance) puis classement d'étape (même tableau) ; le classement général est la page d'édition |
| Classement des coureurs | `/riders/<année>` (100 par page, `?page=N`, 14 pages en 1995) | rang, coureur, équipe, pays, **score** CR ; `/riders/overall` : classement de tous les temps |
| Classement des équipes | `/teams/<année>` (100 par page ; 2 pages en 1995, ~130 équipes) | équipe, pays, score |
| Équipe-saison | `/teams/<année>/<id>/<slug>` | code (MAP), pays, **directeurs sportifs**, **effectif : nom, date de naissance complète (`27-Mar-1961`), pays, score**, victoires majeures de l'année (60 Ko) |
| Fiche coureur | `/rider/<id>/<slug>` | rang de tous les temps, nom, pays, **date de naissance complète + lieu** (`30-Nov-1968 - Mazamet (Midi Pyrenees)`), biographie (Wikipédia), badges, « Major Victories », saisons avec résultats (**398 Ko**, 500 liens de course) |
| Pays | `/countries/<année>` | classement des pays (non étudié) |

Particularités : identifiants numériques stables (`rider/4500`, `teams/1995/1379`), slugs des courses stables d'une année à l'autre mais **le même
slug peut recouvrir plusieurs séries disjointes dans le temps** (rare) ; les noms de course sont ceux de l'époque avec des tirets entourés
d'espaces (« Paris - Roubaix », « G.P. E3 - Harelbeke »), noms de sponsors parfois (« Trofeo Cala Millor - Cala Ratjada » sous le slug
`trofeo-ses-salines-felanitx`) ; pays de la course = pays de départ (« World » pour les championnats du monde et jeux olympiques, code `ioc`).

### Catégories et étoiles (ce que le site dit du niveau d'une course)

- **Étoiles 0 à 5 par édition** (`cr-race-category-small-N`) : « toutes les courses sont classées selon la difficulté, l'importance et le statut
  de la course à son époque » (FAQ). Elles **varient d'une année à l'autre** : sur 1 039 couples (édition, série) de 9 calendriers, 78 % ont la
  même valeur que celle de la page `/races` (la série porte l'étoile « actuelle ou dominante ») ; **lire les étoiles dans le calendrier de
  l'année, pas dans `/races`**.
- Répartition dans 10 calendriers (1910-2005, 1 123 éditions) : 0 étoile 8 %, 1 : 37 %, 2 : 33 %, 3 : 7 %, 4 : 8 %, 5 : 8 %. Au niveau des séries
  commencées avant 1999 : 1 : 872, 2 : 780, 3 : 93, 4 : 31, 5 : 16, 0 : 28 (total 1 820).
- **Étoiles = fonction du niveau UCI depuis 2005** (le calendrier affiche alors le code UCI : `1.1`, `2.1`, `1.HC`, `2.HC`, `1.PT`, `2.PT`, `GT`,
  `WCRR`, `WCTT`), mesurée sur 2005 : 1.1 -> 1 étoile (59 / 59), 2.1 -> 1 (20 / 20), 1.HC / 2.HC -> 2 (31 / 31), 1.2 / 2.2 -> 0 (12 / 12),
  ProTour 2.PT -> 3 ou 4, 1.PT -> 3 à 5, Grand Tour -> 5. Avant 2005 (2001 comparé à CQ Ranking) la correspondance est plus floue :
  `2.HC` CQ -> 4 étoiles (6 / 6), `CDM` -> 4 ou 5, `GT` -> 5 (3 / 3), mais `1.1` -> 1 à 3, `1.2` -> 0 à 2, `1.4` -> 0 à 1.
- Codes de catégorie historiques (entre parenthèses derrière le nom dans le calendrier, `title` = libellé complet) : `CDC` (Challenge
  Desgrange-Colombo, 1948-1958, 11 courses en 1950), `SPP` (Super Prestige Pernod, 1958-1987, 19 en 1970, 28 en 1985), `CdM` (Coupe du Monde,
  1989-2004, 11-12 par an), puis les classes UCI. Ces codes sont une information de niveau **sûre** (appartenance à un challenge officiel).
- **Le site ne distingue pas professionnel / amateur par course** : la FAQ dit « il n'est possible de marquer des points que dans les courses sur
  route » et le calendrier contient quelques épreuves amateurs (« World Championships Road Race (Amateurs) », « Tour de l'Avenir » en 1995) et des
  épreuves de six jours. Mais le **périmètre est celui des courses professionnelles ou ouvertes aux professionnels** (voir couverture : ~100
  courses par an, pas les milliers de courses locales amateurs).

## Couverture mesurée

- **2 036 séries** (462 en France, 203 aux États-Unis, 197 en Grande-Bretagne, 191 en Belgique, 136 en Allemagne, **123 en Italie**, 104 aux Pays-Bas,
  97 en Espagne), dont 1 820 commencent avant 1999 et 1 665 s'achèvent avant 2009 ; 193 sont encore courues en 2026. Comparaison d'échelle :
  Museo liste 5 807 courses d'hommes (dont 2 248 italiennes avant 2009).
- **Éditions** (interpolation sur 12 calendriers lus : 1869, 1900, 1910, 1920, 1930, 1950, 1970, 1985, 1995, 1998, 2001, 2005) : **≈ 11 000 éditions
  de 1869 à 2008, ≈ 9 300 avant 1999**, 26 % avec étapes. Le calendrier de 2001 compte 162 courses contre 456 au calendrier CQ Ranking de la même
  année : le site couvre **un cinquième** des courses de niveau UCI (surtout HC, ProTour, Coupe du Monde, grandes classiques et courses par
  étapes ; peu de 1.2 / 2.2 / 1.4 / 2.4 / 2.5).

### Concordance (a) : calendriers 2001 et 2005 contre CQ Ranking (clé exacte `nom|PAYS`, `museo.cle_museo`)

| Année | CR | CQ | clés communes | CR retrouvées dans CQ | CQ retrouvées dans CR |
|---|---|---|---|---|---|
| 2001 | 162 | 456 | 101 | 62 % | 22 % |
| 2005 | 173 | 528 | 107 | 62 % | 20 % |

- Les 38 % de CR absentes de CQ sont surtout des **noms différents** (« Vuelta a Murcia », « E3 Prijs Vlaanderen », « Driedaagse De Panne »,
  « Circuit de la Sarthe-Pays de Loire », championnats nationaux) : alias à écrire, jamais devinés.
- Catégories 2005 pour les courses communes : 1.1 -> 1 étoile (33), 2.1 -> 1 (14), 1.HC -> 2 (9), 2.HC -> 2 (11), 1.PT1 -> 5, 1.PT2 -> 3 / 4,
  2.PT -> 3 / 4, GT -> 5 : **aucune incohérence**. Le CR a bien retenu **les courses de plus haut niveau** : CQ absentes de CR en 2005 = 96 de
  classe 1.2, 81 de 2.2, 64 de 1.1, 30 de 2.1 et seulement 6 de 1.HC (sur 17).
- Pour 1999-2008 CR n'apporte donc **rien de plus que CQ Ranking** (déjà collecté, avec la classe UCI exacte) : son intérêt est ailleurs.

### Concordance (b) : Museo / Mémoire du Cyclisme avant 1999 (rapprochement exact par clé, `museo.cle_museo`, `gp` appliqué)

Cible : `selection.json` recalculé hors réseau (`--preparer-selection`) : **4 863 courses « sans_classe »**, dont **3 121 n'ont aucune édition en
1999 ou après** (`fin < 1999`, la cible de la demande ; 4 230 ont au moins une édition avant 1999). Pays de CR convertis par le code drapeau (ISO2)
vers ISO3 (`netutil.FLAG_CODES`).

| Ensemble | Courses | Clé exacte `nom|PAYS` dans CR | + période compatible | Étoiles des retrouvées (0 / 1 / 2 / 3 / 4 / 5) |
|---|---|---|---|---|
| Museo `sans_classe`, `fin < 1999` | 3 121 | **176 (5,6 %)** | **164** | 1 / 43 / 95 / 19 / 4 / 2 |
| Museo hommes, `fin < 1999` (toutes) | 3 134 | 185 | 170 | 1 / 43 / 99 / 19 / 4 / 4 |
| Museo `sans_classe`, `debut < 1999` | 4 230 | 193 | 178 | 6 / 48 / 98 / 20 / 4 / 2 |
| Museo déjà classées (`debut < 1999`, ex. suivies) | 380 | 131 | 127 | 23 / 45 / 36 / 4 / 9 / 10 |
| Mémoire du Cyclisme (398 courses lues, 389 avec édition < 1999) | 389 | 54 | 50 | 4 / 21 / 22 / 0 / 2 / 1 |
| dont MDC `amateurs` / `disparues` | 113 / 276 | 10 / 44 | 8 / 42 | |

- **Sens inverse** : sur les 1 820 séries CR commencées avant 1999, **270 existent dans Museo** (clé exacte), 52 dans MDC, 294 dans l'un ou l'autre ;
  pour les séries de **3 étoiles et plus : 46 sur 140 dans Museo, 47 avec MDC** (33 %). Les 93 séries de 3+ étoiles absentes sont en partie des
  six-jours, des courses du XIXe siècle, des championnats du monde / jeux olympiques (Museo les classe sous un autre nom) et des noms différents :
  « Ronde van Vlaanderen » (Museo : Giro delle Fiandre), « Gent-Wevelgem », « Vuelta al Pais Vasco », « Dauphiné Libéré », « G.P. des Nations »,
  « G.P. E3 - Harelbeke »… (liste reproductible hors réseau à partir de `/races` et de `sources/museo/courses.json`).
- **Par année** (édition de l'année dans l'intervalle `debut..fin` de la course Museo) : 1910 : 33 des 84 courses CR retrouvées dans Museo ; 1950 : 45 / 101 ;
  1970 : 48 / 94 ; 1985 : 51 / 104 ; 1998 : 69 / 138. Courses Museo `sans_classe` actives la même année : 99 (1910), 736 (1950), 922 (1970),
  1 062 (1985), 1 198 (1998) ; **retrouvées dans CR : 22, 14, 8, 7, 6**. Autrement dit **plus de 99 % des courses Museo des années récentes
  d'avant 1999 ne sont pas au calendrier CR** : ce sont des épreuves locales, régionales ou amateurs (Coppa …, G.P. …), et CR ne contient qu'un
  calendrier de « grandes » courses (~100 à 140 par an).
- **Rapprochement flou** (jetons du nom hors mots vides, même pays, périodes qui se recouvrent) : **62 courses Museo sans_classe de plus**
  ressemblent à 55 séries CR (« Circuit de Belgique » / « Tour de Belgique », « Marseille-Lyon » / « Lyon - Marseille », « G.P. San Sebastian » /
  « Bilbao - San Sebastian - Bilbao », « G.P. Wolber » / « Grand Prix Wolber », « Trophée Stan Ockers » / « G.P. Stan Ockers », « Circuit de la
  forêt de la Joux » / « Circuit de la Foret de Joux »…) mais avec des faux positifs manifestes (« Vuelta a Espana aficionado » ->
  « Vuelta a Espana », « Gent - Wevelgem indés » -> « Gent - Wevelgem » : course amateur homonyme). **Ne servir que de liste de propositions
  d'alias à valider une à une** (comme `docs/recherche/museo_alias_proposes.json`). Estimation après alias : **+30 à +50 courses**, soit
  **200 à 230 courses sur 3 121 (≈ 7 %)** au maximum qui recevraient un niveau.
- **Gain réel pour Museo / MDC avant 1999** : faible en nombre (≈ 7 %) mais **ciblé** : ce sont précisément les courses pro / semi-pro, avec une
  **étoile par édition** (0 à 5) et un code de challenge (SPP, CdM, CDC) quand il existe. Attention : MDC `amateurs` retrouve 10 courses dans CR
  (Paris-Dieppe, Paris-Mantes, Tour de Belgique, Trofeo Baracchi…) parce que **le périmètre de CR n'est pas strictement professionnel** (certaines
  éditions anciennes ou régionales ont 0 ou 1 étoile) : **présence dans CR = « course suivie par CR », pas « professionnelle » au sens UCI** ;
  les rapprochements par édition (année dans le calendrier de l'année) évitent les faux (Paris-Evreux : une seule édition CR, 1898).
- **Absence de CR ne prouve rien** : « sans classe » reste « sans classe », pas « amateur » (règle de `museo.py`).

### Concordance (c) : vainqueurs (échantillon)

- **Wikidata (`entites/historique/`) contre les pages d'historique CR** de 5 séries (Paris-Roubaix, Milan-San Remo, Tour des Flandres,
  Gand-Wevelgem, Tour de Lombardie), éditions antérieures à 2009 : **466 éditions comparées, 440 vainqueurs de même nom normalisé (94,4 %)** ; les 26
  écarts sont **tous la même personne écrite autrement** (« Albert Dejonghe » / « Berten DEJONGHE », « Henri Suter » / « Heiri SUTER », « Alfred De Bruyne » /
  « Fred DEBRUYNE », « Odile Defraye » / « Odiel DEFRAEYE », « Albéric Schotte » / « Briek SCHOTTE », « Oscar Camenzind » / « Oskar CAMENZIND »,
  « Herman Vanspringel » / « Herman VAN SPRINGEL », un nom absent du cache Wikidata) : **0 désaccord de personne**. Podiums complets (3 noms identiques) :
  386 sur 462 (84 %), les autres ne diffèrent que par l'orthographe ou la place (3e / 4e).
- **Mémoire du Cyclisme** (podiums) contre les vainqueurs des calendriers CR de 1869 à 1998 : 26 éditions comparables sur 10 années, **24 identiques**
  (les 2 autres : 1910 et 1950, à vérifier : variante d'orthographe probable).
- Les pages de résultat 1995 sont conformes à notre mémoire : Paris-Roubaix 1995 : Ballerini, Tchmil, Museeuw (Mapei - GB - Latexco, 6h27'08") ;
  Tour de France 1995 : 115 lignes au général, 114 temps ou écarts.

## Profondeur des résultats

| Page | Lignes | Équipe | Temps / écart | Remarque |
|---|---|---|---|---|
| Paris-Roubaix 1995 | 90 | 90 | 19 | classement **complet** (finishers) |
| Tour de France 1995, général | 115 | 115 | 114 | complet ; équipe + temps |
| Paris - Nice 1995, étape 2 | 30 | 30 | 5 | classement d'étape |
| Milano - Sanremo 1930 | 77 | 77 | 33 | l'équipe est souvent le groupe sportif de l'époque |
| Giro di Lombardia 1970 | 26 | 26 | 5 | **partiel** : les classiques anciennes sont tronquées |

- Comme pour Museo : le classement est complet quand le site possède la source, sinon tronqué, **sans indicateur de complétude** (pas de « partants / arrivés »).
- **Chaque ligne a une équipe** (lien `/teams/<année>/<id>/<slug>` : identifiant d'équipe-saison CR) : c'est ce qui manque aux classements de Museo (« pas
  d'équipe ») et de the-sports.org ; MDC non plus. Pas de dossard, pas de statut (abandon) ; **temps** : 1er en absolu (`6h27'08"`), suivants en écart
  (`01'56"`), cellule vide = même temps que la ligne précédente (à confirmer comme pour CQ Ranking : vide **ambigu, jamais interprété** tant que ce n'est pas établi) ;
  le pays du coureur est le drapeau (titre anglais du pays, à convertir en ISO3 ; pays de l'époque pas vérifiés : à mesurer à l'étape 1).
- Les pages d'édition ne contiennent **ni points CR ni coefficient** : seul le niveau (étoiles / code) est publié.
- **Dates de naissance** : fiche coureur (`30-Nov-1968`, jour complet + lieu, 398 Ko) **et** page d'équipe-saison (date complète pour chaque membre de l'effectif,
  31 coureurs pour 60 Ko : 100 fois moins cher à la page que la fiche). Le classement annuel `/riders/<année>` donne l'identifiant du coureur pour 100 coureurs par page.
  Échantillon d'équipe (Mapei - GB - Latexco 1995) : 31 coureurs, 31 dates complètes. Aucune mesure d'exactitude contre Wikidata (non faite : étape 1).
- **Pays disparus** : les calendriers classent la course en « World », « Czech Republic », etc. au nom actuel ; l'ancienne Tchécoslovaquie / URSS / RDA est à
  mesurer (non vérifié ici : décision du propriétaire du 18/11/2026, codes d'époque).

## Volumes et durée au Crawl-Delay (21 s par requête = 171 requêtes / h = 4 100 / jour)

| Phase | Requêtes | Durée | Taille | Intérêt |
|---|---|---|---|---|
| **P0** vue d'ensemble `/races` | 1 | 21 s | 1,7 Mo | séries, étoiles « dominantes » (déjà en cache) |
| **P1** calendriers annuels 1869-2008 | 140 | **49 min** | ≈ 20 Mo | **courses, dates, pays, étoiles, codes, vainqueur** : de quoi classer Museo / MDC avant 1999 et la sélection du pro avant 2009 |
| P1bis calendriers 2009-2026 | 18 | 6 min | 4 Mo | pas utile (UCI DataRide) |
| P2 historiques de séries (podium de toutes les éditions) | 1 665 (séries terminées avant 2009) ou 140 (≥ 3 étoiles) | 9,7 h ou 49 min | 120 Ko / page | podiums + noms de vainqueurs pour recoupement |
| P3 résultats (éditions) des courses ≥ 3 étoiles avant 2009 (3 + 4 + 5 étoiles = 7 + 8 + 8 = 23 % des ≈ 11 000 éditions) | ≈ 2 500 + étapes (26 % de courses par étapes, 8 à 21 étapes) ≈ + 3 000 | ≈ 32 h | 70 à 120 Ko | classements AVEC équipe |
| P3bis résultats de toutes les éditions < 2009 | ≈ 11 000 + étapes ≈ 15 000 | ≈ 90 h | ≈ 1,2 Go | non recommandé |
| P4 équipes-saisons (effectif + naissances) avant 2009 : ≈ 130 équipes / an en 1995, moins avant | ≈ 5 000 à 8 000 | 30 à 47 h | 60 Ko | dates de naissance (31 par page) |
| P5 fiches coureurs (naissance + lieu) | ≈ 20 000+ (identifiants jusqu'à 124 460) | > 5 jours | 400 Ko | non recommandé |

Chaque page est lue **une seule fois** (cache gzip comme `thesports.py`) ; les calendriers des saisons closes depuis plus d'un an ne sont jamais relus
(`etat.json` + `--relire`). À 50 min par passage nocturne : **P1 en 1 passage** (140 requêtes), P2 limité aux séries retenues en 1 à 2 passages.

## Ce que CR apporte, source par source

1. **Niveau des courses (le vrai gain)** : étoiles par édition + code de challenge (CDC, SPP, CdM) : *aucune autre source* du projet ne donne un
   niveau pour 1869-1998 (Museo : « pas de niveau par course », MDC : sections « amateurs » / « disparues » seulement, CQ Ranking : depuis 1999).
2. **Calendrier pro par année avant 1999** : 7 à 138 courses par an, avec date et pays, utilisable pour décider quelles éditions Museo valent d'être
   collectées (les éditions listées au calendrier CR de leur année) : au lieu de « sans_classe » : « niveau CR : ★★ ».
3. **Classements avec équipe** pour les grandes courses : complète les classements Museo (sans équipe) ; **ne pas** les substituer (source secondaire).
4. **Dates de naissance** par les pages d'équipe : un second jeu de naissances au jour pour les coureurs d'avant 2009 (identifiés par CR id), à rapprocher
   (nom + naissance) de ceux de Museo / the-sports.org / CQ Ranking : utile pour **relier les identités entre sources** ; pas indispensable.
5. **Équipes** : les « teams » par année avec effectif, directeurs sportifs et résultats ; les noms d'équipe-saison de l'époque (« Mapei - GB - Latexco ») ;
   complète `entites/equipes/` pour les années 1990 : aucun code UCI ici (`MAP` = code CR, **non UCI** : ne pas confondre avec `code_uci`).
6. **Pas de remplacement** : étapes hors grands tours souvent absentes, classements partiels sur les anciennes classiques, source elle-même
   compilée à partir de MDC / Museo / CQ (circularité : un accord CR / MDC n'est pas une preuve indépendante).

## Proposition de collecteur `cyclingranking.py` (étape 1, à écrire)

Centré **d'abord sur les calendriers annuels** (P0 + P1), les phases suivantes en options :

- Sortie `ARCHIVES_DIR/sources/cyclingranking/` :
  - `apercu.json` : séries de `/races` (`{slug: {nom, pays (ISO3 + nom CR), etoiles, debut, fin}}`) ;
  - `calendrier/<année>.json` : `{annee, courses: [{slug, nom, pays, date_debut (AAAA-MM-JJ, année de la page), date_fin, etapes (bool), etoiles, code (CdM / SPP / CDC / 1.HC…), vainqueur: {id, nom, nat}, url}]}` ; `lu_le` n'est pas écrit (déterminisme) ;
  - `etat.json` : `{termine, calendriers_restants, pages_restantes}` (sans horodatage, lu par un `cyclingranking.yml` du dépôt d'archives sur le modèle de `museo.yml`, groupe `cyclingranking-data`) ;
  - option `--editions` : `editions/<année>/<slug>.json` (classement `[rang, coureur id, nom, nat, équipe id, équipe, brut, ecart_s]`, étapes en `stages/`), `--equipes` : `equipes/<année>/<id>.json` (effectif avec naissances), `cache/` en gzip.
- Découverte : `/` -> liens `/races` et `/races/<année>` ; la liste des années est lue dans la page (« Season calendar for year 1869 1870 … ») ; slugs et
  identifiants lus dans les liens, jamais calculés ; pagination `?page=N` seulement là où la page l'annonce.
- Politesse : `PAUSE_S = 21`, UA `courses-cyclistes (accord CyclingRanking)`, délai de lecture 60 s, jamais de lien `?highlight=` ni `…/search`, abandon propre
  après 8 échecs de suite, 403 / 429 / challenge : abandon de l'hôte (`netutil`). Budget par défaut 50 min (timeout 60) -> **P1 tient en un passage**.
- Analyse : tableaux `<table class="table">` avec `<tr><td>` ; date `jj/mm` ou `jj/mm - jj/mm` + année de la page (courses à cheval sur deux années :
  non observées, à contrôler) ; code de catégorie = `<abbr title=…>` ou `<span>` dans la cellule du nom ; étoiles = `cr-race-category-small-N` (0 : classe sans
  étoile) ; vainqueur = premier lien `/rider/<id>/…` de la ligne ; `etapes` = lien `/stages`. HTML décodé (`&#xE8;` etc.). Pays = drapeau (`flag-xx`,
  `ioc` = World) converti en ISO3 ; si le drapeau manque : pays `None`, jamais déduit.
- Tests : `python cyclingranking.py --test` sur `tools/fixtures/cyclingranking/` (calendrier 1930 / 1995 / 2005, `/races` allégé, page d'édition, étapes,
  équipe, fiche coureur, historique, classement, robots.txt) ; concordances à rejouer avec les mêmes pages réelles.

## Comment s'en servir pour classer les courses Museo / MDC d'avant 1999

Règle proposée (un fichier `courses_cr.json` produit hors réseau, comme `selection.json`, puis **intégré à `museo.py` comme raison supplémentaire**) :

1. Clé d'une course CR de l'année Y : `museo.cle_museo(nom, pays ISO3)` ; **tolérance prudente** : le nom exact, plus `alias_cyclingranking.json`
   (`{slug CR: id de course Museo}` | `{id Museo: slug}`, manuel, preuve = même vainqueur sur ≥ 2 éditions comparables, propositions générées par le même
   calcul flou que ci-dessus, **validées une à une par le propriétaire**, comme `alias_museo.json`).
2. Une course Museo / MDC (id, pays) est **classée « CR »** pour une édition Y si elle correspond à une course du calendrier CR de **l'année Y** ET que
   le vainqueur (si présent dans notre classement) concorde par nom normalisé (`win.same`) : décision par édition, mémorisée, jamais redemandée. Niveau
   = `etoiles` + `code` de CR (sans conversion en classe UCI : comme CQ Ranking, seule la présence et l'étoile comptent).
3. Seuil de collecte à décider : **présence au calendrier CR de l'année** (toutes les étoiles, y compris 0 / 1) = édition « suivie » ; ou ≥ 2 étoiles pour
   resserrer (≈ 40 % des éditions, hors courses locales). Mesure : 3 121 courses `sans_classe` -> ≈ 164 à 176 reçoivent un niveau (avec alias ≈ 200-230).
4. Ordre d'attribution après l'étape 1 : `alias_museo` / index UCI (déjà fait), puis **CR (avant 1999)**, puis CQ Ranking (1999-2008), puis `sans_classe`.
5. Vérification : relire 20 courses attribuées par CR au hasard sur les pages Museo ; contrôler qu'aucune édition n'est affectée à une année hors de sa période de vie.

## Dépôt des données et affichage

- Crédit « CyclingRanking » (lien `https://www.cyclingranking.com`) sur les pages qui affichent leurs données (étoiles, codes de challenge, classements, naissances) ; pas de reprise des biographies Wikipédia.
- Les étoiles sont un **jugement éditorial** du site : à afficher comme tel (« niveau CyclingRanking »), jamais comme une classe UCI (voir `categorieClasse` de `index.html`, hors CR).

## Points ouverts

- Courses à cheval sur deux années civiles (calendrier de l'année de départ ?) ; **pays des courses 1869-1920** (frontières) ; les 2 écarts de vainqueur MDC
  de 1910 et 1950 non expliqués ; codes pays à l'époque (URS, TCH, GDR…) dans les drapeaux.
- Proportion des classements tronqués : pas de champ « partants / arrivés » ; à mesurer sur ~50 éditions à l'étape 1.
- Cellule de temps vide sur 79 % des lignes de Paris-Roubaix 1995 (71 sur 90) : écart vide = ambigu, jamais interprété.
- Estimation de la durée P4 (équipes) : nombre d'équipes par année avant 1990 non mesuré (130 en 1995 seulement).
- Pas de points CR ni de coefficient publiés par course : seulement des étoiles ; la valeur de l'étoile (0-5) est une échelle du site non documentée (FAQ vague).

## Recommandation

**Écrire `cyclingranking.py` limité aux calendriers annuels 1869-2008 (P0 + P1 = 141 requêtes, 50 min, un passage)**, puis le brancher sur la sélection
Museo / MDC avant 1999 comme **source de niveau** (étoiles + code de challenge). Gain modeste en volume (≈ 7 % des 3 121 courses « sans classe ») mais
**le seul niveau disponible pour 1869-1998** ; il isole en outre les ≈ 200 courses pro d'un fond de ≈ 2 900 courses locales ou amateurs qu'il vaut mieux ne
pas collecter. Ne PAS collecter résultats complets ni équipes à grande échelle (> 90 h) : se limiter, si besoin, aux éditions CR de ≥ 3 étoiles avant 2009
(≈ 2 500 pages, ≈ 15 h) pour obtenir **équipe + temps** là où Museo n'a pas d'équipe.
