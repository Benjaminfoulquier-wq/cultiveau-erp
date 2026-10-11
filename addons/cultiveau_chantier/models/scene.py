from odoo import fields, models


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _chantiers(self, company, taches):
        """La vue d'ensemble montre les chantiers (planifiés, en cours) avec leur équipe et leur avancement."""
        res = super()._chantiers(company, taches)
        chantiers = self.env["cultiveau.chantier"].search([("company_id", "=", company.id), ("etat", "in", ("planifie", "en_cours"))], order="etat desc, date_debut asc", limit=8)
        res["chantiers"] = [{"id": c.id, "nom": c.name, "titre": c.titre, "client": c.partner_id.name, "etat": c.etat, "type": c.type_systeme,
                             "chef": c.chef_id.name or "", "equipe": len(c.equipe_ids), "debut": fields.Date.to_string(c.date_debut) if c.date_debut else "",
                             "fin": fields.Date.to_string(c.date_fin) if c.date_fin else "", "avancement": c.avancement, "surface": c.surface_ha} for c in chantiers]
        deja = set(chantiers.installation_id.ids)
        res["installations"] = [i for i in res["installations"] if i["id"] not in deja]
        return res

    def _compteurs(self, company, taches):
        res = super()._compteurs(company, taches)
        res["chantiers"] = self.env["cultiveau.chantier"].search_count([("company_id", "=", company.id), ("etat", "in", ("brouillon", "planifie", "en_cours"))])
        return res
