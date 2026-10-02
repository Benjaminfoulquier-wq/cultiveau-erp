"""L'irrigation à l'usage (Journées Cultiveau 2025, atelier 5) : du CAPEX à l'OPEX.

L'agriculteur ne finance plus du matériel, il finance sa récolte : un prix au m³ tout inclus
(investissement, intérêts, maintenance, SAV), un volume cible agronomique, une mensualité lissée,
une bande de flexibilité 90–110 % (report en dessous, audit technique au-dessus), un transfert ou
un renouvellement en fin de contrat. Exemple du deck : maïs 30 ha, 50 000 € d'investissement,
3,25 % d'intérêts, 5 000 € de maintenance, 900 000 m³ sur dix ans → 0,073 €/m³, 0,081 €/m³ avec
10 % de marge, environ 600 € par mois.
"""
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import ValidationError

VOLUME_PAR_HA_DEFAUT = 3000.0  # m³/ha/an, ordre de grandeur d'une culture irriguée du Sud ; à remplacer par ETP × Kc × sol


def _fr(n, dec=0):
    s = f"{n:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s


def annuite(capital, taux_pct, duree_ans):
    """L'annuité constante d'un emprunt ; sans taux, le capital divisé par la durée."""
    if not capital or not duree_ans:
        return 0.0
    r = (taux_pct or 0.0) / 100.0
    if r <= 0:
        return capital / duree_ans
    return capital * r / (1 - (1 + r) ** -duree_ans)


