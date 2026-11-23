# Audit technique — Dashboard & Encyclopédie (`courses-cyclistes`)

**Date de l'audit** : 23 novembre 2026  
**Périmètre inspecté** :
- Front-end : `index.html` (310 166 octets, 4 111 lignes)
- Pipeline & entités : `encyclopedie.py` (132 294 octets, 1 841 lignes), `collector.py` (149 995 octets, 2 357 lignes), `netutil.py` (11 345 octets, 217 lignes)
- Référentiel pays historiques : `pays.py` (13 462 octets, 230 lignes), `pays_historiques.json` (13 047 octets, 502 lignes)
- Documentation de référence : `CLAUDE.md`, `docs/SPEC.md`, `docs/AVANCEMENT.md`, `docs/REDESIGN.md`

**Mesures de volume observées localement** :
- `data/` : 234 fichiers, ~43,3 Mio (43 340,5 KiB), dont `riders-2026.json` (~2,0 Mio), `races/uci-76399.json` (~1,86 Mio), `races/uci-76406.json` (~1,82 Mio), `races/uci-76390.json` (~1,80 Mio), `ranking.json` (~828 KiB), `ranking-2026.json` (~822 KiB).
- `tools/fixtures/data/` : 118 fichiers, ~2,1 Mio (2 115,3 KiB).
- Données publiées sur le dépôt d'archives (d'après `docs/SPEC.md` §4.5 et `docs/AVANCEMENT.md`) : ~26 940 coureurs (`entites/coureurs/index.json` ~2,2 Mo brut / ~0,5 Mo gzip), ~5 159 équipes-saisons, ~892 épreuves (`entites/courses/index.json` ~0,15 Mo).

### Synthèse exécutive

1. **Performance Front-end (`index.html`)** : la page d'accueil déclenche, au simple défilement (`IntersectionObserver`), un **éventail de ~26 requêtes HTTP parallèles** (`ceJourLa()`) pour charger l'intégralité de `entites/courses/<lettre>.json`. Les listes longues souffrent d'une **pagination destructive** (`innerHTML` complet) et d'une **absence totale de debounce** sur la recherche/filtrage (~27 000 coureurs filtrés à chaque frappe). Enfin, le cache mémoire (`cache = new Map()`) est **non borné** et force `cache: "no-cache"` même sur des archives immuables.
2. **Dette technique & finitions UI** : les 5 pages de liste (`Courses` / `Épreuves`, `Équipes`, `Coureurs`, `Classements`, `Recherche`) conservent l'ancienne coquille visuelle hors refonte Liquipedia. Les deux bugs fonctionnels de `docs/AVANCEMENT.md` — **onglet « Saison » de la fiche coureur** encore indexé par saison UCI via `riders*.json` et **fil d'Ariane des éditions reportées** (`crumbsEdition`) pointant vers `#courses/<année_civile>` — ont des causes racines identifiées et des correctifs directs.
3. **Optimisation Pipeline & Qualité des données (`encyclopedie.py`, `collector.py`, `netutil.py`)** : `construire()` contient un goulot quadratique $O(E^2 \cdot R)$ dans `_soeur_renommee()` (appelé deux fois par équipe-saison), des normalisations répétées sans cache (`netutil.normalize` / `slugify`), des doubles lectures de `ranking.json` et une rétention mémoire complète jusqu'à la fin de l'exécution. Côté pays historiques, `pays.py` et `pays_historiques.json` **implémentent déjà** la décision du 18/11/2026, mais **ne sont pas encore branchés dans `encyclopedie.py`**.
4. **Pont d'ingestion pré-2009** : `encyclopedie.construire()` n'expose aujourd'hui qu'un point d'extension historique (`historique.appliquer_historique` pour Wikidata). L'étape 2 des 5 sources historiques (`thesports`, `museo`, `cqranking`, `mdc`, `clics`) nécessite un module d'agrégation intermédiaire dédié pour éviter de coupler `encyclopedie.py` aux formats bruts des collecteurs.

---

## 1. Performance Front-end (`index.html`)

### 1.1 Poids et stratégie de chargement des index JSON

