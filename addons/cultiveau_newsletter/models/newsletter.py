"""Le générateur de newsletters de l'adhérent.

La newsletter porte la marque de l'adhérent (logo, couleur) et, en pied seulement, « Membre du réseau Cultiveau ».
Le design est soigné et robuste pour les boîtes mail (tableaux, styles en ligne, pas de CSS externe) : bandeau coloré,
cartes de chiffres clés, encadrés à icônes, bouton d'appel. Le contenu des besoins en eau est ancré dans le référentiel
V4 (tableau A2.1 p. 137, pilotage par bilan hydrique § 16.2.1 p. 109, dose maximale § 6.3.1 p. 44, ET0 x Kc § 6.2.1
p. 42) et complété par les coefficients culturaux déjà tenus dans la base. Tout est créé en brouillon : l'adhérent relit
et envoie lui-même.
"""
import unicodedata

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

# Les ordres de grandeur du référentiel V4, tableau A2.1 « Besoins en eau et profondeur racinaire indicatifs par
# culture » (p. 137). Clé = mot repère cherché dans le nom de la culture. Valeurs indicatives, très dépendantes du
# climat, du sol et de la conduite (c'est écrit tel quel dans le référentiel).
BESOINS_A21 = {
    "maïs": ("6 à 8 mm/j", "250 à 450 mm", "0,8 à 1,2 m", "floraison et remplissage du grain"),
    "blé": ("4 à 6 mm/j", "100 à 200 mm", "0,9 à 1,2 m", "montaison et remplissage"),
    "orge": ("4 à 5 mm/j", "80 à 180 mm", "0,8 à 1,1 m", "montaison"),
    "sorgho": ("5 à 7 mm/j", "150 à 300 mm", "1,0 à 1,5 m", "floraison"),
    "soja": ("5 à 7 mm/j", "150 à 300 mm", "0,8 à 1,2 m", "floraison et remplissage des gousses"),
    "tournesol": ("5 à 6 mm/j", "100 à 250 mm", "1,2 à 1,8 m", "floraison"),
    "betterave": ("5 à 6 mm/j", "150 à 300 mm", "0,8 à 1,2 m", "croissance estivale de la racine"),
    "pomme de terre": ("5 à 7 mm/j", "250 à 400 mm", "0,5 à 0,7 m", "tubérisation"),
    "luzerne": ("6 à 7 mm/j", "300 à 500 mm", "1,2 à 1,8 m", "repousses"),
    "prairie": ("4 à 6 mm/j", "200 à 400 mm", "0,5 à 0,8 m", "repousses estivales"),
    "tomate": ("5 à 7 mm/j", "300 à 500 mm", "0,7 à 1,0 m", "nouaison et grossissement"),
    "oignon": ("4 à 6 mm/j", "200 à 350 mm", "0,3 à 0,5 m", "bulbaison"),
    "salade": ("3 à 5 mm/j", "100 à 200 mm", "0,2 à 0,3 m", "tout le cycle (fréquence élevée)"),
    "melon": ("5 à 6 mm/j", "200 à 350 mm", "0,6 à 0,9 m", "nouaison et grossissement"),
    "fraise": ("3 à 5 mm/j", "250 à 400 mm", "0,2 à 0,4 m", "floraison et récolte"),
    "vigne": ("2 à 4 mm/j", "80 à 200 mm", "1,0 à 2,0 m", "véraison (stress maîtrisé)"),
    "pommier": ("4 à 6 mm/j", "200 à 400 mm", "0,8 à 1,5 m", "grossissement des fruits"),
    "pêcher": ("5 à 6 mm/j", "250 à 450 mm", "0,8 à 1,5 m", "durcissement du noyau et grossissement"),
    "olivier": ("3 à 5 mm/j", "100 à 250 mm", "0,8 à 1,5 m", "durcissement du noyau"),
    "noyer": ("5 à 6 mm/j", "250 à 400 mm", "1,5 à 2,5 m", "remplissage"),
}

