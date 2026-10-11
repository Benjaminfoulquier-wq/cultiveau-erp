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
        this.state = useState({ donnees: null, elements: [], decor: [], stations: [], viewBox: "0 0 10 10", survol: null });
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
        const d = this.state.donnees;
        const elements = [];
        const decor = [];
        const stations = [];
        const court = (texte) => (texte && texte.length > 18 ? texte.slice(0, 17) + "…" : texte || "");
        const ajouter = (x, y, faces, infos) => elements.push({ faces, x, y, cle: elements.length, ...infos, etiquette: court(infos.etiquette) });
        const station = (numero, nom, x, y, w, dd, compte, action) => {
            decor.push({ faces: pave(x, y, 0, w, dd, 0.02, C.zone), cle: nom, x: -100, y: -100 });
            stations.push({ numero, nom, compte, ancre: pt(x + w, y + dd, 0), action });  // le coin bas de la zone : la route, libre
        };
        // Le sol, la route du parcours client, les zones.
        decor.push({ faces: pave(0, 0, -0.3, 36, 28, 0.3, C.sol), cle: "sol", x: -200, y: -200 });
        decor.push({ faces: pave(0, 10.5, 0, 36, 2, 0.01, C.route), cle: "route", x: -99, y: -99 });
        decor.push({ faces: pave(17, 0, 0, 2, 28, 0.01, C.route), cle: "route2", x: -99, y: -99 });
        station(1, "ACCUEIL & COMPTOIR", 19.5, 0.8, 16, 9.2, d.accueil.opportunites.length + d.accueil.comptoir.length,
            { type: "ir.actions.act_window", name: "Opportunités", res_model: "crm.lead", view_mode: "kanban,list,form", views: [[false, "kanban"], [false, "list"], [false, "form"]], domain: [["type", "=", "opportunity"]] });
        station(2, "BUREAU D'ÉTUDE", 0.8, 0.8, 7.5, 9.2, d.bureau.etudes.length + d.bureau.devis.length,
            { type: "ir.actions.act_window", name: "Devis", res_model: "sale.order", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["state", "in", ["draft", "sent"]]] });
        station(3, "MAGASIN & COUR", 8.8, 0.8, 7.7, 9.2, d.magasin.length,
            { type: "ir.actions.act_window", name: "Articles en stock", res_model: "product.template", view_mode: "list,kanban,form", views: [[false, "list"], [false, "kanban"], [false, "form"]], domain: [["qty_available", ">", 0]] });
        station(4, "CHANTIERS", 0.8, 13, 7.5, 14, (d.chantiers.chantiers || []).length + d.chantiers.installations.length + d.chantiers.taches.length,
            d.chantiers.chantiers
                ? { type: "ir.actions.act_window", name: "Chantiers", res_model: "cultiveau.chantier", view_mode: "kanban,list,calendar,form", views: [[false, "kanban"], [false, "list"], [false, "calendar"], [false, "form"]], domain: [["etat", "in", ["brouillon", "planifie", "en_cours"]]] }
                : { type: "ir.actions.act_window", name: "Chantiers", res_model: "cultiveau.installation", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["etat", "=", "realisation"]] });
        station(5, "ATELIER & SAV", 8.8, 13, 7.7, 14, d.atelier.length,
            { type: "ir.actions.act_window", name: "Interventions", res_model: "project.task", view_mode: "kanban,list,form", views: [[false, "kanban"], [false, "list"], [false, "form"]], domain: [["cultiveau_intervention", "=", true], ["state", "not in", ["1_done", "1_canceled"]]] });
        station(6, "PARCELLES EN SERVICE", 19.5, 13, 11, 14, d.parcelles.length,
            { type: "ir.actions.act_window", name: "Parc installé", res_model: "cultiveau.installation", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["etat", "in", ["en_service", "arretee"]]] });
        station(7, "CAISSE", 31, 13, 4.5, 14, d.caisse.length,
            { type: "ir.actions.act_window", name: "Factures à encaisser", res_model: "account.move", view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: [["move_type", "=", "out_invoice"], ["state", "=", "posted"], ["payment_state", "in", ["not_paid", "partial"]]] });

        // 1. L'accueil : le comptoir, la vendeuse, les agriculteurs qui attendent (opportunités) et les ventes de comptoir.
        decor.push({ faces: batiment(20, 1.3, 6, 2.2, 2.2, C.blanc, C.toit), cle: "boutique", x: 20, y: 1.3 });
        decor.push({ faces: pave(20.5, 4, 0, 5, 0.7, 1.0, C.marine), cle: "comptoir", x: 20.5, y: 4 });
        decor.push({ faces: personnage(22.5, 3.0, C.bleu), cle: "vendeur", x: 22.5, y: 3 });
        decor.push({ faces: panneau(33.5, 1.2, C.bleu), cle: "enseigne", x: 33.5, y: 1.2 });
        d.accueil.opportunites.forEach((o, i) => {
            const x = 20.5 + (i % 4) * 1.4, y = 5.6 + Math.floor(i / 4) * 1.6;
            ajouter(x, y, personnage(x, y, C.carton), { titre: `Demande : ${o.nom} — ${o.client} — ${o.etape}${o.montant ? " — " + o.montant.toLocaleString("fr-FR") + " €" : ""}`,
                                                       etiquette: o.client || o.nom, action: this.fiche("crm.lead", o.id) });
        });
        d.accueil.comptoir.forEach((v, i) => {
            const x = 27 + (i % 3) * 1.6, y = 3 + Math.floor(i / 3) * 1.8;
            ajouter(x, y, [...personnage(x, y, C.gris), ...pave(x + 0.9, y + 0.2, 0, 0.5, 0.5, 0.5, C.carton)],
                    { titre: `Vente comptoir ${v.nom} — ${v.client} — ${v.montant.toLocaleString("fr-FR")} €`, etiquette: v.client, action: this.fiche("sale.order", v.id) });
        });
        // 2. Le bureau d'étude : un bureau, les plans (études) et les devis d'installation.
        decor.push({ faces: batiment(1.3, 1.3, 6.5, 2, 2.0, C.blanc, C.toit), cle: "bureau", x: 1.3, y: 1.3 });
        decor.push({ faces: pave(1.8, 4.2, 0, 2.2, 1.0, 0.8, C.bois), cle: "table", x: 1.8, y: 4.2 });
        d.bureau.etudes.forEach((e, i) => {
            const x = 1.2 + (i % 2) * 3.4, y = 5.8 + Math.floor(i / 2) * 1.6;
            ajouter(x, y, [...pave(x, y, 0, 2.2, 1.2, 0.08, e.etat === "etude" ? C.carton : C.gris), ...pave(x + 0.2, y + 0.2, 0.08, 1.8, 0.8, 0.04, C.papier)],
                    { titre: `Étude : ${e.nom} — ${e.client} — ${e.type_libelle}${e.surface ? " — " + e.surface + " ha" : ""} — ${e.etat === "etude" ? "dimensionnement" : "projet"}${e.analyse_validee ? " — analyse validée" : " — analyse des besoins à valider"}`,
                      etiquette: e.client, action: this.fiche("cultiveau.installation", e.id) });
        });
        d.bureau.devis.forEach((v, i) => {
            const x = 4.6 + (i % 2) * 1.3, y = 3.6 + Math.floor(i / 2) * 1.3;
            ajouter(x, y, liasse(x, y, 0.3 + Math.min(1, v.montant / 50000), v.etat === "sent" ? C.bleu : C.gris),
                    { titre: `Devis ${v.nom} — ${v.client} — ${v.installation} — ${v.montant.toLocaleString("fr-FR")} €${v.etat === "sent" ? " (envoyé)" : " (brouillon)"}`, etiquette: v.client, action: this.fiche("sale.order", v.id) });
        });
        // 3. Le magasin et la cour : les rayons, les rouleaux de PE et les tubes dehors, les réceptions fournisseurs.
        decor.push({ faces: batiment(9.3, 1.3, 7, 4.6, 0.02, C.zone, C.zone), cle: "hangar", x: -50, y: -50 });
        d.magasin.forEach((r, i) => {
            const x = 9.5 + (i % 2) * 3.6, y = 1.6 + Math.floor(i / 2) * 1.75;
            const caisses = Math.min(9, Math.max(1, Math.ceil(Math.log10(r.quantite + 1) * 3)));
            ajouter(x, y, etagere(x, y, caisses, i % 2 ? C.carton : C.bleu), {
                titre: `Rayon ${r.nom} — ${r.quantite.toLocaleString("fr-FR")} en stock, ${r.articles} article(s)`, etiquette: r.nom,
                action: { type: "ir.actions.act_window", name: r.nom, res_model: "product.template", view_mode: "list,kanban,form", views: [[false, "list"], [false, "kanban"], [false, "form"]],
                          domain: [["categ_id", "child_of", r.id], ["qty_available", ">", 0]] },
            });
        });
        decor.push({ faces: rouleaux(9.5, 8.5), cle: "rouleaux", x: 9.5, y: 8.5 });
        decor.push({ faces: tubes(11.2, 8.4), cle: "tubes", x: 11.2, y: 8.4 });
        d.cour.receptions.forEach((a, i) => {
            const x = 13 + (i % 2) * 2.2, y = 6.4 + Math.floor(i / 2) * 1.9;
            ajouter(x, y, poidsLourd(x, y), { titre: `Réception attendue : ${a.nom} — ${a.fournisseur} — ${a.montant.toLocaleString("fr-FR")} €${a.date ? " — " + a.date : ""}`,
                                               etiquette: a.fournisseur, action: this.fiche("purchase.order", a.id) });
        });
        d.cour.preparations.forEach((p, i) => {
            const x = 14.5 + (i % 2) * 1.0, y = 1.8 + Math.floor(i / 2) * 1.2;
            ajouter(x, y, pave(x, y, 0, 0.8, 0.8, 0.8, C.carton), { titre: `Préparation à livrer : ${p.nom} — ${p.client}${p.date ? " — " + p.date : ""}`, etiquette: p.client, action: this.fiche("stock.picking", p.id) });
        });
        // 4. Les chantiers : les parcelles en réalisation avec l'équipe de pose et la trancheuse, les mises en service.
        const poses = [
            ...(d.chantiers.chantiers || []).map((c) => ({ ...c, modele: "cultiveau.chantier" })),
            ...d.chantiers.installations.map((c) => ({ ...c, modele: "cultiveau.installation", etat: "en_cours", equipe: 1, avancement: 0 })),
        ];
        poses.slice(0, 6).forEach((c, i) => {
            const x = 1.2 + (i % 2) * 3.6, y = 13.6 + Math.floor(i / 2) * 3.0;
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
            const x = 1.2 + (i % 2) * 3.6, y = 22.5 + Math.floor(i / 2) * 2.0;
            ajouter(x, y, camion(x, y, URGENCE[t.urgence] || C.bleu), { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.date ? " — " + t.date : ""}`,
                                                                        etiquette: t.client || t.nom, action: this.fiche("project.task", t.id) });
        });
        // 5. L'atelier et le SAV : les pompes et enrouleurs sur l'établi (entretiens, diagnostics), les camions de dépannage.
        decor.push({ faces: batiment(9.3, 13.5, 7, 3, 2.4, C.blanc, C.toit), cle: "atelier", x: 9.3, y: 13.5 });
        decor.push({ faces: pave(9.8, 17, 0, 6, 0.9, 0.9, C.bois), cle: "etabli", x: 9.8, y: 17 });
        const depannages = d.atelier.filter((t) => t.nature === "depannage" || t.urgence === "immediate" || t.urgence === "journee");
        const etabli = d.atelier.filter((t) => !depannages.includes(t));
        etabli.forEach((t, i) => {
            const x = 10 + (i % 4) * 1.5, y = 17.1;
            ajouter(x, y, pompe(x, y, URGENCE[t.urgence] || C.bleu), { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.installation ? " — " + t.installation : ""}${t.date ? " — " + t.date : ""}`,
                                                                       etiquette: t.client || t.nom, action: this.fiche("project.task", t.id) });
        });
        depannages.forEach((t, i) => {
            const x = 9.4 + (i % 2) * 3.6, y = 19 + Math.floor(i / 2) * 2.0;
            ajouter(x, y, camion(x, y, URGENCE[t.urgence] || C.bleu), { titre: `Dépannage ${t.urgence_libelle} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.installation ? " — " + t.installation : ""}${t.date ? " — " + t.date : ""}`,
                                                                        etiquette: t.technicien || t.client, action: this.fiche("project.task", t.id) });
        });
        // 6. Les parcelles en service, avec ce que la saison leur demande.
        d.parcelles.forEach((p, i) => {
            const x = 20 + (i % 3) * 3.5, y = 13.6 + Math.floor(i / 3) * 3.0;
            const faces = parcelle(x, y, p.type, p.etat);
            if (p.echeance) {
                faces.push(...panneau(x + 2.0, y + 0.1, C.orange));
            }
            ajouter(x, y, faces, { titre: `${p.nom} — ${p.client} — ${p.type_libelle} — ${p.etat_libelle}${p.surface ? " — " + p.surface + " ha" : ""}${p.commune ? " — " + p.commune : ""}${p.echeance ? " — " + p.echeance : ""}`,
                                   etiquette: p.client, action: this.fiche("cultiveau.installation", p.id) });
        });
        // 7. La caisse : les factures à encaisser, en retard en rouge.
        decor.push({ faces: pave(31.5, 13.6, 0, 3.5, 0.8, 1.0, C.marine), cle: "caisse", x: 31.5, y: 13.6 });
        d.caisse.forEach((f, i) => {
            const x = 31.6 + (i % 3) * 1.1, y = 15 + Math.floor(i / 3) * 1.4;
            ajouter(x, y, liasse(x, y, 0.2 + Math.min(1.2, f.montant / 20000), f.en_retard ? C.rouge : C.vert),
                    { titre: `Facture ${f.nom} — ${f.client} — ${f.montant.toLocaleString("fr-FR")} € restant${f.echeance ? " — échéance " + f.echeance : ""}${f.en_retard ? " (en retard)" : ""}`,
                      etiquette: f.client, action: this.fiche("account.move", f.id) });
        });
        // L'ordre de dessin : du fond vers l'avant.
        const tri = (a, b) => a.x + a.y - (b.x + b.y);
        decor.sort(tri);
        elements.sort(tri);
        const coins = [pt(0, 0, 0), pt(36, 0, 0), pt(36, 28, 0), pt(0, 28, 0), pt(0, 0, 3)];
        const xs = coins.map((c) => c[0]), ys = coins.map((c) => c[1]);
        const minX = Math.min(...xs) - 10, minY = Math.min(...ys) - 60;
        this.state.viewBox = `${minX} ${minY} ${Math.max(...xs) - minX + 10} ${Math.max(...ys) - minY + 30}`;
        this.state.decor = decor;
        this.state.stations = stations;
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