| Ressource | Volume observé / estimé | Stratégie actuelle dans `index.html` | Constat & risque |
|---|---|---|---|
| `entites/coureurs/index.json` | ~2,2 Mo brut (~0,5 Mo gzip), ~26 940 entrées | Chargé en bloc par `chargerCoureursIdx()` (l. 3471) sur `#coureurs` **et** via `mapCoureursIdx()` (l. 3894) dans `pageClassements` pour enrichir les instantanés UCI | Sur mobile (3G/4G ou CPU modeste), le téléchargement + `JSON.parse()` + tri initial (`ordreCoureurs`, l. 3821) bloque le thread principal sur la première ouverture. |
| `entites/equipes/index.json` | ~5 159 entrées | Chargé en bloc par `chargerEquipesIdx()` (l. 3473) sur `#equipes` | Taille raisonnable aujourd'hui, mais croîtra linéairement avec les saisons pré-2009. |
| `entites/courses/index.json` | ~0,15 Mo (~892 épreuves) | Chargé par `chargerEpreuvesIdx()` (l. 3472) sur `#courses/epreuves` **et** sur l'accueil via `ceJourLa()` | Léger et adapté à un chargement à la demande. |
| `entites/recherche/<lettre>.json` | Sharded en ~27 fichiers par initiale de mot | Chargé à la demande dans `chercher(q)` (l. 3278-3281) selon l'initiale du **mot le plus long** (`lettreRecherche`, l. 3273) | Bonne architecture de sharding, mais l'absence de debounce provoque des fetchs inutiles en rafale dès que le mot le plus long change d'initiale pendant la frappe (ex. `pa` → `par` → `pari` → `paris` OK, mais `tour de` → `tour fr` déclenche `t.json` puis `f.json`). |
| `riders-<année>.json` | ~2,0 Mo (`riders-2026.json`) | Chargé par `chargerRidersCourant()` (l. 1202) et `chargerFicheSaison()` (l. 2269) | Chargé pour afficher l'onglet « Saison » d'un coureur alors que l'entité `entites/coureurs/<lettre>.json` est déjà chargée. |

#### Goulot critique sur la page d'accueil : `ceJourLa()` (l. 3582-3603)
Lorsqu'on fait défiler la page d'accueil jusqu'à la section `#b-jour` (`IntersectionObserver` avec `rootMargin: "400px"`, `surVisible` l. 3610-3615), `ceJourLa()` exécute :
```js
const lettres = [...new Set(E.map(x => lettreId(x.k)))];
const F = await Promise.all(lettres.map(chargerCoursesEnt));
```
Cela déclenche **simultanément ~26 requêtes HTTP** (`entites/courses/a.json` à `z.json` + `_.json`), parse l'intégralité des fiches d'épreuves et de leur historique Wikidata en mémoire, **uniquement pour extraire au maximum 6 lignes** (`slice(0, 6)`, l. 3602).  
**Recommandation** : précalculer côté `encyclopedie.py` un fichier léger `entites/ce_jour_la.json` (indexé par `MM-JJ`, ne contenant que les 6 meilleures entrées par jour ou les dates ayant des vainqueurs connus — quelques dizaines de Ko au total), réduisant ces ~27 requêtes à **1 seule requête légère**.

### 1.2 Rendu DOM des listes longues & réactivité à la saisie

1. **Pagination destructive (`innerHTML` intégral)** :
   Les fonctions `majListeCoureurs` (l. 3851), `majListeEquipes` (l. 3785), `majListeEpreuves` (l. 3738), `majListeUci` (l. 1230) et `renderTable` (l. 1494) reconstruisent **la totalité du conteneur** (`box.innerHTML = ...`) de l'index `0` à `state.limitListe` (ou `state.limit`) à chaque clic sur « Afficher 100 de plus » (`co-more`, `eq-more`, `ep-more`, `uc-more`, `more`). À 500 ou 1 000 lignes affichées, chaque clic détruit et recrée l'intégralité des nœuds DOM et relance un reflow complet.  
   **Recommandation** : lorsqu'il s'agit uniquement d'un ajout de page (`*-more`), insérer uniquement la nouvelle tranche (`L.slice(prevLimit, newLimit)`) via `insertAdjacentHTML("beforeend", ...)` sur `.crows` / `.rows` et mettre à jour le seul bouton `.more`.

2. **Absence de debounce sur la saisie (`input`, l. 4016-4033)** :
   Le gestionnaire global `document.addEventListener("input", ...)` exécute de manière synchrone à **chaque frappe** :
   - Sur `#co-q` / `#co-eq` (`saisie`, l. 4007-4015) : filtrage complet des ~27 000 entrées de `state.cIdx` (avec `normIdx()` paresseux), `history.replaceState(...)`, et reconstruction DOM des 100 premiers résultats.
   - Sur `#sr-q` (l. 4024-4030) : appel immédiat à `majRecherche()` (requête réseau potentielle + filtrage + tri + rendu) et `history.replaceState`.
   - Sur `#uc-q` (l. 4031) : filtrage + rendu synchrone.  
   **Recommandation** : ajouter un debounce de **150–200 ms** sur les champs de recherche/filtrage (`#co-q`, `#co-eq`, `#ep-q`, `#eq-q`, `#sr-q`, `#uc-q`), tout en gardant la réactivité immédiate sur `Enter` / `Escape`.

3. **Surcoût récurrent dans `pageCoureurs()` (l. 3876-3879)** :
   À chaque ouverture de `#coureurs`, le code ré-exécute :
   ```js
   state.cIdx = state.cIdx.filter(c => /[\p{L}\p{N}]/u.test(c.n || ""));
   state.cIdx.forEach(c => { if (c.nat) N.set(c.nat, (N.get(c.nat) || 0) + 1); });
   ```
   Or `encyclopedie.py` (l. 882) filtre déjà les noms sans caractère alphanumérique avant d'écrire `coureurs/index.json`. Ce scan + regex Unicode sur ~27 000 objets + reconstruction de `N` est répété inutilement à chaque visite de la route. Il devrait être mémorisé une seule fois lors du chargement de `state.cIdx`.

