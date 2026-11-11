/** @odoo-module **/
// Le schéma de câblage, côté calcul : la palette des appareils, le tracé des fils et les contrôles.
// Rien ici ne touche à l'écran : tout se rejoue hors navigateur (tests).
//
// Les contrôles viennent du référentiel technique de l'irrigation :
//   § 11.2 : l'armoire regroupe la protection contre les surintensités et les courts-circuits, la protection
//            différentielle, la protection thermique du moteur et la protection contre la foudre ;
//   § 11.3, règle 1 : chute de tension admise pour un moteur, 5 % depuis un réseau public, 8 % depuis un poste privé
//            (NF C 15-100, tableau 52W), sur le cumul depuis l'origine ; ΔU = 2 ρ L I / S en monophasé,
//            √3 ρ L I / S en triphasé, ρ ≈ 0,023 Ω·mm²/m pour le cuivre à 70 °C ;
//   § 11.3, règle 2 : appel de 5 à 8 fois l'intensité nominale en démarrage direct, 1,5 à 2 fois avec un démarreur
//            électronique ou un variateur ; au démarrage on admet généralement 10 %.

export const PAS = 20; // la grille, en pixels du dessin

const rond = (cx, cy, r) => `M${cx - r},${cy}a${r},${r} 0 1 0 ${2 * r},0a${r},${r} 0 1 0 ${-2 * r},0`;
const AMONT = { id: "amont", x: 2, y: 0, dir: "haut", genre: "p" };
const AVAL = { id: "aval", x: 2, y: 4, dir: "bas", genre: "p" };
const HAUT = (nom) => ({ id: nom, x: 1, y: 0, dir: "haut", genre: "c" });
const BAS = (nom) => ({ id: nom, x: 1, y: 4, dir: "bas", genre: "c" });
const G = (nom, y) => ({ id: nom, x: 0, y, dir: "gauche", genre: "c" });
const D = (nom, y) => ({ id: nom, x: 4, y, dir: "droite", genre: "c" });
const LAME = "M40,0V26M40,54V80M40,54L27,27"; // un contact de puissance ouvert, de haut en bas
const CONTACT = "M20,0V28M20,54V80M20,54L8,29"; // un contact de commande ouvert

