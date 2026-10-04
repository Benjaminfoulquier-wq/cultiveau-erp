# La clé d'API de l'ERP (Cultiveau → Réglages), créée si elle n'existe pas. Shell Odoo ; imprime « CLE=… ».
import secrets

Param = env["ir.config_parameter"].sudo()
cle = Param.get_param("cultiveau.cle_api")
if not cle:
    cle = secrets.token_urlsafe(32)
    Param.set_param("cultiveau.cle_api", cle)
    env.cr.commit()
print("CLE=" + cle)
