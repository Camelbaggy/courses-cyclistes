# Mémoire du Cyclisme : structure, couverture et collecte (étape 1, `mdc.py`)

Sonde et essai du 18/11/2026 (~115 requêtes, 3,2 s entre requêtes, User-Agent « courses-cyclistes (accord Mémoire du Cyclisme) »).
Complète `sources_avant_2009.md` §2 (ancien domaine `.eu`, liens « classements complets » masqués) : sur le site refait
(`https://www.memoireducyclisme.fr/`, aussi `memoire-du-cyclisme.org`) **les liens d'année ne sont plus masqués**, les classements
complets sont lisibles.

Accord : obtenu par le propriétaire le 18/11/2026 auprès des administrateurs (Dominique Magnier et « Pierrot ») pour lire le
site par programme et afficher ses classements, crédit « Mémoire du Cyclisme ». Pas de `robots.txt` (404). Aucune protection
anti-robot rencontrée (HTTP 200, pas de challenge).

## 1. Structure réelle

Site statique « php free, sans cookie » (Namo WebEditor), pages en UTF-8 de 5 à 175 Ko, un gabarit unique : bandeau, menu de
gauche, colonne centrale (`<td width="472">`), colonne de droite (`<td width="147">`). Tout est relatif à la page, jamais d'URL
devinée par le collecteur : on suit les liens lus.

| Niveau | URL (exemples réels) | Contenu |
|---|---|---|
| Accueil | `/` | liens vers les rubriques : `ligne/en_ligne.html`, `etapes/etapes.html`, `disparues/disparues.html`, `championnats/championnats.html`, `amateurs/amateurs.html`, `criteriums/criteriums.html`, `eta_tdf/presentation_tdf.html` ; « Piste » et « Cyclo-cross » sans lien |
| Index de rubrique | `ligne/en_ligne.html` | liste de courses par groupe (ancres `<a name>` : World Tour, ProSéries, 1.1, 1.2, nationales ; nations pour les disparues ; types pour les amateurs) ; en gras = classement détaillé annoncé ; suffixe : `(Fra)` ou période `1989-2015` (disparues) |
| Course (palmarès) | `ligne/cla_morbihan.html`, `etapes/eta_td_limousin.html`, `amateurs/td_creuse.html`, `disparues/anc_circ_limousin.html` | titre `G.P Morbihan (Fra) - Cat. 1.PS` ; **toutes les éditions** en deux colonnes : année en gras (lien si classement détaillé), date en petit (`5 mai`, `1er juin`, `du 21 au 24 août`), `1. NOM Prénom (Nat)` pour les trois premiers ; sous un filet : remarques (changements de nom, « Non organisé en 1979 et 2005 », reclassements) |
| Classement d'édition | `cla_france/morbihan_1996.html`, `eta_france/limousin2003.html`, `anc_france_cla/circ_limousin_1945.html`, `cla_france/roubaix1926.html` | le dossier varie (`cla_<pays>`, `eta_<pays>`, `anc_<pays>_cla`) : suivre le lien |

Rubriques et pages de détail :

| Rubrique | Courses (index) | En gras | Détail |
|---|---|---|---|
| `ligne` (courses en ligne) | 455 : World Tour 21, ProSéries 35, 1.1 131, 1.2 250, nationales 18 | 246 | lues |
| `etapes` (par étapes) | 320 : 15 / 26 / 73 / 200 / 6 | 200 | lues |
| `amateurs` | 124 : par étapes 47, en ligne 69, CLM 3, championnats du monde 1, nationaux 4 | 38 | palmarès lu ; classements amateurs : un seul pointé dans l'essai (Creuse : aucun lien) |
| `disparues` | 1 362 : ALL 72, AUT 6, BEL 307, ESP 159, FRA 539, GBR 8, HOL 26, ITA 147, LUX 6, POR 5, SUI 39, USA 13, divers 35 | 1 142 | palmarès + classements (`anc_<pays>_cla/`) |
| `criteriums` | 1 774 liens (années `crit_AAAA`, communes `crit_<ville>`) | | **HTTP 404** sur les 3 pages de détail essayées (`crit_1975`, `crit_zwolle`, …) : non exploitable aujourd'hui |
| `championnats` | 87 liens (`chpt_france`, `chpt_mondial`…) | | **HTTP 404** sur 3 pages essayées : non exploitable aujourd'hui |
| `eta_tdf` (Tour de France) | une page par année (`tdf2003.html`, 55 Ko, + une page par étape dans `eta_tdf_2000_2009/`) | | hors périmètre de cette étape (déjà couvert ailleurs) |

