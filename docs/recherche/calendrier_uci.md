# Calendrier UCI à venir et conditions d'utilisation

Date : 8 novembre 2026. Exploration depuis GitHub Actions (`tools/essais/essai_uci.py`, balise `[cal]`), 5 passes, une dizaine de pages
lues, pause de 1,2 s par hôte, aucun contournement.

## Verdict : pas de calendrier à venir exploitable proprement, `uci.list_upcoming()` renvoie `[]`

1. **DataRide** (`/iframe/Competitions/`) ne liste que les courses déjà courues ou en cours (voir `sonde_uci.md`). Les pages iframe
   (`Results`, `Competition`, `Race`, `Event`, `RankingDetails`…) ne contiennent aucun écran de calendrier prévisionnel.
2. **uci.org** : `https://www.uci.org/road/calendar` (et `/calendar/road/2ruOnavHX0dMGTCRozdYAU`, variante `fr.uci.org`) est un site
   rendu par composants React. Le HTML contient un `data-component="CalendarModule"` dont les `data-props` (JSON) donnent seulement
   les libellés, la liste des pays, un carrousel « Latest » (la seule entrée : les Mondiaux 2025 de Kigali) et un carrousel
   « Upcoming » **vide**. La liste des courses est chargée ensuite par le JavaScript de la page avec un **jeton Bearer embarqué dans
   `data-props.bearerToken`** : c'est un secret de l'application, pas une API publique documentée. Il n'a pas été utilisé (ni son
   contenu recopié) : s'en servir reviendrait à imiter l'application hors des conditions d'utilisation (voir ci-dessous).
   Les paramètres d'URL (`?discipline=ROA&raceCategory=ME&raceClass=1.1,2.1,1.UWT,1.Pro,2.Pro,2.UWT`) filtrent côté client : la page
   serveur renvoyée est identique (≈ 75 Ko). Les boutons « Download selection / season » du calendrier sont eux aussi dynamiques
   (aucun lien de fichier dans le HTML).
3. Aucun autre point d'entrée (flux ICS, CSV, JSON public, sitemap de courses) n'a été trouvé dans les pages et le script
   `main.js` (166 Ko, uniquement React et utilitaires).

**Pistes sans contournement pour le futur** : demander à l'UCI un accès officiel (API / export de calendrier) ; ou alimenter le
calendrier à venir depuis les sites des organisateurs déjà autorisés (ASO, accord obtenu) et le calendrier maintenu à la main
dans `docs/recherche/calendrier_courses.json` (hors périmètre de ce module). `list_upcoming` pourra alors être branchée sans
changer son contrat.

## Conditions d'utilisation (https://www.uci.org/terms-and-conditions/5TXuZIQvtkSJH1nYwf94FY, version anglaise, lue le 8/11/2026)

Résumé fidèle des sections utiles (le texte est rendu par un composant `ContentBlock`, d'où une lecture dans les `data-props`) :

- **III. Propriété intellectuelle** : le site est « une œuvre intellectuelle protégée » ; « toute reproduction, représentation,
  modification ou utilisation, complète ou partielle, du site ou de l'un de ses éléments, de quelque manière que ce soit, est
  expressément interdite » ; sont aussi interdits la copie, la création d'œuvres dérivées, la rétro-ingénierie, la vente,
  la cession, la sous-licence (« reproduction, representation, modification, or use … is expressly prohibited »). Aucune mention
  explicite de « scraping », de robots ni de réutilisation automatisée, mais aucune exception pour la réutilisation des données.
- **II. Accès et usage** : informations « données à titre informatif », exactitude non garantie ; tout lien hypertexte vers le site
  requiert l'autorisation écrite préalable de l'UCI.
- Loi applicable : droit suisse, tribunaux du canton de Vaud.
- Ces conditions visent **`www.uci.org`**. Les pages `dataride.uci.org/iframe/*` (conçues pour être intégrées chez des tiers) ne
  portent **aucune** mention légale, aucun lien « terms » ni « disclaimer » (pages `Results`, racine DataRide, `dataride.uci.ch/iframe`
  lues : 8 à 42 caractères de texte). `robots.txt` : rien d'interdit (voir `sonde_uci.md`).

**Lecture prudente pour le projet** : les résultats viennent d'endpoints iframe publics sans CGU propres ni restriction technique ;
la réutilisation du *site* www.uci.org (calendrier) est en revanche couverte par une clause d'interdiction générale. D'où : résultats
DataRide oui (usage non commercial, faible charge, attribution « Source : UCI DataRide » recommandée dans l'interface), calendrier
uci.org non, tant qu'une autorisation écrite n'a pas été obtenue. Ce n'est pas un avis juridique ; une demande à l'UCI
(`dataride`/`media`) lèverait le doute pour les deux usages.
