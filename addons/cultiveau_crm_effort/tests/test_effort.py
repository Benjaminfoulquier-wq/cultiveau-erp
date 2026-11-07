from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestEffort(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Earl du Plateau", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.lead = cls.env["crm.lead"].create({"name": "Pivot 40 ha", "partner_id": cls.agri.id, "type": "opportunity", "stage_id": cls.env.ref("cultiveau_ventes.stage_demande").id})

    def _types(self, lead):
        return set(lead.activity_ids.mapped("activity_type_id"))

    def test_les_etapes_enchainent(self):
        r1, r2, relance, visite = (self.env.ref(f"cultiveau_crm_effort.{x}") for x in ("act_r1", "act_r2", "act_relance", "act_visite_chantier"))
        self.lead.stage_id = self.env.ref("cultiveau_ventes.stage_analyse")
        self.assertIn(r1, self._types(self.lead))
        self.lead.stage_id = self.env.ref("cultiveau_ventes.stage_etude")
        self.assertIn(r2, self._types(self.lead))
        self.lead.stage_id = self.env.ref("cultiveau_ventes.stage_devis")
        self.assertIn(relance, self._types(self.lead))
        self.lead.stage_id = self.env.ref("cultiveau_ventes.stage_devis")  # même étape : pas de doublon
        self.assertEqual(len(self.lead.activity_ids.filtered(lambda a: a.activity_type_id == relance)), 1)
        self.lead.stage_id = self.env.ref("cultiveau_ventes.stage_commande")
        self.assertNotIn(relance, self._types(self.lead))  # la relance tombe quand l'affaire avance
        self.lead.stage_id = self.env.ref("cultiveau_ventes.stage_mise_en_service")
        self.assertIn(visite, self._types(self.lead))

    def test_affaire_oubliee(self):
        self.lead.activity_ids.unlink()
        self.env.flush_all()
        vieux = fields.Datetime.now() - timedelta(days=20)
        self.env.cr.execute("UPDATE crm_lead SET write_date = %s, date_last_stage_update = %s, create_date = %s WHERE id = %s", (vieux, vieux, vieux, self.lead.id))
        self.env.cr.execute("UPDATE mail_message SET date = %s WHERE model = 'crm.lead' AND res_id = %s", (vieux, self.lead.id))
        self.env.invalidate_all()
        self.assertGreaterEqual(self.lead.cultiveau_jours_sans_action, 14, (self.lead.create_date, self.lead.date_last_stage_update, self.env["mail.message"].sudo().search([("model", "=", "crm.lead"), ("res_id", "=", self.lead.id)]).mapped("date")))
        n = self.env["crm.lead"]._cultiveau_cron_reprendre_contact()
        self.assertGreaterEqual(n, 1)
        self.assertIn(self.env.ref("cultiveau_crm_effort.act_reprendre"), self._types(self.lead))

    def test_effort_compte_les_activites_faites(self):
        act = self.lead.activity_schedule(activity_type_id=self.env.ref("cultiveau_crm_effort.act_appel_prospection").id, summary="Appel")
        act.action_feedback(feedback="Joint, rendez-vous pris")
        self.env.cr.flush()
        lignes = self.env["cultiveau.effort.commercial"].search([("lead_id", "=", self.lead.id)])
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes.activity_type_id, self.env.ref("cultiveau_crm_effort.act_appel_prospection"))
        self.assertEqual(lignes.user_id, self.env.user)
        self.assertEqual(self.lead.cultiveau_nb_activites_faites, 1)

    def test_donnees_et_groupes(self):
        self.assertTrue(self.env["crm.lost.reason"].search([("name", "ilike", "autorisation")]))
        self.assertEqual(self.env.ref("cultiveau_crm_effort.plan_entretien_annuel").number_of_months, 12)
        base = self.env.ref("base.group_user")
        self.assertIn(self.env.ref("crm.group_use_lead"), base.implied_ids)
        self.assertIn(self.env.ref("crm.group_use_recurring_revenues"), base.implied_ids)
