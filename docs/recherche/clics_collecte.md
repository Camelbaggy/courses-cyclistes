# Clics sur le cyclisme : structure, couverture et collecte proposée (étape 0, étude sans collecteur)

Étude du 19/11/2026 : 79 requêtes réseau (dont 61 pages de coureurs, 11 pages d'index, `robots.txt`, `sitemap.xml`, accueil, `equipes.html`), 3,2 s entre requêtes,
User-Agent « courses-cyclistes (accord Clics sur le cyclisme) », cache local de chaque page. Écarts à la règle « aucune page demandée deux fois » : `robots.txt` lu deux fois
(refait pour la fixture) et une page de coureur (`gadret-john`) interrogée deux fois (HEAD puis GET, pour mesurer la compression). Pages réelles allégées : `tools/fixtures/clics/`.

Accord : obtenu par le propriétaire le 19/11/2026 pour lire `clicssurlecyclisme.net` par programme et afficher ses données, crédit « Clics sur le cyclisme ».
`robots.txt` : `User-agent: *` / `Allow: /` ; seuls MauiBot, MegaIndex.ru, Semrushbot-SA et HTTrack sont exclus, `Crawl-delay: 10` réservé à BLEXBot, MJ12bot et Seekport ;
`Sitemap: https://www.clicssurlecyclisme.net/sitemap.xml` déclaré. Aucune protection anti-robot rencontrée (HTTP/2 200, pas de challenge, pas de 429).

## 1. Ce que le site est réellement (et ce qu'il n'est pas)

Site e-monsite (Apache, UTF-8, `cache-control: no-cache`, **ni ETag, ni Last-Modified, ni compression** : chaque page se télécharge en entier, 300 à 680 Ko, moyenne 370 Ko).
Bandeau de l'accueil : « ARCHIVES CYCLISTES COMPETITIONS ROUTE, Résultats coureurs depuis… 1868 » et **« SITE EN RE-RECONSTRUCTION après l'arasement du 12 janvier 2021
(fin d'Adobe Flash Player) et la cessation d'hébergement du 31 juillet 2025 »**. Le site est en cours de migration : une partie seulement des pages est ici ; le reste des liens de
l'accueil renvoie vers des copies web.archive.org de l'ancien hébergement (`clicssurlecyclisme.xara.hosting`), hors de l'accord.

**Constat principal : le site est un annuaire de fiches de coureurs, pas une base d'équipes.** La rubrique « Equipes » (`/pages/equipes.html`) annonce « Mémoire du Cyclisme : Les compositions
d'équipes des années 1868…2016 » mais ses 148 liens (un par année) pointent tous vers **web.archive.org** (copie du 7 décembre 2024 de l'ancien `memoire-du-cyclisme.eu/pelotons/annee.php?a=AAAA`,
2014 et 2016 vers `equipes_maillots_AAAA.php`, 2015 sans lien). Aucune composition d'équipe n'est hébergée par Clics ; le « Lexique » A-Z renvoie lui aussi vers web.archive.org. Ces copies
n'ont pas été lues (hors accord Clics ; l'accord Mémoire du Cyclisme du 18/11/2026 vise `memoireducyclisme.fr` / `memoire-du-cyclisme.org`, pas une copie d'archive du `.eu`) :
**question au propriétaire**, voir §7.

| Niveau | URL (réelles) | Contenu |
|---|---|---|
| Accueil | `/` | présentation, liens vers `pages/index-<x>.html` (ceux qui existent déjà), vers `pages/equipes.html`, et vers web.archive.org pour le reste |
| Sitemap | `/sitemap.xml` (465 Ko, 3 244 URL, `lastmod` sur 3 222) | **la liste complète des pages migrées**, avec date de dernière modification (2025-12 → 2026-11, 103 pages modifiées en novembre 2026) |
| Index de plage | `pages/index-b.html`, `-c`, `-d`, `-e` (en réalité F), `-g`, `-h` (vide), `-i-j-k`, `-l`, `-m`, `-q-r`, `-s` | liste des pages d'une lettre : libellé « PREMIER - DERNIER » (`GAAL - GABARD Claude`) = lien vers la page |
| Page de coureurs | `pages/g/gabbai-tal-gabica-francesco.html` (plage), `pages/g/gallopin-tony.html` (coureur notable seul) | un tableau Excel exporté (4 colonnes, voir §2) : **tous les coureurs de la plage** alphabétique, ~19 en moyenne (1 à 45) |
| Dossiers de lettre | `pages/a/` … `pages/s/` (15, dans le sitemap) | non lus (listes de la même nature que les index) |

Découverte sans deviner d'URL : sitemap (déclaré dans `robots.txt`) puis, en contrôle, les pages d'index ; les URL de plage encodent les noms bornes (`-lowie-petrus-lowis.html`, certains slugs
commencent par `-`) et sont donc **instables** si le site redécoupe les plages : toujours repartir du sitemap, ne jamais reconstruire une URL. Les liens des index sont en `http://` : normaliser en `https://`.

## 2. Profondeur mesurée (pages de coureurs)

Structure : une seule `<table>` de 4 colonnes, un `<tr>` par ligne, 4 `<td>` (export Excel : chaque cellule porte 6 `<span style>` imbriqués, d'où 370 Ko pour ~190 lignes utiles ; une fois aplati,
une page pèse 30 Ko). Lecture positionnelle, sans identifiant ni ancre :

| Ligne | Col. 1 | Col. 2 | Col. 3 | Col. 4 |
|---|---|---|---|---|
| Nouveau coureur | `NOM Prénom` (nom en majuscules ; `X dit Y`) | pays en français (`FRANCE`, `ITALIE`, `G-B`, `AFN/FRANCE`, `KENYA/G-B`) | code libre éventuel (`CDP 149`, 7 sur 566) | `°jj-mm-aaaa [à lieu]` |
| Ligne d'état civil | vide | variante de nom | vide | `†jj-mm-aaaa [à lieu]` |
| Année | vide | vide | `1999` | **équipe de la saison**, éventuellement vide |
| Résultat | vide | vide | `jj-mm` | `1er du Grand Prix Alanya (Turq)` |

- Un nouveau coureur = col. 1 non vide. Attention : les **lignes de crédit** `Palmarès établi par` / `Claude Chatelier` sont en col. 1 au milieu de la fiche (avec une date ou une année en col. 3) : un analyseur naïf en fait deux faux coureurs.
- **Date de naissance** : écrite pour 32 % des coureurs (échantillon aléatoire de 520), jour complet (1 % seulement l'année, `°1813 ?`) ; lieu pour 17 % ; décès pour 7 %. **Très inégale selon l'époque** (année de la première saison du coureur) : avant 1940 15 % (168 coureurs), 1940-1979 12 % (171), **1980-1998 51 % (71), 1999-2008 79 % (57), depuis 2009 78 % (49)**. **Aucun identifiant** de coureur (pas de lien, pas d'ancre) ; 67 % des coureurs sont français, surtout amateurs.
- **Équipe par année** : 81 % des lignes-années ont une équipe ; format `SPONSORS-EQUIPEMENTIERS[/CLUB (dép.)][/CATÉGORIE][/MM STAGIAIRE ÉQUIPE]`, par exemple `COFIDIS-LOOK-VITTORIA/VC ETAMPES (91)`, `GO PASS ABX/Elite 2/08 STAGIAIRE FDJ.COM`, `/08 STAGIAIRE FLAMINIA-FONDRIEST` ; l'équipe d'une même saison est écrite à l'identique pour tous ses coureurs (`SAUR-SOJASUN-TIME-PANARACER`). 46 % des libellés contiennent un département `(NN)` (clubs amateurs), 36 % un `/`. Rien ne distingue formellement un professionnel d'un amateur (pas de code UCI, pas de niveau).
- **Résultats** : 6 par coureur en moyenne (sélection, pas exhaustif), en texte libre `Nè du <course> [(Pays)]`, `1er de la 4è étape du Tour d'Istambul (Turq)`, `abandon 13è étape du Tour de France`, `Leader du Tour du Qatar` (date `30-01/03-02`), `4 victoires en 1993 (North)` ; date `jj-mm` (`00-00` si inconnue), année prise sur la ligne d'année ; ni temps, ni écart, ni dossard ; mêle route, cyclo-cross, critériums et épreuves régionales.
- **Époques** : lignes-années de 1890 à 2026 (par décennie, échantillon : 1920 : 88, 1950 : 114, 1990 : 136, 2000 : 307, 2010 : 249, 2020 : 105). Avant 1940, 25 à 50 % des lignes-années n'ont pas d'équipe (coureurs de club).
- Pays en français et en mots, avec doubles nationalités séparées par `/` : il faut une table `sources.clics` dans `pays_historiques.json` (`ALLEMAGNE`, `G-B`, `PAYS-BAS`…, `AFN` = Afrique du Nord française) ; code inconnu = `nat` absent, jamais deviné.

## 3. Concordances mesurées

Échantillon : 61 pages de coureurs (36 tirées au hasard dans le sitemap + 7 coureurs notables + 23 pages de deux équipes + 3), 837 coureurs. Rapprochement : jetons du nom normalisés (`netutil.normalize`) + date de naissance au jour.

| Contrôle | Résultat |
|---|---|
| Dates de naissance Clics vs nos `entites/coureurs` (nom identique, même date) | **47 concordantes, 0 divergente** (141 coureurs absents chez nous : amateurs, avant 2009) |
| Idem contre Wikidata (`entites/wikidata/coureurs.json`, `naissance`) | 34 concordantes / 34 comparables (2 entrées de cache sans champ `naissance`) |
| Dates et décès contre `entites/historique/coureurs.json` (Wikidata) | 13 naissances et 2 décès concordants, 0 divergent |
| Dates contre CQ Ranking (`sources/cqranking/coureurs.json`, 1999-2008) | **32 concordantes, 0 divergente** (1 « divergence » = deux homonymes Anthony Geslin, 1980 et 1983, tous deux sur la page) |
| Équipe-saison 2009-2016 (217 couples coureur-saison de l'échantillon) vs nos `saisons[an].team` | **189 concordants (87 %)** (chevauchement de jetons >= 50 % entre le nom d'équipe et un segment du libellé Clics) ; 28 écarts : équipes nationales chez nous (`Ireland`, `France`, `Serbia`), clubs amateurs, noms différents (`Quickstep Cycling Team` vs `QUICK STEP-INNERGETIC-MERCKX-VITTORIA`, `Cofidis, le Credit EN Ligne` vs `COFIDIS-LOOK-VITTORIA`) |
| Équipe-saison 1999-2008 vs CQ Ranking (code d'équipe daté -> nom) | **127 concordants sur 141 (90 %)** ; les 14 écarts = stagiaires (`/08 STAGIAIRE X` : CQ donne l'équipe pro, Clics le club puis le stage) et clubs amateurs |
| Effectif 2012 de Saur-Sojasun (25 chez nous) | 13 dans une page migrée ; 11 retrouvés (2 non retrouvés dans la page visée), **9 avec l'équipe Saur-Sojasun en 2012**, 2 sans ligne 2012 (fiche incomplète) ; **aucun coureur Clics 2012 Saur-Sojasun absent de notre effectif** |
| Effectif 2012 de FDJ-BigMat (32 chez nous) | 13 dans une page migrée, 8 retrouvés (5 non retrouvés dans la page visée : ordre alphabétique approximatif de ma recherche, non vérifié), 7 avec l'équipe FDJ-BigMat-Lapierre, 1 sans ligne 2012 ; aucun coureur en trop |
| Couverture des coureurs de nos équipes 2010-2016 par les plages migrées | **~33 % des coureurs, ~43 % des Français** (voir §4) |
| Courses Clics vs palmarès Mémoire du Cyclisme (nom de course normalisé + année exacts) | 7 606 résultats analysables, 243 retrouvés chez MDC (3 %) ; sur 46 podiums comparables, 28 concordants (écarts : « Championnat de France » ambigu entre rubriques MDC, ordre prénom/nom) |

Le lien avec Mémoire du Cyclisme est réel mais léger : même vocabulaire et mêmes graphies françaises (`Paris-Evreux`, `Tour de la Manche`, `Boucles de la Mayenne`), mais pas de table commune ni d'identifiant ; les noms de course Clics
(`Grand Prix de Plumelec-Morbihan` contre `G.P du Morbihan` chez MDC) demanderaient des alias manuels comme `alias_museo.json`. Clics est utile pour **identifier les coureurs** (date au jour), pas pour les classements.

## 4. Couverture et volumes

Pages migrées au 19/11/2026 (sitemap = index) : 3 206 pages de coureurs (3 193 liens dans les index + quelques pages hors index), dont ~330 pages d'un seul libellé (coureurs notables) et ~2 870 pages de plage.

| Dossier | Pages | Plage couverte |
|---|---|---|
| a | 11 | Aabye - Abakoumov |
| b | 122 | Boocock - Bozzola |
| c | 165 | Ceaglia - Chzhan |
| d | 414 | Da Col - Dumpon |
| f | 292 | Faanhof - Fzick |
| g | 434 | Gaal - Grgac |
| i / j | 41 + 98 | Iacchi - Jnv |
| l | 530 | Las Heras - Lyver |
| m | 478 | Ma - Mertens |
| q-r | 409 | Rastello - Rzeznicki |
| s | 212 | Sa - Schultz |

Absentes (liens vers web.archive.org ou rien) : E, H, K, N, O, P, T à Z, et la plus grande partie de A, B, C, G (Gri-Gz), M (après Mertens), S (après Schultz). Une page `index-h.html` existe mais est vide.

Estimations (échantillon aléatoire : 18,6 coureurs par page de plage) :
- **~55 000 coureurs** (±10 %), ~170 000 lignes-années dont ~140 000 avec équipe, ~330 000 résultats.
- Collecte : 3 206 pages × (3,2 s de pause + ~2 s de téléchargement, mesuré 5,3 s par page) = **~4,7 h**, soit 6 passages de 50 min (~570 pages chacun) ; ~1,2 Go transférés au total (HTML non compressé).
- Sortie : ~9 Ko de JSON compact par page (échantillon aléatoire), **~30 Mo** pour tout le site résultats compris (~10 Mo compressés), **~9 Mo sans les résultats**.
- Maintien à jour : le sitemap donne `lastmod` ; 100 à 400 pages modifiées par mois depuis février 2026 d'après les `lastmod` (décembre 2025-janvier 2026 : 1 179 pages, pic de migration) : un passage mensuel de rattrapage suffit.

## 5. Collecteur proposé `clics.py` (à écrire en étape 1, même modèle que `thesports.py` / `mdc.py`)

- **Périmètre** : fiches de coureurs seulement (état civil, équipe par année, résultats). Pas d'équipes (non hébergées), pas des copies web.archive.org, pas de lexique.
- **Politesse** : lire `robots.txt` d'abord (interdire d'office toute URL refusée à `*`), UA « courses-cyclistes (accord Clics sur le cyclisme) », `PAUSE_S` 3,2, délai de lecture 60 s, jamais deux fois la même page (`--relire` pour forcer), abandon de l'hôte sur 403 / 429 / challenge (`netutil.hote_bloque`), abandon propre après 8 échecs de suite.
- **Découverte** : `sitemap.xml` (une requête) -> liste des pages `pages/<d>/<slug>.html` avec `lastmod` ; contrôle de cohérence avec les `index-*.html` (une requête chacun, facultatif). `--decouverte-seule` écrit `pages.json`.
- **Sortie** `ARCHIVES_DIR/sources/clics/` :
  - `pages.json` : `{url relative: {lastmod, libelle, lu_le, nb_coureurs, empreinte}}` ;
  - `plages/<dossier>/<slug>.json` : liste ordonnée des coureurs `{nom_affiche, nom_famille, prenom, variante, pays_site, nat, code_site, naissance, naissance_precision "jour"|"annee"|None, naissance_lieu, deces, deces_lieu, annees: [{annee, equipe_brut, club, categorie, stagiaire_depuis, departement}], resultats: [{annee, date_txt, texte, rang, ex_aequo, etape}], credit}` ; **rang du coureur dans la page** conservé (les homonymes sans date ne se distinguent que par là) ;
  - `etat.json` `{termine, pages_restantes, pages_a_relire}` (sans horodatage, lu par un `clics.yml` du dépôt d'archives, cron nocturne, groupe `clics-data`, auto-relance tant que `termine: false` ET progrès) ;
  - `introuvables.json` (404 / structure inconnue : 2 essais puis abandon), `cache/` (HTML aplati gzip, facultatif, `--garder-html`).
- **Ordre** : (1) pages à libellé unique (coureurs notables), (2) pages dont la plage contient le plus de coureurs de `entites/coureurs` et de `sources/cqranking/coureurs.json` (calculé au démarrage, hors réseau), (3) le reste ; `lastmod` plus récent que `lu_le` = à relire ; budget `--budget-min`, `--max-requetes`.
- **Ce que le collecteur ne fait pas** : ne fusionne jamais deux coureurs sur le seul nom (identité = nom normalisé + naissance au jour ; sans naissance : identité de page + rang, jamais rattachée) ; n'interprète pas les libellés d'équipe (`equipe_brut` + segments `/` découpés, pas de rapprochement) ; ne convertit pas les résultats libres en classements ; ne déduit pas France d'une absence de pays.
- **Rapprochement (étape 2, hors collecteur)** : coureur = nom (jetons) + date au jour contre `rider_id` / Wikidata / CQ Ranking ; équipe-saison = jetons du libellé coupé au premier `/` contre le nom d'équipe-saison (seuil 0,5 : 90 à 95 % mesuré), table `alias_equipes_clics.json` manuelle pour les écarts ; usage comme complément (équipe d'une saison avant 2009, naissance, décès), jamais comme effectif complet d'une équipe.
- Tests : `python clics.py --test` sur `tools/fixtures/clics/` (voir §8).

## 6. Pièges relevés

1. **Aucune composition d'équipe sur ce site** (liens web.archive.org) : l'effectif d'une équipe-saison ne peut être reconstitué que par inversion des fiches (coureur -> équipe de l'année), donc **partiel** (33 % des coureurs de nos équipes 2010-2016, 43 % des Français), et incomplet pour les saisons de chaque fiche (19 % de lignes-années sans équipe). À présenter comme « coureurs connus de l'équipe », pas comme effectif.
2. **Site en migration** : couverture alphabétique trouée (E, H, K, N, O, P, T-Z absents) et mouvante ; plages et URL susceptibles de changer ; relire le sitemap à chaque passage.
3. Tableau Excel sans identifiant : lecture positionnelle ; lignes de crédit `Palmarès établi par` en col. 1 ; une ligne d'état civil sans nom (variante en col. 2, décès en col. 4) ; coureur sans pays (2 %).
4. **Homonymes dans la même page** (deux Anthony Geslin, 1980 et 1983) ; 68 % des coureurs sans date de naissance : identité non garantie.
5. Coquilles de source : `°20-10-1190`, `°20-021891`, `°1813 ?`, `à (92) Colombes` (département devant le lieu) ; valider (siècle plausible, `jj-mm-aaaa`) et garder le brut.
6. Libellés d'équipe composites (sponsors + équipementiers, club après `/`, catégorie, `/MM STAGIAIRE`), variantes de graphie d'une saison à l'autre ; pas de code UCI.
7. Pays : mots français et doubles nationalités (`KENYA/G-B`, `AFN/FRANCE`), codes inconnus de `netutil.FLAG_CODES`.
8. Résultats : texte libre, rangs `1er` / `Nè` / `Nème` / `N°` / `ex aequo`, courses sans identifiant, pas de temps ; mêle route, cyclo-cross, piste ; seuls ~3 % se retrouvent par nom exact dans MDC.
9. Pages lourdes et non compressées (370 Ko) : prévoir les 1,2 Go de transfert, ne pas garder le HTML brut dans le dépôt (aplatir ou ne garder que le JSON).
10. `Crawl-delay` absent pour `*` : notre pause de 3,2 s reste notre choix, pas une obligation du site.

## 7. Points ouverts (décisions du propriétaire)

- Les copies web.archive.org des compositions d'équipes de Mémoire du Cyclisme (`.eu`, états 2024) sont-elles couvertes par un accord (Clics ? Mémoire du Cyclisme ?) ? Sinon les compositions d'équipes 1868-2016 restent inaccessibles ; demander éventuellement aux administrateurs de Mémoire du Cyclisme si `memoireducyclisme.fr` rouvrira la rubrique « pelotons ».
- Le site migre : prévoir une nouvelle étude de couverture dans quelques mois (lettres manquantes).
- Périmètre des résultats (hors route : cyclo-cross, piste) : les garder bruts ou les écarter à la collecte.
- Niveau pro / amateur : aucune marque ; à défaut, le rapprochement avec nos équipes-saisons ou CQ Ranking fait office de filtre.

## 8. Fixtures `tools/fixtures/clics/` (pages réelles du 19/11/2026, allégées)

`robots.txt` (réel) · `sitemap_extrait.xml` (37 entrées sur 3 244) · `accueil.html` · `equipes.html` (liens web.archive.org) · `index_g.html` (35 liens sur 434) · `index_h_vide.html` ·
`plage_gabbai.html` (page entière, 27 coureurs : `CDP 149`, variante de nom, décès, lieu, étapes) · `plage_gerardin.html` (80 lignes, coureurs sans prénom) ·
`plage_geslin_homonymes.html` (deux Anthony Geslin) · `plage_gault_credit.html` (ligne de crédit `Palmarès établi par` au milieu d'une fiche) ·
`coureur_gallopin_tony.html`, `coureur_fignon_laurent.html` (pages de coureur notable seul, 70 / 60 lignes, équipes pros et amateurs, `Leader du …`).
Allègement : en-tête, menu, styles et scripts retirés ; attributs `style` et `<span>` imbriqués de l'export Excel supprimés ; lignes tronquées (mention en commentaire de la page).

## 9. À reporter dans CLAUDE.md

> **Clics sur le cyclisme** (`docs/recherche/clics_collecte.md`, étude du 19/11/2026 ; `clics.py` à écrire) : accord du site obtenu par le propriétaire le 19/11/2026 pour lire `clicssurlecyclisme.net` par programme ET afficher ses données, crédit « Clics sur le cyclisme ». `robots.txt` : `*` autorisé, sitemap déclaré ; politesse : UA « courses-cyclistes (accord Clics sur le cyclisme) », >= 3 s entre requêtes (`PAUSE_S` 3,2), aucune page demandée deux fois, abandon de l'hôte sur 403 / 429. Annuaire de fiches de coureurs (pas d'équipes : la rubrique « Equipes » 1868-2016 ne contient que des liens web.archive.org vers l'ancien `memoire-du-cyclisme.eu`, hors accord) : découverte par `sitemap.xml` (3 206 pages `pages/<dossier>/<slug>.html`, `lastmod`), une table Excel de 4 colonnes par page (~19 coureurs, 370 Ko non compressés, ~5,3 s par page mesurées, ~4,7 h au total), par coureur nom, pays (mots français), naissance `°jj-mm-aaaa [à lieu]` (32 % des coureurs, 78 % depuis 1999, 12-15 % avant 1980), décès, équipe de chaque saison en libellé brut (`SPONSORS[/CLUB (dép.)][/catégorie][/MM STAGIAIRE …]`) et résultats choisis en texte libre. Site en migration : A-Z incomplet (E, H, K, N, O, P, T-Z absents), ~33 % des coureurs de nos équipes 2010-2016. Dates concordantes avec nos coureurs, Wikidata et CQ Ranking (0 divergence sur ~90 contrôles recoupés) ; équipe-saison concordante à 87-90 %. Pièges : aucun identifiant, 68 % sans naissance, homonymes dans la même page, lignes de crédit `Palmarès établi par` en col. 1, coquilles de dates. Sortie prévue `ARCHIVES_DIR/sources/clics/` ; pages réelles allégées : `tools/fixtures/clics/`.
