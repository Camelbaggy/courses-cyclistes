# Sonde 2 : sites d'organisateurs (ASO, RCS), DirectVélo, LNC, Cyclingnews

Sonde exécutée depuis GitHub Actions le 8 novembre 2026 (`tools/sondes/sonde_orga.py`, 4 itérations, historique git pour les
versions intermédiaires). User-Agent : `courses-cyclistes-sonde/0.1 (projet personnel non commercial)`. robots.txt lu et appliqué
avant chaque requête (jokers `*` et `$` gérés), pause de 1,2 s entre requêtes (10,5 s pour DirectVélo, qui déclare
`Crawl-delay: 10`). Aucun 403 ni challenge rencontré sur ces sources ; aucun contournement tenté. Tout ce qui est écrit ici a été
observé dans les logs, sauf mention « non vérifié ».

Remarque : les pages ASO servaient le Tour de France « 2027 » (étape 21 terminée) alors que l'horloge du runner indiquait
novembre 2026. Les données des pages ne sont pas recoupées ici ; seule la structure compte. Seule l'édition courante de chaque
site a été testée : l'accès aux éditions antérieures (archives) n'est pas vérifié.

## Synthèse

| Source | Données utiles | Technique | robots.txt | CGU | Verdict |
|---|---|---|---|---|---|
| ASO (letour.fr, paris-nice.fr, dauphiné/Tour AURA, paris-roubaix.fr, liège, paris-tours.fr, lavuelta.es) | classements complets (étape, général, points, montagne, jeune, équipes, combativité), parcours, récits | HTML rendu côté serveur, tableaux `<table>` | autorisé (hors `/api`, `/graphql`, `/*/ajax`, `/*/block`, `/*/login`, `/*/sitemap`) | **interdit** : art. 3.15 des CGU, robots/extraction sans consentement écrit préalable | **techniquement excellent, juridiquement bloqué** : demander l'autorisation écrite à ASO ; sinon ne pas utiliser |
| RCS (Strade Bianche, Tirreno, Milano-Sanremo, Lombardia, Giro) | classements dans des `<div>`, parcours, récits | HTML serveur, pas de `<table>` | autorisé (`/wp-admin/` seul interdit) | **non lues** | exploitable techniquement ; lire les CGU RCS avant tout usage |
| DirectVélo | classements complets des courses françaises, fiche course, récit, direct | HTML serveur, `<table>` | autorisé, `Crawl-delay: 10` | **interdit** : reproduction même partielle sans accord écrit, droits de producteur de bases de données | **non utilisable sans accord écrit** |
| LNC (lncpro.fr) | classements complets des courses pros françaises, classement FDJ United Series | HTML serveur, `<div>` | autorisé | mentions légales sans clause d'extraction détectée (à relire) | **meilleure source pour les .1/.Pro françaises** |
| Cyclingnews RSS | texte intégral d'articles | RSS 2.0 | autorisé pour un bot générique | page Future lue, aucune clause explicite trouvée (texte court) ; robots.txt bloque nommément des crawlers d'IA | utilisable comme matière première avec prudence (accord à demander) |

## A. ASO

### URL validées (HTTP 200)

- Classements, structure commune à tous les sites ASO : `https://www.<site>/fr/classements/etape-<N>/<code>` (la version anglaise
  du Tour est `https://www.letour.fr/en/rankings/stage-<N>`). `…/fr/classements` seul renvoie le général de la dernière étape.
- Codes de classement (confirmés dans `data-types` de la page) : étape `ite` (+ `ipe`, `ime`, `ije`, `ete`), général `itg`,
  points `ipg`, montagne `img`, jeune `ijg`, équipes `etg`, combativité `ice` (ou `icg` sur la Vuelta).
- Vérifiés : letour.fr étape 10 (`itg`, `ipg`, `img`, `ijg`, `etg`, `ite`, `ice`), paris-nice.fr étapes 1 et 8
  (`itg`, `ipg`, `img`, `ijg`, `etg`, `ite`, `ice`), criterium-du-dauphine.fr étape 8 (`itg`, `ipg`, `etg`, `ice`),
  lavuelta.es étape 21 (`itg`, `ipg`, `etg`, `ice`), paris-roubaix.fr/fr/classements, liege-bastogne-liege.be/fr/classements.
