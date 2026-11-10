"""Le générateur de newsletters de l'adhérent.

La newsletter porte la marque de l'adhérent (logo, couleur) et, en pied seulement, « Membre du réseau Cultiveau ».
Le contenu des besoins en eau est ancré dans le référentiel V4 (tableau A2.1 p. 137, pilotage par bilan hydrique
§ 16.2.1 p. 109, dose maximale § 6.3.1 p. 44, ET0 x Kc § 6.2.1 p. 42) et complété par les coefficients culturaux déjà
tenus dans la base (cultiveau.culture). Tout est créé en brouillon : l'adhérent relit et envoie lui-même.
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

    # ------------------------------------------------------------------ la marque de l'adhérent
    def _couleur(self, company):
        return company.primary_color or company.email_primary_color or "#2a7f8f"

    def _pied(self, company):
        """Le pied « Membre du réseau Cultiveau » et les coordonnées de l'adhérent, plus le désabonnement."""
        coords = " · ".join(filter(None, [company.name, company.phone or company.mobile or "", company.email or "", company.website or ""]))
        return Markup(
            "<div style='margin-top:28px;border-top:1px solid #e3e7ea;padding-top:14px;font-size:12px;color:#6c7883;text-align:center'>"
            "<div style='font-weight:600;color:#1b2735'>%s</div>"
            "<div style='margin-top:4px'>Membre du réseau Cultiveau</div>"
            "<div style='margin-top:8px'><a href='/unsubscribe_from_list' style='color:#6c7883'>Se désabonner</a></div>"
            "</div>") % escape(coords)

    def _corps(self, company, titre, blocs):
        """La newsletter complète : bandeau au logo et à la couleur de l'adhérent, le contenu, le pied réseau."""
        couleur = self._couleur(company)
        logo = Markup("<img src='/web/image/res.company/%s/logo' alt='%s' style='max-height:54px;max-width:220px'/>") % (company.id, escape(company.name)) \
            if company.logo else Markup("<div style='font-size:22px;font-weight:700;color:#fff'>%s</div>") % escape(company.name)
        contenu = Markup("").join(blocs)
        return Markup(
            "<div style='max-width:620px;margin:0 auto;font-family:Helvetica,Arial,sans-serif;color:#2b2b2b'>"
            "<div style='background:%s;padding:18px 22px;border-radius:10px 10px 0 0;text-align:center'>%s</div>"
            "<div style='padding:22px;background:#ffffff;border:1px solid #e3e7ea;border-top:0;border-radius:0 0 10px 10px'>"
            "<h1 style='font-size:21px;color:#1b2735;margin:0 0 14px'>%s</h1>%s%s</div></div>"
        ) % (couleur, logo, escape(titre), contenu, self._pied(company))

    def _bloc(self, titre, corps):
        return Markup("<div style='margin:0 0 18px'><h2 style='font-size:16px;color:%s;margin:0 0 6px'>%s</h2>%s</div>") % (
            self._couleur(self.env.company), escape(titre), corps)

    def _p(self, texte):
        return Markup("<p style='margin:0 0 8px;line-height:1.5'>%s</p>") % texte

    def _source(self, texte):
        return Markup("<p style='margin:6px 0 0;font-size:12px;color:#6c7883'>%s</p>") % texte

    # ------------------------------------------------------------------ les contenus
    def _contenu_culture(self, culture):
        blocs = []
        a21 = _besoins(culture)
        if a21:
            pointe, saison, racines, stade = a21
            blocs.append(self._bloc("Ce que demande %s" % culture.name, (
                self._p(Markup("<b>Besoin de pointe :</b> %s. C'est le moment où le réseau doit suivre, l'été.") % pointe)
                + self._p(Markup("<b>Sur la saison :</b> %s, à confronter à votre volume autorisé.") % saison)
                + self._p(Markup("<b>Le stade à ne pas rater :</b> %s. Un manque d'eau à ce moment coûte le plus cher.") % stade)
                + self._p(Markup("<b>Profondeur racinaire :</b> %s, ce qui fixe la réserve du sol que l'on peut remplir par tour.") % racines)
                + self._source("Ordres de grandeur, référentiel Cultiveau V4, tableau A2.1 p. 137. Très dépendants du climat, du sol et de la conduite.")
            )))
        else:
            kc = ("%.2f" % culture.kc_mi) if culture.kc_mi else "non renseigné"
            racines = ("%g m" % culture.racines_max) if culture.racines_max else "selon le sol"
            blocs.append(self._bloc("Ce que demande %s" % culture.name, (
                self._p(Markup("<b>Besoin de pointe = ET0 x Kc.</b> Le coefficient de pointe de cette culture est de %s (référentiel § 6.2.1 p. 42).") % kc)
                + self._p(Markup("<b>Enracinement :</b> %s, ce qui fixe la réserve du sol disponible.") % racines)
                + self._source("Valeurs propres à votre secteur : votre installateur affine avec le climat du département et votre sol.")
            )))
        blocs.append(self._bloc("Le bon réflexe : piloter, ne pas subir", (
            self._p("On tient une comptabilité simple de la réserve du sol : on part d'un niveau connu, on retire l'évapotranspiration, on ajoute la pluie utile et les arrosages, et on déclenche l'apport avant d'arriver au seuil de stress.")
            + self._p(Markup("La dose par tour ne dépasse jamais la réserve facilement utilisable du sol, sinon l'eau passe sous les racines : de l'eau et de l'engrais perdus."))
            + self._source("Référentiel Cultiveau V4 : bilan hydrique § 16.2.1 p. 109 ; dose maximale § 6.3.1 p. 44.")
        )))
        blocs.append(self._bloc("On en parle ?", self._p(
            "Un doute sur votre tour d'eau, votre pression, votre filtration pour cette culture ? Répondez à cet e-mail ou appelez-nous : on fait le point ensemble avant le pic.")))
        return blocs

    def _contenu_famille(self, categorie):
        Culture = self.env["cultiveau.culture"]
        fam = dict(Culture._fields["categorie"].selection).get(categorie, "")
        cultures = Culture.search([("categorie", "=", categorie), ("actif", "=", True)], limit=8)
        lignes = []
        for c in cultures:
            a21 = _besoins(c)
            if a21:
                lignes.append(Markup("<li style='margin-bottom:5px'><b>%s</b> : pointe %s, stade sensible %s.</li>") % (escape(c.name), a21[0], a21[3]))
        detail = Markup("<ul style='margin:0 0 8px;padding-left:18px;line-height:1.5'>%s</ul>") % Markup("").join(lignes) if lignes else Markup("")
        blocs = [self._bloc("%s : la tension arrive" % fam, (
            self._p("Voici, culture par culture, le moment où le besoin grimpe et le stade qu'il ne faut pas rater. C'est là que l'installation doit être prête et bien réglée.")
            + detail
            + self._source("Ordres de grandeur, référentiel Cultiveau V4, tableau A2.1 p. 137.")
        ))]
        blocs.append(self._bloc("Avant le pic, trois gestes", (
            self._p("1. Vérifier la filtration et la pression (un filtre qui se colmate fait chuter l'uniformité, donc l'eau, l'énergie et le rendement d'un coup).")
            + self._p("2. Repérer les zones sèches et les fuites : index du compteur, baisse de pression.")
            + self._p("3. Caler le tour d'eau sur la réserve du sol, pas à l'habitude.")
            + self._source("Référentiel Cultiveau V4 : § 1.3.1 p. 8, § 16.2.1 p. 109.")
        )))
        blocs.append(self._bloc("On passe vous voir ?", self._p(
            "On peut faire un contrôle d'avant-saison et un point de réglage. Répondez à cet e-mail pour fixer une date.")))
        return blocs

    def _contenu_saison(self, theme):
        c = {
            "hivernage": [
                ("Avant le gel, on protège l'installation", self._p(
                    "L'hivernage protège votre matériel du gel et le garde pour l'an prochain. On vidange les réseaux et les points bas, on hiverne la pompe et le compteur (vidange, dépose des éléments sensibles, stockage au sec), on rince et on conserve le goutte à goutte.")
                 + self._source("Référentiel Cultiveau V4, § 18.5 « Opérations de fin de saison et hivernage », p. 121.")),
                ("Réservez votre créneau", self._p(
                    "Les premières gelées ne préviennent pas. Répondez à cet e-mail pour caler votre hivernage, ou pensez au contrat d'entretien qui le fait chaque année sans y penser.")),
            ],
            "remise_route": [
                ("Avant la première irrigation", self._p(
                    "On remet la station de pompage en service (amorçage, contrôle du point de fonctionnement, sécurités), on contrôle les buses, les goutteurs et les pressions, on vérifie les sécurités et les automatismes (marche à sec, pressostats).")
                 + self._source("Référentiel Cultiveau V4, § 18.3 « Opérations de début de saison », p. 120.")),
                ("Prenez de l'avance", self._p(
                    "Au printemps, tout le monde démarre en même temps. Réservez votre remise en route maintenant pour être prêt le jour où il faudra arroser.")),
            ],
            "pleine_saison": [
                ("En pleine chaleur, les bons réflexes", self._p(
                    "Surveillez la pression et le colmatage des filtres, repérez vite une fuite ou une zone sèche, et gardez sous la main le numéro à appeler en cas de panne.")),
                ("Une panne en pleine saison ?", self._p(
                    "Appelez-nous dès les premiers signes : une pression qui baisse, un secteur qui n'arrose plus. Mieux vaut un coup de fil tôt qu'un arrêt au mauvais moment.")),
            ],
            "contrat": [
                ("Le contrat d'entretien, la tranquillité", self._p(
                    "Hivernage, remise en route, contrôle d'avant-saison, priorité en cas de panne : le contrat d'entretien prend en charge le suivi de votre installation toute l'année, à date fixe, sans que vous ayez à y penser.")),
                ("Ce que ça vous évite", self._p(
                    "Un gel oublié, un démarrage dans la précipitation, une pièce d'usure qui lâche en pleine saison. Répondez à cet e-mail pour recevoir une proposition adaptée à votre installation.")),
            ],
            "filtration": [
                ("La filtration, le cœur qui protège tout", self._p(
                    "Un filtre qui se colmate fait monter la perte de charge, chuter la pression et l'uniformité : vous perdez de l'eau, de l'énergie et du rendement en même temps. Un goutteur bouché ne se rattrape pas.")
                 + self._source("Référentiel Cultiveau V4, § 1.3.1 « Trois enjeux solidaires », p. 8.")),
                ("Les signes qui doivent alerter", self._p(
                    "Nettoyages de plus en plus fréquents, pression qui baisse en bout de ligne, secteurs moins arrosés. Si vous les voyez, parlons-en avant que ça coûte cher.")),
            ],
            "aides": [
                ("Les aides du moment", self._p(
                    "Des aides et des dossiers de financement existent pour moderniser l'irrigation, économiser l'eau et l'énergie. Les montants et les conditions changent souvent : on regarde ensemble ce qui s'applique à votre situation.")),
                ("On monte le dossier avec vous", self._p(
                    "Répondez à cet e-mail : on fait le point sur votre projet et sur les aides mobilisables, et on vous aide à constituer le dossier.")),
            ],
        }.get(theme, [])
        return [self._bloc(t, corps) for t, corps in c]

    def _contenu_vierge(self):
        return [Markup(
            "<div style='border:2px dashed #c9d1d7;border-radius:8px;padding:26px;text-align:center;color:#6c7883'>"
            "<p style='margin:0 0 6px;font-weight:600;color:#1b2735'>Votre contenu ici</p>"
            "<p style='margin:0;line-height:1.5'>Cliquez pour écrire votre texte, ou collez l'image de la newsletter que vous avez faite "
            "sur Canva (glissez-la, ou utilisez le bloc Image de l'éditeur). Le bandeau à votre logo et le pied du réseau restent en place.</p>"
            "</div>")]

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
            blocs = self._contenu_culture(self.culture_id)
        elif self.genre == "famille":
            blocs = self._contenu_famille(self.categorie)
        elif self.genre == "saison":
            blocs = self._contenu_saison(self.theme)
        else:
            blocs = self._contenu_vierge()
        corps = self._corps(company, titre, blocs)
        domaine = self._domaine()
        mailing = self.env["mailing.mailing"].create({
            "subject": titre,
            "body_arch": corps,
            "body_html": corps,
            "mailing_model_id": self.env["ir.model"]._get("res.partner").id,
            "mailing_domain": repr(domaine),
            "mailing_type": "mail",
            "reply_to_mode": "update",
        })
        return {
            "type": "ir.actions.act_window", "name": "Newsletter", "res_model": "mailing.mailing",
            "res_id": mailing.id, "view_mode": "form", "target": "current",
        }
