/** @odoo-module **/
// L'éditeur de schéma de câblage, ouvert depuis l'armoire de l'atelier (Map vivante).
// On pose des appareils sur la grille, on tire des fils de borne à borne ; le matériel, la liste des fils et les
// contrôles du référentiel (§ 11.2 et 11.3) se recalculent à chaque geste. Le calcul est dans schema_calcul.js.

import { Component, onMounted, onWillStart, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { APPAREILS, FAMILLES, PAS, SECTIONS, analyser, exemple, fr, milieu, numeroSuivant, positionBorne, repereSuivant, trace } from "./schema_calcul";

const MODELE = "cultiveau.schema.cablage";
const COULEURS = { puissance: "#1d2f38", commande: "#0b7fa3", terre: "#3f9b3a" };
const cale = (v) => Math.round(v / PAS) * PAS;

export class SchemaCablage extends Component {
    static template = "cultiveau_vue3d.Schema";
    static props = { ...standardActionServiceProps };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.toile = useRef("toile");
        this.PAS = PAS;
        this.APPAREILS = APPAREILS;
        this.SECTIONS = SECTIONS;
        this.fr = fr;
        this.palette = FAMILLES.map((famille) => ({
            famille,
            appareils: Object.entries(APPAREILS).filter(([, a]) => a.famille === famille).map(([cle, a]) => ({ cle, nom: a.nom })),
        }));
        this.state = useState({
            id: false, nom: "Nouveau schéma", composants: [], fils: [],
            selection: null,      // { genre: "c" | "f", id }
            depart: null,         // la borne d'où part le fil en cours : { c, b }
            souris: { x: 0, y: 0 },
            vue: { x: 40, y: 20, z: 1 },
            onglet: "proprietes",
            modifie: false, message: "", liste: null, aSupprimer: false, peutAnnuler: false,
        });
        this.historique = [];
        this.geste = null;
        this.compteur = 1;
        useExternalListener(window, "keydown", (ev) => this.clavier(ev));
        onWillStart(async () => {
            const params = (this.props.action && this.props.action.params) || {};
            if (params.schema_id) await this.ouvrir(params.schema_id);
        });
        onMounted(() => this.cadrer());
    }

    // ---------------------------------------------------------------- le dessin

    get schema() { return { composants: this.state.composants, fils: this.state.fils }; }
    get analyse() { return analyser(this.schema); }
    get transform() { const v = this.state.vue; return `translate(${v.x},${v.y}) scale(${v.z})`; }
    get selectionne() {
        const s = this.state.selection;
        if (!s) return null;
        return (s.genre === "c" ? this.state.composants : this.state.fils).find((x) => x.id === s.id) || null;
    }
    get alertes() { return this.analyse.controles.filter((c) => c.etat === "alerte").length; }

    def(c) { return APPAREILS[c.type]; }
    estChoisi(genre, id) { const s = this.state.selection; return !!s && s.genre === genre && s.id === id; }
    bornes(c) {
        return APPAREILS[c.type].bornes.map((b) => {
            const d = { haut: [0, -11, "middle"], bas: [0, 17, "middle"], gauche: [-6, -5, "end"], droite: [6, -5, "start"] }[b.dir];
            return { ...b, px: b.x * PAS, py: b.y * PAS, tx: b.x * PAS + d[0] + (b.dir === "haut" || b.dir === "bas" ? 12 : 0), ty: b.y * PAS + d[1], ancre: b.dir === "haut" || b.dir === "bas" ? "start" : d[2],
                     nom: ["amont", "aval"].includes(b.id) ? "" : b.id };
        });
    }
    valeur(c) {
        const v = c.valeurs || {};
        return APPAREILS[c.type].champs.filter((ch) => v[ch.cle]).map((ch) => (ch.unite ? `${v[ch.cle]} ${ch.unite}` : v[ch.cle])).join(" · ");
    }
    get filsTraces() {
        const parId = Object.fromEntries(this.state.composants.map((c) => [c.id, c]));
        const genres = this.analyse.genres;
        return this.state.fils.map((f) => {
            const p = parId[f.de.c] && positionBorne(parId[f.de.c], f.de.b);
            const q = parId[f.a.c] && positionBorne(parId[f.a.c], f.a.b);
            if (!p || !q) return null;
            const pts = trace(p, q, f.decal || 0);
            const m = milieu(pts);
            const genre = genres[f.id];
            return { id: f.id, num: f.num, d: "M" + pts.map((pt) => pt.join(",")).join("L"), mx: m.x, my: m.y, couleur: COULEURS[genre],
                     epaisseur: genre === "puissance" ? 3 : 1.8, tirets: genre === "terre" ? "7 4" : "", p, q };
        }).filter(Boolean);
    }
    get filEnCours() {
        const d = this.state.depart;
        if (!d) return "";
        const c = this.state.composants.find((x) => x.id === d.c);
        const p = c && positionBorne(c, d.b);
        return p ? `M${p.x},${p.y}L${this.state.souris.x},${this.state.souris.y}` : "";
    }

    // ---------------------------------------------------------------- les gestes

    monde(ev) {
        const r = this.toile.el.getBoundingClientRect();
        const v = this.state.vue;
        return { x: (ev.clientX - r.left - v.x) / v.z, y: (ev.clientY - r.top - v.y) / v.z };
    }
    memoriser() {
        this.historique.push(JSON.stringify(this.schema));
        if (this.historique.length > 60) this.historique.shift();
        this.state.peutAnnuler = true;
        this.state.modifie = true;
        this.state.message = "";
    }
    annuler() {
        const avant = this.historique.pop();
        if (!avant) return;
        const s = JSON.parse(avant);
        this.state.composants = s.composants;
        this.state.fils = s.fils;
        this.state.selection = null;
        this.state.depart = null;
        this.state.peutAnnuler = this.historique.length > 0;
        this.state.modifie = true;
    }
    identifiant(prefixe) {
        const pris = new Set([...this.state.composants, ...this.state.fils].map((x) => x.id));
        let id;
        do { id = prefixe + this.compteur++; } while (pris.has(id));
        return id;
    }
    poser(type, x, y) {
        const def = APPAREILS[type];
        this.memoriser();
        if (x === undefined) {
            // vers le milieu de l'écran
            const r = this.toile.el.getBoundingClientRect();
            const v = this.state.vue;
            x = cale((r.width / 2 - v.x) / v.z - def.l * PAS / 2);
            y = cale((r.height / 3 - v.y) / v.z);
            // la première place libre, en allant vers la droite
            const pris = (px, py) => this.state.composants.some((c) => px < c.x + APPAREILS[c.type].l * PAS + 80 && px + def.l * PAS + 80 > c.x && py < c.y + APPAREILS[c.type].h * PAS + 20 && py + def.h * PAS + 20 > c.y);
            while (pris(x, y)) x += 2 * PAS;
        }
        const c = { id: this.identifiant("c"), type, x: cale(x), y: cale(y), repere: repereSuivant(this.schema, type), nom: "", valeurs: {} };
        def.champs.forEach((ch) => { if (ch.choix) c.valeurs[ch.cle] = ch.choix[0]; });
        this.state.composants.push(c);
        this.state.selection = { genre: "c", id: c.id };
        this.state.onglet = "proprietes";
    }
    glisserPalette(ev, type) { ev.dataTransfer.setData("text/plain", type); }
    deposer(ev) {
        const type = ev.dataTransfer.getData("text/plain");
        if (!APPAREILS[type]) return;
        const p = this.monde(ev);
        this.poser(type, p.x - APPAREILS[type].l * PAS / 2, p.y - APPAREILS[type].h * PAS / 2);
    }
    prendre(ev, c) {
        if (ev.button !== 0) return;
        ev.stopPropagation();
        if (this.state.depart) { this.state.depart = null; return; }
        const p = this.monde(ev);
        this.state.selection = { genre: "c", id: c.id };
        this.state.onglet = "proprietes";
        this.geste = { genre: "deplacer", id: c.id, dx: p.x - c.x, dy: p.y - c.y, avant: JSON.stringify(this.schema), bouge: false };
    }
    prendreFond(ev) {
        if (ev.button !== 0) return;
        if (this.state.depart) { this.state.depart = null; return; }
        this.state.selection = null;
        this.geste = { genre: "glisser", x: ev.clientX, y: ev.clientY, vx: this.state.vue.x, vy: this.state.vue.y };
    }
    bouger(ev) {
        const g = this.geste;
        if (this.state.depart) this.state.souris = this.monde(ev);
        if (!g) return;
        if (g.genre === "glisser") {
            this.state.vue.x = g.vx + ev.clientX - g.x;
            this.state.vue.y = g.vy + ev.clientY - g.y;
        } else {
            const c = this.state.composants.find((x) => x.id === g.id);
            const p = this.monde(ev);
            const x = cale(p.x - g.dx), y = cale(p.y - g.dy);
            if (c && (x !== c.x || y !== c.y)) { c.x = x; c.y = y; g.bouge = true; }
        }
    }
    lacher() {
        const g = this.geste;
        this.geste = null;
        if (g && g.genre === "deplacer" && g.bouge) {
            this.historique.push(g.avant);
            this.state.peutAnnuler = true;
            this.state.modifie = true;
        }
    }
    molette(ev) {
        ev.preventDefault();
        const v = this.state.vue;
        const r = this.toile.el.getBoundingClientRect();
        const z = Math.min(2.5, Math.max(0.3, v.z * (ev.deltaY < 0 ? 1.12 : 1 / 1.12)));
        const sx = ev.clientX - r.left, sy = ev.clientY - r.top;
        v.x = sx - (sx - v.x) * z / v.z;
        v.y = sy - (sy - v.y) * z / v.z;
        v.z = z;
    }
    zoom(k) {
        const r = this.toile.el.getBoundingClientRect();
        this.molette({ preventDefault() {}, deltaY: k > 0 ? -1 : 1, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 });
    }
    cadrer() {
        const el = this.toile.el;
        if (!el || !this.state.composants.length) return;
        const r = el.getBoundingClientRect();
        const xs = this.state.composants.flatMap((c) => [c.x, c.x + APPAREILS[c.type].l * PAS]);
        const ys = this.state.composants.flatMap((c) => [c.y, c.y + APPAREILS[c.type].h * PAS]);
        const x0 = Math.min(...xs) - 90, x1 = Math.max(...xs) + 90, y0 = Math.min(...ys) - 40, y1 = Math.max(...ys) + 40;
        const z = Math.min(1.4, Math.max(0.3, Math.min(r.width / (x1 - x0), r.height / (y1 - y0))));
        this.state.vue = { z, x: (r.width - (x0 + x1) * z) / 2, y: (r.height - (y0 + y1) * z) / 2 };
    }
    // Un clic sur une borne commence un fil ; un clic sur une autre borne le termine.
    cliquerBorne(ev, c, b) {
        ev.stopPropagation();
        const d = this.state.depart;
        if (!d) {
            this.state.depart = { c: c.id, b: b.id };
            this.state.souris = this.monde(ev);
            return;
        }
        this.state.depart = null;
        if (d.c === c.id && d.b === b.id) return;
        const pareil = (f) => (f.de.c === d.c && f.de.b === d.b && f.a.c === c.id && f.a.b === b.id) || (f.a.c === d.c && f.a.b === d.b && f.de.c === c.id && f.de.b === b.id);
        if (this.state.fils.some(pareil)) { this.state.message = "Ces deux bornes sont déjà reliées."; return; }
        this.memoriser();
        const f = { id: this.identifiant("f"), num: numeroSuivant(this.schema), de: d, a: { c: c.id, b: b.id }, section: "", longueur: "", decal: 0 };
        this.state.fils.push(f);
        this.state.selection = { genre: "f", id: f.id };
        this.state.onglet = "proprietes";
    }
    choisirFil(ev, id) {
        ev.stopPropagation();
        if (this.state.depart) { this.state.depart = null; return; }
        this.state.selection = { genre: "f", id };
        this.state.onglet = "proprietes";
    }
    supprimer() {
        const s = this.state.selection;
        if (!s) return;
        this.memoriser();
        if (s.genre === "c") {
            this.state.composants = this.state.composants.filter((c) => c.id !== s.id);
            this.state.fils = this.state.fils.filter((f) => f.de.c !== s.id && f.a.c !== s.id);
        } else {
            this.state.fils = this.state.fils.filter((f) => f.id !== s.id);
        }
        this.state.selection = null;
    }
    clavier(ev) {
        const cible = ev.target;
        if (cible && (["INPUT", "TEXTAREA", "SELECT"].includes(cible.tagName) || cible.isContentEditable)) return;
        if (ev.key === "Escape") this.state.depart = null;
        else if ((ev.key === "Delete" || ev.key === "Backspace") && this.state.selection) { ev.preventDefault(); this.supprimer(); }
        else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "z") { ev.preventDefault(); this.annuler(); }
    }

    // ---------------------------------------------------------------- les propriétés

    changer(objet, champ, ev) { this.memoriser(); objet[champ] = ev.target.value; }
    changerValeur(c, cle, ev) { this.memoriser(); c.valeurs = { ...(c.valeurs || {}), [cle]: ev.target.value }; }
    decaler(f, sens) { this.memoriser(); f.decal = (f.decal || 0) + sens * PAS; }
    extremite(ext) {
        const c = this.state.composants.find((x) => x.id === ext.c);
        return c ? `${c.repere || APPAREILS[c.type].nom}, borne ${ext.b}` : "?";
    }
    renommer(ev) { this.state.nom = ev.target.value; this.state.modifie = true; }

    // ---------------------------------------------------------------- l'enregistrement

    async enregistrer() {
        const valeurs = { name: (this.state.nom || "").trim() || "Schéma sans nom", donnees: JSON.stringify(this.schema) };
        try {
            if (this.state.id) await this.orm.write(MODELE, [this.state.id], valeurs);
            else this.state.id = (await this.orm.create(MODELE, [valeurs]))[0];
            this.state.nom = valeurs.name;
            this.state.modifie = false;
            this.state.message = "Schéma enregistré.";
        } catch {
            this.state.message = "L'enregistrement n'a pas abouti. Vos modifications restent à l'écran.";
        }
    }
    async listerSchemas() {
        this.state.liste = await this.orm.searchRead(MODELE, [], ["name", "nb_composants", "write_date", "partner_id"], { limit: 80 });
        this.state.aSupprimer = false;
    }
    fermerListe() { this.state.liste = null; }
    charger(dessin) {
        this.state.composants = (dessin.composants || []).filter((c) => APPAREILS[c.type]);
        const connus = new Set(this.state.composants.map((c) => c.id));
        this.state.fils = (dessin.fils || []).filter((f) => f.de && f.a && connus.has(f.de.c) && connus.has(f.a.c));
        this.state.selection = null;
        this.state.depart = null;
        this.historique = [];
        this.state.peutAnnuler = false;
        if (this.toile.el) this.cadrer();
    }
    async ouvrir(id) {
        const [s] = await this.orm.read(MODELE, [id], ["name", "donnees"]);
        if (!s) return;
        let dessin = {};
        try { dessin = JSON.parse(s.donnees || "{}"); } catch { dessin = {}; }
        this.state.id = s.id;
        this.state.nom = s.name;
        this.charger(dessin);
        this.state.modifie = false;
        this.state.liste = null;
        this.state.message = "";
    }
    nouveau() {
        this.state.id = false;
        this.state.nom = "Nouveau schéma";
        this.charger({});
        this.state.modifie = false;
        this.state.liste = null;
        this.state.vue = { x: 40, y: 20, z: 1 };
    }
    partirExemple() {
        if (this.state.composants.length) this.memoriser();
        const avant = this.historique.slice();
        this.charger(exemple());
        this.historique = avant;
        this.state.peutAnnuler = avant.length > 0;
        this.state.modifie = true;
        if (this.state.nom === "Nouveau schéma") this.state.nom = "Pompe avec pressostat";
    }
    demanderSuppression(id) { this.state.aSupprimer = id; }
    async archiver(id) {
        await this.orm.write(MODELE, [id], { active: false });
        if (this.state.id === id) this.nouveau();
        await this.listerSchemas();
    }
    date(texte) { return (texte || "").slice(0, 10).split("-").reverse().join("/"); }

    // L'image du schéma, telle qu'à l'écran, pour le dossier du client.
    telecharger() {
        const source = this.toile.el.querySelector("svg");
        if (!source || !this.state.composants.length) return;
        const xs = this.state.composants.flatMap((c) => [c.x, c.x + APPAREILS[c.type].l * PAS]);
        const ys = this.state.composants.flatMap((c) => [c.y, c.y + APPAREILS[c.type].h * PAS]);
        const x0 = Math.min(...xs) - 110, y0 = Math.min(...ys) - 50, l = Math.max(...xs) + 110 - x0, h = Math.max(...ys) + 50 - y0;
        const copie = source.cloneNode(true);
        copie.querySelectorAll(".o_cv_schema_hors_image").forEach((n) => n.remove());
        copie.querySelector(".o_cv_schema_monde").setAttribute("transform", "");
        copie.setAttribute("xmlns", "http://www.w3.org/2000/svg");
        copie.setAttribute("viewBox", `${x0} ${y0} ${l} ${h}`);
        copie.setAttribute("width", l * 2);
        copie.setAttribute("height", h * 2);
        const image = new Image();
        image.onload = () => {
            const toile = document.createElement("canvas");
            toile.width = l * 2;
            toile.height = h * 2;
            const ctx = toile.getContext("2d");
            ctx.fillStyle = "#fff";
            ctx.fillRect(0, 0, toile.width, toile.height);
            ctx.drawImage(image, 0, 0);
            const lien = document.createElement("a");
            lien.download = `${(this.state.nom || "schema").replace(/[^\wÀ-ſ -]+/g, "").trim() || "schema"}.png`;
            lien.href = toile.toDataURL("image/png");
            lien.click();
        };
        image.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(copie));
    }

    retour() {
        this.action.doAction("cultiveau_vue3d.action_vue3d", { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("cultiveau_vue3d.schema", SchemaCablage);
