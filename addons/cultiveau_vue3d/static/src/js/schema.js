/** @odoo-module **/
// L'éditeur de schéma de câblage électrique, ouvert depuis l'armoire de l'atelier câblage.
// Point d'entrée : la toile et le cadre sont posés ici ; l'édition (poser des composants, tirer des fils) vient ensuite.

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class SchemaCablage extends Component {
    static template = "cultiveau_vue3d.Schema";
    static props = { ...standardActionServiceProps };

    setup() {
        this.action = useService("action");
        this.state = useState({
            // la palette des composants qu'on posera bientôt sur la toile
            composants: [
                { cle: "disjoncteur", nom: "Disjoncteur", icone: "fa-toggle-on" },
                { cle: "differentiel", nom: "Différentiel", icone: "fa-shield" },
                { cle: "contacteur", nom: "Contacteur", icone: "fa-square-o" },
                { cle: "bornier", nom: "Bornier", icone: "fa-ellipsis-v" },
                { cle: "moteur", nom: "Moteur / pompe", icone: "fa-cog" },
                { cle: "variateur", nom: "Variateur", icone: "fa-sliders" },
                { cle: "sonde", nom: "Sonde / capteur", icone: "fa-tint" },
                { cle: "alimentation", nom: "Alimentation", icone: "fa-plug" },
            ],
        });
    }

    retour() {
        this.action.doAction("cultiveau_vue3d.action_vue3d", { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("cultiveau_vue3d.schema", SchemaCablage);
