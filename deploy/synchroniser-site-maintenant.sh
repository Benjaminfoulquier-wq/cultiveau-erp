#!/bin/sh
# Lance tout de suite la synchronisation cultiveau.fr → ERP (clients, interventions, chantiers, bons, articles) pour toutes les
# entreprises reliées, puis affiche le résultat par entreprise. Sans danger : c'est le passage horaire, lancé à la main.
set -e
SSH="ssh -i $HOME/.ssh/cultiveau_vps -o IdentitiesOnly=yes -o ConnectTimeout=15"
echo "Synchronisation en cours…"
$SSH root@82.25.116.36 'printf "%s\n" "env[\"cultiveau.site.connexion\"].search([]).action_synchroniser()" "env.cr.commit()" | docker exec -i erp /entrypoint.sh odoo shell -d cultiveau --no-http 2>/dev/null | tail -1
docker exec erp-db psql -U odoo -d cultiveau -tAc "select c.name || '"'"' : '"'"' || to_char(x.derniere_synchro, '"'"'HH24:MI'"'"') || '"'"' UTC '"'"' || case when x.en_erreur then '"'"'ERREUR '"'"' else '"'"'ok '"'"' end || coalesce(x.resultat,'"'"''"'"') from cultiveau_site_connexion x join res_company c on c.id=x.company_id order by x.id"
docker exec erp-db psql -U odoo -d cultiveau -tAc "select '"'"'chantiers : '"'"' || count(*) from cultiveau_chantier where cultiveau_site_ref is not null; select '"'"'articles : '"'"' || count(*) from product_template where cultiveau_site_ref is not null; select '"'"'interventions : '"'"' || count(*) from project_task where cultiveau_site_ref is not null"'
