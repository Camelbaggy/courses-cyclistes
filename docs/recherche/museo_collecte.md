# Museo del Ciclismo (museociclismo.it) : collecte des classements de courses (étape 1 : collecteur seul)

Sonde et essais du **18/11/2026**, depuis le conteneur de développement. Code : `museo.py` (racine), tests `python museo.py --test`
(pages réelles allégées de `tools/fixtures/museo/`). Rien n'est écrit dans `data/` : sortie d'essai dans le dossier de travail, jamais
dans un dépôt. Réseau : ~300 requêtes en tout (≈ 85 d'exploration, 103 de découverte complète des listes, 33 + 40 + 24 d'essais de
collecte, 17 fiches de vérification), 3,2 s entre deux requêtes, aucune page demandée deux fois, aucun échec réseau, serveur toujours
joignable et rapide ce jour-là (page de 280 Ko comprise).

## Accord et politesse

- Accord du Museo del Ciclismo (association culturelle, curateur de l'archive : Paolo Mannini) obtenu par le propriétaire le 18/11/2026 :
  lecture par programme et affichage des données, crédit « Museo del Ciclismo ». Le pied de page du site dit « Tutti i diritti riservati »
  et que les données sont « il risultato di una ricerca bibliografica e storiografica » de l'auteur : le crédit est donc obligatoire.
- `robots.txt` (18/11/2026) : `Disallow` de `/test /paolo /aggiornamento /configuration /technica_lib /rss /bin /dev /etc /logs /tmp /usr /var
  /includes /technicalib` seulement, pas de `Crawl-delay`. Aucun de ces chemins n'est lu. Les classements d'étape passent par
  `/content/stats/GetTappaData.php` (point d'accès appelé par le JavaScript de la page d'édition, non interdit).
- User-Agent `courses-cyclistes (accord Museo del Ciclismo)`, `PAUSE_S = 3,2` (≥ 3 s), délai de lecture 90 s (`netutil.fetch_text(timeout=…)`,
  paramètre ajouté, défaut 30 s inchangé), 3 essais par page, **abandon propre du passage après 8 échecs de suite** (`etat.json` dit alors
  `termine: false` ; la reprise ne relit rien). Un 403 / 429 / challenge abandonne l'hôte (comportement commun de `netutil`).
- Piège : `GET /content/corse/index.php` répond par une redirection vers un hôte qui ne se résout pas (« Name or service not known »).
  Cette page n'est jamais utilisée ; les listes de courses sont lues sur leurs propres URL.

## Structure du site

Toutes les URL de données sont **lues dans les pages** ; la seule URL calculée est la pagination `index<N>.html` (motif des liens de la page 1
+ total « Pagina 1 di N »).

| Niveau | URL | Contenu |
|---|---|---|
| Listes de courses | `/content/corse/corse_in_linea/index.html`, `index2.html`… | 106 pages × 50 = 5 251 courses « Linea » (♂ et ♀) : n°, sexe, lien `/content/corse/corsa/<id>-<nom>/index.html`, `(début - fin)`, Tipo, pays (code à 3 lettres, vide pour certaines) |
| | `/content/corse/corse_a_tappe/…` | 24 pages, 1 177 courses par étapes |
| | `/content/corse/campionati_e_altro/…` | 32 pages : critériums (112 sur 5 pages vues), circuits, contre-la-montre, derny, montées, cyclo-cross, piste : **ignorées par défaut** (`--listes campionati` pour les lire). Les championnats nationaux sur route sont dans la liste Linea (« Road National Championship - Romania »). |
| Page de course | `/content/corse/corsa/<id>-<nom>/index.html` | onglet « Albo oro, edizioni, vincitori » = **toutes** les éditions (n°, année, date `jj.mm.aaaa` si connue, vainqueur + lien coureur, km, temps, vitesse) ; onglet Statistiche (AJAX, inutile) |
| Page d'édition | `…/edizioni/<n>/<cod>.html` (lien de l'albo) | entête (année, date, n°, départ, arrivée, km, **partants, arrivés**), onglet **Classifica** (tableau Pos. / Ciclista (NAZ) + id / Tempo / Distacco / Punti), onglet **Tappe** (étapes : cod, départ, arrivée, km, vainqueur, temps, vitesse, icône chronomètre = contre-la-montre), onglet Prove (vide sur les cas vus) |
| Classement d'étape | `/content/stats/GetTappaData.php?what=tappa_classifica&cod=<cod d'étape>` | même tableau ; l'URL est lue dans le script de la page d'édition ; `tappa_info` (date, 191 octets) et `tappa_classifica_generale` (général après l'étape) existent aussi, **non collectés** |
| Listes de coureurs | `/content/ciclisti/<professionisti\|dilettanti\|elite\|under23\|indipendenti\|juniores\|projunior>/index.html`, `index2.html`… | **professionisti : 726 pages (≈ 36 300 coureurs)** : Cognome, Nome, **date de naissance `jj.mm.aaaa`**, lieu, nationalité, id |
| Fiche coureur | `/content/ciclisti/ciclista/<id>-<nom>/index.html` | « Ciclista Professionista », « Nato a VARESE il 11 maggio 1972 », nationalité (drapeau + code), onglet **Squadre** = équipe **par année** (+ « Compagni di squadra »), onglet Palmares, statistiques (AJAX) |
| Équipes | `/content/squadre/<année>/index.html` (6 pages en 1996), `/content/squadre/squadra/<id>-<nom>/index.html` | 25 608 équipes-années ; page d'équipe-année = effectif (21 coureurs pour Gewiss-Playbus 1996), directeurs sportifs |

## Couverture mesurée (listes parcourues en entier : 130 pages, 6 428 courses)

- 5 807 courses hommes (621 ♀ écartées), dont **5 361 avec au moins une édition avant 2009** (4 470 Linea, 891 Tappe).
- Par pays de la course (hommes, avant 2009) : **ITA 2 248**, FRA 844, BEL 637, ESP 264, GER 106, POR 105, USA 102, NED 101, GBR 99, SUI 88,
  COL 50, ARG 45, AUS 45… (26 sans pays). Très forte part de courses locales italiennes, françaises et belges (« Coppa … », « G.P. … »).
- Par décennie de début : 1890 : 41, 1900 : 108, 1910 : 148, 1920 : 322, 1930 : 391, 1940 : 507, 1950 : 748, 1960 : 581, 1970 : 621,
  1980 : 594, 1990 : 611, 2000 : 685 (les courses démarrant en 2009 ou après ne sont pas comptées).
- Courses actives entre 1990 et 2008 : ITA 843, FRA 378, BEL 201, ESP 153, USA 98, NED 86, POR 77, GER 57, GBR 47, COL 46, SUI 42, ARG 41.
- Nombre d'éditions (borne haute = années entre première et dernière édition, donc trop grande pour les courses lacunaires) :
  **≈ 29 000 pour 1990-2008, ≈ 91 000 avant 2009**.
- Grandes épreuves présentes : Milano-Sanremo (1907-2026, 117 éditions), Il Lombardia (1905-2025), Tour de France (1903-2026, 113 éditions), Coppa
  Bernocchi (1919-2025, 106 éditions), Milano-Torino, Paris-Roubaix (deux fiches : 1896-2026 et 1910-1914), Tour de Vendée (deux fiches)…
  Rapprochement avec les séries suivies par le projet (`series_historiques.json`, 44 clés) par la clé exacte `collector.cle_edition(nom, pays)` : **26 sur 44**
  retrouvées (28 courses museo, 1 826 éditions ≤ 2008) ; 18 absentes pour cause de nom différent (« Ronde van Vlaanderen », « Gent-Wevelgem »,
  « Vuelta a España », « Omloop Het Nieuwsblad »…, noms de sponsors) : alias manuels à écrire, jamais devinés. La même course peut avoir
  **plusieurs fiches** (changement de nom ou période distincte) : l'`id` de course est la clé, pas le nom.
- **Niveau professionnel / amateur** : le site ne le donne **ni par course ni par édition** (aucun champ). Il n'existe que par **coureur** (listes
  professionisti, dilettanti, under23, elite, juniores… et entête de fiche « Ciclista Professionista »). Une course comme Coppa Ardigò, ou une
  « Coppa » locale, ne se distingue d'une classique que par son nom. La sélection des courses doit donc venir du projet : `--cles FICHIER` /
  `--suivies` (rapprochement exact avec les courses connues), `--courses`, `--pays`.

## Profondeur réelle (essai : Milano-Sanremo, Il Lombardia, Coppa Bernocchi, 1990-1999 = 30 éditions, 2 606 lignes)

| Course | Lignes classées par édition | Remarque |
|---|---|---|
| Milano-Sanremo | 110 à 206 (≈ 165 médian ; 175 arrivés pour 198 partants en 1996 : classement **complet**) | |
| Il Lombardia | 42 à 105 | |
| Coppa Bernocchi | 10 à 75 (« partants 148, arrivés 104 » en 1996 mais 40 lignes) | classement **partiel** : `partants` / `arrivés` de l'entête permettent de le mesurer |
| Tour de France 1996 | général final : 129 lignes (= 129 arrivés) ; **22 classements d'étape** de 129 à 197 lignes | 1 prologue, 21 étapes, 2 contre-la-montre individuels (icône chronomètre) |

Profondeur médiane de l'ensemble de l'essai : 65 lignes (min 10, max 206). Le classement final d'une course en ligne est donné intégralement quand
le site le possède, sinon tronqué sans signal autre que l'écart entre `arrivés` et le nombre de lignes.

Contenu d'une ligne : rang, **id du coureur** (lien), nom (prénom + NOM tel qu'imprimé), **nationalité à 3 lettres**, `Tempo` (rempli seulement sur le 1er en
général), `Distacco` (écart), `Punti` (vide dans tous les cas vus). **Pas d'équipe, pas de dossard, pas de statut (abandon, hors délai)** dans les classements.
Les codes de nationalité sont ceux du site : 5 codes hors de `netutil.FLAG_CODES` dans l'essai (CSI, DDR, LAT, TCH, URS ; `LAT` = Lettonie, déjà `LVA` chez nous :
table d'équivalences à écrire à l'intégration, comme `PAYS_SITE_ISO3` pour the-sports.org).

### Temps et écarts : ce qui est lu, ce qui reste ambigu

- Format unique rencontré : `7h 0' 27"` (heures `h`, minutes `'`, secondes `"`), 0 illisible sur 6 224 lignes. Le temps du 1er est absolu ; `Distacco` est
  l'écart au vainqueur (général du Tour 1996 : Ullrich `0h 1' 41"` = 101 s, cohérent avec la course).
