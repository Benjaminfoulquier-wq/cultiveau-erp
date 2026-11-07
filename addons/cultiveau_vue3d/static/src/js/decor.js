/** @odoo-module **/
// Le décor de la Map vivante : ce qui rend le site vrai sans venir des données (07/11/2026, « rends-le encore plus joli
// et détaillé »). Le ciel et ses nuages, l'horizon (collines, bois, village, éoliennes, château d'eau), la route avec
// ses trottoirs, son passage piéton et ses portails, les abords (massifs, mâts et drapeaux, vélos, poubelles, touffes
// d'herbe et fleurs), la cour (tubes, palettes, cônes, traces de pneus), le dedans (suspensions, poteaux, extincteurs,
// tableau blanc, planning de l'atelier, marquage au sol), et chez les agriculteurs (chemin, bornes d'irrigation, haies,
// bassin et station de pompage, balles de paille). Tout est procédural et posé une fois, à la construction ; les
// animations (nuages, drapeaux, pales, oiseaux, eau) passent par `moteur.animes`.
import { TEINTES } from "./modeles";

const T = TEINTES;

/** Un générateur pseudo-aléatoire à graine : le décor est le même à chaque ouverture. */
function hasard(graine = 7) {
    let s = graine * 9301 + 49297;
    return () => ((s = (s * 16807) % 2147483647) / 2147483647);
}

/** Dans quelle zone du plan est ce point (polygone), ou null. */
export function zoneEn(plan, x, z) {
    for (const zone of plan.zones || []) {
        const p = zone.polygone;
        let dedans = false;
        for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
            const [xi, zi] = p[i], [xj, zj] = p[j];
            if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) {
                dedans = !dedans;
            }
        }
        if (dedans) {
            return zone;
        }
    }
    return null;
}

/** Les fenêtres d'un pan de mur de bureaux : un cadre, une vitre, un appui, tous les 3 m. Posées dans le groupe du mur. */
export function fenetres(kit, g, l, epaisseur) {
    const n = Math.floor((l - 1.0) / 3);
    if (n <= 0) {
        return;
    }
    const pas = (l - 1.0) / n;
    for (let i = 0; i < n; i++) {
        const x = -l / 2 + 0.5 + pas * (i + 0.5);
        kit.bloc(g, 1.5, 1.3, epaisseur + 0.08, T.anthracite, x, 1.0, 0, { rayon: 0.02, r: 0.5, m: 0.3 });
        kit.bloc(g, 1.32, 1.12, epaisseur + 0.12, 0xbfe6f0, x, 1.09, 0, { rayon: 0.01, r: 0.08, m: 0.25, o: 0.42, ombre: false });
        kit.bloc(g, 0.08, 1.12, epaisseur + 0.13, T.anthracite, x, 1.09, 0, { vif: true, ombre: false });
        kit.bloc(g, 1.6, 0.06, epaisseur + 0.16, 0xdedad0, x, 0.96, 0, { rayon: 0.01 });
    }
}

/** Une parcelle sans dossier : du blé, une prairie avec ses balles, un tournesol ou un labour, pour que la campagne vive. */
export function champLibre(kit, i) {
    const { THREE, M, bloc, cyl, boule } = kit;
    const g = new THREE.Group();
    const L = 10, P = 8;
    const genre = ["ble", "prairie", "tournesol", "labour"][i % 4];
    if (genre === "ble") {
        bloc(g, L, 0.12, P, 0xd9b45a, 0, 0, 0, { rayon: 0.05, r: 0.95 });
        for (let r = 0; r < 9; r++) {
            const z = -P / 2 + 0.5 + r * ((P - 1) / 8);
            bloc(g, L - 0.6, 0.42, 0.22, 0xe3c46a, 0, 0.12, z, { rayon: 0.06, ombre: false });
        }
    } else if (genre === "prairie") {
        bloc(g, L, 0.12, P, 0x8fc46c, 0, 0, 0, { rayon: 0.05, r: 0.95 });
        for (const [x, z] of [[-3, -2], [0.5, 1.8], [3.2, -1.2], [-1.4, 2.6]]) {
            cyl(g, 0.72, 0.72, 1.2, 0xd9b45a, x, 0.84, z, "x", { r: 0.95, seg: 18 });
            cyl(g, 0.3, 0.3, 1.22, 0xc9a24a, x, 0.84, z, "x", { r: 0.95, seg: 12 });
        }
    } else if (genre === "tournesol") {
        bloc(g, L, 0.12, P, 0x7fb85a, 0, 0, 0, { rayon: 0.05, r: 0.95 });
        for (let r = 0; r < 5; r++) {
            const z = -P / 2 + 0.8 + (r * (P - 1.6)) / 4;
            for (let x = -L / 2 + 0.6; x < L / 2 - 0.4; x += 0.8) {
                cyl(g, 0.03, 0.04, 1.1, 0x4f8f3a, x, 0.67, z, "y", { seg: 6, ombre: false });
                cyl(g, 0.22, 0.22, 0.06, 0xf2c230, x, 1.25, z, "z", { seg: 10, ombre: false });
                cyl(g, 0.1, 0.1, 0.08, 0x5a3a1e, x, 1.25, z, "z", { seg: 8, ombre: false });
            }
        }
    } else {
        bloc(g, L, 0.12, P, 0x8c6240, 0, 0, 0, { rayon: 0.05, r: 1 });
        for (let r = 0; r < 11; r++) {
            const z = -P / 2 + 0.4 + r * ((P - 0.8) / 10);
            bloc(g, L - 0.4, 0.1, 0.18, 0x6b4a2c, 0, 0.12, z, { vif: true, ombre: false });
        }
    }
    g.add(kit.ombreContact(0.01));
    return g;
}

