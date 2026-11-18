# the-sports.org : collecte des résultats d'avant 2009 (exploration du 18/11/2026)

Accord : l'éditeur du site (Vincent Duplessy) a autorisé le propriétaire du projet, le 18/11/2026, à collecter par programme les résultats cyclistes de the-sports.org et à les afficher avec le crédit « the-sports.org ». Collecteur : `thesports.py` (étape 1 : lecture et stockage seulement, rien n'est intégré à `encyclopedie.py` ni à la page). Contexte et premiers constats : `sources_avant_2009.md` §1 (cette exploration corrige : les courses secondaires françaises SONT présentes).

Mesures : environ 155 requêtes, ≥ 2 s d'écart, User-Agent « courses-cyclistes (accord the-sports.org) », robots.txt respecté (aucune des URL interdites n'est demandée). Pages lues : accueil cyclisme, calendriers 1990 / 1995 / 2000 / 2005 / 2008 / 2024, les 4 calendriers par groupe de 1995, 94 éditions de 1995 (toutes les courses actives en 1995, parsées avec une première version du parseur : stats de profondeur et de structure valables, JSON non définitifs), 12 éditions 1995-1998 de Paris-Roubaix / Tour de France / Paris-Nice (parseur final), Tour de France 2003, une fiche coureur.

## 1. Structure du site

- **Accueil** `cycling-s2.html` -> lien « Calendar <année> » -> `cycling-calendar-<année>-s2-c0-b0-u<id>.html` : calendrier de TOUTE la saison (tableau Date / Lieu-Pays / Course / Competition / Classe / Vainqueur) + liste déroulante des années (140 années, 1876 → 2026 ; la valeur de chaque option est l'URL du calendrier de l'année). L'identifiant `u<id>` n'est pas une fonction simple de l'année : on suit les liens de la liste.
- **Calendriers par groupe** (`…-calendar-<année>-s2-c0-b0-g<22|28|23|194>-u<id>.html` : World Tour one-day / stage races, Europe Tour one-day / stage races) : sous-ensembles du calendrier général (1995 : 12 + 5 + 66 + 5 = 88 courses sur 97 lignes du général) ; le calendrier général est la bonne porte d'entrée.
- **Colonne « Competition »** du calendrier général (valeurs vues en 1990 / 1995 / 2000 / 2005 / 2008) : `World Tour`, `UCI Europe Tour`, `UCI Asia / America / Africa Tour`, `Grand Tour`, `National Championships` (4 pays : France, Belgique, Pays-Bas, Nouvelle-Zélande), `World Championships`, `Olympic Games`, `Continental Championships`, et à écarter : `Women's events`, `Juniors events`, `U23 events` (+ noms contenant junior / u23 / espoir / amateur / women). Les libellés « World Tour » et « UCI Europe Tour » sont rétroactifs (le site classe 1990-2004 selon l'équivalent actuel).
- **Page d'édition** `cycling-<nom>-results-<année>-ep<r|m|f|i><id>.html` : `epr` = sans genre (la grande majorité, hommes), `epm` = hommes (championnats du monde, nationaux de certains pays, Giro / Olympiques), `epf` = femmes, `epi` = mixte (écartés). Contenu : `<h4 class="nomargin">` par classement (général, points, montagne, prologue, étape N…) suivi d'un `table-style-2`. Une icône `alt` donne le profil de l'étape (Sprint, Escape, Mountain, Medium mountain, Time Trial). « Display Full results » n'est qu'un repli CSS (tout est dans le HTML). Onglet « Start list » (`…-l1.html`) non lu.
- **Course = onglet « Archives »** de n'importe quelle édition : liste de TOUTES les éditions (`<li><a href="…">1998 - Tour de France</a></li>`), avec les noms successifs de la course (Cholet - Pays de Loire, Cholet - Mauléon, Cholet Agglo Tour…). La liste déroulante d'années en tête de page OMET l'année courante : on lit l'onglet Archives. L'identifiant de course est le `sup<N>` du lien « Prize list » de la barre d'onglets de la page (Paris-Roubaix `s43`, Tour `s94`, Paris-Nice `s96`) ; le menu général contient d'autres liens `sup` (à ne pas confondre : `thesports.id_course` ne lit que la barre d'onglets).
- **Ligne de classement** : rang | `Nom (CODE)` avec lien `<slug>-cycling-spf<id>.html` (id du coureur sur le site) et drapeau | équipe | temps ou points. **Pas de date de naissance** dans les classements ; la fiche coureur (1 requête par coureur) contient « born 11 December 1964 » dans un court texte (non exploité, voir points ouverts).
- **Menu « World Tour - <année> »** (barre latérale) : 18 liens de la saison, redondant avec le calendrier ; non utilisé.