### 1.3 Gestion du cache mémoire (`charger` / `chargerArchive`) et cache HTTP

Dans `index.html` (l. 1045-1067) :
```js
const cache = new Map();
async function charger(chemin) {
  if (cache.has(chemin)) return cache.get(chemin);
  const url = urlDonnee(chemin);
  const p = fetch(url, { cache: "no-cache" }).then(...);
  cache.set(chemin, p);
  p.catch(() => cache.delete(chemin));
  return p;
}
function chargerArchive(chemin) { return charger(`archives/${chemin}`); }
```
Trois faiblesses sont constatées :
1. **Cache mémoire non borné** : `cache` est une `Map` sans limite de taille ni politique d'éviction. Chaque fiche de course ouverte (jusqu'à 1,86 Mo pour un Grand Tour), chaque `riders-<an>.json` (~2 Mo), chaque lettre de `coureurs/<lettre>.json`, `courses/<lettre>.json` (ex. les ~26 fichiers chargés par `ceJourLa()`) et `recherche/<lettre>.json` reste indéfiniment en RAM. Sur mobile (mémoire contrainte sur iOS Safari / Android), une navigation longue cumule plusieurs dizaines de Mo d'objets JS, auxquels s'ajoutent les caches secondaires non bornés : `state.cOrd` (jusqu'à 4 copies triées de `cIdx`), `mapCoureurs` (`Map` de 27 000 entrées, l. 3893), `state.coursesEnt`, `state.eqSaison`, `state.indexes`, `state.archIndexes`.
2. **Cache HTTP `cache: "no-cache"` systématique (l. 1053)** : impose au navigateur une revalidation HTTP (304 / 200) sur **tous** les fichiers, y compris les ressources **immuables** (fiches de courses d'archives closes `<année>/races/*.json`, instantanés UCI `entites/classements/<année>/<date>.json`).  
   **Recommandation** : utiliser `{ cache: "default" }` (ou `"force-cache"`) pour les chemins d'archives immuables (`^\d{4}/races/` ou `entites/classements/\d{4}/` de saisons closes), et réserver `"no-cache"` aux index vivants (`index.json`, `seasons.json`, saison courante).
3. **`cache.clear()` trop agressif** : sur `retry-sr` (l. 4001) et `retry-index` (l. 4003), `cache.clear()` vide l'intégralité du cache applicatif alors que `.catch(() => cache.delete(chemin))` (l. 1063) a déjà purgé la promesse en erreur.

### 1.4 Accessibilité (a11y) et fluidité mobile (390 px)

**Points positifs vérifiés** :
- Mise en page mobile-first à 390 px : `overflow-x: hidden` sur `body` (l. 77), prise en compte de `env(safe-area-inset-bottom)` sur la barre inférieure, masquage de `#maj` sous 400 px (l. 117), `min-width: 0` et `overflow-wrap: anywhere` sur les titres et cellules pour éviter les débordements horizontaux, tableaux enveloppés dans `.tbl-wrap` (`overflow-x: auto`, l. 406).
- Bons attributs déjà en place : `aria-busy="true"` sur les squelettes, `aria-live="polite"` sur `#sr-msg` (l. 3315), `role="progressbar"` avec `aria-valuemin`/`max`/`now` sur `htmlProgression` (l. 3518), `aria-pressed` sur les interrupteurs, styles `:focus` présents.

**Lacunes d'accessibilité repérées** :
1. **Deux `<nav>` avec un `aria-label` identique** : `#dnav` (l. 908) et `#bnav` (l. 918) portent tous deux `aria-label="Menu principal"`. Les lecteurs d'écran listent deux repères de navigation indifférenciés. Il faut les distinguer (`Navigation principale` vs `Navigation mobile`) et masquer celui inactif via `display: none` (ce qui est déjà partiellement fait par CSS, mais les labels doivent rester distincts).
2. **Absence de lien d'évitement (« Aller au contenu principal »)** avant `<header class="top">` pour la navigation au clavier.
3. **Faux liens interactifs (`<span role="link">` et `<div role="link">`)** :
   - `.rlink` dans `plink()` (l. 1073) utilise `<span class="rlink" role="link" tabindex="0" data-rider="...">` au lieu d'un `<a href="#coureur/...">` natif : cela prive l'utilisateur du clic-milieu, du « Ouvrir dans un nouvel onglet » sur mobile (appui long) et de la prévisualisation d'URL.
   - `.rcard` dans `carteAccueil()` (l. 3542) utilise `<div class="rcard" role="link" tabindex="0">` et son gestionnaire clavier (l. 4035) ne réagit qu'à `Enter` (pas à `Space`, bien que ce soit un `role="link"`). L'approche *stretched-link* déjà utilisée dans `rowCoureur()` (`.crow.lk` + `a.nm.stretch`, l. 3848-3849) est nettement supérieure sémantiquement.
4. **Pattern `tablist` incomplet dans `htmlOnglets()` (l. 2308-2311)** : les boutons portent `role="tab"` et `aria-selected`, mais il manque `aria-controls`, un conteneur `role="tabpanel"` avec `aria-labelledby`, et la gestion clavier `ArrowLeft` / `ArrowRight` / `Home` / `End` attendue par WAI-ARIA.
5. **Absence de `@media (prefers-reduced-motion: reduce)`** : le bouton `#to-top` force `behavior: "smooth"` (l. 4054) et les transitions/animations CSS ne sont pas neutralisées pour les utilisateurs sensibles au mouvement.

---

## 2. Dette technique & finitions UI repérées

### 2.1 État des 5 pages de liste non refondues

Conformément à `docs/AVANCEMENT.md` (l. 79-80, 106-107) et `docs/REDESIGN.md` (l. 92), seules la coquille (`.pg`, `enteteListe`) et la sous-navigation (`htmlSousNav`) ont été posées sur les pages de liste :

| Page | Fonction dans `index.html` | État actuel & écarts par rapport au design Liquipedia modernisé |
|---|---|---|
| **Courses** | `pageCourses` (l. 3673), `pageEpreuves` (l. 3744) | Utilise encore `.tools` + `listeCourses` (cartes simples) ou `.crows`/`.crow`. Manque le filet de catégorie homogène sur toutes les vues et la cohérence visuelle avec les cartes d'accueil/épreuve. |
| **Équipes** | `pageEquipes` (l. 3791) | Affiche des `.crow` basiques (l. 3780) sans **maillot** (`slotMaillot`) ni **logo de lignée** (alors que `lignees_index.json` dispose des logos). Le filtre `cat` dépend de `e.cat` qui est absent dès qu'une équipe a changé de division au cours de son histoire (ex. Pro → WT). |
| **Coureurs** | `pageCoureurs` (l. 3857) | Empilement vertical dense sur 390 px dans `.tools` (recherche + chips + `.two` selects + recherche équipe = 4 rangées avant la liste). L'onglet « Français » appelle encore `renderFrancais()` (l. 1302) dans l'ancien format `.fr-card`. |
| **Classements** | `pageClassements` (l. 3927) | Affiche `blocUci()` / `renderFdj()` dans l'ancien `.card.table-card` sans les composants unifiés (`htmlTableau` / pastilles de rang `dot` / tuiles récapitulatives). |
| **Recherche** | `pageRecherche` (l. 3952) | Gabarit minimaliste `.sr-input` + `.sr-body` ; les items `.sr-item` (l. 3307) n'affichent ni sous-titre contextuel (équipe actuelle, pays), ni distinction visuelle forte entre coureurs, équipes, lignées et courses. |

### 2.2 Cohérence des composants Liquipedia & hygiène du code

1. **Harmonisation des titres** (signalé dans `AVANCEMENT.md` l. 80, 107) : `htmlApercu()` utilise `Derniers résultats marquants` (l. 2483), alors que `pageAccueil()` utilise `Derniers résultats` (l. 3632) et les fiches équipes/épreuves utilisent des libellés différents (`Palmarès`, `Victoires`).
2. **Code mort / paramètres inutilisés dans `index.html`** :
   - `function saisie(champ, maj)` (l. 4007) : le paramètre `maj` n'est jamais utilisé dans le corps de la fonction.
   - `o.bandeau` dans `htmlInfobox(o)` (l. 1552-1554) est explicitement commenté comme inutilisé pour l'instant.
   - Redondance de requêtes legacy : `index.html` contient encore des références à `editions.json` (3 occurrences) et `carrieres/` (3 occurrences). Une fois la couverture complète d'`entites/` confirmée sur toutes les saisons, ces replis pourront être retirés (ce qui allégera aussi `collector.write_archives_index`).
3. **Niveau d'équipe par saison** (`docs/REDESIGN.md` l. 93) : `equipes/index.json` et `lignees_index.json` ne fournissent `cat` que si la lignée n'a eu qu'un seul niveau P31 sur toute son existence (car P31 n'est pas daté sur Wikidata). L'affichage d'un badge de niveau fiable par saison dans `pageEquipes` et sur l'infobox d'équipe reste donc bloqué côté données tant que les classes UCI des courses/équipes ou des P31 qualifiés par date ne sont pas exploités.

### 2.3 Analyse et correctifs des bugs listés dans `docs/AVANCEMENT.md`

1. **Onglet « Saison » de la fiche coureur encore par saison UCI (`AVANCEMENT.md` l. 36-37, 110-111)** :
   - **Cause racine** : `chargerFicheSaison(id, ctx)` (l. 2269-2294) charge `archives/<voulue>/riders.json` ou `riders-<voulue>.json`, qui sont générés par **dossier de saison UCI** (et non par année civile). Pour les ~50 courses reportées d'octobre–novembre (ex. Il Lombardia du 16/10/2010 rangé dans l'archive 2011), les totaux et résultats affichés dans l'onglet « Saison » divergent de ceux de l'onglet « Aperçu » / « Saisons » (lus depuis `entites/coureurs/<lettre>.json`, déjà en année civile).
   - **Correctif recommandé** : alimenter l'onglet « Saison » en priorité depuis `entites/coureurs/<lettre>.json` (`cr.ent.saisons[voulue]` et `cr.ent.palmares` filtré sur `season === voulue`), qui est **déjà chargé** à l'ouverture de la fiche coureur et respecte l'année civile. `riders*.json` ne servirait plus qu'en repli optionnel (ou pour lister les top 10/courses sans podium si l'on souhaite conserver le détail exhaustif, mais en appliquant le même décalage de date). Ce changement **supprime en prime un téléchargement de 2 Mo** (`riders-2026.json`) à l'ouverture d'une fiche coureur.

2. **Fil d'Ariane d'une édition reportée (`AVANCEMENT.md` l. 37, 111)** :
   - **Cause racine** : dans `crumbsEdition(c)` (l. 1576-1580) :
     ```js
     const nv = navEdition(c), y = saisonCourse(c), base = [["Accueil", "#/"], ["Courses", "#courses"]];
     if (nv && nv.cle) return htmlCrumbs(base.concat([[nv.nom, `#epreuve/${encodeURIComponent(nv.cle)}`], [String(y ?? c.name)]]));
     return htmlCrumbs(y != null ? base.concat([[String(y), `#courses/${y}`], [c.name]]) : base.concat([[c.name]]));
     ```
     Lorsque `nv` n'a pas de `cle` (course sans page d'épreuve ou avant chargement de `navEdition`), le lien `[String(y), "#courses/" + y]` utilise `y = saisonCourse(c)` (année civile, ex. `2010`), alors que `pageCourses` charge l'index de la **saison UCI** `2010/index.json` — qui ne contient pas la course (stockée dans `2011/index.json`).
   - **Correctif recommandé (immédiat)** : utiliser `c.season` pour le hash du lien `#courses/${c.season}` lorsque `c.season != null` (en gardant `String(y)` comme libellé ou `Saison UCI ${c.season}` si `c.season !== y`), ou à terme pointer vers `#saison/${y}` (étape R3).

3. **Autres points de reprise notés dans `AVANCEMENT.md` (l. 37-38, 110-112)** :
   - `winner` Vuelta 2011 dans `2011/index.json` : le correctif `reviser_vainqueurs_saison` a été implémenté et exécuté (bilan du 20/11 : « 5 vainqueurs recalculés ») — à marquer comme vérifié après contrôle visuel sur `#courses/2011`.
   - Jeu fictif `tools/fixtures/generer_archives.py` : contient encore une saison `2027` dans `entites/` selon `AVANCEMENT.md` l. 38 (à régénérer pour aligner les tests visuels `tools/apercu.py`).
   - Texte obsolète dans `encyclopedie.py` (l. 1069) : `index["limites"]` contient toujours `"pas d'historique du classement UCI (E1c)"`, alors que l'historique E1c est désormais collecté et exposé (462 instantanés d'après `AVANCEMENT.md` l. 143).