// Chaque appareil : sa taille en cases, ses bornes (en cases, sur le bord), son symbole (tracé en pixels).
export const APPAREILS = {
    alimentation: { nom: "Arrivée réseau", famille: "Puissance", prefixe: "", l: 4, h: 3,
        bornes: [{ id: "aval", x: 2, y: 3, dir: "bas", genre: "p" }, { id: "N", x: 0, y: 2, dir: "gauche", genre: "c" }],
        trait: "M40,34V60M26,34H54M30,22l10,12l10,-12", textes: [{ x: 40, y: 15, t: "RÉSEAU" }],
        champs: [{ cle: "tension", nom: "Tension", choix: ["3×400 V", "230 V mono"] },
                 { cle: "origine", nom: "Origine", choix: ["Réseau public", "Poste privé"] },
                 { cle: "puissance", nom: "Puissance souscrite", unite: "kVA" }] },
    interrupteur: { nom: "Interrupteur général", famille: "Puissance", prefixe: "Q", l: 4, h: 4, bornes: [AMONT, AVAL],
        trait: LAME + "M33,26H47", champs: [{ cle: "calibre", nom: "Calibre", unite: "A" }] },
    disjoncteur: { nom: "Disjoncteur", famille: "Puissance", prefixe: "Q", l: 4, h: 4, bornes: [AMONT, AVAL],
        trait: LAME + "M35,21l10,10M45,21l-10,10",
        champs: [{ cle: "calibre", nom: "Calibre", unite: "A" }, { cle: "courbe", nom: "Courbe", choix: ["C", "D", "B"] }] },
    differentiel: { nom: "Interrupteur différentiel", famille: "Puissance", prefixe: "Q", l: 4, h: 4, bornes: [AMONT, AVAL],
        trait: LAME + "M33,26H47M28,66a12,5 0 1 0 24,0a12,5 0 1 0 -24,0", textes: [{ x: 62, y: 70, t: "Δ" }],
        champs: [{ cle: "calibre", nom: "Calibre", unite: "A" }, { cle: "sensibilite", nom: "Sensibilité", choix: ["30 mA", "300 mA"] }] },
    disj_moteur: { nom: "Disjoncteur moteur", famille: "Puissance", prefixe: "Q", l: 4, h: 4, bornes: [AMONT, AVAL, D("13", 1), D("14", 3)],
        trait: LAME + "M35,21l10,10M45,21l-10,10M40,60h9v10h-9", textes: [{ x: 60, y: 44, t: "I>" }],
        champs: [{ cle: "reglage", nom: "Réglage thermique", unite: "A" }] },
    parafoudre: { nom: "Parafoudre", famille: "Puissance", prefixe: "F", l: 4, h: 4,
        bornes: [AMONT, { id: "PE", x: 2, y: 4, dir: "bas", genre: "t" }],
        trait: "M40,0V22M28,22h24v36h-24zM40,58V80M40,28v14M35,36l5,8l5,-8", champs: [{ cle: "type", nom: "Type", choix: ["Type 2", "Type 1", "Type 1+2"] }] },
    contacteur: { nom: "Contacteur", famille: "Puissance", prefixe: "KM", l: 4, h: 4,
        bornes: [AMONT, AVAL, G("A1", 1), G("A2", 3), D("13", 1), D("14", 3)],
        trait: LAME + "M40,20a4,4 0 0 1 0,8M8,30h12v20h-12zM0,20h14v10M0,60h14v-10",
        champs: [{ cle: "calibre", nom: "Calibre", unite: "A" }, { cle: "bobine", nom: "Bobine", choix: ["230 V", "24 V"] }] },
    relais_thermique: { nom: "Relais thermique", famille: "Puissance", prefixe: "F", l: 4, h: 4, bornes: [AMONT, AVAL, D("95", 1), D("96", 3)],
        trait: "M40,0V28h11v24h-11V80", champs: [{ cle: "reglage", nom: "Réglage", unite: "A" }] },
    demarreur: { nom: "Démarreur progressif", famille: "Puissance", prefixe: "U", l: 4, h: 4,
        bornes: [AMONT, AVAL, G("marche", 1), D("R1", 1), D("R2", 3)],
        trait: "M40,0V18M22,18h36v44h-36zM40,62V80M28,54h8l12,-28h6", champs: [{ cle: "calibre", nom: "Calibre", unite: "A" }] },
    variateur: { nom: "Variateur de vitesse", famille: "Puissance", prefixe: "U", l: 4, h: 4,
        bornes: [AMONT, AVAL, G("marche", 1), G("consigne", 3), D("R1", 1), D("R2", 3)],
        trait: "M40,0V18M22,18h36v44h-36zM40,62V80M22,62L58,18", textes: [{ x: 32, y: 34, t: "~" }, { x: 49, y: 56, t: "f" }],
        champs: [{ cle: "puissance", nom: "Puissance", unite: "kW" }] },
    filtre: { nom: "Filtre dv/dt", famille: "Puissance", prefixe: "Z", l: 4, h: 4, bornes: [AMONT, AVAL],
        trait: "M40,0V18M22,18h36v44h-36zM40,62V80", textes: [{ x: 40, y: 44, t: "dv/dt" }], champs: [] },
    bornier: { nom: "Bornier", famille: "Puissance", prefixe: "X", l: 4, h: 4, bornes: [AMONT, AVAL],
        trait: "M40,0V32M40,48V80" + rond(40, 40, 8), champs: [] },
    moteur: { nom: "Moteur / pompe", famille: "Puissance", prefixe: "M", l: 4, h: 4,
        bornes: [AMONT, { id: "PE", x: 4, y: 3, dir: "droite", genre: "t" }],
        trait: "M40,0V18" + rond(40, 44, 26) + "M62,58H72V60H80", textes: [{ x: 40, y: 42, t: "M" }, { x: 40, y: 57, t: "3~" }],
        champs: [{ cle: "puissance", nom: "Puissance", unite: "kW" }, { cle: "intensite", nom: "Intensité nominale", unite: "A" },
                 { cle: "pose", nom: "Pompe", choix: ["Immergée", "De surface"] }] },
    terre: { nom: "Barrette de terre", famille: "Puissance", prefixe: "PE", l: 4, h: 3,
        bornes: [{ id: "PE", x: 2, y: 0, dir: "haut", genre: "t" }], trait: "M40,0V28M24,28H56M30,36H50M36,44H44", champs: [] },
    alim24: { nom: "Alimentation 24 V", famille: "Commande", prefixe: "G", l: 4, h: 4,
        bornes: [AMONT, { id: "+", x: 1, y: 4, dir: "bas", genre: "c" }, { id: "−", x: 3, y: 4, dir: "bas", genre: "c" }],
        trait: "M40,0V18M14,18h52v44h-52zM20,62V80M60,62V80M14,62L66,18", textes: [{ x: 28, y: 34, t: "~" }, { x: 52, y: 56, t: "24 V" }], champs: [] },
    pressostat: { nom: "Pressostat", famille: "Commande", prefixe: "B", l: 2, h: 4, bornes: [HAUT("1"), BAS("2")],
        trait: CONTACT + "M14,41H4M-12,33h16v16h-16z", textes: [{ x: -4, y: 45, t: "P" }],
        champs: [{ cle: "marche", nom: "Enclenchement", unite: "bar" }, { cle: "arret", nom: "Déclenchement", unite: "bar" }] },
    niveau: { nom: "Sécurité manque d'eau", famille: "Commande", prefixe: "B", l: 2, h: 4, bornes: [HAUT("1"), BAS("2")],
        trait: CONTACT + "M14,41H4M-12,33h16v16h-16z", textes: [{ x: -4, y: 45, t: "N" }], champs: [] },
    capteur: { nom: "Capteur de pression 4-20 mA", famille: "Commande", prefixe: "B", l: 2, h: 4, bornes: [HAUT("+"), BAS("S")],
        trait: "M20,0V22M6,22h28v36h-28zM20,58V80", textes: [{ x: 20, y: 38, t: "P" }, { x: 20, y: 52, t: "mA" }],
        champs: [{ cle: "plage", nom: "Plage", unite: "bar" }] },
    bouton_marche: { nom: "Bouton marche", famille: "Commande", prefixe: "S", l: 2, h: 4, bornes: [HAUT("13"), BAS("14")],
        trait: CONTACT + "M14,41H0M0,35v12", champs: [] },
    bouton_arret: { nom: "Bouton arrêt", famille: "Commande", prefixe: "S", l: 2, h: 4, bornes: [HAUT("11"), BAS("12")],
        trait: "M20,0V28M20,54V80M20,54L26,27M20,28H28M23,41H6M6,35v12", champs: [] },
    arret_urgence: { nom: "Arrêt d'urgence", famille: "Commande", prefixe: "S", l: 2, h: 4, bornes: [HAUT("11"), BAS("12")],
        trait: "M20,0V28M20,54V80M20,54L26,27M20,28H28M23,41H4M4,33a9,8 0 0 0 0,16z", champs: [] },
    commutateur: { nom: "Commutateur auto / 0 / manu", famille: "Commande", prefixe: "S", l: 4, h: 4,
        bornes: [{ id: "C", x: 2, y: 0, dir: "haut", genre: "c" }, { id: "auto", x: 1, y: 4, dir: "bas", genre: "c" }, { id: "manu", x: 3, y: 4, dir: "bas", genre: "c" }],
        trait: "M40,0V26M40,26L40,50M20,58V80M60,58V80M20,58h6M60,58h-6", textes: [{ x: 20, y: 48, t: "A" }, { x: 60, y: 48, t: "M" }, { x: 50, y: 34, t: "0" }], champs: [] },
    voyant: { nom: "Voyant", famille: "Commande", prefixe: "H", l: 2, h: 4, bornes: [HAUT("X1"), BAS("X2")],
        trait: "M20,0V28M20,52V80" + rond(20, 40, 12) + "M12,32l16,16M28,32l-16,16",
        champs: [{ cle: "couleur", nom: "Couleur", choix: ["Vert (marche)", "Rouge (défaut)", "Blanc (sous tension)"] }] },
    automate: { nom: "Automate / relais programmable", famille: "Commande", prefixe: "A", l: 6, h: 6,
        bornes: [{ id: "L+", x: 2, y: 0, dir: "haut", genre: "c" }, { id: "M", x: 4, y: 0, dir: "haut", genre: "c" },
                 ...[1, 2, 3, 4].map((n) => ({ id: "I" + n, x: 0, y: n + 1, dir: "gauche", genre: "c" })),
                 ...[1, 2, 3, 4].map((n) => ({ id: "Q" + n, x: 6, y: n + 1, dir: "droite", genre: "c" }))],
        trait: "M12,14h96v96h-96z", textes: [{ x: 60, y: 66, t: "API" }], champs: [] },
};

