#!/bin/sh
# Ferme (ou rouvre) l'accès à l'ERP d'une personne, comme le fait la case par membre d'Admin › Adhérents de cultiveau.fr.
#   sh deploy/fermer-acces-utilisateur.sh commercial@modernirrigation81.fr          # ferme
#   sh deploy/fermer-acces-utilisateur.sh commercial@modernirrigation81.fr ouvrir   # rouvre
set -e
LOGIN="$1"; ACTION="${2:-fermer}"
[ -n "$LOGIN" ] || { echo "usage : $0 <login> [fermer|ouvrir]"; exit 1; }
[ "$ACTION" = "ouvrir" ] && ACTIF=True || ACTIF=False
ssh -i $HOME/.ssh/cultiveau_vps -o IdentitiesOnly=yes -o ConnectTimeout=15 root@82.25.116.36 "printf '%s\n' \"u = env['res.users'].with_context(active_test=False).search([('login', '=ilike', '$LOGIN'), ('share', '=', False)], limit=1)\" \"assert u and u.login != 'admin', 'compte introuvable ou admin'\" \"u.write({'active': $ACTIF})\" \"env.cr.commit()\" \"print(u.login, u.company_id.name, 'actif' if u.active else 'désactivé')\" | docker exec -i erp /entrypoint.sh odoo shell -d cultiveau --no-http 2>/dev/null | tail -1"
