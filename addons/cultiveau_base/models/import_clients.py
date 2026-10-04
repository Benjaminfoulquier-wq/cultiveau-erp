"""L'import des clients d'un adhérent, depuis n'importe quel fichier : Excel, CSV, export de l'assistant
téléphonique ou de l'ancien logiciel. Les colonnes sont reconnues par leur intitulé ; un client déjà connu
(même numéro, sinon même e-mail, sinon même nom et code postal) est mis à jour, jamais dupliqué. Tout est
rangé dans la société de l'adhérent : ses clients ne sont pas visibles des autres adhérents.
"""
from odoo import api, models

from .. import outils
from .res_partner import normaliser_telephone

COLONNES = {
    "civilite": ["civilite", "titre", "genre"],
    "prenom": ["prenom", "first name"],
    "nom": ["nom", "client", "contact", "nom complet", "interlocuteur", "prenom nom", "nom prenom", "nom du client", "name", "last name", "nom contact"],
    "exploitation": ["exploitation", "societe", "entreprise", "raison sociale", "earl", "gaec", "ferme", "domaine", "nom exploitation", "company", "organisation"],
    "telephone": ["portable", "mobile", "telephone", "tel", "gsm", "tel portable", "telephone portable", "telephone mobile", "phone", "numero", "tel 1", "telephone 1"],
    "telephone2": ["fixe", "telephone fixe", "tel fixe", "telephone 2", "autre telephone", "tel2", "tel 2", "bureau", "telephone bureau"],
    "email": ["email", "e mail", "mail", "courriel", "adresse mail", "adresse e mail"],
    "adresse": ["adresse", "rue", "adresse 1", "voie", "adresse postale", "street"],
    "adresse2": ["adresse 2", "complement", "complement d adresse", "lieu dit", "lieu-dit"],
    "code_postal": ["code postal", "cp", "codepostal", "zip", "code postale"],
    "commune": ["commune", "ville", "localite", "city"],
    "pays": ["pays", "country"],
    "siret": ["siret", "siren", "n siret", "numero siret"],
    "tva": ["tva", "tva intracom", "tva intracommunautaire", "n tva", "numero tva"],
    "type": ["type", "type de contact", "statut", "categorie", "qualite", "client prospect"],
    "surface": ["surface", "surface ha", "ha", "hectares", "sau"],
    "cultures": ["cultures", "culture", "productions", "production"],
    "materiel": ["materiel", "installation", "parc", "materiel installe", "equipements", "equipement"],
    "produits": ["produits", "produit", "achats", "articles", "gamme", "produits achetes"],
    "commercial": ["commercial", "suivi par", "charge d affaires", "vendeur", "technico commercial", "commercial attitre", "representant",
                   "responsable commercial", "technicien"],
    "notes": ["notes", "remarque", "remarques", "commentaire", "commentaires", "observations", "note"],
}
TYPES_MOTS = [("fournisseur", "fournisseur"), ("partenaire", "partenaire"), ("coop", "partenaire"), ("chambre", "partenaire"),
              ("adherent", "adherent"), ("prospect", "prospect"), ("client", "agriculteur"), ("agri", "agriculteur")]


