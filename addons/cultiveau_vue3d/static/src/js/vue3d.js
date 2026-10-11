/** @odoo-module **/
// La vue d'ensemble : l'entreprise d'irrigation dessinée en isométrie (SVG) d'après les données de l'ERP, station par
// station le long du parcours client. Chaque élément s'ouvre d'un clic ; les boutons « créer » lancent une étape.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const T = 20; // la taille d'une case, en pixels
const COS = Math.cos(Math.PI / 6);
const SIN = Math.sin(Math.PI / 6);
const C = {
    sol: "#efeae0", zone: "#e6e0d4", route: "#d8d2c4", acier: "#5d6b78", bois: "#c9a46a", carton: "#e3b23c", bleu: "#0b8aa3", marine: "#183840",
    blanc: "#f7f7f5", peau: "#e8b89a", herbe: "#9bc77a", herbeFonce: "#6fa352", terre: "#b58b5a", eau: "#7fc8dd", gris: "#b5bcc4", rouge: "#d9534f",
    orange: "#f0a04b", tube: "#2f3e46", papier: "#fbfaf5", vert: "#4c9a2a", toit: "#8a9ba8",
};
const URGENCE = { immediate: C.rouge, journee: C.orange, semaine: C.bleu, non_urgent: C.gris };
const ETAT = { projet: C.gris, etude: C.carton, realisation: C.orange, en_service: C.herbeFonce, arretee: C.terre };