---

## 3. Optimisation Pipeline & Qualité des données (`encyclopedie.py`, `collector.py`, `netutil.py`)

### 3.1 Complexité algorithmique de `encyclopedie.construire()`

| Emplacement | Complexité actuelle | Problème identifié | Optimisation proposée |
|---|---|---|---|
| `_soeur_renommee()` (l. 1106-1123) | $O(E^2 \cdot R)$ par saison | Pour chaque équipe `tid` sans code, parcourt **toutes** les équipes `e2` de la saison et reconstruit `set(_rids(e2))` à chaque itération. De plus, **appelée deux fois** : dans `_heriter_lignees_renommees()` (l. 710) puis dans `_completer_equipes()` (l. 1170). | Pré-calculer `{tid: set_rids}` une seule fois par saison, construire un index inversé `rider_id -> [tids]` pour ne tester que les équipes partageant au moins 1 coureur, et mémoriser le résultat pour éviter le double calcul. Passage de $O(E^2 \cdot R)$ à $O(E \cdot R)$. |
| `_heriter_lignees_renommees()` (l. 1139-1141) | $O(E \cdot N)$ | Boucle linéaire `for t in eq_index: if t["id"] == tid:` sur tout `EQ_INDEX` (~5 159+ entrées) à chaque équipe héritée. | Maintenir un dict `eq_index_by_id = {t["id"]: t}` (complexité $O(1)$). |
| `netutil.normalize()` / `netutil.slugify()` (l. 171-180) | Répété ~50 000+ fois | Appelés sans cache dans `S.equipe()` (l. 370), `_codes_equipes()` (l. 555), `_traiter_course()` (l. 497), `construire()` (l. 739, 1025), et dans la fonction clé du `sort()` de `recherche/` (l. 1046, recalculé à chaque élément). | Ajouter `@functools.lru_cache(maxsize=16384)` sur `netutil.normalize` (les libellés d'équipes et de coureurs sont très répétitifs). |
| `_ecrire_si_change()` (l. 1254) & `collector._dump_if_changed()` (l. 82) | I/O + double parsing JSON | Relit et `json.load` ~500 fichiers existants pour comparer des `dict`/`list` Python. | Lorsque `ignore=()`, comparer directement la chaîne JSON sérialisée (`json.dumps(..., ensure_ascii=False, separators=(",", ":"))`) avec les octets lus sur disque (ou un hash), évitant la désérialisation complète. |
| Doubles lectures `ranking.json` & archives | 2× à 3× I/O | `ranking.json` est chargé dans `lister_sources()` (l. 341), puis dans `_uci_saison()` (l. 538) et à nouveau dans `_codes_equipes()` (l. 552). De plus, `collector.write_archives_index()` (l. 1355-1356) enchaîne `write_archives_editions_carrieres()` puis `write_entites()`, relisant deux fois les fiches d'archives. | Passer le `ranking` déjà chargé ou mettre en cache par chemin pendant l'exécution de `construire()`. À terme, unifier la génération d'`editions.json`/`carrieres/` avec `encyclopedie.py` ou supprimer la génération legacy si `index.html` n'en dépend plus. |

### 3.2 Gestion mémoire dans `construire()`

Actuellement, `encyclopedie.construire()` libère bien chaque fiche `race` après `_traiter_course` (`del race`, l. 617) et chaque saison `S` en fin de boucle (`del S`, l. 843), ce qui maintient l'empreinte autour de ~120 Mo sur 2019–2027 (`CLAUDE.md` l. 175).  
Toutefois, **toutes les structures agrégées restent en mémoire simultanément** jusqu'au retour de `construire()` : `COUR`, `COURSES`, `PAYS`, `EQ_PAR_AN`, `EQ_INDEX`, `EQ_RECH`, `HISTORIQUE`, `WD`, `HIST`, puis les dictionnaires de sortie `lettres`, `lettres_c` et `recherche` avant écriture. Avec l'arrivée de décennies d'archives pré-2009 (milliers d'éditions et dizaines de milliers de coureurs supplémentaires), le pic mémoire risque d'augmenter fortement.