## 2. Formats de temps rencontrés (colonne 4 d'un classement)

Premier : temps absolu ; suivants : écart au premier (`s.t.` / `m.t.` = même temps que la ligne PRÉCÉDENTE) ; contre-la-montre et prologues : temps absolus pour tous (`0:06:16`, `56'19''`). Formats lus par `thesports.parse_temps` : `6h27'08"` · `4h18'56` (sans marque finale) · `4h12'51'` · `6u05'23"` · `55'30''` · `1'20` · `35''` · `8` (secondes, classement en temps) · `H:MM:SS` · `MM:SS` · `+ 00' 00` (écart explicite) · `5h 49' 18` (espaces) · préfixe `1412 km 37h35'39''` (distance totale du vainqueur) · suffixe ` (40.116 km/h)`. **Jamais interprétés** (brut conservé, compté) : `8.17.00` / `5.36.14` (années 2006+ : H.MM.SS ou MM.SS.cc, ambigu), `4'` / `36'` (Tour 2003 : minutes sans secondes), `t.s.t.`, `-1 Lap`, `0h`. Règle d'absolu / écart : valeur >= temps du premier = absolu, sinon écart (un écart supérieur au temps du vainqueur est impossible) ; seule la 1re ligne du tableau donne la référence : si elle est absente (Tour 2003 : le rang 1, retiré du classement, manque) les temps sans `+` ni `s.t.` restent non résolus (`temps_non_resolus`).

## 3. Profondeur constatée (éditions de 1995, 94 pages)

| Type | Pages | Profondeur du classement final / général |
|---|---|---|
| Course d'un jour | 88 | podium seul (3 lignes) à 10 lignes : 54 ; 11-30 : 17 ; > 30 (jusqu'à 90-100) : 17 |
| Course par étapes | 6 | général complet (99-115 lignes en 1995, 96-146 pour le Tour) |

- Les classements d'étape sont tronqués : Tour de France 20 lignes (prologue 50), Paris-Nice 1995 10 lignes, Paris-Nice 1998 35 lignes ; certaines étapes sont vides (Tour 1998 étape 17 : 0 ligne, Paris-Nice 1995 étape 4 : 0).
- Autres classements présents (Tour de France seulement parmi les éditions lues) : points (10 à 49 lignes), montagne (50 à 84) ; pas de classement par équipes ni des jeunes constaté. Des cellules de temps contenant un code pays (« Rus », « Sui ») existent dans le Tour de Suisse 1995 (illisibles, comptées).
- Statuts (DNF, DNS…) : aucun vu (rangs tous numériques) ; seuls les classés sont listés. Les rangs affichés sont repris tels quels (jamais recalculés ; Paris-Roubaix 1995 : 90 lignes, rangs jusqu'à 91).
- Tour de France 1999-2005 : **présent** sur le site (liste Archives complète 1903-2026, 113 éditions, trous 1915-18 et 1940-46) ; Tour 2003 : GC 146 lignes, rang 1 absent (retrait du classement officiel), 49 lignes aux points, 84 à la montagne. La page « Prize list » omet seulement ces vainqueurs.
- Grands Tours : le calendrier ne contient que le Tour en 1990 et 1995 ; Giro et Vuelta n'ont de pages d'édition qu'à partir de 2002 / 2003 (le Prize list les cite sans lien avant). Olympiques : 2000 et 2008 au calendrier.

## 4. Courses route hommes élite trouvées

Calendriers lus : 1990 (84 courses retenues sur 86 lignes), 1995 (95 / 97), 2000 (110 / 118), 2005 (128 / 142), 2008 (143 / 162). Les 95 courses ci-dessous = toutes les courses actives en 1995 (+ quelques-unes vues en 1996-98) ; **5 026 éditions ≤ 2008** y sont listées (médiane 48 par course, 15 à 113) ; une édition est « présente » dès qu'elle figure dans la liste Archives (sa page n'est lue qu'à la collecte). Les calendriers 2000 / 2005 / 2008 montrent encore 21 / 37 / 54 courses absentes de ce lot (Giro d'Italia, Tour de Romandie, Tour Down Under, Eneco Tour, HEW Cyclassics, Setmana Catalana, Étoile de Bessèges, Tour du Limousin, Tour du Poitou-Charentes, Tour de l'Ain, Tour du Finistère, Paris-Corrèze, Tour de la Somme, Boucles de l'Aulne, Classic Loire-Atlantique, Châteauroux Classic…) : la découverte complète (≈ 130 calendriers de 1876 à 2008) en révélera davantage. **Estimation globale** : 200 à 260 courses, ~8 000 éditions ≤ 2008 (≈ 95 courses × 53 déjà vues + ~130 courses × ~25).

