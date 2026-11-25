# Avancement du projet (point de reprise)

Dernière mise à jour : 25 novembre 2026. À lire avec `CLAUDE.md` (règles, architecture), `docs/PLAN_ENCYCLOPEDIE.md`
(plan et étapes), `docs/PLAN_ARCHIVES.md`, `docs/SPEC.md` (schémas), `docs/recherche/` (sondes et décisions) et `AUDIT_ANTIGRAVITY.md`.

## POINT DE REPRISE DU 25/11/2026 (à lire en premier)

- **Collectes d'archives** (dépôt courses-cyclistes-archives, battement toutes les 10 min) : CQ Ranking, Museo (sélection élargie, 42 alias + 4
  championnats validés), CyclingRanking, Clics terminés ; Mémoire du Cyclisme : 1 édition restante ; the-sports : plus rien à lire, `termine`
  passera à vrai vers le 27/11 (page 1941 en 503 abandonnée après 3 jours, PR #104). Wikidata : identifiants externes collectés (20/11).
  Aucun échec depuis le 19/11 (voir les bilans quotidiens en fin de fichier).
- **Tâche programmée** « bilan quotidien » (7 h 13 heure de Paris) : vérifie les deux dépôts vélo ET les Coupes d'Europe et ajoute un bilan ici.
- **Questions posées au propriétaire, sans réponse** : (1) la sélection Museo doit-elle aussi retenir les courses présentes au calendrier
  CyclingRanking (et à partir de combien d'étoiles) ? (2) l'accord de Mémoire du Cyclisme couvre-t-il les anciennes compositions d'équipes
  archivées sur web.archive.org (rubrique « Equipes » de Clics) ?
- **Chantiers non commencés** : collecteur `cyclingnews_archives.py` (étude faite : `docs/recherche/cyclingnews_archives_collecte.md`) ;
  étape 2 = rattachement des sources d'avant 2009 (the-sports, Museo, CQ Ranking, MDC, Clics, CyclingRanking) aux entités de l'encyclopédie
  (`ids` Wikidata, `ids_inverse.json` statut `ok`, nom + date de naissance) ; puis « Prochaines étapes » ci-dessous.
- **Coupes d'Europe** (dépôt Camelbaggy/coupes-europe) : point de reprise dans SON `docs/AVANCEMENT.md` (étapes 1 à 5 livrées, xG ajoutés le 25/11).

## Session du 23/11/2026 (Audit technique : QW1–QW6, CS1, CS2, CS3, CS4)

- **Quick Wins QW1–QW6** :
  - **QW1** : correction du fil d'Ariane des éditions reportées (`crumbsEdition` pointe vers `#courses/${c.season}` quand `c.season != null`) ; retrait de la limite obsolète E1c dans `encyclopedie.py`.
  - **QW2** : debounce de 180 ms (`debouncer`) sur les saisies (`#co-q`, `#co-eq`, `#ep-q`, `#eq-q`, `#sr-q`, `#uc-q`) et suppression du re-filtrage regex redondant dans `pageCoureurs`.
  - **QW3** : branchement de `pays.drapeau` et `pays.nom_historique` dans `encyclopedie.py` ; nettoyage des doublons `FLAG_CODES` (`ERI`, `RWA`) et décompression gzip sur `HTTPError` dans `netutil.py`.
  - **QW4** : optimisation de `_soeur_renommee()` (index inversé par coureur et mémorisation), `eq_index_by_id` et `@lru_cache` sur `netutil.normalize`.
  - **QW5** : cache HTTP `default` sur les archives immuables (`^\d{4}/races/` et instantanés UCI) dans `charger()`, suppression du `cache.clear()` agressif sur `retry-sr`.
  - **QW6** : lien d'évitement (« Aller au contenu principal »), `aria-label` distincts pour `#dnav` et `#bnav`, support `@media (prefers-reduced-motion: reduce)`, harmonisation des titres « Derniers résultats », suppression du paramètre inutilisé `maj` dans `saisie()`.
- **CS1 (`encyclopedie.py`, `index.html`)** : précalcul de `entites/ce_jour_la.json` côté `encyclopedie.py` et lecture en 1 requête par `ceJourLa()` (avec repli sur `entites/courses/`).
- **CS2 (`index.html`)** :
  - **Cache LRU borné** (`CACHE_MAX = 60`) avec préservation des index cœur (`estIndexCache`).
  - **Onglet « Saison » coureur en année civile** : `construireCoureur`, `ongletsCoureur` et `htmlSaison` alimentés en priorité depuis `cr.ent.saisons[voulue]` et `cr.ent.palmares` filtré sur `season === voulue` (`riders*.json` en repli optionnel uniquement).
  - **Pagination DOM incrémentale** (`insertAdjacentHTML("beforeend", ...)` + mise à jour du bouton `.more`) sur `majListeCoureurs`, `majListeEquipes`, `majListeEpreuves`, `majListeUci` et `majTablePlus`.
- **CS3 (`index.html`)** :
  - **Refonte Liquipedia des 5 pages de liste** : Équipes (`rowEquipe`, `pageEquipes`) avec maillot `slotMaillot` / logo de lignée / initiales ; Coureurs (`pageCoureurs`) avec barre d'outils mobile compacte `.flt-more` à 390 px et vue Français (`carteFrancais`, `renderFrancais`) alignée sur les cartes Liquipedia ; Courses/Épreuves (`listeCourses`, `rowEpreuve`, `pageCourses`) avec filets `--cat` unifiés ; Classements (`blocUci`, `lignesUci`, `renderFdj`) en tableaux `tbl-rank` avec pastilles `dot` ; Recherche (`htmlResultats`) enrichie de sous-titres contextuels `.sr-sub`.
  - **Accessibilité** : remplacement des faux liens `role="link"` (`plink`, `carteAccueil`, `carteVictoireEquipe`, `listeCourses`, `carteFrancais`, `blocVictoiresFr`) par de vrais `<a href>` (*stretched-link* `.lk`), et navigation clavier WAI-ARIA (`ArrowLeft`, `ArrowRight`, `Home`, `End`, `aria-controls`, `aria-labelledby`) sur `htmlOnglets()`.
- **CS4 (`sources_historiques.py`, `encyclopedie.py`, `alias_courses.json`, `index.html`)** :
  - **Pont d'ingestion pré-2009 (`sources_historiques.py`)** : 100 % stdlib Python 3.11, lit `<archives_dir>/sources/bdd_pre2009/` (`manifest.json`, `courses.json`, `coureurs.json`, `equipes.json`, `editions/<slug>/<year>.json`, strictement `year <= 2008`) et fusionne les données dans `COUR`, `COURSES`, `PAYS`, `EQ_PAR_AN`, `EQ_INDEX`, `EQ_INDEX_BY_ID`, `EQ_RECH` avant `historique.appliquer_historique()` (aucun doublon avec Wikidata).
  - **Normalisation & rapprochement strict** : codes pays d'époque (`URS`, `GDR`, `FRG`, `TCH`, `EUN`, etc.) via `pays.pays_ligne()` / `pays.pays_normalise()` ; épreuves par clé exacte `collector.cle_edition()` + `alias_courses.json` (complété pour les courses historiques : Dauphiné, Pays Basque, Catalogne, Gand-Wevelgem, Het Volk / Omloop, Plouay, etc.) ; coureurs par IDs externes Wikidata (`entites/wikidata/coureurs.json` champ `ids`, `ids_inverse.json` `statut == "ok"`) ou correspondance exacte nom normalisé (`riders._nom_cle`) + date de naissance, sinon création d'une entité dédiée `hist-*` (jamais de fusion floue d'homonymes).
  - **Crédits & multi-sources** : conservation de la source exacte (`pcs`, `letour_dataset`, `preflib_00043`, `vuelta_open`, `firstcycling`, etc.) sur chaque édition et ligne de palmarès ; exposition dans `entites/index.json` (`sources` et `sources_historiques`) et dans le pied de page `#foot` d'`index.html` (`majPiedDePage`).
  - **Optimisation mémoire & I/O (`encyclopedie.py`)** : séquencement par phases (Équipes → Pays → Coureurs → Courses & `ce_jour_la.json` → Recherche & `index.json`) avec libération explicite (`del`) des structures intermédiaires ; `_ecrire_si_change()` compare directement les octets JSON sérialisés lorsque `ignore=()`, évitant le double `json.load`.
  - **Déploiement de la base pré-2009 vers `ARCHIVES_DIR`** :
    1. Copier le contenu généré par `export_vers_encyclopedie.py` (`data/export_encyclopedie/*`) vers `<ARCHIVES_DIR>/sources/bdd_pre2009/` (`manifest.json`, `courses.json`, `coureurs.json`, `equipes.json`, `editions/<slug>/<year>.json`).
    2. Reconstruire `entites/` : `python run_pipeline.py --entites` (ou `python encyclopedie.py <ARCHIVES_DIR> data`, ou via le workflow `archives.yml` du dépôt d'archives).
    3. Vérifier `entites/index.json` (`sources_historiques`, `compteurs`) et exécuter `python sources_historiques.py --test` + `python encyclopedie.py --test`.
- **Validation** : `py_compile` sur tous les scripts Python OK, `python sources_historiques.py --test` OK, `python encyclopedie.py --test` OK, `python collector.py --test` OK, `python pays.py --test` OK, `node --check` sur `index.html` OK.

## Session du 18/11 au soir (à lire en premier, puis le point de reprise ci-dessous)

Fait (PR #84 à #86, fusionnées) :
- **Point 1 fait** : `veille_update.yml` (horaire à :52) relance `update.yml` si aucun passage depuis 50 min entre 13 h et 23 h UTC (3 h
  entre 7 h et 9 h) ; essai réel le 18/11 à 18 h 15 : passage sauté détecté (138 min) et relancé.
- **Vainqueur d'une course par étapes** lu dans le général final (Vuelta 2011 : vide -> Froome ; De Panne 2016 : Kristoff -> Westra) ;
  **ordre des demi-étapes** (3a avant 3b, 27 archives) ; révision LOCALE des saisons complètes à chaque passage d'archives
  (`reviser_vainqueurs_saison`, idempotente, ~3 s) : publiée au prochain passage d'archives (vérifier la Vuelta 2011 dans `#courses/2011`).
- **Demi-étapes** : identifiant `3a` / `3b` (`uci.ref_etape`) pour la notification ntfy et les routes `#course/<id>/3b`.
- **Échecs des fiches des sources d'avant 2009** : les 2 320 fiches coureurs the-sports.org avaient été abandonnées pendant la panne 503
  (3 échecs en 3 passages) ; une panne n'est plus un échec, un échec par jour au plus, entrées anciennes re-tentées (`REGLE_ECHECS = 2`,
  aussi MDC : 673 `introuvables` re-tentés, CQ Ranking et Museo par prévention).

En cours / suite :
- **Passage Wikidata relancé à la main (18/11 18 h 14 UTC)** : le cache ne contenait aucune équipe 2009-2011 (dernier passage avant leur
  arrivée). Ensuite : refaire les propositions d'équipes 2009-2010 par continuité d'effectif sur ce qui reste sans lignée (1re version, avant
  ce passage : 42 propositions chaînées via 2011, à refaire ; script `prop.py` à recopier dans `tools/` si réutilisé), puis soumettre au
  propriétaire. Cas notés : `fdj-2010` et `francaise-des-jeux-2010` (même équipe, deux libellés), Rabobank 2010 à 49 %, HTC-Columbia sans suite.
- **Inventaire des 4 sources (18/11, collectes partielles)** : courses rattachées par clé exacte : the-sports 124/152 (après conversion des
  codes pays du site SPA->ESP, SWI->SUI, MAL->MAS), Museo 296, CQ Ranking 151/1 778 clés, MDC 12/2 261 (815 courses sans pays) ; union = 374
  de nos 892 épreuves (113 des 183 WT/Pro). Échecs surtout dus aux anciens noms (Henninger Turm, Het Volk, championnats nationaux) : alias à
  proposer. Coureurs CQ Ranking : 68 % rattachés par nom + date ; 155 de plus avec même date + nationalité mais prénom différent (Greg/Gregory
  Henderson) à soumettre. Vainqueurs 1999-2008 : aucun vrai désaccord entre sources (écarts de graphie seulement). Anomalies : the-sports `nat`
  vide quand `nat_site` est rempli (2 921 lignes), CQ Ranking `*` collé à 629 noms, Museo noms « Prénom NOM ».

## POINT DE REPRISE (18/11/2026, fin de session) : à lire en premier

### Chantiers en cours au moment de la coupure
1. **Saison sportive = année civile : FAIT (PR #75, 18/11)**. Dans l'encyclopédie, une course compte pour l'année de sa `start_date` (Lombardia
   2010 -> 2010) ; stockage par saison UCI inchangé ; `riders.json` / `ranking.json` / `state.json` liés à leur dossier. Publié au prochain passage
   d'archives : vérifier `#epreuve/…lombardia…` (édition 2010 = Gilbert) et la fiche de Gilbert. Onglet « Saison » de la fiche coureur et fil d'Ariane des éditions reportées corrigés le 23/11 (QW1, CS2) ; reste à régénérer le jeu fictif (`tools/fixtures/generer_archives.py`, contient encore une saison 2027).
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
   - **FirstCycling et ProCyclingStats** : accord explicite obtenu par le propriétaire pour utiliser leurs données dans ce projet personnel (crédit « ProCyclingStats » et « FirstCycling » lors de l'affichage ; ne pas republier les caches HTML bruts dans le dépôt public). Techniquement, leurs pages restent derrière un défi Cloudflare (`tools/essais/essai_firstcycling*.py` documentent les essais : même un vrai navigateur sans déguisement échoue depuis GitHub Actions) : accès uniquement si les administrateurs ouvrent une voie dédiée (règle d'exception par en-tête secret, clé d'API ou export), sans contournement anti-robot.
   - Écartés / sans suite : siteducyclisme.com (robots `Disallow: /` délibéré), cyclebase.nl (`Disallow: /`), bases PCM (données de jeu),
     (CyclingRanking : écarté d'abord, puis accord du 19/11/2026, voir `docs/recherche/cyclingranking_collecte.md`). Analyse du rapport Gemini du 18/11 : FirstCycling / CycleBase / Site du Cyclisme
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
- **Refonte du site** (PR #55 à #61, `docs/REDESIGN.md`, achevée le 23/11 avec CS3) : thème clair + sombre, composants Liquipedia modernisés, navigation (recherche
  d'en-tête, retour mobile, sous-navigation), accueil, fiche de course, fiche coureur, articles d'équipe, pages d'épreuve, et les 5 pages de liste (Équipes, Coureurs, Classements, Courses/Épreuves, Recherche) ; titres « Derniers résultats » harmonisés.
- **Archives 2011-2025 complètes** ; sondage des vainqueurs contre Wikidata 2011-2015 (grands tours + 5 monuments) : 40/40 conformes.
  Championnat de France absent avant 2016 (limite DataRide). À regarder : `winner` vide dans l'index 2011 pour la Vuelta 2011 (le `final.gc`
  donne Froome, Cobo déclassé).
- **Équipes** : `data/ranking-<S>.json` (classement de fin de saison des saisons terminées encore au Calendrier, PR #62) et rang UCI des
  `riders-<S>.json` (PR #63) ; `alias_equipes.json` 85 entrées validées (PR #64-68 : 2026, Cofidis 2012-2026, Groupama-FDJ 2012-2026,
  Movistar 2015-2016, 45 équipes 2012-2014) ; lignée reprise par l'équipe renommée en cours de saison (`_heriter_lignees_renommees`, 43 cas ;
  à surveiller : Fundación Orbea 2020 -> Euskaltel-Euskadi). Correctif : coureur 2010 sans nationalité qui bloquait toute reconstruction
  d'`entites/` (PR #70). `entites/` du 18/11 : 26 063 coureurs, 5 223 équipes-saisons, 418 lignées, 871 épreuves ; Wikidata : 2 165 équipes-saisons
  rattachées sur 2 340, 11 311 coureurs.

### À faire ensuite (ordre validé en fin de session du 18/11 : reprendre au point 1)
1. **FAIT le 18/11 au soir (`veille_update.yml`).** Veille d'`update.yml`. GitHub saute la plupart de ses crons
   (3 passages en 24 h au lieu de 11 le 17-18/11) : sans effet en intersaison, mais en saison résultats et notifications ntfy en retard.
   Solution proposée : une veille sur le modèle de `veille.yml` du dépôt d'archives (cron horaire décalé qui relance `update.yml` par
   `gh workflow run` si aucun passage n'a démarré depuis ~1 h 30 pendant le créneau 13 h-22 h UTC, rien si un passage est en file / en cours),
   placée dans CE dépôt (`update.yml` y est) ; option de secours : tâche programmée côté Claude (accord du propriétaire requis).
2. **Étape 2 des sources d'avant 2009 (rattachement), puis étape 3 (affichage).** Conception possible tout de suite sur les données déjà
   collectées (`data/archives/sources/{thesports,mdc,cqranking,museo}/` du dépôt d'archives), les collectes finissent dans quelques jours :
   - courses -> nos épreuves (`cle_edition`, alias) : nom identique validé d'office, cas douteux soumis au propriétaire (Paris-Nice, Tirreno,
     Pays basque, Dauphiné, Paris-Camembert, renommages ; `docs/recherche/thesports_courses_proposees.json`) ;
   - coureurs -> nos `rider_id` / QID Wikidata par nom + date de naissance (CQ Ranking, Museo, the-sports par fiche) ; Mémoire du Cyclisme
     (nom seul) rattachée seulement de façon prudente ;
   - désaccords entre sources : garder toutes les valeurs, chacune avec sa source, jamais trancher ;
   - étape 3 : pages d'épreuve, d'édition et de coureur, crédit de chaque source (« the-sports.org », « Mémoire du Cyclisme », « CQ Ranking »,
     « Museo del Ciclismo »).
3. **FAIT le 23/11/2026 (CS3 + QW6).** Refonte des pages de liste (Équipes, Coureurs, Classements, Courses, Recherche) et harmonisation des titres « Derniers résultats ».
4. **Équipes 2009-2010** une fois 2009 complète : rattachements manuels des équipes de 2e division sans code UCI (continuité d'effectif,
   comme 2012-2014), liste à soumettre au propriétaire avant ajout à `alias_equipes.json`.
5. **Petites corrections** : `winner` vide de la Vuelta 2011 dans l'index 2011 (`final.gc` donne Froome) ; onglet « Saison » (CS2) et fil d'Ariane d'une édition reportée (QW1) faits le 23/11 ; reste à régénérer le jeu fictif
   (`tools/fixtures/generer_archives.py`, contient encore une saison 2027).

**Décisions tranchées / restantes** :
- codes pays historiques de Mémoire du Cyclisme (`Hon`, `Tch`, `Rfa`, `Urs`, `Rda`) et Museo (CSI, DDR, LAT, TCH, URS) : implémentés dans `pays.py` / `pays_historiques.json` (décision du 18/11) et branchés dans `encyclopedie.py` (QW3) ;
- Museo del Ciclismo : rester sur les épreuves suivies (`--suivies`) ou élargir (ex. courses italiennes et françaises d'avant 2009, `--cles`) ;
- bilan quotidien : recréer une tâche programmée pour suivre 2009 et les quatre collectes (l'ancienne « Bilan archives » est arrêtée).

**Accords en attente d'accès technique** : FirstCycling et ProCyclingStats (accord explicite du propriétaire pour usage personnel avec crédit à l'affichage et sans republier les caches HTML bruts dans le dépôt public) restent derrière Cloudflare tant que leurs administrateurs n'ouvrent pas un accès dédié (règle d'exception par en-tête secret, clé d'API ou export) ; aucun contournement de notre côté (`tools/essais/essai_firstcycling*.py` documentent les essais : requêtes simples et vrai navigateur sans déguisement, tous deux bloqués).

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
- **Bilan du 19/11 (6 h 15 UTC, tâche programmée quotidienne à 7 h 13 heure de Paris)** : battements des deux dépôts relancés seuls (2e à 0 h,
  3e à 5 h 20-5 h 27) ; `update.yml` ~1 passage par heure ; collectes enchaînées sans trou. the-sports : 0 édition restante (4 497 la veille),
  8 686 fiches coureurs ; MDC : 1 690 courses + 935 éditions ; CQ Ranking : 0 page, 4 306 fiches (5 450) ; Museo (sélection élargie) : 102 albos,
  2 503 éditions, 13 à décider ; CyclingRanking et Clics : 1er passage en cours. Seul échec 24 h : mdc #1 (`KeyError: 'affiche'`, corrigé le 18/11).
  Archives 2009-2025 complètes ; Wikidata #11 (18/11) : 12 288 coureurs, 2 240 équipes-saisons (2009 : 30/32, 2010 : 30/31, 2011 : 18/18).
  `archives.yml` relancé à la main le 19/11 (rien depuis le 18/11 14 h 38) pour publier vainqueurs corrigés, demi-étapes et équipes 2009-2011.
- **Bilan du 20/11 (6 h 15 UTC)** : aucun échec en 24 h ; battements continus (un toutes les ~5 h 20 dans chaque dépôt). Collectes TERMINÉES : CQ Ranking,
  Museo (sélection élargie : 231 épreuves suivies dont 35 par alias_museo, 4 championnats, 32 + 231 courses CQ ; les 7 alias sans édition avant 2009
  sont normaux), CyclingRanking (calendriers 1869-2008), Clics (3 211 pages, 7 en « structure inconnue » : pages Indurain, Jalabert, Impanis… à examiner).
  En cours : the-sports (34 fiches en échec, passages à vide toutes les ~71 min jusqu'à leur abandon après 3 jours), MDC (1 448 courses + 941 éditions).
  Archives : passage du 19/11 publié (27 demi-étapes réordonnées, 5 vainqueurs recalculés, entites/ : 26 940 coureurs, 5 159 équipes-saisons, 892 épreuves).
  `wikidata.yml` lancé à la main le 20/11 pour la première collecte des identifiants externes (`ids`, `ids_inverse.json`).
- **Bilan du 24/11 (21-24/11 regroupés)** : aucun échec en 4 jours ; battements continus (deux trous de 3-6 h après une annulation, repris seuls).
  Wikidata (20/11, 62 min) : 12 292 coureurs relus dont 12 218 avec identifiants externes ; sens inverse : 26 449 ids CQ / the-sports cherchés,
  1 118 trouvés dont 1 057 nouveaux QID, 122 `a_verifier`, 0 ambigu ; entites/ reconstruit ensuite (dernier 23/11). MDC : 414 courses + 458 éditions
  restantes (~4 jours). the-sports : 0 restant mais `termine` reste faux (découverte bloquée) : passages à vide toutes les ~70 min, correctif en cours.
- **Bilan du 25/11 (6 h 15 UTC)** : aucun échec côté vélo ; battements continus dans les deux dépôts. MDC : 0 course + 1 édition restante (414 + 458
  la veille) ; the-sports : 0 restant, `termine` encore faux (abandon de la page 1941 en 503 attendu vers le 27/11, correctif PR #104) ; autres
  collectes terminées. Coupes d'Europe (suivi ajouté au bilan le 25/11) : soirée du 24/11 complète et notifiée ; 40 soirées de la saison
  reconstituées (historique) ; rattrapage IA : 10 résumés Gemini faits, 17 restants (2 passages / jour).
