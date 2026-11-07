from . import models


def activer_virement(env):
    env["res.company"].sudo().search([]).cultiveau_activer_paiement_en_ligne()
