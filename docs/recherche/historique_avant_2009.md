# Sonde historique avant 2009 (Wikidata + Wikipédia) — 16 novembre 2026

Script : `tools/essais/sonde_historique.py` (`series`, `souseditions`, `wikitext`, `stats`) ; cache HTTP dans `cache/` (rejouable sans requête).
Données brutes : `series.json` (éditions), `coureurs.json`, `wikitext.json`, `souseditions_champfr.json`, `stats.json`, `stats.txt` (tableau complet par épreuve).
Mesures : 39 séries, 3 017 éditions Wikidata dont 2 298 de 2008 ou avant ; ~330 requêtes Wikidata (+ 27 Wikipédia).

## 1. Modèle Wikidata (constaté)
- Série = élément « course » ; **chaque édition est une instance de la série** (P31 = QID de la série), trouvée par CirrusSearch `haswbstatement:P31=<série>` (500 résultats/requête). P179 / P3450 : 0 résultat. Date P585 (2 029) ou P580 (986) ; 2 éditions sans date (année lue dans le libellé).
- Vainqueur/podium : `P1346` répété avec qualificatif `P2501` = Q20882667 / Q20882668 / Q20882669 (vainqueur / 2e / 3e du classement général). 473 éditions ≤ 2008 ont P1346 sans P2501.
- Classement : `P2321` (une déclaration par coureur ; qualificatifs P1352 rang, P2781 temps, P2911 écart, P2912 équipe), souvent top 10 / 20 / 25 ; `P1923` participants ; `P527` étapes. Les articles fr « Cycling race/generalclassification|Qxxx » **affichent ces données Wikidata** (donc fr = Wikidata pour ces éditions).
- Sélection des séries : la recherche par nom ne suffit pas (« recurring sporting event » écarté ; Omloop et Paris-Camembert ajoutés par QID à la main : Q506447, Q1400788 ; Dauphiné = « Tour Auvergne-Rhône-Alpes » Q655150 ; Gand-Wevelgem = « In Flanders Fields » Q498661).
- Championnat de France : l'édition est un conteneur ; la course masculine en ligne est un élément `P527` (« Course en ligne masculine aux championnats… ») : 100/101 éditions ≤ 2008 en ont un, 95 avec vainqueur et podium ; aucun article fr/en à ce niveau.