- **Écart vide sur une ligne autre que le 1er : AMBIGU, donc jamais interprété** (`ecart_vide: true`, pas de `ecart_s`). Mesuré : 199 lignes sur 2 606 (7,6 %)
  des courses en ligne, toutes en tête de tableau (2e, 3e… : « même temps que le vainqueur » plausible). Mais les **classements d'étape du Tour 1996** ont
  917 écarts vides sur 3 618 lignes, **y compris en fin de tableau** (16 étapes sur 22 où des vides suivent des valeurs) : hors délai ou temps inconnu ?
  La synthèse du collecteur compte ces cas (`ecarts_vides_non_prefixe`). Le temps d'un coureur n'est donc **jamais recalculé** ici ; l'intégration
  pourra dériver `temps = temps_vainqueur + écart` quand l'écart est présent, rien de plus.
- Dates d'étape quasi toujours vides dans l'onglet Tappe (`date_brut` absent) ; `tappa_info` les donne (1 requête de plus par étape, non fait).

## Dates de naissance et fiches coureurs

- **Listes** `professionisti` (échantillon de 4 pages = 196 coureurs réparties de A à Z) : **180 dates complètes (92 %)**, 2 années seules, 14 sans rien. Une
  seule requête donne 50 coureurs avec date, lieu et nationalité : **726 requêtes ≈ 39 min** pour tous les professionnels (`--listes-coureurs professionisti`),
  contre une requête par coureur pour les fiches. Seule une date `jj.mm.aaaa` valide est `precision: "jour"` ; `00.00.1950`, `31.02.1990` ne sont pas des dates.
