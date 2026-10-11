/** @odoo-module **/
// La vue d'ensemble : le site type d'un adhérent Cultiveau en vraie 3D (WebGL), à l'échelle (1 case = 1 m), et qui ouvre tout.
// Une caméra isométrique de jeu vidéo : on zoome à la molette, on glisse pour se déplacer, on tourne la vue (Q / E), on vole
// d'une zone à l'autre. Chaque poste du plan (la facturation, le coin conseil, un rayon, le quai…) ouvre une carte d'actions ;
// chaque objet vivant (un devis, une facture, un camion, un chantier) ouvre sa fiche. Le site se construit à l'arrivée,
// les camions roulent, le chariot va et vient, les pivots tournent, les asperseurs et les canons arrosent.
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { bibliotheque, TEINTES } from "./modeles";

const LIB = "/cultiveau_vue3d/static/lib/three/three.min.js";
const C = {
    sol: "#efeae0", zone: "#e8e2d6", route: "#c9c2b2", acier: "#5d6b78", bois: "#d4ae74", carton: "#efbf4a", bleu: "#0b9bb8", marine: "#1d4550",
    blanc: "#fbfaf7", peau: "#f0c3a3", herbe: "#a9d68a", herbeFonce: "#76b357", terre: "#c29563", eau: "#86d4ea", gris: "#bfc6cd", rouge: "#e2605b",
    orange: "#f6a852", tube: "#34454e", papier: "#ffffff", vert: "#53a832", toit: "#93a5b2", client: "#d9efe6", admin: "#ede7f3", atelier: "#dfdbd2",
    vitre: "#c4e8f1",
};
const URGENCE = { immediate: C.rouge, journee: C.orange, semaine: C.bleu, non_urgent: C.gris };
const URGENCE_HEX = { immediate: TEINTES.rouge, journee: TEINTES.orange, semaine: TEINTES.bleu, non_urgent: TEINTES.gris };
const ETAT = { projet: C.gris, etude: C.carton, realisation: C.orange, en_service: C.herbeFonce, arretee: C.terre };
const TEINTES_FAMILLES = [C.bleu, C.carton, C.vert, C.orange, "#8a7fd0", C.rouge, "#2fb3a3", "#d27a97"];
const ELEVATION = 0.6; // l'angle de la caméra au-dessus de l'horizon (≈ 34°)

function teinte(hex, facteur) {
    const n = parseInt(hex.slice(1), 16);
    const c = [n >> 16, (n >> 8) & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(v * facteur))));
    return "#" + c.map((v) => v.toString(16).padStart(2, "0")).join("");
}
/** Un pavé posé en (x, y, z) du plan, de largeur w (vers x), profondeur d (vers y), hauteur h. */
function pave(x, y, z, w, d, h, couleur, extra = null) {
    return [{ x, y, z, w, d, h: Math.max(h, 0.01), c: couleur, ...(extra || {}) }];
}
function sansAccents(texte) {
    return (texte || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}
const nombre = (v) => (v || 0).toLocaleString("fr-FR");
const facile = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
const rebond = (k) => {
    const c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2);
};
const echapper = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// Les zones du site : où l'on vole quand on les choisit.
const ZONES = [
    { cle: "magasin", nom: "Magasin & comptoir", icone: "fa-shopping-basket", box: [0, 9, 14, 21] },
    { cle: "administratif", nom: "Administratif", icone: "fa-briefcase", box: [0, 0, 14, 9] },
    { cle: "stockage", nom: "Stockage & familles", icone: "fa-cubes", box: [14, 0, 32, 21] },
    { cle: "atelier", nom: "Atelier & SAV", icone: "fa-wrench", box: [32, 0, 48, 21] },
    { cle: "parking", nom: "Parking clients", icone: "fa-car", box: [0, 22.5, 14.5, 36.5] },
    { cle: "dehors", nom: "Dépôt & cour", icone: "fa-truck", box: [15, 22, 48, 37] },
    { cle: "agriculteurs", nom: "Chez les clients", icone: "fa-leaf", box: [0, 43, 48, 64] },
];
const TOUT = [-1, -1, 49, 62];