Total accessible : **2 261 courses** (455 + 320 + 124 + 1 362). Les listes sont des courses « à nom stable » : une course renommée
peut figurer deux fois (ex. « Circuit de la Mayenne » en disparues, « Boucles de la Mayenne » en étapes) : le rapprochement avec nos
épreuves est l'étape 2.

## 2. Profondeur mesurée

Sur les pages lues (palmarès et classements) :

- **Palmarès** : tout l'historique de la course, podium (3 premiers) de chaque édition, tel qu'affiché. Morbihan 1974→2024 (47 éditions,
  « non organisé en 1979 et 2005 »), Limousin 1975→2024 (50), Boucles de la Mayenne 2005→2024 (19), Paris-Roubaix 1896→2023 (120),
  Tour de la Creuse amateurs 1988→2017 (29).
- **Classement détaillé** : seulement les éditions dont l'année est un lien. Morbihan 21 / 47 (1974, 1987, 1996, 2002, 2007, puis
  quasi toutes ensuite), Limousin 47 / 50, Mayenne 19 / 19, Paris-Roubaix 104 / 120, Creuse 0 / 29. Une édition sans lien n'a que son podium.
  - course d'un jour : classement **complet** des classés (Morbihan 1996 : 62 ; 1987 : 28 ; Paris-Roubaix 1926 : 86, 1989 : 57), distance,
    « Partants », « Classés », moyenne, date « Disputé le … » ; temps du vainqueur (`en 4h49'26"`) et écarts (`à 2"`) ;
  - course par étapes : liste des étapes (parcours, km), **top 10 à 20 de chaque étape**, **classement général complet** (Limousin 2003 : 72 classés ;
    1983 : 61), classements annexes (« Meilleur grimpeur », « Points chauds » avec points ; « Montagnes : », « Sprints : », « Espoirs : », « Equipes : »
    en pied), ligne `* Nom` après chaque étape (sens non confirmé), et pour les éditions anciennes (années 1979-1984 lues) **la liste des partants par équipe**
    (« Les partants » : équipe en gras, coureurs, `(ab.4°)` abandon à l'étape 4, `(forfait)`, `np.3°`) ;
  - certains classements sont tronqués par le site (`...` : Limousin 1980, GC 31 lignes) : champ `tronque`.
- **Équipes** : jamais dans les classements de pros (sauf la liste des partants des éditions anciennes de courses par étapes et « Equipes : » au pied) ;
  pour les amateurs `(El.2 - Vendée U)` = catégorie - club (champs `categorie`, `equipe`).
- **Nationalité** : code du site entre parenthèses (`Bel`, `All`, `Hol`, `Afs`…, une centaine de codes distincts vus) ; **absente pour les Français sur les pages de
  courses françaises anciennes** (« France = absence de mention »), mais écrite `(Fra)` sur les pages récentes et sur beaucoup de pages d'étapes. Le
  collecteur ne déduit jamais France d'une absence. Quelques codes ambigus ou fautifs restent hors table (`Hon` Hongrie ou Honduras, `Tch`, `Rfa`, `Urs`,
  `Rda`, `Ber`, `Fa`, `Fr`, `rus`, `Ouz`, `Isr`…) : comptés dans `codes_pays_inconnus`, complétés après vérification.
- **Date de naissance : aucune. Identifiant de coureur : aucun** (ni lien de fiche, ni numéro). Seul le nom est donné : « NOM Prénom » dans les palmarès (majuscules
  = nom de famille), « Prénom Nom » dans les classements (le vainqueur a son NOM en gras). Les deux ordres, les prénoms abrégés (`Jean-Phi.`) et les
  graphies (Kuschynski / Kuchynski) varient : le rattachement à nos coureurs devra se faire par nom normalisé + course + année (rapprochement strict, à décider en étape 2).
