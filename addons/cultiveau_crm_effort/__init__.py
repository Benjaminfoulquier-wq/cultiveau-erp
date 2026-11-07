from . import models


def activer_groupes(env):
    """Pistes et revenus récurrents pour tout le monde : les deux cases de Réglages › CRM cochées d'office."""
    base = env.ref("base.group_user")
    for xmlid in ("crm.group_use_lead", "crm.group_use_recurring_revenues"):
        g = env.ref(xmlid, raise_if_not_found=False)
        if g and g not in base.implied_ids:
            base.implied_ids |= g
