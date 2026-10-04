"""Le réseau Cultiveau dans l'ERP, d'après un fichier JSON : le groupe (Cultiveau, la holding, Solution Magnus),
l'équipe, les adhérents et leurs équipes, les prospects du réseau, les fournisseurs référencés et leurs contacts.

Le fichier n'est pas dans le dépôt (il contient des coordonnées de personnes) : l'équipe Cultiveau le dépose
dans Cultiveau → Réglages → Importer le réseau. Relançable : tout est reconnu par nom (sociétés), e-mail
ou nom (personnes) et complété, jamais dupliqué.
"""
import json
import re
import unicodedata

from odoo import api, models

from .res_partner import normaliser_telephone


def _cle(texte):
    s = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _tel(numero):
    n = normaliser_telephone(numero)
    return ("+" + n) if n else False


class ReseauMoteur(models.AbstractModel):
    _name = "cultiveau.reseau.moteur"
    _description = "Import du réseau Cultiveau (moteur)"

    # ---------------------------------------------------------------- outils

    def _pays(self, code):
        return self.env["res.country"].search([("code", "=", (code or "FR").upper())], limit=1)

    def _coordonnees(self, d):
        vals = {}
        for cle, champ in (("street", "street"), ("street2", "street2"), ("zip", "zip"), ("city", "city"), ("website", "website")):
            if d.get(cle):
                vals[champ] = d[cle]
        if d.get("email"):
            vals["email"] = d["email"].lower()
        if d.get("phone"):
            vals["phone"] = _tel(d["phone"]) or d["phone"]
        if d.get("mobile"):
            vals["mobile"] = _tel(d["mobile"]) or d["mobile"]
        if d.get("vat"):
            vals["vat"] = d["vat"].replace(" ", "")
        if d.get("siret") and "company_registry" in self.env["res.partner"]._fields:
            vals["company_registry"] = d["siret"].replace(" ", "")
        if d.get("country") or d.get("zip") or d.get("city"):
            pays = self._pays(d.get("country"))
            if pays:
                vals["country_id"] = pays.id
        return vals

    def _societe_partenaire(self, d, cultiveau_type, bilan):
        """Le partenaire société (res.partner is_company) reconnu par son nom, créé ou complété."""
        Partner = self.env["res.partner"].sudo()
        nom = d["name"]
        candidats = [nom] + [c for c in d.get("cles", [])] + ([d["raison"]] if d.get("raison") else [])
        partenaire = Partner
        for c in candidats:
            partenaire = Partner.search([("is_company", "=", True), ("name", "=ilike", c)], limit=1)
            if partenaire:
                break
        if not partenaire:
            for c in d.get("cles", []):  # un fournisseur du catalogue s'appelle « NELSON », le fichier dit « Nelson Irrigation »
                partenaire = Partner.search([("is_company", "=", True), ("name", "=ilike", c + "%")], limit=1)
                if partenaire:
                    break
        vals = dict(self._coordonnees(d), is_company=True, cultiveau_type=cultiveau_type)
        notes = []
        if d.get("raison") and d["raison"] != nom:
            notes.append(f"Raison sociale : {d['raison']}")
        if d.get("rcs"):
            notes.append(f"RCS {d['rcs']}")
        if d.get("qualite"):
            notes.append(f"Qualité dans le réseau : {d['qualite']}")
        if d.get("secteur"):
            notes.append(f"Secteur : {d['secteur']}")
        if d.get("note"):
            notes.append(d["note"])
        if notes:
            vals["comment"] = "\n".join(notes)
        if partenaire:
            maj = {k: v for k, v in vals.items() if v and (not partenaire[k] or k in ("cultiveau_type", "comment"))}
            if maj:
                partenaire.write(maj)
            bilan["societes_maj"] += 1
        else:
            vals["name"] = nom
            partenaire = Partner.create(vals)
            bilan["societes_creees"] += 1
        return partenaire

    def _contacts(self, societe_partenaire, contacts, bilan, company=None):
        """Les personnes d'une société : reconnues par e-mail, sinon par nom ; complétées."""
        Partner = self.env["res.partner"].sudo()
        for c in contacts:
            nom = " ".join((c.get("name") or "").split())
            if not nom:
                continue
            email = (c.get("email") or "").lower()
            existant = Partner
            if email:
                existant = Partner.search([("email", "=ilike", email), ("is_company", "=", False)], limit=1)
            if not existant:
                existant = Partner.search([("name", "=ilike", nom), ("parent_id", "=", societe_partenaire.id)], limit=1)
            vals = {"name": nom, "parent_id": societe_partenaire.id, "type": "contact", "is_company": False,
                    "cultiveau_type": societe_partenaire.cultiveau_type}
            if c.get("fonction"):
                vals["function"] = c["fonction"][:128]
            if email:
                vals["email"] = email
            if c.get("mobile"):
                vals["mobile"] = _tel(c["mobile"]) or c["mobile"]
            if c.get("phone"):
                vals["phone"] = _tel(c["phone"]) or c["phone"]
            if company is not None:
                vals["company_id"] = company.id if company else False
            if existant:
                existant.write({k: v for k, v in vals.items() if k not in ("name", "parent_id") and (v and not existant[k])})
                bilan["contacts_maj"] += 1
            else:
                Partner.create(vals)
                bilan["contacts_crees"] += 1

    # ---------------------------------------------------------------- le groupe

    def _societe_odoo(self, d, bilan):
        """Une société Odoo (res.company) du groupe ou un adhérent, reconnue par son nom."""
        Company = self.env["res.company"].sudo()
        if d.get("principale"):
            company = Company.browse(1) if Company.browse(1).exists() else Company.search([], limit=1)
        else:
            company = Company.search([("name", "=ilike", d["name"])], limit=1)
            if not company and d.get("raison"):
                company = Company.search([("name", "=ilike", d["raison"])], limit=1)
        vals = {"cultiveau_adherent": bool(d.get("adherent", True))}
        if d.get("numero_dedie"):
            vals["cultiveau_numero_dedie"] = d["numero_dedie"]
        if company:
            if company.name != d["name"] and not d.get("principale"):
                pass
            company.write(vals)
            bilan["societes_odoo_maj"] += 1
        else:
            company = Company.create(dict(vals, name=d["name"]))
            bilan["societes_odoo_creees"] += 1
        partenaire = company.partner_id
        coord = self._coordonnees(d)
        coord["cultiveau_type"] = "adherent" if d.get("adherent", True) else "partenaire"
        notes = [x for x in (d.get("forme") and f"Forme : {d['forme']}" + (f", capital {d['capital']}" if d.get("capital") else ""),
                             d.get("rcs") and f"RCS {d['rcs']}", d.get("qualite") and f"Qualité dans le réseau : {d['qualite']}",
                             d.get("secteur") and f"Secteur : {d['secteur']}", d.get("slogan"), d.get("note")) if x]
        if notes:
            coord["comment"] = "\n".join(notes)
        partenaire.write({k: v for k, v in coord.items() if v and (not partenaire[k] or k in ("comment", "cultiveau_type"))})
        if d.get("principale") and d.get("name") and company.name != d["name"]:
            company.name = d["name"]
        return company

    def _utilisateur(self, p, company, bilan):
        """Un membre de l'équipe : son contact (sous la société), et son compte Équipe Cultiveau s'il est demandé."""
        Users = self.env["res.users"].sudo()
        Partner = self.env["res.partner"].sudo()
        email = p["email"].lower()
        user = Users.with_context(active_test=False).search([("login", "=ilike", email)], limit=1)
        if not user and p.get("utilisateur"):
            groupes = [self.env.ref("base.group_user").id, self.env.ref("cultiveau_base.group_adherent").id]
            if p["utilisateur"] == "equipe":
                groupes.append(self.env.ref("cultiveau_base.group_equipe").id)
            francais = self.env["res.lang"].sudo().search([("code", "=", "fr_FR"), ("active", "=", True)], limit=1)
            vals = {"name": p["name"], "login": email, "email": email, "lang": francais.code if francais else self.env.lang, "tz": "Europe/Paris",
                    "company_id": company.id, "company_ids": [(6, 0, self.env["res.company"].sudo().search([]).ids)], "groups_id": [(6, 0, groupes)]}
            if p.get("signature"):
                vals["signature"] = "<p>" + p["signature"] + "</p>"
            user = Users.create(vals)
            bilan["utilisateurs_crees"] += 1
        elif user:
            vals = {}
            if p["utilisateur"] == "equipe" and self.env.ref("cultiveau_base.group_equipe") not in user.groups_id:
                vals["groups_id"] = [(4, self.env.ref("cultiveau_base.group_equipe").id)]
            toutes = self.env["res.company"].sudo().search([])
            if p["utilisateur"] == "equipe" and set(toutes.ids) - set(user.company_ids.ids):
                vals["company_ids"] = [(6, 0, toutes.ids)]
            if not user.tz:
                vals["tz"] = "Europe/Paris"
            if vals:
                user.write(vals)
            bilan["utilisateurs_maj"] += 1
        partenaire = user.partner_id if user else Partner.search([("email", "=ilike", email)], limit=1)
        vals = {"name": p["name"], "email": email, "function": p.get("fonction") or False, "cultiveau_type": "adherent",
                "parent_id": company.partner_id.id, "type": "contact"}
        if p.get("mobile"):
            vals["mobile"] = _tel(p["mobile"]) or p["mobile"]
        if p.get("phone"):
            vals["phone"] = _tel(p["phone"]) or p["phone"]
        if partenaire:
            partenaire.write({k: v for k, v in vals.items() if v and (not partenaire[k] or k in ("function", "cultiveau_type", "parent_id"))})
        else:
            Partner.create(vals)
        if user and p.get("signature") and (not user.signature or "--" in str(user.signature)):  # la signature par défaut (« -- Nom »)
            user.signature = "<p>" + p["signature"] + "</p>"

    # ---------------------------------------------------------------- l'import

    @api.model
    def importer(self, donnees):
        """donnees : le JSON du réseau (dict ou texte). Renvoie un bilan."""
        if isinstance(donnees, (bytes, str)):
            donnees = json.loads(donnees)
        bilan = {k: 0 for k in ("societes_odoo_creees", "societes_odoo_maj", "societes_creees", "societes_maj", "contacts_crees", "contacts_maj",
                                "utilisateurs_crees", "utilisateurs_maj", "prospects", "reglages")}
        bilan["erreurs"] = []
        Param = self.env["ir.config_parameter"].sudo()
        for cle, valeur in (donnees.get("reglages") or {}).items():
            Param.set_param(cle, valeur)
            bilan["reglages"] += 1
        societes = {}
        for d in donnees.get("groupe") or []:
            societes[d.get("cle") or d["name"]] = self._societe_odoo(dict(d, adherent=d.get("adherent", False)), bilan)
        principale = next((c for k, c in societes.items() if k == "cultiveau"), None) or self.env["res.company"].sudo().browse(1)
        for d in donnees.get("adherents") or []:
            company = self._societe_odoo(dict(d, adherent=True), bilan)
            self._contacts(company.partner_id, d.get("contacts") or [], bilan, company=False)
        for p in donnees.get("equipe") or []:  # après les adhérents : l'équipe voit toutes les sociétés
            try:
                self._utilisateur(p, societes.get(p.get("societe"), principale), bilan)
            except Exception as e:  # noqa: BLE001 — un compte en double, un e-mail déjà pris
                bilan["erreurs"].append(f"{p.get('name')} : {str(e).splitlines()[0][:160]}")
        Lead = self.env["crm.lead"].sudo() if "crm.lead" in self.env else None
        for d in donnees.get("prospects") or []:
            partenaire = self._societe_partenaire(d, "adherent", bilan)
            self._contacts(partenaire, d.get("contacts") or [], bilan)
            etiquette = self.env["res.partner.category"].sudo().search([("name", "=ilike", "Prospect réseau")], limit=1) or \
                self.env["res.partner.category"].sudo().create({"name": "Prospect réseau"})
            partenaire.category_id = [(4, etiquette.id)]
            if Lead is not None and not Lead.with_context(active_test=False).search([("partner_id", "=", partenaire.id), ("company_id", "=", principale.id)], limit=1):
                Lead.create({"name": f"Adhésion — {partenaire.name}", "partner_id": partenaire.id, "type": "opportunity", "company_id": principale.id,
                             "description": "Entreprise d'irrigation approchée par le réseau (comités, journées Cultiveau)."})
                bilan["prospects"] += 1
        for d in donnees.get("fournisseurs") or []:
            partenaire = self._societe_partenaire(d, "fournisseur", bilan)
            if not partenaire.supplier_rank and "supplier_rank" in partenaire._fields:
                partenaire.supplier_rank = 1
            self._contacts(partenaire, d.get("contacts") or [], bilan)
        return bilan
