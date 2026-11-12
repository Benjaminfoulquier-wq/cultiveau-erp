/** L'outil de câblage (cablage.cultiveau.fr) affiché dans le cadre de l'ERP ; ouvert depuis un dossier, il en reprend la description. */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class OutilCablage extends Component {
    static template = "cultiveau_cablage.Outil";
    static props = { ...standardActionServiceProps };

    get adresse() {
        const armoire = this.props.action.params?.armoire || this.props.action.context?.armoire;
        return "/cultiveau/cablage/ouvrir" + (armoire ? `?armoire=${encodeURIComponent(armoire)}` : "");
    }
}

registry.category("actions").add("cultiveau_cablage.outil", OutilCablage);
