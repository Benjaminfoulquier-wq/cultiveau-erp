"""Le nom de l'éditeur n'apparaît dans aucun écran : exemples de saisie, info-bulles et libellés des vues sont réécrits."""
import re

from odoo import api, models

ATTRIBUTS = ("placeholder", "help", "string", "title", "confirm")


def sans_editeur(texte):
    texte = re.sub(r"(?i)(https?://)?(www\.)?odoo\.com", "https://www.exemple.fr", texte)
    return re.sub(r"\b(Odoo|ODOO)\b", "Cultiveau", texte)


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        for noeud in arch.xpath("//*[@placeholder or @help or @string or @title or @confirm]"):
            for attr in ATTRIBUTS:
                valeur = noeud.get(attr)
                if valeur and "odoo" in valeur.lower():
                    noeud.set(attr, sans_editeur(valeur))
        return arch, view
