/** @odoo-module **/
// Le champ HTML de la page Qualité : les boutons « Voir et corriger » ouvrent la liste du contrôle.
import { Component, markup, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class QualiteHtmlField extends Component {
    static template = "cultiveau_qualite.QualiteHtmlField";
    static props = { ...standardFieldProps };
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.racine = useRef("root");
        onMounted(() => {
            this.racine.el.addEventListener("click", async (ev) => {
                const b = ev.target.closest("button[data-controle]");
                if (!b) {
                    return;
                }
                ev.preventDefault();
                const action = await this.orm.call("cultiveau.qualite", "action_voir", [[this.props.record.resId], +b.dataset.controle]);
                this.action.doAction(action);
            });
        });
    }
    get html() {
        return markup(this.props.record.data[this.props.name] || "");
    }
}

registry.category("fields").add("cultiveau_qualite_html", { component: QualiteHtmlField, supportedTypes: ["html"] });