export const FAMILLES = ["Puissance", "Commande"];
export const SECTIONS = ["1,5", "2,5", "4", "6", "10", "16", "25", "35", "50", "70", "95"];
const RHO_CUIVRE = 0.023;
const nombre = (v) => { const x = parseFloat(String(v === undefined || v === null ? "" : v).replace(",", ".")); return isFinite(x) ? x : 0; };
export const fr = (x, d = 1) => (Math.round(x * 10 ** d) / 10 ** d).toFixed(d).replace(".", ",");

export function borne(composant, idBorne) {
    const def = APPAREILS[composant.type];
    return def && def.bornes.find((b) => b.id === idBorne);
}

// La position d'une borne dans le dessin, et le sens dans lequel le fil en sort.
export function positionBorne(composant, idBorne) {
    const b = borne(composant, idBorne);
    if (!b) return null;
    const v = { haut: [0, -1], bas: [0, 1], gauche: [-1, 0], droite: [1, 0] }[b.dir];
    return { x: composant.x + b.x * PAS, y: composant.y + b.y * PAS, vx: v[0], vy: v[1], genre: b.genre };
}

// Le genre d'un fil se déduit de ses deux bornes : terre, puissance ou commande.
export function genreFil(schema, fil) {
    const parId = Object.fromEntries(schema.composants.map((c) => [c.id, c]));
    const a = parId[fil.de.c] && borne(parId[fil.de.c], fil.de.b);
    const b = parId[fil.a.c] && borne(parId[fil.a.c], fil.a.b);
    if (!a || !b) return "commande";
    if (a.genre === "t" || b.genre === "t") return "terre";
    return a.genre === "p" && b.genre === "p" ? "puissance" : "commande";
}

