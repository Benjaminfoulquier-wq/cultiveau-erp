/** @odoo-module **/
// La vue d'ensemble : le site type d'un adhérent Cultiveau dessiné en isométrie, à l'échelle (1 case = 1 m), et qui ouvre tout.
// Chaque poste du plan (le bureau de facturation, le coin conseil, un rayon, le quai…) ouvre une carte d'actions ;
// chaque objet vivant (un devis, une facture, un camion, un chantier) ouvre sa fiche. On zoome à la molette, on se déplace
// en glissant, on vole d'une zone à l'autre, et « Où aller ? » trouve le bon poste.
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const T = 20; // une case (1 m), en unités du dessin
const COS = Math.cos(Math.PI / 6);
const SIN = Math.sin(Math.PI / 6);
const C = {
    sol: "#efeae0", zone: "#e6e0d4", route: "#cfc8b8", acier: "#5d6b78", bois: "#c9a46a", carton: "#e3b23c", bleu: "#0b8aa3", marine: "#183840",
    blanc: "#f7f7f5", peau: "#e8b89a", herbe: "#a5cf84", herbeFonce: "#6fa352", terre: "#b58b5a", eau: "#7fc8dd", gris: "#b5bcc4", rouge: "#d9534f",
    orange: "#f0a04b", tube: "#2f3e46", papier: "#fbfaf5", vert: "#4c9a2a", toit: "#8a9ba8", client: "#d7ece3", admin: "#ebe5f0", atelier: "#dcd8cf",
    vitre: "#bfe3ec",
};
const URGENCE = { immediate: C.rouge, journee: C.orange, semaine: C.bleu, non_urgent: C.gris };
const ETAT = { projet: C.gris, etude: C.carton, realisation: C.orange, en_service: C.herbeFonce, arretee: C.terre };
const TEINTES_FAMILLES = [C.bleu, C.carton, C.vert, C.orange, "#7a6fb0", C.rouge, "#2a9d8f", "#c06c84"];

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
const personnage = (x, y, chemise) => [...pave(x + 0.15, y + 0.15, 0, 0.5, 0.4, 1.0, chemise), ...pave(x + 0.22, y + 0.2, 1.0, 0.36, 0.3, 0.36, C.peau)];
const camion = (x, y, couleur) => [
    ...pave(x + 0.3, y + 0.1, 0, 0.6, 1.8, 0.4, C.marine), ...pave(x + 3.6, y + 0.1, 0, 0.6, 1.8, 0.4, C.marine),
    ...pave(x, y, 0.4, 1.4, 2.0, 1.4, couleur), ...pave(x + 1.4, y, 0.4, 3.2, 2.0, 1.8, C.blanc), ...pave(x + 1.4, y + 0.05, 1.5, 3.2, 1.9, 0.4, couleur),
];
const poidsLourd = (x, y) => [
    ...pave(x + 0.4, y + 0.2, 0, 0.8, 2.0, 0.5, C.marine), ...pave(x + 7.2, y + 0.2, 0, 0.8, 2.0, 0.5, C.marine),
    ...pave(x, y, 0.5, 2.0, 2.4, 2.4, C.bleu), ...pave(x + 2.2, y, 0.5, 6.4, 2.4, 2.9, C.blanc), ...pave(x + 2.2, y + 0.05, 2.9, 6.4, 2.3, 0.5, C.bleu),
];
function rack(x, y, remplissage, couleur) {
    // un rack à palettes de 3,6 × 1,1 m sur trois niveaux ; les palettes reflètent le stock de la famille
    const faces = [...pave(x, y, 0, 0.12, 1.1, 3.0, C.acier), ...pave(x + 3.48, y, 0, 0.12, 1.1, 3.0, C.acier)];
    for (let niveau = 0; niveau < 3; niveau++) {
        faces.push(...pave(x, y, niveau * 1.0, 3.6, 1.1, 0.08, C.carton === couleur ? C.bois : teinte(C.acier, 1.3)));
        for (let k = 0; k < 3; k++) {
            if (niveau * 3 + k < remplissage) {
                faces.push(...pave(x + 0.2 + k * 1.15, y + 0.15, niveau * 1.0 + 0.08, 1.0, 0.8, 0.7, k % 2 ? teinte(couleur, 0.88) : couleur));
            }
        }
    }
    return faces;
}
function gondole(x, y, couleur, remplissage) {
    const faces = [...pave(x, y, 0, 4.2, 1.0, 1.5, C.gris)];
    for (let k = 0; k < Math.max(1, remplissage); k++) {
        faces.push(...pave(x + 0.2 + (k % 5) * 0.8, y + 0.15, 1.5, 0.6, 0.7, 0.35, k % 2 ? teinte(couleur, 0.85) : couleur));
    }
    return faces;
}
const bobines = (x, y) => {
    const faces = [];
    for (let k = 0; k < 4; k++) {
        faces.push(...pave(x + k * 1.6, y, 0, 1.4, 1.4, 1.2, C.tube), ...pave(x + k * 1.6 + 0.45, y + 0.45, 1.2, 0.5, 0.5, 0.05, C.sol));
    }
    faces.push(...pave(x + 0.8, y, 1.25, 1.4, 1.4, 1.2, C.tube), ...pave(x + 1.25, y + 0.45, 2.45, 0.5, 0.5, 0.05, C.sol));
    return faces;
};
const cantilever = (x, y, longueur, couleur) => {
    const faces = [];
    for (let k = 0; k < 3; k++) {
        faces.push(...pave(x + k * (longueur / 2 - 0.1), y, 0, 0.15, 1.6, 2.4, C.acier));
    }
    for (let n = 0; n < 4; n++) {
        faces.push(...pave(x, y + 0.2, 0.3 + n * 0.55, longueur, 1.2, 0.3, n % 2 ? couleur : teinte(couleur, 0.8)));
    }
    return faces;
};
function parcelle(x, y, type, etat) {
    const s = 2; // une parcelle « à l'échelle du plan » : 6 × 4,8 m
    const faces = [...pave(x, y, 0, 3 * s, 2.4 * s, 0.12, etat === "projet" || etat === "etude" ? C.terre : C.herbeFonce)];
    const c = ETAT[etat] || C.gris;
    if (type === "pivot") {
        faces.push(...pave(x + 1.4 * s, y + 1.1 * s, 0.12, 0.3, 0.3, 1.6, C.acier), ...pave(x + 0.3 * s, y + 1.15 * s, 1.6, 2.5 * s, 0.25, 0.15, c));
    } else if (type === "enrouleur") {
        faces.push(...pave(x + 0.4 * s, y + 0.9 * s, 0.12, 1.6, 1.4, 1.5, c), ...pave(x + 1.2 * s, y + 1.2 * s, 0.12, 3.2, 0.15, 0.15, C.marine));
    } else if ((type || "").startsWith("goutte") || type === "micro_aspersion") {
        for (let r = 0; r < 5; r++) {
            faces.push(...pave(x + 0.3 * s, y + 0.3 * s + r * 0.9, 0.12, 2.4 * s, 0.1, 0.08, c));
        }
    } else {
        for (let r = 0; r < 3; r++) {
            faces.push(...pave(x + 0.5 * s + r * 1.8, y + 1.0 * s, 0.12, 0.15, 0.15, 1.2, C.acier), ...pave(x + 0.35 * s + r * 1.8, y + 0.85 * s, 1.3, 0.6, 0.6, 0.12, c));
        }
    }
    return faces;
}
const panneau = (x, y, couleur) => [...pave(x + 0.45, y + 0.45, 0, 0.12, 0.12, 2.0, C.acier), ...pave(x, y + 0.4, 2.0, 1.4, 0.12, 0.9, couleur)];
const bureau = (x, y, w = 2.4) => [...pave(x, y, 0, w, 1.0, 0.75, C.bois), ...pave(x + w / 2 - 0.4, y + 0.1, 0.75, 0.8, 0.08, 0.5, C.marine)];
const liasse = (x, y, z, hauteur, couleur) => [...pave(x, y, z, 0.5, 0.4, hauteur, C.papier), ...pave(x + 0.05, y + 0.12, z + hauteur, 0.4, 0.1, 0.02, couleur)];
const pompe = (x, y, couleur) => [...pave(x, y, 0, 1.0, 0.7, 0.55, couleur), ...pave(x + 0.25, y + 0.15, 0.55, 0.5, 0.4, 0.5, C.acier), ...pave(x + 1.0, y + 0.2, 0.2, 0.7, 0.3, 0.3, C.tube)];
const plante = (x, y) => [...pave(x, y, 0, 0.5, 0.5, 0.45, C.terre), ...pave(x + 0.05, y + 0.05, 0.45, 0.4, 0.4, 0.6, C.herbeFonce)];