- Les onglets de la page passent par `/en/ajax/ranking/...` (interdit) mais **ne sont pas nécessaires** : chaque code a sa
  propre URL, rendue côté serveur.
- Sites : le Dauphiné est désormais servi par `criterium-du-dauphine.fr` sous le titre « Tour Auvergne-Rhône-Alpes 2026 ». Paris-Tours :
  `https://www.paris-tours.fr/` répond 200 (non creusé). `fleche-wallonne.be`, `parisstours.fr` et variantes : DNS inexistant ou
  certificat invalide (non trouvés).

### Structure d'un tableau

Un seul `<table>` par page. En-têtes : `Rang | Coureur | Dossard | Équipe | Temps | Écart | B | P` (général et étape), `… | Points | P`
(points, montagne), `Rang | Équipe | Temps | Écart | P` (équipes), `Rang | Coureur | Dossard | Équipe` (combativité).
HTML d'une ligne (Tour) : `<tr class="rankingTables__row …">` avec la position, la photo, un `<span data-bib="#1" class="flag … "
data-class="flag--slo">` (**nationalité en code pays à 3 lettres**), le lien coureur `/fr/coureur/1/uae-team-emirates-xrg/tadej-pogacar`,
le lien équipe `/fr/equipe/UEX/…` (code d'équipe), puis temps, écart, bonification (`B : 10''`), pénalité.
Noms abrégés sur le Tour et la Vuelta (`T. POGACAR`), complets sur Paris-Nice et le Dauphiné (`JONAS VINGEGAARD`). Sur la Vuelta, une
colonne supplémentaire (numéro d'équipe) s'intercale après le dossard.

### Complétude

Classements complets, pas de top N : Tour étape 10 = 175 coureurs (176 lignes avec en-tête), points 100, montagne 43,
jeune 39, équipes 23, étape 175 ; Paris-Nice général étape 8 = 89 ; Dauphiné 91 ; Vuelta 142 ; Paris-Roubaix 139 ; Liège 105.
Combativité : une seule ligne. Pages lourdes (jusqu'à 780 ko).

### Parcours et étapes

- Tour : `https://www.letour.fr/fr/etape-N` / `https://www.letour.fr/en/stage-N` ; le menu de la page donne distance, type et dénivelé
  (« Stage 10 Annecy > Sallanches Length 171 km Type Mountain D+ 3750 m »). `https://www.letour.fr/en/overall-route` : tableau
  `Stage | Type | Date | Start and Finish | Distance`. Le tableau horaire de la page étape est quasi vide sur le Tour.
- Paris-Nice : `/fr/parcours-general` (tableau étape/type/date/départ-arrivée/distance) et `/fr/etape-8` : tableau horaire de 49
  lignes (km, passages) plus bloc « montagne » (`Col de la Porte`, `Km 50.7 - 1057m`, `7km de montée à 7.2%`) et barème des points
  par col. Bon pour les cols.
- Paris-Roubaix `/fr/etape-1` : tableau de 187 lignes avec les 30 secteurs pavés (« Début du secteur pavé de Troisvilles à Inchy
  (N° 30) », longueur en mètres, km restants).
- Récits : fil « Film de l'étape » en HTML avec articles complets (`/fr/actus/2026/etape-8/vingegaard-la-grande-razzia/25347` :
  plusieurs paragraphes de récit rédigé) et interviews. Le fil en direct passe par `/fr/ajax/news/...` : **interdit par robots.txt**.
  `https://www.letour.fr/en/live` : 404. Pas de live texte autorisé.

### Conformité

- robots.txt : accès autorisé à tout ce qui précède. Même robots.txt sur letour.fr, paris-nice.fr et le Dauphiné (+ blocage nominal
  de `meta-webindexer` et `meta-externalagent`).
- **CGU (`/fr/mentions-legales`, art. 3.15)** : interdit « d'utiliser un robot, un agent numérique, … une application d'extraction ou
  d'analyse du web … permettant d'extraire, d'indexer, d'explorer des données, ou de … reproduire … le Site ou son contenu sans notre
  consentement écrit préalable », sauf moteurs de recherche publics pour l'indexation. L'art. 4 réserve à ASO les droits sur
  « bases de données … contenus ». robots.txt permet donc ce que les CGU interdisent. Le projet s'impose de respecter les CGU : **ne
  pas collecter sans accord écrit d'ASO**.

### Verdict ASO