- **Fiches** : 40 + 17 fiches lues dans l'essai : **57 sur 57 avec date complète** (« 11 maggio 1972 »), lieu, nationalité, catégorie « Professionista » ; l'onglet
  Squadre donne l'équipe **par année** (ex. Colombo : Gewiss - Playbus 1996, Cantina Tollo 1999-2001…), ce qui est la **seule** source d'équipe du site pour un coureur
  d'une édition (`--equipes`).
- **Concordance des dates avec Wikidata** (cache publié `entites/historique/coureurs.json`, naissance au jour, rapprochement par nom normalisé) : **31 rapprochés,
  31 identiques**, 0 différent (26 coureurs sans correspondance Wikidata). Les homonymes restent à traiter à l'intégration (nom + date de naissance).
- L'`id` du site est stable (même id dans le classement, la liste et la fiche).

## Concordance avec les palmarès Wikidata publiés (`entites/courses/<lettre>.json`, champ `historique`)

- **Vainqueurs : 20 sur 20 identiques** (Milano-Sanremo 1990-1999 : 10/10 ; Il Lombardia 1990-1999 : 10/10).
- **Podiums** : 17 sur 20 identiques ; les 3 autres ne diffèrent que par l'orthographe d'un nom (Rolf SORENSEN / Sørensen, Alexandre / Alexander GONTCHENKOV,
  Charles / Charly MOTTET) : mêmes personnes.