## 2. Couverture ≤ 2008 par épreuve (extrait ; tout : stats.txt)
Format : 1re édition avec élément / nb éditions ≤ 2008 / années attendues manquantes / vainqueur / podium / classement >= 10 lignes / article fr / en.
    tdf          Tour de France             1re=1903 av.2009= 95 manq=  1/ 96 vq=100% pod=100% top10=69% tps=67% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=100
    giro         Tour d'Italie              1re=1909 av.2009= 91 manq=  0/ 90 vq=100% pod=100% top10=82% tps=81% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=100
    vuelta       Tour d'Espagne             1re=1935 av.2009= 63 manq=  8/ 68 vq=100% pod=98% top10=52% tps=54% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=100
    msr          Milan-San Remo             1re=1907 av.2009= 99 manq=  0/ 92 vq=100% pod=100% top10=61% tps=63% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=60
    rvv          Tour des Flandres          1re=1913 av.2009= 92 manq=  0/ 86 vq=100% pod=100% top10=66% tps=66% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=64
    pr           Paris-Roubaix              1re=1896 av.2009=106 manq=  0/103 vq=100% pod=99% top10=76% tps=76% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=100
    lbl          Liège-Bastogne-Liège       1re=1892 av.2009= 94 manq= 15/107 vq=100% pod=99% top10=65% tps=65% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=54
    lom          Tour de Lombardie          1re=1905 av.2009=102 manq=  0/ 94 vq=100% pod=100% top10=61% tps=61% fr=81% en=100% fr|en=100% it=100 nl=100 es=100 de=56
    pn           Paris-Nice                 1re=1933 av.2009= 66 manq=  4/ 70 vq=100% pod=100% top10=23% tps=35% fr=100% en=100% fr|en=100% it=92 nl=12 es=100 de=11
    dau          Tour Auvergne-Rhône-Alpes  1re=1947 av.2009= 60 manq=  2/ 62 vq=100% pod=100% top10=55% tps=55% fr=77% en=100% fr|en=100% it=85 nl=13 es=0 de=5
    tds          Tour de Suisse             1re=1933 av.2009= 72 manq=  0/ 70 vq=100% pod=100% top10=86% tps=89% fr=18% en=100% fr|en=100% it=100 nl=10 es=17 de=100
    tir          Tirreno-Adriatico          1re=1966 av.2009= 43 manq=  0/ 43 vq=100% pod=100% top10=60% tps=60% fr=100% en=100% fr|en=100% it=100 nl=21 es=100 de=9
    fw           Flèche wallonne            1re=1936 av.2009= 72 manq=  0/ 67 vq=100% pod=100% top10=22% tps=24% fr=100% en=100% fr|en=100% it=100 nl=62 es=100 de=3
    gw           Gand-Wevelgem              1re=1934 av.2009= 70 manq=  0/ 69 vq=100% pod=100% top10=37% tps=37% fr=84% en=100% fr|en=100% it=100 nl=10 es=100 de=0
    amstel       Amstel Gold Race           1re=1966 av.2009= 43 manq=  0/ 43 vq=100% pod=100% top10=42% tps=42% fr=100% en=100% fr|en=100% it=100 nl=100 es=100 de=0
    cat          Tour de Catalogne          1re=1911 av.2009= 88 manq=  6/ 88 vq=100% pod=100% top10=69% tps=69% fr=100% en=94% fr|en=100% it=44 nl=11 es=100 de=6
    pb           Tour du Pays basque        1re=1924 av.2009= 48 manq= 31/ 79 vq=100% pod=100% top10=100% tps=100% fr=46% en=100% fr|en=100% it=100 nl=12 es=100 de=15
    rom          Tour de Romandie           1re=1947 av.2009= 62 manq=  0/ 62 vq=100% pod=100% top10=18% tps=18% fr=16% en=100% fr|en=100% it=85 nl=10 es=100 de=6
    pt           Paris-Tours                1re=1896 av.2009=102 manq=  8/103 vq=100% pod=100% top10=16% tps=16% fr=21% en=100% fr|en=100% it=22 nl=100 es=100 de=22
    bc           Bretagne Classic           1re=1931 av.2009= 72 manq=  1/ 72 vq=100% pod=100% top10=1% tps=1% fr=8% en=79% fr|en=79% it=42 nl=21 es=0 de=0
    css          Classique de Saint-Sébasti 1re=1981 av.2009= 28 manq=  0/ 28 vq=100% pod=100% top10=11% tps=11% fr=79% en=100% fr|en=100% it=100 nl=100 es=100 de=29
    omloop       Circuit Het Nieuwsblad     1re=1945 av.2009= 61 manq=  3/ 63 vq=100% pod=100% top10=69% tps=69% fr=69% en=100% fr|en=100% it=82 nl=25 es=0 de=0
    e3           E3 Saxo Bank Classic       1re=1958 av.2009= 51 manq=  0/ 51 vq=100% pod=100% top10=18% tps=18% fr=20% en=100% fr|en=100% it=100 nl=100 es=8 de=0
    ain          Tour de l'Ain              1re=1989 av.2009= 20 manq=  0/ 20 vq=100% pod=90% top10=60% tps=60% fr=30% en=0% fr|en=30% it=65 nl=0 es=0 de=5
    occ          Route d'Occitanie          1re=1977 av.2009= 32 manq=  0/ 32 vq=100% pod=100% top10=0% tps=0% fr=0% en=0% fr|en=0% it=91 nl=0 es=0 de=3
    mayenne      Boucles de la Mayenne      1re=1975 av.2009= 34 manq=  0/ 34 vq=100% pod=35% top10=0% tps=0% fr=0% en=0% fr|en=0% it=0 nl=0 es=0 de=0
    limousin     Tour du Limousin-Nouvelle- 1re=1968 av.2009= 41 manq=  0/ 41 vq=100% pod=100% top10=0% tps=0% fr=83% en=0% fr|en=83% it=34 nl=0 es=0 de=2
    camembert    Paris-Camembert            1re=1934 av.2009= 72 manq=  0/ 69 vq=100% pod=100% top10=86% tps=35% fr=0% en=0% fr|en=0% it=100 nl=0 es=0 de=0
    plumelec     Grand Prix du Morbihan     1re=1974 av.2009= 35 manq=  0/ 35 vq=100% pod=91% top10=17% tps=17% fr=9% en=0% fr|en=9% it=91 nl=0 es=0 de=0
    tbl          Tro Bro Leon               1re=1984 av.2009= 25 manq=  0/ 25 vq=100% pod=100% top10=36% tps=40% fr=16% en=40% fr|en=40% it=36 nl=0 es=0 de=0
    polynormande Polynormande               1re=1980 av.2009= 29 manq=  0/ 29 vq=100% pod=100% top10=17% tps=17% fr=14% en=0% fr|en=14% it=21 nl=0 es=0 de=0
    doubs        Tour du Doubs              1re=1934 av.2009= 24 manq= 45/ 69 vq=100% pod=100% top10=25% tps=25% fr=0% en=0% fr|en=0% it=38 nl=0 es=0 de=0
    cla          Classic Loire-Atlantique   1re=2000 av.2009=  9 manq=  0/  9 vq=100% pod=100% top10=0% tps=0% fr=0% en=0% fr|en=0% it=44 nl=0 es=0 de=0
    cholet       Cholet Agglo Tour          1re=1978 av.2009= 31 manq=  0/ 31 vq=100% pod=100% top10=55% tps=55% fr=3% en=0% fr|en=3% it=55 nl=0 es=0 de=0
    denain       Grand Prix de Denain       1re=1959 av.2009= 50 manq=  0/ 50 vq=100% pod=100% top10=60% tps=10% fr=100% en=24% fr|en=100% it=68 nl=100 es=0 de=0
    vendee       Tour de Vendée             1re=1980 av.2009= 29 manq=  0/ 29 vq=100% pod=100% top10=55% tps=48% fr=14% en=0% fr|en=14% it=76 nl=0 es=0 de=0
    bourges      Paris–Bourges              1re=1913 av.2009= 58 manq= 29/ 86 vq=100% pod=100% top10=34% tps=24% fr=22% en=0% fr|en=22% it=48 nl=0 es=0 de=0
    cdn          Chrono des Nations-Les Her 1re=1982 av.2009= 28 manq=  0/ 27 vq=100% pod=100% top10=0% tps=0% fr=0% en=14% fr|en=14% it=14 nl=0 es=0 de=0
    champfr      championnats de France de  1re=1907 av.2009=101 manq=  2/ 92 vq=0% pod=0% top10=0% tps=0% fr=4% en=0% fr|en=4% it=0 nl=0 es=0 de=0

