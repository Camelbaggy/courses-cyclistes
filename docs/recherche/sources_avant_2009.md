# Sources de résultats pour les saisons d'avant 2009 : recensement et évaluation (18/11/2026)

Sonde : `tools/essais/sonde_sources_avant_2009.py` (commandes `robots HOTE…` et `get URL`). User-Agent `courses-cyclistes (recherche)`, 2 s minimum entre deux requêtes sur un même hôte (10 s pour DirectVélo, Crawl-delay), cache disque, aucun contournement : un 403 / 429 / challenge est noté et l'hôte abandonné. Environ 10 à 15 pages par site (le-sports.org un peu plus : voir §1). Toutes les observations datent du **18/11/2026**, faites depuis le conteneur de développement. Rien n'est écrit dans `data/`. ProCyclingStats, FirstCycling et leurs miroirs n'ont pas été utilisés, même pour comparer.

Contexte : DataRide n'a rien avant 2009 (`archives_dataride.md`) ; avant 2009 le projet n'a que Wikidata (`historique.py`, vainqueur + podium, parfois top 10 : ~46 % des éditions ≤ 2008 ont ≥ 10 lignes, `historique_avant_2009.md`). Les contrôles de qualité ci-dessous comparent chaque source au cache Wikidata du 16/11/2026 (`historique/series.json` de la sonde précédente).

## Tableau récapitulatif