- Coppa Bernocchi : aucune série `historique` publiée (pas dans `series_historiques.json`) : rien à comparer, mais les 10 vainqueurs 1990-1999 sont plausibles
  (ex. 1996 : Fabio Baldato, déjà vu à Milano-Sanremo) ; le classement existe sur 10 à 75 lignes alors que Wikidata n'a rien.
- Le museo apporte donc, pour ces classiques, **le classement complet** là où Wikidata n'a que le podium, avec une concordance parfaite sur ce qui se recoupe.

## Volume et durée (3,2 s par requête)

| Poste | Requêtes | Durée |
|---|---|---|
| Découverte (listes Linea + Tappe) | 130 | 7 min |
| Une course (albo) | 1 | |
| Une édition en ligne | 1 | |
| Une édition par étapes (Tour de France) | 1 + 1 par étape (22) | 75 s |
| Listes de coureurs professionisti | 726 | 39 min |
| Une fiche coureur | 1 | |
| Essai 3 classiques × 10 éditions | 33 | 2 min |
| Fiches des coureurs de cet essai | ≈ 810 (807 coureurs distincts) | ≈ 43 min |
| **Toutes les éditions 1990-2008, tous pays (≤ 29 000)** | ≈ 29 000 + albos (≈ 3 000) | ≈ 28 h |
| Toutes les éditions avant 2009 (≤ 91 000) | ≈ 91 000 | ≈ 80 h |
| Séries suivies seules (26 clés, 1 826 éditions ≤ 2008 ; 492 pour 1990-2008) | ≈ 1 850 (500) | ≈ 1 h 40 (27 min) |

Taille : ≈ 80 octets de JSON compact par ligne de classement ; 31 éditions (dont le Tour 1996 avec ses étapes) = 492 Ko pour 6 224 lignes. Estimation 1990-2008, tous
pays : 29 000 éditions × ≈ 50 lignes × 80 o ≈ **115 Mo** (≈ 15 Mo en gzip). `courses.json` (index des 6 428 courses + éditions des courses lues) : 1 Mo.
`coureurs.json` : ≈ 350 octets par coureur avec équipes (≈ 36 300 pros ≈ 10 Mo).

## Données écrites par `museo.py` (`ARCHIVES_DIR/sources/museo/`)

