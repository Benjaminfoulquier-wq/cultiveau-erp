/** @odoo-module **/
// La Map vivante : l'écran autour de la scène 3D (mise en page « contrôle ») : barre, recherche, sélecteur de zone, Live,
// notifications, trois KPI, fiche détaillée, suivi du dossier, tableau à onglets, visite guidée, scénario de démo, éditeur.
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { router } from "@web/core/browser/router";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { creerKit } from "./kit";
import { Moteur } from "./moteur";

const LIB = "/cultiveau_vue3d/static/lib/three/three.min.js";
const ICONES = { personne: "fa-user", camion: "fa-truck", client: "fa-car", dossier: "fa-leaf", chantier: "fa-wrench", intervention: "fa-bolt", rayon: "fa-archive", rayon_fixe: "fa-archive",
                 zone: "fa-map-o", borne: "fa-id-card-o", livraison: "fa-truck", poste: "fa-desktop", machine: "fa-cog", objet: "fa-cube", comptoir: "fa-shopping-basket", etabli: "fa-wrench", article: "fa-cube",
                 assistant: "fa-comments-o", appel: "fa-phone", salle: "fa-users" };
const GENRES_FICHE = { personne: "personne", camion: "camion", client: "client", dossier: "dossier", chantier: "chantier", intervention: "intervention", rayon: "rayon", zone: "zone", borne: "borne",
                       livraison: "livraison", poste: "poste", machine: "intervention", article: "article", appel: "appel" };
const ICONES_EVENEMENT = { arrivee: "fa-sign-in", depart: "fa-sign-out", pause_debut: "fa-coffee", pause_fin: "fa-coffee", depart_intervention: "fa-truck", retour_intervention: "fa-truck",
                           depart_chantier: "fa-truck", retour_chantier: "fa-truck", bon_signe: "fa-pencil", devis_signe: "fa-check-circle", devis_envoye: "fa-paper-plane", facture_payee: "fa-euro",
                           livraison: "fa-dropbox", sortie_stock: "fa-cube", stock_bas: "fa-exclamation-triangle", intervention_creee: "fa-bolt", intervention_terminee: "fa-check",
                           chantier_demarre: "fa-wrench", chantier_termine: "fa-flag-checkered", mise_en_service: "fa-tint", alerte_irrigation: "fa-tint", ambiance: "fa-bell-o", etape: "fa-arrow-right",
                           appel: "fa-phone", reunion: "fa-calendar", conge: "fa-plane", frais: "fa-ticket", courriel: "fa-envelope", courriel_relance: "fa-envelope-o" };
const sansAccents = (t) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const heure = (iso) => {
    if (!iso) {
        return "";
    }
    const d = new Date(iso.replace(" ", "T") + "Z");
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
};
const duree = (iso) => {
    if (!iso) {
        return "";
    }
    const min = Math.max(0, Math.round((Date.now() - new Date(iso.replace(" ", "T") + "Z").getTime()) / 60000));
    if (min >= 1440) {
        return `${Math.floor(min / 1440)} j ${Math.floor((min % 1440) / 60)} h`;
    }
    return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")}`;
};

