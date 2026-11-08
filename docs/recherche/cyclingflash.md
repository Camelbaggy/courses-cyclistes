# cyclingflash.com : rapport de conformité (8 novembre 2026)

**Verdict : source inutilisable, aucun module écrit.** Sonde `tools/essais/essai_calendrier.py` exécutée depuis
GitHub Actions (run 42479398085, User-Agent honnête de `netutil`, une requête toutes les 2 s) :

| URL | Résultat |
|---|---|
| `https://cyclingflash.com/robots.txt` | HTTP 403, page « Just a moment... » |
| `https://cyclingflash.com/` | HTTP 403, même page |
| `https://cyclingflash.com/calendar/road/2027/uci-world-tour` | HTTP 403, même page |

En-têtes : `Server: cloudflare`, `Cf-Mitigated: challenge`, `Content-Type: text/html`. Le corps est un défi Cloudflare
« managed » (`cType: 'managed'`, `challenges.cloudflare.com`, « Enable JavaScript and cookies to continue »).

Conséquences : robots.txt et les CGU n'ont pas pu être lus (le défi s'applique à tout, robots.txt compris) ; un robot
sans navigateur est donc explicitement refusé par le propriétaire du site. Passer ce défi exigerait un faux navigateur ou
un jeton de session, ce que CLAUDE.md interdit. Pistes éventuelles : demander à cyclingflash.com une autorisation
écrite / un flux ou une API publique (contact via le site), ou une liste blanche de l'UA. Sans cela, ne pas réessayer.
