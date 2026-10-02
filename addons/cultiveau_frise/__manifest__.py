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

Les stades et fenêtres sont renseignés par département (valeurs du Gard fournies) avec un repli
sur des valeurs générales.
""",
    "version": "18.0.1.0.0",
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
