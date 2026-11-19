# Cyclingnews, archives de résultats 1998-2008 : accès, couverture, format et proposition de collecteur (étude du 19/11/2026)

Accord : Cyclingnews a autorisé le propriétaire du projet, le 19/11/2026, à lire ses **archives de résultats** par programme et à afficher les résultats, avec le crédit « Cyclingnews ». Le flux RSS (`cyclingnews.py`) reste réservé à l'IA (texte intégral jamais republié) : l'accord ne le concerne pas. Étude sans collecteur (étape 0). Rien n'est intégré à `encyclopedie.py` ni à la page.

Mesures : ~125 requêtes au total (dont ~25 échecs ou reprises de requêtes CDX, 28 pages rejouées), >= 4,2 s entre requêtes, User-Agent « courses-cyclistes (accord Cyclingnews) », arrêt sur 429 (jamais reçu). Le conteneur de développement n'atteint pas `web.archive.org` (tunnel fermé, seul `archive.org/wayback/available` répond) : tout est mesuré depuis GitHub Actions avec la sonde `tools/essais/essai_cyclingnews.py` (`[essai:cyclingnews]`, variable `ETAPE`, 8 étapes successives ; conservée comme référence, à supprimer quand le collecteur existera). Une page a parfois été demandée deux fois (gpkranj08, alentejo085) pour imprimer l'HTML brut après l'avoir mesurée. Extraits réels allégés : `tools/fixtures/cyclingnews_archives/` (reconstitués depuis les journaux de la sonde : en-tête et lignes de tête / queue du `<pre>`, pas les pages entières).

## 1. Où sont les pages