La meilleure source technique (complète, homogène sur toutes les épreuves ASO, nationalité, bonifications, cols, secteurs pavés, récit).
Elle est utilisable uniquement après autorisation écrite d'ASO (demande à formuler pour usage personnel non commercial). Sans
accord : écarter.

## B. RCS (Gazzetta)

URL vérifiées (200) : `https://www.tirrenoadriatico.it/classifiche/?classifica=CLGEN` (aussi `CLGENGIO`, `CLGPMGEN`, `CLPUNGEN`,
`CLSQAGEN`), `…/classifiche/di-tappa/7`, `https://www.strade-bianche.it/archivio-classifiche/u/2026/` (hommes, `/d/` femmes),
`https://www.milanosanremo.it/archivio-men-2026/`, `https://www.ilombardia.it/archivio-classifiche/2026/`,
`https://www.giroditalia.it/classifiche/` (+ `/classifiche/di-tappa/21`), pages `/percorso…`. `strada-bianche.it` n'existe pas : le bon
domaine est `strade-bianche.it`. Pas de `<table>` : classement en `<div>` (`class="name p-3"` prénom, `class="surname p-3 is-bold"` nom,
`class="team p-3"` équipe + lien `/squadre/<slug>/`, puis temps/écart/points). Le sélecteur (onglets
`tab-classifica-CLGEN`…) est rendu côté serveur : tous les onglets sont dans la même page (Tirreno : 274 noms en 5 onglets ;
Giro : 538 en 9 onglets, dont `CLCOMGEN` combativité, `CLPUIGEN`, `CLFUGGEN`). Strade Bianche : environ 115 lignes (classement
complet des arrivants). Les classements des classiques sont archivés par édition ; la page étape de Tirreno affiche aussi le podium
et un texte « La gara in breve » (récit court rédigé). Nationalité : non vue dans le texte (drapeaux en images, non vérifié).
Parcours : pages `percorso` en HTML (contenu non détaillé ici). Pas d'URL de live texte (`milanosanremo.it/live/tappa/1` : 404 ; les
PDF de classement officiels sont aussi liés dans `/wp-content/uploads/…pdf`).
robots.txt : `Disallow: /wp-admin/` seulement. **CGU RCS non lues** (pied de page : « Copyright 2026 © RCS Sport », à lire avant
usage). Verdict : bonne source pour Strade Bianche, Tirreno, Milano-Sanremo, Lombardia, Giro, plus lourde à parser que l'ASO
(div, pas de table), à n'utiliser qu'après lecture des CGU.

## C. DirectVélo

- robots.txt : bloc générique `User-agent: *` avec `Disallow: /casino/ /jeu/ /recherche/` et **`Crawl-delay: 10`** (appliqué).
- URL vérifiées : `/calendrier/2026/08`, `/resultats/2026-10-11` (liste du jour, podiums), `/epreuve/48914/paris-tours-2026`,
  `/epreuve/48961/la-polynormande-2026`, `/direct/6313/la-polynormande-2026`, `/coupe-de-france/2026/dn1`, `/mentions-legales`.
- Fiche course : départ, arrivée, distance (168,9 km), heure de départ, catégorie (1.1), moyenne (44,106 km/h) et **classement complet**
  dans un `<table>` : Polynormande 123 coureurs, Paris-Tours 165. Colonnes : Place | Coureur | Équipe | points | temps (temps du
  vainqueur puis écarts, ex. `0" 3h49'46"`) | âge | challenge ; pas de nationalité ni de dossard. Liens vers la start-list
  (« les partants ») et les éditions précédentes. Récits : articles d'actualité (`/actualite/<id>/<slug>`, ex. « FDJ United Series 11 classements »)
  et page « Direct » avec présentation de la course. Couverture : amateurs N1-N3, pros, femmes, juniors, cyclo-cross ; les courses
  .1/.2/Pro françaises y sont, ainsi que les Coupes de France (les Coupe de France N1 sont des classements amateurs).
- **Mentions légales** : « Toute reproduction, distribution, modification, adaptation, retransmission ou publication, même partielle,
  de ces différents éléments est strictement interdite sans l'accord exprès par écrit de DirectVelo » ; DirectVelo se déclare aussi
  « propriétaire des droits des producteurs de bases de données ». Liens profonds restreints.
- Verdict : riche mais **non utilisable sans accord écrit** (association à but non lucratif, contact possible).

## C bis. LNC (lncpro.fr), alternative française