- `courses.json` : `{source, listes, courses: {id: {nom, slug, debut, fin, type, pays, sexe, liste, editions: [{n, cod, annee, date?, url, vainqueur?, echecs?}]}}}`.
- `editions/<id course>/<année>.json` (suffixe `-<cod>` si deux éditions la même année) : entête (`nom`, `annee`, `date`, `n`, `depart`, `arrivee`, `km`, `partants`, `arrives`,
  `pays`, `type`, `cod`), `classement` (lignes `{rang, id, nom, nat, temps_s?, temps_brut?, ecart_s?, ecart_brut?, ecart_vide?, points_brut?}`), `etapes` (`{cod, numero, clm?, depart,
  arrivee, km, vainqueur, temps_s, vitesse_kmh, classement}`), `vainqueur_albo`, `source_url`, `lu_le`, `stats`.
- `coureurs.json` : `{id: {cognome, nome | nom (fiche), naissance, precision, lieu, nat, categories (listes), categorie (fiche), equipes: [{annee, id, nom, pays}], url, lu_le, fiche_lue}}`.
- `urls_coureurs.json` (id -> chemin de fiche, lu dans les classements), `listes_coureurs.json` (progression par liste), `etat.json` (`termine`, `editions_restantes`,
  `coureurs_restants`, sans horodatage), `cache/` (listes en gzip).

Options : `--sortie`, `--avant 2009`, `--depuis`, `--courses` (id ou nom exact), `--suivies`, `--cles FICHIER`, `--pays`, `--listes linea,tappe[,campionati]`, `--relire`, `--budget-min`,
`--max-requetes`, `--decouverte-seule`, `--sans-etapes`, `--sans-fiches`, `--equipes`, `--listes-coureurs professionisti[,dilettanti…]`. Reprenable : une édition écrite n'est jamais relue,
les étapes restantes le sont une fois, un album ou une édition en échec est abandonné après 3 essais (`echecs`).

## Points ouverts

1. **Niveau des courses** : aucune donnée par course ; décider quelles courses collecter (clés d'édition de `entites/courses`, liste blanche manuelle d'`id`, ou ensemble
   pro d'après la part de coureurs « professionisti » dans les classements, à mesurer une fois `coureurs.json` rempli).
2. **Équipe d'un coureur dans une édition** : seulement via la fiche (équipe par année) ; ambiguïté possible si un coureur a deux équipes la même année (non vu).
3. **Écarts vides** (voir plus haut) ; **tableaux tronqués** (Bernocchi) ; absence de statuts d'abandon.
4. Noms de course et de coureur : orthographes différentes de Wikidata / UCI ; alias manuels, jamais flous. Doublons de fiches de course (Paris-Roubaix, Tour de Vendée).
5. Étapes : dates (`tappa_info`) et classements généraux intermédiaires (`tappa_classifica_generale`) non collectés ; onglet « Prove » jamais vu rempli.
6. Intégration (étape 2) : table `nat` du site -> codes du projet (LAT, URS, TCH, DDR, CSI…), rapprochement coureurs (id museo -> `rider_id` par nom + naissance), champ de licence /
   crédit « Museo del Ciclismo » à l'affichage.
7. Charge : ≈ 28 h de requêtes pour 1990-2008 en entier, donc un workflow nocturne dans le dépôt d'archives (comme `thesports.yml`) : groupe de concurrence propre, sortie
   `data/archives/sources/museo/` seule, relance tant que `etat.json` dit `termine: false` ET que le passage a changé des fichiers.

## À reporter dans CLAUDE.md

> - **Museo del Ciclismo** (`museo.py`, `docs/recherche/museo_collecte.md`) : accord de l'association (curateur Paolo Mannini) obtenu par le propriétaire le 18/11/2026 pour lire
>   museociclismo.it par programme ET afficher ses données, crédit « Museo del Ciclismo ». Politesse : robots.txt respecté (jamais /test, /paolo, /includes, /bin, /var…), UA
>   « courses-cyclistes (accord Museo del Ciclismo) », ≥ 3 s entre requêtes (`PAUSE_S` 3,2), délai de lecture 90 s, aucune page demandée deux fois, abandon propre après 8 échecs de
>   suite. Découverte = listes `corse_in_linea` (106 pages) + `corse_a_tappe` (24) -> page de course (albo = toutes les éditions) -> page d'édition (`Classifica` : rang, id coureur, NAZ,
>   Tempo du 1er, Distacco ; `Tappe` : étapes dont le classement vient de `GetTappaData.php?what=tappa_classifica&cod=…`, URL lue dans le script) ; la pagination `index<N>.html` est la
>   seule URL calculée. **Pas de niveau pro / amateur par course** (seulement par coureur : listes `professionisti` 726 pages avec **date de naissance** `jj.mm.aaaa` + lieu + nationalité,
>   fiche `Nato a … il 11 maggio 1972`, onglet Squadre = équipe par année) : la sélection des courses vient du projet (`--cles`, `--suivies`, `--courses`, `--pays`). Classements en ligne
>   complets pour les classiques (110-206 lignes à Milano-Sanremo, 42-105 au Lombardia) mais parfois tronqués (Bernocchi 10-75 pour 104-148 arrivés). Temps `7h 0' 27"` seul format ;
>   **écart vide = ambigu, jamais interprété** (vide en tête ET en fin de tableau sur les étapes du Tour 1996). Pas d'équipe, de dossard ni de statut dans les classements. Concordance
>   Wikidata : 20/20 vainqueurs, 17/20 podiums (3 écarts d'orthographe), 31/31 dates de naissance. Sortie `ARCHIVES_DIR/sources/museo/` (`courses.json`, `editions/<id>/<année>.json`,
>   `coureurs.json`, `urls_coureurs.json`, `etat.json`, `cache/`) ; `museo.yml` du dépôt d'archives à écrire sur le modèle de `thesports.yml`. Tests : `python museo.py --test`.