**Recommandation** : séquencer les écritures et libérer (`del`) chaque bloc dès qu'il n'est plus nécessaire :
1. Finaliser et écrire `equipes/` (`lignees.json`, `index.json`, `<an>.json`, `lignees/<QID>.json`) puis `del EQ_PAR_AN, EQ_INDEX`.
2. Extraire les entrées `recherche` de `COUR` et `COURSES` en flux pendant l'écriture de `coureurs/*.json` et `courses/*.json`, puis `del COUR, COURSES, HISTORIQUE, WD, HIST`.

### 3.3 Qualité & robustesse de `netutil.py`

1. **Clés dupliquées dans `FLAG_CODES`** (`netutil.py` l. 189-217) :
   - `"ERI": "er"` apparaît **3 fois** (l. 196, 212, 214).
   - `"RWA": "rw"` apparaît **2 fois** (l. 207, 212).
2. **Divergence de codes CIO vs ISO3 entre `netutil.FLAG_CODES` et `encyclopedie.PAYS_NOMS` / `pays_historiques.json`** :
   - `netutil.FLAG_CODES` utilise `LVA`, `IRN`, `IDN`, `LBY`, `TRI`, `SGP`, `NGA`, `MWI`, `BRB`, `ATG`, alors que `encyclopedie.PAYS_NOMS` (et `pays_historiques.json`) utilisent les codes CIO/UCI `LAT`, `IRI`, `INA`, `LBA`, `TTO`, `SIN`, `NGR`, `MAW`, `BAR`, `ANT`. Sans unification (ou passage par `pays.drapeau`), `netutil.flag_code("LAT")` ou `netutil.flag_code("IRI")` renvoie `None`.