function pt(x, y, z) {
    return [(x - y) * T * COS, (x + y) * T * SIN - z * T];
}
function teinte(hex, facteur) {
    const n = parseInt(hex.slice(1), 16);
    const c = [n >> 16, (n >> 8) & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(v * facteur))));
    return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
}
function poly(points, fill) {
    return { points: points.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" "), fill };
}
/** Un pavé posé en (x, y, z), de largeur w (vers x), profondeur d (vers y), hauteur h. */
function pave(x, y, z, w, d, h, couleur) {
    const faces = [];
    if (h > 0) {
        faces.push(poly([pt(x, y + d, z), pt(x + w, y + d, z), pt(x + w, y + d, z + h), pt(x, y + d, z + h)], teinte(couleur, 0.78)));
        faces.push(poly([pt(x + w, y, z), pt(x + w, y + d, z), pt(x + w, y + d, z + h), pt(x + w, y, z + h)], teinte(couleur, 0.62)));
    }
    faces.push(poly([pt(x, y, z + h), pt(x + w, y, z + h), pt(x + w, y + d, z + h), pt(x, y + d, z + h)], couleur));
    return faces;
}
const personnage = (x, y, chemise) => [...pave(x + 0.15, y + 0.15, 0, 0.7, 0.7, 0.9, chemise), ...pave(x + 0.25, y + 0.25, 0.9, 0.5, 0.5, 0.45, C.peau)];
const camion = (x, y, couleur) => [
    ...pave(x + 0.1, y + 0.2, 0, 0.6, 1.0, 0.25, C.marine), ...pave(x + 2.1, y + 0.2, 0, 0.6, 1.0, 0.25, C.marine),
    ...pave(x, y, 0.25, 1.1, 1.4, 1.1, couleur), ...pave(x + 1.1, y, 0.25, 1.9, 1.4, 1.5, C.blanc), ...pave(x + 1.1, y + 0.05, 0.9, 1.9, 1.3, 0.3, couleur),
];
const poidsLourd = (x, y) => [
    ...pave(x + 0.2, y + 0.2, 0, 0.6, 1.2, 0.3, C.marine), ...pave(x + 3.2, y + 0.2, 0, 0.6, 1.2, 0.3, C.marine),
    ...pave(x, y, 0.3, 1.2, 1.6, 1.4, C.bleu), ...pave(x + 1.2, y, 0.3, 3.2, 1.6, 2.0, C.blanc),
];
function etagere(x, y, caisses, couleurCaisse) {
    const faces = [...pave(x, y, 0, 0.15, 1.2, 2.6, C.acier), ...pave(x + 2.85, y, 0, 0.15, 1.2, 2.6, C.acier)];
    for (let niveau = 0; niveau < 3; niveau++) {
        faces.push(...pave(x, y, niveau * 0.9, 3, 1.2, 0.08, C.bois));
        for (let k = 0; k < 3; k++) {
            if (niveau * 3 + k < caisses) {
                faces.push(...pave(x + 0.25 + k * 0.9, y + 0.2, niveau * 0.9 + 0.08, 0.7, 0.8, 0.6, k % 2 ? teinte(couleurCaisse, 0.9) : couleurCaisse));
            }
        }
    }
    return faces;
}
const rouleaux = (x, y) => {
    const faces = [];
    for (let k = 0; k < 3; k++) {
        faces.push(...pave(x + k * 1.1, y, 0, 1, 1, 1, C.tube), ...pave(x + k * 1.1 + 0.3, y + 0.3, 1, 0.4, 0.4, 0.05, C.sol));
    }
    faces.push(...pave(x + 0.55, y, 1.05, 1, 1, 1, C.tube), ...pave(x + 0.85, y + 0.3, 2.05, 0.4, 0.4, 0.05, C.sol));
    return faces;
}
const tubes = (x, y) => {
    const faces = [];
    for (let k = 0; k < 4; k++) {
        faces.push(...pave(x, y + k * 0.35, k % 2 ? 0.3 : 0, 5, 0.3, 0.3, k % 2 ? C.bleu : C.tube));
    }
    return faces;
};
function parcelle(x, y, type, etat) {
    const faces = [...pave(x, y, 0, 3, 2.4, 0.12, etat === "projet" || etat === "etude" ? C.terre : C.herbe)];
    const c = ETAT[etat] || C.gris;
    if (type === "pivot") {
        faces.push(...pave(x + 1.4, y + 1.1, 0.12, 0.3, 0.3, 0.9, C.acier), ...pave(x + 0.3, y + 1.15, 0.9, 2.5, 0.2, 0.12, c));
    } else if (type === "enrouleur") {
        faces.push(...pave(x + 0.4, y + 0.9, 0.12, 0.8, 0.7, 0.8, c), ...pave(x + 1.2, y + 1.2, 0.12, 1.6, 0.1, 0.1, C.marine));
    } else if ((type || "").startsWith("goutte") || type === "micro_aspersion") {
        for (let r = 0; r < 4; r++) {
            faces.push(...pave(x + 0.3, y + 0.3 + r * 0.55, 0.12, 2.4, 0.08, 0.06, c));
        }
    } else {
        for (let r = 0; r < 3; r++) {
            faces.push(...pave(x + 0.5 + r * 0.9, y + 1.0, 0.12, 0.15, 0.15, 0.7, C.acier), ...pave(x + 0.35 + r * 0.9, y + 0.85, 0.82, 0.45, 0.45, 0.1, c));
        }
    }
    return faces;
}
const batiment = (x, y, w, d, h, mur, toit) => [...pave(x, y, 0, w, d, h, mur), ...pave(x - 0.15, y - 0.15, h, w + 0.3, d + 0.3, 0.25, toit)];
const pompe = (x, y, couleur) => [...pave(x, y, 0, 0.9, 0.6, 0.5, couleur), ...pave(x + 0.2, y + 0.15, 0.5, 0.5, 0.3, 0.5, C.acier), ...pave(x + 0.9, y + 0.15, 0.15, 0.6, 0.3, 0.3, C.tube)];
const liasse = (x, y, hauteur, couleur) => [...pave(x, y, 0, 0.8, 1.0, hauteur, C.papier), ...pave(x + 0.1, y + 0.2, hauteur, 0.6, 0.15, 0.03, couleur)];
const panneau = (x, y, couleur) => [...pave(x + 0.45, y + 0.45, 0, 0.1, 0.1, 1.6, C.acier), ...pave(x, y + 0.35, 1.6, 1.0, 0.1, 0.7, couleur)];