## Sélection élargie (18/11/2026)

Décision du propriétaire : élargir la collecte au-delà des épreuves suivies, en suivant les règles du projet. Règles (`museo.construire_selection`, `--preparer-selection` hors réseau, `--selection`) :

1. id dans `alias_museo.json` `_championnats` (liste manuelle, vide au départ) -> `championnat`, toutes les éditions < 2009 ;
2. clé d'épreuve (`cle_edition` + « G.P. » -> « GP » + `alias_courses.json` + `alias_museo.json` `{id Museo: clé d'épreuve}`) dans `entites/courses/index.json` avec une classe actuelle WT / Pro / .1 / .2 -> `epreuve_suivie`, toutes les éditions < 2009 ;
3. hors index, 1999-2008 seulement, course présente au calendrier CQ Ranking de l'année (clé exacte, championnats NC / WC / CC / XX exclus) : en France -> `calendrier_uci_france` (édition de l'année retenue) ;
4. à l'étranger -> `calendrier_uci_top10` : édition retenue si un FRA (pays normalisés par `pays.py`) est dans le top 10 du général final / de la course, d'après le fichier CQ (0 requête Museo) sinon d'après la page Museo lue ; décision mémorisée par édition (`lue`, `ecartee`, `ecartee_cq`) : aucune page n'est redemandée ;
5. le reste : `sans_classe` (niveau inconnu, pas « amateur »), non collecté. Avant 1999 : règles 1 et 2 seulement. Aucune classe CQ n'est convertie (PT, GT, CDM, XPT : seule la présence au calendrier compte).

Chiffres de `selection.json` sur les données du 18/11/2026 (alias_museo vide) : 209 courses `epreuve_suivie` (~8057 éditions estimées, borne 9156), 0 `championnat`, 33 `calendrier_uci_france` (130 éditions), 241 `calendrier_uci_top10` (1041 éditions : a_decider 722, ecartee_cq 282, retenue 37), 4878 `sans_classe`.

### Propositions d'alias (à valider une à une ; `alias_museo.json` reste vide)

Produit par `tools/essais/proposer_alias_museo.py` (une page d'albo par candidate ; JSON complet : `museo_alias_proposes.json`). `preuve` = vainqueurs Museo concordants sur >= 2 années 2005-2008 avec une référence liée à l'épreuve par sa clé (Wikidata, calendrier CQ : type `cle`) ou, à défaut, avec le vainqueur CQ de même date et même pays lorsque le nom est aussi très proche (type `date_pays_cq`).

| Preuve | Id Museo | Course Museo (années) | Clé d'épreuve proposée | Classe | Années concordantes | Type |
|---|---|---|---|---|---|---|
| oui | 2751 | Clasica San Sebastian (1981-2026) | `donostia san sebastian klasikoa\|ESP` (+ `clasica ciclista san sebastian san sebastian\|ESP`) | WT | 2005, 2006, 2007, 2008 | cle |
| oui | 41416 | De Vlaamse Pijl Harelbeke (1968-2012) | `e3 harelbeke\|BEL` (+ `e3 prijs vlaanderen harelbeke\|BEL`, `record bank e3 harelbeke\|BEL`) | WT | 2006, 2007, 2008 | date_pays_cq |
| oui | 9954 | Dwars door Vlaanderen (1945-2026) | `dwars door vlaanderen a travers la flandre\|BEL` (+ `dwars door vlaanderen a travers les flandres\|BEL`) | WT | 2006, 2007, 2008 | date_pays_cq |
| oui | 2820 | In Flanders Fields (1934-2026) | `gent wevelgem in flanders fields\|BEL` | WT | 2005, 2006, 2007, 2008 | cle |
| oui | 9714 | Brabantse Pijl (1961-2025) | `de brabantse pijl la fleche brabanconne\|BEL` | Pro | 2006, 2007, 2008 | date_pays_cq |
| oui | 9787 | Circuit Franco-Belge - Eurometropole Tour (1924-2025) | `circuit franco belge\|BEL` | Pro | 2007, 2008 | cle |
| oui | 12802 | Danmark Rundt (1985-2022) | `post danmark rundt tour of denmark\|DEN` | Pro | 2006, 2007, 2008 | cle |
| oui | 11337 | G.P. Kanton Aargau Gippingen (1964-2024) | `gp du canton d argovie gippingen\|SUI` (+ `gp du canton d argovie\|SUI`) | Pro | 2006, 2007, 2008 | date_pays_cq |
| oui | 11440 | G.P. Miguel Indurain (1999-2026) | `gran premio miguel indurain\|ESP` | Pro | 2006, 2007, 2008 | date_pays_cq |
| oui | 22962 | G.P. de Wallonie (1935-2025) | `grand prix de wallonie\|BEL` | Pro | 2007, 2008 | date_pays_cq |
| oui | 2584 | G.P. du Morbihan (1990-2026) | `grand prix du morbihan\|FRA` | Pro | 2006, 2007, 2008 | cle |
| oui | 31649 | Munsterland Giro (2000-2025) | `sparkassen munsterland giro\|GER` | Pro | 2007, 2008 | date_pays_cq |
| non | 92772 | Eschborn-Frankfurt U23 (1998-2024) | `rund um den finanzplatz eschborn frankfurt\|GER` | WT | 2008 | - |
| non | 92726 | G.P. Copenhagen Classic (2008-2009) | `copenhagen sprint\|DEN` | WT | 2008 | - |
| non | 110260 | G.P. de Plouay Elite Open (2002-2026) | `gp ouest france plouay\|FRA` | WT | - | - |
| non | 1488 | Giro di Romagna (1910-2025) | `giro di lombardia\|ITA` | WT | 2007, 2008 | - |
| non | 63010 | Lombardia Tour (2006-2008) | `giro di lombardia\|ITA` | WT | 2008 | - |
| non | 61576 | Omloop Het Nieuwsblad voor Beloften & elite z-c (1950-2018) | `omloop het nieuwsblad elite\|BEL` | WT | - | - |
| non | 55936 | Tour of California (2006-2019) | `amgen tour of california\|USA` | WT | - | - |
| non | 22529 | Vuelta Ciclista a Navarra (1941-2008) | `la vuelta ciclista a espana\|ESP` | WT | - | - |
| non | 195493 | Vuelta Ciclista a Salamanca (1935-2019) | `la vuelta ciclista a espana\|ESP` | WT | - | - |
| non | 2535 | 4 Jours de Dunkerque (1955-2025) | `4 jours de dunkerque grand prix des hauts de france\|FRA` | Pro | - | - |
| non | 92812 | Ardèche Classic (2001-2026) | `faun ardeche classic\|FRA` | Pro | 2008 | - |
| non | 63376 | Brussel-Opwijk (1951-2006) | `parijs brusssel paris bruxelles\|BEL` | Pro | - | - |
| non | 62014 | Bruxelles-Zepperen (1975-2020) | `parijs brusssel paris bruxelles\|BEL` | Pro | - | - |
| non | 184559 | Circuit du Morbihan (1975-2023) | `grand prix du morbihan\|FRA` | Pro | - | - |
| non | 1303 | Coppa Sabatini (1952-2025) | `coppa sabatini gran premio citta di peccioli\|ITA` | Pro | 2007 | - |
| non | 2956 | G.P. Industria e Artigianato - Larciano (1977-2025) | `gp industria artigianato\|ITA` | Pro | 2006, 2007, 2008 | - |
| non | 97227 | Giro dei Tre Ponti (1931-2014) | `giro del trentino\|ITA` | Pro | - | - |
| non | 60089 | Giro del Casentino (1910-2022) | `giro del trentino\|ITA` | Pro | 2006 | - |
| non | 11816 | Japan Cup (1992-2024) | `japan cup cycle road race\|JPN` | Pro | 2007, 2008 | - |
| non | 64024 | Paris-Tours espoirs (1943-2025) | `paris tours elite\|FRA` | Pro | 2007, 2008 | - |
| non | 8157 | Philadelphia Cycling Classic (1985-2026) | `philadelphia international championship\|USA` | Pro | 2007, 2008 | - |
| non | 68439 | Presidential Tour of Turkey (1965-2026) | `56 presidential cycling tour of turkey\|TUR` | Pro | - | - |
| non | 8323 | Tour de Langkawi (1996-2025) | `petronas le tour de langkawi\|MAS` | Pro | - | - |
| non | 6266 | Tour de Luxembourg (1935-2025) | `skoda tour de luxembourg\|LUX` | Pro | - | - |
| non | 13191 | Volta a Portugal (1927-2026) | `volta a portugal em bicicleta edp\|POR` | Pro | - | - |
| non | 52789 | Vuelta a San Juan (1982-2023) | `vuelta a san juan internacional\|ARG` | Pro | - | - |

Remarques : plusieurs clés d'index peuvent désigner la même course Museo (changements de nom) : `alias_museo.json` n'en porte qu'une, les autres dénominations restent des épreuves distinctes. Museo 41416 (De Vlaamse Pijl Harelbeke) concorde avec les vainqueurs d'E3 mais Museo 4533 (E3 Saxo Classic) est déjà sélectionnée par clé : doublon probable, `collisions` de selection.json à examiner avant de valider. Sans candidate (57 épreuves, dont la plupart sont postérieures à 2008) : liste `epreuves_sans_candidate` du JSON.

### Championnats (clé `_championnats`, à valider)

| Preuve | Id Museo | Course Museo | Années concordantes (CQ, classe officielle) |
|---|---|---|---|
| oui | 2634 | World Championship Road Race (1927-2025) | 2007, 2008 |
| non | 34548 | Olympic Games Road Race (1896-2021) | - |
| oui | 20739 | Road National Championship - France (1907-2026) | 2006, 2007, 2008 |
| non | 180623 | African Continental Championship - Road Race (2005-2024) | 2008 |
| oui | 176524 | Asian Championship Road Race (1999-2019) | 2007, 2008 |
| non | 233912 | Oceania Championship Road Race (1995-2026) | - |
| oui | 58073 | Pan American Championship Road Race (1974-2026) | 2006, 2008 |

Championnats : preuve par la classe CQ officielle (WCRR monde, NC France, CC continentaux) à la même date. Jeux olympiques : une seule édition 2005-2008 (2008), donc pas de preuve possible ; Océanie : aucune édition datée 2005-2008 trouvée ; Afrique : une seule année concordante. Les championnats nationaux d'autres pays ne sont pas proposés (règle du projet : seulement en France). Le championnat d'Europe élite sur route n'existe pas avant 2016 (aucune édition < 2009).