export class VueEnsemble extends Component {
    static template = "cultiveau_vue3d.Vue";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.hote = useRef("hote");
        this.calque = useRef("calque");
        this.carteRef = useRef("carte");
        this.bulle = useRef("bulle");
        this.state = useState({ donnees: null, carte: null, survol: null, recherche: "", resultats: [], zone: null, sans3d: false, pret: false });
        this.postes = [];
        onWillStart(async () => {
            await this.charger();
            try {
                await loadJS(LIB);
            } catch {
                this.state.sans3d = true;
            }
        });
        onMounted(() => {
            if (!this.state.sans3d) {
                try {
                    this.initialiser();
                } catch (e) {
                    console.warn("Vue 3D indisponible :", e);
                    this.state.sans3d = true;
                }
            }
            this._clavier = (ev) => this.onClavier(ev);
            window.addEventListener("keydown", this._clavier);
        });
        onWillUnmount(() => this.detruire());
    }

    async charger() {
        this.state.donnees = await this.orm.call("cultiveau.scene", "donnees", []);
        this.dispo = new Set(this.state.donnees.actions || []);
        this.construire();
    }

    fiche(modele, id) {
        return { type: "ir.actions.act_window", res_model: modele, res_id: id, views: [[false, "form"]] };
    }

    // ------------------------------------------------------------------ le plan : postes, objets, libellés

    construire() {
        const d = this.state.donnees;
        const k = d.compteurs;
        const T = TEINTES;
        const sols = [];
        const objets = [];
        const libelles = [];
        const postes = [];
        const jets = [];
        const court = (texte, n = 22) => (texte && texte.length > n ? texte.slice(0, n - 1) + "…" : texte || "");
        /** Un modèle de la bibliothèque, posé en (x, y) du plan, tourné de rot (radians), à la hauteur z. */
        const M = (m, x, y, o = {}, rot = 0, z = 0) => ({ m, x, y, z, rot, o });
        const sol = (cle, x, y, w, dd, couleur, zone = null, z = 0) => sols.push({ cle, faces: pave(x, y, z - 0.02, w, dd, 0.02, couleur), zone });
        const decor = (cle, faces, classe = "") => objets.push({ cle, faces, genre: "decor", classe });
        const element = (faces, infos) => {
            objets.push({ cle: "e" + objets.length, faces, genre: "element", classe: infos.classe || "", ...infos });
            if (infos.etiquette && infos.ou) {
                libelles.push({ texte: court(infos.etiquette, 18), p: infos.ou, genre: "objet" });
            }
        };
        const libelle = (texte, x, y, genre = "piece", z = 0) => libelles.push({ texte, p: [x, y, z], genre });
        const ok = (cle) => this.dispo.has(cle);
        /** Un poste du plan : un ensemble qui ouvre une carte d'actions. */
        const poste = (cle, x, y, faces, infos) => {
            const actions = (infos.actions || []).filter((a) => ok(a.cle));
            if (!actions.length) {
                return;
            }
            const p = { cle, zone: infos.zone, titre: infos.titre, texte: infos.texte || "", icone: infos.icone || "fa-circle", actions,
                        badge: infos.badge || 0, urgent: !!infos.urgent, mots: infos.mots || "", haut: infos.haut || 2.4,
                        parametre: infos.parametre || null, stats: infos.stats || [], couleur: infos.couleur || "#1d4550", ancre: [x, y, infos.haut || 2.4] };
            postes.push(p);
            objets.push({ cle: "p-" + cle, faces, genre: "poste", poste: p, classe: infos.classe || "" });
        };
        const A = (cle, libelle, extra = {}) => ({ cle, libelle, ...extra });
        const hex = (c) => "#" + c.toString(16).padStart(6, "0");

        // ---------------- le terrain, la route, les champs, les arbres
        sol("terrain", -1, -1, 50, 38.5, "#e6e1d6");
        sol("trottoir", -1, 37.5, 50, 0.6, "#d2ccc0");
        sol("route", -1, 38.1, 50, 3.6, "#5d646b");
        sol("trottoir2", -1, 41.7, 50, 0.6, "#d2ccc0");
        for (let x = 0; x < 48; x += 3) {
            sol("tiret" + x, x, 39.83, 1.6, 0.14, "#f4f1e8", null, 0.01);
        }
        sol("champs", -1, 42.3, 50, 22, "#cfe3ad", "agriculteurs");
        libelle("ROUTE D'ACCÈS", 46, 40, "route");
        libelle("ENTRÉE CLIENTS", 7, 37.2, "entree");
        libelle("ENTRÉE POIDS LOURDS", 42, 37.2, "entree");
        decor("livreur", [M("utilitaire", 0, 0, { couleur: T.bleu })], "route");
        decor("livreur2", [M("semi", 0, 0, { couleur: T.vert })], "route2");
        for (let n = 0; n < 3; n++) {
            decor("passant" + n, [M("personne", 0, 0, { chemise: [T.orange, T.vert, T.rouge][n], pantalon: [T.marine, 0x5a6b7a, T.anthracite][n] })], "passant");
        }
        const arbres = [];
        for (let x = -3; x < 52; x += 4.2) {
            arbres.push(M("arbre", x, -3.2 + (x % 3) * 0.3, { h: 4 + (x % 5) * 0.4 }));
            arbres.push(M("arbre", x + 1.5, 65 + (x % 2), { h: 4.5, couleur: x % 8 < 4 ? T.feuillage : T.feuillageFonce }));
        }
        for (let y = 2; y < 36; y += 4.5) {
            arbres.push(M("arbre", -3.4, y, { h: 4 + (y % 3) * 0.5, sapin: y % 9 < 4 }));
            arbres.push(M("arbre", 51.5, y + 1, { h: 4.2, sapin: y % 9 >= 4 }));
        }
        decor("arbres", arbres);

        // ---------------- le bâtiment : dalle, murs, vitrine, cloisons
        sol("admin", 0, 0, 14, 9, "#efe9f3", "administratif");
        sol("magasin", 0, 9, 14, 12, "#dff0e8", "magasin");
        sol("stockage", 14, 0, 18, 21, "#ebe6dc", "stockage");
        sol("atelier", 32, 0, 16, 21, "#e3dfd6", "atelier");
        const murs = [
            ...pave(-0.25, -0.25, 0, 48.5, 0.25, 3.2, "#f7f5ef"), ...pave(-0.25, 0, 0, 0.25, 9, 3.2, "#f7f5ef"),
            ...pave(-0.25, 9, 0, 0.25, 12, 0.5, "#f7f5ef"), ...pave(48, 0, 0, 0.25, 21.25, 0.5, "#f7f5ef"),
            ...pave(0, 21, 0, 5.5, 0.25, 0.5, "#f7f5ef"), ...pave(8.5, 21, 0, 30.5, 0.25, 0.5, "#f7f5ef"), ...pave(45, 21, 0, 3, 0.25, 0.5, "#f7f5ef"),
            ...pave(14, 0, 0, 0.15, 13, 0.5, "#cfd4d8"), ...pave(14, 16, 0, 0.15, 5, 0.5, "#cfd4d8"),
            ...pave(32, 0, 0, 0.15, 8, 0.5, "#cfd4d8"), ...pave(32, 11, 0, 0.15, 10, 0.5, "#cfd4d8"),
            ...pave(0, 9, 0, 6, 0.15, 0.5, "#cfd4d8"), ...pave(9, 9, 0, 5, 0.15, 0.5, "#cfd4d8"),
        ];
        // la vitrine du magasin : montants marine et grandes vitres
        const vitrine = [];
        for (let y = 9; y <= 21; y += 2) {
            vitrine.push(...pave(-0.25, y - 0.06, 0.5, 0.25, 0.12, 2.2, "#1d4550"));
        }
        for (const [x0, x1] of [[0, 5.5], [8.5, 14]]) {
            for (let x = x0; x <= x1; x += 1.83) {
                vitrine.push(...pave(x - 0.06, 21, 0.5, 0.12, 0.25, 2.2, "#1d4550"));
            }
        }
        vitrine.push(...pave(-0.25, 9, 2.7, 0.25, 12, 0.18, "#1d4550"), ...pave(0, 21, 2.7, 5.5, 0.25, 0.18, "#1d4550"), ...pave(8.5, 21, 2.7, 5.5, 0.25, 0.18, "#1d4550"));
        decor("murs", murs);
        decor("vitrine", vitrine);
        decor("vitres", [...pave(-0.18, 9, 0.5, 0.06, 12, 2.2, "#bfe6f0"), ...pave(0, 21.08, 0.5, 5.5, 0.06, 2.2, "#bfe6f0"), ...pave(8.5, 21.08, 0.5, 5.5, 0.06, 2.2, "#bfe6f0")], "verre");
        libelle("ADMINISTRATIF", 7, 8.3, "zone");
        libelle("MAGASIN", 6.8, 20.4, "zone");
        libelle("STOCKAGE", 23, 12.9, "zone");
        libelle("ATELIER", 40, 10.8, "zone");

        // ---------------- l'administratif
        poste("facturation", 2.2, 1.7, [M("bureau", 2.2, 1.7), M("personne", 2.2, 2.55, { chemise: T.bleu, cheveux: 0x2b1d14 }, Math.PI / 2)], {
            zone: "administratif", titre: "Facturation", icone: "fa-file-text-o", badge: k.factures, urgent: d.caisse.some((f) => f.en_retard), couleur: "#0b9bb8",
            texte: "Faire une facture, suivre ce qui reste à encaisser, les avoirs.",
            stats: [`${nombre(k.factures)} facture(s) à encaisser`, `${nombre(k.factures_montant)} € restant dû`],
            actions: [A("facture_nouvelle", "Faire une facture", { principal: true, icone: "fa-plus" }), A("factures_a_encaisser", "Factures à encaisser", { badge: k.factures }),
                      A("factures", "Toutes les factures"), A("avoirs", "Avoirs")],
            mots: "facture facturer facturation avoir encaisser impaye relance client paiement",
        });
        d.caisse.forEach((f, i) => {
            const x = 1.55 + (i % 4) * 0.42;
            element([M("liasse", x, 1.9 + Math.floor(i / 4) * 0.35, { h: 0.06 + Math.min(0.3, f.montant / 30000), couleur: f.en_retard ? T.rouge : T.vert }, 0, 0.77)],
                    { titre: `Facture ${f.nom} — ${f.client} — ${nombre(f.montant)} € restant${f.echeance ? " — échéance " + f.echeance : ""}${f.en_retard ? " (en retard)" : ""}`,
                      action: this.fiche("account.move", f.id), classe: f.en_retard ? "alerte" : "" });
        });
        poste("compta", 6.2, 1.7, [M("bureau", 6.2, 1.7), M("personne", 6.2, 2.55, { chemise: T.marine, cheveux: 0x7a5434 }, Math.PI / 2), M("armoire", 8.2, 0.7, {}, Math.PI / 2)], {
            zone: "administratif", titre: "Comptabilité", icone: "fa-calculator", couleur: "#1d4550",
            texte: "Les fournisseurs à payer, les paiements, les journaux et la banque.",
            actions: [A("a_payer", "Fournisseurs à payer", { principal: true }), A("factures_fournisseurs", "Factures fournisseurs"), A("paiements", "Paiements"),
                      A("journaux", "Journaux et banque"), A("ecritures", "Écritures")],
            mots: "compta comptabilite banque paiement journal fournisseur payer tva ecriture",
        });
        poste("etude", 11, 2.0, [M("plans", 11, 2.0), M("personne", 10.2, 3.1, { chemise: T.jaune }, Math.PI / 2), M("personne", 11.9, 3.1, { chemise: T.bleu, cheveux: 0x2b1d14 }, Math.PI / 2)], {
            zone: "administratif", titre: "Bureau d'étude", icone: "fa-pencil-square-o", badge: d.bureau.etudes.length, couleur: "#efbf4a",
            texte: "Analyse des besoins, dimensionnement, tracé du réseau en 3D.",
            actions: [A("etude_nouvelle", "Nouvelle étude", { principal: true, icone: "fa-plus" }), A("etudes", "Études en cours", { badge: d.bureau.etudes.length }),
                      A("schema3d", "Cultiveau 3D : tracer le réseau", { icone: "fa-cube" }), A("usages", "Simulations à l'usage"), A("installations", "Toutes les installations")],
            mots: "etude dimensionnement plan reseau 3d schema cultiveau 3d trace installation besoins",
        });
        d.bureau.etudes.forEach((e, i) => {
            element([M("dossiers", 10.0 + (i % 3) * 0.85, 1.6 + Math.floor(i / 3) * 0.6, { couleur: e.etat === "etude" ? T.jaune : T.gris }, 0.1 * (i % 3), 0.96)],
                    { titre: `Étude : ${e.nom} — ${e.client} — ${e.type_libelle}${e.surface ? " — " + e.surface + " ha" : ""}${e.analyse_validee ? " — analyse validée" : " — analyse des besoins à valider"}`,
                      etiquette: e.client, ou: [10.0 + (i % 3) * 0.85, 1.6, 1.4], action: this.fiche("cultiveau.installation", e.id) });
        });
        poste("reunion", 3.8, 6.2, [M("table", 3.8, 6.2, { l: 5, p: 1.7 }), ...pave(1.2, 8.6, 1.0, 3, 0.08, 1.5, "#1d4550")], {
            zone: "administratif", titre: "Salle de réunion", icone: "fa-handshake-o", badge: k.devis, couleur: "#2a63b0",
            texte: "Les devis avec l'agriculteur, les demandes en cours, les rendez-vous.",
            stats: [`${nombre(k.devis)} devis en cours — ${nombre(k.devis_montant)} €`],
            actions: [A("devis_nouveau", "Faire un devis", { principal: true, icone: "fa-plus" }), A("devis", "Devis en cours", { badge: k.devis }),
                      A("pipeline", "Demandes et opportunités", { badge: d.accueil.opportunites.length }), A("commandes", "Commandes"), A("rendez_vous", "Rendez-vous")],
            mots: "devis chiffrage reunion opportunite demande rendez vous rdv commande vente pipeline",
        });
        d.bureau.devis.forEach((v, i) => {
            element([M("liasse", 1.9 + (i % 6) * 0.75, 6.0 + Math.floor(i / 6) * 0.5, { h: 0.05 + Math.min(0.3, v.montant / 60000), couleur: v.etat === "sent" ? T.bleu : T.gris }, 0, 0.78)],
                    { titre: `Devis ${v.nom} — ${v.client} — ${v.installation} — ${nombre(v.montant)} €${v.etat === "sent" ? " (envoyé)" : " (brouillon)"}`, action: this.fiche("sale.order", v.id) });
        });
        poste("direction", 11, 6.2, [M("bureau", 11, 6.2, { l: 2.2 }), M("personne", 11, 7.05, { chemise: T.vert, cheveux: 0x2b1d14 }, Math.PI / 2), M("plante", 13.2, 8.2), M("machineCafe", 13.3, 0.7)], {
            zone: "administratif", titre: "Direction", icone: "fa-line-chart", couleur: "#53a832",
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
        const teinteFamille = (i) => TEINTES_FAMILLES[i % TEINTES_FAMILLES.length];
        const posteFamille = (f, i, x, y, faces, zone, haut = 3.6) => poste("famille-" + f.id, x, y, faces, {
            zone, titre: f.nom, icone: "fa-th-large", badge: f.mien, parametre: f.id, couleur: teinteFamille(i), haut,
            texte: "Une famille de produits : mes articles, le stock, le catalogue Cultiveau et les fiches techniques.",
            stats: [`${nombre(f.mien)} dans mon catalogue`, `${nombre(f.reseau)} au catalogue Cultiveau`, `${nombre(f.stock)} en stock`],
            actions: [A("famille_mien", "Mes articles", { principal: true, badge: f.mien }), A("famille_stock", "En stock", { badge: f.stock }),
                      A("famille_reseau", "Catalogue Cultiveau", { badge: f.reseau }), A("famille_fiches", "Fiches techniques", { icone: "fa-file-pdf-o" })],
            mots: "famille rayon produit article " + f.nom,
        });
        libreService.forEach((f, i) => {
            const y = 11.4 + i * 2.35;
            posteFamille(f, i, 3.2, y, [M("gondole", 3.2, y, { couleur: parseInt(teinteFamille(i).slice(1), 16) })], "magasin", 2.4);
        });
        poste("comptoir", 11.2, 14.5, [M("comptoir", 11.2, 14.5), M("personne", 12.3, 13.6, { chemise: T.bleu }, Math.PI), M("personne", 12.3, 15.8, { chemise: T.bleu, cheveux: 0x7a5434 }, Math.PI)], {
            zone: "magasin", titre: "Comptoir", icone: "fa-barcode", badge: d.accueil.comptoir.length, haut: 2.6, couleur: "#1d4550",
            texte: "La vente au magasin : on scanne, on encaisse, le ticket sort.",
            actions: [A("comptoir", "Ouvrir le comptoir", { principal: true, icone: "fa-barcode" }), A("ventes_comptoir", "Ventes au comptoir"), A("agriculteurs", "Les clients")],
            mots: "comptoir vente caisse scan douchette ticket encaisser magasin",
        });
        d.accueil.opportunites.forEach((o, i) => {
            const x = 9.3 - Math.floor(i / 5) * 0.9, y = 12.2 + (i % 5) * 1.0;
            element([M("personne", x, y, { chemise: [T.orange, T.vert, T.jaune, T.rouge, 0x8a7fd0][i % 5], pantalon: i % 2 ? T.marine : 0x5a6b7a, casque: false })],
                    { titre: `Demande : ${o.nom} — ${o.client} — ${o.etape}${o.montant ? " — " + nombre(o.montant) + " €" : ""}`,
                      action: this.fiche("crm.lead", o.id), classe: "personne" });
        });
        d.accueil.comptoir.forEach((v, i) => {
            const y = 12.2 + i * 0.6;
            element(pave(10.95, y, 1.08, 0.45, 0.45, 0.35, "#d9a35a"), { titre: `Vente comptoir ${v.nom} — ${v.client} — ${nombre(v.montant)} €`, action: this.fiche("sale.order", v.id) });
        });
        poste("conseil", 8.6, 19.4, [M("borne", 8.6, 19.4, {}, -Math.PI / 2), M("table", 11.4, 19.6, { l: 1.4, p: 1.0 }), M("plante", 0.7, 20.2), M("plante", 13.3, 20.3)], {
            zone: "magasin", titre: "Coin conseil", icone: "fa-desktop", badge: k.fiches, haut: 2.6, couleur: "#0b9bb8",
            texte: "Avec l'agriculteur : les fiches techniques, le catalogue, le réseau en 3D.",
            actions: [A("fiches", "Fiches techniques", { principal: true, icone: "fa-file-pdf-o", badge: k.fiches }), A("schema3d", "Cultiveau 3D", { icone: "fa-cube" }),
                      A("catalogue", "Catalogue Cultiveau", { badge: k.catalogue }), A("mon_catalogue", "Mon catalogue", { badge: k.mon_catalogue }), A("rendez_vous", "Prendre rendez-vous")],
            mots: "fiche technique fiches techniques documentation notice pdf conseil catalogue 3d cultiveau 3d schema bibliotheque",
        });
        decor("totem", [M("totem", -2.2, 22.8, {}, Math.PI / 4)]);

        // ---------------- le stockage : une famille par rack, la préparation
        const racks = restantes.slice(0, 11);
        racks.forEach((f, i) => {
            const x = 16.6 + (i % 4) * 4.4, y = 2.0 + Math.floor(i / 4) * 4.2;
            const remplissage = Math.min(6, Math.max(1, Math.ceil(Math.log10(f.stock + f.mien + 1) * 1.7)));
            posteFamille(f, i + 4, x, y, [M("rack", x, y, { remplissage, couleur: parseInt(teinteFamille(i + 4).slice(1), 16) })], "stockage");
        });
        if (restantes.length > 11 || ok("categories")) {
            const x = 16.6 + 3 * 4.4, y = 2.0 + 2 * 4.2;
            poste("toutes-familles", x, y, [M("rack", x, y, { remplissage: 2, couleur: T.gris })], {
                zone: "stockage", titre: restantes.length > 11 ? `+ ${restantes.length - 11} autres familles` : "Toutes les familles", icone: "fa-sitemap", haut: 3.6,
                texte: "Toutes les familles et sous-familles de produits.",
                actions: [A("mon_catalogue", "Mon catalogue", { principal: true }), A("catalogue", "Catalogue Cultiveau"), A("categories", "Les familles"),
                          A("import_articles", "Importer mes articles"), A("fournisseurs", "Fournisseurs")],
                mots: "familles categories catalogue articles importer fournisseurs",
            });
        }
        sol("prepa", 15, 14, 16, 6, "#e2ddd1", null, 0.01);
        sol("prepa-ligne", 15, 14, 16, 0.1, "#f2c230", null, 0.015);
        decor("chariot", [M("chariot", 0, 0)], "chariot");
        poste("preparation", 17.2, 15.4, [M("etabli", 17.2, 15.4), M("personne", 17.2, 16.4, { chemise: T.orange }, Math.PI / 2), M("palette", 19.3, 15.4, { h: 0.2 })], {
            zone: "stockage", titre: "Préparation · expéditions", icone: "fa-dropbox", badge: d.cour.preparations.length, couleur: "#f28c28",
            texte: "Les commandes à préparer pour les clients et les chantiers, les réceptions, l'inventaire.",
            actions: [A("livraisons", "À préparer et livrer", { principal: true, badge: d.cour.preparations.length }), A("receptions", "Réceptions"),
                      A("inventaire", "Inventaire"), A("reappro", "Réapprovisionnement"), A("mouvements", "Mouvements de stock")],
            mots: "preparation livraison expedition stock inventaire reception reapprovisionnement mouvement picking bon",
        });
        libelle("préparation commandes · chantiers", 23, 20.4);
        d.cour.preparations.forEach((p, i) => {
            const x = 21.5 + (i % 6) * 1.6, y = 16 + Math.floor(i / 6) * 1.6;
            element([M("palette", x, y, { h: 0.1 + (i % 3) * 0.15 })], { titre: `À préparer : ${p.nom} — ${p.client}${p.date ? " — " + p.date : ""}`, etiquette: p.client, ou: [x, y, 1.3],
                                                                       action: this.fiche("stock.picking", p.id) });
        });

        // ---------------- l'atelier
        const atelier = d.atelier || [];
        const depannages = atelier.filter((t) => t.nature === "depannage" || t.urgence === "immediate" || t.urgence === "journee");
        const etabli = atelier.filter((t) => !depannages.includes(t));
        poste("banc", 35.5, 2.3, [M("bac", 35.5, 2.3), M("personne", 35.5, 3.6, { chemise: T.bleuRoi, casque: true }, Math.PI / 2)], {
            zone: "atelier", titre: "Banc d'essai pompes", icone: "fa-tachometer", badge: etabli.length, couleur: "#2a63b0",
            texte: "Entretiens, diagnostics et révisions : ce qui est sur le banc.",
            actions: [A("entretiens", "Entretiens en cours", { principal: true, badge: etabli.length }), A("equipements_a_renouveler", "Équipements à renouveler"), A("registre", "Registre de maintenance")],
            mots: "banc pompe entretien diagnostic revision equipement renouveler registre maintenance",
        });
        etabli.slice(0, 3).forEach((t, i) => {
            element([M("pompe", 34.3 + i * 1.25, 2.3, { couleur: [T.bleuRoi, T.rouge, T.vert][i % 3] }, 0, 0.8)],
                    { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.installation ? " — " + t.installation : ""}`, action: this.fiche("project.task", t.id) });
        });
        decor("atelier-fond", [M("armoire", 47.3, 2.2, {}, Math.PI), M("etabli", 44.5, 0.8, {}, 0), M("soudeuse", 35.5, 6.5), M("personne", 35.5, 7.4, { chemise: T.anthracite, casque: true }, Math.PI / 2)]);
        decor("etincelles", [...pave(35.4, 6.45, 1.25, 0.08, 0.08, 0.08, "#ffb347"), ...pave(35.6, 6.6, 1.35, 0.06, 0.06, 0.06, "#fff1a8")], "etincelle");
        libelle("soudure PE", 35.5, 7.9);
        libelle("local élec.", 47.3, 3.7);
        poste("prefa", 41.5, 6.3, [M("prefa", 41.5, 6.3)], {
            zone: "atelier", titre: "Préfabrication des stations", icone: "fa-cogs", badge: k.chantiers || 0, couleur: "#53a832",
            texte: "On assemble les stations de tête à l'atelier, on les pose sur le chantier.",
            actions: [A("chantiers", "Chantiers à préparer", { principal: true, badge: k.chantiers || 0 }), A("planning", "Planning des équipes"), A("chantier_nouveau", "Nouveau chantier")],
            mots: "prefabrication station tete chantier pose planning equipe",
        });
        decor("pont", [...pave(32.6, 9.6, 0, 0.25, 0.25, 4.0, "#5d6b78"), ...pave(47.4, 9.6, 0, 0.25, 0.25, 4.0, "#5d6b78"), ...pave(32.6, 9.55, 4.0, 15.1, 0.35, 0.35, "#f2c230"),
                       ...pave(39.6, 9.5, 3.4, 0.5, 0.45, 0.6, "#2c3a43")]);
        sol("sav", 33, 11.5, 14, 8.5, "#ddd8ce", null, 0.01);
        poste("sav", 34.2, 12.6, [M("panneau", 34.2, 12.6, { couleur: T.rouge }), M("utilitaire", 44.2, 19, { couleur: T.bleu, gyrophare: true }, Math.PI / 2)], {
            zone: "atelier", titre: "SAV · enrouleurs et pivots", icone: "fa-wrench", badge: depannages.length, urgent: depannages.some((t) => t.urgence === "immediate"), couleur: "#e2605b",
            haut: 3.2, texte: "Les pannes et les dépannages : enrouleurs, pivots, pompes en saison.",
            actions: [A("depannage_nouveau", "Nouveau dépannage", { principal: true, icone: "fa-plus" }), A("depannages", "Dépannages en cours", { badge: depannages.length }),
                      A("interventions", "Toutes les interventions"), A("registre", "Registre de maintenance")],
            mots: "sav depannage panne intervention enrouleur pivot reparation urgence technicien",
        });
        depannages.slice(0, 4).forEach((t, i) => {
            const x = 37.2 + (i % 2) * 4.6, y = 13.6 + Math.floor(i / 2) * 3.6;
            element([M("enrouleur", x, y, { couleur: [T.rouge, T.bleuRoi, T.orange, T.vert][i % 4] }), M("personne", x + 1.8, y + 1.2, { chemise: T.bleu, casque: true }, Math.PI)],
                    { titre: `${t.nature_libelle} ${t.urgence_libelle || ""} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.installation ? " — " + t.installation : ""}`,
                      etiquette: t.client || t.nom, ou: [x, y, 3.6], action: this.fiche("project.task", t.id), classe: t.urgence === "immediate" ? "alerte" : "" });
        });
        libelle("grande porte 5 × 5 m", 42, 21.8);

        // ---------------- dehors : parking, dépôt, cour
        sol("parking", 0, 23, 14, 13, "#d6d9d4", "parking");
        // cinq places de chaque côté de l'allée ; la place bleue (PMR) au bout, côté route
        for (let p = 0; p < 6; p++) {
            sol("place" + p, 0.4 + p * 2.7, 23.4, 0.1, 4.6, "#ffffff", null, 0.01);
            sol("place-b" + p, 0.4 + p * 2.7, 31.0, 0.1, 4.6, "#ffffff", null, 0.01);
        }
        sol("pmr", 11.25, 31.0, 2.5, 4.6, "#3d7fc4", null, 0.015);
        libelle("PARKING CLIENTS", 7, 29.5, "zone");
        decor("parking-decor", [M("haie", 7, 36.4, { l: 13 }), M("lampadaire", 13.6, 29.3), M("personne", 13.9, 33.2, { chemise: T.orange, pantalon: T.marine }, Math.PI)]);
        // les clients, chacun son véhicule : on voit qui fait quoi ; un clic ouvre les clients de ce type
        const parType = k.clients_par_type || {};
        const TYPES = [
            { t: "agriculteur", titre: "Agriculteurs", un: "agriculteur", icone: "fa-leaf", couleur: "#3f9a3a", m: ["tracteur", {}],
              texte: "Les exploitations : leurs cultures et leur frise disent qui appeler au bon moment.",
              plus: [A("a_contacter", "À contacter ce mois-ci", { badge: k.a_contacter }), A("cultures", "Cultures et frise"), A("personas", "Profils")],
              mots: "agriculteur exploitant exploitation ferme gaec earl tracteur culture frise" },
            { t: "collectivite", titre: "Collectivités", un: "collectivité", icone: "fa-university", couleur: "#1f4ea1", m: ["plateau", { couleur: T.blanc, charge: "benne", gyrophare: true, tricolore: true }],
              texte: "Mairies, syndicats, golfs, stades : arrosage des espaces publics et des terrains de sport.", mots: "collectivite mairie commune syndicat golf stade public espaces verts" },
            { t: "industrie", titre: "Industries", un: "industriel", icone: "fa-industry", couleur: "#5f6874", m: ["fourgonnette", { couleur: 0x6b7480, bande: 0xf0b429 }],
              texte: "Usines, carrières, entreprises : pompage, process, lavage, défense incendie.", mots: "industrie usine carriere entreprise pompage process" },
            { t: "plombier", titre: "Plombiers", un: "plombier", icone: "fa-wrench", couleur: "#2f7fc1", m: ["fourgonnette", { couleur: T.blanc, tuyaux: true, bande: 0x2f7fc1 }],
              texte: "Les plombiers qui achètent au comptoir : raccords, vannes, pompes, surpresseurs.", mots: "plombier plomberie chauffagiste artisan raccord tuyau" },
            { t: "particulier", titre: "Particuliers", un: "particulier", icone: "fa-home", couleur: "#2d6cdf", m: ["voiture", { couleur: 0x2d6cdf }],
              texte: "Jardins, potagers, arrosage automatique, récupération d'eau de pluie.", mots: "particulier jardin potager maison arrosage automatique" },
            { t: "paysagiste", titre: "Paysagistes", un: "paysagiste", icone: "fa-tree", couleur: "#5fae3e", m: ["plateau", { couleur: 0xf0a23b, charge: "vert" }],
              texte: "Les paysagistes : programmateurs, électrovannes, goutte-à-goutte, tuyères.", mots: "paysagiste espaces verts jardinier entretien parc" },
            { t: "pisciniste", titre: "Piscinistes", un: "pisciniste", icone: "fa-tint", couleur: "#1aa7c4", m: ["fourgonnette", { couleur: 0x1aa7c4, echelle: true, galerie: true, bande: T.blanc }],
              texte: "Les piscinistes : pompes, filtration, raccords PVC pression.", mots: "pisciniste piscine filtration pompe" },
            { t: "autre", titre: "Autres clients", un: "client", icone: "fa-user", couleur: "#7c8592", m: ["fourgonnette", { couleur: 0xe9edf0 }],
              texte: "Les clients qui ne rentrent dans aucune case.", mots: "autre client divers" },
        ];
        const places = [[1.75, 25.6], [4.45, 25.6], [7.15, 25.6], [9.85, 25.6], [12.55, 25.6], [1.75, 33.4], [4.45, 33.4], [7.15, 33.4]];
        TYPES.forEach((c, i) => {
            const [x, y] = places[i];
            const n = parType[c.t] || 0;
            poste("client-" + c.t, x, y, [M(c.m[0], x, y, c.m[1], Math.PI / 2)], {
                zone: "parking", titre: c.titre, icone: c.icone, badge: n, haut: c.t === "agriculteur" ? 3.4 : 2.7, couleur: c.couleur, parametre: c.t,
                classe: "garer", texte: c.texte,
                actions: [A("clients_type", `Les ${c.titre.toLowerCase()}`, { principal: true, badge: n }), A("client_type_nouveau", `Nouveau ${c.un}`, { icone: "fa-plus" }),
                          ...(c.plus || []), A("agriculteurs", "Tous les clients", { badge: k.agriculteurs }), A("import_clients", "Importer mes clients")],
                mots: c.mots + " client clients",
            });
        });
        sol("depot", 16, 23, 18, 13, "#dcd6c9", "dehors");
        libelle("DÉPÔT EXTÉRIEUR", 25, 22.8, "zone");
        const poteaux = [16.3, 25, 33.7].flatMap((x) => [...pave(x, 23.4, 0, 0.22, 0.22, 3.4, "#5d6b78"), ...pave(x, 27.6, 0, 0.22, 0.22, 3.4, "#5d6b78")]);
        decor("auvent-poteaux", poteaux);
        decor("auvent", pave(16, 23.2, 3.4, 18, 4.8, 0.12, "#9fb0bc"), "toit");
        dehors.forEach((f, i) => {
            const x = 20.6 + i * 8.6, y = 25.6;
            posteFamille(f, i + 2, x, y, [M("cantilever", x, y, { l: 7.8, couleur: i ? 0x9aa3ab : 0x2a63b0 })], "dehors", 3.0);
        });
        if (!dehors.length) {
            decor("cantilever", [M("cantilever", 20.6, 25.6, { l: 7.8 }), M("cantilever", 29.2, 25.6, { l: 7.8, couleur: 0x2a63b0 })]);
        }
        decor("bobines", [M("bobines", 20.5, 30.8)]);
        libelle("bobines PE", 20.5, 32.4);
        poste("occasion", 28.6, 30.8, [M("enrouleur", 28, 30.8, { couleur: 0xb07a5a }), M("pompe", 31.4, 31.6, { couleur: 0x8a8f94 })], {
            zone: "dehors", titre: "Occasion · reprises", icone: "fa-recycle", haut: 3.6, couleur: "#c29563",
            texte: "Le matériel repris ou d'occasion : enrouleurs, travées, pompes à réviser.",
            actions: [A("occasion", "Le matériel d'occasion", { principal: true })], mots: "occasion reprise seconde main enrouleur travee pompe",
        });
        decor("bennes", [M("benne", 18.6, 34.4, { couleur: T.vert }), M("benne", 21.9, 34.4, { couleur: T.jaune }), M("benne", 25.2, 34.4, { couleur: 0x5d6b78 })]);
        libelle("bennes de tri · recyclage du plastique agricole", 22, 35.9);
        sol("cour", 36, 23, 12, 13, "#d3cdc0", "dehors");
        libelle("COUR POIDS LOURDS", 42, 22.8, "zone");
        poste("quai", 37.4, 29, [M("quai", 37.4, 29)], {
            zone: "dehors", titre: "Quai de réception", icone: "fa-truck", badge: d.cour.receptions.length, haut: 2.0, couleur: "#2a63b0",
            texte: "Les camions des fournisseurs : commandes attendues, réceptions, achats.",
            actions: [A("achat_nouveau", "Commander à un fournisseur", { principal: true, icone: "fa-plus" }), A("receptions", "Réceptions attendues", { badge: d.cour.receptions.length }),
                      A("achats", "Commandes fournisseurs"), A("demandes_prix", "Demandes de prix"), A("fournisseurs", "Fournisseurs")],
            mots: "quai reception fournisseur achat commande camion livraison demande de prix approvisionnement",
        });
        d.cour.receptions.slice(0, 2).forEach((a, i) => {
            const x = 40.2 + i * 3.4;
            element([M("semi", x, 28.6, { couleur: [T.bleuRoi, T.rouge][i % 2] }, -Math.PI / 2)],
                    { titre: `Réception attendue : ${a.nom} — ${a.fournisseur} — ${nombre(a.montant)} €${a.date ? " — " + a.date : ""}`,
                      etiquette: a.fournisseur, ou: [x, 28.6, 4.4], action: this.fiche("purchase.order", a.id) });
        });
        sol("lavage", 43.4, 32.6, 4.2, 3, "#9ad7e8", null, 0.015);
        decor("lavage", [M("nettoyeur", 47.3, 33.2)], "");
        libelle("aire de lavage", 45.5, 35.9);

        // ---------------- chez les agriculteurs, de l'autre côté de la route
        libelle("CHEZ LES AGRICULTEURS", 24, 43.4, "zone");
        const poses = [
            ...(d.chantiers.chantiers || []).map((c) => ({ ...c, modele: "cultiveau.chantier" })),
            ...d.chantiers.installations.map((c) => ({ ...c, modele: "cultiveau.installation", etat: "en_cours", equipe: 1, avancement: 0 })),
        ];
        poste("chantiers", 1.8, 45, [M("panneau", 1.8, 45, { couleur: T.orange })], {
            zone: "agriculteurs", titre: "Chantiers", icone: "fa-road", badge: poses.length, haut: 3.0, couleur: "#f6a852",
            texte: "Les équipes de pose : planning, matériel sorti du magasin, PV de mise en service.",
            actions: [A("chantier_nouveau", "Nouveau chantier", { principal: true, icone: "fa-plus" }), A("planning", "Planning des équipes"), A("chantiers", "Tous les chantiers", { badge: poses.length })],
            mots: "chantier pose equipe planning mise en service pv travaux",
        });
        poses.slice(0, 4).forEach((c, i) => {
            const x = 6.2 + (i % 2) * 11, y = 50 + Math.floor(i / 2) * 9.5;
            const planifie = c.etat === "planifie";
            const pieces = [M("culture", x, y, { nu: true, l: 10, p: 7.6 })];
            if (!planifie) {
                pieces.push(M("minipelle", x - 2, y - 1, { couleur: T.orange }, 0.4), M("utilitaire", x + 2.4, y + 4.4, { couleur: T.bleu }, 0));
                for (let n = 0; n < Math.min(3, 1 + (c.equipe || 0)); n++) {
                    pieces.push(M("personne", x + 1 + n * 0.9, y - 0.6 + n * 0.7, { chemise: T.orange, casque: true }, Math.PI / 2 + n));
                }
            } else {
                pieces.push(M("panneau", x - 3.5, y - 2.6, { couleur: T.bleu }));
            }
            const detail = c.modele === "cultiveau.chantier"
                ? `${planifie ? "Chantier planifié" : "Chantier en cours"} : ${c.titre} — ${c.client}${c.chef ? " — " + c.chef : ""}${c.debut ? " — du " + c.debut + (c.fin ? " au " + c.fin : "") : ""} — ${c.avancement} %`
                : `Chantier : ${c.nom} — ${c.client} — ${c.type_libelle}${c.surface ? " — " + c.surface + " ha" : ""}`;
            element(pieces, { titre: detail, etiquette: c.client, ou: [x, y, 2.6], action: this.fiche(c.modele, c.id) });
        });
        (d.chantiers.taches || []).slice(0, 2).forEach((t, i) => {
            const x = 6 + i * 7;
            element([M("utilitaire", x, 36.9, { couleur: URGENCE_HEX[t.urgence] ?? T.bleu }, 0)],
                    { titre: `${t.nature_libelle} : ${t.nom} — ${t.client}${t.technicien ? " — " + t.technicien : ""}${t.date ? " — " + t.date : ""}`, action: this.fiche("project.task", t.id) });
        });
        poste("parc", 25.8, 45, [M("panneau", 25.8, 45, { couleur: T.vert })], {
            zone: "agriculteurs", titre: "Parc installé", icone: "fa-tint", badge: d.parcelles.length, haut: 3.0, couleur: "#76b357",
            texte: "Les installations en service, leur registre, ce que la saison demande.",
            actions: [A("parc", "Installations en service", { principal: true }), A("equipements_a_renouveler", "Équipements à renouveler"),
                      A("registre", "Registre de maintenance"), A("installations", "Toutes les installations")],
            mots: "parc installation parcelle service hivernage remise en route registre equipement irrigation",
        });
        d.parcelles.slice(0, 4).forEach((p, i) => {
            const x = 30.5 + (i % 2) * 12, y = 50 + Math.floor(i / 2) * 9.5;
            const type = p.type || "";
            const arrete = p.etat !== "en_service";
            const pieces = [];
            if (type === "pivot") {
                pieces.push(M("culture", x, y, { l: 11, p: 8.4, genre: "mais" }), M("pivot", x, y, { longueur: 5.2 }));
            } else if (type === "enrouleur") {
                pieces.push(M("culture", x, y, { l: 11, p: 8.4, genre: "mais" }), M("enrouleur", x - 4.2, y + 2.6, { couleur: T.rouge, tuyau: 7.4 }), M("canon", x + 3.4, y + 2.6, {}, Math.PI));
                if (!arrete) {
                    jets.push({ x: x + 3.0, y: y + 2.6, h: 1.8, r: 3.6, canon: true });
                }
            } else if (type.startsWith("goutte")) {
                pieces.push(M("culture", x, y, { l: 11, p: 8.4, genre: "vigne", goutte: true }));
            } else if (type === "micro_aspersion") {
                pieces.push(M("culture", x, y, { l: 11, p: 8.4, genre: "verger", goutte: true }));
                if (!arrete) {
                    jets.push({ x: x - 2.5, y, h: 0.4, r: 1.0 }, { x: x + 2.5, y, h: 0.4, r: 1.0 });
                }
            } else {
                pieces.push(M("culture", x, y, { l: 11, p: 8.4, genre: "mais" }));
                for (const [ax, ay] of [[-3.4, -2.2], [0, -2.2], [3.4, -2.2], [-3.4, 2.2], [0, 2.2], [3.4, 2.2]]) {
                    pieces.push(M("asperseur", x + ax, y + ay));
                    if (!arrete) {
                        jets.push({ x: x + ax, y: y + ay, h: 1.15, r: 1.6 });
                    }
                }
            }
            if (p.echeance) {
                pieces.push(M("panneau", x + 4.6, y - 3.8, { couleur: T.orange }));
            }
            element(pieces, { titre: `${p.nom} — ${p.client} — ${p.type_libelle} — ${p.etat_libelle}${p.surface ? " — " + p.surface + " ha" : ""}${p.commune ? " — " + p.commune : ""}${p.echeance ? " — " + p.echeance : ""}`,
                              etiquette: p.client, ou: [x, y + 4.3, 1.5], action: this.fiche("cultiveau.installation", p.id), classe: p.echeance ? "alerte" : "" });
        });
        this.jets = jets;
        this.sols = sols;
        this.objets = objets;
        this.libelles = libelles;
        this.postes = postes;
    }

    // ------------------------------------------------------------------ le monde en 3D

    initialiser() {
        const THREE = window.THREE;
        const hote = this.hote.el;
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        hote.appendChild(renderer.domElement);
        const scene = new THREE.Scene();
        const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, -400, 800);
        this.t3 = { THREE, renderer, scene, camera, raycaster: new THREE.Raycaster(), cibles: [], sols: [], anim: [], horloge: performance.now(), debut: performance.now() };
        this.lib = bibliotheque(THREE);
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.05;

        // la lumière : un ciel clair et un soleil bas qui dessine des ombres douces
        scene.add(new THREE.HemisphereLight(0xf4f8ff, 0xd9cdb2, 2.2));
        const soleil = new THREE.DirectionalLight(0xfff1d6, 3.2);
        soleil.position.set(-12, 55, 6);
        soleil.target.position.set(24, 0, 30);
        soleil.castShadow = true;
        soleil.shadow.mapSize.set(4096, 4096);
        Object.assign(soleil.shadow.camera, { left: -55, right: 55, top: 55, bottom: -55, near: 1, far: 160 });
        soleil.shadow.bias = -0.0005;
        soleil.shadow.normalBias = 0.02;
        scene.add(soleil, soleil.target);
        // le sol autour du site
        const plaine = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshStandardMaterial({ color: 0xcfe3ad, roughness: 1 }));
        plaine.rotation.x = -Math.PI / 2;
        plaine.position.set(24, -0.05, 30);
        plaine.receiveShadow = true;
        scene.add(plaine);

        // les sols (zones cliquables), les objets, les postes
        for (const s of this.sols) {
            const m = this.maillage(s.faces, false);
            m.material.roughness = 0.95;
            m.receiveShadow = true;
            m.userData = { sol: s };
            scene.add(m);
            if (s.zone) {
                this.t3.sols.push(m);
            }
        }
        for (const o of this.objets) {
            const groupe = this.objet3d(o);
            if (groupe) {
                scene.add(groupe);
            }
        }
        // l'anneau de sélection, sous le poste ouvert
        const anneau = new THREE.Mesh(new THREE.RingGeometry(1.3, 1.65, 48), new THREE.MeshBasicMaterial({ color: 0x0b9bb8, transparent: true, opacity: 0.9, depthWrite: false }));
        anneau.rotation.x = -Math.PI / 2;
        anneau.visible = false;
        scene.add(anneau);
        this.t3.anneau = anneau;
        this.arrosage();

        // la caméra : on arrive de loin, en tournant, et on se pose sur le site
        this.cam = { x: 24, z: 30, hauteur: 60, azimut: Math.PI / 4 };
        const cible = this.cadrer(TOUT);
        this.cam = { ...cible, hauteur: cible.hauteur * 2.2, azimut: Math.PI / 4 + 0.9 };
        this.voler(cible, 2200);

        this.creerEtiquettes();
        this.mesurer();
        this._observateur = new ResizeObserver(() => this.mesurer());
        this._observateur.observe(hote);
        this.ecouter(renderer.domElement);
        this.state.pret = true;
        const boucle = (t) => {
            this._boucle = requestAnimationFrame(boucle);
            this.image(t);
        };
        this._boucle = requestAnimationFrame(boucle);
    }

    detruire() {
        cancelAnimationFrame(this._boucle);
        this._observateur?.disconnect();
        window.removeEventListener("keydown", this._clavier);
        if (this.t3) {
            this.t3.scene.traverse((o) => {
                o.geometry?.dispose();
                if (o.material) {
                    [].concat(o.material).forEach((m) => m.dispose());
                }
            });
            this.t3.renderer.dispose();
            this.t3.renderer.domElement.remove();
            this.t3 = null;
        }
    }

    /** Une géométrie unique pour une liste de pavés (couleurs aux sommets). */
    geometrie(boites) {
        const THREE = this.t3.THREE;
        if (!this._cube) {
            this._cube = new THREE.BoxGeometry(1, 1, 1).toNonIndexed();
        }
        const base = this._cube.attributes.position.array, normales = this._cube.attributes.normal.array, n = base.length / 3;
        const pos = new Float32Array(boites.length * n * 3), nor = new Float32Array(boites.length * n * 3), col = new Float32Array(boites.length * n * 3);
        const couleur = new THREE.Color();
        let i = 0;
        for (const b of boites) {
            couleur.set(b.c);
            for (let v = 0; v < n; v++) {
                pos[i] = b.x + (base[v * 3] + 0.5) * b.w;
                pos[i + 1] = b.z + (base[v * 3 + 1] + 0.5) * b.h;
                pos[i + 2] = b.y + (base[v * 3 + 2] + 0.5) * b.d;
                nor[i] = normales[v * 3];
                nor[i + 1] = normales[v * 3 + 1];
                nor[i + 2] = normales[v * 3 + 2];
                col[i] = couleur.r;
                col[i + 1] = couleur.g;
                col[i + 2] = couleur.b;
                i += 3;
            }
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        g.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
        g.setAttribute("color", new THREE.BufferAttribute(col, 3));
        g.computeBoundingBox();
        return g;
    }

    maillage(boites, ombre = true, rendu = "") {
        const THREE = this.t3.THREE;
        const g = this.geometrie(boites);
        const bb = g.boundingBox;
        const cx = (bb.min.x + bb.max.x) / 2, cz = (bb.min.z + bb.max.z) / 2, y0 = bb.min.y;
        g.translate(-cx, -y0, -cz);
        const options = { vertexColors: true, roughness: 0.85, metalness: 0.02 };
        if (rendu === "verre") {
            Object.assign(options, { transparent: true, opacity: 0.35, roughness: 0.1, depthWrite: false });
        } else if (rendu === "toit") {
            Object.assign(options, { transparent: true, opacity: 0.55, depthWrite: false });
        } else if (rendu === "nuage") {
            // un nuage invisible : seule son ombre passe sur le site
            Object.assign(options, { colorWrite: false, depthWrite: false });
        }
        const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial(options));
        m.position.set(cx, y0, cz);
        m.castShadow = ombre;
        m.receiveShadow = rendu !== "nuage";
        return m;
    }

    /** Fusionne les maillages fixes d'un groupe, par matière : quelques appels de dessin au lieu de dizaines. */
    fusionner(groupe, garder) {
        const THREE = this.t3.THREE;
        groupe.updateMatrixWorld(true);
        const inverse = new THREE.Matrix4().copy(groupe.matrixWorld).invert();
        const parMatiere = new Map();
        const aRetirer = [];
        groupe.traverse((o) => {
            if (!o.isMesh || o.userData.garde) {
                return;
            }
            for (let p = o.parent; p && p !== groupe; p = p.parent) {
                if (garder.has(p.name)) {
                    return;
                }
            }
            const g = (o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone());
            g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inverse, o.matrixWorld));
            for (const nom of Object.keys(g.attributes)) {
                if (!["position", "normal"].includes(nom)) {
                    g.deleteAttribute(nom);
                }
            }
            const cle = o.material.uuid;
            if (!parMatiere.has(cle)) {
                parMatiere.set(cle, { matiere: o.material, geos: [], ombre: false });
            }
            const lot = parMatiere.get(cle);
            lot.geos.push(g);
            lot.ombre = lot.ombre || o.castShadow;
            aRetirer.push(o);
        });
        for (const o of aRetirer) {
            o.parent.remove(o);
        }
        for (const { matiere, geos, ombre } of parMatiere.values()) {
            const total = geos.reduce((s, g) => s + g.attributes.position.count, 0);
            const pos = new Float32Array(total * 3), nor = new Float32Array(total * 3);
            let i = 0;
            for (const g of geos) {
                pos.set(g.attributes.position.array, i);
                nor.set(g.attributes.normal.array, i);
                i += g.attributes.position.array.length;
                g.dispose();
            }
            const g = new THREE.BufferGeometry();
            g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
            g.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
            const m = new THREE.Mesh(g, matiere);
            m.castShadow = ombre;
            m.receiveShadow = true;
            groupe.add(m);
        }
    }

    objet3d(o) {
        const THREE = this.t3.THREE;
        const boites = o.faces.filter((b) => !b.m);
        const modeles = o.faces.filter((b) => b.m);
        if (!boites.length && !modeles.length) {
            return null;
        }
        // la base de l'objet : le centre de son emprise
        const xs = [...boites.flatMap((b) => [b.x, b.x + b.w]), ...modeles.map((m) => m.x)];
        const ys = [...boites.flatMap((b) => [b.y, b.y + b.d]), ...modeles.map((m) => m.y)];
        const base = new THREE.Vector3((Math.min(...xs) + Math.max(...xs)) / 2, 0, (Math.min(...ys) + Math.max(...ys)) / 2);
        const groupe = new THREE.Group();
        groupe.position.copy(base);
        if (boites.length) {
            const m = this.maillage(boites, !["verre", "toit"].includes(o.classe), o.classe);
            m.position.sub(base);
            m.userData.garde = true; // déjà d'un seul tenant, avec ses couleurs aux sommets
            groupe.add(m);
        }
        const mobile = ["route", "route2", "passant", "chariot", "garer"].includes(o.classe);
        for (const md of modeles) {
            const fabrique = this.lib.M[md.m];
            if (!fabrique) {
                continue;
            }
            const g = fabrique(md.o || {});
            g.position.set(md.x - base.x, md.z || 0, md.y - base.z);
            g.rotation.y = md.rot || 0;
            groupe.add(g);
        }
        // les pièces animées restent à part : le bras des pivots, les roues de ce qui roule
        const garder = new Set(mobile ? ["bras", "roue", "gyrophare", "fumee"] : ["bras", "gyrophare", "fumee"]);
        const bras = [], gyros = [], fumees = [];
        groupe.traverse((x) => (x.name === "bras" && bras.push(x)) || (x.name === "gyrophare" && gyros.push(x)) || (x.name === "fumee" && fumees.push(x)));
        if (o.classe !== "nuage" && o.classe !== "verre" && o.classe !== "toit") {
            this.fusionner(groupe, garder);
        }
        for (const b of bras) {
            this.t3.anim.push({ genre: "pivot", objet: b, vitesse: 0.22 + Math.random() * 0.15, phase: Math.random() * 6 });
        }
        for (const gy of gyros) {
            gy.traverse((x) => x.isMesh && (x.material = x.material.clone()));
            this.t3.anim.push({ genre: "gyrophare", objet: gy, phase: Math.random() * 6 });
        }
        for (const f of fumees) {
            f.children.forEach((b) => (b.material = b.material.clone()));
            this.t3.anim.push({ genre: "fumee", objet: f });
        }
        if (mobile) {
            const roues = [];
            groupe.traverse((x) => x.name === "roue" && roues.push(x));
            groupe.userData.roues = roues;
        }
        const pickable = o.genre === "poste" || (o.genre === "element" && o.action);
        groupe.userData = { ...groupe.userData, objet: o, base: base.clone(), leve: 0 };
        if (pickable) {
            // chaque objet cliquable a ses propres matières, pour s'éclairer au survol
            const matieres = [];
            groupe.traverse((x) => {
                if (x.isMesh) {
                    x.material = x.material.clone();
                    matieres.push(x.material);
                }
            });
            groupe.userData.matieres = matieres;
            this.t3.cibles.push(groupe);
        }
        // l'arrivée : chaque objet surgit à son tour, de l'entrée vers le fond du site
        const retard = 0.3 + Math.min(1.7, ((base.x + base.z) / 110) * 1.7) + (o.genre === "decor" ? 0 : 0.25);
        if (o.classe === "garer") {
            groupe.visible = false;
            this.t3.anim.push({ genre: "garer", objet: groupe, retard: 0.6 + (this.t3.anim.filter((a) => a.genre === "garer").length) * 0.22 });
        } else if (!["nuage", "route", "route2", "passant", "chariot"].includes(o.classe)) {
            groupe.scale.set(0.001, 0.001, 0.001);
            this.t3.anim.push({ genre: "pop", objet: groupe, retard });
        }
        const anim = { route: "route", route2: "route2", passant: "passant", chariot: "chariot", nuage: "nuage", etincelle: "etincelle", personne: "respire", alerte: "alerte" }[o.classe];
        if (anim) {
            this.t3.anim.push({ genre: anim, objet: groupe, phase: Math.random() * 10, rang: this.t3.anim.filter((a) => a.genre === anim).length });
        }
        if (o.genre === "poste") {
            o.poste.groupe = groupe;
        }
        return groupe;
    }

    arrosage() {
        // l'eau : des gouttes qui partent en arc, en tournant (asperseurs) ou en long jet (canon d'enrouleur)
        const THREE = this.t3.THREE;
        const jets = this.jets || [];
        if (!jets.length) {
            return;
        }
        const parJet = 60;
        const g = new THREE.BufferGeometry();
        g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(jets.length * parJet * 3), 3));
        const points = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xbdeefa, size: 3.2, sizeAttenuation: false, transparent: true, opacity: 0.9, depthWrite: false }));
        points.frustumCulled = false;
        this.t3.scene.add(points);
        this.t3.jets = { points, jets, parJet };
    }

    // ------------------------------------------------------------------ chaque image

    image(t) {
        const t3 = this.t3;
        if (!t3) {
            return;
        }
        const dt = Math.min(0.05, (t - t3.horloge) / 1000);
        t3.horloge = t;
        const temps = (t - t3.debut) / 1000;
        this.animerCamera(t);
        const rouler = (o, distance) => {
            for (const r of o.userData.roues || []) {
                r.rotation.z = -distance / (r.userData.rayon || 0.4);
            }
        };
        for (const a of t3.anim) {
            const o = a.objet;
            switch (a.genre) {
                case "pop": {
                    const k = Math.max(0, Math.min(1, (temps - a.retard) / 0.6));
                    const e = k <= 0 ? 0.001 : rebond(k);
                    o.scale.set(Math.max(0.001, 0.7 + 0.3 * e), Math.max(0.001, e), Math.max(0.001, 0.7 + 0.3 * e));
                    if (k >= 1) {
                        o.scale.set(1, 1, 1);
                        a.fini = true;
                    }
                    break;
                }
                case "pivot":
                    o.rotation.y = -(temps * a.vitesse + a.phase);
                    break;
                case "garer": {
                    // entre par l'allée en marche avant, ralentit, le nez plonge au freinage, puis se pose
                    const k = Math.max(0, Math.min(1, (temps - a.retard) / 1.5));
                    o.visible = temps >= a.retard;
                    const e = 1 - Math.pow(1 - k, 3);
                    const recul = 4.6 * (1 - e);
                    const b = o.userData.base;
                    o.position.x = b.x;
                    o.position.z = b.z + recul;
                    o.rotation.x = -0.06 * Math.sin(Math.PI * Math.max(0, Math.min(1, (k - 0.7) / 0.3)));
                    rouler(o, e * 4.6);
                    if (k >= 1) {
                        o.position.z = b.z;
                        o.rotation.x = 0;
                        a.fini = true;
                    }
                    break;
                }
                case "gyrophare": {
                    o.rotation.y = temps * 5 + a.phase;
                    const flash = (Math.sin(temps * 10 + a.phase) + 1) / 2;
                    o.traverse((x) => x.isMesh && (x.material.emissiveIntensity = 0.25 + flash * 0.9));
                    break;
                }
                case "fumee":
                    o.children.forEach((b, i) => {
                        const vie = (temps * 0.55 + i / o.children.length) % 1;
                        b.position.set(-vie * 0.5, vie * 1.4, 0);
                        b.scale.setScalar(0.5 + vie * 1.6);
                        b.material.opacity = 0.55 * (1 - vie);
                    });
                    break;
                case "route": {
                    const d = temps * 7 + 20;
                    o.position.set((d % 75) - 13, 0, 39.0);
                    rouler(o, d);
                    break;
                }
                case "route2": {
                    const d = temps * 5;
                    o.position.set(63 - (d % 82), 0, 40.8);
                    o.rotation.y = Math.PI;
                    rouler(o, d);
                    break;
                }
                case "chariot": {
                    const k = (Math.sin(temps * 0.4) + 1) / 2;
                    o.position.set(16.5 + k * 12.5, 0, 12.6);
                    o.rotation.y = Math.cos(temps * 0.4) > 0 ? 0 : Math.PI;
                    rouler(o, k * 12.5);
                    break;
                }
                case "passant": {
                    // du parking à la porte du magasin
                    const chemin = [[3.2, 37.4], [5.6, 30.4], [6.8, 24.5], [7.0, 21.8]];
                    const k = ((temps * 0.07 + a.rang / 3) % 1) * (chemin.length - 1);
                    const i = Math.min(chemin.length - 2, Math.floor(k)), f = k - i;
                    const p = chemin[i], q = chemin[i + 1];
                    o.position.set(p[0] + (q[0] - p[0]) * f, Math.abs(Math.sin(temps * 8 + a.rang)) * 0.06, p[1] + (q[1] - p[1]) * f);
                    o.rotation.y = Math.atan2(q[0] - p[0], q[1] - p[1]) - Math.PI / 2;
                    o.scale.setScalar(Math.max(0.001, Math.min(1, k * 3, (chemin.length - 1 - k) * 3)));
                    break;
                }
                case "nuage": {
                    const x = ((temps * 1.3 + a.rang * 30) % 100) - 30;
                    o.position.set(x, 22, 6 + a.rang * 19);
                    break;
                }
                case "respire":
                    o.position.y = o.userData.base.y + o.userData.leve + Math.abs(Math.sin(temps * 1.6 + a.phase)) * 0.05;
                    break;
                case "etincelle":
                    o.visible = Math.sin(temps * 37 + Math.sin(temps * 11) * 3) > 0.2;
                    break;
                case "alerte":
                    for (const m of o.userData.matieres || []) {
                        m.emissive.setRGB(0.55, 0.08, 0.04);
                        m.emissiveIntensity = ((Math.sin(temps * 4) + 1) / 2) * 0.35;
                    }
                    break;
            }
        }
        t3.anim = t3.anim.filter((a) => !a.fini);
        // le survol : l'objet se lève et s'éclaire
        for (const g of t3.cibles) {
            const actif = g === this._survole || (this.state.carte && this.state.carte.groupe === g);
            const vise = actif ? 0.4 : 0;
            if (Math.abs(vise - g.userData.leve) < 0.002 && !actif && !g.userData.enCours) {
                continue;
            }
            g.userData.leve += (vise - g.userData.leve) * Math.min(1, dt * 12);
            g.userData.enCours = Math.abs(vise - g.userData.leve) > 0.002;
            if (g.userData.objet.classe !== "personne") {
                g.position.y = g.userData.base.y + g.userData.leve;
            }
            if (g.userData.objet.classe !== "alerte") {
                for (const m of g.userData.matieres || []) {
                    m.emissive.setRGB(0.05, 0.32, 0.4);
                    m.emissiveIntensity = g.userData.leve * 0.9;
                }
            }
        }
        // l'anneau sous le poste ouvert
        const p = this.state.carte;
        t3.anneau.visible = !!p;
        if (p) {
            t3.anneau.position.set(p.ancre[0], 0.06, p.ancre[1]);
            t3.anneau.scale.setScalar(1 + Math.sin(temps * 4) * 0.08);
            t3.anneau.material.opacity = 0.65 + Math.sin(temps * 4) * 0.25;
        }
        // l'eau
        if (t3.jets) {
            const { points, jets, parJet } = t3.jets;
            const pos = points.geometry.attributes.position.array;
            let i = 0;
            jets.forEach((j, n) => {
                for (let k = 0; k < parJet; k++) {
                    const vie = (temps * (j.canon ? 0.6 : 0.9) + k / parJet) % 1;
                    let angle, r, h;
                    if (j.canon) {
                        // le canon balaie un secteur et envoie loin
                        angle = Math.PI + Math.sin(temps * 0.5 + n) * 0.6 + ((k % 5) - 2) * 0.03;
                        r = vie * j.r * 1.6;
                        h = j.h + Math.sin(vie * Math.PI) * 2.6 - vie * 0.6;
                    } else {
                        angle = temps * 0.9 + n * 1.7 + Math.floor((k * 3) / parJet) * 2.09;
                        r = vie * j.r;
                        h = j.h + Math.sin(vie * Math.PI) * j.r * 0.45;
                    }
                    pos[i++] = j.x + Math.cos(angle) * r;
                    pos[i++] = Math.max(0.15, h);
                    pos[i++] = j.y + Math.sin(angle) * r;
                }
            });
            points.geometry.attributes.position.needsUpdate = true;
        }
        t3.renderer.render(t3.scene, t3.camera);
        this.placerEtiquettes();
    }

    // ------------------------------------------------------------------ la caméra

    mesurer() {
        const el = this.hote.el;
        if (!el || !this.t3) {
            return;
        }
        const r = el.getBoundingClientRect();
        this.taille = { w: Math.max(1, r.width), h: Math.max(1, r.height) };
        this.t3.renderer.setSize(this.taille.w, this.taille.h, false);
        this.t3.renderer.domElement.style.width = "100%";
        this.t3.renderer.domElement.style.height = "100%";
        this.appliquerCamera();
    }

    axes(azimut = this.cam.azimut) {
        // r : la droite de l'écran au sol ; f : vers le fond de l'écran, au sol (repère du plan : x, y)
        return { r: [Math.cos(azimut), -Math.sin(azimut)], f: [-Math.sin(azimut), -Math.cos(azimut)] };
    }

    appliquerCamera() {
        const t3 = this.t3;
        if (!t3 || !this.taille) {
            return;
        }
        const { x, z, hauteur, azimut } = this.cam;
        const R = 200, cam = t3.camera;
        cam.position.set(x + R * Math.sin(azimut) * Math.cos(ELEVATION), R * Math.sin(ELEVATION), z + R * Math.cos(azimut) * Math.cos(ELEVATION));
        cam.lookAt(x, 0, z);
        const ratio = this.taille.w / this.taille.h;
        Object.assign(cam, { left: (-hauteur * ratio) / 2, right: (hauteur * ratio) / 2, top: hauteur / 2, bottom: -hauteur / 2 });
        cam.updateProjectionMatrix();
        const classe = hauteur < 26 ? "proche" : hauteur < 48 ? "moyen" : "loin";
        if (this.calque.el && this._classe !== classe) {
            this.calque.el.className = "o_cv3_calque " + classe;
            this._classe = classe;
        }
    }

    /** La caméra qui montre la boîte [x0, y0, x1, y1] du plan (en mètres), avec l'azimut donné. */
    cadrer(box, azimut = Math.PI / 4, marge = 1.12) {
        const [x0, y0, x1, y1] = box;
        const { r, f } = this.axes(azimut);
        const coins = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
        const sx = coins.map(([x, y]) => x * r[0] + y * r[1]);
        const sy = coins.map(([x, y]) => (x * f[0] + y * f[1]) * Math.sin(ELEVATION));
        const largeur = Math.max(...sx) - Math.min(...sx), haut = Math.max(...sy) - Math.min(...sy) + 4 * Math.cos(ELEVATION);
        const ratio = this.taille ? this.taille.w / this.taille.h : 1.6;
        return { x: (x0 + x1) / 2, z: (y0 + y1) / 2, hauteur: Math.max(haut, largeur / ratio) * marge, azimut };
    }

    voler(cible, duree = 900) {
        this._vol = { de: { ...this.cam }, vers: { ...cible }, t0: performance.now(), duree };
    }

    animerCamera(t) {
        const v = this._vol;
        if (v) {
            const k = Math.min(1, (t - v.t0) / v.duree);
            const e = facile(k);
            for (const cle of ["x", "z", "hauteur", "azimut"]) {
                this.cam[cle] = v.de[cle] + (v.vers[cle] - v.de[cle]) * e;
            }
            if (k >= 1) {
                this._vol = null;
            }
        }
        this.appliquerCamera();
    }

    allerZone(zone) {
        this.state.carte = null;
        this.state.zone = zone.cle;
        if (this.t3) {
            this.voler(this.cadrer(zone.box, this.cam.azimut, 1.05));
        }
    }

    toutVoir() {
        this.state.carte = null;
        this.state.zone = null;
        if (this.t3) {
            this.voler(this.cadrer(TOUT, this.cam.azimut));
        }
    }

    tourner(sens) {
        if (!this.t3) {
            return;
        }
        const base = this._vol ? this._vol.vers : this.cam;
        this.voler({ ...base, azimut: base.azimut + (sens * Math.PI) / 2 }, 800);
    }

    zoomer(facteur, ev = null) {
        if (!this.t3) {
            return;
        }
        this._vol = null;
        const avant = ev ? this.auSol(ev) : null;
        this.cam.hauteur = Math.min(160, Math.max(7, this.cam.hauteur * facteur));
        this.appliquerCamera();
        if (avant) {
            const apres = this.auSol(ev);
            if (apres) {
                this.cam.x += avant.x - apres.x;
                this.cam.z += avant.z - apres.z;
            }
        }
    }

    ndc(ev) {
        const r = this.t3.renderer.domElement.getBoundingClientRect();
        return new this.t3.THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    }

    auSol(ev) {
        const THREE = this.t3.THREE;
        this.t3.raycaster.setFromCamera(this.ndc(ev), this.t3.camera);
        const p = new THREE.Vector3();
        return this.t3.raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), p) ? p : null;
    }

    viser(ev) {
        this.t3.raycaster.setFromCamera(this.ndc(ev), this.t3.camera);
        const touche = this.t3.raycaster.intersectObjects(this.t3.cibles, true)[0];
        let o = touche ? touche.object : null;
        while (o && !o.userData.objet) {
            o = o.parent;
        }
        return o;
    }

    ecouter(canvas) {
        canvas.addEventListener("wheel", (ev) => {
            ev.preventDefault();
            this.zoomer(Math.exp(ev.deltaY * 0.0012), ev);
        }, { passive: false });
        canvas.addEventListener("pointerdown", (ev) => {
            if (ev.button !== 0) {
                return;
            }
            this._vol = null;
            this._glisse = { x: ev.clientX, y: ev.clientY, cam: { ...this.cam }, bouge: false };
            canvas.setPointerCapture(ev.pointerId);
        });
        canvas.addEventListener("pointermove", (ev) => {
            const g = this._glisse;
            if (g) {
                const dx = ev.clientX - g.x, dy = ev.clientY - g.y;
                if (g.bouge || Math.hypot(dx, dy) > 5) {
                    g.bouge = true;
                    const echelle = g.cam.hauteur / this.taille.h;
                    const { r, f } = this.axes(g.cam.azimut);
                    const dr = dx * echelle, df = (dy * echelle) / Math.sin(ELEVATION);
                    this.cam.x = g.cam.x - r[0] * dr + f[0] * df;
                    this.cam.z = g.cam.z - r[1] * dr + f[1] * df;
                    return;
                }
            }
            const vise = this.viser(ev);
            if (vise !== this._survole) {
                this._survole = vise;
                const o = vise && vise.userData.objet;
                this.state.survol = o ? (o.genre === "poste" ? `${o.poste.titre} — ${o.poste.texte}` : o.titre) : null;
                canvas.style.cursor = vise ? "pointer" : "grab";
            }
            if (this.bulle.el) {
                const r = this.hote.el.getBoundingClientRect();
                this.bulle.el.style.transform = `translate(${ev.clientX - r.left + 16}px, ${ev.clientY - r.top + 18}px)`;
            }
        });
        canvas.addEventListener("pointerup", (ev) => {
            const g = this._glisse;
            this._glisse = null;
            if (g && !g.bouge) {
                this.clic(ev);
            }
        });
        canvas.addEventListener("pointerleave", () => {
            this._survole = null;
            this.state.survol = null;
        });
    }

    clic(ev) {
        const vise = this.viser(ev);
        if (vise) {
            const o = vise.userData.objet;
            if (o.genre === "poste") {
                this.ouvrirPoste(o.poste);
            } else if (o.action) {
                this.action.doAction(o.action);
            }
            return;
        }
        if (this.state.carte) {
            this.state.carte = null;
            return;
        }
        // un clic sur une zone : on y vole
        this.t3.raycaster.setFromCamera(this.ndc(ev), this.t3.camera);
        const sol = this.t3.raycaster.intersectObjects(this.t3.sols, false)[0];
        const zone = sol && ZONES.find((z) => z.cle === sol.object.userData.sol.zone);
        if (zone && zone.cle !== this.state.zone) {
            this.allerZone(zone);
        }
    }

    onClavier(ev) {
        if (ev.target.closest?.("input, textarea, .o_dialog")) {
            if (ev.key === "Escape") {
                this.state.recherche = "";
                this.state.resultats = [];
            }
            return;
        }
        const touches = { Escape: () => (this.state.carte = null), "+": () => this.zoomer(0.8), "=": () => this.zoomer(0.8), "-": () => this.zoomer(1.25),
                          0: () => this.toutVoir(), q: () => this.tourner(-1), e: () => this.tourner(1) };
        const f = touches[ev.key] || touches[ev.key.toLowerCase?.()];
        if (f && document.contains(this.hote.el)) {
            f();
        }
    }

    // ------------------------------------------------------------------ les étiquettes (HTML posé sur la 3D)

    creerEtiquettes() {
        const calque = this.calque.el;
        calque.innerHTML = "";
        this.etiquettes = [];
        const ajouter = (html, classe, p, clic) => {
            const el = document.createElement("div");
            el.className = classe;
            el.innerHTML = html;
            if (clic) {
                el.addEventListener("click", (ev) => {
                    ev.stopPropagation();
                    clic();
                });
            }
            calque.appendChild(el);
            this.etiquettes.push({ el, p });
            return el;
        };
        for (const l of this.libelles) {
            ajouter(echapper(l.texte), "o_cv3_libelle " + l.genre, l.p);
        }
        for (const p of this.postes) {
            const badge = p.badge ? `<span class="badge-cv3${p.urgent ? " urgent" : ""}">${p.badge > 999 ? Math.round(p.badge / 1000) + "k" : p.badge}</span>` : "";
            p.etiquette = ajouter(`<span class="ic" style="background:${p.couleur}"><i class="fa ${p.icone}"></i></span><span class="t">${echapper(p.titre)}</span>${badge}`,
                                  "o_cv3_poste", [p.ancre[0], p.ancre[1], p.haut + 0.6], () => this.ouvrirPoste(p));
        }
    }

    ecran(x, y, z) {
        const v = new this.t3.THREE.Vector3(x, z, y).project(this.t3.camera);
        return [((v.x + 1) / 2) * this.taille.w, ((1 - v.y) / 2) * this.taille.h, v.z];
    }

    placerEtiquettes() {
        if (!this.etiquettes || !this.taille) {
            return;
        }
        for (const e of this.etiquettes) {
            const [sx, sy] = this.ecran(e.p[0], e.p[1], e.p[2]);
            const dehors = sx < -100 || sy < -60 || sx > this.taille.w + 100 || sy > this.taille.h + 60;
            e.el.style.display = dehors ? "none" : "";
            if (!dehors) {
                e.el.style.transform = `translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px)`;
            }
        }
        const p = this.state.carte;
        const el = this.carteRef.el;
        if (p && el) {
            const [sx, sy] = this.ecran(p.ancre[0], p.ancre[1], p.haut);
            const largeur = 330;
            let left = sx + 40;
            if (left + largeur > this.taille.w - 12) {
                left = Math.max(12, sx - largeur - 40);
            }
            const top = Math.max(12, Math.min(this.taille.h - el.offsetHeight - 12, sy - 70));
            el.style.left = `${left}px`;
            el.style.top = `${top}px`;
        }
    }

    // ------------------------------------------------------------------ ouvrir

    ouvrirPoste(p, voler = true) {
        this.state.carte = p;
        this.state.recherche = "";
        this.state.resultats = [];
        if (voler && this.t3) {
            // on s'approche du poste en le gardant à gauche, pour laisser la place à la carte
            const hauteur = Math.min(this.cam.hauteur, 24);
            const { r } = this.axes(this.cam.azimut);
            const decale = (hauteur * (this.taille.w / this.taille.h)) * 0.14;
            this.voler({ x: p.ancre[0] + r[0] * decale, z: p.ancre[1] + r[1] * decale, hauteur, azimut: this.cam.azimut }, 850);
        }
    }

    async lancer(a, p = this.state.carte) {
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
        for (const p of this.postes) {
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

    // ------------------------------------------------------------------ l'en-tête, la vue sans 3D

    get zones() {
        return ZONES;
    }

    get postesParZone() {
        return ZONES.map((z) => ({ ...z, postes: this.postes.filter((p) => p.zone === z.cle) })).filter((z) => z.postes.length);
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
}

registry.category("actions").add("cultiveau_vue3d.vue", VueEnsemble);
