/** Un écran de cultiveau.fr ou de la logistique, affiché dans le cadre de l'ERP (le contexte de l'action dit lequel). */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class EcranCultiveau extends Component {
    static template = "cultiveau_site.Ecran";
    static props = { ...standardActionServiceProps };

    get adresse() {
        const vers = this.props.action.params?.vers || this.props.action.context?.vers || "/adherent/espace";
        return `/cultiveau/ecran?vers=${encodeURIComponent(vers)}`;
    }
}

registry.category("actions").add("cultiveau_site.ecran", EcranCultiveau);