| Source | Couverture constatée | Profondeur | Technique | robots.txt / CGU | Verdict |
|---|---|---|---|---|---|
| **the-sports.org** | Tour de France 1903→, Paris-Roubaix 1933→, Amstel 1966→, menu « World Tour 1991 » (18 courses) ; courses secondaires françaises non trouvées | **Classement complet** (90 lignes Paris-Roubaix 1995, 626 lignes Tour 1998 = GC + chaque étape), équipe, nationalité (code à 3 lettres), temps | HTML statique, URLs `…-results-<année>-epr<id>.html` prévisibles via la page de la course | robots : allow général, pas de `Disallow` sur ces pages ; pas de CGU trouvées, « © All rights reserved » | **Utilisable avec accord à demander** (webmaster) |
| **memoire-du-cyclisme.eu** | ~400 courses en ligne + ~250 courses à étapes, dont de nombreuses courses françaises (Morbihan 1974→, Limousin, Mayenne, Denain, Cholet…) | **Podium de chaque édition** (nom + nationalité si étrangère, pas d'équipe) ; « classement complet » annoncé pour les courses en gras mais **liens masqués** (voir §2) | HTML statique WordPress, 1 page par course = toutes les éditions | robots : tout autorisé ; « Légal » : **mise en réseau / rediffusion interdites sans accord préalable**, base de données protégée (CPI L.112-3) | **Utilisable avec accord à demander** (association / webmaster) |
| **bikeraceinfo.com** | Paris-Roubaix 1896→ ; Tour, Giro, classiques, quelques courses à étapes ; peu de courses françaises secondaires (Haut-Var, Doubs, Paris-Tours…) | Classement complet pour les épreuves couvertes (PR 1995 : 70 classés + hors-délais), équipe abrégée, **sans rang ni nationalité** dans la liste | HTML statique, `classics/paris-roubaix/pr1995.html` | pas de robots.txt (404) ; © McGann Publishing, pas de CGU lues | **Utilisable avec accord** (Bill McGann), couverture trop étroite pour être la base |
| **cqranking.com** | Résultats **2003→** (course 27/06/2003 lue), points CQ ; lancé en 2007, « Anja-ranking » 2005 : le début réel de la base n'est pas établi | Résultats jusqu'aux places à points (top 10 d'une course 2.2 de 2003), équipe en code, **date de naissance et ID UCI sur la fiche coureur** | ASP classique, `race.asp?raceid=N`, `rider.asp?riderid=N` ; ids non chronologiques | pas de robots.txt (404) ; crédits : usage libre avec source citée, **usage commercial : demander la permission** | **Utilisable avec accord à demander** (info@cqranking.com) ; ne couvre que 2003-2008 |
| **Wikipédia (fr / en)** | Grands tours, classiques, quelques .1 françaises | top 10 en `wikitable` pour beaucoup de classiques ; GC complet (107-147 lignes) sur en pour les grands tours ; modèles Wikidata ailleurs | API MediaWiki, wikitext hétérogène | API documentée pour les robots (User-Agent) ; CC BY-SA | **Déjà étudié** (`historique_avant_2009.md` §5) : peu au-delà de Wikidata, parseur fragile |
| **LeTourDataSet** (GitHub, miroir de letour.fr) | Tour de France hommes 1903-2026 | GC complet (96 lignes en 1998 : rang, coureur, dossard, équipe, temps, écart) + étapes ; **ni nationalité ni naissance** | 4 CSV, `raw.githubusercontent.com` | **aucun fichier de licence** (404) ; les données reproduisent letour.fr (ASO) | **Tour seulement ; licence non établie, dérivé ASO : accord ASO requis** |
| **letour.fr / sites ASO (histoire)** | page `/fr/histoire` : onglets 1903→2026 | contenu des années chargé par `/fr/block/history/<id>/<hash>` | robots : **`Disallow: /*/block`**, `/*/ajax`, `/api` | Même avec l'accord ASO, ces chemins restent interdits par robots.txt | **Bloqué** (robots) ; demander à ASO un export |
| **Wayback Machine (web.archive.org)** | Archives cyclingnews 1995-2008 : **non vérifié** | — | hôte inaccessible depuis ce conteneur (connexion réinitialisée) | CGU / limites CDX non lues (`archive.org/about/terms.php` rendu en JavaScript, 2 Ko) | **Non évalué** : sonde à lancer depuis GitHub Actions |
| **cyclingnews.com (site actuel)** | Aucune archive 1990-2008 : `autobus.cyclingnews.com/results/archives/` redirige (301) vers `/race-results/` ; `/races/<course>-<année>/results/` : 404 | — | — | robots permissif sauf robots IA | **Sans objet** (archives seulement via Wayback) |
| **LNC / lncpro.fr** | Sélecteur d'année : 2026 et 2027 seulement | — | — | robots : autorisé | **Inutile pour l'historique** |
| **FFC (ffc.fr)** | non exploré au-delà de robots.txt (autorise tout sauf `/wp-admin/`) | — | — | — | Pas de piste d'historique trouvée |
| **DirectVélo** | `/resultats/<AAAA-MM-JJ>` répond pour 2003-08-22 | liste des épreuves du jour **chargée dynamiquement** (« Chargement en cours »), non vue dans le HTML | HTML + JS | `Crawl-delay: 10`, accord du propriétaire déjà obtenu | **À sonder davantage** : l'historique pré-2009 est-il rempli ? |
| **museociclismo.it** (Museo del Ciclismo) | « 106 pages » de courses en ligne (surtout italiennes), albo d'oro par course, fiches coureurs | vainqueur par édition lu sur une page ; classements par édition **non vérifiés** | HTML (`/content/corse/corsa/<id>-<nom>/index.html`) | robots : autorisé ; « Tutti i diritti riservati », données = « ricerca bibliografica » de l'auteur | **Accord à demander** si besoin ; piste secondaire (courses italiennes) |
| cyclebase.nl | — | — | — | robots : **`User-agent: * / Disallow: /`** (hors Google) | **Écarté** |
| les-sports.info | — | — | **Cloudflare « Just a moment », HTTP 403 dès robots.txt** | — | **Écarté** (pas de contournement) |
| siteducyclisme.net | — | — | domaine servant une page de paris thaïlandaise (`lang="th"`) | — | **Écarté** (domaine détourné) |
| radsportseiten.net / dewielersite.net | — | — | radsportseiten : titre de la page d'accueil injecté (« GBO007 … Situs Gaming Online … Gacor »), dewielersite.net : certificat invalide / injoignable | — | **Écarté** (intégrité douteuse) |
| cyclingarchives.com | « 14 800+ coureurs » en accueil, « 92+ profils, 8 courses majeures » dans « À propos » | — | WordPress, Cloudflare | robots permissif | **Écarté** (contenu éditorial incohérent, couverture minuscule) |
| Jeux de données ouverts | Mendeley « UCI race results 2010-2020 », arXiv « Geospatial Road Cycling Race Results » (2017-2023) | **aucune période avant 2009** | CSV | licences non lues | **Sans intérêt ici** |
| WielerFlits (offre « developers ») | historique complet annoncé, payant | — | — | non chargée par la sonde (information de recherche web) | Hors périmètre gratuit |

## 1. the-sports.org

- **robots.txt** (extrait) : `User-agent: *` interdit seulement `/accueil.php`, `/index.php`, `/admin.php`, `/go.php`, `/calendrier.php`, `/tmp/`, `/zz`, `/how-to-`, `/*.html/` ; des crawlers SEO nommés sont bloqués (AhrefsBot, SiteBot…) ; `Crawl-delay` de 2 à 10 s pour d'autres. Aucune règle contre notre usage ; Cloudflare en frontal mais **aucun challenge** (HTTP 200 sur toutes les pages).
- **CGU** : aucune page « mentions légales » trouvée (`/legal-notice.html`, `/terms-and-conditions.html` : 404). Pied de page : « © Copyright 2007-2026 - All rights reserved - Links - Site map - Contact » ; page contact : webmaster `webmaster_at_the-sports.org`, éditeur Vincent Duplessy (Épinal), partenariats possibles (`partnership_at_the-sports.org`), correction d'erreurs bienvenue. **Le droit de reprise n'est pas défini : accord à demander.**
- **URLs** : `cycling-<course>-results-<année>-epr<id>.html`, avec **la liste de toutes les éditions de la course sur chaque page** (donc 1 page de course donne les ~90 URLs). Les `id` ne suivent pas l'ordre des années (Amstel 1991 = 10110, 1992 = 10109, mais 2005 = 2381) : il faut lire les liens, pas deviner. Menu annuel « World Tour - 1991 » (18 courses avec lien).
- **Échantillons** :
  - Paris-Roubaix 1995 (`epr9234`) : 1 Franco Ballerini (ITA) Mapei-GB 6h27'08", 2 Andrei Tchmil (MDA) Lotto-Isoglass-Echo 1'56", 3 Johan Museeuw (BEL) ; 90 lignes classées. **Concorde** avec Wikidata (Ballerini / Tchmil / Museeuw).
  - Tour de France 1998 (`epr15611`) : GC 1 Pantani 92h49'46'', 2 Ullrich +3'21'', 3 Julich +4'08'' ; étape 1 (Dublin) Tom Steels, distance et vitesse ; 626 lignes au total. **Concorde** (Pantani / Ullrich / Julich).
  - Amstel Gold Race 1991 : 1 Frans Maassen (NED), 2 Fondriest, 3 Dirk De Wolf, 4 Thierry Laurent (FRA)… complet avec équipes.
- **Lacunes constatées** : la liste des éditions du Tour sur la page de prize list saute 1999-2005 (années Armstrong), Giro 2002 seulement à partir de 2002 sur la page de prize list (autres années non vérifiées) ; **aucune course secondaire française trouvée** dans les menus lus (pas de Limousin, Mayenne, Morbihan : non listés, la présence éventuelle des .1 / .2 Europe Tour d'époque n'est pas établie) ; **aucune date de naissance** ; noms de pays en codes maison (SPA, SWI, GER…) à convertir.
- **Volume** : ~30-40 courses × ~19 éditions (1990-2008) ≈ 600-800 pages, ~1 h à 2 s par page.
- Remarque de méthode : la sonde a dépassé le plafond de ~10 requêtes (≈ 15) pour cartographier les URLs ; aucune réponse anormale.

## 2. memoire-du-cyclisme.eu

- **robots.txt** : `User-agent: *` / `Disallow:` (seul un fichier JSON de plugin est interdit) + sitemap Yoast. Cloudflare en frontal, aucun challenge (200).
- **Légal** (`/site/legal.html`, fichier du 02/12/2024) : « droit d'usage privé, non collectif et non exclusif » ; « **toute mise en réseau, toute rediffusion, sous quelque forme que ce soit, partielle ou totale, sont interdites sans l'accord préalable de "Mémoire du cyclisme"** » ; la base de données « peut être considérée comme protégée » (CPI art. L.112-3). Site tenu par une association loi 1901 (pied de page « © 1997/2024 », page `association.html`), « plus de 70 000 pages de résultats » (accueil). **Accord indispensable** ; contact via `/site/contact.html` (non lue).
- **Structure** : `ligne/en_ligne.html` (401 liens `ligne/cla_<nom>.html`), `etapes/etapes.html` (252 liens `etapes/eta_<nom>.html`) ; **une page par course contient le podium de toutes les éditions** (nom en majuscules, nationalité entre parenthèses si étranger, dates parfois). Courses françaises très présentes : Morbihan (1974→ 2019), Limousin, Mayenne, Denain, Cholet, Plouay, Paris-Tours, Dauphiné, Paris-Nice…
- **Échantillons** :
  - Tour du Limousin 2003 (19-22 août) : 1 Massimiliano Lelli (Ita), 2 Laurent Lefèvre, 3 Thor Hushovd (Nor) ; Wikidata : Lelli / Lefèvre / Hushovd ; Wikipédia fr (Tour du Limousin 2003) : vainqueur Lelli. **Concorde.**
  - Boucles de la Mayenne 2005 (16-19 juin) : 1 Kuschynski (Blr), 2 Pchelkin (Rus), 3 Boggia (Ita) ; Wikidata : Kuschynski / Pchelkin / Boggia. **Concorde.**
  - GP du Morbihan 1996 : Capiot / Kirsipuu / Eeckhout ; 1990 : Museeuw / De Wilde / Redant (non comparés à Wikidata).
- **Point bloquant technique** : les courses en gras ont un « classement complet » en cliquant sur l'année, mais **tous les liens d'année sont réécrits vers la page d'accueil** (`href="https://www.memoire-du-cyclisme.eu"`) dans le HTML reçu (Morbihan 1996, Limousin 2003, Mayenne 2005, liste des courses en ligne pour Paris-Roubaix et Gand-Wevelgem). Les classements complets n'ont donc pas pu être lus ; `ligne/cla_paris_roubaix.html` et `cla_roubaix.html` : 404. Je n'ai pas cherché à reconstituer ces URLs (pas de devinette, ni de contournement) : **à demander au propriétaire du site**, en même temps que l'accord.
- Les listes ne donnent ni équipe ni date de naissance, et les nationalités ne sont données que pour les étrangers (France = absence de mention). Plusieurs formats de date selon les éditions (« 1er juin », « du 19 au 22 août »).
- **Volume** : ~650 pages (401 + 252) pour toutes les éditions de toutes les courses, soit ~25 min à 2 s par page : de très loin la source la moins chère pour le podium de **toutes les courses françaises secondaires**.

## 3. bikeraceinfo.com

- robots.txt : 404 (rien d'interdit). Serveur LiteSpeed, aucun challenge. Pages « About Us » : site des McGann (ex-Torelli Imports), « plus de 7 000 pages » ; pied de page « © McGann Publishing » ; pas de CGU trouvées (page contact sans mention de copyright).
- Page de course (`classics/paris-roubaix/paris-roubaix-index.html` : podium + temps + distance + vitesse de chaque édition, 1896→) et page d'édition (`pr1995.html` : « Complete Results » avec équipe abrégée et écart ; 178 partants, 70 classés). **Concorde** : Ballerini 6h27'08'', Tchmil +1'56'', Museeuw s.t.
- Pas de nationalité dans le détail, pas de rang numérique ; équipes abrégées (« Novel », « MG-Technogym ») ; liste de courses limitée (classiques, grands tours, quelques courses à étapes), très peu de courses françaises secondaires. **Accord à demander à McGann Publishing** ; utile en recoupement.

## 4. cqranking.com (CQ Ranking)

- Joignable en `https://cqranking.com/` (le nom `www.` donne une erreur de certificat) ; serveur IIS, pas de challenge ; **robots.txt : 404**.
- **Crédits** : « Our rankings are available for your own usage, but in that case we expect you to provide a correct source notification. When you want to use our rankings for commercial purpose, you have to ask our permission first. » ; création en 2007 (ancien « Anja-ranking » de Gigabike depuis 2005), successeur non officiel du classement UCI.
- **Données** : `race.asp?raceid=N` (course 10000 = Tvrdonice contre-la-montre, 27/06/2003, catégorie NCT3 : top 10 avec équipe en code, temps, points CQ ; course 2000 = étape 2005 d'un Tour 2.PTs) ; `rider.asp?riderid=N` donne **nom, date de naissance (30/10/1992 pour Tim Merlier), ID UCI**, équipes et rang par année ; téléchargements hebdomadaires `cqYYYYMMDD.zip` (xls) de 2007 à aujourd'hui seulement.
- **Intérêt réel pour avant 2009** : saisons 2003-2008 seulement (la borne basse exacte n'a pas été établie), résultats **limités aux places qui marquent des points**, mais le seul candidat avec **date de naissance par coureur**, utile pour relier un coureur de 2003-2008 à nos `rider_id` (naissance + nom). Pas d'avant 2003 constaté.

## 5. Wikipédia et Wikidata

- Déjà mesuré (`historique_avant_2009.md` §2-§5) : Wikidata = 46 % des éditions ≤ 2008 avec ≥ 10 lignes ; Wikipédia en = tableau GC complet (107-147 lignes) pour le Tour, fr = top 10 `wikitable` pour de nombreuses classiques mais aussi simples modèles Wikidata, formats hétérogènes (≥ 6 familles de modèles de drapeaux).
- **Constat nouveau (fr)** : l'article « Coupe de France de cyclisme sur route 2003 » (via `Cycling race/seasoninfobox|Q671471` et `Cycling race/calendarcustom|Q671471|podium=1`) affiche **les 15 courses et leurs podiums depuis Wikidata** : les saisons de la Coupe de France sont donc modélisées dans Wikidata (élément de saison Q671471 pour 2003) ; c'est la meilleure piste pour la Coupe de France sans autre source (à explorer dans `historique.py`). L'article « Tour du Limousin 2003 » (4,6 Ko) : infobox (vainqueur, meilleur grimpeur / sprinteur / jeune, équipe) + récit de la course, pas de tableau de classement. « Boucles de la Mayenne 2005 » : pas d'article fr sous ce titre.
- Note : `fr.wikipedia.org/robots.txt` contient `Disallow: /w/` (donc `api.php`), mais l'API est le canal prévu pour les robots (User-Agent identifiable) et déjà utilisé par le projet.

## 6. letour.fr / ASO et le miroir LeTourDataSet

- **letour.fr/robots.txt** : `Disallow: /admin /sonatadmin /api /graphql /login /*/ajax /*/block /*/login /*/sitemap`. La page `/fr/histoire` (HTTP 200, 250 Ko) contient un sélecteur d'années 1903→2026 mais **chaque `<div id="1998">` est vide** ; le contenu vient de `/fr/block/history/10791/<hash>` (`data-tabs-ajax`), chemin **interdit** par `/*/block`. Conclusion : l'historique du Tour n'est pas lisible sans violer robots.txt, **même avec l'accord ASO** (qui devrait fournir un export). Le CLAUDE.md note déjà que seule l'édition courante est servie par les autres chemins.
- **LeTourDataSet** (`raw.githubusercontent.com/thomascamminady/LeTourDataSet`, accessible) : `TDF_Riders_History.csv` (colonnes Rank, Rider, Rider No., Team, Times, Gap, B, P, Year, Distance, Number of stages, ResultType, TotalSeconds, GapSeconds ; 96 lignes pour 1998, dont Ullrich 2e à +3'21'' = 201 s), `TDF_Stages_History.csv` ; « all 113 editions » 1903-2026 ; le README précise que les données **reproduisent letour.fr** avec ses défauts (rangs sautés, lacunes 1905-1908). **Aucun fichier LICENSE** (404 sur `master/LICENSE`) ; une recherche web précédente mentionnait « MIT » sans que je l'aie vérifié : à considérer **non établi**. Données d'origine ASO soumises aux CGU ASO (art. 3.15, `sonde_orga.md`) : accord ASO nécessaire.

## 7. Wayback Machine / Cyclingnews 1995-2008

- `web.archive.org` : connexion réinitialisée depuis le conteneur (`curl: (35) Recv failure: Connection reset by peer`), alors que `archive.org` répond (200). `https://archive.org/robots.txt` : `Disallow: /control/`, `/report/` seulement. Les conditions d'usage (`/about/terms.php`) sont rendues en JavaScript (2 Ko de HTML) et n'ont pas pu être lues. **Rien n'est donc affirmé** sur l'API CDX, ses quotas ni la présence des pages `autobus.cyclingnews.com/results/archives/…`.
- Côté site actuel, l'ancien domaine `autobus.cyclingnews.com/results/archives/` redirige (301) vers `https://www.cyclingnews.com/race-results/`, qui ne propose pas d'années 1990-2008 (aucun lien `/races/…199x|200x` trouvé) ; `/races/paris-roubaix-1995/results/` : 404.
- À faire : sonde depuis GitHub Actions (renommer en `essai_sources_avant_2009.py` pour le workflow `essais.yml`) : lire les CGU d'archive.org, tester 5-10 requêtes CDX (`limit` faible) sur `cyclingnews.com/results/archives/`, mesurer la présence de Paris-Roubaix 1995 et du Tour 1998. Rappel : résultats Cyclingnews = droits d'auteur d'un éditeur commercial (Future) ; la copie Wayback ne lève pas ces droits.

## 8. Écartés (preuves)

- **cyclebase.nl** : `/robots.txt` → `User-agent: *` / `Disallow: /` (seuls Googlebot et Mediapartners-Google autorisés), puis interdictions explicites de `page=races`, `page=results`, `page=renner`…
- **les-sports.info** : `robots.txt` lui-même répond **HTTP 403 « Just a moment… » (Cloudflare)** ; abandon immédiat.
- **siteducyclisme.net** : robots.txt renvoie en fait une page HTML de paris en thaï (`<html lang="th">`, titre « แทงบอลUFABET… ») : domaine détourné.
- **radsportseiten.net** : `<title>` de l'accueil = « GBO007 | Situs Gaming Online Baru Resmi Radsport Gacor » (injection de spam) ; **dewielersite.net** injoignable (certificat ne correspondant pas à `www.dewielersite.net`, `dewielersite.net` ne se résout pas).
- **cyclingarchives.com** : page d'accueil « 14 800+ riders » mais « À propos » : « 92+ rider profiles, 8 major races » ; contenu éditorial récent, non fiable comme archive.

## RECOMMANDATION

### 1990-2008 : combinaison conseillée
1. **Base : Wikidata** (déjà en place, CC0, 100 % vainqueur / podium des 39 séries, naissance des coureurs) : à étendre aux saisons de la Coupe de France et aux .1 / .2 françaises par QID (piste §5).
2. **the-sports.org** pour les **classements complets** (équipe, nationalité, temps) des ~20-40 épreuves WT / grands tours / classiques, 1990-2008 : le plus riche constaté, mais **sans date de naissance** (rattachement coureur par QID Wikidata via nom + nationalité + année, avec contrôle de l'équipe ; sinon coureur sans identifiant). **Accord à demander au webmaster** (Vincent Duplessy ; `webmaster_at_the-sports.org`).
3. **memoire-du-cyclisme.eu** pour le **podium de toutes les épreuves françaises secondaires** (et de ~650 épreuves en tout), recoupé avec Wikidata (deux sources concordantes = affichage normal, divergence = conflit affiché comme pour `historique.py`). **Accord à demander** à l'association (légal : « mise en réseau interdite sans accord préalable ») ; demander aussi l'accès aux classements complets des courses en gras (liens masqués) et un export de la base.
4. **cqranking.com** pour 2003-2008 si on veut un identifiant coureur **à date de naissance** : accord à demander à info@cqranking.com (usage non commercial : source citée ; reprise dans une base publique : demander).
5. Recoupement ponctuel : bikeraceinfo.com (McGann Publishing) ; Wikipédia en pour le GC complet des grands tours (déjà possible, CC BY-SA, parseur fragile).

### Avant 1990
Wikidata (vainqueur + podium, décennies 1950-80 : 95-97 %), puis the-sports.org (Tour 1903→, Paris-Roubaix 1933→, Amstel 1966→, Vuelta 1935→ avec trous) et bikeraceinfo (Paris-Roubaix 1896→) pour le détail ; memoire-du-cyclisme pour les palmarès des courses françaises (Morbihan 1974→, présence des années plus anciennes non vérifiée).

### Accords à demander (ordre de priorité)
1. **Mémoire du cyclisme** (association, via `/site/contact.html`) : reprise des podiums et accès aux classements complets.
2. **the-sports.org** (webmaster) : reprise des classements détaillés avec crédit.
3. **CQ Ranking** (info@cqranking.com) : résultats 2003-2008 et dates de naissance.
4. **McGann Publishing / bikeraceinfo.com** : optionnel.
5. **ASO** : export de l'historique du Tour (le site l'interdit techniquement) ; vérifier avec l'auteur de LeTourDataSet / ASO la licence du CSV avant tout usage.
6. Wayback / Cyclingnews : pas d'accord possible à demander ici ; d'abord sonde depuis Actions.

### Effort estimé
- the-sports.org : parseur HTML simple (lignes « rang nom (PAYS) équipe temps »), ~600-800 pages, 1 passage de ~1 h 30 ; table de codes pays à écrire ; rattachement coureurs (le plus long) ; 2-3 jours.
- memoire-du-cyclisme : parseur du bloc « année / 1. 2. 3. » (formats de date et de nom variables), ~650 pages, 1-2 jours ; rattachement coureurs par nom.
- CQ : ~1 jour pour les fiches / courses, mais id de courses non chronologiques → passer par le calendrier / recherche du site.
- Schéma : étendre `historique/` (champ `source` par donnée, déjà dans le principe de `historique.py`) avec un classement détaillé par édition.

### Risques
Juridique (aucune des trois sources utiles n'autorise explicitement la reprise : tout est conditionné à un accord) ; fiabilité hétérogène (lacunes du Tour 1999-2005 chez the-sports.org, disqualifications, noms variables) → toujours afficher la source, jamais fusionner sans concordance, laisser vide ce qui manque (règle cardinale) ; identité des coureurs d'avant 2009 (pas de naissance hors Wikidata / CQ) ; sites amateurs fragiles (domaines détournés relevés : siteducyclisme.net, radsportseiten.net).

### Non établi (à vérifier, ne pas considérer comme acquis)
Existence et URL des « classements complets » de memoire-du-cyclisme ; couverture du Limousin / Mayenne / .2 françaises par the-sports.org ; date de début des résultats CQ avant 2003 ; contenu historique de DirectVélo avant 2009 ; contenu du Wayback pour cyclingnews ; licence du CSV LeTourDataSet ; contenu des pages d'édition de museociclismo.it.