(« manq » = années entre la 1re édition et 2008 sans élément, hors 1915-18 et 1940-45 : borne haute, certaines années n'ont pas eu de course. Séries incomplètes : Tour du Doubs 45/69, Pays basque 31/79, Paris-Bourges 29/86, Liège-Bastogne-Liège 15/107.)

## 3. Par décennie (toutes épreuves de l'échantillon, éditions ayant un élément)
```
Par décennie (toutes épreuves, éditions avec élément Wikidata) :
1890 {'n': 8, 'vainqueur': 100, 'podium': 100, 'top10': 0, 'fr': 100, 'en': 100, 'fr_ou_en': 100, 'any_lang': 100}
1900 {'n': 37, 'vainqueur': 89, 'podium': 89, 'top10': 14, 'fr': 76, 'en': 89, 'fr_ou_en': 89, 'any_lang': 89}
1910 {'n': 67, 'vainqueur': 85, 'podium': 85, 'top10': 3, 'fr': 75, 'en': 82, 'fr_ou_en': 87, 'any_lang': 87}
1920 {'n': 110, 'vainqueur': 91, 'podium': 91, 'top10': 12, 'fr': 69, 'en': 85, 'fr_ou_en': 86, 'any_lang': 86}
1930 {'n': 148, 'vainqueur': 93, 'podium': 93, 'top10': 24, 'fr': 60, 'en': 82, 'fr_ou_en': 82, 'any_lang': 86}
1940 {'n': 131, 'vainqueur': 92, 'podium': 92, 'top10': 31, 'fr': 54, 'en': 76, 'fr_ou_en': 80, 'any_lang': 85}
1950 {'n': 211, 'vainqueur': 95, 'podium': 95, 'top10': 60, 'fr': 55, 'en': 82, 'fr_ou_en': 83, 'any_lang': 88}
1960 {'n': 228, 'vainqueur': 96, 'podium': 96, 'top10': 51, 'fr': 66, 'en': 85, 'fr_ou_en': 89, 'any_lang': 94}
1970 {'n': 285, 'vainqueur': 96, 'podium': 94, 'top10': 57, 'fr': 62, 'en': 76, 'fr_ou_en': 81, 'any_lang': 91}
1980 {'n': 352, 'vainqueur': 97, 'podium': 94, 'top10': 44, 'fr': 52, 'en': 65, 'fr_ou_en': 70, 'any_lang': 80}
1990 {'n': 373, 'vainqueur': 97, 'podium': 95, 'top10': 47, 'fr': 56, 'en': 63, 'fr_ou_en': 68, 'any_lang': 84}
2000 {'n': 348, 'vainqueur': 98, 'podium': 97, 'top10': 67, 'fr': 72, 'en': 66, 'fr_ou_en': 76, 'any_lang': 91}
```
Le « vainqueur » baisse (85-98 %) à cause du championnat de France (0 % au niveau édition) ; hors lui : 100 % partout.

## 4. Coureurs anciens
- 1 038 vainqueurs distincts, 1 876 deuxièmes/troisièmes (≤ 2008) : naissance P569 présente pour 97 % et 98 % ; **à la précision du jour : 1 005 et 1 840** ; année seule : 3 et 7. Les « sans naissance » sont surtout des **équipes** mises en P1346 (ex. « ONCE-Eroski 2001 ») : ~99 % des personnes ont une date au jour. Article fr 95 %, en 93 % chez les vainqueurs. Par décennie de victoire : 93 % (années 1910) à 100 %.
- Les coureurs d'avant 2009 n'existent pas dans nos archives (2011→) : identifiant = QID ; pour les chevauchements (carrières 2009-2015) un rapprochement par nom + date de naissance exacte (règle de wikidata.py) reste possible.

## 5. Wikipédia (wikitext, 9 éditions) — fr / en / de
- Tour (1985, 1995, 2005) : **en = tableau `wikitable` « General classification » de 107-147 lignes** (rang, `{{Flag athlete|[[coureur]]|PAYS}}`, `{{UCI team code|…}}`, écart `+ 15' 10"`), tableau des étapes (7 colonnes, vainqueur), tableaux de classements annexes 10 lignes. **fr = modèle `{{Classement final|…|1er=…|pays du 1er=…|équipe du 1er=…|temps du 1er=…}}` limité au top 25** (24 « Ne » comptés), temps en `{{heure|113|24|23}}`, liste des étapes via `{{Étape|…}}`/en-tête de tableau, tableau « Évolution des classements » (maillots). de : 3 à 27 ko, peu de tableaux (0-22), pas de GC en tableau.
- Classiques (Paris-Roubaix 1990 / 2000, Paris-Tours 1998, Plouay 2005) : fr = `wikitable` top 10 (colonnes #, Coureur, Équipe, Temps ; `{{bandiera|CAN}}`, `{{ITA-d}}`, `{{BLR}}`) pour 1990 / 1998 / 2005, mais **`{{Cycling race/generalclassification|Q…}}` (Wikidata) pour 2000, 2003 Ain, 2002 Dauphiné** ; en = `wikitable` top 10 (1990, 2000), mais Paris-Tours 1998 et Plouay 2005 : tableau imbriqué dans un `{|` (compté 1 ligne, parseur naïf insuffisant).
- Tour de l'Ain 2003 : article fr de 1,3 ko, entièrement modèles Wikidata ; en / de absents. Dauphiné 2002 : fr et en = modèles Wikidata.
- Modèles hétérogènes selon l'âge de l'article (≥ 6 familles de modèles de drapeaux : bandiera, XXX-d, Flag athlete, flagathlete, `{{FRA}}`, `{{États-Unis}}`), noms de coureur parfois barrés `<s>` (déclassés : Tour 2005 « Place vacante »).
- Régularité : **aucun format commun** ; en le plus riche et régulier pour les grands tours ; fr suffisant (top 10) pour les classiques de 1990-2008 mais non homogène ; de rarement utile.

## 6. Incohérences relevées
- Tour de France 1999-2005 : P1346 = « non attribué » (Q66666778) alors que P2321 rang 1 = Lance Armstrong (7 éditions) ; 8 éditions ≤ 2008 avec « non attribué » en tête ; pages fr/en traitent les déclassements différemment (« Place vacante », texte barré).
- P1346 rang 1 ≠ P2321 rang 1 : 10 éditions sur 1 170 comparables (3 hors Tour : Liège 1974, 1981 ; Lombardie 1973 : ex æquo / deux rang 1).
- P1346 pointe parfois vers une équipe ; 2 éditions avec plusieurs rang 1 ; doublons d'année (Chrono des Nations 1995 et 2021, champ. de France 1907).
- Qualificatifs P1352 absents sur 5 éditions ayant un classement.

## 7. Volume et requêtes
- Échantillon : 39 séries -> 2 298 éditions ≤ 2008 (59 en moyenne) ; 150 séries : ~5 000-9 000 éditions ≤ 2008 (+ ~3 000 de 2009-2010).
- Wikidata seul : ~7 requêtes/série (recherche, comptes, éditions par 50) + ~1 requête par 40 coureurs distincts ; ~1 500 requêtes pour 150 séries et leurs vainqueurs/podiums (~25 min à 1 req/s). Observé : ~45 min car IP partagée soumise à des 429 (Retry-After 8-60 s) -> prévoir reprise.
- Wikitext : 1 requête par article et par langue (~9 000 x 2) ou ~400 requêtes lots de 50 (100 Ko+ par article de grand tour) ; coûteux, hétérogène.

## 8. Recommandation (zéro hallucination, source citée par donnée)
Faisable proprement : **Wikidata seul** — séries, éditions (date P585/P580), vainqueur / podium (P1346+P2501), classement top 10-25 avec temps/écarts quand P2321 en a (≈ 46 % des éditions ≤ 2008 ont ≥ 10 lignes ; ~43 % avec temps), naissance des coureurs, liens Wikipédia (fr/en > 80 % pour les 23 grandes épreuves, < 30 % pour la plupart des .1 françaises). Champ `source: {qid, propriété}` par donnée ; valeur absente = vide ; ne jamais combler.
À éviter en première version : parsing du wikitext des tableaux (formats non homogènes) ; à n'envisager que pour les grands tours en (tableau GC complet), avec contrôle de cohérence contre P2321.
Précautions : traiter « non attribué » (Q66666778) et P1346/P2321 divergents comme conflit affiché (« vainqueur déclassé »), pas de choix automatique ; ignorer les P1346 vers des équipes ; gérer les championnats par `P527`.
Étapes : (1) séries + éditions + vainqueur/podium des 39 épreuves (extension à ~150 par liste de QID vérifiés, sans recherche par nom) ; (2) coureurs historiques par QID (cache, comme wikidata.py) ; (3) classements P2321 + liens Wikipédia ; (4) pages « épreuve » étendues (palmarès avant 2009 distinct des archives UCI, source affichée) ; (5) éventuellement GC complet des grands tours depuis en.wikipedia.

## 9. Règles retenues pour l'implémentation (`historique.py`, étape « Historique »)
Source unique : Wikidata (CC0), `source_qid` = élément de l'édition. Cache `entites/historique/`, schéma SPEC §4.5.
- **Série** : élément « course » dont chaque édition est une instance (P31 = QID de la série) ; liste par CirrusSearch `haswbstatement:P31=<QID>` (500 par requête), lecture des éditions par `wbgetentities` (50 par requête). Les séries sont celles de `series_historiques.json`, retenues par **preuve** : au moins 2 éditions 2019-2025 où le vainqueur Wikidata (statut `ok`) est NOTRE vainqueur (cache `entites/wikidata/coureurs.json`, sinon P569 jour + nom concordant) ; sinon refus, listé dans `series_historiques_refusees.json`. Extension aux épreuves suivies : `python historique.py --proposer` (recherche `wbsearchentities` par nom, classe P31 sous-classe de « course cycliste » Q15091377, au moins 3 éditions, même preuve ; deux candidates prouvées = refus « ambigu »).
- **Vainqueur / podium** : P1346 + P2501 (Q20882667 / 8 / 9). P1346 SANS P2501 = vainqueur ; P1346 avec un autre P2501 (maillots, classements annexes) ignoré ; P1346 vers un non-humain (équipe) ignoré (`detail.ignores`) ; seuls les P31 = Q5 sont des coureurs.
- **Statuts** (jamais tranchés) : `ok` ; `non_attribue` (rang 1 = Q66666778, `detail.p2321` = rang 1 du classement P2321 s'il existe) ; `conflit` (plusieurs rang 1, ou rang 1 de P2321 différent de P1346 : les deux valeurs dans `detail`) ; `inconnu` (aucun vainqueur humain).
- **Date** : P585, sinon P580 / P582 (précision de la source) ; sans date, année lue dans le libellé (`annee_source: "libelle"`) ; sans année : édition conservée dans le cache, non publiée dans les entités.
- **Championnat de France (conteneur)** : l'édition est un conteneur ; l'épreuve est l'élément P527 dont un libellé (fr, en, es, it, nl, de) correspond à « course en ligne masculine » / « men's (elite) road race » / « course en ligne hommes (élite) » et dont aucun libellé n'est féminin / junior / espoir / U23 / amateur / contre-la-montre / relais / équipes ; zéro ou plusieurs éléments retenus : `statut: "inconnu"`, `detail.raison` (jamais de choix arbitraire).
- **Coureurs** : nom fr, sinon en, sinon autre langue lue ; P569 / P570 à la précision de la source (plusieurs valeurs : la plus précise si les autres en sont des préfixes, sinon rien) ; nationalité = code CIO (P984) du ou des pays P27 (texte si un seul, liste sinon, absente si aucun pays n'a de code) ; `rider_id` seulement par le cache Wikidata ou par nom + date de naissance exacte et UN SEUL de nos coureurs.
- **Dans les entités** : seules les années ABSENTES de nos éditions UCI (clé ou clé sœur, même série) entrent dans `historique` ; records recalculés à part (UCI + historique, années couvertes mentionnées) ; coureurs d'avant nos données = entités légères `wd-<QID>`.
- **Réseau** : 1 requête/s, User-Agent du projet, 429 -> attente du `Retry-After` (borné à 120 s, 10 reprises par requête) sans abandonner l'hôte (`netutil.fetch_json(..., attendre_429=True)`), 403 -> abandon.

## 10. Mesures réelles du module (16 novembre 2026, `historique.py` contre wikidata.org)
- **39 séries** (44 clés d'épreuve de nos données : plusieurs noms successifs par série), toutes retenues par la preuve (au moins une clé par série ; 2 à 7 concordances sur 2019-2025, une seule discordance : La Polynormande 2022, Wikidata donne Franck Bonnamour, nous Lorenzo Rota) ; 13 clés refusées : 11 variantes de nom à une seule édition 2019-2025 (« moins_de_2_editions_2019_2025 ») et 3 des 4 clés du championnat de France (une saison par clé : à fusionner par `alias_courses.json` pour les prouver ensemble).
- **Volume** : 3 017 éditions (comme la sonde), 2 725 coureurs en cache (2 657 avec naissance au jour, 2 548 avec nationalité, 474 rattachés à un de nos `rider_id`), 255 requêtes réelles (166 pour les éditions et la preuve, 89 pour les coureurs et pays), ~19 min au total avec les 429 (attente de 8 à 54 s, ~25 fois) ; 5,9 min pour la seconde passe seule. Cache : 1,85 Mo ; entités : `coureurs_historiques/` 1,6 Mo (2 249 coureurs), `courses/` 2,4 Mo (contre 1,0), recherche +~0,4 Mo.
- **Statuts** (éditions de toutes les clés dédoublonnées par série) : ok 2 928, non_attribue 7 (Tour de France 1999-2005), conflit 20, inconnu 62 (dont éditions annoncées sans résultat, 62 au total à ces dates).
- **Extension automatique** (`--proposer`, 10 épreuves essayées) : 7 retenues (Giro dell'Emilia, Gran Piemonte, Milano-Torino, Le Samyn, Dwars door Vlaanderen, Kuurne-Bruxelles-Kuurne, La Route Adélie), 3 refusées (aucune candidate, preuve insuffisante) ; 190 requêtes, 16 min, soit ~19 requêtes par épreuve (~200 épreuves : plusieurs heures, reprenables avec `--budget-min`).

## 11. Équivalences de courses renommées (`alias_courses.json`, 16 novembre 2026)

Validées par le propriétaire. Preuve : chaque groupe de clés pointe vers le **même élément Wikidata de la série**
(`series_historiques.json` / `series_historiques_refusees.json`) ; canonique = la clé prouvée qui a le plus d'éditions dans nos
données. Vérifié sur une génération réelle d'`encyclopedie` : Paris-Roubaix 2018-2026 en une seule épreuve, championnat de
France 2018-2026 continu.

| Série Wikidata | Clé canonique | Clés rattachées |
|---|---|---|
| Q33992 | paris roubaix\|FRA | paris roubaix hauts de france |
| Q33970 | ronde van vlaanderen tour des flandres\|BEL | ronde van vlaanderen |
| Q655150 | criterium du dauphine\|FRA | tour auvergne rhone alpes |
| Q498661 | gent wevelgem in flanders fields\|BEL | in flanders fields from middelkerke to wevelgem |
| Q599219 | e3 saxo classic\|BEL | e3 saxo bank classic, e3 binckbank classic |
| Q506447 | omloop het nieuwsblad elite\|BEL | omloop nieuwsblad |
| Q740787 | donostia san sebastian klasikoa\|ESP | clasica ciclista san sebastian, dssk donostia san sebastian klasikoa |
| Q287950 | bretagne classic ouest france\|FRA | bretagne classic cic |
| Q32435 | national road championships france\|FRA | championnats nationaux route france, … me we, national road championships france elite |
| Q1572415 | la route d occitanie la depeche du midi\|FRA | la route d occitanie cic |
| Q1417470 | grand prix du morbihan\|FRA | grand prix de plumelec morbihan |
| Q1542681 | cholet pays de la loire\|FRA | cholet agglo tour |
| Q894986 | boucles de la mayenne credit mutuel\|FRA | boucles de la mayenne |
| Q1025846 | tour du limousin nouvelle aquitaine\|FRA | tour du limousin perigord nouvelle aquitaine |

### Ajout du 17 novembre 2026 : courses renommées des maillots distinctifs (25 groupes)

Demandé par le propriétaire (les maillots WorldDB restent quand la course change de nom ; les palmarès sont regroupés de la même façon).
Preuve, sonde `tools/essais/essai_alias_courses.py` (`[essai:alias_courses]`, run 43976590338, 461 requêtes, 8 min) : séries candidates
cherchées sur toutes les dénominations du groupe, puis concordance des vainqueurs de NOS éditions avec Wikidata sur **toutes les années**
(certaines dénominations n'ont servi qu'un an) ; retenu seulement si UNE série donne au moins une concordance et **aucune discordance pour
chaque clé**, et au moins 2 concordances au total. Canonique = clé qui a le plus d'éditions. Vérifié sur une génération réelle d'`encyclopedie`
(AlUla Tour 2020-2025, Tour of Britain 2017-2025, Route d'Occitanie 2017-2025, Langkawi 2017-2025 : une seule épreuve chacune).

| Série Wikidata | Clé canonique | Clés rattachées |
|---|---|---|
| Q290588 | etoile de besseges tour du gard\|FRA | etoile de besseges |
| Q1092873 | circuit des ardennes\|FRA | circuit des ardennes international |
| Q955021 | region pays de la loire tour\|FRA | circuit cycliste sarthe pays de la loire |
| Q3009575 | czech tour\|CZE | sazka tour |
| Q160696 | deutschland tour\|GER | lidl deutschland tour |
| Q1519385 | istarsko proljece istrian spring trophy\|CRO | istrian spring tour |
| Q1146627 | okolo slovenska tour de slovaquie\|SVK | tour de slovaquie |
| Q681555 | alpes isere tour\|FRA | rhone alpes isere tour |
| Q2357535 | international tour of rhodes\|GRE | tour of rhodes powered by rodos palace |
| Q1401155 | tour alsace\|FRA | tour d alsace |
| Q84318914 | alula tour\|KSA | saudi tour |
| Q15233563 | tour of sharjah\|UAE | sharjah tour |
| Q1519109 | cro race\|CRO | tour of croatia |
| Q505799 | postnord danmark rundt tour of denmark\|DEN | postnord tour of denmark |
| Q327365 | volta a portugal em bicicleta\|POR | volta a portugal santander, volta a portugal em bicicleta edicao especial |
| Q1572415 | la route d occitanie la depeche du midi\|FRA | route d occitanie, route du sud la depeche du midi (+ la route d occitanie cic) |
| Q22677272 | tour de la provence\|FRA | tour cycliste international la provence |
| Q505810 | skoda tour de luxembourg\|LUX | skoda tour luxembourg |
| Q918091 | tour of britain\|GBR | lloyds bank tour of britain men, ovo energy tour of britain, lloyds tour of britain men |
| Q27997365 | gree tour of guangxi\|CHN | tour of guangxi |
| Q775110 | petronas le tour de langkawi\|MAS | le tour de langkawi |
| Q181266 | itzulia basque country\|ESP | vuelta ciclista al pais vasco |
| Q1533156 | tour poitou charentes en nouvelle aquitaine\|FRA | tour du poitou charentes … vienne, tpc en nouvelle aquitaine |
| Q1431283 | volta ao algarve em bicicleta\|POR | volta ao algarve cofidis |
| Q2120129 | volta a la comunitat valenciana\|ESP | volta comunitat valenciana |

**Non regroupés** (pas de preuve, à revoir à la main si besoin) : une discordance sur une année — Tour du Loir-et-Cher (E. Provost 2018),
Tour of Qinghai Lake (2024), Presidential Tour of Turkey (2019), Visit South Aegean Islands (2025, série Wikidata peut-être différente
du South Aegean Tour) ; aucune série trouvée par la recherche — 4 Jours de Dunkerque (2017), Tour du Limousin (2017), Tour of Thailand
(3 graphies). Les maillots WorldDB de ces courses restent affichés sur toutes leurs dénominations (`COURSES_WORLDDB`).