// Le tracé d'un fil, à angles droits : une sortie droite de chaque borne, puis un coude.
export function trace(p, q, decalage = 0) {
    const s = PAS;
    const a = { x: p.x + p.vx * s, y: p.y + p.vy * s };
    const b = { x: q.x + q.vx * s, y: q.y + q.vy * s };
    const pts = [[p.x, p.y], [a.x, a.y]];
    if (p.vy !== 0 && q.vy !== 0) {
        // deux bornes verticales : on se rejoint sur une horizontale
        let y = p.vy === q.vy ? (p.vy > 0 ? Math.max(a.y, b.y) : Math.min(a.y, b.y)) : (a.y + b.y) / 2;
        if (p.vy !== q.vy && ((p.vy > 0 && b.y < a.y) || (p.vy < 0 && b.y > a.y))) {
            const x = (a.x + b.x) / 2 + decalage;
            pts.push([x, a.y], [x, b.y]);
        } else {
            y += decalage;
            pts.push([a.x, y], [b.x, y]);
        }
    } else if (p.vx !== 0 && q.vx !== 0) {
        let x = p.vx === q.vx ? (p.vx > 0 ? Math.max(a.x, b.x) : Math.min(a.x, b.x)) : (a.x + b.x) / 2;
        x += decalage;
        pts.push([x, a.y], [x, b.y]);
    } else {
        // une borne verticale et une horizontale : un seul coude, celui qui ne fait pas revenir le fil sur lui-même
        const coudes = [[a.x, b.y], [b.x, a.y]];
        const bon = coudes.find((k) => (k[0] - a.x) * p.vx + (k[1] - a.y) * p.vy >= 0 && (b.x - k[0]) * q.vx + (b.y - k[1]) * q.vy <= 0);
        pts.push(bon || coudes[0]);
    }
    pts.push([b.x, b.y], [q.x, q.y]);
    return pts.filter((pt, i) => i === 0 || pt[0] !== pts[i - 1][0] || pt[1] !== pts[i - 1][1]);
}

