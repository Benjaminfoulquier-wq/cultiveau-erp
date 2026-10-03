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
  # Si un vrai dossier data/ traîne (créé par Docker ou un essai manuel), on l écarte : data doit pointer sur /srv/erp/data.
  if [ -d data ] && [ ! -L data ]; then mv data "data.ancien.$(date +%s)"; fi
  ln -sfn /srv/erp/data data
  # Odoo écrit ses fichiers (filestore, sessions) avec l utilisateur 101 du conteneur.
  chown -R 101:101 /srv/erp/data/odoo
  chmod +x deploy/sauvegarde.sh scripts/*.sh
  grep -q "erp/app/deploy/sauvegarde.sh" /etc/crontab || echo "45 1 * * * root /srv/erp/app/deploy/sauvegarde.sh" >> /etc/crontab
  docker compose pull -q
  # Les droits du dossier de fichiers d Odoo sont posés depuis l intérieur du conteneur : c est le seul point de vue
  # qui vaut quelle que soit la façon dont le serveur mappe les utilisateurs des conteneurs.
  docker compose run --rm --user root --entrypoint sh odoo -c 'mkdir -p /var/lib/odoo/filestore /var/lib/odoo/sessions && chown -R odoo:odoo /var/lib/odoo && ls -ld /var/lib/odoo /var/lib/odoo/filestore'
  docker compose up -d
  # Les modules Cultiveau sont mis à jour sur la base de production, seulement si elle existe et est installée.
  . /srv/erp/.env
  sleep 5
  etat=$(docker compose exec -T db psql -U odoo -d "$ODOO_DB" -tAc "select state from ir_module_module where name='"'"'base'"'"'" 2>/dev/null || true)
  if [ "$etat" = "installed" ]; then
    docker compose exec -T odoo odoo -d "$ODOO_DB" -u cultiveau_base,cultiveau_frise,cultiveau_persona,cultiveau_catalogue,cultiveau_installation,cultiveau_ventes,cultiveau_interventions,cultiveau_connecteurs --stop-after-init 2>&1 | tail -3
    docker compose restart odoo
  else
    echo "Base « $ODOO_DB » pas encore installée : lancer scripts/installer.sh (première installation)."
  fi
'
if [ "${1:-}" = "domaine" ]; then
  rsync -az -e "$SSH" deploy/proxy/sites/erp.caddy "$SERVEUR:/srv/proxy/sites/"
  $SSH "$SERVEUR" 'docker exec caddy caddy reload --config /etc/caddy/Caddyfile'
  echo "En ligne : https://$DOMAINE"
else
  echo "Conteneurs à jour. Site public : relancer avec « domaine » une fois le DNS en place."
fi
