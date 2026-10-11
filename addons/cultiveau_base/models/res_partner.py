from odoo import api, fields, models

TYPES = [
    ("agriculteur", "Agriculteur"),
    ("collectivite", "Collectivité"),
    ("particulier", "Particulier"),
    ("industrie", "Industrie"),
    ("plombier", "Plombier"),
    ("paysagiste", "Paysagiste"),
    ("pisciniste", "Pisciniste"),
    ("adherent", "Adhérent du réseau"),
    ("fournisseur", "Fournisseur"),
    ("partenaire", "Partenaire (coopérative, chambre, pépinière…)"),
    ("autre", "Autre"),
]


# Les types de clients (ceux qui achètent de l'irrigation) : chacun a son véhicule en guise de portrait.
CLIENTS = ["agriculteur", "collectivite", "particulier", "industrie", "plombier", "paysagiste", "pisciniste", "autre"]


def departement_depuis_code_postal(code_postal):
    """« 30100 » → « 30 », « 20167 » → « 2A », « 97400 » → « 974 »."""
    cp = (code_postal or "").strip().replace(" ", "")
    if len(cp) < 2 or not cp[:2].isdigit():
        return ""
    if cp.startswith(("97", "98")) and len(cp) >= 3 and cp[:3].isdigit():
        return cp[:3]
    if cp.startswith("20") and len(cp) >= 3 and cp[:3].isdigit():
        return "2A" if int(cp[:3]) < 202 else "2B"
    return cp[:2]


class ResPartner(models.Model):
    _inherit = "res.partner"

    cultiveau_type = fields.Selection(TYPES, string="Type de contact", index=True,
                                      help="Agriculteur, collectivité (mairie, syndicat, golf, stade…), particulier, industrie, plombier, paysagiste, pisciniste… "
                                           "Chaque type a son véhicule : on voit d'un coup d'œil qui fait quoi.")
    cultiveau_est_client = fields.Boolean("Client", compute="_compute_est_client", store=True, index=True)

    @api.depends("cultiveau_type")
    def _compute_est_client(self):
        for p in self:
            p.cultiveau_est_client = p.cultiveau_type in CLIENTS

    # ---------------------------------------------------------------- le portrait : un véhicule par type de client
    def _avatar_get_placeholder_path(self):
        if self.cultiveau_type in CLIENTS and not self.parent_id:
            return f"cultiveau_base/static/src/img/clients/{self.cultiveau_type}.svg"
        return super()._avatar_get_placeholder_path()

    @api.depends("cultiveau_type", "parent_id")
    def _compute_avatar_1920(self):
        super()._compute_avatar_1920()

    @api.depends("cultiveau_type", "parent_id")
    def _compute_avatar_1024(self):
        super()._compute_avatar_1024()

    @api.depends("cultiveau_type", "parent_id")
    def _compute_avatar_512(self):
        super()._compute_avatar_512()

    @api.depends("cultiveau_type", "parent_id")
    def _compute_avatar_256(self):
        super()._compute_avatar_256()

    @api.depends("cultiveau_type", "parent_id")
    def _compute_avatar_128(self):
        super()._compute_avatar_128()
    exploitation = fields.Char("Exploitation", help="Le nom de l'exploitation agricole, s'il diffère du contact.")
    departement = fields.Char(
        "Département", size=3, compute="_compute_departement", store=True, readonly=False, index=True,
        help="Déduit du code postal ; modifiable. Sert à la frise culturale (stades par département).")
    numero_court = fields.Char("Téléphone normalisé", compute="_compute_numero_court", store=True, index=True,
                               help="Chiffres seulement, au format international : pour reconnaître qui appelle.")

    @api.depends("zip")
    def _compute_departement(self):
        for p in self:
            if not p.departement or p.zip:
                p.departement = departement_depuis_code_postal(p.zip) or p.departement or ""

    @api.depends("phone", "mobile")
    def _compute_numero_court(self):
        for p in self:
            p.numero_court = normaliser_telephone(p.mobile or p.phone)

    @api.model
    def cultiveau_par_telephone(self, telephone, company=None):
        """Le contact qui a ce numéro (mobile ou fixe), dans la société donnée si précisée."""
        n = normaliser_telephone(telephone)
        if not n:
            return self.browse()
        domaine = [("numero_court", "=", n)]
        if company:
            domaine = ["&", ("company_id", "in", [company.id, False])] + domaine
        return self.search(domaine, limit=1)


def normaliser_telephone(numero):
    """« 06 12 34 56 78 » → « 33612345678 » ; « +33 6 12 34 56 78 » → idem ; vide si rien."""
    chiffres = "".join(c for c in (numero or "") if c.isdigit())
    if not chiffres:
        return ""
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    elif chiffres.startswith("0") and len(chiffres) == 10:
        chiffres = "33" + chiffres[1:]
    elif len(chiffres) == 9 and chiffres[0] in "123456789":  # un tableur a mangé le 0 initial
        chiffres = "33" + chiffres
    return chiffres
