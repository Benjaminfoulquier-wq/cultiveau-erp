#!/bin/sh
# Met en ligne la version du poste sur le serveur, depuis la racine du projet :
#   sh deploy/deployer.sh            # code + conteneurs (Odoo redémarre, les modules Cultiveau sont mis à jour)
#   sh deploy/deployer.sh domaine    # + le site Caddy (seulement quand le DNS pointe sur le serveur)
# Premier passage : crée /srv/erp, le .env (mots de passe), puis `sh scripts/installer.sh` depuis le serveur.
set -eu
SERVEUR=${SERVEUR:-root@82.25.116.36}
CLE=${CLE:-$HOME/.ssh/cultiveau_vps}
SSH="ssh -i $CLE -o IdentitiesOnly=yes"
DOMAINE=${DOMAINE:-erp.cultiveau.fr}

$SSH "$SERVEUR" "
  set -e
  mkdir -p /srv/erp/app /srv/erp/data/postgres /srv/erp/data/odoo /srv/sauvegardes/erp
  chown 101:101 /srv/erp/data/odoo
  if [ ! -f /srv/erp/.env ]; then
    umask 077
    {
      echo POSTGRES_PASSWORD=\$(openssl rand -hex 24)
      echo ODOO_ADMIN_PASSWD=\$(openssl rand -hex 16)
      echo ODOO_DB=cultiveau
      echo DOMAINE=$DOMAINE
    } > /srv/erp/.env
  fi
"
rsync -az --delete -e "$SSH" --exclude=.git --exclude=data --exclude=.env --exclude=__pycache__ ./ "$SERVEUR:/srv/erp/app/"
$SSH "$SERVEUR" '
  set -e
  cd /srv/erp/app
  ln -sfn /srv/erp/.env .env
  ln -sfn /srv/erp/data data
  chmod +x deploy/sauvegarde.sh scripts/*.sh
  grep -q "erp/app/deploy/sauvegarde.sh" /etc/crontab || echo "45 1 * * * root /srv/erp/app/deploy/sauvegarde.sh" >> /etc/crontab
  docker compose pull -q
  docker compose up -d
  # Les modules Cultiveau sont mis à jour sur la base de production (sans effet si rien n a changé).
  . /srv/erp/.env
  docker compose exec -T odoo odoo -d "$ODOO_DB" -u cultiveau_base,cultiveau_frise,cultiveau_persona,cultiveau_catalogue,cultiveau_installation,cultiveau_ventes,cultiveau_interventions,cultiveau_connecteurs --stop-after-init 2>&1 | tail -3 || echo "Base pas encore créée : lancer scripts/installer.sh"
  docker compose restart odoo
'
if [ "${1:-}" = "domaine" ]; then
  rsync -az -e "$SSH" deploy/proxy/sites/erp.caddy "$SERVEUR:/srv/proxy/sites/"
  $SSH "$SERVEUR" 'docker exec caddy caddy reload --config /etc/caddy/Caddyfile'
  echo "En ligne : https://$DOMAINE"
else
  echo "Conteneurs à jour. Site public : relancer avec « domaine » une fois le DNS en place."
fi
