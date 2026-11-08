# Essais réseau

Le conteneur de développement n'a pas d'accès réseau aux sources. Pour tester un module sur les vraies données :
écrire `tools/essais/essai_<nom>.py` (exécuté depuis la racine du dépôt : `sys.path.insert(0, ".")` puis
`import <module>`), puis pousser sur une branche `ccr-*` un commit dont le message contient `[essai:<nom>]`
(plusieurs balises possibles). Ajouter `[avec-ia]` pour autoriser Gemini (sinon `AI_BUDGET_SECONDS=0`).
Lire ensuite les logs du job « Essais réseau ».
