"""Lecture comportementale du persona.

Le questionnaire demande au client qui il est. Mais la plupart des clients ne répondront jamais à huit
questions. L'ERP, lui, voit déjà comment ils se comportent : quand ils appellent, pour quoi, s'ils
reprennent les mêmes produits ou cherchent le meilleur, s'ils acceptent ce qu'on leur propose, s'ils ont
des projets. Ce module lit ces signaux et en déduit un persona *observé*, avec une confiance (plus il y a
de preuves, plus elle monte) et la liste des éléments qui l'ont fait pencher. L'Agent s'en sert quand il
n'y a pas de questionnaire ; quand il y en a un, c'est le déclaré qui gagne, et l'écart est signalé.

Garde-fous (mémoire Benjamin) :
- Les signaux sont des indices, jamais une vérité : le persona observé est corrigeable et non figé.
- Le profilage reste interne à l'adhérent : on ne lit que les enregistrements du client lui-même
  (ses appels, ses devis, ses opportunités chez cet adhérent). Rien ne sort, rien ne se recoupe ailleurs.
- Chaque axe PRISM mesurable correspond à un signal nommé, et chaque conclusion s'explique en français.
"""
from odoo import api, fields, models

from .questionnaire import ORDRE

# Seuils : volontairement prudents. En dessous, on ne conclut pas sur l'axe.
MINI_APPELS = 2          # il faut au moins deux appels pour lire une habitude
MINI_LIGNES = 4          # au moins quatre lignes de commande pour juger de la répétition
MINI_DEVIS = 3           # au moins trois devis pour juger du taux d'acceptation
SEUIL_GAMME = 200.0      # €/ligne au-delà duquel on parle de matériel de gamme élevée