class Usage(models.Model):
    _name = "cultiveau.usage"
    _description = "Simulation d'irrigation à l'usage"
    _order = "create_date desc"

    name = fields.Char("Simulation", compute="_compute_name", store=True)
    partner_id = fields.Many2one("res.partner", "Agriculteur", required=True)
    installation_id = fields.Many2one("cultiveau.installation", "Installation", domain="[('partner_id', '=', partner_id)]")
    sale_order_id = fields.Many2one("sale.order", "Devis de référence", domain="[('partner_id', '=', partner_id)]")
    culture_id = fields.Many2one("cultiveau.culture", "Culture")
    surface_ha = fields.Float("Surface (ha)", digits=(8, 2))
    volume_m3_an = fields.Float("Volume cible (m³/an)", digits=(12, 0), required=True,
                                help="Le besoin agronomique : ETP × Kc × surface, borné par le volume autorisé. "
                                     "À défaut, 3 000 m³/ha/an.")
    volume_source = fields.Char("D'où vient le volume", compute="_compute_defauts", store=True, readonly=False)
    investissement = fields.Float("Investissement (€ HT)", digits=(12, 0), required=True)
    taux_pct = fields.Float("Taux d'intérêt (%)", digits=(5, 2), default=3.25)
    duree_ans = fields.Integer("Durée (ans)", default=10, required=True)
    entretien_an = fields.Float("Maintenance et SAV (€/an)", digits=(12, 0), default=500.0)
    marge_pct = fields.Float("Marge (%)", digits=(5, 2), default=10.0)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    interets = fields.Float("Intérêts sur la durée (€)", compute="_compute_calculs", digits=(12, 0))
    cout_total = fields.Float("Coût complet (€)", compute="_compute_calculs", digits=(12, 0))
    volume_total = fields.Float("Volume sur la durée (m³)", compute="_compute_calculs", digits=(12, 0))
    prix_m3 = fields.Float("Prix de revient (€/m³)", compute="_compute_calculs", digits=(8, 4))
    prix_m3_marge = fields.Float("Prix client (€/m³)", compute="_compute_calculs", digits=(8, 4))
    mensualite = fields.Float("Mensualité lissée (€/mois)", compute="_compute_calculs", digits=(12, 2))
    mensualite_capex = fields.Float("Mensualité d'un crédit classique (€/mois)", compute="_compute_calculs", digits=(12, 2),
                                    help="Le même investissement au même taux, sans la maintenance ni le SAV.")
    volume_min = fields.Float("Bande basse 90 % (m³/an)", compute="_compute_calculs", digits=(12, 0))
    volume_max = fields.Float("Bande haute 110 % (m³/an)", compute="_compute_calculs", digits=(12, 0))
    comparatif_html = fields.Html("CAPEX ou usage", compute="_compute_calculs", sanitize=False)

    @api.constrains("duree_ans", "volume_m3_an", "investissement")
    def _verifier(self):
        for u in self:
            if u.duree_ans <= 0 or u.volume_m3_an <= 0 or u.investissement <= 0:
                raise ValidationError("Durée, volume et investissement doivent être positifs.")

    @api.depends("partner_id", "culture_id", "duree_ans")
    def _compute_name(self):
        for u in self:
            u.name = f"Usage — {u.partner_id.name or '?'}" + (f", {u.culture_id.name.lower()}" if u.culture_id else "") + f" sur {u.duree_ans or 0} ans"

    @api.onchange("installation_id", "sale_order_id")
    def _onchange_defauts(self):
        for u in self:
            i = u.installation_id
            if i:
                u.surface_ha = u.surface_ha or i.surface_ha
                u.culture_id = u.culture_id or i.culture_pointe_id
            if u.sale_order_id and not u.investissement:
                u.investissement = u.sale_order_id.amount_untaxed
            if not u.volume_m3_an:
                u.volume_m3_an, u.volume_source = u._volume_par_defaut()

    @api.depends("installation_id", "surface_ha")
    def _compute_defauts(self):
        for u in self:
            if not u.volume_source:
                u.volume_source = u._volume_par_defaut()[1]

    def _volume_par_defaut(self):
        """(volume, explication) : le besoin de pointe sur 60 jours s'il est connu, sinon 3 000 m³/ha, borné par le volume autorisé."""
        self.ensure_one()
        i = self.installation_id
        surface = self.surface_ha or (i.surface_ha if i else 0.0)
        if i and i.besoin_pointe_mm_j and surface:
            volume, source = i.besoin_pointe_mm_j * 10 * surface * 60, f"besoin de pointe {i.besoin_pointe_mm_j:g} mm/j × 60 jours × {surface:g} ha"
        else:
            volume, source = VOLUME_PAR_HA_DEFAUT * surface, f"{_fr(VOLUME_PAR_HA_DEFAUT)} m³/ha/an × {surface:g} ha (ordre de grandeur)"
        if i and i.volume_autorise_m3 and volume > i.volume_autorise_m3:
            volume, source = i.volume_autorise_m3, f"volume autorisé {_fr(i.volume_autorise_m3)} m³ (le besoin calculé le dépasse)"
        return volume, source

    @api.depends("investissement", "taux_pct", "duree_ans", "entretien_an", "marge_pct", "volume_m3_an")
    def _compute_calculs(self):
        for u in self:
            n = max(u.duree_ans or 0, 0)
            a = annuite(u.investissement, u.taux_pct, n)
            u.interets = max(a * n - u.investissement, 0.0)
            u.cout_total = u.investissement + u.interets + (u.entretien_an or 0.0) * n
            u.volume_total = (u.volume_m3_an or 0.0) * n
            u.prix_m3 = u.cout_total / u.volume_total if u.volume_total else 0.0
            u.prix_m3_marge = u.prix_m3 * (1 + (u.marge_pct or 0.0) / 100)
            u.mensualite = u.cout_total * (1 + (u.marge_pct or 0.0) / 100) / (12 * n) if n else 0.0
            u.mensualite_capex = a / 12 if n else 0.0
            u.volume_min, u.volume_max = (u.volume_m3_an or 0.0) * 0.9, (u.volume_m3_an or 0.0) * 1.1
            u.comparatif_html = u._rendre_comparatif()

    def _rendre_comparatif(self):
        self.ensure_one()
        lignes = [
            ("Investissement initial", f"{_fr(self.investissement)} € à financer", "aucun : il paie l'eau qu'il utilise"),
            ("Mensualité", f"{_fr(self.mensualite_capex, 2)} €/mois de crédit, plus les pannes", f"{_fr(self.mensualite, 2)} €/mois tout inclus"),
            ("Prix de l'eau", "—", f"{self.prix_m3_marge:.3f} €/m³ (revient {self.prix_m3:.3f})"),
            ("Maintenance, SAV, obsolescence", "à sa charge, imprévisibles", "inclus, matériel entretenu (valeur résiduelle 90 % au lieu de 40 %)"),
            ("Année pluvieuse", "mensualité identique", f"bande 90–110 % : {_fr(self.volume_min)} à {_fr(self.volume_max)} m³ sans ajustement ; report en dessous, audit au-dessus"),
            ("Fin de contrat", "matériel vieilli", "transfert de propriété ou renouvellement (réinvestissement de 25 % pour cinq ans de plus)"),
        ]
        corps = "".join(f"<tr><th style='text-align:left;padding:4px 8px'>{escape(t)}</th><td style='padding:4px 8px'>{escape(c)}</td>"
                        f"<td style='padding:4px 8px;background:#e3f1d9'>{escape(u)}</td></tr>" for t, c, u in lignes)
        return Markup("<table style='border-collapse:collapse;width:100%;font-size:13px'><thead><tr><th></th><th style='text-align:left;padding:4px 8px'>Achat + crédit (CAPEX)</th>"
                      "<th style='text-align:left;padding:4px 8px'>Irrigation à l'usage (OPEX)</th></tr></thead><tbody>" + corps + "</tbody></table>"
                      f"<p style='font-size:12px;color:#5d6b78;margin-top:6px'>Coût complet sur {self.duree_ans} ans : {_fr(self.cout_total)} € "
                      f"(investissement {_fr(self.investissement)}, intérêts {_fr(self.interets)}, maintenance {_fr((self.entretien_an or 0) * self.duree_ans)}) "
                      f"pour {_fr(self.volume_total)} m³. Volume : {escape(self.volume_source or '')}.</p>")

    def action_pitch(self):
        """La phrase d'accroche des Journées, posée dans le fil de l'agriculteur."""
        self.ensure_one()
        self.partner_id.message_post(body=Markup(
            f"<p><b>Irrigation à l'usage</b> — « Et si vous ne payiez que l'eau que vous utilisez vraiment, sans investissement lourd ? » "
            f"{escape(self.culture_id.name) if self.culture_id else 'Votre culture'} sur {self.surface_ha:g} ha : "
            f"<b>{self.prix_m3_marge:.3f} €/m³</b> tout inclus, soit <b>{_fr(self.mensualite, 2)} €/mois</b> lissés sur {self.duree_ans} ans, "
            f"maintenance et SAV compris. Avec Cultiveau, vous ne financez plus du matériel, vous financez votre récolte.</p>"))
        return True


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    usage_ids = fields.One2many("cultiveau.usage", "installation_id", string="Simulations à l'usage")
    nb_usages = fields.Integer(compute="_compute_nb_usages")

    def _compute_nb_usages(self):
        for i in self:
            i.nb_usages = len(i.usage_ids)

    def action_simuler_usage(self):
        self.ensure_one()
        volume, source = self.env["cultiveau.usage"].new({"installation_id": self.id, "surface_ha": self.surface_ha})._volume_par_defaut()
        devis = self.sale_order_ids.sorted("date_order", reverse=True)[:1]
        return {"type": "ir.actions.act_window", "name": "Irrigation à l'usage", "res_model": "cultiveau.usage", "view_mode": "form",
                "context": {"default_partner_id": self.partner_id.id, "default_installation_id": self.id, "default_surface_ha": self.surface_ha,
                            "default_culture_id": self.culture_pointe_id.id, "default_volume_m3_an": volume, "default_volume_source": source,
                            "default_sale_order_id": devis.id, "default_investissement": devis.amount_untaxed if devis else 0.0}}
