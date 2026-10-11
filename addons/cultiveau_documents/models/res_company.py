"""Les réglages des documents de l'adhérent : acompte, CGV, relances, mise en page."""
from odoo import api, fields, models

CGV_PAR_DEFAUT = """
<p><strong>1. Objet.</strong> Les présentes conditions régissent les ventes de matériel d'irrigation, les études et les travaux d'installation
réalisés par notre entreprise. Toute commande implique leur acceptation sans réserve.</p>
<p><strong>2. Devis.</strong> Nos devis sont valables trente jours. Ils sont établis d'après les éléments fournis par le client (surface, cultures,
ressource en eau, pression et débit disponibles). Toute modification de ces éléments peut entraîner une révision du prix.</p>
<p><strong>3. Commande et acompte.</strong> La commande est ferme à la signature du devis et au versement de l'acompte indiqué. Le matériel
spécifique est commandé chez nos fournisseurs à réception de l'acompte.</p>
<p><strong>4. Délais.</strong> Les délais de livraison et de pose sont donnés à titre indicatif ; ils dépendent des fournisseurs, de la météo et
de l'accessibilité des parcelles. Un retard ne peut donner lieu ni à annulation ni à indemnité.</p>
<p><strong>5. Livraison et réception.</strong> Le client vérifie le matériel à la livraison et signale toute réserve sous 48 heures. La mise en
service fait l'objet d'un procès-verbal signé des deux parties qui vaut réception des travaux.</p>
<p><strong>6. Prix et paiement.</strong> Les prix s'entendent hors taxes, TVA en sus au taux en vigueur. Sauf mention contraire, les factures
sont payables à trente jours. Tout retard entraîne de plein droit des pénalités au taux de trois fois le taux d'intérêt légal et une indemnité
forfaitaire de 40 € pour frais de recouvrement (art. L. 441-10 du Code de commerce). Aucun escompte pour paiement anticipé.</p>
<p><strong>7. Réserve de propriété.</strong> Le matériel reste notre propriété jusqu'au paiement intégral du prix ; les risques sont transférés
au client dès la livraison.</p>
<p><strong>8. Garanties.</strong> Le matériel bénéficie de la garantie du constructeur. Nos travaux sont garantis un an contre tout défaut de
pose. Sont exclus l'usure normale, le gel, les dégâts liés à l'eau (sable, calcaire, algues), le non-respect des consignes d'hivernage et
toute intervention d'un tiers.</p>
<p><strong>9. Responsabilité.</strong> Notre responsabilité est limitée au montant de la commande. Le client reste responsable de
l'autorisation de prélèvement, du respect des arrêtés préfectoraux et de la conduite de l'irrigation.</p>
<p><strong>10. Litiges.</strong> À défaut d'accord amiable, les litiges relèvent du tribunal de commerce du siège de notre entreprise.</p>
"""


class Societe(models.Model):
    _inherit = "res.company"

    cultiveau_acompte_pct = fields.Float("Acompte à la commande", default=30.0, help="En pourcentage du devis TTC.")
    cultiveau_cgv = fields.Html("Conditions générales de vente", translate=False, sanitize=True,
                                help="Imprimées en dernière page des devis. Le texte proposé est un modèle : faites-le relire.")
    cultiveau_mention_reseau = fields.Boolean("Mentionner « membre du réseau Cultiveau »", default=True)
    cultiveau_relances_devis = fields.Boolean("Relancer les devis sans réponse", default=True)
    cultiveau_relance_devis_jours = fields.Integer("Après (jours)", default=7)
    cultiveau_relance_devis_max = fields.Integer("Relances de devis au plus", default=2,
                                                 help="Au-delà, une activité « appeler le client » est créée pour le commercial.")
    cultiveau_relances_factures = fields.Boolean("Relancer les factures en retard", default=True)
    cultiveau_relance_facture_jours = fields.Integer("Après l'échéance (jours)", default=5)
    cultiveau_relance_facture_max = fields.Integer("Relances au plus", default=2)

    @api.model
    def cultiveau_mise_en_page(self):
        """À chaque mise à jour : la mise en page Cultiveau, la couleur et les CGV pour qui n'a rien choisi, la signature en ligne."""
        gabarit = self.env.ref("cultiveau_documents.external_layout_cultiveau")
        standard = self.env.ref("web.external_layout_standard", raise_if_not_found=False)
        for societe in self.sudo().search([]):
            vals = {}
            if not societe.external_report_layout_id or societe.external_report_layout_id == standard:
                vals["external_report_layout_id"] = gabarit.id
            if not societe.primary_color or societe.primary_color.lower() in ("#000000", "#875a7b", "#714b67"):
                vals["primary_color"] = "#0b8aa3"
            if not societe.secondary_color or societe.secondary_color.lower() in ("#000000", "#875a7b", "#714b67"):
                vals["secondary_color"] = "#183840"
            if not societe.cultiveau_cgv:
                vals["cultiveau_cgv"] = CGV_PAR_DEFAUT
            if not societe.portal_confirmation_sign:
                vals["portal_confirmation_sign"] = True
            if vals:
                societe.write(vals)

    def cultiveau_ligne_legale(self):
        """La ligne du pied de page : forme, SIRET, TVA — ce que la société a renseigné."""
        self.ensure_one()
        morceaux = [self.name]
        if self.company_registry:
            morceaux.append(f"SIRET {self.company_registry}")
        if self.vat:
            morceaux.append(f"TVA {self.vat}")
        if self.phone:
            morceaux.append(self.phone)
        if self.email:
            morceaux.append(self.email)
        if self.website:
            morceaux.append(self.website.replace("https://", "").replace("http://", "").rstrip("/"))
        return " · ".join(morceaux)
