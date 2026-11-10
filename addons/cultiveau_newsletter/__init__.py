from . import models


def _post_init_acces_newsletters(env):
    """Donner tout de suite l'accès Email Marketing aux comptes adhérents déjà créés (l'implication de groupe ne
    repropage pas toujours d'elle-même aux utilisateurs existants)."""
    adherent = env.ref("cultiveau_base.group_adherent", raise_if_not_found=False)
    mm = env.ref("mass_mailing.group_mass_mailing_user", raise_if_not_found=False)
    if adherent and mm and adherent.users:
        mm.sudo().write({"users": [(4, u.id) for u in adherent.users]})