export class VueEnsemble extends Component {
    static template = "cultiveau_vue3d.Vue";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ donnees: null, elements: [], decor: [], stations: [], libelles: [], viewBox: "0 0 10 10", survol: null });
        onWillStart(async () => {
            await this.charger();
        });
    }

    async charger() {
        this.state.donnees = await this.orm.call("cultiveau.scene", "donnees", []);
        this.construire();
    }

    fiche(modele, id) {
        return { type: "ir.actions.act_window", res_model: modele, res_id: id, views: [[false, "form"]] };
    }

    construire() {
        // Le plan type d'un site adhérent Cultiveau (bâtiment 48 × 21 m, terrain 5 000 à 6 000 m²), 1 case = 2 m.
        // Une règle structure le site : le client et le poids lourd ne se croisent jamais. Les parcelles sont de l'autre côté de la route.
        const d = this.state.donnees;
        const elements = [];
        const decor = [];
        const stations = [];
        const libelles = [];
        const court = (texte) => (texte && texte.length > 18 ? texte.slice(0, 17) + "…" : texte || "");
        const ajouter = (x, y, faces, infos) => elements.push({ faces, x, y, cle: elements.length, ...infos, etiquette: court(infos.etiquette) });
        const fond = (cle, faces, x = -100, y = -100) => decor.push({ faces, cle, x, y });
        const station = (numero, nom, x, y, compte, action) => stations.push({ numero, nom, compte, ancre: pt(x, y, 0), action });  // la pastille dans la zone
        const libelle = (texte, x, y, classe = "") => libelles.push({ texte, p: pt(x, y, 0), classe });
        const mur = (x, y, w, dd, h, couleur = C.blanc) => fond(`mur${x},${y}`, pave(x, y, 0, w, dd, h, couleur), x, y);
        const sol = (cle, x, y, w, dd, couleur) => fond(cle, pave(x, y, 0, w, dd, 0.02, couleur));

        // Le terrain, la route d'accès, les champs de l'autre côté.
        fond("terrain", pave(-0.5, -0.5, -0.3, 25, 18.8, 0.3, C.sol), -200, -200);
        fond("route", pave(-0.5, 18.3, -0.3, 25, 2.4, 0.3, C.route), -199, -199);
        fond("champs", pave(-0.5, 20.7, -0.3, 25, 10.8, 0.3, C.herbe), -198, -198);
        fond("bande", pave(-0.5, 19.45, 0, 25, 0.1, 0.01, C.blanc), -150, -150);
        libelle("ROUTE D'ACCÈS", 23.2, 19.5, "route");
        libelle("ENTRÉE CLIENTS", 3, 17.85, "entree");
        libelle("ENTRÉE PL", 21, 17.85, "entree");
        fond("fleche-clients", pave(2.9, 17.6, 0, 0.2, 0.7, 0.05, C.vert), 2.9, 17.6);
        fond("fleche-pl", pave(20.9, 17.6, 0, 0.2, 0.7, 0.05, C.marine), 20.9, 17.6);

        // Le bâtiment (24 × 10,5 cases) : dalle, murs du fond, cloisons basses pour voir dedans.
        sol("dalle", 0, 0, 24, 10.5, C.zone);
        sol("magasin", 0, 4.5, 6.5, 6, "#e3efe9");
        mur(0, -0.15, 24.15, 0.15, 1.6, C.blanc);          // mur nord
        mur(-0.15, -0.15, 0.15, 10.8, 1.6, C.blanc);       // mur ouest
        mur(24, -0.15, 0.15, 10.8, 0.35, C.blanc);         // mur est (bas)
        mur(0, 10.5, 6.5, 0.15, 0.35, C.eau);              // la vitrine du magasin
        mur(6.5, 10.5, 17.5, 0.15, 0.35, C.blanc);         // façade sud
        mur(6.5, 0, 0.15, 10.5, 0.35, C.gris);             // cloison magasin / stockage
        mur(17, 0, 0.15, 10.5, 0.35, C.gris);              // cloison stockage / atelier
        mur(0, 4.5, 6.5, 0.15, 0.35, C.gris);              // cloison administratif / magasin
        libelle("ADMINISTRATIF", 3.2, 0.2, "zone");
        libelle("MAGASIN", 1.7, 4.75, "zone");
        libelle("STOCKAGE", 11.7, 0.2, "zone");
        libelle("ATELIER", 20.5, 0.2, "zone");

        // 2. L'administratif : le bureau d'étude (plans), la salle de réunion (devis avec l'agriculteur), le bureau de la caisse.
        fond("bureau1", pave(0.4, 0.5, 0, 2.6, 0.7, 0.75, C.bois), 0.4, 0.5);
        fond("table-reunion", pave(0.6, 2.7, 0, 2.3, 1.1, 0.7, C.bois), 0.6, 2.7);
        fond("bureau2", pave(3.5, 0.5, 0, 2.6, 0.7, 0.75, C.bois), 3.5, 0.5);
        fond("wc", pave(3.5, 2.7, 0, 2.6, 1.4, 0.5, C.blanc), 3.5, 2.7);
        libelle("réunion", 1.75, 3.9, "piece");
        libelle("wc · vestiaires", 4.8, 3.9, "piece");
        station(2, "BUREAU D'ÉTUDE", 0.5, 0.4, d.bureau.etudes.length + d.bureau.devis.length,
            { type: "ir.actions.act_window", name: "Devis", res_model: "sale.order", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["state", "in", ["draft", "sent"]]] });
        d.bureau.etudes.forEach((e, i) => {
            // les plans sur le bureau d'étude, puis par terre devant
            const x = 0.45 + (i % 2) * 1.3, yy = i < 2 ? 0.55 : 1.35 + Math.floor((i - 2) / 2) * 0.5;
            const z = i < 2 ? 0.75 : 0;
            ajouter(x, yy, [...pave(x, yy, z, 1.1, 0.6, 0.06, e.etat === "etude" ? C.carton : C.gris), ...pave(x + 0.1, yy + 0.1, z + 0.06, 0.9, 0.4, 0.03, C.papier)],
                    { titre: `Étude : ${e.nom} — ${e.client} — ${e.type_libelle}${e.surface ? " — " + e.surface + " ha" : ""} — ${e.etat === "etude" ? "dimensionnement" : "projet"}${e.analyse_validee ? " — analyse validée" : " — analyse des besoins à valider"}`,
                      etiquette: e.client, action: this.fiche("cultiveau.installation", e.id) });
        });
        d.bureau.devis.forEach((v, i) => {
            const x = 0.7 + (i % 4) * 0.55, y = 2.8 + Math.floor(i / 4) * 0.5;
            ajouter(x, y, [...pave(x, y, 0.7, 0.45, 0.4, 0.15 + Math.min(0.5, v.montant / 50000), C.papier), ...pave(x + 0.05, y + 0.1, 0.85 + Math.min(0.5, v.montant / 50000), 0.35, 0.08, 0.02, v.etat === "sent" ? C.bleu : C.gris)],
                    { titre: `Devis ${v.nom} — ${v.client} — ${v.installation} — ${v.montant.toLocaleString("fr-FR")} €${v.etat === "sent" ? " (envoyé)" : " (brouillon)"}`, etiquette: v.client, action: this.fiche("sale.order", v.id) });
        });
        // 7. La caisse : le second bureau, les factures à encaisser, en retard en rouge.
        station(7, "CAISSE", 5.2, 9.3, d.caisse.length,
            { type: "ir.actions.act_window", name: "Factures à encaisser", res_model: "account.move", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["move_type", "=", "out_invoice"], ["state", "=", "posted"], ["payment_state", "in", ["not_paid", "partial"]]] });
        d.caisse.forEach((f, i) => {
            const x = 5.0 + (i % 2) * 0.45, y = 5.15 + Math.floor(i / 2) * 0.55;
            ajouter(x, y, [...pave(x, y, 1.0, 0.4, 0.45, 0.1 + Math.min(0.6, f.montant / 20000), C.papier), ...pave(x + 0.05, y + 0.1, 1.1 + Math.min(0.6, f.montant / 20000), 0.3, 0.1, 0.02, f.en_retard ? C.rouge : C.vert)],
                    { titre: `Facture ${f.nom} — ${f.client} — ${f.montant.toLocaleString("fr-FR")} € restant${f.echeance ? " — échéance " + f.echeance : ""}${f.en_retard ? " (en retard)" : ""}`,
                      etiquette: f.client, action: this.fiche("account.move", f.id) });
        });

        // 1. Le magasin : la vitrine du réseau. Libre-service des petites pièces, coin conseil avec écran, comptoir au fond collé au stockage.
        for (let r = 0; r < 3; r++) {
            fond(`libre-service-${r}`, [...pave(0.6, 5.1 + r * 1.3, 0, 2.6, 0.5, 0.9, C.gris), ...pave(0.7, 5.15 + r * 1.3, 0.9, 2.4, 0.4, 0.15, r % 2 ? C.carton : C.bleu)], 0.6, 5.1 + r * 1.3);
        }
        fond("ecran-conseil", [...pave(0.5, 9.6, 0, 1.2, 0.35, 0.7, C.bois), ...pave(0.6, 9.65, 0.7, 1.0, 0.1, 0.6, C.marine)], 0.5, 9.6);
        fond("comptoir", pave(4.9, 5.0, 0, 0.9, 3.4, 1.0, C.marine), 4.9, 5.0);
        fond("vendeur", personnage(5.9, 6.3, C.bleu), 5.9, 6.3);
        fond("enseigne", panneau(-0.3, 11.2, C.bleu), -0.3, 11.2);
        libelle("libre-service", 1.9, 9.2, "piece");
        libelle("comptoir", 5.35, 8.8, "piece");
        station(1, "ACCUEIL & COMPTOIR", 0.5, 4.9, d.accueil.opportunites.length + d.accueil.comptoir.length,
            { type: "ir.actions.act_window", name: "Demandes en cours", res_model: "crm.lead", view_mode: "kanban,list,form", views: [[false, "kanban"], [false, "list"], [false, "form"]], domain: [["type", "=", "opportunity"]] });
        d.accueil.opportunites.forEach((o, i) => {
            // les agriculteurs qui attendent au comptoir (deux files), puis ceux qui arrivent du parking
            const [xx, yy] = i < 8 ? [3.9 - Math.floor(i / 4) * 0.7, 5.1 + (i % 4) * 0.85] : [0.7 + ((i - 8) % 4) * 1.5, 12.6 + Math.floor((i - 8) / 4) * 3.1];
            ajouter(xx, yy, personnage(xx, yy, C.carton), { titre: `Demande : ${o.nom} — ${o.client} — ${o.etape}${o.montant ? " — " + o.montant.toLocaleString("fr-FR") + " €" : ""}`,
                                                             etiquette: o.client || o.nom, action: this.fiche("crm.lead", o.id) });
        });
        d.accueil.comptoir.forEach((v, i) => {
            const x = 3.9 + (i % 2) * 0.5, y = 8.9 + Math.floor(i / 2) * 0.55;
            ajouter(x, y, pave(x, y, 0, 0.45, 0.45, 0.45, C.carton),
                    { titre: `Vente comptoir ${v.nom} — ${v.client} — ${v.montant.toLocaleString("fr-FR")} €`, etiquette: v.client, action: this.fiche("sale.order", v.id) });
        });

        // 3. Le stockage : racks à palettes et casiers adressés (les rayons), la zone de préparation des commandes et des chantiers.
        libelle("préparation commandes · chantiers", 11.7, 7.2, "piece");
        station(3, "MAGASIN & COUR", 7.2, 0.4, d.magasin.length + d.cour.receptions.length + d.cour.preparations.length,
            { type: "ir.actions.act_window", name: "Articles en stock", res_model: "product.template", view_mode: "list,kanban,form", views: [[false, "list"], [false, "kanban"], [false, "form"]], domain: [["qty_available", ">", 0]] });
        d.magasin.forEach((r, i) => {
            const x = 7.2 + (i % 3) * 3.3, y = 0.8 + Math.floor(i / 3) * 2.4;
            const caisses = Math.min(9, Math.max(1, Math.ceil(Math.log10(r.quantite + 1) * 3)));
            ajouter(x, y, etagere(x, y, caisses, i % 2 ? C.carton : C.bleu), {
                titre: `Rayon ${r.nom} — ${r.quantite.toLocaleString("fr-FR")} en stock, ${r.articles} article(s)`, etiquette: r.nom,
                action: { type: "ir.actions.act_window", name: r.nom, res_model: "product.template", view_mode: "list,kanban,form", views: [[false, "list"], [false, "kanban"], [false, "form"]],
                          domain: [["categ_id", "child_of", r.id], ["qty_available", ">", 0]] },
            });
        });
        fond("chariot", [...pave(15.2, 8.6, 0, 1.2, 0.8, 0.6, C.carton), ...pave(15.2, 8.6, 0.6, 0.4, 0.8, 0.9, C.marine), ...pave(16.4, 8.9, 0, 0.9, 0.2, 0.08, C.acier)], 15.2, 8.6);
        d.cour.preparations.forEach((p, i) => {
            const x = 7.3 + (i % 6) * 1.3, y = 8.0 + Math.floor(i / 6) * 1.1;
            ajouter(x, y, pave(x, y, 0, 0.8, 0.8, 0.8, C.carton), { titre: `Préparation à livrer : ${p.nom} — ${p.client}${p.date ? " — " + p.date : ""}`, etiquette: p.client, action: this.fiche("stock.picking", p.id) });
        });

        // 5. L'atelier : banc d'essai pompes, local électrique, soudure PE, préfabrication des stations de tête, établis, zone enrouleurs et pivots.
        fond("banc-pompes", [...pave(17.5, 0.5, 0, 3, 1.1, 0.5, C.acier), ...pave(17.6, 0.6, 0.5, 2.8, 0.9, 0.2, C.eau)], 17.5, 0.5);
        fond("elec", [...pave(21.5, 0.4, 0, 2.2, 1.0, 1.2, C.gris), ...pave(21.6, 0.45, 1.2, 2.0, 0.9, 0.05, C.marine)], 21.5, 0.4);
        fond("soudure", [...pave(17.5, 2.3, 0, 2.5, 0.8, 0.7, C.bois), ...pave(18.2, 2.5, 0.7, 1.0, 0.4, 0.3, C.tube)], 17.5, 2.3);
        fond("prefa", [...pave(21.3, 2.2, 0, 2.3, 2.6, 0.08, C.gris), ...pave(21.6, 2.5, 0.08, 1.8, 0.3, 0.3, C.bleu), ...pave(21.6, 3.3, 0.08, 1.8, 0.3, 0.3, C.bleu), ...pave(22.2, 2.5, 0.38, 0.6, 1.1, 0.5, C.marine)], 21.3, 2.2);
        fond("etablis", pave(17.5, 4.3, 0, 2.5, 0.8, 0.85, C.bois), 17.5, 4.3);
        fond("pont-roulant", [...pave(17.3, 6.0, 0, 0.12, 0.12, 2.2, C.acier), ...pave(23.6, 6.0, 0, 0.12, 0.12, 2.2, C.acier), ...pave(17.3, 6.0, 2.2, 6.4, 0.12, 0.12, C.carton)], 17.3, 6.0);
        libelle("banc pompes", 19, 1.9, "piece");
        libelle("élec.", 22.6, 1.7, "piece");
        libelle("soudure PE", 18.75, 3.4, "piece");
        libelle("préfa", 22.45, 5.1, "piece");
        libelle("enrouleurs · pivots", 20.5, 9.9, "piece");
        station(5, "ATELIER & SAV", 17.7, 0.4, d.atelier.length,
            { type: "ir.actions.act_window", name: "Interventions", res_model: "project.task", view_mode: "kanban,list,form", views: [[false, "kanban"], [false, "list"], [false, "form"]], domain: [["cultiveau_intervention", "=", true], ["state", "not in", ["1_done", "1_canceled"]]] });
        const depannages = d.atelier.filter((t) => t.nature === "depannage" || t.urgence === "immediate" || t.urgence === "journee");
        const etabli = d.atelier.filter((t) => !depannages.includes(t));
        const places = [[17.7, 0.6], [19.2, 0.6], [17.7, 4.3], [19.2, 4.3], [17.8, 6.6], [19.8, 6.6], [21.8, 6.6], [17.8, 8.3], [19.8, 8.3], [21.8, 8.3]];
        etabli.forEach((t, i) => {
            const [x, y] = places[i % places.length];
            const faces = i < 4 ? pompe(x, y + (i < 2 ? 0.15 : -0.1), URGENCE[t.urgence] || C.bleu)
                                : [...pave(x, y, 0, 1.0, 0.9, 1.0, URGENCE[t.urgence] || C.bleu), ...pave(x + 1.0, y + 0.3, 0, 0.9, 0.12, 0.12, C.marine), ...pave(x - 0.1, y - 0.1, 1.0, 1.2, 1.1, 0.05, C.acier)];
            ajouter(x, y, faces, { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.installation ? " — " + t.installation : ""}${t.date ? " — " + t.date : ""}`,
                                   etiquette: t.client || t.nom, action: this.fiche("project.task", t.id) });
        });

        // Dehors, côté client : le parking (8 places, dont une PMR) ouvert sur la route, sans passer par la cour.
        sol("parking", 0, 12, 6.5, 5.5, "#dfe9e4");
        for (let k = 0; k < 5; k++) {
            fond(`place-${k}`, [...pave(0.3 + k * 1.5, 12.2, 0, 0.06, 2.0, 0.01, C.blanc), ...pave(0.3 + k * 1.5, 15.3, 0, 0.06, 2.0, 0.01, C.blanc)], -90, -90);
        }
        fond("pmr", pave(0.5, 12.5, 0, 1.1, 0.6, 0.02, C.bleu), -89, -89);
        libelle("PARKING CLIENTS", 3.2, 14.2, "zone");
        fond("allee", pave(6.5, 10.6, 0, 11, 1.2, 0.005, C.route), -95, -95);  // l'allée interne entre le bâtiment et le dépôt

        // Dehors, côté interne : le dépôt extérieur (auvent et racks cantilever pour les tubes, bobines PE, occasion et reprises, bennes de tri).
        sol("depot", 7.5, 12, 9.5, 5.5, C.zone);
        fond("auvent", [...[7.7, 11.5, 15.3].flatMap((x) => [...pave(x, 12.2, 0, 0.15, 0.15, 1.7, C.acier), ...pave(x, 13.9, 0, 0.15, 0.15, 1.7, C.acier)]), ...pave(7.5, 12.0, 1.7, 8.5, 2.2, 0.12, C.toit)], 7.5, 12.0);
        fond("tubes-pvc", tubes(8.2, 12.4), 8.2, 12.4);
        fond("tubes-acier", tubes(12.0, 12.4), 12.0, 12.4);
        fond("bobines", rouleaux(7.8, 15.0), 7.8, 15.0);
        fond("occasion", [...pave(12.5, 15.0, 0, 1.2, 1.0, 1.1, C.terre), ...pave(13.7, 15.3, 0, 1.4, 0.12, 0.12, C.marine), ...pave(15.3, 15.1, 0, 0.9, 0.6, 0.5, C.gris)], 12.5, 15.0);
        for (let k = 0; k < 3; k++) {
            fond(`benne-${k}`, pave(7.8 + k * 1.3, 16.5, 0, 1.0, 0.7, 0.6, [C.vert, C.carton, C.acier][k]), 7.8 + k * 1.3, 16.5);
        }
        libelle("DÉPÔT EXTÉRIEUR", 12.2, 11.6, "zone");
        libelle("bobines PE", 9.4, 16.1, "piece");
        libelle("occasion · reprises", 14, 16.3, "piece");
        libelle("tri", 11.8, 17.1, "piece");

        // La cour poids lourds : entrée séparée, quai, aire de lavage. Les réceptions fournisseurs attendues, les camions de dépannage qui partent.
        sol("cour", 17.5, 12, 6.5, 5.5, "#dcd6ca");
        fond("quai", pave(17.8, 12.2, 0, 1.4, 4.8, 0.6, C.gris), 17.8, 12.2);
        fond("lavage", [...pave(21.0, 15.8, 0, 2.6, 1.4, 0.03, C.eau), ...pave(21.1, 15.9, 0, 0.12, 0.12, 1.3, C.acier)], 21.0, 15.8);
        libelle("COUR PL", 20.5, 11.6, "zone");
        libelle("quai", 18.5, 17.2, "piece");
        libelle("lavage", 22.3, 17.3, "piece");
        d.cour.receptions.forEach((a, i) => {
            const x = 19.4, y = 12.2 + i * 1.8;
            ajouter(x, y, poidsLourd(x, y), { titre: `Réception attendue : ${a.nom} — ${a.fournisseur} — ${a.montant.toLocaleString("fr-FR")} €${a.date ? " — " + a.date : ""}`,
                                               etiquette: a.fournisseur, action: this.fiche("purchase.order", a.id) });
        });
        depannages.forEach((t, i) => {
            const [x, y] = [[15.5, 18.9], [21.0, 12.3], [21.0, 14.1], [19.4, 16.3]][i % 4];
            ajouter(x, y, camion(x, y, URGENCE[t.urgence] || C.bleu), { titre: `Dépannage ${t.urgence_libelle} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.installation ? " — " + t.installation : ""}${t.date ? " — " + t.date : ""}`,
                                                                        etiquette: t.technicien || t.client, action: this.fiche("project.task", t.id) });
        });

        // De l'autre côté de la route, chez les agriculteurs : 4. les chantiers (équipe de pose), 6. les parcelles en service.
        libelle("CHEZ LES AGRICULTEURS", 12, 21.1, "zone");
        libelle("chantiers", 3.9, 30.9, "piece");
        libelle("parcelles en service", 16.5, 30.9, "piece");
        station(4, "CHANTIERS", 0.4, 21.3, (d.chantiers.chantiers || []).length + d.chantiers.installations.length + d.chantiers.taches.length,
            d.chantiers.chantiers
                ? { type: "ir.actions.act_window", name: "Chantiers", res_model: "cultiveau.chantier", view_mode: "kanban,list,calendar,form", views: [[false, "kanban"], [false, "list"], [false, "calendar"], [false, "form"]], domain: [["etat", "in", ["brouillon", "planifie", "en_cours"]]] }
                : { type: "ir.actions.act_window", name: "Chantiers", res_model: "cultiveau.installation", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["etat", "=", "realisation"]] });
        const poses = [
            ...(d.chantiers.chantiers || []).map((c) => ({ ...c, modele: "cultiveau.chantier" })),
            ...d.chantiers.installations.map((c) => ({ ...c, modele: "cultiveau.installation", etat: "en_cours", equipe: 1, avancement: 0 })),
        ];
        poses.slice(0, 6).forEach((c, i) => {
            const x = 0.3 + (i % 2) * 3.6, y = 22.2 + Math.floor(i / 2) * 3.0;
            const couleur = c.etat === "planifie" ? C.bleu : C.orange;
            const equipe = Math.min(3, 1 + (c.equipe || 0));
            const faces = [...parcelle(x, y, c.type, "realisation")];
            if (c.etat !== "planifie") {
                faces.push(...pave(x + 0.2, y + 0.2, 0.12, 1.2, 0.8, 0.7, couleur));
            }
            for (let k = 0; k < equipe; k++) {
                faces.push(...personnage(x + 1.8 + (k % 2) * 0.5, y + 0.2 + k * 0.6, couleur));
            }
            const detail = c.modele === "cultiveau.chantier"
                ? `${c.etat === "planifie" ? "Chantier planifié" : "Chantier en cours"} : ${c.titre} — ${c.client}${c.chef ? " — " + c.chef : ""}${c.debut ? " — du " + c.debut + (c.fin ? " au " + c.fin : "") : ""} — ${c.avancement} %`
                : `Chantier : ${c.nom} — ${c.client} — ${c.type_libelle}${c.surface ? " — " + c.surface + " ha" : ""}${c.commune ? " — " + c.commune : ""}`;
            ajouter(x, y, faces, { titre: detail, etiquette: c.client, action: this.fiche(c.modele, c.id) });
        });
        d.chantiers.taches.forEach((t, i) => {
            const x = 5.8 + (i % 3) * 3.3, y = 18.9;
            ajouter(x, y, camion(x, y, URGENCE[t.urgence] || C.bleu), { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.date ? " — " + t.date : ""}`,
                                                                        etiquette: t.client || t.nom, action: this.fiche("project.task", t.id) });
        });
        station(6, "PARCELLES EN SERVICE", 9.9, 21.3, d.parcelles.length,
            { type: "ir.actions.act_window", name: "Parc installé", res_model: "cultiveau.installation", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["etat", "in", ["en_service", "arretee"]]] });
        d.parcelles.forEach((p, i) => {
            const x = 9.8 + (i % 4) * 3.6, y = 22.2 + Math.floor(i / 4) * 3.0;
            const faces = parcelle(x, y, p.type, p.etat);
            if (p.echeance) {
                faces.push(...panneau(x + 2.0, y + 0.1, C.orange));
            }
            ajouter(x, y, faces, { titre: `${p.nom} — ${p.client} — ${p.type_libelle} — ${p.etat_libelle}${p.surface ? " — " + p.surface + " ha" : ""}${p.commune ? " — " + p.commune : ""}${p.echeance ? " — " + p.echeance : ""}`,
                                   etiquette: p.client, action: this.fiche("cultiveau.installation", p.id) });
        });

        // L'ordre de dessin : du fond vers l'avant.
        const tri = (a, b) => a.x + a.y - (b.x + b.y);
        decor.sort(tri);
        elements.sort(tri);
        stations.sort((a, b) => a.numero - b.numero);
        const coins = [pt(-0.5, -0.5, 0), pt(24.5, -0.5, 0), pt(24.5, 31.5, 0), pt(-0.5, 31.5, 0), pt(-0.5, -0.5, 3)];
        const xs = coins.map((c) => c[0]), ys = coins.map((c) => c[1]);
        const minX = Math.min(...xs) - 10, minY = Math.min(...ys) - 40;
        this.state.viewBox = `${minX} ${minY} ${Math.max(...xs) - minX + 10} ${Math.max(...ys) - minY + 30}`;
        this.state.decor = decor;
        this.state.stations = stations;
        this.state.libelles = libelles;
        this.state.elements = elements;
    }

    ouvrir(element) {
        if (element.action) {
            this.action.doAction(element.action);
        }
    }

    ouvrirListe(modele, domaine, nom) {
        this.action.doAction({ type: "ir.actions.act_window", name: nom, res_model: modele, view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: domaine });
    }

    ouvrirAction(xmlid) {
        this.action.doAction(xmlid);
    }

    creer(modele, contexte) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: modele, views: [[false, "form"]], target: "current", context: contexte || {} });
    }

    etiquette(element) {
        return pt(element.x, element.y + 1.2, 1.9);
    }
}

registry.category("actions").add("cultiveau_vue3d.vue", VueEnsemble);