export function decorer(moteur) {
    const { THREE, kit, plan } = moteur;
    const { M, bloc, cyl, boule, barre } = kit;
    const rnd = hasard(11);
    const ext = plan.exterieur || {};
    const [[x0, z0], [x1, z1]] = ext.sol || [[-8, -2], [72, 66]];
    const accent = new THREE.Color(moteur.accent).getHex();
    const G = new THREE.Group();
    G.name = "decor";
    moteur.statique.add(G);
    moteur.lampes = [];
    const animer = (f) => moteur.animes.push({ statique: true, animer: f });
    const sansOmbre = (o) => { o.traverse((m) => { if (m.isMesh) { m.castShadow = false; } }); return o; };
    /** Un décalque au sol : une image ou une couleur, posée à plat juste au-dessus du sol. */
    const decal = (w, d, x, z, o = {}) => {
        const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshBasicMaterial({
            color: o.couleur ?? 0xffffff, map: o.map || null, transparent: true, opacity: o.opacite ?? 1, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }));
        m.rotation.x = -Math.PI / 2;
        m.rotation.z = o.rot || 0;
        m.position.set(x, o.y ?? 0.015, z);
        m.receiveShadow = true;
        G.add(m);
        return m;
    };
    const texte = (t, w, h, x, y, z, o = {}) => {
        const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: kit.texteTexture(t, { couleur: o.couleur || "#ffffff", taille: o.taille || 56 }), transparent: true, side: THREE.DoubleSide }));
        m.position.set(x, y, z);
        m.rotation.y = o.rot || 0;
        (o.parent || G).add(m);
        return m;
    };

    // ------------------------------------------------------------------ le ciel : des nuages qui dérivent
    const nuageTexture = kit.texture("nuage", 256, 128, (ctx, w, h) => {
        ctx.clearRect(0, 0, w, h);
        for (const [cx, cy, r] of [[70, 80, 46], [120, 60, 58], [175, 78, 44], [110, 92, 40], [150, 95, 36]]) {
            const gr = ctx.createRadialGradient(cx, cy, 2, cx, cy, r);
            gr.addColorStop(0, "rgba(255,255,255,0.95)");
            gr.addColorStop(0.55, "rgba(255,255,255,0.55)");
            gr.addColorStop(1, "rgba(255,255,255,0)");
            ctx.fillStyle = gr;
            ctx.fillRect(0, 0, w, h);
        }
    });
    nuageTexture.wrapS = nuageTexture.wrapT = THREE.ClampToEdgeWrapping;
    nuageTexture.needsUpdate = true;
    const nuages = [];
    for (let i = 0; i < 8; i++) {
        const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: nuageTexture, transparent: true, opacity: 0.75 + rnd() * 0.2, depthWrite: false }));
        const echelle = 26 + rnd() * 30;
        s.scale.set(echelle, echelle * 0.5, 1);
        s.position.set(x0 - 60 + rnd() * (x1 - x0 + 160), 48 + rnd() * 26, z0 - 120 + rnd() * 120);
        s.userData.v = 0.35 + rnd() * 0.5;
        G.add(s);
        nuages.push(s);
    }
    animer((dt) => { for (const n of nuages) { n.position.x += n.userData.v * dt; if (n.position.x > x1 + 110) { n.position.x = x0 - 90; } } });

    // ------------------------------------------------------------------ l'horizon : collines, bois, village, éoliennes, château d'eau
    const collines = [[-150, -170, 190, 0xb3cf9a], [40, -230, 260, 0xa9c8a2], [210, -160, 170, 0xb8d0a0], [-60, -110, 120, 0xa5c58a], [120, -120, 110, 0xaecb94], [300, -60, 150, 0xa9c4b5], [-230, -40, 140, 0xa9c4b5]];
    for (const [x, z, r, c] of collines) {
        const col = sansOmbre(boule(G, r, c, x, -r * 0.84, z, { seg: 18, r: 1, ombre: false }));
        col.scale.y = 0.22;
        col.receiveShadow = false;
    }
    const bois = (za, xa, xb, pas, h) => { for (let x = xa; x <= xb; x += pas) { const a = sansOmbre(M.arbre({ h: h + rnd() * 2.5, sapin: rnd() < 0.3 })); a.position.set(x + rnd() * 2, 0, za + rnd() * 3); G.add(a); } };
    bois(-26, -70, 140, 5.5, 6);
    bois(-48, -90, 160, 7, 7.5);
    bois(-16, 70, 130, 4.5, 5);
    // le village : des maisons aux toits de tuiles, un clocher
    const maison = (x, z, rot, l = 7, p = 6, c = 0xf1ece2) => {
        const g = new THREE.Group();
        bloc(g, l, 3, p, c, 0, 0, 0, { rayon: 0.05 });
        const toit = new THREE.Mesh(new THREE.CylinderGeometry(0.01, p * 0.72, l, 4, 1), kit.mat(0xb8573f, { r: 0.9 }));
        toit.rotation.z = Math.PI / 2;
        toit.rotation.x = Math.PI / 4;
        toit.position.y = 3 + p * 0.5;
        toit.scale.z = 0.55;
        toit.castShadow = true;
        g.add(toit);
        cyl(g, 0.25, 0.25, 1.2, 0xc9c2b4, l * 0.3, 4.6, 0, "y");
        g.position.set(x, 0, z);
        g.rotation.y = rot;
        G.add(sansOmbre(g));
        return g;
    };
    for (const [x, z, r] of [[134, -54, 0.1], [143, -49, -0.3], [152, -56, 0.4], [139, -64, 0.9], [160, -46, 0.2], [148, -70, -0.6], [168, -60, 0.5], [126, -46, -0.2]]) {
        maison(x, z, r, 6 + rnd() * 4, 5 + rnd() * 3, [0xf1ece2, 0xe8dcc6, 0xf6efe0][Math.floor(rnd() * 3)]);
    }
    {
        const clocher = new THREE.Group();
        bloc(clocher, 4, 9, 4, 0xe2d9c5, 0, 0, 0, { rayon: 0.05 });
        const fleche = new THREE.Mesh(new THREE.ConeGeometry(2.6, 6, 4), kit.mat(0x5a6b7a, { r: 0.8 }));
        fleche.position.y = 12;
        fleche.rotation.y = Math.PI / 4;
        clocher.add(fleche);
        clocher.position.set(156, 0, -66);
        G.add(sansOmbre(clocher));
    }
    // les éoliennes qui tournent, loin derrière
    const pales = [];
    for (const [x, z, h] of [[-38, -78, 26], [-4, -104, 30], [34, -92, 27]]) {
        const g = new THREE.Group();
        cyl(g, 0.5, 1.1, h, 0xf2f2ee, 0, h / 2, 0, "y", { r: 0.6, seg: 10 });
        bloc(g, 3.2, 1.8, 1.6, 0xf2f2ee, 0.4, h - 0.9, 0, { rayon: 0.4 });
        const rotor = new THREE.Group();
        rotor.position.set(2.2, h, 0);
        for (let k = 0; k < 3; k++) {
            const pale = bloc(rotor, 0.5, h * 0.55, 0.12, 0xf7f7f3, 0, 0, 0, { rayon: 0.05, ombre: false });
            pale.position.y = h * 0.275;
            const bras = new THREE.Group();
            bras.rotation.x = (k * Math.PI * 2) / 3;
            bras.add(pale);
            rotor.add(bras);
        }
        g.add(rotor);
        g.position.set(x, 0, z);
        g.rotation.y = 0.5;
        G.add(sansOmbre(g));
        pales.push(rotor);
    }
    animer((dt) => { for (const r of pales) { r.rotation.x += dt * 0.9; } });
    // le château d'eau du village : l'eau, ça se voit de loin
    {
        const g = new THREE.Group();
        cyl(g, 1.6, 2.2, 16, 0xe6e1d6, 0, 8, 0, "y", { r: 0.8, seg: 14 });
        cyl(g, 5.5, 3.2, 5, 0xeeeae1, 0, 18.5, 0, "y", { r: 0.8, seg: 18 });
        cyl(g, 5.6, 5.6, 0.6, accent, 0, 21.2, 0, "y", { r: 0.6, seg: 18 });
        cyl(g, 0.01, 5.4, 1.6, 0xdcd6ca, 0, 22.3, 0, "y", { r: 0.8, seg: 18 });
        g.position.set(182, 0, -84);
        G.add(sansOmbre(g));
    }

    // ------------------------------------------------------------------ la route : trottoir, bordures, lignes, passage piéton, portails
    if (ext.route) {
        const [a, b] = ext.route;
        const l = Math.abs(b[0] - a[0]);
        const xm = (a[0] + b[0]) / 2, zr = a[1];
        // le trottoir côté dépôt, avec sa bordure ; côté champs, un accotement en gravier et un fossé
        const trottoir = new THREE.Mesh(new THREE.PlaneGeometry(l, 1.4), new THREE.MeshStandardMaterial({ map: kit.sol("trottoir", l, 1.4), roughness: 0.95 }));
        trottoir.rotation.x = -Math.PI / 2;
        trottoir.position.set(xm, 0.05, zr - 3.7);
        trottoir.receiveShadow = true;
        G.add(trottoir);
        bloc(G, l, 0.14, 0.22, 0xd3cfc5, xm, -0.02, zr - 3.0, { rayon: 0.03, r: 0.9 });
        const accotement = new THREE.Mesh(new THREE.PlaneGeometry(l, 1.6), new THREE.MeshStandardMaterial({ map: kit.sol("gravier", l, 1.6), roughness: 1 }));
        accotement.rotation.x = -Math.PI / 2;
        accotement.position.set(xm, -0.005, zr + 3.8);
        accotement.receiveShadow = true;
        G.add(accotement);
        decal(l, 0.7, xm, zr + 4.95, { couleur: 0x5f6e4e, opacite: 0.75, y: -0.02 });
        // les lignes de rive
        for (const dz of [-2.85, 2.85]) {
            decal(l, 0.12, xm, zr + dz, { couleur: 0xf2eee4, opacite: 0.9, y: 0.005 });
        }
        // le passage piéton devant l'entrée des clients, et les panneaux
        for (const [[ax], [bx]] of ext.acces || []) {
            if (ax < 30) {
                for (let k = -3; k <= 3; k++) {
                    decal(0.55, 5.2, ax + k * 0.95, zr, { couleur: 0xf7f4ec, opacite: 0.92, y: 0.006 });
                }
                // le panneau « passage piéton » et le panneau du dépôt à l'entrée
                const p = new THREE.Group();
                cyl(p, 0.04, 0.04, 2.4, T.grisFonce, 0, 1.2, 0, "y", { m: 0.5, seg: 8 });
                bloc(p, 0.7, 0.7, 0.04, 0x2a63b0, 0, 2.2, 0, { rayon: 0.02 });
                bloc(p, 0.5, 0.5, 0.05, 0xf7f7f3, 0, 2.3, 0, { rayon: 0.02 });
                p.position.set(ax - 3.4, 0, zr - 3.6);
                G.add(p);
            } else {
                decal(4, 1.6, bx, zr - 3.7, { map: kit.texteTexture("LIVRAISONS →", { couleur: "#1d2f38", taille: 60 }), opacite: 0.85, y: 0.06 });
            }
        }
        // les portails coulissants (ouverts) aux deux accès de la clôture
        for (const [[ax]] of ext.acces || []) {
            for (const dx of [-3, 3]) {
                cyl(G, 0.14, 0.14, 2.0, T.anthracite, ax + dx, 1.0, zr - 2.5, "y", { m: 0.3, r: 0.5, seg: 10 });
                bloc(G, 0.32, 0.08, 0.32, accent, ax + dx, 2.0, zr - 2.5, { rayon: 0.02 });
            }
            const vantail = new THREE.Group();
            for (let k = 0; k < 10; k++) {
                bloc(vantail, 0.05, 1.7, 0.05, 0x5d6b78, k * 0.6 - 2.7, 0.1, 0, { vif: true, m: 0.5, r: 0.4, ombre: false });
            }
            bloc(vantail, 5.8, 0.06, 0.06, 0x5d6b78, 0, 1.76, 0, { vif: true, m: 0.5 });
            bloc(vantail, 5.8, 0.06, 0.06, 0x5d6b78, 0, 0.1, 0, { vif: true, m: 0.5 });
            vantail.position.set(ax + 6, 0, zr - 2.5 + 0.3);
            G.add(vantail);
        }
    }

    // ------------------------------------------------------------------ les abords : massifs, auvent, mâts, vélos, poubelles, marquages
    const contour = plan.contour || [];
    const zFacade = Math.max(...contour.map((p) => p[1]));
    const entree = (plan.portes || []).find((p) => p.nom === "entree_clients");
    if (entree) {
        const xe = (entree.a[0] + entree.b[0]) / 2, le = Math.abs(entree.b[0] - entree.a[0]);
        // l'auvent de l'entrée, à la couleur, qui porte le nom de la société
        const auvent = new THREE.Group();
        bloc(auvent, le + 2.6, 0.16, 1.6, accent, 0, 2.75, 0.9, { rayon: 0.04 });
        bloc(auvent, le + 2.6, 0.5, 0.08, accent, 0, 2.3, 1.68, { rayon: 0.02 });
        for (const dx of [-(le / 2 + 1.1), le / 2 + 1.1]) {
            cyl(auvent, 0.06, 0.06, 2.75, T.anthracite, dx, 1.375, 1.6, "y", { m: 0.5, seg: 10 });
        }
        const nom = (moteur.options.nom || "").toUpperCase();
        if (nom) {
            const m = new THREE.Mesh(new THREE.PlaneGeometry(le + 2.2, 0.42), new THREE.MeshBasicMaterial({ map: kit.texteTexture(nom, { couleur: "#ffffff", taille: 64 }), transparent: true }));
            m.position.set(0, 2.55, 1.73);
            auvent.add(m);
        }
        auvent.position.set(xe, 0, zFacade);
        G.add(auvent);
        // le tapis « bienvenue » et les deux massifs fleuris de part et d'autre
        decal(le - 0.4, 1.1, xe, zFacade + 0.75, { couleur: 0x3a4a56, opacite: 0.85, y: 0.02 });
        decal(le - 0.8, 0.5, xe, zFacade + 0.75, { map: kit.texteTexture("BIENVENUE", { couleur: "#f4f1ea", taille: 60 }), y: 0.03 });
        for (const dx of [-(le / 2 + 2.3), le / 2 + 2.3]) {
            const j = new THREE.Group();
            bloc(j, 3.0, 0.45, 0.7, 0x8a6a48, 0, 0, 0, { rayon: 0.03 });
            bloc(j, 2.8, 0.1, 0.5, 0x4a3828, 0, 0.42, 0, { vif: true, ombre: false });
            for (let k = 0; k < 5; k++) {
                boule(j, 0.22 + rnd() * 0.12, [T.feuillage, T.feuillageFonce, 0x7fb85a][k % 3], -1.2 + k * 0.6, 0.62, (rnd() - 0.5) * 0.3, { seg: 8 });
                boule(j, 0.06, [0xf2c230, 0xe85d8a, 0xffffff, 0xf28c28][Math.floor(rnd() * 4)], -1.3 + k * 0.6 + rnd() * 0.3, 0.86, (rnd() - 0.5) * 0.3, { seg: 6, ombre: false });
            }
            j.position.set(xe + dx, 0, zFacade + 0.7);
            G.add(j);
        }
    }
    // les mâts et leurs drapeaux
    const drapeaux = [];
    const totem = (plan.objets || []).find((o) => o.type === "totem");
    if (totem) {
        for (let k = 0; k < 2; k++) {
            const x = totem.x - 2.2 - k * 1.0, z = totem.z + 0.2;
            cyl(G, 0.04, 0.06, 6.5, 0xdfe5ea, x, 3.25, z, "y", { m: 0.7, r: 0.3, seg: 10 });
            boule(G, 0.09, 0xf2c230, x, 6.55, z, { seg: 8, e: 0.2 });
            const d = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 0.85, 8, 1), new THREE.MeshStandardMaterial({ map: k === 0 ? kit.logoTexture(moteur.options.logo || "C", moteur.accent) : null, color: k === 0 ? 0xffffff : accent, side: THREE.DoubleSide, roughness: 0.8 }));
            d.position.set(x + 0.67, 5.95, z);
            d.userData.phase = k * 1.3;
            d.castShadow = true;
            G.add(d);
            drapeaux.push(d);
        }
        animer((dt, t) => {
            for (const d of drapeaux) {
                const p = d.geometry.attributes.position;
                for (let i = 0; i < p.count; i++) {
                    const u = (p.getX(i) + 0.65) / 1.3;
                    p.setZ(i, Math.sin(t * 5 + d.userData.phase + u * 4) * 0.09 * u);
                }
                p.needsUpdate = true;
                d.rotation.y = Math.sin(t * 0.7 + d.userData.phase) * 0.18;
            }
        });
    }
    const parking = (plan.zones || []).find((z) => z.type === "parking");
    if (parking) {
        const xs = parking.polygone.map((p) => p[0]), zs = parking.polygone.map((p) => p[1]);
        const px0 = Math.min(...xs), pz0 = Math.min(...zs), px1 = Math.max(...xs);
        // le range-vélos, les poubelles de tri
        const velos = new THREE.Group();
        for (let k = 0; k < 3; k++) {
            barre(velos, [k * 0.7, 0, -0.35], [k * 0.7, 0.75, -0.35], 0.025, 0xdfe5ea, { m: 0.8, r: 0.3 });
            barre(velos, [k * 0.7, 0, 0.35], [k * 0.7, 0.75, 0.35], 0.025, 0xdfe5ea, { m: 0.8, r: 0.3 });
            barre(velos, [k * 0.7, 0.75, -0.35], [k * 0.7, 0.75, 0.35], 0.025, 0xdfe5ea, { m: 0.8, r: 0.3 });
        }
        velos.position.set(px0 + 5, 0, pz0 + 0.8);
        G.add(velos);
        for (const [k, c] of [[0, 0xf2c230], [1, 0x4fa83a], [2, 0x6c7883]].values()) {
            cyl(G, 0.3, 0.26, 0.95, c, px0 + 1.2 + k * 0.8, 0.475, pz0 + 0.8, "y", { r: 0.6, seg: 12 });
            cyl(G, 0.32, 0.32, 0.08, T.anthracite, px0 + 1.2 + k * 0.8, 0.99, pz0 + 0.8, "y", { r: 0.6, seg: 12 });
        }
        // les flèches de circulation et la place PMR
        const fleche = kit.texteTexture("➜", { couleur: "#f4f1ea", taille: 110 });
        decal(2.4, 1.2, px0 + 5, pz0 + 6.8, { map: fleche, opacite: 0.75, y: 0.01, rot: Math.PI });
        decal(2.4, 1.2, px1 - 4, pz0 + 6.8, { map: fleche, opacite: 0.75, y: 0.01 });
        const pmr = (plan.places || []).find((p) => p.cle === "parking-1");
        if (pmr) {
            decal(1.1, 1.1, pmr.x, pmr.z + 1.4, { map: kit.texteTexture("♿", { couleur: "#f4f1ea", taille: 100 }), opacite: 0.9, y: 0.01 });
            decal(2.6, 5.2, pmr.x, pmr.z, { couleur: 0x2a63b0, opacite: 0.22, y: 0.004 });
        }
    }

    // ------------------------------------------------------------------ la cour : tubes, palettes, cônes, traces
    const cour = (plan.zones || []).find((z) => z.type === "cour");
    if (cour) {
        const xs = cour.polygone.map((p) => p[0]), zs = cour.polygone.map((p) => p[1]);
        const cx0 = Math.min(...xs), cz0 = Math.min(...zs), cx1 = Math.max(...xs), cz1 = Math.max(...zs);
        // le fardeau de tubes PVC sur ses cales
        const tubes = new THREE.Group();
        for (const dz of [-1.8, 1.8]) {
            bloc(tubes, 0.18, 0.18, 1.2, 0x8a6a48, dz, 0, 0, { vif: true });
        }
        for (let rang = 0; rang < 3; rang++) {
            for (let k = 0; k < 5 - rang; k++) {
                cyl(tubes, 0.1, 0.1, 6, rang % 2 ? 0x2f7fc1 : 0xf1ece2, 0, 0.28 + rang * 0.18, -0.4 + k * 0.21 + rang * 0.105, "x", { r: 0.35, seg: 12 });
            }
        }
        tubes.position.set(cx0 + 5.5, 0, cz1 - 4.2);
        G.add(tubes);
        // les piles de palettes vides
        for (const [dx, n] of [[0, 6], [1.35, 4], [2.7, 8]]) {
            for (let k = 0; k < n; k++) {
                bloc(G, 1.2, 0.14, 0.8, 0xd2b07a, cx1 - 21.5 + dx, k * 0.15, cz1 - 2.8, { rayon: 0.01, ombre: k === n - 1 });
            }
        }
        // les cônes et les traces de pneus devant les places des camions
        const camions = (plan.places || []).filter((p) => p.usage === "camion");
        for (const [i, p] of camions.entries()) {
            decal(2.2, 1.2, p.x + 0.4, p.z - 0.3, { couleur: 0x2c3a43, opacite: 0.16 + (i % 2) * 0.08, y: 0.008 });
            for (const dz of [-0.9, 0.9]) {
                decal(0.32, 9, p.x + dz, p.z + 3.5, { couleur: 0x2c3a43, opacite: 0.12, y: 0.007 });
            }
        }
        if (camions.length) {
            const p = camions[0];
            for (const [dx, dz] of [[-2.2, -1.5], [-2.9, -0.4], [-2.4, 1.0]]) {
                cyl(G, 0.02, 0.2, 0.6, T.orange, p.x + dx, 0.3, p.z + dz, "y", { seg: 10 });
                cyl(G, 0.13, 0.13, 0.04, 0xffffff, p.x + dx, 0.32, p.z + dz, "y", { seg: 10, ombre: false });
                bloc(G, 0.42, 0.03, 0.42, T.anthracite, p.x + dx, 0, p.z + dz, { vif: true });
            }
        }
        // devant la porte de la cour : un transpalette et des caisses
        const porteCour = (plan.portes || []).find((p) => p.nom === "porte_cour");
        if (porteCour) {
            const x = porteCour.a[0] + 3.2, z = (porteCour.a[1] + porteCour.b[1]) / 2 - 3.2;
            const tp = new THREE.Group();
            bloc(tp, 1.15, 0.08, 0.16, T.orange, 0, 0.08, -0.25, { rayon: 0.01 });
            bloc(tp, 1.15, 0.08, 0.16, T.orange, 0, 0.08, 0.25, { rayon: 0.01 });
            bloc(tp, 0.3, 0.5, 0.56, T.orange, -0.65, 0, 0, { rayon: 0.03 });
            barre(tp, [-0.8, 0.5, 0], [-1.25, 1.1, 0], 0.025, T.anthracite);
            bloc(tp, 0.3, 0.06, 0.04, T.anthracite, -1.25, 1.08, 0, { vif: true });
            tp.position.set(x, 0, z);
            tp.rotation.y = 0.5;
            G.add(tp);
            bloc(G, 0.9, 0.5, 0.7, T.carton, x + 2.0, 0, z + 0.2, { rayon: 0.02 });
            bloc(G, 0.8, 0.45, 0.6, 0xc8934e, x + 2.0, 0.5, z + 0.25, { rayon: 0.02 });
            bloc(G, 0.9, 0.5, 0.7, T.carton, x + 3.1, 0, z - 0.1, { rayon: 0.02 });
        }
    }

    // ------------------------------------------------------------------ le dedans : suspensions, poteaux, extincteurs, tableaux, marquage
    const lampe = (x, z, haut = 3.2) => {
        const g = new THREE.Group();
        cyl(g, 0.01, 0.01, 0.5, T.anthracite, 0, haut - 0.25, 0, "y", { seg: 6, ombre: false });
        const abat = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.34, 0.26, 16, 1, true), new THREE.MeshStandardMaterial({ color: 0x2c3a43, roughness: 0.5, metalness: 0.4, side: THREE.DoubleSide }));
        abat.position.y = haut - 0.63;
        g.add(abat);
        const ampoule = new THREE.Mesh(new THREE.CircleGeometry(0.3, 16), new THREE.MeshStandardMaterial({ color: 0xfff1c8, emissive: 0xffe9b0, emissiveIntensity: 0.9, roughness: 0.6 }));
        ampoule.rotation.x = Math.PI / 2;
        ampoule.position.y = haut - 0.77;
        g.add(ampoule);
        g.position.set(x, 0, z);
        G.add(g);
        moteur.lampes.push(ampoule.material);
    };
    const panneauLed = (x, z, l = 1.2, p = 0.4, haut = 3.1) => {
        const m = new THREE.Mesh(new THREE.BoxGeometry(l, 0.05, p), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff6e2, emissiveIntensity: 0.7, roughness: 0.4 }));
        m.position.set(x, haut, z);
        G.add(m);
        moteur.lampes.push(m.material);
    };
    for (const z of plan.zones || []) {
        const xs = z.polygone.map((p) => p[0]), zs = z.polygone.map((p) => p[1]);
        const [ax, bx, az, bz] = [Math.min(...xs), Math.max(...xs), Math.min(...zs), Math.max(...zs)];
        if (z.exterieur) {
            continue;
        }
        if (z.type === "stockage" || z.type === "atelier") {
            for (let x = ax + 2.5; x < bx - 1; x += 4.5) {
                for (let zz = az + 2.5; zz < bz - 1; zz += 4.5) {
                    lampe(x, zz);
                }
            }
        } else {
            for (let x = ax + 1.8; x < bx - 0.8; x += 3.2) {
                for (let zz = az + 1.8; zz < bz - 0.8; zz += 3.2) {
                    panneauLed(x, zz);
                }
            }
        }
    }
    // les poteaux de la charpente le long des murs du hall (hors portes)
    const dansPorte = (x, z) => (plan.portes || []).some((p) => Math.hypot((p.a[0] + p.b[0]) / 2 - x, (p.a[1] + p.b[1]) / 2 - z) < 3.2);
    for (const mur of plan.murs || []) {
        const dx = mur.b[0] - mur.a[0], dz = mur.b[1] - mur.a[1];
        const l = Math.hypot(dx, dz);
        if (l < 9) {
            continue;
        }
        const [cx, cz] = [(contour.reduce((s, p) => s + p[0], 0) / contour.length), (contour.reduce((s, p) => s + p[1], 0) / contour.length)];
        const nx = dz / l, nz = -dx / l;
        const versCentre = ((cx - (mur.a[0] + mur.b[0]) / 2) * nx + (cz - (mur.a[1] + mur.b[1]) / 2) * nz) > 0 ? 1 : -1;
        for (let s = 5; s < l - 2; s += 5) {
            const x = mur.a[0] + (dx / l) * s + nx * versCentre * 0.32, z = mur.a[1] + (dz / l) * s + nz * versCentre * 0.32;
            const zone = zoneEn(plan, x, z);
            if (!zone || !["stockage", "atelier", "magasin"].includes(zone.type) || dansPorte(x, z)) {
                continue;
            }
            bloc(G, 0.26, 3.2, 0.26, 0x8a97a3, x, 0, z, { rayon: 0.02, r: 0.5, m: 0.5 });
            bloc(G, 0.34, 0.06, 0.34, 0x6c7883, x, 0, z, { vif: true });
        }
    }
    // les extincteurs, le tableau blanc du bureau d'étude, le planning de l'atelier, l'horloge de l'accueil
    const extincteur = (x, z, rot = 0) => {
        const g = new THREE.Group();
        bloc(g, 0.3, 0.4, 0.3, T.rouge, 0, 1.0, 0, { rayon: 0.02 });
        texte("EXT", 0.26, 0.2, 0, 1.2, 0.16, { taille: 40, parent: g });
        cyl(g, 0.07, 0.07, 0.5, T.rouge, 0, 0.75, 0.05, "y", { r: 0.4, m: 0.3, seg: 12 });
        cyl(g, 0.04, 0.04, 0.08, T.anthracite, 0, 1.04, 0.05, "y", { seg: 8 });
        g.position.set(x, 0, z);
        g.rotation.y = rot;
        G.add(g);
    };
    for (const z of plan.zones || []) {
        if (z.exterieur || !["stockage", "atelier", "accueil", "bureau"].includes(z.type)) {
            continue;
        }
        const xs = z.polygone.map((p) => p[0]), zs = z.polygone.map((p) => p[1]);
        extincteur(Math.min(...xs) + 0.3, Math.min(...zs) + 1.2, Math.PI / 2);
    }
    const bureau = (plan.zones || []).find((z) => z.cle === "bureau");
    if (bureau) {
        const xs = bureau.polygone.map((p) => p[0]), zs = bureau.polygone.map((p) => p[1]);
        const tableau = kit.texture("tableau_blanc", 512, 320, (ctx, w, h) => {
            ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, w, h);
            ctx.strokeStyle = "#2a63b0"; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(40, 250); ctx.lineTo(140, 150); ctx.lineTo(240, 190); ctx.lineTo(340, 90); ctx.lineTo(470, 120); ctx.stroke();
            ctx.strokeStyle = "#d94f45"; ctx.beginPath(); ctx.arc(340, 90, 22, 0, Math.PI * 2); ctx.stroke();
            ctx.fillStyle = "#1d2f38"; ctx.font = "bold 30px sans-serif"; ctx.fillText("Débit · pression · pertes de charge", 40, 50);
            ctx.font = "26px sans-serif"; ctx.fillStyle = "#4fa83a"; ctx.fillText("Q = 150 m³/h", 60, 300); ctx.fillStyle = "#f28c28"; ctx.fillText("HMT 70 m", 300, 300);
        });
        tableau.wrapS = tableau.wrapT = THREE.ClampToEdgeWrapping;
        tableau.needsUpdate = true;
        const tb = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.35), new THREE.MeshStandardMaterial({ map: tableau, roughness: 0.4 }));
        tb.position.set((Math.min(...xs) + Math.max(...xs)) / 2 - 0.5, 1.75, Math.min(...zs) + 0.14);
        G.add(tb);
        bloc(G, 2.3, 0.05, 0.06, 0xdfe5ea, tb.position.x, 1.05, tb.position.z + 0.02, { rayon: 0.01, m: 0.6 });
    }
    const atelier = (plan.zones || []).find((z) => z.type === "atelier");
    if (atelier) {
        const xs = atelier.polygone.map((p) => p[0]), zs = atelier.polygone.map((p) => p[1]);
        const planning = kit.texture("planning_atelier", 512, 384, (ctx, w, h) => {
            ctx.fillStyle = "#c9a26a"; ctx.fillRect(0, 0, w, h);
            ctx.fillStyle = "#1d2f38"; ctx.font = "bold 34px sans-serif"; ctx.fillText("SEMAINE", 24, 50);
            const couleurs = ["#f2c230", "#9fd3e3", "#f6a7c1", "#b8e986", "#f2c230", "#ffffff"];
            for (let i = 0; i < 12; i++) {
                ctx.save(); ctx.translate(40 + (i % 4) * 118, 90 + Math.floor(i / 4) * 95); ctx.rotate((((i * 7) % 5) - 2) * 0.04);
                ctx.fillStyle = couleurs[i % couleurs.length]; ctx.fillRect(0, 0, 96, 76);
                ctx.fillStyle = "rgba(0,0,0,0.5)"; ctx.fillRect(10, 20, 70, 4); ctx.fillRect(10, 36, 50, 4); ctx.fillRect(10, 52, 60, 4);
                ctx.restore();
            }
        });
        planning.wrapS = planning.wrapT = THREE.ClampToEdgeWrapping;
        planning.needsUpdate = true;
        const pl = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 1.35), new THREE.MeshStandardMaterial({ map: planning, roughness: 0.8 }));
        pl.position.set(Math.min(...xs) + 0.14, 1.7, (Math.min(...zs) + Math.max(...zs)) / 2 - 4);
        pl.rotation.y = Math.PI / 2;
        G.add(pl);
    }
    const accueil = (plan.zones || []).find((z) => z.type === "accueil");
    if (accueil) {
        const xs = accueil.polygone.map((p) => p[0]), zs = accueil.polygone.map((p) => p[1]);
        const x = Math.min(...xs) + 0.14, z = Math.min(...zs) + 1.6;
        cyl(G, 0.3, 0.3, 0.04, 0xffffff, x, 2.35, z, "x", { seg: 24 });
        cyl(G, 0.32, 0.32, 0.03, T.anthracite, x - 0.005, 2.35, z, "x", { seg: 24 });
        const aiguilles = new THREE.Group();
        bloc(aiguilles, 0.02, 0.2, 0.01, T.anthracite, 0, 0, 0, { vif: true, ombre: false });
        const minutes = new THREE.Group();
        bloc(minutes, 0.015, 0.26, 0.01, T.anthracite, 0, 0, 0, { vif: true, ombre: false });
        aiguilles.position.set(x + 0.03, 2.35, z);
        minutes.position.set(x + 0.035, 2.35, z);
        G.add(aiguilles, minutes);
        animer(() => { const d = new Date(); aiguilles.rotation.x = -((d.getHours() % 12) / 12 + d.getMinutes() / 720) * Math.PI * 2; minutes.rotation.x = -(d.getMinutes() / 60) * Math.PI * 2; });
    }
    // le marquage au sol de l'allée principale du stockage
    const stockage = (plan.zones || []).find((z) => z.type === "stockage");
    if (stockage) {
        const xs = stockage.polygone.map((p) => p[0]), zs = stockage.polygone.map((p) => p[1]);
        const l = Math.max(...xs) - Math.min(...xs) - 1, xm = (Math.min(...xs) + Math.max(...xs)) / 2;
        for (const dz of [1.7, 0.3]) {
            decal(l, 0.1, xm, Math.max(...zs) - dz, { couleur: 0xf2c230, opacite: 0.85, y: 0.012 });
        }
        decal(2.6, 0.9, Math.min(...xs) + 2.2, Math.max(...zs) - 1.0, { map: kit.texteTexture("PIÉTONS", { couleur: "#f2c230", taille: 60 }), y: 0.013 });
    }

    // ------------------------------------------------------------------ chez les agriculteurs : chemin, bornes, haies, bassin, pompage, balles
    const champs = (plan.places || []).filter((p) => p.usage === "champ");
    if (champs.length) {
        const zc = champs[0].z;
        const chemin = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, 2.6), new THREE.MeshStandardMaterial({ map: kit.sol("gravier", x1 - x0, 2.6), roughness: 1 }));
        chemin.rotation.x = -Math.PI / 2;
        chemin.position.set((x0 + x1) / 2, -0.01, zc - 5.6);
        chemin.receiveShadow = true;
        G.add(chemin);
        for (const dz of [-0.7, 0.7]) {
            decal(x1 - x0, 0.3, (x0 + x1) / 2, zc - 5.6 + dz, { couleur: 0x6b4a2c, opacite: 0.35, y: 0.0 });
        }
        // une borne d'irrigation au coin de chaque parcelle, une haie entre deux parcelles sur trois
        champs.forEach((c, i) => {
            cyl(G, 0.13, 0.15, 0.85, 0x2a63b0, c.x - 4.6, 0.425, c.z - 4.6, "y", { r: 0.5, m: 0.3, seg: 12 });
            cyl(G, 0.2, 0.2, 0.1, 0x2a63b0, c.x - 4.6, 0.9, c.z - 4.6, "y", { r: 0.5, seg: 12 });
            cyl(G, 0.05, 0.05, 0.5, T.gris, c.x - 4.35, 0.6, c.z - 4.6, "x", { m: 0.6, seg: 8 });
            if (i % 3 === 1 && champs[i + 1]) {
                const h = M.haie({ l: 8.4 });
                h.position.set((c.x + champs[i + 1].x) / 2, 0, c.z);
                h.rotation.y = Math.PI / 2;
                G.add(h);
                for (let k = 0; k < 3; k++) {
                    const a = M.arbre({ h: 3.5 + rnd() * 1.5 });
                    a.position.set((c.x + champs[i + 1].x) / 2, 0, c.z - 3 + k * 3);
                    G.add(a);
                }
            }
        });
        // le bassin de stockage et sa station de pompage, à l'est des parcelles
        const dernier = champs[champs.length - 1];
        const bx = dernier.x + 11.5, bz = dernier.z + 0.5;
        bloc(G, 12, 0.5, 9.5, 0x8c6b45, bx, 0, bz, { rayon: 0.25, r: 1 });
        const eauTexture = kit.sol("eau", 10, 7.5);
        const eau = new THREE.Mesh(new THREE.PlaneGeometry(10, 7.5), new THREE.MeshStandardMaterial({ map: eauTexture, color: 0x7fd0ea, roughness: 0.15, metalness: 0.1, transparent: true, opacity: 0.92 }));
        eau.rotation.x = -Math.PI / 2;
        eau.position.set(bx, 0.42, bz);
        G.add(eau);
        animer((dt, t) => { eauTexture.offset.x = t * 0.012; eauTexture.offset.y = Math.sin(t * 0.3) * 0.01; });
        for (let k = 0; k < 3; k++) {
            const r = M.arbre({ h: 4 + k * 0.8, couleur: 0x6fae55 });
            r.position.set(bx + 7 - k * 1.5, 0, bz + 4.5 + (k % 2) * 1.5);
            G.add(r);
        }
        const station = new THREE.Group();
        bloc(station, 2.6, 2.1, 2.2, 0xe8e3d8, 0, 0, 0, { rayon: 0.04 });
        const toit = bloc(station, 3.0, 0.12, 2.6, 0x5a6b7a, 0, 2.12, 0, { rayon: 0.02 });
        toit.rotation.x = 0.12;
        bloc(station, 0.9, 1.7, 0.06, 0x3a4a56, 0.5, 0, 1.12, { rayon: 0.02 });
        barre(station, [-1.3, 0.4, 0], [-4.2, 0.4, 0], 0.11, 0x2a63b0, { r: 0.5 });
        barre(station, [-4.2, 0.4, 0], [-4.2, 0.05, 2.8], 0.11, 0x2a63b0, { r: 0.5 });
        cyl(station, 0.16, 0.16, 0.5, T.gris, -2.5, 0.4, 0, "x", { m: 0.6, seg: 12 });
        bloc(station, 0.5, 0.9, 0.4, T.anthracite, 1.55, 0.3, -0.6, { rayon: 0.03 });
        texte("STATION DE POMPAGE", 2.2, 0.3, 0, 1.75, 1.16, { couleur: "#1d2f38", taille: 50, parent: station });
        station.position.set(bx + 1.5, 0, bz - 6.8);
        G.add(station);
        // les balles de paille à l'ouest, un vieux tracteur garé
        const premier = champs[0];
        for (const [dx, dz] of [[-9.5, -1], [-9.5, 2.2], [-11.2, 0.6], [-9.0, 5.5]]) {
            cyl(G, 0.78, 0.78, 1.25, 0xd9b45a, premier.x + dx, 0.78, premier.z + dz, "x", { r: 0.95, seg: 18 });
            cyl(G, 0.32, 0.32, 1.27, 0xc9a24a, premier.x + dx, 0.78, premier.z + dz, "x", { r: 0.95, seg: 12 });
        }
    }

    // ------------------------------------------------------------------ l'herbe : touffes, fleurs, buissons dans les coins
    const touffeGeo = new THREE.ConeGeometry(0.14, 0.36, 5);
    const touffeMats = [kit.mat(0x7fb85a), kit.mat(0x6fae55), kit.mat(0x9ccd77)];
    const zonesExt = (plan.zones || []).filter((z) => z.exterieur);
    const libre = (x, z) => !zoneEn(plan, x, z) && !(x > Math.min(...contour.map((p) => p[0])) - 0.3 && x < Math.max(...contour.map((p) => p[0])) + 0.3 && z > Math.min(...contour.map((p) => p[1])) - 0.3 && z < Math.max(...contour.map((p) => p[1])) + 0.3)
        && !(ext.route && Math.abs(z - ext.route[0][1]) < 5.2);
    let poses = 0;
    for (let essai = 0; essai < 1400 && poses < 260; essai++) {
        const x = x0 + 1 + rnd() * (x1 - x0 - 2), z = z0 + 1 + rnd() * (z1 - z0 - 2);
        if (!libre(x, z) || (zonesExt.length && z > (ext.route ? ext.route[0][1] + 5 : z1))) {
            continue;
        }
        const t = new THREE.Mesh(touffeGeo, touffeMats[Math.floor(rnd() * 3)]);
        t.position.set(x, 0.12, z);
        t.rotation.y = rnd() * 3;
        t.scale.setScalar(0.7 + rnd() * 0.8);
        G.add(t);
        if (rnd() < 0.25) {
            boule(G, 0.05, [0xf2c230, 0xffffff, 0xe85d8a, 0x8a7fd0][Math.floor(rnd() * 4)], x + 0.2, 0.22, z + 0.1, { seg: 6, ombre: false });
        }
        poses++;
    }
    for (const [x, z] of [[x0 + 11, 8.6], [x0 + 11, 26.5], [x1 - 13, 9.2], [x1 - 13, 21]]) {
        if (!libre(x, z)) {
            continue;
        }
        for (let k = 0; k < 3; k++) {
            boule(G, 0.5 + rnd() * 0.35, [T.feuillage, T.feuillageFonce][k % 2], x + (rnd() - 0.5) * 1.4, 0.45, z + (rnd() - 0.5) * 1.4, { seg: 9 });
        }
    }

    // ------------------------------------------------------------------ les oiseaux
    const vols = [];
    for (let v = 0; v < 2; v++) {
        const centre = new THREE.Vector3(x0 + 20 + v * 30, 20 + v * 5, z0 + 18 + v * 14);
        for (let k = 0; k < 5; k++) {
            const o = new THREE.Group();
            bloc(o, 0.5, 0.03, 0.08, 0x2c3a43, -0.25, 0, 0, { vif: true, ombre: false }).rotation.z = 0.3;
            bloc(o, 0.5, 0.03, 0.08, 0x2c3a43, 0.25, 0, 0, { vif: true, ombre: false }).rotation.z = -0.3;
            G.add(o);
            vols.push({ o, centre, rayon: 9 + k * 1.3, phase: k * 0.5, vitesse: 0.35 + v * 0.1 });
        }
    }
    animer((dt, t) => {
        for (const b of vols) {
            const a = t * b.vitesse + b.phase;
            b.o.position.set(b.centre.x + Math.cos(a) * b.rayon, b.centre.y + Math.sin(t * 2 + b.phase) * 0.6, b.centre.z + Math.sin(a) * b.rayon);
            b.o.rotation.y = -a;
            const batt = Math.sin(t * 9 + b.phase) * 0.5;
            b.o.children[0].rotation.z = 0.3 + batt;
            b.o.children[1].rotation.z = -0.3 - batt;
        }
    });

    return G;
}
