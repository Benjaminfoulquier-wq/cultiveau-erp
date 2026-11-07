/** @odoo-module **/
// Le « ? » de chaque écran : à quoi il sert, par où commencer, où lire la suite.
import { Component, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

class AideDialog extends Component {
    static template = "cultiveau_roles.AideDialog";
    static components = { Dialog };
    static props = { aide: Object, close: Function };
    setup() {
        this.action = useService("action");
        this.texte = markup(this.props.aide.texte || "");
    }
    modifier() {
        this.props.close();
        this.action.doAction({ type: "ir.actions.act_window", res_model: "cultiveau.aide", res_id: this.props.aide.id, views: [[false, "form"]], target: "new" });
    }
}

export class AideSystray extends Component {
    static template = "cultiveau_roles.AideSystray";
    static props = {};
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ occupe: false });
    }
    get courant() {
        const c = this.action.currentController;
        const a = c && c.action;
        return a ? { xmlid: a.xml_id || a.xmlId || null, modele: a.res_model || null, nom: a.display_name || a.name || "" } : { xmlid: null, modele: null, nom: "" };
    }
    async ouvrir() {
        if (this.state.occupe) {
            return;
        }
        this.state.occupe = true;
        try {
            const { xmlid, modele, nom } = this.courant;
            const aide = await this.orm.call("cultiveau.aide", "pour", [xmlid, modele]);
            if (!aide) {
                this.notification.add(nom ? `Pas encore d'aide pour « ${nom} ». Le menu Cultiveau regroupe tout ; Mathis (icône à côté) répond à vos questions.` : "Pas d'aide pour cet écran.", { type: "info" });
                return;
            }
            this.dialog.add(AideDialog, { aide });
        } finally {
            this.state.occupe = false;
        }
    }
}

registry.category("systray").add("cultiveau_roles.aide", { Component: AideSystray }, { sequence: 1 });
