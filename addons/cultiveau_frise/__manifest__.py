{
    "name": "Cultiveau — frise culturale",
    "summary": "Les cultures de chaque agriculteur, leurs stades et besoins en eau, et les deux moments où l'appeler.",
    "description": """
La frise culturale
==================

Un installateur d'irrigation vend en hiver et dépanne en été : Odoo ne le sait pas. Ce module
donne à chaque agriculteur ses cultures (surface, département) et dessine sa frise sur douze mois :
stades, coefficients culturaux (Kc), besoins en eau, irrigation recommandée, et surtout les deux
**fenêtres commerciales** de chaque culture : « projet » (l'agriculteur a le temps d'étudier) et
« achat » (il commande). Chaque mois, les clients qui entrent dans une fenêtre remontent dans la
liste « À contacter ce mois-ci » et une activité est créée pour leur commercial.

Chaque stade porte aussi la **posture** que l'agriculteur attend de nous, les quatre saisons
émotionnelles des Journées Cultiveau 2025 : écoute (hiver), support (printemps), discrétion (été et
périodes critiques : semis, floraison, récolte, vendanges), proposition (automne, après récolte).
Chaque culture porte la tendance de ses **cours** (hausse, stable, baisse), qui change le ton :
sécurité et retour sur investissement quand les cours baissent, innovation et ambition quand ils
montent. La fiche de l'agriculteur affiche sa posture du mois, toutes cultures confondues.

Les stades et fenêtres sont renseignés par département (valeurs du Gard fournies) avec un repli
sur des valeurs générales.
""",
    "version": "18.0.2.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_base"],
    "data": [
        "security/ir.model.access.csv",
        "data/frise_gard.xml",
        "data/cron.xml",
        "views/culture_views.xml",
        "views/res_partner_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