- robots.txt : Drupal standard, seuls `/core/`, `/profiles/` et fichiers README interdits. Mentions légales
  (`/index.php/mentions-legales`, 21 ko) : aucun terme « robot / extraction / reproduction / propriété intellectuelle » détecté par la
  sonde (à relire à la main).
- URL : `https://www.lncpro.fr/resultats` (liste paginée `?page=N`, filtres `french_cup=1`, `type=one_day_race|stage_race`,
  `uci_ranking=…`), `https://www.lncpro.fr/resultats/<slug>` (ex. `la-polynormande`, `paris-tours-elite`, `tour-de-vendee`,
  `gp-de-fourmies-la-voix-du-nord`, `bretagne-classic-ouest-france`, `tour-de-france`), `/fdj-united-series`, `/calendrier`.
- Page course : date, classe (1.1, 1.Pro), classement complet sans `<table>` (lignes `div` `result-item-header` : rang, coureur
  `NOM, Prénom`, pays, équipe, temps ou points ; Paris-Tours : 165 lignes, temps `4:31:46`, écarts `+00:00:02`) et classement général
  FDJ United Series (Polynormande : points par coureur). Liste de la page `/resultats` : vainqueur, temps, équipe pour chaque course
  du calendrier pro. Résultats du Tour de France et des championnats de France inclus. Pas de récit de course (vidéos replay, articles
  d'actualité LNC).
- Verdict : **source recommandée pour les courses pros françaises** (FDJ United Series, Paris-Tours, Tour de Vendée…) si les mentions
  légales sont confirmées.

## D. Cyclingnews RSS

- `https://www.cyclingnews.com/feeds.xml` (alias `/rss`) : 200, 1,2 Mo, **50 items couvrant 3 jours** (4-7 novembre 2026). `/racing/feeds.xml`
  et `/pro-cycling/feeds.xml` : 404 (les pages sont rendues mais sans flux).
- Item : `title`, `link`, `guid`, `pubDate`, `dc:creator`, `description` (extrait ~210-330 caractères), **`dc:content` et
  `content:encoded` : texte HTML intégral de l'article** (3 000 à 13 600 caractères ; l'article témoin du flux fait 8 349 caractères de
  texte pour 18 409 sur la page entière avec ses menus : le flux contient bien le corps), `media:*`, `enclosure`, `category` multiples
  (`Pro Cycling` 38/50, `Racing` 23, `Teams & Riders`, `Women's Cycling`, `Transfers`, `Rules`…). Pas de balise « course » ou
  « coureur » : filtrage par catégorie `Racing` + mots du titre (nom de course, d'équipe, de coureur). Tableaux de résultats parfois
  inclus (`table` dans `dc:content`).
- Couverture limitée dans le temps : à interroger souvent (toutes les heures) pour ne rien perdre pendant les courses.
- robots.txt : `User-agent: *` interdit seulement des motifs techniques (`*q=*`, `*/comments/*`, …) ; des crawlers d'IA nommés
  (bytespider, cohere, anthropic non cité, etc.) sont bloqués. Cyclingnews et futureplc.com ont la même politique.
- CGU : `cyclingnews.com/terms-and-conditions/` : 404. Renvoi vers `https://futureplc.com/terms-conditions/` (60 ko de HTML mais 2 658
  caractères de texte) : aucune clause sur le scraping, l'IA ou la syndication trouvée par la recherche de motifs ; texte à relire.
- Verdict : exploitable comme matière première des résumés (jamais republié) pour les courses du moment, avec accord écrit
  conseillé vu le blocage des crawlers d'IA ; le contenu en anglais complète bien un dossier factuel UCI/organisateur.

## Recommandations

1. Résultats : demander à ASO (puis à RCS et DirectVélo) une autorisation écrite pour un usage personnel non commercial ; en attendant,
   s'appuyer sur la source UCI (autre sonde) et LNC pour les courses françaises.
2. Si ASO accepte : un seul parseur couvre toutes les épreuves ASO (`/fr/classements/etape-N/<code>`), prévoir 2-3 s de pause, ne jamais
   toucher aux URL `/ajax`.
3. Si RCS accepte : parseur `div` unique pour les sites WordPress Gazzetta.
4. Récit pour l'IA : Cyclingnews RSS (texte complet, 3 jours de profondeur) + récits ASO si autorisés. Ne jamais republier.