3. **Décompression gzip manquante sur `HTTPError` dans `fetch_text()`** (`netutil.py` l. 116-122) :
   - La requête envoie `"Accept-Encoding": "gzip"` (l. 101). En cas de succès (l. 110-111), `body` est décompressé si `body[:2] == b"\x1f\x8b"`. En cas de `HTTPError` (403, 429, 503), `txt = e.read(4000).decode(...)` (l. 119) **ne décompresse pas** si le serveur répond en gzip : `_looks_like_challenge(e.code, txt)` risque alors de manquer les marqueurs `"Just a moment"` / `"challenge-platform"`.

### 3.4 Normalisation des pays historiques (`Hon`, `Tch`, `Rfa`, `Urs`, `Rda` / `CSI`, `DDR`, `LAT`)

**Constat clé** : contrairement aux questions encore listées comme ouvertes dans `docs/AVANCEMENT.md` (l. 48, 56, 115-116), la décision du propriétaire du 18/11/2026 a **déjà été implémentée et testée** dans `pays.py` et `pays_historiques.json` :
- **11 pays disparus** modélisés avec code d'époque et drapeau Wikimedia Commons vérifié (`URS`, `GDR`, `FRG`, `TCH`, `YUG`, `SCG`, `EUN`, `AHO`, `ZAI`, `BOH`, `VSO`).
- **20 `codes_actuels_supplementaires`** dont `LAT`, `IRI`, `INA`, `LBA`, `TTO`.
- **Conversions complètes par source** :
  - `mdc` : `Hon` → `HUN`, `Rfa` → `FRG`, `Urs`/`Urss` → `URS`, `Rda` → `GDR`, `Let` → `LAT`, `Tch` → `TCH` jusqu'en 1992 puis `CZE` (`jusqu_a: 1992`, `apres: "CZE"`).
  - `museo` : `CSI` → `EUN`, `DDR` → `GDR`, `RFA` → `FRG`, `TCH` → `TCH` (≤ 1992) / `CZE` (> 1992).
  - `thesports`, `cqranking`, `clics` : tables complètes + `pays_ligne()` permettant de renormaliser à la lecture sans réécrire les données brutes.
