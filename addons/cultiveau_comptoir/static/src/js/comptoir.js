/** @odoo-module **/
// Le comptoir : un seul écran. La douchette (ou le clavier) trouve l'article, le panier se remplit, on choisit le client
// (ou « client de passage »), puis on encaisse : commande, sortie de stock, facture et paiement sont faits derrière.
import { Component, onMounted, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class Comptoir extends Component {
    static template = "cultiveau_comptoir.Comptoir";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.scan = useRef("scan");
        this.state = useState({
            contexte: null, texte: "", candidats: [], cherche: false, panier: [], client: null, rechercheClient: "", clients: [], choixClient: false,
            note: "", occupe: false, vente: null,
        });
        onWillStart(async () => {
            this.state.contexte = await this.orm.call("cultiveau.comptoir", "contexte", []);
            this.state.client = { id: this.state.contexte.client_defaut, nom: "Client de passage", ville: "", telephone: "" };
        });
        onMounted(() => this.focus());
    }

    focus() {
        this.scan.el?.focus();
    }

    // ------------------------------------------------------------ chercher et ajouter

    async chercher() {
        const texte = this.state.texte.trim();
        if (!texte) {
            this.state.candidats = [];
            return;
        }
        this.state.cherche = true;
        const resultats = await this.orm.call("cultiveau.comptoir", "chercher", [texte, this.state.client?.id]);
        this.state.cherche = false;
        const exacts = resultats.filter((r) => r.exact);
        if (exacts.length === 1) {
            // la douchette a lu un code : l'article va droit dans le panier
            this.ajouter(exacts[0]);
            this.state.texte = "";
            this.state.candidats = [];
        } else {
            this.state.candidats = resultats;
        }
        this.focus();
    }

    onTouche(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.chercher();
        } else if (ev.key === "Escape") {
            this.state.texte = "";
            this.state.candidats = [];
        }
    }

    onSaisie() {
        // la frappe au clavier cherche au fil de l'eau (après trois caractères) ; la douchette finit par Entrée
        clearTimeout(this._minuteur);
        if (this.state.texte.trim().length >= 3) {
            this._minuteur = setTimeout(() => this.chercher(), 250);
        }
    }

    ajouter(article) {
        const ligne = this.state.panier.find((l) => l.product_id === article.id);
        if (ligne) {
            ligne.quantite += 1;
        } else {
            this.state.panier.push({ product_id: article.id, nom: article.nom, code: article.code, unite: article.unite, quantite: 1, prix_ht: article.prix_ht, taux: article.taux, stock: article.stock });
        }
        this.state.texte = "";
        this.state.candidats = [];
        this.focus();
    }

    quantite(ligne, delta) {
        ligne.quantite = Math.max(0, Math.round((ligne.quantite + delta) * 100) / 100);
        if (ligne.quantite === 0) {
            this.retirer(ligne);
        }
    }

    saisirQuantite(ligne, ev) {
        const v = parseFloat(String(ev.target.value).replace(",", "."));
        ligne.quantite = isNaN(v) || v < 0 ? 0 : v;
    }

    saisirPrix(ligne, ev) {
        const v = parseFloat(String(ev.target.value).replace(",", "."));
        if (!isNaN(v) && v >= 0) {
            ligne.prix_ht = v;
        }
    }

    retirer(ligne) {
        this.state.panier = this.state.panier.filter((l) => l !== ligne);
        this.focus();
    }

    get totaux() {
        let ht = 0, ttc = 0;
        for (const l of this.state.panier) {
            const lht = l.quantite * l.prix_ht;
            ht += lht;
            ttc += lht * (1 + (l.taux || 0) / 100);
        }
        return { ht, tva: ttc - ht, ttc, articles: this.state.panier.reduce((s, l) => s + l.quantite, 0) };
    }

    montant(v) {
        return (Math.round(v * 100) / 100).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // ------------------------------------------------------------ le client

    async chercherClient() {
        clearTimeout(this._minuteurClient);
        this._minuteurClient = setTimeout(async () => {
            this.state.clients = await this.orm.call("cultiveau.comptoir", "clients", [this.state.rechercheClient]);
        }, 200);
    }

    async ouvrirClients() {
        this.state.choixClient = true;
        this.state.rechercheClient = "";
        this.state.clients = await this.orm.call("cultiveau.comptoir", "clients", [""]);
    }

    choisirClient(c) {
        this.state.client = c;
        this.state.choixClient = false;
        this.focus();
    }

    clientDePassage() {
        this.state.client = { id: this.state.contexte.client_defaut, nom: "Client de passage", ville: "", telephone: "" };
        this.state.choixClient = false;
        this.focus();
    }

    nouveauClient() {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "res.partner", views: [[false, "form"]], target: "new",
                               context: { default_cultiveau_type: "agriculteur", default_is_company: false, default_name: this.state.rechercheClient } },
                             { onClose: () => this.ouvrirClients() });
    }

    // ------------------------------------------------------------ vendre

    async vendre(mode, journal_id) {
        if (!this.state.panier.length || this.state.occupe) {
            return;
        }
        this.state.occupe = true;
        try {
            const lignes = this.state.panier.map((l) => ({ product_id: l.product_id, quantite: l.quantite, prix_ht: l.prix_ht }));
            const vente = await this.orm.call("cultiveau.comptoir", "vendre", [this.state.client?.id, lignes, mode, journal_id || null, this.state.note]);
            this.state.vente = { ...vente, mode, client: this.state.client.nom, lignes: this.state.panier.length };
            this.state.panier = [];
            this.state.note = "";
            this.notification.add(vente.message, { type: "success" });
        } finally {
            this.state.occupe = false;
        }
    }

    async ticket() {
        if (this.state.vente?.facture_id) {
            this.action.doAction(await this.orm.call("cultiveau.comptoir", "ticket", [this.state.vente.facture_id]));
        }
    }

    ouvrirDocument() {
        const v = this.state.vente;
        if (v?.facture_id) {
            this.action.doAction({ type: "ir.actions.act_window", res_model: "account.move", res_id: v.facture_id, views: [[false, "form"]] });
        } else if (v?.commande_id) {
            this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order", res_id: v.commande_id, views: [[false, "form"]] });
        }
    }

    nouvelleVente() {
        this.state.vente = null;
        this.clientDePassage();
    }
}

registry.category("actions").add("cultiveau_comptoir.comptoir", Comptoir);
