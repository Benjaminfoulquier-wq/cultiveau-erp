{
    "name": "Cultiveau — persona client",
    "summary": "Qui est l'agriculteur en face, et comment lui parler : huit questions, cinq personas (Lion, Jaguar, Chat, Tortue, Abeille), et l'Agent qui croise persona, frise et cours.",
    "description": """
Le persona client
=================

« Le client ne cherche plus à être convaincu, il cherche à être compris. » Les cinq personas
agricoles de l'étude PRISM 2023 (BVA, Réussir, Agriconomie : 1 766 chefs d'exploitation), retenus
par les Journées Cultiveau 2025 :

- 🦁 **le Lion**, le leader : innovant, décide vite, aime être en avance ;
- 🐆 **le Jaguar**, l'opportuniste : calcule le retour sur investissement, cherche le meilleur deal ;
- 🐈 **le Chat**, le routinier : préfère ce qu'il connaît, change peu ;
- 🐢 **la Tortue**, le fidèle : loyal, relation longue, confiance ;
- 🐝 **l'Abeille**, le collaboratif : partage, échange, aime le collectif.

Chacun est rattaché au besoin qu'il cherche d'abord à satisfaire sur la pyramide de Maslow de
l'agriculteur (viabilité, sécurité, appartenance, estime, accomplissement). Depuis la fiche d'un
agriculteur, le commercial répond à huit questions, celles qui discriminent le mieux les cinq
groupes dans l'étude ; le persona est calculé et affiché avec le profil, l'approche, les arguments,
le canal, le moment et les pièges.

**L'Agent** (pilier 4 des Journées) croise le persona, la frise culturale (posture du mois, période
critique) et les cours agricoles pour recommander, sur la fiche et dans l'API de l'assistant
téléphonique, quand contacter et sur quel ton : « viticulteur Chat, après vendanges, cours du vin en
baisse → attendre la fin du stress, approche rassurante, fiabilité et témoignages, pas de prix tout
de suite ».
""",
    "version": "18.0.2.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_frise"],
    "data": [
        "security/ir.model.access.csv",
        "data/personas.xml",
        "views/persona_views.xml",
        "wizard/persona_wizard_views.xml",
        "views/res_partner_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