- **Côté front-end (`index.html`)** : `DRAPEAUX_HIST` et `flag()` gèrent déjà les codes `h-<code_lower>` (vérifié par `python pays.py --test`, l. 214-221).

**Ce qu'il reste à brancher dans `encyclopedie.py`** (explicitement noté dans `CLAUDE.md` l. 237 : *« Intégration dans `encyclopedie.py` : à faire »*) :
1. Importer `pays` dans `encyclopedie.py` et remplacer `netutil.flag_code(code)` (l. 1011 et `_drapeau_pays` l. 1231) par `pays.drapeau(code)` (qui gère les pays disparus `h-urs`, les `codes_actuels_supplementaires` comme `LAT`, et `FLAG_CODES`).
2. Compléter `PAYS_NOMS` (ou consulter `pays.nom_historique(code)` et `pays.table()["codes_actuels_supplementaires"]`) pour éviter que tous les pays historiques et codes supplémentaires ne déclenchent `anomalies["pays_sans_nom"]` (l. 1018) et n'apparaissent sans nom français dans `pays.json`.
3. Mettre à jour `docs/AVANCEMENT.md` pour clore les questions tranchées le 18/11.

### 3.5 Préparation du pont d'ingestion pour les données pré-2009

Aujourd'hui, `encyclopedie.construire()` ne lit que les fiches UCI (`archives/` + `data/`) et le cache Wikidata d'historique (`historique.appliquer_historique`, l. 846). Les 5 collecteurs pré-2009 (`thesports.py`, `museo.py`, `cqranking.py`, `mdc.py`, `clics.py`) écrivent chacun leur propre format dans `ARCHIVES_DIR/sources/<source>/`.

Pour réussir l'Étape 2 sans alourdir ni fragiliser `encyclopedie.py`, il est recommandé d'introduire un **module pont dédié** (ex. `sources_historiques.py`) appelé au même niveau que `historique.appliquer_historique()`, avec le contrat suivant :
1. **Normalisation à la lecture (zéro réécriture des sources)** :
   - Pays : appel systématique à `pays.pays_ligne(source, ligne, annee)` (qui résout notamment les 2 921 lignes the-sports avec `nat` vide mais `nat_site` rempli, et les codes `Tch`/`TCH` post-1992).
   - Nettoyage déterministe des anomalies connues (`AVANCEMENT.md` l. 28-29) : retrait du `*` collé sur 629 noms CQ Ranking, normalisation « Prénom NOM » de Museo, validation des dates complètes uniquement.
2. **Rattachement des épreuves** :
   - Utilisation stricte de `collector.cle_edition(nom, pays)` + tables d'alias par source (ex. `alias_museo`, `docs/recherche/thesports_courses_proposees.json`), sans rapprochement flou.
3. **Cascade d'identité coureur (zéro hallucination)** :
   - Priorité 1 : identifiants externes Wikidata (`entites/wikidata/coureurs.json` champ `ids` et `ids_inverse.json` **uniquement** quand `statut == "ok"`, jamais `"a_verifier"`).
   - Priorité 2 : rapprochement strict `nom normalisé + date de naissance au jour exact` (disponible sur CQ Ranking, Museo, fiches the-sports, Clics).
   - Priorité 3 : Mémoire du Cyclisme (sans date de naissance ni id) — uniquement si le coureur est déjà rattaché sur une autre source la même saison/épreuve ou conservé en entité légère non fusionnée.
