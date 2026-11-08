"""L'aide par écran : à quoi sert l'écran, le pas à pas, les pièges, où lire ou regarder la suite.

08/11/2026 (Benjamin) : « je veux un petit ? sur chaque page, on clique et on a le tuto ». Le « ? » est en haut à droite de tous les
écrans ; il reconnaît la page par l'identifiant de son action (ou son numéro, résolu ici), sinon par le modèle affiché, sinon il
montre les gestes qui font gagner du temps. Les textes se modifient dans Réglages › Aides des écrans.
"""
from odoo import api, fields, models


class Aide(models.Model):
    _name = "cultiveau.aide"
    _description = "Tuto d'un écran"
    _order = "sequence, name"

    name = fields.Char("Écran", required=True)
    sequence = fields.Integer(default=10)
    action_xmlid = fields.Char("Action (identifiant externe)", help="Ex. cultiveau_vue3d.action_vue3d. Le tuto s'affiche sur cet écran.")
    res_model = fields.Char("Modèle", help="À défaut d'action : le tuto s'affiche sur tous les écrans de ce modèle (ex. sale.order).")
    resume = fields.Char("En une phrase", required=True)
    etapes = fields.Html("Pas à pas", sanitize=True, help="Une liste numérotée : ce qu'on fait, dans l'ordre, sur cet écran.")
    texte = fields.Html("Par où commencer", sanitize=True)
    pieges = fields.Html("À ne pas faire, pièges", sanitize=True)
    doc = fields.Char("Documentation", help="Un lien : page du dépôt, article…")
    video = fields.Char("Tuto vidéo", help="Le lien de la vidéo (cultiveau.fr, YouTube…) quand il existe.")
    active = fields.Boolean(default=True)

    @api.model
    def _xmlid_de_l_action(self, action_id, action_type=None):
        """Le numéro d'action que le navigateur connaît → son identifiant externe, s'il en a un."""
        if not action_id:
            return None
        modeles = [action_type] if action_type else ["ir.actions.act_window", "ir.actions.client", "ir.actions.server", "ir.actions.act_url"]
        d = self.env["ir.model.data"].sudo().search([("model", "in", modeles), ("res_id", "=", int(action_id))], limit=1)
        return f"{d.module}.{d.name}" if d else None

    @api.model
    def pour(self, action_xmlid=None, res_model=None, action_id=None, action_type=None):
        """Le tuto de l'écran courant : par action, sinon par modèle, sinon les gestes. Renvoie aussi « precis » : vrai quand le tuto est
        celui de cette page et pas le repli."""
        aide = self.env["cultiveau.aide"]
        xmlid = action_xmlid or self._xmlid_de_l_action(action_id, action_type)
        if xmlid:
            aide = self.search([("action_xmlid", "=", xmlid)], limit=1)
        if not aide and res_model:
            aide = self.search([("res_model", "=", res_model), ("action_xmlid", "=", False)], limit=1) or self.search([("res_model", "=", res_model)], limit=1)
        precis = bool(aide)
        if not aide:
            aide = self.search([("action_xmlid", "=", "cultiveau_roles.gestes")], limit=1)
        if not aide:
            return False
        return {"id": aide.id, "nom": aide.name, "resume": aide.resume, "etapes": aide.etapes or "", "texte": aide.texte or "", "pieges": aide.pieges or "",
                "doc": aide.doc or "", "video": aide.video or "", "precis": precis,
                "editable": self.env.user.has_group("cultiveau_base.group_equipe")}

    @api.model
    def _nettoyer_anciens(self):
        """Les textes d'origine qui pointaient sur un identifiant qui n'existe pas (la Map) laissent la place au tuto de la page."""
        self.sudo().search([("action_xmlid", "=", "cultiveau_vue3d.action_map")]).unlink()
        return True

    RELECTURES = {  # 08/11/2026 : les libellés vérifiés sur les vrais écrans
        "cultiveau_roles.tuto_devis": [("« Relire le référentiel » ajoute les notes techniques.", "« Relire avec le référentiel » montre ce que le référentiel dit du devis, « Écrire ces notes sur le devis » les ajoute en notes techniques.")],
        "cultiveau_roles.tuto_automatisations": [("« Et si… ? » teste une règle sur une copie avant de la lancer.", "Une règle se lit « Si… alors… » ; « Lancer maintenant » l'exécute tout de suite pour voir ce qu'elle fait.")],
        "cultiveau_roles.tuto_liaison_site": [("« Tout relire » efface les curseurs pour un passage complet.", "« Tout relire au prochain passage » efface les curseurs : le passage suivant reprend tout depuis le début.")],
        "cultiveau_roles.tuto_tableau_bord": [("Choisissez la période en haut (mois, trimestre, année).", "Les chiffres sont ceux du mois et de l'année en cours, recalculés à l'ouverture.")],
        "cultiveau_roles.tuto_commandes": [("« Créer la facture » pour l'acompte ou le solde", "« Créer une facture » pour l'acompte ou le solde")],
    }

    @api.model
    def _retirer_liens_github(self):
        """Les tutos ne renvoient jamais vers GitHub (08/11/2026) : le lien « documentation » qui pointait sur le dépôt est effacé ;
        la personne a le texte et la vidéo, rien d'autre."""
        self.sudo().search(["|", ("doc", "ilike", "github"), ("video", "ilike", "github")]).write({"doc": False})
        return True

    @api.model
    def _relecture_20261108(self):
        """Les corrections de la relecture, appliquées aux tutos déjà en base (ils sont en noupdate pour garder les modifications de l'adhérent)."""
        from markupsafe import escape as _esc  # noqa: PLC0415
        for xmlid, paires in self.RELECTURES.items():
            aide = self.env.ref(xmlid, raise_if_not_found=False)
            if not aide:
                continue
            for champ in ("etapes", "texte"):
                valeur = aide[champ] or ""
                nouveau = valeur
                for avant, apres in paires:
                    for a, b in ((avant, apres), (str(_esc(avant)), str(_esc(apres)))):
                        if a in nouveau:
                            nouveau = nouveau.replace(a, b)
                if nouveau != valeur:
                    aide.write({champ: nouveau})
        return True
