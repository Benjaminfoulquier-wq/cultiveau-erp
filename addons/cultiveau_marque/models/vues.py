"""Le nom de l'éditeur n'apparaît dans aucun écran : exemples de saisie, info-bulles et libellés des vues sont réécrits."""
import re

from odoo import api, models

ATTRIBUTS = ("placeholder", "help", "string", "title", "confirm")


def sans_editeur(texte):
    texte = re.sub(r"(?i)(https?://)?(www\.)?odoo\.com", "https://www.exemple.fr", texte)
    return re.sub(r"\b(Odoo|ODOO)\b", "Cultiveau", texte)


def sans_editeur_texte(texte):
    """Dans un texte courant, l'éditeur est « la plateforme » (plateforme agréée, réseau…) plutôt que Cultiveau, qui n'est pas l'éditeur."""
    texte = re.sub(r"(?i)(https?://)?(www\.)?odoo\.com", "https://www.exemple.fr", texte)
    texte = re.sub(r"\b(to|vers) (Odoo|ODOO)\b", lambda m: f"{m.group(1)} la plateforme agréée", texte)
    return re.sub(r"\b(Odoo|ODOO)\b", "la plateforme", texte)


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
        # les textes des écrans eux-mêmes (réglages, assistants) : « Migrer vers Odoo » devient « Migrer vers la plateforme agréée »
        for noeud in arch.iter():
            if isinstance(noeud.tag, str):
                if noeud.text and "odoo" in noeud.text.lower():
                    noeud.text = sans_editeur_texte(noeud.text)
                if noeud.tail and "odoo" in noeud.tail.lower():
                    noeud.tail = sans_editeur_texte(noeud.tail)
        return arch, view
