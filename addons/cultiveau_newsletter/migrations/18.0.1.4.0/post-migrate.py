"""Retirer les enregistrements de démonstration d'Odoo pour l'app Email Marketing (mailings en faux latin, faux taux,
listes et contacts de démo). Ils sont apparus quand l'installation de l'app a chargé sa démo. On ne vise que les
enregistrements qui portent un identifiant externe du module mass_mailing : les vraies newsletters et listes des
adhérents, créées dans l'application, n'en ont pas, donc elles ne sont jamais touchées."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for modele in ("mailing.mailing", "mailing.list", "mailing.contact"):
        if modele not in env:
            continue
        data = env["ir.model.data"].search([("model", "=", modele), ("module", "in", ("mass_mailing", "mass_mailing_sms"))])
        enregistrements = env[modele].browse(set(data.mapped("res_id"))).exists()
        for r in enregistrements:
            try:
                r.unlink()
            except Exception:  # noqa: BLE001 — un enregistrement récalcitrant ne doit pas bloquer la mise à jour
                pass