class ResPartnerImport(models.AbstractModel):
    _name = "cultiveau.import.clients.moteur"
    _description = "Import des clients d'un adhérent (moteur)"

    @api.model
    def analyser(self, nom_fichier, contenu):
        """Lit le fichier ; renvoie {correspondance, en_tete, lignes, inconnus} ou lève ValueError."""
        lignes = outils.lire_tableau(nom_fichier, contenu)
        if not lignes:
            raise ValueError("le fichier est vide")
        corr, en_tete, donnees, inconnus = outils.reconnaitre(lignes, COLONNES)
        if "nom" not in corr and "exploitation" not in corr:
            raise ValueError("je ne trouve pas de colonne « Nom » (ou « Exploitation », « Société ») dans le fichier")
        return {"correspondance": corr, "en_tete": en_tete, "lignes": donnees, "inconnus": inconnus}

    @api.model
    def importer(self, nom_fichier, contenu, type_defaut="agriculteur", societe=None, mettre_a_jour=True):
        """Importe les contacts dans la société courante (ou donnée). Renvoie un bilan."""
        societe = societe or self.env.company
        lu = self.analyser(nom_fichier, contenu)
        corr = lu["correspondance"]
        # Pendant un import, pas de notification « vous avez été assigné » ni de trace de suivi : un fichier de 2 000 lignes
        # ne doit pas remplir la boîte mail de l'équipe.
        Partner = self.env["res.partner"].with_company(societe).with_context(mail_auto_subscribe_no_notify=True, mail_create_nolog=True,
                                                                               mail_notrack=True, tracking_disable=True)
        bilan = {"crees": 0, "maj": 0, "ignores": 0, "erreurs": [], "colonnes": sorted(corr), "inconnus": lu["inconnus"]}
        france = self.env.ref("base.fr", raise_if_not_found=False)
        pays_cache, users_cache, etiquettes = {}, {}, {}

        def val(ligne, champ):
            return outils.valeur(ligne, corr, champ)

        for n, ligne in enumerate(lu["lignes"], start=1):
            nom, prenom, exploitation = val(ligne, "nom"), val(ligne, "prenom"), val(ligne, "exploitation")
            if "(exemple)" in nom.lower() or nom.lower().startswith("ex :"):
                bilan["ignores"] += 1
                continue
            if not nom and not exploitation:
                bilan["ignores"] += 1
                continue
            tels = [normaliser_telephone(val(ligne, "telephone")), normaliser_telephone(val(ligne, "telephone2"))]
            tels = [t for t in tels if t]
            mobile = next((t for t in tels if t.startswith(("336", "337"))), "")
            fixe = next((t for t in tels if t != mobile), "")
            email = val(ligne, "email").lower()
            if email and "@" not in email:
                bilan["erreurs"].append(f"ligne {n} ({nom or exploitation}) : e-mail « {email} » ignoré")
                email = ""
            code_postal = val(ligne, "code_postal").replace(" ", "").zfill(5) if val(ligne, "code_postal") else ""
            nom_complet = " ".join(x for x in (prenom, nom) if x) or exploitation
            type_mot = outils.normaliser(val(ligne, "type"))
            type_c = next((t for mot, t in TYPES_MOTS if mot in type_mot), type_defaut) if type_mot else type_defaut
            prospect = type_c == "prospect"
            if prospect:
                type_c = "agriculteur"
            valeurs = {
                "name": nom_complet[:160], "is_company": not nom and bool(exploitation), "company_id": societe.id,
                "cultiveau_type": type_c, "customer_rank": 1 if type_c in ("agriculteur",) else 0,
                "supplier_rank": 1 if type_c == "fournisseur" else 0,
            }
            if nom and exploitation:
                valeurs["exploitation"] = exploitation[:160]
            if mobile:
                valeurs["mobile"] = "+" + mobile
            if fixe:
                valeurs["phone"] = "+" + fixe
            if email:
                valeurs["email"] = email
            if val(ligne, "adresse"):
                valeurs["street"] = val(ligne, "adresse")[:128]
            if val(ligne, "adresse2"):
                valeurs["street2"] = val(ligne, "adresse2")[:128]
            if code_postal:
                valeurs["zip"] = code_postal[:12]
            if val(ligne, "commune"):
                valeurs["city"] = val(ligne, "commune")[:64]
            pays = val(ligne, "pays")
            if pays:
                if pays not in pays_cache:
                    pays_cache[pays] = self.env["res.country"].search(["|", ("name", "=ilike", pays), ("code", "=ilike", pays)], limit=1)
                if pays_cache[pays]:
                    valeurs["country_id"] = pays_cache[pays].id
            elif france and (code_postal or val(ligne, "commune")):
                valeurs["country_id"] = france.id
            if val(ligne, "siret") and "company_registry" in Partner._fields:
                valeurs["company_registry"] = val(ligne, "siret").replace(" ", "")[:20]
            if val(ligne, "tva"):
                valeurs["vat"] = val(ligne, "tva").replace(" ", "")[:32]
            civ = outils.normaliser(val(ligne, "civilite"))
            if civ and "title" in Partner._fields:
                xmlid = "base.res_partner_title_madam" if civ.startswith(("mme", "mad", "f")) else "base.res_partner_title_mister" if civ.startswith(("m", "mr")) else None
                titre = self.env.ref(xmlid, raise_if_not_found=False) if xmlid else None
                if titre:
                    valeurs["title"] = titre.id
            commercial = val(ligne, "commercial")
            if commercial:
                if commercial not in users_cache:
                    users_cache[commercial] = self.env["res.users"].search([("name", "ilike", commercial.split()[0]), ("company_ids", "in", societe.id)], limit=1)
                if users_cache[commercial]:
                    valeurs["user_id"] = users_cache[commercial].id
            notes = [f"{libelle} : {val(ligne, champ)}" for champ, libelle in (("surface", "Surface (ha)"), ("cultures", "Cultures"), ("materiel", "Matériel installé"),
                                                                              ("produits", "Produits achetés / suivis"), ("notes", "Notes")) if val(ligne, champ)]
            existant = Partner.browse()
            if tels:
                existant = Partner.search([("numero_court", "in", tels), ("company_id", "in", [societe.id, False])], limit=1)
            if not existant and email:
                existant = Partner.search([("email", "=ilike", email), ("company_id", "in", [societe.id, False])], limit=1)
            if not existant and code_postal:
                existant = Partner.search([("name", "=ilike", nom_complet), ("zip", "=", code_postal), ("company_id", "in", [societe.id, False])], limit=1)
            valeurs = {k: v for k, v in valeurs.items() if k in Partner._fields}  # customer_rank… viennent de la comptabilité
            if existant:
                if not mettre_a_jour:
                    bilan["ignores"] += 1
                    continue
                maj = {k: v for k, v in valeurs.items() if v not in (False, 0, "") or k == "company_id"}
                maj.pop("is_company", None)
                if existant.company_id and existant.company_id != societe:
                    maj.pop("company_id")
                existant.write(maj)
                if notes:
                    existant.message_post(body="Import : " + " ; ".join(notes), subtype_xmlid="mail.mt_note")
                partenaire = existant
                bilan["maj"] += 1
            else:
                if notes:
                    valeurs["comment"] = "\n".join(notes)
                partenaire = Partner.create(valeurs)
                bilan["crees"] += 1
            if prospect:
                if "Prospect" not in etiquettes:
                    Cat = self.env["res.partner.category"]
                    etiquettes["Prospect"] = Cat.search([("name", "=ilike", "Prospect")], limit=1) or Cat.create({"name": "Prospect"})
                partenaire.category_id = [(4, etiquettes["Prospect"].id)]
        return bilan