class ResPartnerComportement(models.Model):
    _inherit = "res.partner"

    cultiveau_persona_observe_id = fields.Many2one(
        "cultiveau.persona", "Persona observé", readonly=True,
        help="Déduit du comportement réel du client (appels, devis, commandes, projets). Indice, pas vérité.")
    cultiveau_persona_confiance = fields.Integer(
        "Confiance", readonly=True, help="0 à 100 : plus il y a de signaux concordants, plus c'est fiable.")
    cultiveau_persona_observe_le = fields.Datetime("Observé le", readonly=True)
    cultiveau_persona_elements = fields.Text(
        "Ce qui l'a fait pencher", readonly=True, help="Les signaux lus, en clair, un par ligne.")
    cultiveau_persona_ecart = fields.Boolean(
        "Écart déclaré / observé", compute="_compute_persona_ecart", store=True,
        help="Vrai quand le client s'est décrit autrement qu'il ne se comporte.")

    # Le persona retenu : le déclaré gagne, sinon l'observé. Surcharge volontaire de res_partner.py.
    @api.depends("cultiveau_persona_evaluation_ids.persona_id", "cultiveau_persona_evaluation_ids.date",
                 "cultiveau_persona_observe_id")
    def _compute_persona(self):
        for p in self:
            derniere = p.cultiveau_persona_evaluation_ids.sorted(lambda e: (e.date, e.id), reverse=True)[:1]
            p.cultiveau_persona_id = derniere.persona_id or p.cultiveau_persona_observe_id
            p.cultiveau_persona_date = derniere.date or p.cultiveau_persona_observe_le

    @api.depends("cultiveau_persona_evaluation_ids.persona_id", "cultiveau_persona_observe_id")
    def _compute_persona_ecart(self):
        for p in self:
            derniere = p.cultiveau_persona_evaluation_ids.sorted(lambda e: (e.date, e.id), reverse=True)[:1]
            p.cultiveau_persona_ecart = bool(
                derniere.persona_id and p.cultiveau_persona_observe_id
                and derniere.persona_id != p.cultiveau_persona_observe_id)

    # ---- la lecture elle-même -------------------------------------------------
    def cultiveau_comportement_signaux(self):
        """Lit les signaux du client et renvoie (code_persona|None, confiance 0-100, [éléments]).

        Ne conclut que sur ce qu'elle voit. Chaque signal ajoute des points aux personas qu'il désigne,
        et une phrase explicable. La confiance monte avec le nombre de preuves, pas avec le score.
        """
        self.ensure_one()
        scores = dict.fromkeys(ORDRE, 0)
        elements = []
        preuves = 0

        # 1. Appels : pourquoi il appelle. Beaucoup de dépannage/conseil → il attend d'être accompagné
        #    (tortue, abeille). Actif mais n'appelle jamais → il se débrouille seul (chat, jaguar).
        nb_appels = 0
        if "cultiveau.appel" in self.env:
            appels = self.env["cultiveau.appel"].sudo().search(
                [("partner_id", "child_of", self.id), ("sens", "=", "entrant")])
            nb_appels = len(appels)
            preuves += min(nb_appels, 6)
            if nb_appels >= MINI_APPELS:
                aide = appels.filtered(
                    lambda a: (a.urgence in ("immediate", "journee"))
                    or any(m in ((a.categorie or "") + " " + (a.sujet or "")).lower()
                           for m in ("panne", "dépann", "depann", "fuite", "problème", "probleme", "conseil", "aide")))
                part = len(aide) / nb_appels
                if part >= 0.5 or len(aide) >= 3:
                    scores["tortue"] += 2
                    scores["abeille"] += 1
                    elements.append(
                        f"Rappelle souvent pour être dépanné ou conseillé ({len(aide)} appel·s sur {nb_appels}) : "
                        "il attend qu'on l'accompagne.")

        # 2. Commandes : reprend-il les mêmes références (chat) ou varie-t-il pour le meilleur (jaguar) ?
        #    Et quelle part de matériel de gamme élevée (lion, jaguar) ?
        if "sale.order" in self.env:
            commandes = self.env["sale.order"].sudo().search(
                [("partner_id", "child_of", self.id), ("state", "in", ("sale", "done"))])
            lignes = commandes.mapped("order_line").filtered(lambda l: l.product_id and not l.display_type)
            total = len(lignes)
            if total >= MINI_LIGNES:
                preuves += min(total // 2, 6)
                uniques = len(set(lignes.mapped("product_id").ids))
                part_unique = uniques / total
                if part_unique <= 0.6:
                    scores["chat"] += 2
                    scores["tortue"] += 1
                    elements.append(
                        "Reprend surtout les mêmes références : il va vers ce qui a déjà fait ses preuves.")
                elif part_unique >= 0.85:
                    scores["jaguar"] += 2
                    scores["lion"] += 1
                    elements.append(
                        "Change souvent de références : il cherche le meilleur produit à chaque fois.")
                chers = len(lignes.filtered(lambda l: l.price_unit >= SEUIL_GAMME))
                if total and chers / total >= 0.3:
                    scores["lion"] += 1
                    scores["jaguar"] += 1
                    elements.append("Achète du matériel de gamme élevée : sensible à la performance et au neuf.")

            # 3. Devis : accepte-t-il ce qu'on lui propose (tortue, abeille) ou renégocie-t-il tout ?
            devis = self.env["sale.order"].sudo().search([("partner_id", "child_of", self.id)])
            proposes = devis.filtered(lambda o: o.state in ("sent", "sale", "done"))
            if len(proposes) >= MINI_DEVIS:
                preuves += 2
                acceptes = len(devis.filtered(lambda o: o.state in ("sale", "done")))
                taux = acceptes / len(proposes)
                if taux >= 0.7:
                    scores["tortue"] += 2
                    scores["abeille"] += 1
                    elements.append(
                        f"Accepte le plus souvent ce qu'on lui propose ({acceptes} sur {len(proposes)}) : "
                        "il suit le conseil.")
                elif taux <= 0.3:
                    scores["jaguar"] += 1
                    elements.append("Laisse filer beaucoup de devis : il compare et ne signe pas sur parole.")

        # 4. Présence numérique : e-mail et site → plutôt autonome et connecté (jaguar).
        if self.email and self.website:
            preuves += 1
            scores["jaguar"] += 1
            elements.append("Présent en ligne (e-mail et site) : plutôt autonome et à l'aise avec le numérique.")

        # 5. Projets ouverts : des opportunités en cours → tourné vers l'avenir (jaguar, lion).
        if "crm.lead" in self.env:
            opps = self.env["crm.lead"].sudo().search(
                [("partner_id", "child_of", self.id), ("type", "=", "opportunity"), ("active", "=", True)])
            if opps:
                preuves += min(len(opps), 3)
                scores["jaguar"] += 1
                scores["lion"] += 1
                elements.append(f"A {len(opps)} projet·s en cours : il investit et regarde devant.")

        # 6. Actif mais silencieux : des commandes, aucun appel → il se débrouille seul (chat, jaguar).
        if "sale.order" in self.env and nb_appels == 0:
            actif = self.env["sale.order"].sudo().search_count(
                [("partner_id", "child_of", self.id), ("state", "in", ("sale", "done"))])
            if actif >= 3:
                scores["chat"] += 1
                scores["jaguar"] += 1
                elements.append("Commande régulièrement sans jamais appeler : il se débrouille seul.")

        confiance = min(100, preuves * 9)
        if not any(scores.values()):
            return None, confiance, elements
        code = max(ORDRE, key=lambda c: (scores[c], -ORDRE.index(c)))
        return code, confiance, elements

    def cultiveau_comportement_lire(self):
        """Lit les signaux et écrit le persona observé sur la fiche. Renvoie l'action pour rafraîchir."""
        personas = self.env["cultiveau.persona"]
        par_code = {p.code: p for p in personas.sudo().search([])}
        for p in self:
            code, confiance, elements = p.cultiveau_comportement_signaux()
            p.cultiveau_persona_observe_id = par_code.get(code) if code else False
            p.cultiveau_persona_confiance = confiance
            p.cultiveau_persona_observe_le = fields.Datetime.now() if code else False
            p.cultiveau_persona_elements = "\n".join(elements)
        return True

    def action_cultiveau_comportement_lire(self):
        self.cultiveau_comportement_lire()
        return True

    @api.model
    def cultiveau_comportement_cron(self, limite=400):
        """Relit le comportement des clients agriculteurs qui ont de l'historique. Nocturne, par lots."""
        clients = self.search([("cultiveau_est_client", "=", True)], limit=limite)
        clients.cultiveau_comportement_lire()
        return True
