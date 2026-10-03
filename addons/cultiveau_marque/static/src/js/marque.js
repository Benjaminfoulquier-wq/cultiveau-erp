/** @odoo-module **/
// Le nom qui s'affiche partout est Cultiveau : titre de l'onglet, et le menu utilisateur sans les liens vers l'éditeur.
import { registry } from "@web/core/registry";
import { titleService } from "@web/core/browser/title_service";

const MARQUE = "Cultiveau";

const titreCultiveau = {
    start() {
        const service = titleService.start();
        const original = service.setParts;
        // Le logiciel pose son propre nom dans la partie « zopenerp » du titre : on y met Cultiveau.
        service.setParts = (parts) => {
            const corrigees = { ...parts };
            if ("zopenerp" in corrigees && corrigees.zopenerp) {
                corrigees.zopenerp = MARQUE;
            }
            return original(corrigees);
        };
        service.setParts({ zopenerp: MARQUE });
        return service;
    },
};
registry.category("services").add("title", titreCultiveau, { force: true });

for (const entree of ["odoo_account", "documentation", "support"]) {
    if (registry.category("user_menuitems").contains(entree)) {
        registry.category("user_menuitems").remove(entree);
    }
}
