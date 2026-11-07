from . import models


def preparer(env):
    """La pro forma pour tous ; le bloc « Projet » en tête des modèles de devis du réseau."""
    base = env.ref("base.group_user")
    pf = env.ref("sale.group_proforma_sales", raise_if_not_found=False)
    if pf and pf not in base.implied_ids:
        base.implied_ids |= pf
    env["sale.order.template"].sudo().cultiveau_ajouter_bloc_projet()