export function milieu(pts) {
    let total = 0;
    const longueurs = [];
    for (let i = 1; i < pts.length; i++) {
        const l = Math.abs(pts[i][0] - pts[i - 1][0]) + Math.abs(pts[i][1] - pts[i - 1][1]);
        longueurs.push(l);
        total += l;
    }
    let reste = total / 2;
    for (let i = 0; i < longueurs.length; i++) {
        if (reste <= longueurs[i]) {
            const t = longueurs[i] ? reste / longueurs[i] : 0;
            return { x: pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, y: pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t };
        }
        reste -= longueurs[i];
    }
    return { x: pts[0][0], y: pts[0][1] };
}

// Le prochain repère libre d'un appareil : Q1, Q2, KM1…
export function repereSuivant(schema, type) {
    const prefixe = APPAREILS[type].prefixe;
    if (!prefixe) return "";
    const pris = new Set(schema.composants.map((c) => c.repere));
    let n = 1;
    while (pris.has(prefixe + n)) n++;
    return prefixe + n;
}

export function numeroSuivant(schema) {
    const pris = new Set(schema.fils.map((f) => String(f.num)));
    let n = 1;
    while (pris.has(String(n))) n++;
    return String(n);
}

function designation(c) {
    const def = APPAREILS[c.type];
    const v = c.valeurs || {};
    const details = def.champs.filter((ch) => v[ch.cle]).map((ch) => (ch.unite ? `${v[ch.cle]} ${ch.unite}` : v[ch.cle]));
    return [c.nom || def.nom, ...details].join(", ");
}

// Le chemin de puissance d'un moteur jusqu'à l'arrivée réseau : les appareils traversés et les fils empruntés.
function cheminVersReseau(schema, moteur, genres) {
    const voisins = {};
    schema.fils.forEach((f) => {
        if (genres[f.id] !== "puissance") return;
        (voisins[f.de.c] = voisins[f.de.c] || []).push({ c: f.a.c, f });
        (voisins[f.a.c] = voisins[f.a.c] || []).push({ c: f.de.c, f });
    });
    const parId = Object.fromEntries(schema.composants.map((c) => [c.id, c]));
    const vient = { [moteur.id]: null };
    const file = [moteur.id];
    while (file.length) {
        const id = file.shift();
        if (parId[id] && parId[id].type === "alimentation") {
            const appareils = [], fils = [];
            for (let x = id; x !== moteur.id; x = vient[x].c) { appareils.push(parId[x]); fils.push(vient[x].f); }
            return { reseau: parId[id], appareils, fils };
        }
        for (const v of voisins[id] || []) {
            // on ne traverse pas un autre moteur ni un parafoudre : ils sont en bout de ligne
            if (v.c in vient || !parId[v.c] || ["moteur", "parafoudre"].includes(parId[v.c].type)) continue;
            vient[v.c] = { c: id, f: v.f };
            file.push(v.c);
        }
    }
    return null;
}

