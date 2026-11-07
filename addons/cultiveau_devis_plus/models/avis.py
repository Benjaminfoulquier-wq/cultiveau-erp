"""Les avis du référentiel : des règles simples (des mots dans le devis, un type d'installation) qui déclenchent une note technique
citant la section, la page et le niveau de prescription (§ 1.4.3). Les règles livrées viennent du V4 ; l'adhérent gérant peut en ajouter."""
import re
import unicodedata

from odoo import api, fields, models

NIVEAUX = [("exigence_reglementaire", "Exigence réglementaire"), ("exigence_technique", "Exigence technique"),
           ("recommandation", "Recommandation"), ("ordre_de_grandeur", "Ordre de grandeur")]
GENRES = [("presence", "Quand ce matériel est dans le devis"), ("absence", "Quand ce matériel manque au devis"), ("toujours", "Sur tout devis du type")]


def plat(texte):
    """Minuscules, sans accents, pour comparer des mots."""
    texte = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in texte if not unicodedata.combining(c)).lower()


def mots(chaine):
    return [m.strip() for m in plat(chaine).replace(";", ",").split(",") if m.strip()]


def contient(corpus, liste):
    """Un des mots (ou expressions) de la liste se trouve-t-il dans le corpus ? Mot entier pour les mots courts, sous-chaîne sinon."""
    for m in liste:
        if len(m) <= 4:
            if re.search(rf"(?<![a-z0-9]){re.escape(m)}(?![a-z0-9])", corpus):
                return True
        elif m in corpus:
            return True
    return False


class Avis(models.Model):
    _name = "cultiveau.referentiel.avis"
    _description = "Avis du référentiel sur un devis"
    _order = "sequence, id"

    name = fields.Char("Sujet", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    genre = fields.Selection(GENRES, "Se déclenche", required=True, default="presence")
    mots_cles = fields.Char("Mots qui déclenchent", help="Séparés par des virgules ; cherchés dans les désignations, références et familles des lignes du devis. Pour « manque » : les mots dont l'absence déclenche l'avis.")
    si_present = fields.Char("Seulement si le devis contient", help="Pour « manque » : l'avis ne s'applique que si l'un de ces mots est présent (ex. une injection sans anti-retour).")
    types = fields.Char("Types d'installation", help="Clés séparées par des virgules (goutte_surface, goutte_enterre, micro_aspersion, couverture_integrale, couverture_partielle, enrouleur, pivot, mixte). Vide : tous.")
    texte = fields.Text("La note sur le devis", required=True)
    section = fields.Char("Section du référentiel", required=True)
    page = fields.Integer("Page")
    niveau = fields.Selection(NIVEAUX, "Niveau de prescription (§ 1.4.3)", required=True, default="recommandation")
    company_id = fields.Many2one("res.company", "Propre à l'adhérent", help="Vide : règle du réseau, visible de tous.")

    def libelle(self):
        self.ensure_one()
        niveau = dict(NIVEAUX)[self.niveau].lower()
        page = f", p. {self.page}" if self.page else ""
        return f"Référentiel Cultiveau V4, § {self.section}{page} ({niveau}) : {self.texte.strip()}"

    @api.model
    def pour_devis(self, order):
        """Les avis déclenchés par un devis : [(avis, lots concernés)]. Lots = noms des lots où le matériel apparaît (présence)."""
        lots = order.cultiveau_lots_corpus()
        corpus_total = " ".join(lots.values())
        type_s = order.cultiveau_type_systeme or ""
        resultats = []
        for a in self.search([("company_id", "in", [False, order.company_id.id])]):
            types = mots(a.types)
            if types and type_s not in types:
                continue
            if a.genre == "toujours":
                resultats.append((a, []))
            elif a.genre == "presence":
                concernes = [nom for nom, corpus in lots.items() if contient(corpus, mots(a.mots_cles))]
                if concernes:
                    resultats.append((a, concernes))
            else:
                if a.si_present and not contient(corpus_total, mots(a.si_present)):
                    continue
                if not contient(corpus_total, mots(a.mots_cles)):
                    resultats.append((a, []))
        return resultats
