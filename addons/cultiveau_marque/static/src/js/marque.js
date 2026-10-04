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

// L'adresse de l'application est /app : le routeur du client web lit et écrit ce préfixe, les liens internes
// qui porteraient encore l'ancien préfixe sont réécrits, et un clic sur l'un d'eux reste dans l'application.
import { router, routerBus } from "@web/core/browser/router";
import { browser } from "@web/core/browser/browser";

const PREFIXE = "/app";
const ANCIEN = /^\/odoo(?=[/?#]|$)/;
const estApp = (chemin) => chemin === PREFIXE || chemin.startsWith(PREFIXE + "/");

const stateToUrl = router.stateToUrl;
router.stateToUrl = (state) => stateToUrl(state).replace(ANCIEN, PREFIXE);
const urlToState = router.urlToState;
router.urlToState = (urlObj) => {
    if (estApp(urlObj.pathname)) {
        urlObj.pathname = "/odoo" + urlObj.pathname.slice(PREFIXE.length);
    }
    return urlToState(urlObj);
};
// Le routeur a déjà lu l'adresse de départ avec l'ancien préfixe : on la relit.
if (estApp(browser.location.pathname)) {
    router.replaceState(router.urlToState(new URL(browser.location)), { replace: true, sync: true });
}

const corrigerLiens = (racine) => {
    if (!racine || racine.nodeType !== Node.ELEMENT_NODE) {
        return;
    }
    const liens = racine.matches("a[href]") ? [racine] : [];
    liens.push(...racine.querySelectorAll('a[href^="/odoo"]'));
    for (const a of liens) {
        const href = a.getAttribute("href");
        if (ANCIEN.test(href)) {
            a.setAttribute("href", href.replace(ANCIEN, PREFIXE));
        }
    }
};
new MutationObserver((mutations) => {
    for (const m of mutations) {
        if (m.type === "attributes") {
            corrigerLiens(m.target);
        } else {
            m.addedNodes.forEach(corrigerLiens);
        }
    }
}).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ["href"] });

browser.addEventListener(
    "click",
    (ev) => {
        const a = ev.target.closest?.("a[href]");
        if (!a || ev.defaultPrevented || ev.ctrlKey || ev.metaKey || ev.shiftKey || a.target === "_blank" || a.hasAttribute("download")) {
            return;
        }
        let url;
        try {
            url = new URL(a.href);
        } catch {
            return;
        }
        if (url.host !== browser.location.host || !(estApp(url.pathname) || ANCIEN.test(url.pathname)) || !estApp(browser.location.pathname)) {
            return;
        }
        ev.preventDefault();
        router.pushState(router.urlToState(url), { replace: true, sync: true });
        new Promise((res) => setTimeout(res, 0)).then(() => routerBus.trigger("ROUTE_CHANGE"));
    },
    true
);
