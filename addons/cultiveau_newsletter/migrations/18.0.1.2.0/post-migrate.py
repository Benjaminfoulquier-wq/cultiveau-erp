"""À la mise à jour : donner l'accès Email Marketing aux comptes adhérents déjà créés (le post_init_hook ne tourne
qu'à l'installation ; en production le module est déjà installé, donc c'est ici que la propagation se fait)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    adherent = env.ref("cultiveau_base.group_adherent", raise_if_not_found=False)
    mm = env.ref("mass_mailing.group_mass_mailing_user", raise_if_not_found=False)
    if adherent and mm and adherent.users:
        mm.sudo().write({"users": [(4, u.id) for u in adherent.users]})