export class MapVivante extends Component {
    static template = "cultiveau_vue3d.Map";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.bus = useService("bus_service");
        this.mathis = this.env.services.mathis || null;
        this.hote = useRef("hote");
        this.calque = useRef("calque");
        this.rechercheRef = useRef("recherche");
        this.state = useState({
            v: null, pret: false, chargement: 0, sans3d: false, heure: "", recherche: "", resultats: [], zones: [], zoneOuverte: false, cloche: false, lues: 0,
            selection: null, fiche: null, ficheChargement: false, complete: null, onglet: "equipe", notifs: [], kpi: [], flash: {}, suivi: null, visite: null,
            edition: false, palette: false, objetEdite: null, lien: { modele: "", recherche: "", resultats: [] }, historique: [], futur: [], planModifie: false, creerOuvert: false,
            demo: { actif: false, etape: 0 }, erreur: "",
            planif: null,
        });
        this.traites = new Set();
        this.minuteries = [];
        this.focusDemande = this.props.action?.params?.focus || router.current?.focus || new URLSearchParams(window.location.search).get("focus") || null;
        window.cultiveauMap = this; // pour le débogage dans la console
        onWillStart(async () => {
            try {
                await loadJS(LIB);
            } catch {
                this.state.sans3d = true;
            }
            await this.charger();
        });
        onMounted(() => this.monter());
        onWillUnmount(() => this.demonter());
    }

    // ------------------------------------------------------------------ les données

    async charger() {
        try {
            this.state.v = await this.orm.call("cultiveau.map", "vivant", []);
            this.state.kpi = this.state.v.kpi;
            this._zones();
        } catch (e) {
            this.state.erreur = e.data?.message || e.message || String(e);
        }
    }
    _zones() {
        const v = this.state.v;
        const compte = {};
        for (const p of v.personnes) {
            const z = p.statut === "en_pause" ? "pause" : p.statut === "en_reunion" ? "reunion" : p.statut === "au_poste" ? p.zone : null;
            if (z) {
                compte[z] = (compte[z] || 0) + 1;
            }
        }
        this.state.zones = (v.plan.zones || []).map((z) => ({ ...z, icone: (v.secteur.zones.find((s) => s.cle === z.cle) || {}).icone || "fa-map-o", presents: compte[z.cle] || 0,
                                                              taux: Math.min(100, (compte[z.cle] || 0) * 25) }));
    }
    async rafraichir() {
        if (this._rafraichit) {
            this._encore = true;
            return;
        }
        this._rafraichit = true;
        try {
            const avant = this.state.kpi;
            const v = await this.orm.call("cultiveau.map", "vivant", []);
            this.state.v = v;
            for (const k of v.kpi) {
                const a = avant.find((x) => x.cle === k.cle);
                if (a && a.valeur !== k.valeur) {
                    this.state.flash[k.cle] = Date.now();
                    this.minuterie(() => delete this.state.flash[k.cle], 1600);
                }
            }
            this.state.kpi = v.kpi;
            this._zones();
            this.moteur?.peupler(v);
            this.majSalle();
            if (this.state.selection && this.state.fiche) {
                this.ouvrirFiche(this.state.selection, false);
            }
        } finally {
            this._rafraichit = false;
            if (this._encore) {
                this._encore = false;
                this.rafraichir();
            }
        }
    }

    // ------------------------------------------------------------------ la scène

    monter() {
        const v = this.state.v;
        if (!v) {
            return;
        }
        this._clavier = (ev) => this.onClavier(ev);
        window.addEventListener("keydown", this._clavier);
        this.minuterie(() => this.tic(), 0, true);
        if (this.state.sans3d) {
            return;
        }
        try {
            const THREE = window.THREE;
            this.kit = creerKit(THREE);
            this.moteur = new Moteur(THREE, this.kit, this.hote.el, this.calque.el, {
                accent: v.societe.accent, logo: (v.societe.nom || "C")[0].toUpperCase(), nom: v.societe.nom,
                onSelection: (cle, o) => this.onSelection(cle, o), onSurvol: (cle, o) => this.onSurvol(cle, o), onClicVide: () => this.fermerFiche(),
                onObjetDeplace: () => this.marquerPlan(),
            });
            this.state.chargement = 40;
            this.moteur.construire(v.plan);
            this.state.chargement = 75;
            this.moteur.peupler(v, true);
            this.majSalle();
            this.state.chargement = 100;
            // la boucle : frame(dt) séparée, pas de temps borné, pause quand l'onglet est caché
            let dernier = performance.now();
            const boucle = (t) => {
                this._boucle = requestAnimationFrame(boucle);
                if (document.hidden) {
                    dernier = t;
                    return;
                }
                const dt = (t - dernier) / 1000;
                dernier = t;
                this.moteur.frame(dt);
            };
            this._boucle = requestAnimationFrame(boucle);
            this.minuterie(() => {
                this.state.pret = true;
                let memo = null;
                try {
                    memo = JSON.parse(sessionStorage.getItem(`cultiveau_map_${v.societe.id}`) || "null");
                } catch {
                    memo = null;
                }
                if (memo && Date.now() - memo.quand < 20 * 60 * 1000 && !this.focusDemande) {
                    this.moteur.restaurerCamera(memo);
                    if (memo.selection && this.moteur.objets.has(memo.selection)) {
                        this.moteur.selectionner(memo.selection, false);
                    }
                    this.apresIntro();
                } else {
                    this.moteur.intro(() => this.apresIntro());
                }
            }, 500);
        } catch (e) {
            console.warn("Map vivante : 3D indisponible", e);
            this.state.sans3d = true;
        }
        this.ecouterBus();
        this.minuterie(() => this.rafraichir(), 30000, true);
    }
    apresIntro() {
        if (this.focusDemande) {
            this.focaliser(this.focusDemande);
            this.focusDemande = null;
        }
        if (this.state.v.societe.demo) {
            this.demarrerDemo();
        }
    }
    demonter() {
        try {
            if (this.moteur && this.state.v) {
                sessionStorage.setItem(`cultiveau_map_${this.state.v.societe.id}`, JSON.stringify(this.moteur.etatCamera()));
            }
        } catch {
            /* pas de stockage de session : tant pis */
        }
        cancelAnimationFrame(this._boucle);
        window.removeEventListener("keydown", this._clavier);
        for (const m of this.minuteries) {
            clearTimeout(m);
            clearInterval(m);
        }
        if (this.state.v?.canal) {
            this.bus.unsubscribe("cultiveau_map", this._surEvenement);
            this.bus.deleteChannel(this.state.v.canal);
        }
        this.moteur?.detruire();
    }
    minuterie(fn, delai, repete = false) {
        const id = repete ? setInterval(fn, delai) : setTimeout(fn, delai);
        this.minuteries.push(id);
        return id;
    }
    tic() {
        this.state.heure = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
        const t = Date.now();
        this.state.notifs = this.state.notifs.filter((n) => t - n.t < 6000);
        if (this.minuterieTic) {
            return;
        }
        this.minuterieTic = this.minuterie(() => this.tic(), 1000);
        this.minuteries = this.minuteries.filter((m) => m !== this.minuterieTic);
        this.minuterieTic = null;
    }

    // ------------------------------------------------------------------ le temps réel

    ecouterBus() {
        const v = this.state.v;
        this._surEvenement = (ev) => this.traiterEvenement(ev);
        try {
            this.bus.addChannel(v.canal);
            this.bus.subscribe("cultiveau_map", this._surEvenement);
        } catch (e) {
            console.warn("Map vivante : pas de temps réel", e);
        }
    }
    async traiterEvenement(ev) {
        if (!ev || this.traites.has(ev.id)) {
            return;
        }
        this.traites.add(ev.id);
        const v = this.state.v;
        v.evenements = [ev, ...(v.evenements || [])].slice(0, 30);
        const charge = ev.charge || {};
        const clePersonne = charge.user_id ? `personne:${charge.user_id}` : null;
        this.notifier(ev);
        const m = this.moteur;
        if (!m) {
            return;
        }
        switch (ev.genre) {
            case "arrivee": {
                await this.rafraichir();
                if (clePersonne) {
                    const borne = [...m.objets.values()].find((o) => o.genre === "borne");
                    if (borne) {
                        m.passerPar(clePersonne, [borne.groupe.position.x + 0.9, borne.groupe.position.z], null, "entree_clients");
                    } else {
                        m.entrer(clePersonne, "entree_equipe");
                    }
                }
                break;
            }
            case "depart_intervention":
            case "depart_chantier":
                if (clePersonne) {
                    m.sortir(clePersonne, "porte_cour", () => this.rafraichir());
                } else {
                    this.rafraichir();
                }
                break;
            case "retour_intervention":
            case "retour_chantier":
                await this.rafraichir();
                this.minuterie(() => clePersonne && m.entrer(clePersonne, "porte_cour"), 6500);
                break;
            case "depart":
                if (clePersonne) {
                    m.sortir(clePersonne, "entree_equipe", () => this.rafraichir());
                }
                break;
            case "livraison":
                m.livrer(`livraison:${charge.picking_id || "demo"}`, () => this.rafraichir());
                break;
            case "appel":
                m.assistantDecroche(25);
                this.rafraichir();
                break;
            case "reunion":
                this.rafraichir();
                break;
            case "ambiance":
                break;
            default:
                this.rafraichir();
        }
    }
    notifier(ev) {
        this.state.notifs = [{ ...ev, t: Date.now() }, ...this.state.notifs].slice(0, 3);
    }
    get evenementsNonLus() {
        return Math.max(0, (this.state.v?.evenements || []).length - this.state.lues);
    }
    ouvrirCloche() {
        this.state.cloche = !this.state.cloche;
        this.state.lues = (this.state.v?.evenements || []).length;
    }
    cleDeEvenement(ev) {
        const c = ev.charge || {};
        if (c.user_id) { return `personne:${c.user_id}`; }
        if (c.technicien_id) { return `personne:${c.technicien_id}`; }
        if (c.installation_id) { return `dossier:${c.installation_id}`; }
        if (c.picking_id) { return `livraison:${c.picking_id}`; }
        if (c.appel_id) { return `appel:${c.appel_id}`; }
        if (c.reunion_id) { return "zone:reunion"; }
        if (ev.modele === "project.task") { return `intervention:${ev.res_id}`; }
        if (ev.modele === "cultiveau.installation") { return `dossier:${ev.res_id}`; }
        if (ev.modele === "res.users") { return `personne:${ev.res_id}`; }
        return null;
    }
    allerEvenement(ev) {
        const cle = this.cleDeEvenement(ev);
        this.state.cloche = false;
        if (cle) {
            this.aller(cle);
        } else if (ev.modele && ev.res_id) {
            this.ouvrirBackOffice(ev.modele, ev.res_id);
        }
    }

    // ------------------------------------------------------------------ la sélection et les fiches

    onSelection(cle, o, visible = true) {
        this.state.selection = cle;
        if (cle && !visible) {
            this.notification.add(`${o.nom} n'est pas sur la map en ce moment (${(o.sousTitre || "").toLowerCase() || "absent"}).`, { type: "info" });
        }
        for (const e of [...this.moteur.etiquettes.keys()]) {
            if (e.startsWith("selection:")) {
                this.moteur.retirerEtiquette(e);
            }
        }
        if (!cle) {
            this.state.fiche = null;
            this.state.objetEdite = null;
            return;
        }
        visible && this.moteur.etiquette(`selection:${cle}`, `<span class="o_cv_etiq_plein"><b>${o.nom || ""}</b>${o.sousTitre ? ` <span>|</span> ${o.sousTitre}` : ""}</span>`, "selection");
        if (this.state.edition && o.statique && o.plan) {
            this.state.objetEdite = { cle, id: o.plan.id, type: o.plan.type, rot: o.plan.rot || 0, entite: o.plan.entite, zone: o.plan.zone };
            this.state.fiche = null;
            return;
        }
        if (o.genre === "salle" || (o.genre === "zone" && o.id === "reunion" && this.state.v.reunion)) {
            this.ouvrirSalle(cle);
            return;
        }
        if (o.genre === "assistant") {
            this.state.fiche = { genre: "assistant", nom: o.nom, sousTitre: o.sousTitre, cle, appels: (this.state.v.assistant || {}).appels || [], actions: [] };
            return;
        }
        if (o.genre === "porte" || o.genre === "objet" || o.genre === "comptoir" || o.genre === "etabli" || o.genre === "rayon_fixe") {
            this.state.fiche = { genre: "objet", nom: o.nom, sousTitre: o.sousTitre, cle, actions: [] };
            return;
        }
        this.ouvrirFiche(cle, true);
    }
    onSurvol(cle, o) {
        for (const e of [...this.moteur.etiquettes.keys()]) {
            if (e.startsWith("survol:")) {
                this.moteur.retirerEtiquette(e);
            }
        }
        if (cle && cle !== this.state.selection && o.nom) {
            this.moteur.etiquette(`survol:${cle}`, `<span class="o_cv_etiq"><b>${o.nom}</b>${o.sousTitre ? ` · ${o.sousTitre}` : ""}</span>`, "survol");
        }
    }
    async ouvrirFiche(cle, afficher = true) {
        const o = this.moteur?.objets.get(cle);
        if (!o) {
            return;
        }
        const genre = GENRES_FICHE[o.genre];
        if (!genre) {
            return;
        }
        this.state.ficheChargement = afficher;
        try {
            const args = genre === "zone" ? ["zone", 0] : [genre, o.id];
            const fiche = await this.orm.call("cultiveau.map", "fiche", args, genre === "zone" ? { cle: o.id } : {});
            fiche.cle = cle;
            fiche.genre = fiche.genre || genre;
            fiche.icone = ICONES[o.genre] || "fa-cube";
            this.state.fiche = fiche;
        } catch (e) {
            this.state.fiche = { genre: "objet", nom: o.nom, sousTitre: e.data?.message || e.message, cle, actions: [] };
        } finally {
            this.state.ficheChargement = false;
        }
    }
    fermerFiche() {
        this.state.fiche = null;
        this.state.complete = null;
        if (this.moteur?.selection) {
            this.moteur.deselectionner();
        }
    }
    aller(cle, ouvrir = true) {
        if (!this.moteur) {
            return;
        }
        let o = this.moteur.objets.get(cle);
        if (!o && cle.startsWith("dossier:")) {
            // l'installation est peut-être représentée par son chantier
            const autre = [...this.moteur.objets.entries()].find(([k, x]) => k.startsWith("chantier:") && x.meta?.installation === +cle.split(":")[1]);
            if (autre) {
                cle = autre[0];
                o = autre[1];
            }
        }
        if (!o) {
            // une intervention : on va vers son technicien ou son installation
            const [genre, id] = cle.split(":");
            if (genre === "intervention") {
                const t = (this.state.v.interventions || []).find((x) => x.id === +id);
                const autre = t?.technicien_id && this.moteur.objets.has(`personne:${t.technicien_id}`) ? `personne:${t.technicien_id}`
                    : t?.installation && this.moteur.objets.has(`dossier:${t.installation}`) ? `dossier:${t.installation}` : null;
                if (autre) {
                    this.moteur.volerVers(autre, 1);
                }
                this.state.selection = cle;
                this.state.fiche = null;
                this.state.ficheChargement = true;
                this.orm.call("cultiveau.map", "fiche", ["intervention", +id]).then((f) => { f.cle = cle; f.icone = ICONES.intervention; this.state.fiche = f; }).finally(() => (this.state.ficheChargement = false));
                return;
            }
            // pas sur la map en ce moment (une installation à l'étude, un client parti) : la fiche s'ouvre quand même
            const fiche = GENRES_FICHE[genre];
            if (!fiche) {
                this.notification.add("Cet élément n'est pas sur la map en ce moment.", { type: "warning" });
                return;
            }
            this.state.selection = cle;
            this.state.fiche = null;
            this.state.ficheChargement = true;
            this.orm.call("cultiveau.map", "fiche", [fiche, +id]).then((f) => { f.cle = cle; f.icone = ICONES[genre]; this.state.fiche = f; })
                .catch((e) => this.notification.add(e.data?.message || e.message, { type: "warning" })).finally(() => (this.state.ficheChargement = false));
            return;
        }
        if (ouvrir) {
            this.moteur.selectionner(cle, true);
        } else {
            this.moteur.volerVers(cle, 0);
        }
    }
    /** Un article : sa fiche, et la caméra sur le rayon de sa famille s'il est sur la map. */
    async ouvrirArticle(id, rayon) {
        const rack = rayon && [...this.moteur.objets.entries()].find(([k, o]) => o.genre === "rayon" && o.id === rayon);
        if (rack) {
            this.moteur.volerVers(rack[0], 1);
        }
        this.state.selection = `article:${id}`;
        this.state.fiche = null;
        this.state.ficheChargement = true;
        try {
            const f = await this.orm.call("cultiveau.map", "fiche", ["article", id]);
            f.cle = `article:${id}`;
            f.icone = ICONES.article;
            this.state.fiche = f;
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "warning" });
        } finally {
            this.state.ficheChargement = false;
        }
    }
    allerLigne(l) {
        const cle = l.cible === "intervention" ? `intervention:${l.res_id}` : `${l.cible}:${l.id}`;
        if (l.cible === "rayon") {
            const rack = [...this.moteur.objets.entries()].find(([k, o]) => o.genre === "rayon" && o.id === l.id);
            if (rack) {
                this.aller(rack[0]);
                return;
            }
        }
        this.aller(cle);
    }
    suivre() {
        if (!this.state.selection) {
            return;
        }
        this.state.suivi = this.moteur.suivre(this.state.selection);
    }
    async focaliser(focus) {
        const [modele, id] = focus.split(":");
        try {
            const f = await this.orm.call("cultiveau.map", "focus", [modele, +id]);
            if (f.genre === "intervention") {
                this.aller(`intervention:${id}`);
            } else if (f.genre === "camion") {
                this.aller(`camion:${f.id}`);
            } else if (f.genre === "rayon") {
                const rack = [...this.moteur.objets.entries()].find(([k, o]) => o.genre === "rayon" && o.id === f.id);
                rack && this.aller(rack[0]);
            } else if (f.genre === "zone") {
                this.moteur.vueEnsemble();
            } else {
                this.aller(`${f.genre}:${f.id}`);
            }
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "warning" });
        }
    }
    async lancerAction(a) {
        const f = this.state.fiche;
        try {
            if (a.cle === "badger") {
                await this.orm.call("cultiveau.map", "badger", [a.genre, f.id]);
                this.notification.add("Pointage enregistré.", { type: "success" });
                return;
            }
            if (a.cle === "appeler") {
                if (a.tel) {
                    window.location.href = `tel:${a.tel}`;
                } else {
                    this.notification.add("Pas de numéro de téléphone.", { type: "warning" });
                }
                return;
            }
            if (a.url) {
                window.open(a.url, "_blank");
                return;
            }
            if (a.appel) {
                // un bouton de bloc : une méthode du serveur (valider, refuser…), puis la fiche se met à jour
                const res = await this.orm.call(a.appel.modele, a.appel.methode, a.appel.args || [], a.appel.kwargs || {});
                if (res && res.type) {
                    await this.action.doAction(res);
                } else if (a.message || (res && res.message)) {
                    this.notification.add((res && res.message) || a.message, { type: "success" });
                }
                f.cle && this.ouvrirFiche(f.cle, false);
                return;
            }
            if (a.doaction) {
                await this.action.doAction(a.doaction);
                return;
            }
            if (a.cle === "planifier_reunion") {
                this.ouvrirPlanif({ client: a.client_id ? { id: a.client_id, nom: a.client_nom || f.nom } : null, participants: a.user_id ? [a.user_id] : [], titre: a.titre || "" });
                return;
            }
            if (a.cle === "rejoindre") {
                window.open(a.lien, "_blank");
                return;
            }
            if (a.cle === "connecter_google" || a.cle === "connecter_outlook") {
                await this.connecterAgenda(a.cle === "connecter_google" ? "google" : "microsoft");
                return;
            }
            if (a.cle === "notifier") {
                await this.action.doAction({ type: "ir.actions.act_window", res_model: "mail.compose.message", view_mode: "form", target: "new",
                                             context: { default_model: "res.partner", default_res_ids: [a.id], default_composition_mode: "comment", default_partner_ids: [a.id] } });
                return;
            }
            if (a.cle === "interventions_de") {
                await this.action.doAction({ type: "ir.actions.act_window", name: `Interventions — ${f.nom || f.conducteur || ""}`, res_model: "project.task", view_mode: "list,form",
                                             domain: [["cultiveau_intervention", "=", true], ["user_ids", "in", [f.id || f.conducteur_id]]] });
                return;
            }
            if (a.cle === "devis_nouveau") {
                await this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order", views: [[false, "form"]], context: a.contexte || {} });
                return;
            }
            if (a.modele && a.domaine) {
                await this.action.doAction(await this.orm.call("cultiveau.map", "ouvrir", [a.modele, 0, a.domaine, a.nom]));
                return;
            }
            if (a.modele) {
                await this.ouvrirBackOffice(a.modele, a.id);
                return;
            }
            // une clé de la vue d'ensemble (famille_stock, reappro…)
            await this.action.doAction(await this.orm.call("cultiveau.scene", "action", [a.cle, a.parametre || null]));
        } catch (e) {
            this.notification.add(e.data?.message || e.message || String(e), { type: "danger" });
        }
    }
    async ouvrirBackOffice(modele, id) {
        if (!modele) {
            return;
        }
        await this.action.doAction(await this.orm.call("cultiveau.map", "ouvrir", [modele, id]));
    }
    ficheComplete() {
        this.state.complete = this.state.fiche;
    }
    get suiviDossier() {
        const f = this.state.fiche;
        if (!f) {
            return null;
        }
        if (f.genre === "dossier" && f.etapes) {
            return f;
        }
        if (f.genre === "chantier" && f.dossier) {
            return f.dossier;
        }
        if (f.genre === "intervention" && f.installation) {
            return (this.state.v.dossiers || []).find((d) => d.id === f.installation) || (this.state.v.parcelles || []).map((p) => ({ ...p, etapes: null })).find((d) => d.id === f.installation && d.etapes) || null;
        }
        return null;
    }

    // ------------------------------------------------------------------ la salle de réunion, les agendas, la visio
    majSalle() {
        const r = this.state.v?.reunion;
        const zone = this.moteur?.objets.get("zone:reunion");
        if (!r || !zone || !this.moteur) {
            return;
        }
        const s = r.salle;
        const html = s.en_cours
            ? `<span class="o_cv_salle occupee"><i class="fa fa-circle"></i> <b>${r.salle_nom}</b> · ${s.en_cours.titre} · jusqu'à ${heure(s.en_cours.fin)}</span>`
            : `<span class="o_cv_salle libre"><i class="fa fa-circle"></i> <b>${r.salle_nom}</b> · libre${s.prochaine ? ` · ${heure(s.prochaine.debut)} ${s.prochaine.titre}` : ""}</span>`;
        const c = zone.centre;
        this.moteur.etiquette("salle:reunion", html, "salle", new window.THREE.Vector3(c.x, 2.9, c.z));
    }
    async ouvrirSalle(cle) {
        this.state.ficheChargement = true;
        try {
            const f = await this.orm.call("cultiveau.map", "fiche", ["zone", 0], { cle: "reunion" });
            f.cle = cle;
            f.icone = ICONES.salle;
            f.genre = "salle";
            this.state.fiche = f;
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "warning" });
        } finally {
            this.state.ficheChargement = false;
        }
    }
    ouvrirPlanif(pre = {}) {
        const r = this.state.v?.reunion;
        if (!r) {
            this.notification.add("Les réunions ne sont pas installées sur cet ERP.", { type: "warning" });
            return;
        }
        this.state.planif = {
            titre: pre.titre || (pre.client ? `Rendez-vous ${pre.client.nom}` : "Point d'équipe"), participants: [...(pre.participants || [])], client: pre.client || null,
            duree: 60, lieu: pre.client ? "visio" : "salle", visio: r.visio_defaut || "erp", lien: "", description: "",
            rechercheClient: "", resultatsClient: [], creneaux: null, choisi: null, occupe: false, fait: null,
        };
    }
    ouvrirUrl(url) {
        if (url) {
            window.open(url, "_blank", "noopener");
        }
    }
    fermerPlanif() {
        this.state.planif = null;
    }
    basculerParticipant(id) {
        const p = this.state.planif;
        p.participants = p.participants.includes(id) ? p.participants.filter((x) => x !== id) : [...p.participants, id];
        p.creneaux = null;
        p.choisi = null;
    }
    async chercherClientPlanif() {
        const p = this.state.planif;
        if ((p.rechercheClient || "").length < 2) {
            p.resultatsClient = [];
            return;
        }
        const r = await this.orm.call("cultiveau.map", "chercher", [p.rechercheClient, 6]);
        p.resultatsClient = r.filter((x) => x.genre === "client");
    }
    choisirClientPlanif(c) {
        const p = this.state.planif;
        p.client = { id: c.id, nom: c.nom };
        p.rechercheClient = "";
        p.resultatsClient = [];
        if (!p.titre || p.titre === "Point d'équipe") {
            p.titre = `Rendez-vous ${c.nom}`;
        }
    }
    async proposerCreneaux() {
        const p = this.state.planif;
        p.occupe = true;
        try {
            p.creneaux = await this.orm.call("cultiveau.reunion", "creneaux", [p.participants, p.duree], { salle: p.lieu === "salle" });
            p.choisi = p.creneaux.length ? 0 : null;
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        } finally {
            p.occupe = false;
        }
    }
    async planifier() {
        const p = this.state.planif;
        if (p.choisi === null || !p.creneaux || !p.creneaux[p.choisi]) {
            return;
        }
        p.occupe = true;
        try {
            const res = await this.orm.call("cultiveau.reunion", "planifier", [{
                titre: p.titre, debut: p.creneaux[p.choisi].debut_utc, duree_min: p.duree, user_ids: p.participants, client_id: p.client?.id || false,
                lieu: p.lieu, visio: p.lieu === "exterieur" ? "aucune" : p.visio, lien: p.lien, description: p.description,
            }]);
            p.fait = res;
            this.rafraichir();
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        } finally {
            p.occupe = false;
        }
    }
    async connecterAgenda(fournisseur) {
        try {
            const r = await rpc(`/${fournisseur === "google" ? "google" : "microsoft"}_calendar/sync_data`, { model: "calendar.event", fromurl: window.location.href });
            if (r.status === "need_auth" && r.url) {
                window.location.href = r.url;
            } else if (r.status === "need_config_from_admin") {
                this.notification.add(`La connexion ${fournisseur === "google" ? "Google Agenda" : "Outlook"} n'est pas encore configurée : l'administrateur renseigne les identifiants dans Réglages → Cultiveau → Réunions et agendas.`, { type: "warning", sticky: true });
            } else {
                this.notification.add(`Votre agenda ${fournisseur === "google" ? "Google" : "Outlook"} est synchronisé.`, { type: "success" });
                this.rafraichir();
            }
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
        }
    }
    get equipePlanif() {
        return (this.state.v?.personnes || []).filter((p) => !p.moi);
    }

    // ------------------------------------------------------------------ Mathis
    ouvrirMathis(question = "") {
        if (!this.mathis) {
            this.notification.add("Mathis n'est pas installé sur cet ERP.", { type: "warning" });
            return;
        }
        this.mathis.ouvrir(question);
    }

    // ------------------------------------------------------------------ la barre : recherche, zones, création

    chercher() {
        const q = sansAccents(this.state.recherche).trim();
        if (q.length < 2) {
            this.state.resultats = [];
            return;
        }
        const v = this.state.v;
        const r = [];
        const ok = (...t) => t.some((x) => sansAccents(x).includes(q));
        for (const p of v.personnes) {
            ok(p.nom, p.role_nom) && r.push({ groupe: "Équipe", nom: p.nom, sous: `${p.role_nom} · ${p.statut_nom}`, cle: `personne:${p.id}`, icone: "fa-user" });
        }
        for (const d of [...v.dossiers, ...v.parcelles]) {
            ok(d.nom, d.client, d.commune) && r.push({ groupe: "Installations", nom: d.nom, sous: d.client, cle: `dossier:${d.id}`, icone: "fa-leaf" });
        }
        for (const c of v.chantiers) {
            ok(c.nom, c.client) && r.push({ groupe: "Chantiers", nom: c.nom, sous: c.client, cle: `chantier:${c.id}`, icone: "fa-wrench" });
        }
        for (const t of v.interventions) {
            ok(t.nom, t.client, t.technicien) && r.push({ groupe: "Interventions", nom: t.nom, sous: `${t.client} · ${t.technicien}`, cle: `intervention:${t.id}`, icone: "fa-bolt" });
        }
        for (const c of v.clients) {
            ok(c.nom) && r.push({ groupe: "Clients sur place", nom: c.nom, sous: c.devis?.nom || "", cle: `client:${c.id}`, icone: "fa-car" });
        }
        for (const s of v.stock) {
            ok(s.nom) && r.push({ groupe: "Stock", nom: s.nom, sous: `${s.stock} en stock`, rayon: s.id, icone: "fa-archive" });
        }
        for (const z of this.state.zones) {
            ok(z.nom) && r.push({ groupe: "Zones", nom: z.nom, sous: `${z.presents} présent(s)`, cle: `zone:${z.cle}`, icone: z.icone });
        }
        for (const v3 of v.vehicules) {
            ok(v3.nom, v3.conducteur) && r.push({ groupe: "Camions", nom: v3.nom, sous: v3.conducteur, cle: `camion:${v3.id}`, icone: "fa-truck" });
        }
        // les écrans du back-office, par la zone qui les ouvre (« TVA », « bilan », « réassort »…)
        for (const [zone, portes] of Object.entries(v.portes || {})) {
            const z = this.state.zones.find((x) => x.cle === zone);
            for (const p of portes) {
                ok(p.nom) && !r.some((x) => x.porte === p.cle) && r.push({ groupe: "Écrans", nom: p.nom, sous: z ? z.nom : zone, porte: p.cle, zone, icone: p.icone });
            }
        }
        this.state.resultats = r.slice(0, 12);
        this.state.curseur = 0;
        clearTimeout(this._rechercheServeur);
        const demande = this.state.recherche;
        this._rechercheServeur = setTimeout(async () => {
            try {
                const distants = await this.orm.call("cultiveau.map", "chercher", [demande]);
                if (this.state.recherche !== demande) {
                    return;
                }
                const deja = new Set(this.state.resultats.map((x) => x.cle));
                const ajouts = distants.map((d) => ({ ...d, cle: `${d.genre}:${d.id}` })).filter((d) => !deja.has(d.cle));
                this.state.resultats = [...this.state.resultats, ...ajouts].slice(0, 18);
            } catch {
                /* la recherche locale suffit */
            }
        }, 250);
    }
    choisir(r) {
        this.state.recherche = "";
        this.state.resultats = [];
        if (this.rechercheRef.el) {
            this.rechercheRef.el.value = "";
            this.rechercheRef.el.blur();
        }
        if (r.porte) {
            this.lancer(r.porte);
            return;
        }
        if (r.genre === "article") {
            this.ouvrirArticle(r.id, r.rayon);
            return;
        }
        if (r.rayon) {
            const rack = [...this.moteur.objets.entries()].find(([k, o]) => o.genre === "rayon" && o.id === r.rayon);
            rack && this.aller(rack[0]);
            return;
        }
        this.aller(r.cle);
    }
    onToucheRecherche(ev) {
        if (ev.key === "Enter" && this.state.resultats.length) {
            this.choisir(this.state.resultats[this.state.curseur || 0]);
        } else if (ev.key === "ArrowDown") {
            this.state.curseur = Math.min(this.state.resultats.length - 1, (this.state.curseur || 0) + 1);
            ev.preventDefault();
        } else if (ev.key === "ArrowUp") {
            this.state.curseur = Math.max(0, (this.state.curseur || 0) - 1);
            ev.preventDefault();
        } else if (ev.key === "Escape") {
            this.state.recherche = "";
            this.state.resultats = [];
            ev.target.blur();
        }
    }
    allerZone(z) {
        this.state.zoneOuverte = false;
        this.aller(`zone:${z.cle}`, false);
    }
    onClavier(ev) {
        const dansChamp = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
        if (ev.key === "/" && !dansChamp) {
            ev.preventDefault();
            this.rechercheRef.el?.focus();
        } else if (ev.key === "Escape") {
            if (this.state.complete) {
                this.state.complete = null;
            } else if (this.state.visite) {
                this.moteur.arreterVisite();
            } else if (this.state.palette) {
                this.state.palette = false;
            } else {
                this.fermerFiche();
            }
        } else if (!dansChamp && (ev.key === "t" || ev.key === "T")) {
            this.visiteGuidee();
        } else if (!dansChamp && (ev.key === "h" || ev.key === "H")) {
            this.moteur?.vueEnsemble();
        } else if (!dansChamp && this.state.edition && (ev.key === "r" || ev.key === "R") && this.state.objetEdite) {
            this.tournerObjet(ev.shiftKey ? -15 : 15);
        } else if (!dansChamp && this.state.edition && (ev.key === "Delete" || ev.key === "Backspace") && this.state.objetEdite) {
            this.supprimerObjet();
        } else if (!dansChamp && this.state.edition && (ev.ctrlKey || ev.metaKey) && ev.key === "z") {
            ev.preventDefault();
            ev.shiftKey ? this.retablir() : this.annuler();
        }
    }
    async lancer(cle, parametre = null) {
        this.state.creerOuvert = false;
        try {
            await this.action.doAction(await this.orm.call("cultiveau.scene", "action", [cle, parametre]));
        } catch (e) {
            this.notification.add(e.data?.message || e.message || String(e), { type: "danger" });
        }
    }
    creer(modele, contexte = {}) {
        this.state.creerOuvert = false;
        return this.action.doAction({ type: "ir.actions.act_window", res_model: modele, views: [[false, "form"]], context: contexte });
    }
    kpiClic(k) {
        if (k.action) {
            this.lancer(k.action);
        }
    }

    // ------------------------------------------------------------------ la visite guidée

    visiteGuidee() {
        if (!this.moteur) {
            return;
        }
        if (this.state.visite) {
            this.moteur.arreterVisite();
            return;
        }
        const v = this.state.v;
        const plans = [{ titre: "Le site", distance: this.moteur.vue.distance, polaire: this.moteur.vue.polaire, duree: 5 }];
        const zone = (cle, titre) => this.moteur.objets.has(`zone:${cle}`) && plans.push({ cle: `zone:${cle}`, titre, distance: 34 });
        zone("accueil", "L'accueil et le comptoir");
        const p = v.personnes.find((p) => p.statut === "au_poste");
        p && plans.push({ cle: `personne:${p.id}`, titre: `${p.nom}, ${p.role_nom.toLowerCase()}`, distance: 22 });
        zone("stockage", "Le stockage par famille");
        zone("atelier", "L'atelier et le SAV");
        const c = v.vehicules[0];
        c && plans.push({ cle: `camion:${c.id}`, titre: c.nom, distance: 26 });
        zone("cour", "La cour et le dépôt extérieur");
        const d = v.chantiers[0] ? `chantier:${v.chantiers[0].id}` : v.dossiers.find((x) => x.etat === "realisation") ? `dossier:${v.dossiers.find((x) => x.etat === "realisation").id}` : null;
        d && plans.push({ cle: d, titre: "Un chantier en cours", distance: 30 });
        const parc = v.parcelles[0];
        parc && plans.push({ cle: `dossier:${parc.id}`, titre: `${parc.nom}, en service`, distance: 30 });
        zone("bureau", "Le bureau d'étude");
        plans.push({ titre: "Retour à la vue d'ensemble", distance: this.moteur.vue.distance, polaire: this.moteur.vue.polaire, duree: 4 });
        this.moteur.demarrerVisite(plans, (plan, i, n) => { this.state.visite = { titre: plan.titre, i: i + 1, n }; }, () => { this.state.visite = null; });
    }

    // ------------------------------------------------------------------ le scénario de démonstration

    async demarrerDemo() {
        try {
            const etapes = await this.orm.call("cultiveau.map", "scenario_demo", []);
            if (!etapes.length) {
                return;
            }
            this.state.demo = { actif: true, etape: 0, n: etapes.length };
            for (const e of etapes) {
                this.minuterie(async () => {
                    try {
                        const ev = await this.orm.call("cultiveau.map", "jouer_demo", [e]);
                        this.state.demo.etape++;
                        if (ev && ev.id) {
                            this.traiterEvenement(ev);
                        }
                        if (e.kpi) {
                            this.state.flash[e.kpi] = Date.now();
                            this.minuterie(() => delete this.state.flash[e.kpi], 1600);
                        }
                    } catch (err) {
                        console.warn("démo :", err);
                    }
                }, e.t * 1000);
            }
            const ambiance = await this.orm.call("cultiveau.map", "ambiance_demo", []);
            let i = 0;
            const suivant = () => {
                if (!ambiance.length) {
                    return;
                }
                this.notifier({ id: `ambiance-${i}`, genre: "ambiance", titre: "Au fil de la journée", texte: ambiance[i % ambiance.length], charge: {} });
                i++;
                this.minuterie(suivant, 14000 + Math.random() * 6000);
            };
            this.minuterie(suivant, 9000);
        } catch (e) {
            console.warn("démo :", e);
        }
    }

    // ------------------------------------------------------------------ l'éditeur de plan

    basculerEdition() {
        if (!this.state.v.utilisateur.editeur || !this.moteur) {
            return;
        }
        this.state.edition = !this.state.edition;
        this.moteur.modeEdition(this.state.edition);
        this.state.fiche = null;
        this.state.objetEdite = null;
        this.state.palette = false;
        if (this.state.edition) {
            this.state.historique = [];
            this.state.futur = [];
            this.planInitial = JSON.stringify(this.moteur.planCourant());
        }
    }
    marquerPlan() {
        this.state.historique = [...this.state.historique.slice(-30), this.dernierPlan || this.planInitial];
        this.state.futur = [];
        this.dernierPlan = JSON.stringify(this.moteur.planCourant());
        this.state.planModifie = true;
    }
    annuler() {
        const plan = this.state.historique.pop();
        if (!plan) {
            return;
        }
        this.state.futur.push(JSON.stringify(this.moteur.planCourant()));
        this.dernierPlan = plan;
        this.moteur.chargerPlan(JSON.parse(plan));
        this.moteur.modeEdition(true);
    }
    retablir() {
        const plan = this.state.futur.pop();
        if (!plan) {
            return;
        }
        this.state.historique.push(JSON.stringify(this.moteur.planCourant()));
        this.dernierPlan = plan;
        this.moteur.chargerPlan(JSON.parse(plan));
        this.moteur.modeEdition(true);
    }
    ajouterObjet(type) {
        const c = this.moteur.cam.cible;
        this.moteur.ajouterObjet(type, c.x, c.z);
        this.state.palette = false;
        this.marquerPlan();
    }
    tournerObjet(pas) {
        if (!this.state.objetEdite) {
            return;
        }
        this.moteur.tournerObjet(this.state.objetEdite.cle, pas);
        this.state.objetEdite.rot = this.moteur.objets.get(this.state.objetEdite.cle).plan.rot;
        this.marquerPlan();
    }
    supprimerObjet() {
        if (!this.state.objetEdite) {
            return;
        }
        this.moteur.supprimerObjet(this.state.objetEdite.cle);
        this.state.objetEdite = null;
        this.marquerPlan();
    }
    async chercherLien() {
        const l = this.state.lien;
        if (!l.modele || l.recherche.length < 2) {
            l.resultats = [];
            return;
        }
        l.resultats = await this.orm.call(l.modele, "name_search", [l.recherche], { limit: 8 });
    }
    lier(r) {
        const l = this.state.lien;
        this.moteur.lierObjet(this.state.objetEdite.cle, { modele: l.modele, id: r[0], nom: r[1] });
        this.state.objetEdite.entite = { modele: l.modele, id: r[0], nom: r[1] };
        l.resultats = [];
        l.recherche = "";
        this.marquerPlan();
    }
    delier() {
        this.moteur.lierObjet(this.state.objetEdite.cle, null);
        this.state.objetEdite.entite = null;
        this.marquerPlan();
    }
    async enregistrerPlan(publier) {
        try {
            const res = await this.orm.call("cultiveau.plan", "enregistrer", [this.moteur.planCourant(), publier, publier ? "Publié depuis l'éditeur" : "Brouillon de l'éditeur"]);
            this.notification.add(publier ? `Plan publié (version ${res.version}).` : `Brouillon enregistré (version ${res.version}).`, { type: "success" });
            this.state.planModifie = false;
            if (publier) {
                this.basculerEdition();
            }
        } catch (e) {
            this.notification.add(e.data?.message || e.message || String(e), { type: "danger" });
        }
    }

    // ------------------------------------------------------------------ les petits utilitaires du gabarit

    heure(iso) { return heure(iso); }
    duree(iso) { return duree(iso); }
    icone(genre) { return ICONES[genre] || "fa-cube"; }
    iconeEvenement(genre) { return ICONES_EVENEMENT[genre] || "fa-circle"; }
    euros(n) { return (Math.round(n || 0)).toLocaleString("fr-FR"); }
    get paletteParCategorie() {
        const cats = {};
        for (const p of this.kit?.PALETTE || []) {
            (cats[p.categorie] = cats[p.categorie] || []).push(p);
        }
        return Object.entries(cats);
    }
    get lignesOnglet() {
        return (this.state.v?.onglets || {})[this.state.onglet] || [];
    }
    get onglets() {
        return (this.state.v?.secteur.onglets || []).map((o) => ({ ...o, n: ((this.state.v?.onglets || {})[o.cle] || []).length }));
    }
}

registry.category("actions").add("cultiveau_vue3d.vue", MapVivante);