// Tout ce que le dessin permet de dire : le matériel, les fils, les câbles et les contrôles.
export function analyser(schema) {
    const parId = Object.fromEntries(schema.composants.map((c) => [c.id, c]));
    const genres = Object.fromEntries(schema.fils.map((f) => [f.id, genreFil(schema, f)]));
    const nomBorne = (ext) => {
        const c = parId[ext.c];
        return c ? `${c.repere || APPAREILS[c.type].nom} · ${ext.b}` : "?";
    };

    // le matériel, regroupé par désignation
    const lignes = {};
    schema.composants.filter((c) => c.type !== "alimentation").forEach((c) => {
        const d = designation(c);
        lignes[d] = lignes[d] || { designation: d, quantite: 0, reperes: [] };
        lignes[d].quantite++;
        if (c.repere) lignes[d].reperes.push(c.repere);
    });
    const materiel = Object.values(lignes).sort((a, b) => a.designation.localeCompare(b.designation, "fr"));

    const fils = schema.fils.map((f) => ({ id: f.id, num: f.num, genre: genres[f.id], de: nomBorne(f.de), a: nomBorne(f.a), section: f.section || "", longueur: f.longueur || "" }))
        .sort((a, b) => nombre(a.num) - nombre(b.num));

    const metres = {};
    schema.fils.forEach((f) => {
        if (!nombre(f.longueur)) return;
        const cle = `${{ puissance: "Câble de puissance", commande: "Fil de commande", terre: "Conducteur de terre" }[genres[f.id]]} ${f.section ? f.section + " mm²" : "(section à préciser)"}`;
        metres[cle] = (metres[cle] || 0) + nombre(f.longueur);
    });
    const cables = Object.entries(metres).map(([designation, longueur]) => ({ designation, longueur })).sort((a, b) => a.designation.localeCompare(b.designation, "fr"));

    // les contrôles
    const controles = [];
    const dire = (etat, texte, source) => controles.push({ etat, texte, source });
    const moteurs = schema.composants.filter((c) => c.type === "moteur");
    const chemins = moteurs.map((m) => ({ moteur: m, chemin: cheminVersReseau(schema, m, genres) }));
    // l'intensité d'un tronçon : la somme des moteurs qu'il alimente, tous en marche
    const intensite = {};
    chemins.forEach(({ moteur, chemin }) => chemin && chemin.fils.forEach((f) => { intensite[f.id] = (intensite[f.id] || 0) + nombre((moteur.valeurs || {}).intensite); }));

    if (!schema.composants.length) {
        dire("info", "Le schéma est vide : posez une arrivée réseau, les protections, puis le moteur.", "");
    } else if (!moteurs.length) {
        dire("info", "Aucun moteur posé : les contrôles se font départ par départ, du moteur vers l'arrivée réseau.", "");
    }
    chemins.forEach(({ moteur, chemin }) => {
        const nom = moteur.repere || "Le moteur";
        if (!chemin) {
            dire("alerte", `${nom} n'est pas relié à une arrivée réseau par des fils de puissance.`, "");
            return;
        }
        const types = chemin.appareils.map((c) => c.type);
        const a = (...liste) => liste.some((t) => types.includes(t));
        const exige = (present, quoi, appareils) => dire(present ? "ok" : "alerte",
            present ? `${nom} : ${quoi}, présente.` : `${nom} : ${quoi}, absente du départ (${appareils}).`, "§ 11.2");
        exige(a("disjoncteur", "disj_moteur"), "protection contre les surintensités et les courts-circuits", "disjoncteur ou disjoncteur moteur");
        exige(a("differentiel"), "protection différentielle", "interrupteur différentiel");
        exige(a("disj_moteur", "relais_thermique", "variateur", "demarreur"), "protection thermique du moteur", "disjoncteur moteur, relais thermique, démarreur ou variateur");
        if (!a("contacteur", "variateur", "demarreur")) {
            dire("alerte", `${nom} : aucun organe de commande sur le départ (contacteur, démarreur ou variateur).`, "§ 11.2");
        }
        if (!schema.fils.some((f) => genres[f.id] === "terre" && (f.de.c === moteur.id || f.a.c === moteur.id))) {
            dire("info", `${nom} : la terre du moteur n'est pas dessinée.`, "hors référentiel, règle de l'art");
        }

        // la chute de tension, sur le cumul depuis l'origine
        const v = chemin.reseau.valeurs || {};
        const tri = v.tension !== "230 V mono";
        const tension = tri ? 400 : 230;
        const limite = v.origine === "Poste privé" ? 8 : 5;
        const iN = nombre((moteur.valeurs || {}).intensite);
        const incomplets = chemin.fils.filter((f) => !nombre(f.longueur) || !nombre(f.section));
        if (!iN || incomplets.length) {
            dire("info", `${nom} : chute de tension non calculée. Il manque ${[!iN && "l'intensité nominale du moteur", incomplets.length && `la longueur ou la section de ${incomplets.length} fil(s) du départ`].filter(Boolean).join(" et ")}.`, "§ 11.3, règle 1");
            return;
        }
        const volts = chemin.fils.reduce((s, f) => s + (tri ? Math.sqrt(3) : 2) * RHO_CUIVRE * nombre(f.longueur) * intensite[f.id] / nombre(f.section), 0);
        const pct = volts / tension * 100;
        dire(pct <= limite ? "ok" : "alerte",
            `${nom} : chute de tension en régime établi ${fr(pct)} % (${fr(volts)} V) pour ${limite} % admis depuis ${limite === 8 ? "un poste privé" : "le réseau public"}, câbles en cuivre, tous les moteurs en marche.`,
            "§ 11.3, règle 1 (exigence réglementaire)");
        const doux = a("variateur", "demarreur");
        const [k1, k2] = doux ? [1.5, 2] : [5, 8];
        dire(pct * k2 <= 10 ? "ok" : "info",
            `${nom} : au démarrage ${doux ? "(démarreur ou variateur)" : "direct"}, l'appel est de ${doux ? "1,5 à 2" : "5 à 8"} fois l'intensité nominale, soit une chute de l'ordre de ${fr(pct * k1)} à ${fr(pct * k2)} %. On admet généralement 10 %.`,
            "§ 11.3, règle 2");
    });
    if (schema.composants.length && !schema.composants.some((c) => c.type === "parafoudre")) {
        dire("info", "Pas de parafoudre. En zone orageuse, prévoir parafoudre et mise à la terre soignée : variateurs, automates et sondes sont les premiers sinistrés.", "§ 11.2");
    }
    const prises = new Set();
    schema.fils.forEach((f) => { prises.add(f.de.c + "|" + f.de.b); prises.add(f.a.c + "|" + f.a.b); });
    const libres = schema.composants.filter((c) => APPAREILS[c.type].bornes.some((b) => b.genre === "p" && !prises.has(c.id + "|" + b.id)));
    if (libres.length) {
        dire("info", `Borne de puissance non raccordée sur : ${libres.map((c) => c.repere || APPAREILS[c.type].nom).join(", ")}.`, "");
    }
    return { materiel, fils, cables, controles, genres };
}