4. **Conservation multi-sources sans arbitrage** :
   - En cas de divergence entre sources (temps, rang, nom), conserver les entrées par source avec mention explicite (`source`: `"thesports"`, `"mdc"`, `"cqranking"`, `"museo"`, `"clics"`) pour permettre le crédit obligatoire dans l'UI.

---

## 4. Plan de priorisation (Impact / Effort)

### 4.1 Quick Wins (Impact élevé / Effort faible, < 0,5 jour)

| Priorité | Chantier | Fichier(s) | Impact attendu |
|---|---|---|---|
| **QW1** | **Corriger le fil d'Ariane des éditions reportées** (`#courses/${c.season}` quand `c.season != null`) + mettre à jour `AVANCEMENT.md` (pays historiques déjà implémentés) et supprimer la limite obsolète E1c (`encyclopedie.py` l. 1069) | `index.html`, `encyclopedie.py`, `docs/AVANCEMENT.md` | Corrige un bug de navigation utilisateur immédiat et aligne la doc. |
| **QW2** | **Ajouter un debounce (150–200 ms)** sur les saisies (`#co-q`, `#co-eq`, `#ep-q`, `#eq-q`, `#sr-q`, `#uc-q`) et retirer le re-filtrage regex inutile dans `pageCoureurs` | `index.html` | Supprime les saccades à la frappe sur 27 000 coureurs et évite les rafales réseau sur `#recherche`. |
| **QW3** | **Brancher `pays.drapeau` et `pays.nom_historique` dans `encyclopedie.py`** + nettoyer les doublons `FLAG_CODES` (`ERI`, `RWA`) et la décompression gzip sur `HTTPError` dans `netutil.py` | `encyclopedie.py`, `netutil.py` | Prévient les `pays_sans_nom` et drapeaux manquants pré-2009 ; renforce la détection anti-bot sur 403/503 gzippés. |
| **QW4** | **Optimiser `_soeur_renommee()`** (index inversé + appel unique), `eq_index_by_id` et **`@lru_cache` sur `netutil.normalize`** | `encyclopedie.py`, `netutil.py` | Réduit la complexité de $O(E^2 \cdot R)$ à $O(E \cdot R)$ et accélère la génération d'`entites/`. |
| **QW5** | **Adapter le cache HTTP dans `charger()`** (`default` sur archives immuables, `no-cache` sur index vivants) et retirer `cache.clear()` sur `retry-sr` | `index.html` | Évite les revalidations réseau inutiles sur les fiches d'archives déjà visitées. |
| **QW6** | **Accessibilité rapide & harmonisation titres** : skip-link, `aria-label` distincts pour `#dnav`/`#bnav`, `@media (prefers-reduced-motion: reduce)`, titre « Derniers résultats » unifié, suppression du paramètre mort `maj` dans `saisie()` | `index.html` | Améliore immédiatement la conformité a11y et la cohérence éditoriale. |

### 4.2 Chantiers structurels (Impact élevé / Effort moyen à fort)

| Priorité | Chantier | Fichier(s) | Effort estimé | Impact attendu |
|---|---|---|---|---|
| **CS1** | **Précalculer `entites/ce_jour_la.json`** côté `encyclopedie.py` et remplacer le `Promise.all` des 26 lettres dans `ceJourLa()` | `encyclopedie.py`, `index.html` | ~0,5–1 j | Élimine **~26 requêtes HTTP parallèles** et ~2 Mo de parsing JSON sur la page d'accueil. |
| **CS2** | **Onglet « Saison » coureur en année civile** (lecture depuis `entites/coureurs/<lettre>.json` au lieu de `riders*.json`) + **pagination incrémentale DOM** (`insertAdjacentHTML`) + **cache LRU borné** | `index.html` | ~1–1,5 j | Corrige le dernier bug année civile d'`AVANCEMENT.md`, économise un fetch de 2 Mo et stabilise la RAM mobile. |
| **CS3** | **Refonte Liquipedia des 5 pages de liste** (`Courses`/`Épreuves`, `Équipes`, `Coureurs`, `Classements`, `Recherche`) + vrais liens `<a href>` (*stretched-link*) et navigation clavier complète `tablist` | `index.html` | ~2–3 j | Achève la refonte visuelle (`docs/REDESIGN.md`), corrige l'a11y des liens et améliore l'ergonomie mobile à 390 px. |
| **CS4** | **Pont d'ingestion pré-2009 (`sources_historiques.py`, Étape 2 → 3)** + **libération mémoire par phases** dans `encyclopedie.construire()` + comparaison directe des octets dans `_ecrire_si_change()` / suppression progressive du doublon `editions.json` & `carrieres/` | `sources_historiques.py` (nouveau), `encyclopedie.py`, `collector.py`, `index.html` | ~3–5 j | Intègre 100+ ans d'archives multi-sources sans faire exploser la RAM du pipeline ni la durée de build. |