Colonne « Trous » : années ≤ 2008 sans édition dans la liste Archives du site (guerres, éditions non annulées mais absentes). Colonne « Clé proposée » : voir `thesports_courses_proposees.json` (null = pas de rattachement sûr).

| id site | Course | Compétition (calendrier) | Éd. ≤ 2008 | Années (site) | Trous ≤ 2008 | Clé proposée |
|---|---|---|---|---|---|---|
| s36 | World Championships | World Championships | 36 | 1921-2007 | 51 années | **null** |
| s37 | French National Championships | National Championships | 97 | 1907-2008 | 1915-1918, 1940 | national road championships france\|FRA |
| s38 | Milan - San Remo | World Tour | 99 | 1907-2008 | 1916, 1944-1945 | milano sanremo\|ITA |
| s39 | Ronde van Vlaanderen | World Tour | 92 | 1913-2008 | 1915-1918 | ronde van vlaanderen tour des flandres\|BEL |
| s43 | Paris-Roubaix | World Tour | 106 | 1896-2008 | 1915-1918, 1940-1942 | paris roubaix\|FRA |
| s44 | Liege - Bastogne - Liege | World Tour | 94 | 1892-2008 | 23 années | liege bastogne liege\|BEL |
| s45 | Amstel Gold Race | World Tour | 43 | 1966-2008 | — | amstel gold race\|NED |
| s47 | Clasica San Sebastian | World Tour | 28 | 1981-2008 | — | donostia san sebastian klasikoa\|ESP |
| s48 | Championship of Zurich | World Tour | 92 | 1914-2007 | 1915-1916 | **null** |
| s49 | Paris-Tours | World Tour | 102 | 1896-2008 | 1897-1900, 1902-1905, 1915-1916, 1940 | paris tours\|FRA |
| s50 | Giro di Lombardia | World Tour | 102 | 1905-2008 | 1943-1944 | giro di lombardia\|ITA |
| s53 | Omloop Het Nieuwsblad | UCI Europe Tour | 61 | 1945-2008 | 1960, 1986, 2004 | omloop het nieuwsblad elite\|BEL |
| s54 | Tour Mediterraneen | UCI Europe Tour | 35 | 1974-2008 | — | tour mediterraneen\|FRA |
| s55 | Grote Scheldeprijs - Vlaanderen | UCI Europe Tour | 95 | 1907-2008 | 1915-1918, 1940, 1944-1945 | scheldeprijs\|BEL |
| s56 | Rund um den Henninger Turm | UCI Europe Tour | 47 | 1962-2008 | — | eschborn frankfurt\|GER |
| s58 | Criterium International | UCI Europe Tour | 77 | 1932-2008 | — | criterium international\|FRA |
| s59 | Driedaagse van De Panne | UCI Europe Tour | 32 | 1977-2008 | — | ag driedaagse brugge de panne\|BEL |
| s60 | Veenendaal - Veenendaal | UCI Europe Tour | 23 | 1985-2008 | 1986 | arnhem veenendaal classic\|NED |
| s61 | Coppa Placci | UCI Europe Tour | 57 | 1923-2008 | 29 années | **null** |
| s62 | Paris-Bruxelles | UCI Europe Tour | 88 | 1893-2008 | 28 années | brussels cycling classic\|BEL |
| s63 | Four Days of Dunkirk | UCI Europe Tour | 54 | 1955-2008 | — | 4 jours de dunkerque grand prix des hauts de france\|FRA |
| s65 | Giro dell'Emilia | UCI Europe Tour | 91 | 1909-2008 | 9 années | giro dell emilia\|ITA |
| s66 | Giro del Lazio | UCI Europe Tour | 73 | 1935-2008 | 1944 | roma maxima\|ITA |
| s67 | Giro del Piemonte | UCI Europe Tour | 95 | 1906-2008 | 8 années | giro del piemonte\|ITA |
| s94 | Tour de France | Grand Tour | 95 | 1903-2008 | 1915-1918, 1940-1946 | tour de france\|FRA |
| s96 | Paris - Nice | World Tour | 19 | 1990-2008 | — | paris nice\|FRA |
| s97 | Tirreno-Adriatico | World Tour | 19 | 1990-2008 | — | tirreno adriatico\|ITA |
| s98 | Vuelta al Pais Vasco | World Tour | 19 | 1990-2008 | — | itzulia basque country\|ESP |
| s100 | Criterium du Dauphine Libere | World Tour | 19 | 1990-2008 | — | criterium du dauphine\|FRA |
| s102 | Tour de Suisse | World Tour | 72 | 1933-2008 | 1940, 1943-1945 | tour de suisse\|SUI |
| s1362 | Gent-Wevelgem | World Tour | 70 | 1934-2008 | 1940-1944 | gent wevelgem\|BEL |
| s1363 | Fleche Wallonne | World Tour | 72 | 1936-2008 | 1940 | la fleche wallonne\|BEL |
| s1365 | GP Ouest France - Plouay | World Tour | 72 | 1931-2008 | 1939-1944 | gp ouest france plouay\|FRA |
| s1369 | Tour de la Region Wallonne | UCI Europe Tour | 15 | 1994-2008 | — | ethias tour de wallonie\|BEL |
| s1924 | Kuurne-Brussel-Kuurne | UCI Europe Tour | 61 | 1946-2008 | 1986, 1993 | kuurne brussel kuurne\|BEL |
| s2695 | E3 Prijs Vlaanderen | UCI Europe Tour | 51 | 1958-2008 | — | e3 saxo classic\|BEL |
| s2697 | Rund um Köln | UCI Europe Tour | 43 | 1910-2008 | 56 années | rund um koln\|GER |
| s2698 | GP du Canton d'Argovie - Gippingen | UCI Europe Tour | 45 | 1964-2008 | — | gp gippingen\|SUI |
| s2699 | Philadelphia International Championship | UCI America Tour | 24 | 1985-2008 | — | the philadelphia cycling classic\|USA |
| s2700 | Tre Valli Varesine | UCI Europe Tour | 87 | 1919-2008 | 1943-1944, 1982 | tre valli varesine\|ITA |
| s2701 | GP de Fourmies | UCI Europe Tour | 76 | 1928-2008 | 1940, 1942, 1944-1945, 1966 | gp de fourmies la voix du nord\|FRA |
| s2702 | Milano-Torino | UCI Europe Tour | 90 | 1876-2007 | 42 années | milano torino\|ITA |
| s3053 | Tour de Vendée | UCI Europe Tour | 29 | 1980-2008 | — | tour de vendee\|FRA |
| s3055 | GP Le Samyn | UCI Europe Tour | 39 | 1968-2008 | 1988, 2005 | ename samyn classic\|BEL |
| s3056 | Nokere Koerse | UCI Europe Tour | 63 | 1944-2008 | 1959, 1962 | danilith nokere koerse\|BEL |
| s3057 | Dwars door Vlaanderen | UCI Europe Tour | 63 | 1945-2008 | 1971 | dwars door vlaanderen a travers la flandre\|BEL |
| s3058 | Brabantse Pijl | UCI Europe Tour | 48 | 1961-2008 | — | de brabantse pijl la fleche brabanconne\|BEL |
| s3059 | Paris-Bourges | UCI Europe Tour | 54 | 1913-2008 | 42 années | paris bourges\|FRA |
| s3292 | Cholet - Pays de Loire | UCI Europe Tour | 31 | 1978-2008 | — | cholet pays de loire\|FRA |
| s3294 | Hel van het Mergelland - Volta Limburg Classic | UCI Europe Tour | 31 | 1977-2008 | 2001 | volta limburg classic\|NED |
| s3295 | Grand Prix Pino Cerami | UCI Europe Tour | 43 | 1964-2008 | 1993, 1997 | grand prix pino cerami\|BEL |
| s3296 | Paris - Camembert | UCI Europe Tour | 73 | 1906-2008 | 1907-1933, 1940-1941, 1945 | paris camembert\|FRA |
| s3297 | G.P. Città di Lugano | UCI Europe Tour | 24 | 1981-2008 | 1997-2000 | g p citta di lugano\|SUI |
| s3300 | Halle - Ingooigem | UCI Europe Tour | 61 | 1945-2008 | 1948-1950 | halle ingooigem\|BEL |
| s3301 | Belgian National Championships | National Championships | 109 | 1894-2008 | 1906, 1915-1918, 1944 | **null** |
| s3302 | Dutch National Championships | National Championships | 113 | 1888-2008 | 1897-1903, 1905 | **null** |
| s3307 | GP Stad Zottegem | UCI Europe Tour | 73 | 1934-2008 | 1940, 1944 | gp stad zottegem\|BEL |
| s3308 | Druivenkoers - Overijse | UCI Europe Tour | 48 | 1961-2008 | — | druivenkoers overijse\|BEL |
| s3309 | Schaal Sels | UCI Europe Tour | 82 | 1921-2008 | 1922, 1939-1940, 1944-1945, 1996 | schaal sels merksem johan museeuw classic\|BEL |
| s3310 | GP Jef Scherens | UCI Europe Tour | 42 | 1963-2008 | 1966-1968, 1989 | grote prijs jef scherens rondom leuven\|BEL |
| s3311 | Memorial Rik Van Steenbergen | UCI Europe Tour | 18 | 1991-2008 | — | **null** |
| s3312 | GP de Wallonie | UCI Europe Tour | 49 | 1935-2008 | 1940-1941, 1945-1948, 1951-1969 | grand prix de wallonie\|BEL |
| s3313 | Flemish Championship | UCI Europe Tour | 93 | 1908-2008 | 1914-1918, 1939-1940, 1944 | kampioenschap van vlaanderen\|BEL |
| s3315 | Omloop van Het Houtland | UCI Europe Tour | 63 | 1945-2008 | 2002 | omloop van het houtland\|BEL |
| s3317 | Nationale Sluitingprijs | UCI Europe Tour | 75 | 1929-2008 | 1939-1942, 1944 | nationale sluitingprijs putte kapellen\|BEL |
| s3337 | Clásica de Almería | UCI Europe Tour | 17 | 1992-2008 | — | clasica de almeria\|ESP |
| s3543 | Coppa Agostoni | UCI Europe Tour | 62 | 1946-2008 | 1962 | coppa agostoni giro delle brianze\|ITA |
| s3546 | Coppa Bernocchi | UCI Europe Tour | 87 | 1919-2008 | 1931, 1943, 1984 | coppa bernocchi\|ITA |
| s3547 | Trofeo Melinda | UCI Europe Tour | 17 | 1992-2008 | — | **null** |
| s3609 | Binche-Tournai-Binche | UCI Europe Tour | 22 | 1911-1996 | 1913-1921, 1928-1929, 1931-1983 | binche tournai binche\|BEL |
| s3722 | Grand Prix d'Ouverture La Marseillaise | UCI Europe Tour | 29 | 1980-2008 | — | grand prix cycliste de marseille la marseillaise\|FRA |
| s3724 | Trofeo Palma de Mallorca | UCI Europe Tour | 17 | 1992-2008 | — | trofeo palma\|ESP |
| s3725 | Trofeo Cala Millor | UCI Europe Tour | 17 | 1992-2008 | — | trofeo alcudia port d alcudia\|ESP |
| s3726 | Trofeo Inca | UCI Europe Tour | 17 | 1992-2008 | — | **null** |
| s3727 | Trophée Deià | UCI Europe Tour | 17 | 1992-2008 | — | **null** |
| s3728 | Trofeo Magaluf-Palmanova | UCI Europe Tour | 16 | 1992-2008 | 1996 | **null** |
| s3729 | Trofeo Laigueglia | UCI Europe Tour | 45 | 1964-2008 | — | trofeo laigueglia\|ITA |
| s3736 | Grand Prix de Denain | UCI Europe Tour | 50 | 1959-2008 | — | gp de denain porte du hainaut valenciennes metropole\|FRA |
| s4024 | New Zealand National Championships | National Championships | 18 | 1990-2008 | 1993 | **null** |
| s4033 | Chrono des Herbiers | UCI Europe Tour | 27 | 1982-2008 | — | chrono des nations\|FRA |
| s4056 | Ster van Zwolle | UCI Europe Tour | 48 | 1961-2008 | — | **null** |
| s4070 | Giro del Friuli | UCI Europe Tour | 29 | 1974-2004 | 1997, 2000 | **null** |
| s4073 | Omloop van het Waasland | UCI Europe Tour | 44 | 1965-2008 | — | omloop van het waasland\|BEL |
| s4074 | Kattekoers | UCI Europe Tour | 69 | 1934-2008 | 1940-1945 | kattekoers\|BEL |
| s4075 | Paris-Troyes | UCI Europe Tour | 60 | 1910-2008 | 39 années | paris troyes\|FRA |
| s4140 | Klasika Primavera de Amorebieta | UCI Europe Tour | 56 | 1946-2008 | 1948-1954 | klasika primavera de amorebieta\|ESP |
| s4141 | Giro dell'Appennino | UCI Europe Tour | 69 | 1934-2008 | 1940-1945 | giro dell appennino\|ITA |
| s4143 | Tro-Bro Léon | UCI Europe Tour | 25 | 1984-2008 | — | tro bro leon\|FRA |
| s4144 | Grand Prix Midtbank | UCI Europe Tour | 16 | 1992-2007 | — | **null** |
| s4181 | Omloop van Voorne-Putten | UCI Europe Tour | 20 | 1989-2008 | — | **null** |
| s4184 | A Travers le Morbihan | UCI Europe Tour | 32 | 1974-2008 | 1979, 1989, 2005 | grand prix du morbihan\|FRA |
| s4190 | Gran Premio Città di Camaiore | UCI Europe Tour | 42 | 1966-2008 | 1978 | **null** |
| s4195 | Gran Premio Industria e Commercio Artigianato Carnaghese | UCI Europe Tour | 18 | 1991-2008 | — | **null** |
| s4287 | Polynormande | UCI Europe Tour | 29 | 1980-2008 | — | la poly normande\|FRA |
| s9609 | Grand Prix de Rennes | UCI Europe Tour | 19 | 1990-2008 | — | **null** |

