"""Les textes enregistrés en base par les modules de l'éditeur (aide des écrans vides, modèles de courriels et de SMS, noms de menus,
actions serveur) sont réécrits à chaque mise à jour : le nom de l'éditeur devient Cultiveau, son site cultiveau.fr."""
import json
import logging

from odoo import api, models

from .traductions import sans_editeur_phrase

_logger = logging.getLogger(__name__)

# (table, colonnes) ; les colonnes traduites sont des jsonb (une valeur par langue), les autres du texte.
CIBLES = [
    ("ir_act_window", ("help",)),
    ("ir_act_server", ("name",)),
    ("ir_ui_menu", ("name",)),
    ("mail_template", ("subject", "body_html", "name")),
    ("sms_template", ("body", "name")),
    ("mail_message_subtype", ("name", "description")),
    ("mail_activity_type", ("name", "summary")),
    ("digest_digest", ("name",)),
    ("res_company", ("report_header", "report_footer")),
]


# Les écrans vides dont l'aide est une publicité de l'éditeur (vidéo, exemple à télécharger) : réécrits dans les mots du réseau.
AIDES = {
    "sale.action_quotations_with_onboarding": """<p class="o_view_nocontent_smiling_face">Faites votre premier devis</p>
<p>Depuis votre stock ou depuis le catalogue du réseau, avec les phases du chantier.<br/>Une fois signé, le devis déclenche tout : chantier, acompte, achats, mise en service.</p>""",
    "sale.action_quotations": """<p class="o_view_nocontent_smiling_face">Faites votre premier devis</p>
<p>Depuis votre stock ou depuis le catalogue du réseau, avec les phases du chantier.<br/>Une fois signé, le devis déclenche tout : chantier, acompte, achats, mise en service.</p>""",
    "sale.action_orders": """<p class="o_view_nocontent_smiling_face">Pas encore de commande</p>
<p>Un devis signé par le client devient une commande : le chantier, les achats et la facturation s'enchaînent d'eux-mêmes.</p>""",
}


class ActionsFenetre(models.Model):
    _inherit = "ir.actions.act_window"

    @api.model
    def cultiveau_sans_editeur(self):
        """Remplace le nom et le site de l'éditeur dans les textes stockés. Appelée par les données du module, donc à chaque mise à jour."""
        cr, total = self.env.cr, 0
        for table, colonnes in CIBLES:
            cr.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s AND column_name IN %s", (table, tuple(colonnes)))
            for colonne, type_sql in cr.fetchall():
                jsonb = type_sql == "jsonb"
                cr.execute(f"SELECT id, {colonne}::text FROM {table} WHERE {colonne}::text ~* 'odoo'")  # noqa: S608 — noms issus de CIBLES
                for id_, texte in cr.fetchall():
                    if jsonb:
                        valeur = json.loads(texte)
                        nouvelle = {langue: sans_editeur_phrase(v) for langue, v in valeur.items()} if isinstance(valeur, dict) else sans_editeur_phrase(valeur)
                        if nouvelle == valeur:
                            continue
                        cr.execute(f"UPDATE {table} SET {colonne} = %s::jsonb WHERE id = %s", (json.dumps(nouvelle), id_))  # noqa: S608
                    else:
                        nouvelle = sans_editeur_phrase(texte)
                        if nouvelle == texte:
                            continue
                        cr.execute(f"UPDATE {table} SET {colonne} = %s WHERE id = %s", (nouvelle, id_))  # noqa: S608
                    total += 1
        for xmlid, aide in AIDES.items():
            action = self.env.ref(xmlid, raise_if_not_found=False)
            if action and action.help != aide:
                action.help = aide
                total += 1
        self.env.registry.clear_cache()
        _logger.info("Cultiveau : %s texte(s) de l'éditeur réécrit(s) en base.", total)
        return total
