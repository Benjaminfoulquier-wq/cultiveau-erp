/** @odoo-module **/
// L'écran « Aujourd'hui » : une tuile par chose à traiter, du plus pressant au moins pressant.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class Aujourdhui extends Component {
    static template = "cultiveau_quotidien.Aujourdhui";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ charge: false, tuiles: [], bonjour: "", date: "", societe: "", total: 0, urgent: 0 });
        onWillStart(() => this.charger());
    }
    async charger() {
        const r = await this.orm.call("cultiveau.aujourdhui", "ecran", []);
        Object.assign(this.state, r, { charge: true });
    }
    toutVoir(t) {
        this.action.doAction(t.action);
    }
    ouvrir(l) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: l.modele, res_id: l.id, views: [[false, "form"]], target: "current" });
    }
    demanderMathis() {
        const mathis = this.env.services.mathis;
        if (mathis && mathis.ouvrir) {
            mathis.ouvrir("Qu'est-ce que j'ai à faire aujourd'hui, par quoi je commence ?");
        }
    }
    get resume() {
        if (!this.state.total) {
            return "Tout est à jour. Belle journée !";
        }
        return `${this.state.total} chose${this.state.total > 1 ? "s" : ""} à traiter` + (this.state.urgent ? `, dont ${this.state.urgent} urgente${this.state.urgent > 1 ? "s" : ""}.` : ".");
    }
}

registry.category("actions").add("cultiveau_quotidien.aujourdhui", Aujourdhui);