- **Le site de Cyclingnews ne les sert plus.** `https://autobus.cyclingnews.com/road.php?id=road/2008/may08/gpkranj08` répond 301 vers `https://www.cyclingnews.com/road/` ; `autobus.cyclingnews.com/` -> 301 vers la page d'accueil moderne ; `www.cyclingnews.com/road.php?id=…` -> 404. Il n'existe aucun sous-domaine ni chemin d'archive vivant (confirme `sources_avant_2009.md` §7). `www.cyclingnews.com/robots.txt` ne dit rien contre nous (une règle `Disallow: /` vise des robots d'IA nommés), mais on ne lit pas ce site.
- **Wayback Machine (Internet Archive) : tout y est**, captures de 1999 à 2026 sur des URL `autobus.cyclingnews.com` (et `www.cyclingnews.com` / `cyclingnews.com` pour 1998-2004). Rejeu du contenu brut : `https://web.archive.org/web/<horodatage>id_/<url d'origine>` (un horodatage partiel, ex. `2010`, redirige vers la capture la plus proche). Les pages reconstituées sont les **dernières versions du site** (captures de 2012 à 2026 pour 2003-2008 ; 1999-2000 : captures de 1999 à 2003 du site d'époque). Liste : API CDX `https://web.archive.org/cdx/search/cdx?url=<préfixe>&matchType=prefix&fl=timestamp,original,statuscode&collapse=urlkey&output=txt&limit=N`.
- Comportement de l'Internet Archive observé : requêtes CDX de plus de ~20 000 lignes -> 502 (`limit=400000` échoue, `limit=20000` passe) ; 504 de temps en temps ; **« Connection refused » en rafale** après une dizaine de requêtes CDX rapprochées (récupéré en attendant 60-75 s) ; les rejeux `id_` passent presque toujours (2 échecs de connexion sur 28, `status 0`, probablement passagers : Roubaix 2005 et Roubaix 2003 de la page de course). Aucun 429. `archive.org/robots.txt` interdit seulement `/control/` et quelques chemins : pas d'obstacle ; rester courtois (>= 4,5 s, une seule connexion).

## 2. Structure des pages et découverte (sans deviner d'URL)

Il existe **deux familles de pages en 2003-2008** et un **ancien format 1998-2002**.

**Famille A, `road.php?id=road/<AAAA>/<mmm>AA/<slug>[/<slug><N>|/default]`** (courses de second rang, petites courses et locales : GP Kranj, Alentejo, Sarthe, Paris-Roubaix Espoirs…). Une course d'un jour = une page `<slug>` ; une course par étapes = un dossier `<slug>/` avec `default` (page principale : liste de départ, présentation, parfois le général) et une page par étape `<slug>1`, `<slug>2`… (la dernière donne aussi le général final, voir §4). Mois en `jan`… `dec` + `AA` (`may08`), dossiers spéciaux `transfers08`, `natchamps08`, `worlds04`… Les pages locales de clubs ont un préfixe pays (`road/AUS/2005/apr05/...`, `road/UK/...`) : hors sujet.

**Famille B, `/road/<AAAA>/<mmm>AA/<slug>/?id=results[/<étape>]`** (courses principales : Paris-Roubaix, Amstel, Lombardia, Milan-San Remo, Flandres, Paris-Nice, Tirreno, Dauphiné, Romandie, Suisse, Eneco, Pologne, Langkawi, Tour Down Under…). Une « page de course » par course avec onglets `?id=results`, `startlist`, `history`, `map`, `photos`, `live`, `features` ; pour une course par étapes les classements sont `?id=results/<slug><N>` (ex. `parisnice08/?id=results/parisnice080`). Mois spéciaux (`worldcup03/parisroubaix03` en 2003).

**Ancien site 1998-2002** (hôtes `www.cyclingnews.com` / `cyclingnews.com` / `autobus.cyclingnews.com`, chemin `/results/<AAAA>/<mmm>AA/<course>.html|.shtml`, ex. `results/1999/apr99/parisroubaix99results.html`, `results/2000/apr00/amstel/amstelresults.shtml`, `results/2001/apr01/amstel/results.shtml`) : un mélange de pages de courses, de brèves (`apr1.shtml`), de cartes, de départs et de photos ; 2002 est mixte (`results/2002/2002resultsFRA.html` par pays + pages `road.php` de la famille A).

**Découverte** : il n'y a **pas de page d'index par mois exploitable**. `/results/?id=2008/may08` est un calendrier de courses *locales* (13 liens en mai 2008, aucune course UCI : le texte renvoie aux « calendriers UCI » séparés) ; `archiveindex.php` ne liste que 2000-2002 ; la page `road.php` (accueil, 135 Ko, ~1 070 liens) ne mène qu'aux courses du moment. **La seule liste complète est la CDX** (préfixes `autobus.cyclingnews.com/road.php?id=road/<année>/` pour A, `autobus.cyclingnews.com/road/<année>/` pour B, `www.cyclingnews.com/results/<année>/` pour 1998-2002). On ne demande donc que des URL **présentes dans la CDX** (aucune URL devinée, aucun gabarit complété). Les pages d'étapes se retrouvent par la CDX et par les liens « Main Page » / « Previous Stage » de chaque page.

## 3. Couverture mesurée

CDX `collapse=urlkey`, statut 200 sauf mention, hôte `autobus.cyclingnews.com` :

| année | famille A : URL / dossiers (courses) | dont par étapes (> 2 pages) | famille B : courses (avec `?id=results` capturé) | ancien site : pages `.html` 200 hors brèves/photos |
|---|---|---|---|---|
| 1995-1997 | — | — | — | **0** (`results/1997/…` 404, `results/1995/…` 404) |
| 1998 | — | — | — | CDX non obtenue (refus) : ~2 070 URL toutes natures sous `results/1998/` |
| 1999 | — | — | — | 870 (sur 1 878 URL, 1 653 pages html) |
| 2000 | 1 | — | — | 1 719 (sur 3 879 URL) |
| 2001 | 0 | — | — | 2 013 (sur 4 792 URL) |
| 2002 | 183 / 174 (+ ~200 sur `www.`) | 0 | non mesurée | 874 (sur 1 564 URL, pays par pays) |
| 2003 | 1 672 / 594 | 181 | 38 (22) | — |
| 2004 | 1 520 / 701 | 154 | non mesurée | — |
| 2005 | 2 101 / 649 | 263 | 60 (48) | — |
| 2006 | 2 277 / 670 | 281 | non mesurée | — |
| 2007 | 2 161 / 620 | 276 | non mesurée | — |
| 2008 | 2 241 / 616 | 284 | 73 (65) | — |

- **Utilisable : 1999-2008** (1998 probable, à mesurer ; 1995-1997 absents des archives). Qualité de capture : 97-99 % de statuts 200 (2008 : 51 en 301, 5 en 503, 11 « - », 1 en 404 sur 2 241) ; une seule course sans aucune page 200 en 2008, deux en 2007. Les 301 sont à suivre une fois.
- **Nombre de courses hommes élite route** (UCI + régionales) : les dossiers de la famille A mélangent tout (dames `rvv_w08`, juniors `parisroubaixjuniors08`, espoirs `U23rvv08`, clubs, critériums US, courses d'Asie…). Estimation grossière : ~600 dossiers A + ~70 courses B par an en 2005-2008, dont peut-être 40 à 60 % d'épreuves UCI hommes élite (le h1 de la page donne la classe UCI, voir §4 ; l'ordre de grandeur est à confirmer par comptage sur pages réelles au premier passage). 2003-2004 : moins de captures de la famille B (38 courses en 2003).
- **La famille B est la vraie valeur** (World Cup, ProTour, HC : classiques et grands tours du calendrier). Elle est absente de `road.php` : une CDX sur `road.php?id=road/` seule la manquerait (c'est ce qui est arrivé aux premières mesures : Roubaix / Amstel / Flandres / Lombardia 2008 introuvables dans la famille A, présents en B). Courses B vues en 2008 : Roubaix, Amstel, Lombardia, Milan-San Remo (`msr08`), Flandres (`rvv08`), Gand-Wevelgem, Liège (`lbl08`), E3, Het Volk (`hetvolk`), Paris-Nice, Tirreno, Catalogne, Pays basque, Romandie, Dauphiné, Suisse, Eneco, Pologne, San Sebastián, Plouay, Vattenfall, Montréal, Californie…

## 4. Format des classements

Page HTML (windows-1252 déclaré par `<META … charset=windows-1252>`, en-tête HTTP iso-8859-1 : décoder en **cp1252**, `netutil.fetch_text(encoding="cp1252")`). Pages de 18 à 70 Ko (cadre de navigation, photos, publicités). La partie utile est très stable (famille A comme B, 2003-2008) :

```
<h1 align="center"> 35th GP Kranj - 1.1</h1>            <- nom + CLASSE UCI (« 1.1 », « 2.1 », « 1.2 (Jr) »…)
<h2 align="center">Slovenia, May 31, 2008</h2>            <- pays (en toutes lettres, anglais), date(s)
<h3>Stage 5 - April 13: Évora - Évora , 186.2 km</h3>     <- étapes seulement
<h3><a name="res"></a>Results - 161.6 km</h3>
<pre>1 Grega Bole (Slo) Adria Mobil                          3.45.56 (42.92 km/h)
2 Jure Kocjan (Slo) Perutnina Ptuj
9 Eddy Serry (Ita) Miche - Silver Cross                    0.05
DNF Fabian Angermair (Aut) Tyrol - Team Radland Tirol
</pre>
<h3><a name="past"></a>Past winners</h3><pre>2007 Borut Boic (Slo) Team L.P.R. …</pre>
```

- **Une ligne = rang, prénom nom, `(Nat)`, équipe, temps** (rang d'un seul jeton : `1`, `DNF`, `DNS`, `OTL`, `HD`, `DSQ`…). Le **coureur est un texte libre** : pas d'identifiant, **pas de date de naissance**, nationalité en code de 3 lettres entre parenthèses, de casse variable (`Slo`, `GBr`, `NZl`, `RSA`) ou sans parenthèses (`Dragan Spasic SRB Srbija`). L'équipe est du texte libre (noms de club de plusieurs mots, parfois absente). Aucun dossard.
- **Temps** : le 1er porte un temps absolu `H.MM.SS` ou `MM.SS` suivi parfois de la vitesse `(42.92 km/h)` ; les suivants un **écart** `M.SS` / `MM.SS` / `H.MM.SS` (`0.05`, `3.39`, `29.35`) ; **cellule vide = même temps que la ligne précédente** (vérifié sur Kranj : rangs 10-18 vides après `0.05` puis `0.10` au rang 19 ; Roubaix 2008 : `3.57`, vide, `3.59`). Même règle que DataRide, pas la règle de CQ Ranking (vide = temps du 1er). Les classements par équipes donnent des temps absolus (`58.32.40`), les points « `73 pts` » (classements par points, ProTour), les grimpeurs des points entiers. Aucune seconde bonification signalée.
- **Pages d'étape** (famille A et B) : un seul `<pre>` qui enchaîne l'étape et tous les classements annexes, séparés par des lignes `&nbsp;` et des intertitres `<b>…</b>` : « Points classification », « Mountains » (+ « Category 4, km 59.30 »), « Metas volantes / intermediate sprint », « Teams », « Final classification », « Points classification », « Mountains classification », « Teams » (alentejo085 : 303 lignes, étape + général + annexes). Les intertitres sont libres (anglais, parfois autre langue) : à classer par table de mots, jamais deviner.
- **Page de course B** : un `<pre>` de résultats puis un deuxième pour les classements annexes (Amstel 2008 : classement ProTour, classement par pays) précédé d'un intertitre `<h4>`.
- **Anciens formats 1999-2002** : rangs suivis d'un point (` 1. Andrea Tafi (Ita) Mapei-Quick Step  6.44.15`), tableaux de points (Roubaix 1999 : classement Coupe du monde), listes de départ en deux colonnes (`1. Franco Ballerini (Ita)	11. Johan Museeuw (Bel)`) : plusieurs `<pre>` dont un seul est le classement ; titres libres (aucun h1 normalisé constaté). Format de temps `6.44.15` / `2.14`. **À étudier plus avant** avant de s'engager sur 1999-2002 (pas d'échantillon plus large lu).
- **Défauts de la source** : accents perdus ou mutilés dans les noms (`Botjan Rezman` pour Boštjan, `Gorazd tangelj` pour Štangelj, `Bla un`, `Ino Ileic Aldo` pour Aldo Ino Ilešić), ordre prénom / nom parfois inversé (`Panayotov Peter`, `Baugnies Jerome`), pays écrit `SRB` sans parenthèses, classes UCI absentes de certaines pages anciennes, lignes de commentaire (« Results courtesy of ciclismotoscano.it ») dans le `<pre>`, tabulations en fin de ligne. Les HTML contiennent des entités (`&nbsp;`, `&amp;`, `&#39;`).

**Profondeur réelle** (échantillon, pages de 2005-2008) :

| course | Cyclingnews | CQ Ranking (fichier local) |
|---|---|---|
| Paris-Roubaix 2008 (B) | 113 classés, aucun DNF listé | 113 lignes |
| Amstel 2008 (B) | 184 lignes dont DNF / DNS | 146 |
| Il Lombardia 2008 (B) | 167 lignes dont DNF | 94 |
| Paris-Nice 2008, étape 0 (B) | 490 classés | — |
| GP Kranj 2008, 1.1 (A) | liste complète + DNF (≥ 55 lignes lues sur ~100) | 105 |
| Paris-Roubaix Espoirs 2008, 1.2 (A) | **84 classés + HD** | **20** |
| GP Sats 2005 (A, Danemark) | 62 lignes | — |
| Pavé de Roubaix juniors 2005 (A) | 43 | — |
| Alentejo 2008 étape 5, 2.1 (A) | ~90 + général (~100) + annexes | — |

Pour 2005-2007 CQ Ranking se limite aux places à points (Roubaix 2005 : 80 lignes, Espoirs 2005 : 20). **Cyclingnews donne des classements complets, y compris pour des .1 / .2 et des étapes**, avec les abandons (DNF / DNS / OTL / HD / DSQ). C'est l'apport principal : profondeur 2 à 4 fois supérieure pour les petites courses, abandons absents de CQ.

**Dates de naissance : aucune** (confirmé). Les coureurs ne se rattachent donc que par nom + nationalité + équipe + année, comme pour Mémoire du Cyclisme.

## 5. Concordance avec CQ Ranking et Wikidata (échantillon)

Contrôle sur 5 courses de 2008 avec fichier CQ local (`sources/cqranking/courses/2008/`) : **vainqueur, podium et temps du vainqueur identiques sur 5 sur 5** :

- Roubaix 2008 : Boonen (QST) 5.58.42, Cancellara (SUI, CSC), Ballan (ITA, LAM). Écart de 1 s : Cyclingnews donne `0.01` au 2e, CQ « vide » (même temps que le 1er) ; deux sources, deux valeurs : à ne pas trancher.
- Amstel 2008 : Cunego (LAM) 6.35.29, F. Schleck (CSC), Valverde (+2 s : `0.02` / `02"`).
- Lombardia 2008 : Cunego 5.37.04, Brajkovic (+24 s : `0.24` / `24"`), Uran.
- GP Kranj 2008 : Bole 3.45.56, Kocjan, Ilešić (« Ino Ileic Aldo » côté Cyclingnews contre `ILESIC Aldo Ino` chez CQ : rapprochement par nom impossible sans normalisation des accents et sans ordre).
- Roubaix Espoirs 2008 : Vermeltfoort 4.21.21 (NED, RB3), 2e ITA, 3e SUI.

**Wikidata** (cache local `entites/historique/`, sans requête) : Amstel 2008 et Il Lombardia 2008 ont le même vainqueur (`Q316910`), cohérent avec Cunego des deux côtés ; Roubaix 2008 a le même QID de vainqueur que Roubaix 2005 (Boonen) ; cohérent aussi avec CQ. Je n'ai pas lu les libellés Wikidata : à refaire proprement par `historique.py` avec le rapprochement (nom + année) au premier passage. L'échantillon est petit (classiques majeures et deux petites courses) et choisi : il ne dit rien des petites courses sans autre source, ni des anciens formats 1999-2002 (aucun contrôle fait).

## 6. Pièges

- **Pas d'identifiant ni de naissance** : tout coureur devra être rapproché d'une autre source (CQ Ranking, Museo, the-sports.org) par nom normalisé + nationalité + année + équipe ; les noms mutilés (accents, ordre) imposent une normalisation prudente et un statut « non rapproché » plutôt qu'une devinette. Étape 2 (hors collecteur).
- **Deux familles de pages, une seule jamais listée par `road.php`** : oublier la famille B perd les classiques majeures.
- **CDX capricieuse** : 502 au-delà de ~20 000 lignes, 504, refus de connexion en rafale ; pagination par `limit` modeste + reprise ; vérifier qu'une année « vide » n'est pas un échec (1995-2001 sur `road.php` = 0 URL, mais l'ancien site en a ; 1998 : requête refusée, à refaire).
- **Plusieurs captures d'une même URL** : `collapse=urlkey` garde la première ; la plus ancienne n'est pas forcément la plus complète (pages 1999-2003 capturées sur le site d'époque, 2012-2026 sur le site final). Choix à faire : dernière capture 200 (`filter=statuscode:200`, tri inverse) ou première ; à vérifier sur un échantillon (non fait). Doublons d'hôte (`:80`, `http` / `https`, `cyclingnews.com` / `www.`) : `urlkey` les fusionne.
- **Statuts** : 301 (~2 %, suivre une fois), 503 / « - » (ignorer), 404.
- **Course introuvable ≠ course absente** : la capture manquante n'est pas une preuve d'absence de la course. La CDX est une liste de captures, pas un calendrier : aucune complétude ne peut être garantie (comparer au calendrier CQ de l'année).
- **Pages non-résultats** : brèves, cartes, listes de départ, photos, journaux de bord portent le même chemin ou un chemin voisin ; filtrer par présence d'un `<pre>` dont la majorité des lignes valent `rang nom (Nat) équipe` et d'un h1 / h3 reconnu, sinon ignorer.
- **Étapes** : numérotation `<slug>N` sans zéro, `default` = page principale, parfois `…0` (Paris-Nice 08 : `parisnice080` = prologue) ; ne jamais calculer l'URL suivante, lire la CDX.
- **Hommes élite** : aucun marqueur de sexe explicite hors du slug (`_w`, `women`) ou du h1 ; « (Jr) », « U23 », « Espoirs », « juniors » dans le nom ou le slug. Filtre prudent : garder seulement les pages dont le h1 porte une classe UCI hommes élite (`1.HC`, `2.HC`, `1.1`, `1.2`, `2.1`, `2.2`, `PT`, `CM`…) sans « (Jr) », « Women », « U23 », « Espoirs » ; le reste est compté, pas écrit.
- **Politesse** : l'Internet Archive n'a pas de consigne chiffrée trouvée ; > 4,5 s entre requêtes, arrêt net après 5 refus consécutifs, relance ultérieure ; l'accord de Cyclingnews porte sur le contenu, pas sur l'infrastructure de l'Internet Archive : rester discret, ne pas multiplier les connexions.

## 7. Volume et durée

- Pages à lire (1999-2008, hommes élite route + tout le reste non filtré à la découverte) : famille A 2003-2008 ≈ 12 000 URL (dont ~3 000 de pages `default`), 2002 ≈ 400, famille B ≈ 6 × 600 à 1 500 (à mesurer ; onglets `results` seulement), ancien site 1999-2002 ≈ 5 500 pages (borne haute, brèves comprises). **Total 15 000 à 25 000 requêtes** de pages, plus ~40 requêtes CDX. À 4,5 s : **19 à 31 h, soit 23 à 37 passages de 50 min** (`--budget-min`, reprenable). Avec le filtre hommes élite à la découverte (seule la classe du h1 donne l'information : elle exige de lire la page) : le tri se fait *après* lecture, donc le coût est celui du total ; seule la réduction par motif de slug (`_w`, `u23`, `junior`, dossiers locaux avec préfixe pays) économise des requêtes (~20 %).
- Taille : 20-70 Ko d'HTML par page mais ~3 Ko de JSON utile ; pour 15 000 à 25 000 pages **45 à 75 Mo** non compressés (~12 à 20 Mo gzippés), même ordre que CQ Ranking. Ne pas conserver l'HTML (cache optionnel `--garder-html` seulement pour rejouer l'analyseur).

## 8. Proposition de collecteur (`cyclingnews_archives.py`, étape 1 : lecture et stockage seulement)

- **Périmètre** : 1999-2008, en commençant par **2003-2008 famille B** (classiques et grands tours : la valeur la plus sûre et la plus lisible), puis famille A 2003-2008, puis 1999-2002 (ancien format, après une étude plus large du format). `--depuis` / `--avant`, `--familles A,B,ancien`, `--courses <motif de slug>`. Hommes élite route : critères du §6, le reste est compté dans `etat.json` (`ecartees`), pas écrit.
- **Accès** : exclusivement `web.archive.org` en rejeu `id_` (jamais `autobus.cyclingnews.com`, qui redirige), 4,5 s entre requêtes (`PAUSE_S` 4,6), UA « courses-cyclistes (accord Cyclingnews) », 429 -> attente du `Retry-After` puis arrêt si répété, « Connection refused » -> pause de 60 s puis reprise (3 tentatives, puis passage arrêté), `netutil.fetch_text(encoding="cp1252")`.
- **Découverte** : CDX par année et par famille (`limit=5000`, pagination par `resumeKey`, pause de 10 s, `filter=statuscode:200`), écrite telle quelle dans `cdx/<famille>-<année>.json` (jamais refaite pour une année `complete` ; relue après 90 jours si on veut les captures récentes). Aucune URL calculée.
- **Analyse** (fonction pure, tests sur `tools/fixtures/cyclingnews_archives/`) : h1 -> `nom`, `classe` (suffixe `- 1.1`), `(Jr)` ; h2 -> `pays_texte`, dates ; h3 `Stage N - mois jour : départ - arrivée, km` ; `<pre>` -> lignes `rang nom (nat) équipe temps` ; détection d'intertitres `<b>` ; temps = absolu pour la 1re ligne, écart ensuite, vide = même temps que la ligne précédente (même résolution qu'`uci.py` pour DataRide : `ecart_s` cumulatif) ; formats de temps non reconnus comptés, jamais devinés.
- **Sortie** `ARCHIVES_DIR/sources/cyclingnews/` : `cdx/`, `courses/<année>/<famille>/<slug>.json` = `{url, capture, famille, slug, annee, nom, classe, jr, pays_texte, debut, fin, km, pages: [{type jour|etape|general|annexe, libelle, etape, date, depart, arrivee, km, temps_s, lignes: [[rang, nom, nat_site, equipe, brut, ecart_s]], abandons: [...], commentaires}], source, lu_le}`, `etat.json` `{termine, urls_restantes, cdx_restantes, ecartees, formats_inconnus}` (sans horodatage, lu par un `cyclingnews.yml` du dépôt d'archives sur le modèle de `cqranking.yml` : cron nocturne, groupe `cyclingnews-data`, commit seulement de `sources/cyclingnews/`, auto-relance si `termine: false` et progrès), `introuvables.json` (URL en échec définitif).
- **Pays** : `nat_site` = code brut entre parenthèses (`Slo`, `GBr`, `NZl`) ; `nat` = `pays.pays_normalise(code, "cyclingnews")` (table `sources.cyclingnews` à créer dans `pays_historiques.json` : casse, `GBr` -> GBR, `SRB` / `Srb`, `Ger`…, `Swi` -> SUI…), code inconnu = absent et compté.
- **Étape 2 (hors collecteur)** : rattachement des courses (clé d'épreuve : h1 + pays texte + année, `alias_courses.json`), des coureurs (nom normalisé + nat + année + équipe, contre CQ / Museo / the-sports.org) et fusion de classements concurrents (Cyclingnews plus profond, CQ plus fiable sur les identifiants : à décider avec le propriétaire, ne rien trancher en silence quand les temps divergent d'une seconde).
- Tests : `python cyclingnews_archives.py --test` (fixtures), `--decouverte-seule`, `--max-requetes N`, `--relire`.

## 9. Points ouverts

- Mesurer 1998 et les années B 2004, 2006-2007 ; compter les épreuves hommes élite réelles (classe du h1) sur un échantillon de 100 pages.
- Lire un échantillon plus large de l'ancien format 1999-2002 (aucun h1 normalisé, temps en `H.MM.SS`, tableaux de points mêlés) avant de s'engager sur ces années.
- Choix de la capture (première / dernière) et fréquence des différences entre captures d'une même URL.
- Recoupement systématique des vainqueurs avec Wikidata (`historique.py`) et CQ sur toutes les courses lues, pas sur 5.
- Cas des 301 et des deux échecs de rejeu (Roubaix 2005 et 2003, page de course) : réessayer.
- Crédit à ajouter côté page : « Cyclingnews » (accord du 19/11/2026).

## À reporter dans CLAUDE.md

Fait dans la même modification (paragraphe « Cyclingnews, archives de résultats » et mise à jour de la ligne RSS).
