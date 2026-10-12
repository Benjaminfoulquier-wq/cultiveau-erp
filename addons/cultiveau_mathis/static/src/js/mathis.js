/** @odoo-module **/
// Mathis dans l'ERP : un service (ouvrir, fermer), une icône en haut à droite, et le panneau de conversation sur tous les écrans.
import { Component, useState, useRef, onMounted, onWillStart, reactive, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const RESSOURCES = { clients: "res.partner", interventions: "project.task", chantiers: "cultiveau.chantier", installations: "cultiveau.installation", devis: "sale.order",
                     commandes: "sale.order", factures: "account.move", articles: "product.template", opportunites: "crm.lead" };
const echapper = (t) => (t || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Le texte de Mathis : les liens [[ressource:id|Libellé]] deviennent cliquables, **gras** et retours à la ligne respectés. */
function rendre(texte) {
    let h = echapper(texte);
    h = h.replace(/\[\[(\w+):(\d+)\|([^\]]+)\]\]/g, (m, r, id, lib) => `<a href="#" class="o_mathis_lien" data-modele="${RESSOURCES[r] || r}" data-id="${id}">${lib}</a>`);
    h = h.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    h = h.replace(/^\s*[-•]\s+(.*)$/gm, "<li>$1</li>").replace(/(<li>[\s\S]*?<\/li>)(\n(?!<li>)|$)/g, "<ul>$1</ul>$2");
    return markup(h.replace(/\n/g, "<br/>"));
}

export const mathisService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        const etat = reactive({ ouvert: false, question: "" });
        return {
            etat,
            ouvrir(question = "") { etat.question = question; etat.ouvert = true; },
            fermer() { etat.ouvert = false; },
            basculer() { etat.ouvert = !etat.ouvert; },
        };
    },
};
registry.category("services").add("mathis", mathisService);

export class MathisSystray extends Component {
    static template = "cultiveau_mathis.Systray";
    static props = {};
    setup() {
        this.mathis = useService("mathis");
        this.etat = useState(this.mathis.etat);
    }
}
registry.category("systray").add("cultiveau_mathis.systray", { Component: MathisSystray }, { sequence: 5 });

export class MathisPanneau extends Component {
    static template = "cultiveau_mathis.Panneau";
    static props = {};
    setup() {
        this.mathis = useService("mathis");
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.etat = useState(this.mathis.etat);
        this.state = useState({ conversation: null, messages: [], propositions: [], suggestions: [], prenom: "Mathis", pret: true, saisie: "", occupe: false, charge: false });
        this.fil = useRef("fil");
        this.champ = useRef("champ");
        onWillStart(() => this.charger());
    }
    async charger() {
        try {
            this.appliquer(await this.orm.call("cultiveau.mathis", "ouvrir", [null]));
            this.state.charge = true;
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }
    appliquer(r) {
        this.state.conversation = r.conversation_id;
        this.state.messages = r.messages.map((m) => ({ ...m, html: m.texte ? rendre(m.texte) : null }));
        this.state.propositions = r.propositions || [];
        if (r.suggestions) {
            this.state.suggestions = r.suggestions;
        }
        this.state.prenom = r.prenom;
        this.state.pret = r.pret;
        for (const m of r.messages) {
            if (m.action && m.action.type === "action" && !m._joue) {
                m._joue = true;
            }
        }
        this.defiler();
    }
    defiler() {
        setTimeout(() => { if (this.fil.el) { this.fil.el.scrollTop = this.fil.el.scrollHeight; } }, 50);
    }
    async envoyer(texte = null) {
        const q = (texte ?? this.state.saisie).trim();
        if (!q || this.state.occupe) {
            return;
        }
        this.state.saisie = "";
        if (this.champ.el) {
            this.champ.el.value = "";
        }
        this.state.messages = [...this.state.messages, { role: "user", texte: q, html: rendre(q) }];
        this.state.occupe = true;
        this.defiler();
        try {
            const r = await this.orm.call("cultiveau.mathis", "repondre", [this.state.conversation, q]);
            const avant = this.state.messages.length;
            this.appliquer(r);
            // une action client (un écran à ouvrir, un courriel à relire) jointe à la réponse
            const derniers = r.messages.slice(-4).filter((m) => m.action && m.action.type === "action");
            for (const m of derniers) {
                if (!this._actionsJouees) { this._actionsJouees = new Set(); }
                const cle = JSON.stringify(m.action.action).slice(0, 200) + avant;
                if (!this._actionsJouees.has(cle)) {
                    this._actionsJouees.add(cle);
                    this.action.doAction(m.action.action);
                }
            }
        } catch (e) {
            const texte = `Je ne peux pas répondre : ${e.data?.message || e.message}`;
            this.state.messages = [...this.state.messages, { role: "assistant", texte, html: rendre(texte) }];
            this.defiler();
        } finally {
            this.state.occupe = false;
            this.champ.el?.focus();
        }
    }
    async confirmer(p, oui) {
        this.state.occupe = true;
        try {
            const r = await this.orm.call("cultiveau.mathis", "confirmer", [this.state.conversation, p.id, oui]);
            this.appliquer(r);
            const dernier = r.messages[r.messages.length - 1];
            if (dernier && dernier.action && dernier.action.type === "action") {
                this.action.doAction(dernier.action.action);
            }
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        } finally {
            this.state.occupe = false;
        }
    }
    async nouvelle() {
        this.appliquer(await this.orm.call("cultiveau.mathis", "nouvelle", []));
    }
    onClicFil(ev) {
        const a = ev.target.closest("a.o_mathis_lien");
        if (a) {
            ev.preventDefault();
            this.action.doAction({ type: "ir.actions.act_window", res_model: a.dataset.modele, res_id: +a.dataset.id, views: [[false, "form"]], target: "current" });
        }
    }
    ouvrirLien(l) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: l.modele, res_id: l.id, views: [[false, "form"]], target: "current" });
    }
    onTouche(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.envoyer();
        }
    }
    get questionInitiale() {
        const q = this.etat.question;
        if (q) {
            this.etat.question = "";
            this.envoyer(q);
        }
        return "";
    }
}
registry.category("main_components").add("cultiveau_mathis.panneau", { Component: MathisPanneau });