THEMES = [
    ("hivernage", "Fin de saison : on protège l'installation"),
    ("remise_route", "Remise en route de printemps"),
    ("pleine_saison", "Pleine chaleur : les bons réflexes"),
    ("contrat", "Le contrat d'entretien"),
    ("filtration", "La filtration, le cœur qui protège tout"),
    ("aides", "Les aides du moment"),
]


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _besoins(culture):
    """Les ordres de grandeur A2.1 pour cette culture (par mot repère du nom), ou None."""
    nom = _sans_accents(culture.name)
    for cle, valeurs in BESOINS_A21.items():
        if _sans_accents(cle) in nom:
            return valeurs
    return None


class Newsletter(models.TransientModel):
    _name = "cultiveau.newsletter"
    _description = "Créer une newsletter de l'adhérent"

    genre = fields.Selection([
        ("famille", "Par famille et par moment (recommandé)"),
        ("culture", "Pour une culture précise"),
        ("saison", "De saison (hivernage, remise en route, contrat...)"),
        ("vierge", "La mienne (je colle mon visuel Canva ou mon texte)"),
    ], string="Quelle newsletter", required=True, default="famille")
    categorie = fields.Selection(selection=lambda self: self.env["cultiveau.culture"]._fields["categorie"].selection,
                                 string="Famille de cultures", default="grandes_cultures")
    culture_id = fields.Many2one("cultiveau.culture", string="Culture")
    theme = fields.Selection(THEMES, string="Thème de saison", default="hivernage")
    titre = fields.Char("Titre", help="Le sujet de l'e-mail et le titre affiché. Prérempli, à ajuster librement.")
    cibler = fields.Boolean("Cibler les agriculteurs concernés", default=True,
                            help="La newsletter ne part qu'aux agriculteurs qui ont cette culture ou cette famille (frise culturale). "
                                 "Décochez pour l'adresser à tous vos clients.")

    @api.onchange("genre", "categorie", "culture_id", "theme")
    def _onchange_titre(self):
        self.titre = self._titre_defaut()

    def _titre_defaut(self):
        if self.genre == "culture" and self.culture_id:
            return f"Vos besoins en eau : {self.culture_id.name}"
        if self.genre == "famille" and self.categorie:
            fam = dict(self.env["cultiveau.culture"]._fields["categorie"].selection).get(self.categorie, "")
            return f"Besoins en eau : {fam.lower()}, le point de la saison"
        if self.genre == "saison" and self.theme:
            return dict(THEMES).get(self.theme, "Votre newsletter")
        return "Ma newsletter"

    # ------------------------------------------------------------------ la marque et le style (robuste pour les boîtes mail)
    @staticmethod
    def _rgb(c):
        c = (c or "#2a7f8f").lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        try:
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        except (ValueError, IndexError):
            return (42, 127, 143)

    def _melange(self, c, vers, t):
        r, g, b = self._rgb(c)
        vr, vg, vb = vers
        return "#%02x%02x%02x" % (round(r + (vr - r) * t), round(g + (vg - g) * t), round(b + (vb - b) * t))

    def _couleur(self, company=None):
        company = company or self.env.company
        return company.primary_color or company.email_primary_color or "#2a7f8f"

    def _clair(self, company, t=0.90):
        return self._melange(self._couleur(company), (255, 255, 255), t)

    def _fonce(self, company, t=0.28):
        return self._melange(self._couleur(company), (0, 0, 0), t)

    def _p(self, texte):
        return Markup("<p style='margin:0 0 9px;line-height:1.55;font-size:14px'>%s</p>") % texte

    def _source(self, texte):
        return Markup("<p style='margin:6px 0 0;font-size:12px;color:#8a949b;font-style:italic'>%s</p>") % texte

    def _hero(self, company, titre, sous_titre):
        couleur, fonce = self._couleur(company), self._fonce(company)
        logo = Markup("<img src='/web/image/res.company/%s/logo' alt='%s' style='max-height:46px;max-width:200px;margin-bottom:10px'/>") % (company.id, escape(company.name)) \
            if company.logo else Markup("<div style='font-size:20px;font-weight:700;color:#fff;margin-bottom:6px'>%s</div>") % escape(company.name)
        st = Markup("<div style='color:rgba(255,255,255,.88);font-size:15px;margin-top:5px'>%s</div>") % escape(sous_titre) if sous_titre else Markup("")
        return Markup(
            "<tr><td style='background:%s;padding:26px 28px 22px;text-align:center'>%s"
            "<div style='font-size:23px;font-weight:700;color:#fff;line-height:1.25'>%s</div>%s</td></tr>"
            "<tr><td style='height:5px;line-height:5px;font-size:0;background:%s'>&nbsp;</td></tr>") % (couleur, logo, escape(titre), st, fonce)

    def _stats(self, company, items):
        """Une rangée de cartes de chiffres clés : (icône, valeur, libellé)."""
        clair, couleur = self._clair(company), self._couleur(company)
        cells = Markup("").join(Markup(
            "<td width='%s%%' valign='top' style='padding:5px'>"
            "<div style='background:%s;border-radius:10px;padding:14px 8px;text-align:center'>"
            "<div style='font-size:22px;line-height:1'>%s</div>"
            "<div style='font-size:17px;font-weight:700;color:%s;margin:7px 0 2px'>%s</div>"
            "<div style='font-size:12px;color:#5b6a72'>%s</div></div></td>") % (round(100 / len(items)), clair, ic, couleur, escape(val), escape(lab))
            for ic, val, lab in items)
        return Markup("<table role='presentation' width='100%%' cellpadding='0' cellspacing='0' style='margin:4px 0 14px'><tr>%s</tr></table>") % cells

    def _callout(self, company, texte):
        couleur, clair = self._couleur(company), self._clair(company, 0.86)
        return Markup(
            "<div style='background:%s;border-left:4px solid %s;border-radius:6px;padding:12px 14px;margin:2px 0 16px;font-size:14px;line-height:1.5'>%s</div>") % (clair, couleur, texte)

    def _carte(self, company, icone, titre, corps):
        couleur = self._couleur(company)
        return Markup(
            "<div style='border:1px solid #e7ecee;border-radius:10px;padding:16px 18px;margin:0 0 16px'>"
            "<div style='font-size:16px;font-weight:700;color:%s;margin:0 0 8px'>%s %s</div>%s</div>") % (couleur, icone, escape(titre), corps)

    def _cta(self, company, texte, accroche=""):
        couleur = self._couleur(company)
        a = Markup("<div style='font-size:14px;color:#4a5560;margin:0 0 12px;line-height:1.5'>%s</div>") % escape(accroche) if accroche else Markup("")
        return Markup(
            "<div style='text-align:center;margin:22px 0 8px'>%s"
            "<a href='#' style='display:inline-block;background:%s;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:13px 28px;border-radius:26px'>%s</a></div>") % (a, couleur, escape(texte))

    def _pied(self, company):
        couleur = self._couleur(company)
        coords = " · ".join(filter(None, [company.phone or company.mobile or "", company.email or "", company.website or ""]))
        return Markup(
            "<div style='border-top:1px solid #eceff0;padding:16px 0 22px;text-align:center;font-size:12px;color:#8a949b'>"
            "<div style='font-weight:700;color:#1b2735;font-size:13px'>%s</div>"
            "<div style='margin-top:3px'>%s</div>"
            "<div style='margin-top:11px'><span style='display:inline-block;background:%s;color:#fff;border-radius:12px;padding:4px 13px;font-size:11px;font-weight:600'>Membre du réseau Cultiveau</span></div>"
            "<div style='margin-top:10px'><a href='/unsubscribe_from_list' style='color:#8a949b'>Se désabonner</a></div></div>") % (escape(company.name), escape(coords), couleur)

    def _corps(self, company, titre, sous_titre, contenu):
        """La newsletter complète : bandeau à la marque de l'adhérent, le contenu, le pied réseau."""
        return Markup(
            "<div style='background:#f4f6f7;padding:18px 10px'>"
            "<table role='presentation' align='center' width='620' cellpadding='0' cellspacing='0' "
            "style='max-width:620px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;"
            "border:1px solid #e7ecee;font-family:Helvetica,Arial,sans-serif;color:#2b2b2b'>"
            "%s<tr><td style='padding:22px 26px 4px'>%s</td></tr>"
            "<tr><td style='padding:0 26px'>%s</td></tr></table></div>") % (
            self._hero(company, titre, sous_titre), contenu, self._pied(company))

    # ------------------------------------------------------------------ les contenus
    def _contenu_culture(self, culture):
        company = self.env.company
        a21 = _besoins(culture)
        parts = []
        if a21:
            pointe, saison, racines, stade = a21
            parts.append(self._p("Voici, en un coup d'œil, ce que cette culture demande en eau et le moment à ne pas manquer."))
            parts.append(self._stats(company, [("💧", pointe, "besoin de pointe"), ("📅", saison, "sur la saison"), ("🌱", racines, "enracinement")]))
            parts.append(self._callout(company, Markup("<b>Le stade à ne pas rater :</b> %s. Un manque d'eau à ce moment coûte le plus cher.") % stade))
            parts.append(self._source("Ordres de grandeur, référentiel Cultiveau V4, tableau A2.1 p. 137. Très dépendants du climat, du sol et de la conduite."))
        else:
            kc = ("%.2f" % culture.kc_mi) if culture.kc_mi else "–"
            racines = ("%g m" % culture.racines_max) if culture.racines_max else "selon le sol"
            parts.append(self._p("Le besoin de pointe se calcule par ET0 x Kc. Voici les repères de cette culture."))
            parts.append(self._stats(company, [("💧", kc, "Kc de pointe"), ("🌱", racines, "enracinement")]))
            parts.append(self._source("Référentiel Cultiveau V4 § 6.2.1 p. 42. Votre installateur affine avec le climat du département et votre sol."))
        parts.append(self._carte(company, "💡", "Le bon réflexe : piloter, ne pas subir",
            self._p("On tient une comptabilité simple de la réserve du sol : on retire l'évapotranspiration, on ajoute la pluie utile et les arrosages, et on déclenche l'apport avant le seuil de stress.")
            + self._p("La dose par tour ne dépasse jamais la réserve facilement utilisable du sol, sinon l'eau file sous les racines : de l'eau et de l'engrais perdus.")
            + self._source("Référentiel Cultiveau V4 : bilan hydrique § 16.2.1 p. 109 ; dose maximale § 6.3.1 p. 44.")))
        parts.append(self._cta(company, "On fait le point ensemble",
                               "Un doute sur votre tour d'eau, votre pression ou votre filtration pour cette culture ? Répondez à cet e-mail, on regarde avant le pic."))
        return culture.name, Markup("").join(parts)

    def _contenu_famille(self, categorie):
        company = self.env.company
        Culture = self.env["cultiveau.culture"]
        fam = dict(Culture._fields["categorie"].selection).get(categorie, "")
        cultures = Culture.search([("categorie", "=", categorie), ("actif", "=", True)], limit=8)
        couleur = self._couleur(company)
        lignes = []
        for c in cultures:
            a21 = _besoins(c)
            if a21:
                lignes.append(Markup(
                    "<tr><td style='padding:9px 0;border-bottom:1px solid #f0f3f4'>"
                    "<b style='color:#1b2735;font-size:14px'>%s</b><br/>"
                    "<span style='font-size:13px;color:#5b6a72'>💧 pointe %s · ⚠️ stade %s</span></td></tr>") % (escape(c.name), a21[0], a21[3]))
        tableau = Markup("<table role='presentation' width='100%%' cellpadding='0' cellspacing='0' style='margin:2px 0 14px'>%s</table>") % Markup("").join(lignes) if lignes else Markup("")
        parts = [
            self._p("Voici, culture par culture, le moment où le besoin grimpe et le stade qu'il ne faut pas rater. C'est là que l'installation doit être prête et bien réglée."),
            tableau,
            self._source("Ordres de grandeur, référentiel Cultiveau V4, tableau A2.1 p. 137."),
            self._carte(company, "✅", "Avant le pic, trois gestes",
                self._p("<b>1.</b> Vérifier la filtration et la pression : un filtre colmaté fait chuter l'uniformité, donc l'eau, l'énergie et le rendement d'un coup.")
                + self._p("<b>2.</b> Repérer les zones sèches et les fuites : index du compteur, baisse de pression.")
                + self._p("<b>3.</b> Caler le tour d'eau sur la réserve du sol, pas sur l'habitude.")
                + self._source("Référentiel Cultiveau V4 : § 1.3.1 p. 8, § 16.2.1 p. 109.")),
            self._cta(company, "Prendre rendez-vous", "On peut faire un contrôle d'avant-saison et un point de réglage. Répondez pour fixer une date."),
        ]
        return f"{fam}, le point de la saison", Markup("").join(parts)

    def _contenu_saison(self, theme):
        company = self.env.company
        T = {
            "hivernage": ("Protégez votre installation avant le gel", [
                ("❄️", "Avant le gel, on protège tout", self._p("L'hivernage protège votre matériel du gel et le garde pour l'an prochain : on vidange les réseaux et les points bas, on hiverne la pompe et le compteur (vidange, dépose des éléments sensibles, stockage au sec), on rince et on conserve le goutte à goutte.") + self._source("Référentiel Cultiveau V4, § 18.5 « Opérations de fin de saison et hivernage », p. 121.")),
            ], "Réserver mon hivernage", "Les premières gelées ne préviennent pas. Répondez à cet e-mail pour caler votre créneau."),
            "remise_route": ("Prêt pour la première irrigation", [
                ("🌱", "Ce qu'on vérifie avant de démarrer", self._p("On remet la station de pompage en service (amorçage, contrôle du point de fonctionnement, sécurités), on contrôle les buses, les goutteurs et les pressions, on vérifie les sécurités et les automatismes (marche à sec, pressostats).") + self._source("Référentiel Cultiveau V4, § 18.3 « Opérations de début de saison », p. 120.")),
            ], "Réserver ma remise en route", "Au printemps, tout le monde démarre en même temps. Prenez de l'avance."),
            "pleine_saison": ("En pleine chaleur, les bons réflexes", [
                ("☀️", "Les gestes de la saison", self._p("Surveillez la pression et le colmatage des filtres, repérez vite une fuite ou une zone sèche, et gardez sous la main le numéro à appeler en cas de panne.")),
            ], "Noter votre numéro d'astreinte", "Une pression qui baisse, un secteur qui n'arrose plus : appelez dès les premiers signes."),
            "contrat": ("La tranquillité toute l'année", [
                ("🛡️", "Ce que couvre le contrat d'entretien", self._p("Hivernage, remise en route, contrôle d'avant-saison, priorité en cas de panne : le contrat prend en charge le suivi de votre installation toute l'année, à date fixe, sans que vous ayez à y penser.")),
                ("👍", "Ce que ça vous évite", self._p("Un gel oublié, un démarrage dans la précipitation, une pièce d'usure qui lâche en pleine saison.")),
            ], "Recevoir une proposition", "Répondez à cet e-mail pour une proposition adaptée à votre installation."),
            "filtration": ("La filtration, le cœur qui protège tout", [
                ("🔧", "Pourquoi c'est si important", self._p("Un filtre qui se colmate fait monter la perte de charge, chuter la pression et l'uniformité : vous perdez de l'eau, de l'énergie et du rendement en même temps. Un goutteur bouché ne se rattrape pas.") + self._source("Référentiel Cultiveau V4, § 1.3.1 « Trois enjeux solidaires », p. 8.")),
                ("👀", "Les signes qui doivent alerter", self._p("Nettoyages de plus en plus fréquents, pression qui baisse en bout de ligne, secteurs moins arrosés.")),
            ], "En parler avec nous", "Si vous voyez ces signes, parlons-en avant que ça coûte cher."),
            "aides": ("Les aides du moment", [
                ("💶", "Des financements existent", self._p("Des aides et des dossiers de financement existent pour moderniser l'irrigation et économiser l'eau et l'énergie. Les montants et les conditions changent souvent : on regarde ensemble ce qui s'applique à votre situation.")),
            ], "Faire le point sur mon projet", "On vous aide à monter le dossier."),
        }
        sous_titre, cartes, cta, accroche = T.get(theme, ("", [], "Nous contacter", ""))
        parts = [self._carte(company, ic, t, corps) for ic, t, corps in cartes]
        parts.append(self._cta(company, cta, accroche))
        return sous_titre, Markup("").join(parts)

    def _contenu_vierge(self):
        return "", Markup(
            "<div style='border:2px dashed #c9d1d7;border-radius:10px;padding:32px;text-align:center;color:#6c7883'>"
            "<div style='font-size:32px'>🎨</div>"
            "<p style='margin:8px 0 6px;font-weight:600;color:#1b2735;font-size:15px'>Votre contenu ici</p>"
            "<p style='margin:0;line-height:1.55;font-size:14px'>Écrivez votre texte, ou collez l'image de la newsletter que vous avez faite "
            "sur Canva (glissez-la, ou utilisez le bloc Image de l'éditeur à droite). Le bandeau à votre logo et le pied "
            "du réseau restent en place.</p></div>")

    # ------------------------------------------------------------------ créer le brouillon
    def _domaine(self):
        """Les destinataires : par culture, par famille, ou tous les clients de l'adhérent."""
        base = [("cultiveau_est_client", "=", True)] if "cultiveau_est_client" in self.env["res.partner"]._fields else []
        if not self.cibler:
            return base
        if self.genre == "culture" and self.culture_id:
            return base + [("cultiveau_culture_ids.culture_id", "=", self.culture_id.id)]
        if self.genre == "famille" and self.categorie:
            return base + [("cultiveau_culture_ids.culture_id.categorie", "=", self.categorie)]
        return base

    def action_creer(self):
        self.ensure_one()
        company = self.env.company
        if self.genre == "culture" and not self.culture_id:
            raise UserError("Choisissez la culture de la newsletter.")
        titre = self.titre or self._titre_defaut()
        if self.genre == "culture":
            sous_titre, contenu = self._contenu_culture(self.culture_id)
        elif self.genre == "famille":
            sous_titre, contenu = self._contenu_famille(self.categorie)
        elif self.genre == "saison":
            sous_titre, contenu = self._contenu_saison(self.theme)
        else:
            sous_titre, contenu = self._contenu_vierge()
        corps = self._corps(company, titre, sous_titre, contenu)
        # L'expéditeur du réseau : « Nom de l'adhérent <notification@cultiveau.fr> », réponses vers l'adhérent
        # (même règle que le reste de l'ERP ; l'envoi le reforce de toute façon via mail.mail).
        email_from, reply_to, _serveur = company.cultiveau_expediteur(self.env.user.partner_id)
        mailing = self.env["mailing.mailing"].create({
            "subject": titre,
            "body_arch": corps,
            "body_html": corps,
            "mailing_model_id": self.env["ir.model"]._get("res.partner").id,
            "mailing_domain": repr(self._domaine()),
            "mailing_type": "mail",
            "email_from": email_from,
            "reply_to_mode": "new" if reply_to else "update",
            "reply_to": reply_to or False,
        })
        return {
            "type": "ir.actions.act_window", "name": "Newsletter", "res_model": "mailing.mailing",
            "res_id": mailing.id, "view_mode": "form", "target": "current",
        }
