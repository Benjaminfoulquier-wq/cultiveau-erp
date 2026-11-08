/** @odoo-module **/
// Le « ? » de chaque écran : le tuto de la page (pas à pas, par où commencer, pièges, doc, vidéo).
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
        this.etapes = markup(this.props.aide.etapes || "");
        this.texte = markup(this.props.aide.texte || "");
        this.pieges = markup(this.props.aide.pieges || "");
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
        if (!a) {
            return { xmlid: null, modele: null, id: null, type: null };
        }
        return { xmlid: a.xml_id || a.xmlId || null, modele: a.res_model || null, id: typeof a.id === "number" ? a.id : null, type: a.type || null };
    }
    async ouvrir() {
        if (this.state.occupe) {
            return;
        }
        this.state.occupe = true;
        try {
            const { xmlid, modele, id, type } = this.courant;
            const aide = await this.orm.call("cultiveau.aide", "pour", [xmlid, modele, id, type]);
            if (!aide) {
                this.notification.add("Pas encore de tuto pour cet écran.", { type: "info" });
                return;
            }
            this.dialog.add(AideDialog, { aide });
        } finally {
            this.state.occupe = false;
        }
    }
}

registry.category("systray").add("cultiveau_roles.aide", { Component: AideSystray }, { sequence: 1 });