Courses mal ou pas rattachables : championnats du monde (une épreuve par pays hôte et par discipline dans notre index ; page du site = plusieurs courses : CLM, ligne, amateurs : à traiter à part), championnats nationaux de Belgique, des Pays-Bas et de Nouvelle-Zélande (absents de notre index), 14 courses disparues avant 2009 ou sans édition UCI 2011+.

## 5. Table des codes pays du site

Codes vus (33 + SCO), convertis en code projet par `PAYS_SITE_ISO3` : tous identiques à l'UCI sauf `SPA` -> `ESP` et `SWI` -> `SUI` (`GER`, `NED`, `DEN`, `SLO`, `LAT` identiques). Vus : AUS AUT BEL CAN CHI COL CRC CRO CZE DEN EST FIN FRA GBR GER HUN ITA JPN KAZ LAT LTU MDA MEX NED NOR NZL POL POR RUS SLO SPA SWE SWI UKR USA UZB VEN. **`SCO` (Écosse, 7 lignes au Tour 2003) non converti** (décision à prendre : `GBR` à l'UCI). La synthèse de la collecte liste `codes_pays_inconnus` : table à compléter après chaque passage réel, par vérification.

## 6. Volume et durée (extrapolation)

- Pause 2,2 s (mesuré : 12 pages en 24 s). Découverte : 1 page d'accueil + 1 calendrier par année ≤ 2008 (~130, de 1876 à 2008) + 1 page par course inconnue (~230) = ~360 requêtes ≈ 13 min.
- Éditions : ~8 000 pages ≈ 5 h (à étaler en passages de 50 min avec `--budget-min`, reprise automatique : une édition écrite n'est jamais relue ; la découverte est gratuite au passage suivant grâce aux calendriers en cache gzip).
- Transfert : pages de 50 à 280 Ko (course d'un jour ~60 Ko, Tour ~270 Ko) ≈ 600-700 Mo ; sortie JSON compacte ≈ 10 Ko par édition d'un jour, 40-160 Ko par course par étapes ≈ 100 Mo pour tout ≤ 2008. Option `--garder-html` : conserve les pages (gzip, ~20 % du volume) pour relire sans requête (dév.).

## 7. Collecte d'essai et concordance avec Wikidata

`python thesports.py --sortie <scratch> --depuis 1995 --avant 1999 --courses s43,s94,s96 …` : 12 éditions lues (Paris-Roubaix, Tour de France, Paris-Nice, 1995 à 1998), 4 013 lignes, 1 temps illisible (`t.s.t.`), 0 code pays inconnu après complément de la table. **Podium (3 premiers, dans l'ordre) = Wikidata (`historique/editions` + `coureurs.json`, 16/11/2026) pour les 12 éditions** (écarts de graphie seulement : « Andreï Tchmil » / « Andrei Tchmil », « Miguel Indurain » / « Miguel Indurain Larraya », « Santiago Blanco » / « Santiago Blanco Gil », « Marcelino García » / « Marcelino Garcia Alonso »). Profondeur Wikidata : podium seul ; the-sports.org apporte 49 à 138 lignes par classement général.

## 8. Points ouverts

1. **Identification des coureurs** : le site fournit un nom, un code pays, une équipe et un id interne `spf<N>`, pas de date de naissance. Le rapprochement avec nos `rider_id` (slug + naissance) est impossible sans la fiche coureur (1 requête chacune, ~10 000 coureurs ≤ 2008 : ~6 h, texte « born 11 December 1964 » non systématique, à tester) ou sans recouper nom + nationalité + équipe + saison. À décider avant l'étape 2 ; en attendant, `id_site` est conservé.
2. Formats de temps ambigus (points séparés 2006+, minutes seules 2003) : à lever éventuellement avec distance / vitesse du vainqueur (déterministe, non fait) ou à laisser vides.
3. Pages d'avant 1990 non explorées (profondeur, formats `u` / `h`, noms de colonnes) ; calendriers de 1876 à 1989 non lus.
4. `World Championships` : une page = plusieurs courses (CLM, ligne, amateurs, nom `epm`) : le filtre actuel garde les sections `autre` brutes ; sélection de la course en ligne élite à faire à l'étape 2.
5. Les 94 éditions de 1995 du scratch ont été écrites par une version antérieure du parseur : refaire une collecte complète, rien n'est à conserver de ces fichiers.
6. Les classements d'étape sont tronqués par le site (10 à 35 lignes) : ne pas les présenter comme complets.