// Un départ type pour ne pas partir d'une page blanche : une pompe pilotée par pressostat, en 3×400 V.
export function exemple() {
    const C = (id, type, x, y, repere, valeurs = {}) => ({ id, type, x, y, repere, nom: "", valeurs });
    const F = (num, c1, b1, c2, b2, section = "", longueur = "") => ({ id: "f" + num, num: String(num), de: { c: c1, b: b1 }, a: { c: c2, b: b2 }, section, longueur });
    return {
        composants: [
            C("c1", "alimentation", 300, 20, "", { tension: "3×400 V", origine: "Réseau public" }),
            C("c2", "interrupteur", 300, 120, "Q1", { calibre: "40" }),
            C("c3", "differentiel", 300, 240, "Q2", { calibre: "40", sensibilite: "300 mA" }),
            C("c4", "disj_moteur", 300, 360, "Q3", { reglage: "11" }),
            C("c5", "contacteur", 300, 480, "KM1", { calibre: "18", bobine: "230 V" }),
            C("c6", "bornier", 300, 600, "X1"),
            C("c7", "moteur", 300, 720, "M1", { puissance: "5,5", intensite: "11", pose: "Immergée" }),
            C("c8", "parafoudre", 540, 240, "F1", { type: "Type 2" }),
            C("c9", "terre", 540, 740, "PE"),
            C("c10", "pressostat", 80, 360, "B1", { marche: "4", arret: "6" }),
            C("c11", "niveau", 80, 480, "B2"),
        ],
        fils: [
            F(1, "c1", "aval", "c2", "amont", "6", "25"), F(2, "c2", "aval", "c3", "amont", "6", "1"), F(3, "c3", "aval", "c4", "amont", "6", "1"),
            F(4, "c4", "aval", "c5", "amont", "2,5", "1"), F(5, "c5", "aval", "c6", "amont", "2,5", "1"), F(6, "c6", "aval", "c7", "amont", "2,5", "60"),
            F(7, "c2", "aval", "c8", "amont", "6", "1"), F(8, "c8", "PE", "c9", "PE", "16", "2"), F(9, "c7", "PE", "c9", "PE", "2,5", "60"),
            F(10, "c3", "aval", "c10", "1", "1,5", "8"), F(11, "c10", "2", "c11", "1", "1,5", "12"), F(12, "c11", "2", "c5", "A1", "1,5", "12"),
            { ...F(13, "c5", "A2", "c1", "N", "1,5", "2"), decal: -40 },
        ],
    };
}
