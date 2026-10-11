"""Le climat de chaque département : de quoi adapter la frise culturale et les Kc à l'endroit où pousse la culture."""
from odoo import api, fields, models

ZONES = [("med_littoral", "Méditerranée littorale"), ("med_interieur", "Provence et vallée du Rhône méridionale"),
         ("sud_ouest", "Sud-Ouest"), ("aquitaine", "Aquitaine océanique"), ("centre_ouest", "Centre-Ouest"), ("centre_loire", "Centre et Val de Loire"),
         ("nord_bassin", "Bassin parisien et Champagne"), ("nord_manche", "Nord et Manche"), ("bretagne", "Bretagne"), ("est", "Est continental"),
         ("rhone_alpes", "Plaines de Rhône-Alpes et d'Auvergne"), ("limousin", "Moyenne montagne"), ("montagne", "Montagne"), ("tropical", "Tropical (DOM)")]
JOURS_MOIS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def pluie_efficace(pluie_mois):
    """La part de la pluie du mois réellement utile à la culture (formule FAO/AGLW, mm/mois)."""
    p = pluie_mois or 0.0
    return max(0.0, 0.8 * p - 25) if p > 75 else max(0.0, 0.6 * p - 10)


class Climat(models.Model):
    _name = "cultiveau.climat"
    _description = "Climat d'un département (ETo, pluie, vent, humidité, avance du calendrier)"
    _order = "code"
    _rec_name = "name"

    code = fields.Char("Département", size=3, required=True, index=True)
    name = fields.Char("Nom", required=True)
    zone = fields.Selection(ZONES, "Zone climatique")
    vent_u2 = fields.Float("Vent à 2 m en été (m/s)", digits=(3, 1), default=2.0,
                           help="Corrige le Kc de mi-saison et de fin de cycle (FAO-56, équations 62 et 65) : plus de vent, plus de besoin.")
    hr_min = fields.Float("Humidité relative minimale en été (%)", digits=(3, 0), default=45,
                          help="Air plus sec que 45 % : le Kc monte ; plus humide : il baisse (FAO-56).")
    decalage_jours = fields.Integer("Avance du calendrier (jours)", default=0,
                                    help="Par rapport à la frise France : négatif = les stades arrivent plus tôt (sud), positif = plus tard (nord, altitude).")
    source = fields.Char("Source", default="Zone climatique (normales 1991-2020) — à remplacer par la station Météo-France la plus proche")
    eto_1, eto_2, eto_3, eto_4, eto_5, eto_6 = (fields.Float(f"ETo {m}", digits=(3, 1)) for m in ("janv.", "févr.", "mars", "avr.", "mai", "juin"))
    eto_7, eto_8, eto_9, eto_10, eto_11, eto_12 = (fields.Float(f"ETo {m}", digits=(3, 1)) for m in ("juil.", "août", "sept.", "oct.", "nov.", "déc."))
    pluie_1, pluie_2, pluie_3, pluie_4, pluie_5, pluie_6 = (fields.Float(f"Pluie {m}", digits=(4, 0)) for m in ("janv.", "févr.", "mars", "avr.", "mai", "juin"))
    pluie_7, pluie_8, pluie_9, pluie_10, pluie_11, pluie_12 = (fields.Float(f"Pluie {m}", digits=(4, 0)) for m in ("juil.", "août", "sept.", "oct.", "nov.", "déc."))
    eto_annuelle = fields.Integer("ETo annuelle (mm)", compute="_compute_cumuls")
    pluie_annuelle = fields.Integer("Pluie annuelle (mm)", compute="_compute_cumuls")

    _sql_constraints = [("code_unique", "unique(code)", "Ce département a déjà son climat.")]

    @api.depends(*[f"eto_{m}" for m in range(1, 13)], *[f"pluie_{m}" for m in range(1, 13)])
    def _compute_cumuls(self):
        for c in self:
            c.eto_annuelle = round(sum(c.eto(m) * JOURS_MOIS[m - 1] for m in range(1, 13)))
            c.pluie_annuelle = round(sum(c.pluie(m) for m in range(1, 13)))

    def eto(self, mois):
        """L'ETo de référence moyenne du mois (mm/j)."""
        return self[f"eto_{mois}"] or 0.0

    def pluie(self, mois):
        return self[f"pluie_{mois}"] or 0.0

    @api.model
    def pour(self, departement):
        return self.search([("code", "=", (departement or "").upper())], limit=1) if departement else self.browse()