- **Temps** : seul le vainqueur a un temps absolu ; les autres un écart au premier, croissant, **uniquement quand il est écrit** (quand deux coureurs ont le même temps
  seul le premier porte l'écart, ou `m.t.`) : le collecteur n'infère pas « même temps ». Formats lus : `4h49'26"`, `8'00"`, `59"`. Centièmes (`5'55"74`, `3"26`,
  Boucles de la Mayenne 2007 : 10 lignes) : gardés en texte brut (`temps_brut`, `ecart_brut`).
- Coquilles de source relevées : « 23 Raymond » sans point (rang accepté), « 42. ? » (coureur inconnu : `inconnu: true`), « Partants : ? » (champ absent),
  Morbihan 1987 : classement « Laurent Bondi » contre palmarès « BIONDI Laurent » (le collecteur signale ce genre de divergence, `podiums_divergents`).

## 3. Collecteur `mdc.py`

Même architecture que `thesports.py` (voir sa docstring) : découverte accueil -> index -> courses (accueil et index en cache gzip), puis course par course
(page de course = palmarès de toutes les éditions, puis pages de classement des éditions `< --avant`, défaut 2009, sans borne basse ; le palmarès de TOUTES les
années est gardé dans `courses.json`), reprenable, jamais deux fois la même page, budget `--budget-min`, plafond `--max-requetes`, `--courses` (id `ligne-morbihan`
ou fragment d'URL), `--sections`, `--depuis`, `--relire`, `--garder-html`, `--decouverte-seule`, `--sans-decouverte`, `--test`.

Sortie `ARCHIVES_DIR/sources/mdc/` : `courses.json` (index + palmarès : `section`, `groupe`, `gras`, `classe_site`, `drapeau`, éditions `{annee, cle, date_txt, date | date_debut/date_fin, url, podium[], notes[]}`),
`editions/<id>/<année>.json` (`classements[]` de type `course` / `etape` / `general` / `autre`, `etapes`, `resume`, `annexes`, `equipes_partantes`, `podium_palmares`, `source_url`, `lu_le`),
`etat.json` `{termine, editions_restantes, courses_restantes}` (sans horodatage), `introuvables.json` (page en erreur : 2 essais puis abandon, `termine` reste atteignable),
`cache/`. Un 403 / 429 abandonne l'hôte pour le passage (`termine` faux).

Test sans réseau : `python mdc.py --test` (10 pages réelles de `tools/fixtures/mdc/` : accueil, trois index allégés, deux pages de course, quatre pages d'édition, plus un passage
complet découverte -> lecture -> reprise avec réseau simulé).

## 4. Essai local (3 courses françaises secondaires)

Commande : `python mdc.py --sortie <dossier hors dépôt> --courses ligne-morbihan,etapes-td_limousin,etapes-boucles_mayenne --sections ligne,etapes --avant 2009`
(`ligne-morbihan` = « G.P du Morbihan » = Grand Prix de Plumelec-Morbihan). 3 pages de course, 41 pages d'édition, **3 592 lignes de classement**, 784 Ko de JSON.

| Course | Palmarès MDC | Éditions lues (< 2009) | Vainqueurs MDC trouvés dans Wikidata (champ `historique`) |
|---|---|---|---|
| G.P du Morbihan | 1974→2024, 47 éditions | 5 | 35 concordants, 0 divergent, 12 années sans vainqueur dans Wikidata |
| Tour du Limousin | 1975→2024, 50 | 31 | 34 concordants, 0 divergent, 16 années sans vainqueur dans Wikidata |
| Boucles de la Mayenne | 2005→2024, 19 | 4 | 4 concordants, 1 « divergent » = translittération (Kuschynski / Kuchynski), 14 sans vainqueur dans Wikidata |

**73 vainqueurs concordants sur 74 comparables (l'écart restant n'est qu'une graphie)** : MDC est cohérent avec Wikidata et comble ~42 années où Wikidata n'a pas de vainqueur. Les podiums
(2e, 3e) n'ont pas été comparés systématiquement ; le palmarès et le classement détaillé de la même édition se recoupent (une seule divergence sur 41 éditions : la coquille de Morbihan 1987).
Wikidata historique de la Mayenne remonte à 1975, MDC à 2005 pour « Boucles de la Mayenne » (les éditions antérieures sont dans « Circuit de la Mayenne », rubrique disparues).

## 5. Volume estimé (ordre de grandeur, à confirmer)

- Découverte : 5 requêtes (accueil + 4 index) ; lecture des 2 261 pages de course : ~2 261 requêtes ≈ **2 h à 3,2 s**.
- Classements d'édition `< 2009` : non mesurable avant d'avoir lu les palmarès. Sur l'échantillon (courses secondaires françaises) 4 à 31 pages par course,
  Paris-Roubaix ~80. Hypothèse prudente 10 à 20 pages par course « en gras » × ~1 600 courses en gras ≈ **16 000 à 32 000 pages, soit 14 à 28 h**. À mesurer :
  le premier passage donne `editions_restantes` exact une fois les pages de course lues (`--decouverte-seule` ne suffit pas : il faut lire les palmarès).
- Poids : ~19 Ko de JSON compact par édition lue (784 Ko / 41), soit quelques centaines de Mo pour l'ensemble si tout est gardé (à compresser ou à réduire avant publication).
- Étalement conseillé : budget 50 min par passage (~900 pages), ~25 à 40 passages nocturnes.

## 6. Points ouverts

- **Identification des coureurs** : pas de date de naissance ni d'id. Piste : nom normalisé + équipe (listes de partants des éditions anciennes) + course + année contre les
  palmarès Wikidata et thesports ; ne jamais fusionner sur le seul nom. Les noms de famille composés / particules (« DE CLERCQ », « VAN DER POEL ») sont lus par la typographie.
- Rubriques `criteriums` et `championnats` : relire l'état du site plus tard (pages de détail absentes aujourd'hui) ; amateurs : vérifier la profondeur des classements (seul Creuse essayé).
- Ambiguïté des codes pays (`Hon`, `Tch`, `Rfa`, `Urs`, `Rda`), à trancher par le propriétaire avant mapping.
- Sens exact de `* Nom` après chaque étape (probablement le leader du général, non confirmé : gardé tel quel dans `etoile`).
- Centièmes de seconde (`5'55"74`) : non interprétés.
- Pages de classement d'éditions de courses disparues non essayées en profondeur (une page de course lue, `anc_circ_limousin`).
- Couverture des années sans lien : seul le podium existe.

## 7. À reporter dans CLAUDE.md

> **Mémoire du Cyclisme** (`mdc.py`, `docs/recherche/mdc_collecte.md`) : accord des administrateurs (Dominique Magnier et « Pierrot ») obtenu par le propriétaire le 18/11/2026 pour lire
> `memoireducyclisme.fr` (aussi `memoire-du-cyclisme.org`) par programme et afficher ses classements, crédit « Mémoire du Cyclisme ». Pas de robots.txt ; politesse quand même : User-Agent
> « courses-cyclistes (accord Mémoire du Cyclisme) », >= 3 s entre requêtes (`PAUSE_S` 3,2), aucune page demandée deux fois, abandon de l'hôte sur 403 / 429. Découverte accueil -> index
> (`ligne`, `etapes`, `amateurs`, `disparues` ; `criteriums` et `championnats` : pages de détail en 404, `eta_tdf` hors périmètre) -> page de course (palmarès de toutes les éditions, podium) ->
> page de classement de l'édition quand l'année est un lien (liens jamais devinés : le dossier varie). Ni date de naissance ni identifiant de coureur : seulement le nom (`affiche`) ;
> nationalité écrite seulement quand elle l'est (jamais déduite France) ; écarts et temps seulement quand ils sont écrits. Sortie `ARCHIVES_DIR/sources/mdc/` (`courses.json`,
> `editions/<id>/<année>.json`, `etat.json` `{termine, editions_restantes, courses_restantes}`, `introuvables.json`, `cache/`). Commande :
> `python mdc.py --sortie <dossier> [--avant 2009] [--courses ligne-morbihan] [--sections ligne,etapes] [--budget-min N] [--max-requetes N] [--relire]` ; tests : `python mdc.py --test`
> (pages réelles allégées de `tools/fixtures/mdc/`). Vainqueurs concordants avec Wikidata sur 3 courses françaises (73 / 74, l'écart = une translittération).