function sansAccents(texte) {
    return (texte || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}
const nombre = (v) => (v || 0).toLocaleString("fr-FR");

// Les zones du site : où l'on vole quand on les choisit.
const ZONES = [
    { cle: "magasin", nom: "Magasin & comptoir", icone: "fa-shopping-basket", box: [0, 9, 14, 21] },
    { cle: "administratif", nom: "Administratif", icone: "fa-briefcase", box: [0, 0, 14, 9] },
    { cle: "stockage", nom: "Stockage & familles", icone: "fa-cubes", box: [14, 0, 32, 21] },
    { cle: "atelier", nom: "Atelier & SAV", icone: "fa-wrench", box: [32, 0, 48, 21] },
    { cle: "dehors", nom: "Dépôt, cour & parking", icone: "fa-truck", box: [0, 22, 48, 37] },
    { cle: "agriculteurs", nom: "Chez les agriculteurs", icone: "fa-leaf", box: [0, 43, 48, 64] },
];
const TOUT = [-1, -1, 49, 65];

export class VueEnsemble extends Component {
    static template = "cultiveau_vue3d.Vue";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.scene = useRef("scene");
        this.state = useState({
            donnees: null, sols: [], objets: [], libelles: [], postes: [], vue: { x: 0, y: 0, w: 100, h: 60 }, taille: { w: 1200, h: 700 },
            survol: null, carte: null, recherche: "", resultats: [], zone: null,
        });
        onWillStart(async () => {
            await this.charger();
        });
        onMounted(() => {
            this._observateur = new ResizeObserver(() => this.mesurer());
            if (this.scene.el) {
                this._observateur.observe(this.scene.el);
            }
            this.mesurer();
            // l'arrivée : on descend sur le site
            const cible = this.cadrer(TOUT);
            this.state.vue = { x: cible.x - cible.w * 0.25, y: cible.y - cible.h * 0.25, w: cible.w * 1.5, h: cible.h * 1.5 };
            this.voler(cible, 1100);
            this._clavier = (ev) => this.onClavier(ev);
            window.addEventListener("keydown", this._clavier);
        });
        onWillUnmount(() => {
            this._observateur?.disconnect();
            cancelAnimationFrame(this._anim);
            window.removeEventListener("keydown", this._clavier);
        });
    }

    async charger() {
        this.state.donnees = await this.orm.call("cultiveau.scene", "donnees", []);
        this.dispo = new Set(this.state.donnees.actions || []);
        this.construire();
    }

    fiche(modele, id) {
        return { type: "ir.actions.act_window", res_model: modele, res_id: id, views: [[false, "form"]] };
    }

    // ------------------------------------------------------------------ le dessin

    construire() {
        const d = this.state.donnees;
        const k = d.compteurs;
        const sols = [];
        const objets = [];
        const libelles = [];
        const postes = [];
        const court = (texte, n = 22) => (texte && texte.length > n ? texte.slice(0, n - 1) + "…" : texte || "");
        const sol = (cle, x, y, w, dd, couleur, zone = null, z = 0) => sols.push({ cle, faces: pave(x, y, z - 0.02, w, dd, 0.02, couleur), zone });
        const decor = (cle, faces, x, y, classe = "") => objets.push({ cle, faces, prof: x + y, genre: "decor", classe });
        const element = (x, y, faces, infos) => {
            objets.push({ cle: "e" + objets.length, faces, prof: x + y, genre: "element", classe: infos.classe || "", ...infos });
            if (infos.etiquette) {
                libelles.push({ texte: court(infos.etiquette, 18), p: pt(x + 0.5, y + 0.5, infos.haut || 1.8), genre: "objet" });
            }
        };
        const libelle = (texte, x, y, genre = "piece", z = 0) => libelles.push({ texte, p: pt(x, y, z), genre });
        const ok = (cle) => this.dispo.has(cle);
        /** Un poste du plan : un meuble qui ouvre une carte d'actions. */
        const poste = (cle, x, y, faces, infos) => {
            const actions = (infos.actions || []).filter((a) => ok(a.cle));
            if (!actions.length && !infos.info) {
                return;
            }
            const p = { cle, x, y, faces, zone: infos.zone, titre: infos.titre, texte: infos.texte || "", icone: infos.icone || "fa-circle", actions,
                        badge: infos.badge || 0, urgent: !!infos.urgent, mots: infos.mots || "", info: infos.info || "", haut: infos.haut || 2.2,
                        parametre: infos.parametre || null, stats: infos.stats || [], couleur: infos.couleur || C.marine };
            p.ancre = pt(x + (infos.cx || 0.8), y + (infos.cy || 0.5), p.haut);
            postes.push(p);
            objets.push({ cle: "p-" + cle, faces, prof: x + (infos.cx || 0.8) + y + (infos.cy || 0.5), genre: "poste", poste: p, classe: infos.classe || "" });
        };
        const A = (cle, libelle, extra = {}) => ({ cle, libelle, ...extra });

        // ---------------- le terrain, la route, les champs
        sol("terrain", -1, -1, 50, 39, C.sol);
        sol("route", -1, 38, 50, 3.6, C.route);
        sol("bande", -1, 39.75, 50, 0.12, C.blanc);
        sol("champs", -1, 42, 50, 23, C.herbe, "agriculteurs");
        libelle("ROUTE D'ACCÈS", 46, 39.2, "route");
        libelle("ENTRÉE CLIENTS", 7, 37.4, "entree");
        libelle("ENTRÉE POIDS LOURDS", 42, 37.4, "entree");
        // le camion qui passe sur la route (il roule en boucle)
        decor("livreur", camion(-8, 38.5, C.bleu), 60, 0, "roule");

        // ---------------- le bâtiment : dalle, murs, cloisons
        sol("admin", 0, 0, 14, 9, C.admin, "administratif");
        sol("magasin", 0, 9, 14, 12, C.client, "magasin");
        sol("stockage", 14, 0, 18, 21, C.zone, "stockage");
        sol("atelier", 32, 0, 16, 21, C.atelier, "atelier");
        decor("mur-n", pave(-0.2, -0.2, 0, 48.4, 0.2, 2.6, C.blanc), -0.2, -0.2);
        decor("mur-o", pave(-0.2, 0, 0, 0.2, 9, 2.6, C.blanc), -0.2, 0);
        decor("vitrine-o", [...pave(-0.2, 9, 0, 0.2, 12, 0.5, C.blanc), ...pave(-0.2, 9, 0.5, 0.08, 12, 1.8, C.vitre)], -0.2, 9);
        decor("vitrine-s", [...pave(0, 21, 0, 5.5, 0.2, 0.5, C.blanc), ...pave(0, 21, 0.5, 5.5, 0.08, 1.2, C.vitre), ...pave(8.5, 21, 0, 5.5, 0.2, 0.5, C.blanc), ...pave(8.5, 21, 0.5, 5.5, 0.08, 1.2, C.vitre)], 7, 21);
        decor("facade-s", [...pave(14, 21, 0, 25, 0.2, 0.5, C.blanc), ...pave(45, 21, 0, 3, 0.2, 0.5, C.blanc)], 30, 21);
        decor("mur-e", pave(48, 0, 0, 0.2, 21.2, 0.5, C.blanc), 48, 10);
        decor("cloison-1", [...pave(14, 0, 0, 0.15, 13, 0.45, C.gris), ...pave(14, 16, 0, 0.15, 5, 0.45, C.gris)], 14, 8);
        decor("cloison-2", [...pave(32, 0, 0, 0.15, 8, 0.45, C.gris), ...pave(32, 11, 0, 0.15, 10, 0.45, C.gris)], 32, 8);
        decor("cloison-3", [...pave(0, 9, 0, 6, 0.15, 0.45, C.gris), ...pave(9, 9, 0, 5, 0.15, 0.45, C.gris)], 4, 9);
        libelle("ADMINISTRATIF", 7, 0.6, "zone");
        libelle("MAGASIN", 3.4, 9.7, "zone");
        libelle("STOCKAGE", 23, 0.6, "zone");
        libelle("ATELIER", 40, 0.6, "zone");

        // ---------------- l'administratif
        poste("facturation", 1, 1.2, [...bureau(1, 1.2), ...personnage(1.9, 2.4, C.bleu)], {
            zone: "administratif", titre: "Facturation", icone: "fa-file-text-o", badge: k.factures, urgent: d.caisse.some((f) => f.en_retard),
            texte: "Faire une facture, suivre ce qui reste à encaisser, les avoirs.",
            stats: [`${nombre(k.factures)} facture(s) à encaisser`, `${nombre(k.factures_montant)} € restant dû`],
            actions: [A("facture_nouvelle", "Faire une facture", { principal: true, icone: "fa-plus" }), A("factures_a_encaisser", "Factures à encaisser", { badge: k.factures }),
                      A("factures", "Toutes les factures"), A("avoirs", "Avoirs")],
            mots: "facture facturer facturation avoir encaisser impaye relance client paiement",
        });
        d.caisse.forEach((f, i) => {
            const x = 1.15 + (i % 4) * 0.55, y = 1.25;
            const h = 0.08 + Math.min(0.5, f.montant / 20000) + Math.floor(i / 4) * 0.1;
            element(x, y, liasse(x, y, 0.75, h, f.en_retard ? C.rouge : C.vert), { titre: `Facture ${f.nom} — ${f.client} — ${nombre(f.montant)} € restant${f.echeance ? " — échéance " + f.echeance : ""}${f.en_retard ? " (en retard)" : ""}`,
                                                                                  action: this.fiche("account.move", f.id), haut: 1.3, classe: f.en_retard ? "alerte" : "" });
        });
        poste("compta", 5, 1.2, [...bureau(5, 1.2), ...personnage(5.9, 2.4, C.marine)], {
            zone: "administratif", titre: "Comptabilité", icone: "fa-calculator",
            texte: "Les fournisseurs à payer, les paiements, les journaux et la banque.",
            actions: [A("a_payer", "Fournisseurs à payer", { principal: true }), A("factures_fournisseurs", "Factures fournisseurs"), A("paiements", "Paiements"),
                      A("journaux", "Journaux et banque"), A("ecritures", "Écritures")],
            mots: "compta comptabilite banque paiement journal fournisseur payer tva ecriture",
        });
        poste("etude", 9.2, 1, [...pave(9.2, 1, 0, 3.8, 2.2, 0.75, C.bois), ...personnage(10, 3.4, C.carton), ...personnage(12, 3.4, C.bleu)], {
            zone: "administratif", titre: "Bureau d'étude", icone: "fa-pencil-square-o", badge: d.bureau.etudes.length, cx: 1.9, cy: 1.1,
            texte: "Analyse des besoins, dimensionnement, tracé du réseau en 3D.",
            actions: [A("etude_nouvelle", "Nouvelle étude", { principal: true, icone: "fa-plus" }), A("etudes", "Études en cours", { badge: d.bureau.etudes.length }),
                      A("schema3d", "Cultiveau 3D : tracer le réseau", { icone: "fa-cube" }), A("usages", "Simulations à l'usage"), A("installations", "Toutes les installations")],
            mots: "etude dimensionnement plan reseau 3d schema cultiveau 3d trace installation besoins",
        });
        d.bureau.etudes.forEach((e, i) => {
            const x = 9.4 + (i % 3) * 1.2, y = 1.2 + Math.floor(i / 3) * 0.8;
            element(x, y, [...pave(x, y, 0.75, 1.0, 0.6, 0.05, e.etat === "etude" ? C.carton : C.gris), ...pave(x + 0.1, y + 0.1, 0.8, 0.8, 0.4, 0.02, C.papier)],
                    { titre: `Étude : ${e.nom} — ${e.client} — ${e.type_libelle}${e.surface ? " — " + e.surface + " ha" : ""}${e.analyse_validee ? " — analyse validée" : " — analyse des besoins à valider"}`,
                      etiquette: e.client, action: this.fiche("cultiveau.installation", e.id), haut: 1.2 });
        });
        const chaises = [];
        for (let c = 0; c < 3; c++) {
            chaises.push(...pave(1.6 + c * 1.6, 4.4, 0, 0.5, 0.5, 0.45, C.marine), ...pave(1.6 + c * 1.6, 7.4, 0, 0.5, 0.5, 0.45, C.marine));
        }
        poste("reunion", 1.2, 5.1, [...chaises, ...pave(1.2, 5.1, 0, 5.2, 2.0, 0.75, C.bois)], {
            zone: "administratif", titre: "Salle de réunion", icone: "fa-handshake-o", badge: k.devis, cx: 2.6, cy: 1,
            texte: "Les devis avec l'agriculteur, les demandes en cours, les rendez-vous.",
            stats: [`${nombre(k.devis)} devis en cours — ${nombre(k.devis_montant)} €`],
            actions: [A("devis_nouveau", "Faire un devis", { principal: true, icone: "fa-plus" }), A("devis", "Devis en cours", { badge: k.devis }),
                      A("pipeline", "Demandes et opportunités", { badge: d.accueil.opportunites.length }), A("commandes", "Commandes"), A("rendez_vous", "Rendez-vous")],
            mots: "devis chiffrage reunion opportunite demande rendez vous rdv commande vente pipeline",
        });
        d.bureau.devis.forEach((v, i) => {
            const x = 1.4 + (i % 6) * 0.8, y = 5.3 + Math.floor(i / 6) * 0.9;
            element(x, y, liasse(x, y, 0.75, 0.1 + Math.min(0.5, v.montant / 50000), v.etat === "sent" ? C.bleu : C.gris),
                    { titre: `Devis ${v.nom} — ${v.client} — ${v.installation} — ${nombre(v.montant)} €${v.etat === "sent" ? " (envoyé)" : " (brouillon)"}`, action: this.fiche("sale.order", v.id), haut: 1.3 });
        });
        poste("direction", 9.5, 5.4, [...bureau(9.5, 5.4, 3), ...personnage(10.8, 6.6, C.vert), ...plante(12.8, 7.8)], {
            zone: "administratif", titre: "Direction", icone: "fa-line-chart",
            texte: "Les chiffres de l'entreprise, l'équipe, les réglages du réseau.",
            actions: [A("ventes_analyse", "Chiffre d'affaires", { principal: true }), A("achats_analyse", "Achats"), A("crm_analyse", "Demandes et signatures"),
                      A("utilisateurs", "L'équipe"), A("reglages", "Réglages Cultiveau"), A("import_reseau", "Importer le réseau")],
            mots: "direction tableau de bord chiffre affaires statistiques analyse equipe utilisateurs reglages parametres reseau",
        });

        // ---------------- le magasin : la vitrine du réseau
        const familles = d.familles || [];
        const petites = /raccord|goutte|asperseur|micro|fixation|consommable|collier|buse|arrosage|jardin|automat|programm/i;
        const exterieur = /tuyau|tube|pvc|\bpe\b|poly|gaine|canalisation/i;
        const dehors = familles.filter((f) => exterieur.test(f.nom)).slice(0, 2);
        const libreService = familles.filter((f) => !dehors.includes(f) && petites.test(f.nom)).slice(0, 4);
        const restantes = familles.filter((f) => !dehors.includes(f) && !libreService.includes(f));
        while (libreService.length < 4 && restantes.length > 12) {
            libreService.push(restantes.shift());
        }
        const posteFamille = (f, i, x, y, faces, zone, extra = {}) => poste("famille-" + f.id, x, y, faces, {
            zone, titre: f.nom, icone: "fa-th-large", badge: f.mien, parametre: f.id, couleur: TEINTES_FAMILLES[i % TEINTES_FAMILLES.length], haut: extra.haut || 3.2, cx: extra.cx || 1.8,
            texte: "Une famille de produits : mes articles, le stock, le catalogue Cultiveau et les fiches techniques.",
            stats: [`${nombre(f.mien)} dans mon catalogue`, `${nombre(f.reseau)} au catalogue Cultiveau`, `${nombre(f.stock)} en stock`],
            actions: [A("famille_mien", "Mes articles", { principal: true, badge: f.mien }), A("famille_stock", "En stock", { badge: f.stock }),
                      A("famille_reseau", "Catalogue Cultiveau", { badge: f.reseau }), A("famille_fiches", "Fiches techniques", { icone: "fa-file-pdf-o" })],
            mots: "famille rayon produit article " + f.nom,
        });
        libreService.forEach((f, i) => {
            const y = 11 + i * 2.3;
            posteFamille(f, i, 1.2, y, gondole(1.2, y, TEINTES_FAMILLES[i % TEINTES_FAMILLES.length], Math.min(5, Math.ceil(Math.log10(f.mien + f.stock + 1) * 2))), "magasin",
                         { haut: 2.0, cx: 2.1 });
        });
        libelle("libre-service", 3.3, 20.3);
        poste("comptoir", 10.6, 11, [...pave(10.6, 11, 0, 1.0, 6.5, 1.05, C.marine), ...pave(10.7, 12, 1.05, 0.7, 0.5, 0.35, C.acier), ...personnage(12.1, 13.5, C.bleu)], {
            zone: "magasin", titre: "Comptoir", icone: "fa-barcode", badge: d.accueil.comptoir.length, cy: 3, haut: 2.4,
            texte: "La vente au magasin : on scanne, on encaisse, le ticket sort.",
            actions: [A("comptoir", "Ouvrir le comptoir", { principal: true, icone: "fa-barcode" }), A("ventes_comptoir", "Ventes au comptoir"),
                      A("agriculteurs", "Les agriculteurs")],
            mots: "comptoir vente caisse scan douchette ticket encaisser magasin",
        });
        d.accueil.opportunites.forEach((o, i) => {
            const x = 8.6 - Math.floor(i / 5) * 1.0, y = 11.6 + (i % 5) * 1.2;
            element(x, y, personnage(x, y, C.carton), { titre: `Demande : ${o.nom} — ${o.client} — ${o.etape}${o.montant ? " — " + nombre(o.montant) + " €" : ""}`,
                                                       etiquette: o.client || o.nom, action: this.fiche("crm.lead", o.id), classe: "personne" });
        });
        d.accueil.comptoir.forEach((v, i) => {
            const x = 10.65 + (i % 2) * 0.45, y = 14.6 + Math.floor(i / 2) * 0.55;
            element(x, y, pave(x, y, 1.05, 0.4, 0.4, 0.35, C.carton), { titre: `Vente comptoir ${v.nom} — ${v.client} — ${nombre(v.montant)} €`, action: this.fiche("sale.order", v.id), haut: 1.6 });
        });
        poste("conseil", 7.6, 18.4, [...pave(7.6, 18.4, 0, 2.4, 1.2, 0.75, C.bois), ...pave(7.9, 18.5, 0.75, 1.8, 0.12, 1.1, C.marine), ...pave(8.0, 18.48, 0.85, 1.6, 0.05, 0.9, C.eau),
                                    ...pave(10.4, 18.6, 0, 0.5, 0.5, 0.45, C.marine)], {
            zone: "magasin", titre: "Coin conseil", icone: "fa-desktop", badge: k.fiches, cx: 1.2, cy: 0.6, haut: 2.2,
            texte: "Avec l'agriculteur : les fiches techniques, le catalogue, le réseau en 3D.",
            actions: [A("fiches", "Fiches techniques", { principal: true, icone: "fa-file-pdf-o", badge: k.fiches }), A("schema3d", "Cultiveau 3D", { icone: "fa-cube" }),
                      A("catalogue", "Catalogue Cultiveau", { badge: k.catalogue }), A("mon_catalogue", "Mon catalogue", { badge: k.mon_catalogue }), A("rendez_vous", "Prendre rendez-vous")],
            mots: "fiche technique fiches techniques documentation notice pdf conseil catalogue 3d cultiveau 3d schema bibliotheque",
        });
        decor("enseigne", panneau(-1, 21.6, C.bleu), -1, 21.6);
        decor("plante-m", plante(0.4, 20.2), 0.4, 20.2);

        // ---------------- le stockage : une famille par rack, la zone de préparation
        const racks = restantes.slice(0, 11);
        racks.forEach((f, i) => {
            const x = 15 + (i % 4) * 4.2, y = 1.6 + Math.floor(i / 4) * 4.0;
            const remplissage = Math.min(9, Math.max(1, Math.ceil(Math.log10(f.stock + f.mien + 1) * 2.5)));
            posteFamille(f, i + 4, x, y, rack(x, y, remplissage, TEINTES_FAMILLES[(i + 4) % TEINTES_FAMILLES.length]), "stockage");
        });
        if (restantes.length > 11 || ok("categories")) {
            const x = 15 + (11 % 4) * 4.2, y = 1.6 + 2 * 4.0;
            poste("toutes-familles", x, y, rack(x, y, 3, C.gris), {
                zone: "stockage", titre: restantes.length > 11 ? `+ ${restantes.length - 11} autres familles` : "Toutes les familles", icone: "fa-sitemap", haut: 3.2, cx: 1.8,
                texte: "Toutes les familles et sous-familles de produits.",
                actions: [A("mon_catalogue", "Mon catalogue", { principal: true }), A("catalogue", "Catalogue Cultiveau"), A("categories", "Les familles"),
                          A("import_articles", "Importer mes articles"), A("fournisseurs", "Fournisseurs")],
                mots: "familles categories catalogue articles importer fournisseurs",
            });
        }
        sol("prepa", 15, 14, 16, 6, teinte(C.zone, 0.94), null, 0.01);
        poste("preparation", 15.4, 14.4, [...pave(15.4, 14.4, 0, 3, 1.2, 0.85, C.bois), ...pave(28.5, 17.5, 0, 1.4, 1.0, 0.6, C.carton), ...pave(28.5, 17.5, 0.6, 0.5, 1.0, 1.2, C.marine)], {
            zone: "stockage", titre: "Préparation · expéditions", icone: "fa-dropbox", badge: d.cour.preparations.length, cx: 1.5,
            texte: "Les commandes à préparer pour les clients et les chantiers, les réceptions, l'inventaire.",
            actions: [A("livraisons", "À préparer et livrer", { principal: true, badge: d.cour.preparations.length }), A("receptions", "Réceptions"),
                      A("inventaire", "Inventaire"), A("reappro", "Réapprovisionnement"), A("mouvements", "Mouvements de stock")],
            mots: "preparation livraison expedition stock inventaire reception reapprovisionnement mouvement picking bon",
        });
        libelle("préparation commandes · chantiers", 23, 20.5);
        d.cour.preparations.forEach((p, i) => {
            const x = 19 + (i % 6) * 1.5, y = 15 + Math.floor(i / 6) * 1.6;
            element(x, y, pave(x, y, 0, 1.0, 1.0, 0.9, C.carton), { titre: `À préparer : ${p.nom} — ${p.client}${p.date ? " — " + p.date : ""}`, etiquette: p.client, action: this.fiche("stock.picking", p.id), haut: 1.3 });
        });

        // ---------------- l'atelier
        const atelier = d.atelier || [];
        const depannages = atelier.filter((t) => t.nature === "depannage" || t.urgence === "immediate" || t.urgence === "journee");
        const etabli = atelier.filter((t) => !depannages.includes(t));
        poste("banc", 33, 1.2, [...pave(33, 1.2, 0, 5, 1.8, 0.7, C.acier), ...pave(33.2, 1.4, 0.7, 4.6, 1.4, 0.25, C.eau)], {
            zone: "atelier", titre: "Banc d'essai pompes", icone: "fa-tachometer", badge: etabli.length, cx: 2.5, cy: 0.9,
            texte: "Entretiens, diagnostics et révisions : ce qui est sur le banc.",
            actions: [A("entretiens", "Entretiens en cours", { principal: true, badge: etabli.length }), A("equipements_a_renouveler", "Équipements à renouveler"), A("registre", "Registre de maintenance")],
            mots: "banc pompe entretien diagnostic revision equipement renouveler registre maintenance",
        });
        etabli.slice(0, 4).forEach((t, i) => {
            const x = 33.3 + i * 1.15, y = 1.5;
            element(x, y, pompe(x, y, URGENCE[t.urgence] || C.bleu).map((f) => f), { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.installation ? " — " + t.installation : ""}`, action: this.fiche("project.task", t.id), haut: 2.0 });
        });
        decor("elec", [...pave(44.5, 0.8, 0, 3, 2.2, 2.2, C.gris), ...pave(44.6, 3.0, 0.4, 0.9, 0.05, 1.4, C.marine), ...pave(45.8, 3.0, 0.4, 0.9, 0.05, 1.4, C.marine)], 44.5, 0.8);
        libelle("local élec.", 46, 3.6);
        decor("soudure", [...pave(33, 5, 0, 3.2, 1.2, 0.85, C.bois), ...pave(34, 5.3, 0.85, 1.4, 0.5, 0.4, C.tube)], 33, 5);
        decor("etincelles", [...pave(34.4, 5.4, 1.35, 0.15, 0.15, 0.15, C.orange), ...pave(34.8, 5.6, 1.5, 0.1, 0.1, 0.1, C.carton)], 34.6, 5.5, "etincelle");
        libelle("soudure PE", 34.6, 6.9);
        poste("prefa", 38, 4.5, [...pave(38, 4.5, 0, 5, 3, 0.1, C.gris), ...pave(38.4, 5, 0.1, 4.2, 0.4, 0.4, C.bleu), ...pave(38.4, 6.4, 0.1, 4.2, 0.4, 0.4, C.bleu),
                                 ...pave(39.6, 5.0, 0.5, 1.0, 1.8, 0.9, C.marine), ...pave(41.2, 5.6, 0.5, 0.4, 0.4, 0.8, C.rouge)], {
            zone: "atelier", titre: "Préfabrication des stations", icone: "fa-cogs", badge: k.chantiers || 0, cx: 2.5, cy: 1.5,
            texte: "On assemble les stations de tête à l'atelier, on les pose sur le chantier.",
            actions: [A("chantiers", "Chantiers à préparer", { principal: true, badge: k.chantiers || 0 }), A("planning", "Planning des équipes"), A("chantier_nouveau", "Nouveau chantier")],
            mots: "prefabrication station tete chantier pose planning equipe",
        });
        decor("pont", [...pave(32.6, 9.5, 0, 0.2, 0.2, 3.4, C.acier), ...pave(47.4, 9.5, 0, 0.2, 0.2, 3.4, C.acier), ...pave(32.6, 9.5, 3.4, 15, 0.3, 0.25, C.carton)], 40, 9.5);
        sol("sav", 33, 11.5, 14, 8.5, teinte(C.atelier, 0.95), null, 0.01);
        poste("sav", 33.4, 11.8, [...panneau(33.4, 11.8, C.rouge)], {
            zone: "atelier", titre: "SAV · enrouleurs et pivots", icone: "fa-wrench", badge: depannages.length, urgent: depannages.some((t) => t.urgence === "immediate"), cx: 0.6,
            texte: "Les pannes et les dépannages : enrouleurs, pivots, pompes en saison.",
            actions: [A("depannage_nouveau", "Nouveau dépannage", { principal: true, icone: "fa-plus" }), A("depannages", "Dépannages en cours", { badge: depannages.length }),
                      A("interventions", "Toutes les interventions"), A("registre", "Registre de maintenance")],
            mots: "sav depannage panne intervention enrouleur pivot reparation urgence technicien",
        });
        depannages.slice(0, 6).forEach((t, i) => {
            const x = 36 + (i % 3) * 3.6, y = 12.5 + Math.floor(i / 3) * 3.6;
            const faces = [...pave(x, y, 0, 2.0, 1.6, 1.5, URGENCE[t.urgence] || C.bleu), ...pave(x + 2.0, y + 0.6, 0, 1.2, 0.15, 0.15, C.marine), ...pave(x - 0.1, y - 0.1, 1.5, 2.2, 1.8, 0.06, C.acier)];
            element(x, y, faces, { titre: `${t.nature_libelle} ${t.urgence_libelle || ""} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.installation ? " — " + t.installation : ""}`,
                                   etiquette: t.client || t.nom, action: this.fiche("project.task", t.id), classe: t.urgence === "immediate" ? "alerte" : "" });
        });
        libelle("grande porte 5 × 5 m", 42.5, 21.6);

        // ---------------- dehors : parking, dépôt, cour
        sol("parking", 0, 23, 14, 13, "#dfe9e4", "dehors");
        for (let p = 0; p < 6; p++) {
            sol("place" + p, 0.5 + p * 2.2, 23.5, 0.08, 4.5, C.blanc, null, 0.01);
            sol("place-b" + p, 0.5 + p * 2.2, 30.5, 0.08, 4.5, C.blanc, null, 0.01);
        }
        sol("pmr", 0.6, 24, 2.0, 3.8, C.bleu, null, 0.02);
        libelle("PARKING CLIENTS", 7, 29.3, "zone");
        poste("agriculteurs", 4.5, 31, [...camion(4.5, 31, C.vert), ...personnage(9.5, 32, C.carton)], {
            zone: "dehors", titre: "Les agriculteurs", icone: "fa-users", badge: k.agriculteurs, cx: 2.5, cy: 1, haut: 2.6,
            texte: "Vos clients : leurs cultures, leur profil, ceux à appeler ce mois-ci.",
            actions: [A("agriculteurs", "Les agriculteurs", { principal: true, badge: k.agriculteurs }), A("agriculteur_nouveau", "Nouvel agriculteur", { icone: "fa-plus" }),
                      A("a_contacter", "À contacter ce mois-ci", { badge: k.a_contacter }), A("cultures", "Cultures et frise"), A("personas", "Profils"), A("import_clients", "Importer mes clients")],
            mots: "agriculteur client contact exploitant culture frise profil persona appeler importer clients",
        });
        sol("depot", 16, 23, 18, 13, C.zone, "dehors");
        libelle("DÉPÔT EXTÉRIEUR", 25, 23.3, "zone");
        decor("auvent", [...[16.2, 24.9, 33.6].flatMap((x) => [...pave(x, 23.8, 0, 0.2, 0.2, 3.2, C.acier), ...pave(x, 27.6, 0, 0.2, 0.2, 3.2, C.acier)]), ...pave(16, 23.6, 3.2, 18, 4.4, 0.15, C.toit)], 25, 23.6, "toit");
        dehors.forEach((f, i) => {
            const x = 16.6 + i * 8.6, y = 24.6;
            posteFamille(f, i + 2, x, y, cantilever(x, y, 8, i ? C.tube : C.bleu), "dehors", { haut: 2.6, cx: 4 });
        });
        if (!dehors.length) {
            decor("cantilever", cantilever(16.6, 24.6, 16.6, C.bleu), 16.6, 24.6);
        }
        decor("bobines", bobines(17, 29.5), 17, 29.5);
        libelle("bobines PE", 20, 31.8);
        poste("occasion", 26, 29.5, [...pave(26, 29.5, 0, 2.2, 1.8, 1.6, C.terre), ...pave(28.2, 30.2, 0, 2.8, 0.2, 0.2, C.marine), ...pompe(30.4, 29.8, C.gris)], {
            zone: "dehors", titre: "Occasion · reprises", icone: "fa-recycle", cx: 2.5, cy: 1,
            texte: "Le matériel repris ou d'occasion : enrouleurs, travées, pompes à réviser.",
            actions: [A("occasion", "Le matériel d'occasion", { principal: true })], mots: "occasion reprise seconde main enrouleur travee pompe",
        });
        decor("bennes", [0, 1, 2].flatMap((b) => pave(17 + b * 2.0, 33.4, 0, 1.6, 1.2, 0.9, [C.vert, C.carton, C.acier][b])), 19, 33.4);
        libelle("bennes de tri · recyclage du plastique agricole", 22, 35.3);
        sol("cour", 36, 23, 12, 13, "#d9d3c6", "dehors");
        libelle("COUR POIDS LOURDS", 42, 23.3, "zone");
        poste("quai", 36.6, 24, pave(36.6, 24, 0, 2.2, 10, 1.1, C.gris), {
            zone: "dehors", titre: "Quai de réception", icone: "fa-truck", badge: d.cour.receptions.length, cx: 1.1, cy: 5, haut: 1.8,
            texte: "Les camions des fournisseurs : commandes attendues, réceptions, achats.",
            actions: [A("achat_nouveau", "Commander à un fournisseur", { principal: true, icone: "fa-plus" }), A("receptions", "Réceptions attendues", { badge: d.cour.receptions.length }),
                      A("achats", "Commandes fournisseurs"), A("demandes_prix", "Demandes de prix"), A("fournisseurs", "Fournisseurs")],
            mots: "quai reception fournisseur achat commande camion livraison demande de prix approvisionnement",
        });
        d.cour.receptions.slice(0, 3).forEach((a, i) => {
            const x = 39, y = 24 + i * 3.2;
            element(x, y, poidsLourd(x, y), { titre: `Réception attendue : ${a.nom} — ${a.fournisseur} — ${nombre(a.montant)} €${a.date ? " — " + a.date : ""}`,
                                               etiquette: a.fournisseur, action: this.fiche("purchase.order", a.id), haut: 3.6 });
        });
        decor("lavage", [...pave(43, 33, 0, 4, 2.4, 0.04, C.eau), ...pave(43.1, 33.1, 0, 0.15, 0.15, 2.2, C.acier)], 43, 33, "eau");
        libelle("aire de lavage", 45, 35.8);

        // ---------------- chez les agriculteurs, de l'autre côté de la route
        libelle("CHEZ LES AGRICULTEURS", 24, 43, "zone");
        const poses = [
            ...(d.chantiers.chantiers || []).map((c) => ({ ...c, modele: "cultiveau.chantier" })),
            ...d.chantiers.installations.map((c) => ({ ...c, modele: "cultiveau.installation", etat: "en_cours", equipe: 1, avancement: 0 })),
        ];
        poste("chantiers", 1, 44, panneau(1, 44, C.orange), {
            zone: "agriculteurs", titre: "Chantiers", icone: "fa-road", badge: poses.length, cx: 0.7, haut: 3,
            texte: "Les équipes de pose : planning, matériel sorti du magasin, PV de mise en service.",
            actions: [A("chantier_nouveau", "Nouveau chantier", { principal: true, icone: "fa-plus" }), A("planning", "Planning des équipes"), A("chantiers", "Tous les chantiers", { badge: poses.length })],
            mots: "chantier pose equipe planning mise en service pv travaux",
        });
        poses.slice(0, 6).forEach((c, i) => {
            const x = 3 + (i % 2) * 9, y = 46 + Math.floor(i / 2) * 6;
            const couleur = c.etat === "planifie" ? C.bleu : C.orange;
            const faces = [...parcelle(x, y, c.type, "realisation")];
            if (c.etat !== "planifie") {
                faces.push(...pave(x + 0.4, y + 0.4, 0.12, 2.0, 1.4, 1.1, couleur), ...pave(x + 2.4, y + 0.8, 0.12, 1.0, 0.3, 0.3, C.marine));
            }
            for (let n = 0; n < Math.min(3, 1 + (c.equipe || 0)); n++) {
                faces.push(...personnage(x + 3.4 + (n % 2) * 0.9, y + 0.6 + n * 1.1, couleur));
            }
            const detail = c.modele === "cultiveau.chantier"
                ? `${c.etat === "planifie" ? "Chantier planifié" : "Chantier en cours"} : ${c.titre} — ${c.client}${c.chef ? " — " + c.chef : ""}${c.debut ? " — du " + c.debut + (c.fin ? " au " + c.fin : "") : ""} — ${c.avancement} %`
                : `Chantier : ${c.nom} — ${c.client} — ${c.type_libelle}${c.surface ? " — " + c.surface + " ha" : ""}`;
            element(x, y, faces, { titre: detail, etiquette: c.client, action: this.fiche(c.modele, c.id) });
        });
        (d.chantiers.taches || []).slice(0, 3).forEach((t, i) => {
            const x = 2 + i * 7, y = 38.6;
            element(x, y, camion(x, y, URGENCE[t.urgence] || C.bleu), { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.date ? " — " + t.date : ""}`,
                                                                        etiquette: t.client || t.nom, action: this.fiche("project.task", t.id), haut: 3 });
        });
        poste("parc", 25, 44, panneau(25, 44, C.herbeFonce), {
            zone: "agriculteurs", titre: "Parc installé", icone: "fa-tint", badge: d.parcelles.length, cx: 0.7, haut: 3,
            texte: "Les installations en service, leur registre, ce que la saison demande.",
            actions: [A("parc", "Installations en service", { principal: true }), A("equipements_a_renouveler", "Équipements à renouveler"),
                      A("registre", "Registre de maintenance"), A("installations", "Toutes les installations")],
            mots: "parc installation parcelle service hivernage remise en route registre equipement irrigation",
        });
        d.parcelles.slice(0, 8).forEach((p, i) => {
            const x = 27 + (i % 3) * 7, y = 46 + Math.floor(i / 3) * 6;
            const faces = parcelle(x, y, p.type, p.etat);
            if (p.echeance) {
                faces.push(...panneau(x + 4.2, y + 0.2, C.orange));
            }
            element(x, y, faces, { titre: `${p.nom} — ${p.client} — ${p.type_libelle} — ${p.etat_libelle}${p.surface ? " — " + p.surface + " ha" : ""}${p.commune ? " — " + p.commune : ""}${p.echeance ? " — " + p.echeance : ""}`,
                                   etiquette: p.client, action: this.fiche("cultiveau.installation", p.id), classe: p.echeance ? "alerte" : "" });
        });

        objets.sort((a, b) => a.prof - b.prof);
        this.state.sols = sols;
        this.state.objets = objets;
        this.state.libelles = libelles;
        this.state.postes = postes;
    }

    // ------------------------------------------------------------------ la caméra

    mesurer() {
        const el = this.scene.el;
        if (!el) {
            return;
        }
        const r = el.getBoundingClientRect();
        if (r.width && r.height) {
            const ancien = this.state.taille;
            this.state.taille = { w: r.width, h: r.height };
            const v = this.state.vue;
            // garder le même centre et la même échelle
            const s = ancien.w / v.w;
            const cx = v.x + v.w / 2, cy = v.y + v.h / 2;
            const w = r.width / s, h = r.height / s;
            this.state.vue = { x: cx - w / 2, y: cy - h / 2, w, h };
        }
    }

    get viewBox() {
        const v = this.state.vue;
        return `${v.x.toFixed(1)} ${v.y.toFixed(1)} ${v.w.toFixed(1)} ${v.h.toFixed(1)}`;
    }

    get echelle() {
        return this.state.taille.w / this.state.vue.w;
    }

    get classeScene() {
        const e = this.echelle;
        return e > 1.15 ? "proche" : e > 0.75 ? "moyen" : "loin";
    }

    /** La vue qui montre la boîte [x0, y0, x1, y1] (en mètres), au format du cadre. */
    cadrer(box, marge = 50) {
        const [x0, y0, x1, y1] = box;
        const coins = [pt(x0, y0, 0), pt(x1, y0, 0), pt(x1, y1, 0), pt(x0, y1, 0), pt(x0, y0, 3.5), pt(x1, y0, 3.5)];
        const xs = coins.map((c) => c[0]), ys = coins.map((c) => c[1]);
        let w = Math.max(...xs) - Math.min(...xs) + marge * 2, h = Math.max(...ys) - Math.min(...ys) + marge * 2;
        const ratio = this.state.taille.h / this.state.taille.w;
        if (h / w > ratio) {
            w = h / ratio;
        } else {
            h = w * ratio;
        }
        const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
        return { x: cx - w / 2, y: cy - h / 2, w, h };
    }

    voler(cible, duree = 750) {
        cancelAnimationFrame(this._anim);
        const de = { ...this.state.vue };
        const t0 = performance.now();
        const pas = (t) => {
            const k = Math.min(1, (t - t0) / duree);
            const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
            this.state.vue = { x: de.x + (cible.x - de.x) * e, y: de.y + (cible.y - de.y) * e, w: de.w + (cible.w - de.w) * e, h: de.h + (cible.h - de.h) * e };
            if (k < 1) {
                this._anim = requestAnimationFrame(pas);
            }
        };
        this._anim = requestAnimationFrame(pas);
    }

    allerZone(zone) {
        this.state.carte = null;
        this.state.zone = zone.cle;
        this.voler(this.cadrer(zone.box, 30));
    }

    toutVoir() {
        this.state.carte = null;
        this.state.zone = null;
        this.voler(this.cadrer(TOUT));
    }

    zoomer(facteur, cx = null, cy = null) {
        const v = this.state.vue;
        const nw = Math.min(6000, Math.max(250, v.w * facteur));
        const f = nw / v.w;
        const px = cx ?? v.x + v.w / 2, py = cy ?? v.y + v.h / 2;
        this.state.vue = { x: px - (px - v.x) * f, y: py - (py - v.y) * f, w: v.w * f, h: v.h * f };
    }

    pointDessin(ev) {
        const r = this.scene.el.getBoundingClientRect();
        const v = this.state.vue;
        return [v.x + ((ev.clientX - r.left) / r.width) * v.w, v.y + ((ev.clientY - r.top) / r.height) * v.h];
    }

    onMolette(ev) {
        ev.preventDefault();
        cancelAnimationFrame(this._anim);
        const [px, py] = this.pointDessin(ev);
        this.zoomer(Math.exp(ev.deltaY * 0.0012), px, py);
    }

    onAppui(ev) {
        if (ev.button !== 0 || ev.target.closest?.(".o_cv_carte")) {
            return;
        }
        cancelAnimationFrame(this._anim);
        this._glisse = { x: ev.clientX, y: ev.clientY, vue: { ...this.state.vue }, bouge: false };
    }

    onDeplacement(ev) {
        const g = this._glisse;
        if (!g) {
            return;
        }
        const dx = ev.clientX - g.x, dy = ev.clientY - g.y;
        if (!g.bouge && Math.hypot(dx, dy) < 5) {
            return;
        }
        g.bouge = true;
        const s = this.state.taille.w / g.vue.w;
        this.state.vue = { ...g.vue, x: g.vue.x - dx / s, y: g.vue.y - dy / s };
    }

    onRelache() {
        if (this._glisse) {
            this._apresGlisse = this._glisse.bouge;
            this._glisse = null;
            setTimeout(() => (this._apresGlisse = false), 0);
        }
    }

    onClavier(ev) {
        if (ev.target.closest?.("input, textarea")) {
            if (ev.key === "Escape") {
                this.state.recherche = "";
                this.state.resultats = [];
            }
            return;
        }
        if (ev.key === "Escape") {
            this.state.carte = null;
        } else if (ev.key === "+" || ev.key === "=") {
            this.zoomer(0.8);
        } else if (ev.key === "-") {
            this.zoomer(1.25);
        } else if (ev.key === "0") {
            this.toutVoir();
        }
    }

    // ------------------------------------------------------------------ cliquer

    clicObjet(o) {
        if (this._apresGlisse) {
            return;
        }
        if (o.genre === "poste") {
            this.ouvrirPoste(o.poste);
        } else if (o.genre === "element" && o.action) {
            this.action.doAction(o.action);
        }
    }

    clicSol(s) {
        if (this._apresGlisse || !s.zone) {
            return;
        }
        this.allerZone(ZONES.find((z) => z.cle === s.zone));
    }

    clicFond() {
        if (!this._apresGlisse) {
            this.state.carte = null;
        }
    }

    ouvrirPoste(p, voler = true) {
        this.state.carte = p;
        this.state.recherche = "";
        this.state.resultats = [];
        if (voler) {
            // on s'approche du poste, en le gardant un peu à gauche pour laisser la place à la carte
            const v = this.state.vue;
            const w = Math.min(v.w, 1100), h = w * (this.state.taille.h / this.state.taille.w);
            this.voler({ x: p.ancre[0] - w * 0.38, y: p.ancre[1] - h * 0.45, w, h }, 650);
        }
    }

    get positionCarte() {
        const p = this.state.carte;
        if (!p) {
            return "";
        }
        const v = this.state.vue, t = this.state.taille;
        const sx = ((p.ancre[0] - v.x) / v.w) * t.w, sy = ((p.ancre[1] - v.y) / v.h) * t.h;
        const largeur = 320;
        let left = sx + 28;
        if (left + largeur > t.w - 12) {
            left = Math.max(12, sx - largeur - 28);
        }
        const top = Math.max(12, Math.min(t.h - 360, sy - 60));
        return `left:${left}px; top:${top}px; width:${largeur}px;`;
    }

    async lancer(a) {
        const p = this.state.carte;
        try {
            const action = await this.orm.call("cultiveau.scene", "action", [a.cle, p && p.parametre]);
            this.state.carte = null;
            await this.action.doAction(action);
        } catch (e) {
            this.notification.add(e.data?.message || e.message || String(e), { type: "danger" });
        }
    }

    // ------------------------------------------------------------------ « Où aller ? »

    chercher() {
        const q = sansAccents(this.state.recherche).trim();
        if (q.length < 2) {
            this.state.resultats = [];
            return;
        }
        const mots = q.split(/\s+/);
        const resultats = [];
        for (const p of this.state.postes) {
            const texte = sansAccents([p.titre, p.texte, p.mots, ...p.actions.map((a) => a.libelle)].join(" "));
            if (mots.every((m) => texte.includes(m))) {
                const action = p.actions.find((a) => mots.some((m) => sansAccents(a.libelle).includes(m))) || p.actions[0];
                const score = sansAccents(p.titre).includes(q) ? 0 : sansAccents(p.mots).includes(q) ? 0.5 : p.cle.startsWith("famille-") ? 2 : 1;
                resultats.push({ poste: p, action, score });
            }
        }
        for (const z of ZONES) {
            if (sansAccents(z.nom).includes(q)) {
                resultats.push({ zone: z, score: 0.5 });
            }
        }
        this.state.resultats = resultats.sort((a, b) => a.score - b.score).slice(0, 7);
    }

    onToucheRecherche(ev) {
        if (ev.key === "Enter" && this.state.resultats.length) {
            this.choisir(this.state.resultats[0]);
        }
    }

    choisir(r) {
        if (r.zone) {
            this.allerZone(r.zone);
        } else {
            this.ouvrirPoste(r.poste);
        }
        this.state.recherche = "";
        this.state.resultats = [];
    }

    // ------------------------------------------------------------------ l'en-tête

    get zones() {
        return ZONES;
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

    taillePolice(base) {
        // les libellés gardent une taille lisible à l'écran, quel que soit le zoom
        return (base / this.echelle).toFixed(2);
    }
}

registry.category("actions").add("cultiveau_vue3d.vue", VueEnsemble);
