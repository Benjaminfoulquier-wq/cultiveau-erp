/** @odoo-module **/
// Les modèles 3D de la vue d'ensemble : ce qu'on voit dans un magasin d'irrigation, dessiné proprement (angles arrondis,
// roues, vitres, phares). Unités : le mètre. Chaque modèle est un THREE.Group posé au sol (y = 0), centré sur son
// emprise, sa longueur le long de l'axe x. Les pièces animées portent un nom : « bras » (pivot), « roue » (véhicules).

export const TEINTES = {
    blanc: 0xf7f6f2, creme: 0xf1ece2, gris: 0xc3c9cf, grisFonce: 0x6c7883, anthracite: 0x2c3a43, noir: 0x1f2428, pneu: 0x24282c,
    marine: 0x1d4550, bleu: 0x0b9bb8, bleuRoi: 0x2a63b0, vert: 0x4fa83a, herbe: 0x8fcb6b, feuillage: 0x5fae45, feuillageFonce: 0x3f8f3a,
    orange: 0xf28c28, jaune: 0xf2c230, rouge: 0xd94f45, bois: 0xc89a62, boisClair: 0xe0bd8a, carton: 0xd9a35a, peau: 0xf0c3a3,
    vitre: 0x9fd3e3, vitreFoncee: 0x2f5866, eau: 0x6ccbe6, terre: 0xa9774a, beton: 0xdcd6ca, papier: 0xffffff,
};

export function bibliotheque(THREE) {
    const T = TEINTES;
    const materiaux = new Map();
    const mat = (couleur, o = {}) => {
        const cle = [couleur, o.r ?? 0.75, o.m ?? 0.05, o.e ?? 0, o.o ?? 1].join("|");
        if (!materiaux.has(cle)) {
            materiaux.set(cle, new THREE.MeshStandardMaterial({
                color: couleur, roughness: o.r ?? 0.75, metalness: o.m ?? 0.05, emissive: o.e ? couleur : 0x000000, emissiveIntensity: o.e || 0,
                transparent: (o.o ?? 1) < 1, opacity: o.o ?? 1,
            }));
        }
        return materiaux.get(cle);
    };
    const geos = new Map();
    const geo = (cle, fabrique) => {
        if (!geos.has(cle)) {
            geos.set(cle, fabrique());
        }
        return geos.get(cle);
    };
    /** Un pavé aux angles arrondis (les sommets proches des arêtes sont poussés sur un arrondi de rayon r). */
    const geoRonde = (w, h, d, r) => geo(`r${w}|${h}|${d}|${r}`, () => {
        r = Math.min(r, w / 2 - 0.001, h / 2 - 0.001, d / 2 - 0.001);
        const seg = (l) => Math.max(2, Math.min(10, Math.round(l / Math.max(r, 0.05)) + 2));
        const g = new THREE.BoxGeometry(w, h, d, seg(w), seg(h), seg(d));
        const p = g.attributes.position, n = g.attributes.normal;
        const hx = w / 2 - r, hy = h / 2 - r, hz = d / 2 - r;
        const v = new THREE.Vector3(), c = new THREE.Vector3(), dir = new THREE.Vector3();
        for (let i = 0; i < p.count; i++) {
            v.fromBufferAttribute(p, i);
            c.set(Math.max(-hx, Math.min(hx, v.x)), Math.max(-hy, Math.min(hy, v.y)), Math.max(-hz, Math.min(hz, v.z)));
            dir.subVectors(v, c);
            if (dir.lengthSq() > 1e-10) {
                dir.normalize();
                v.copy(c).addScaledVector(dir, r);
                p.setXYZ(i, v.x, v.y, v.z);
                n.setXYZ(i, dir.x, dir.y, dir.z);
            }
        }
        return g;
    });
    const ombre = (m, porte = true) => {
        m.castShadow = porte;
        m.receiveShadow = true;
        return m;
    };
    /** Ajoute à g un pavé arrondi de w × h × d, posé avec son bas en (x, y, z) (centre en x et z). */
    const bloc = (g, w, h, d, couleur, x = 0, y = 0, z = 0, o = {}) => {
        const m = ombre(new THREE.Mesh(o.vif ? new THREE.BoxGeometry(w, h, d) : geoRonde(w, h, d, o.rayon ?? Math.min(0.06, w / 5, h / 5, d / 5)), mat(couleur, o)), o.ombre ?? true);
        m.position.set(x, y + h / 2, z);
        g.add(m);
        return m;
    };
    /** Un cylindre d'axe vertical (axe « y »), horizontal (« x » ou « z »), posé avec son centre en (x, y, z). */
    const cyl = (g, r1, r2, h, couleur, x = 0, y = 0, z = 0, axe = "y", o = {}) => {
        const m = ombre(new THREE.Mesh(geo(`c${r1}|${r2}|${h}|${o.seg || 20}`, () => new THREE.CylinderGeometry(r1, r2, h, o.seg || 20)), mat(couleur, o)), o.ombre ?? true);
        m.position.set(x, y, z);
        if (axe === "x") {
            m.rotation.z = Math.PI / 2;
        } else if (axe === "z") {
            m.rotation.x = Math.PI / 2;
        }
        g.add(m);
        return m;
    };
    const boule = (g, r, couleur, x, y, z, o = {}) => {
        const m = ombre(new THREE.Mesh(geo(`s${r}|${o.seg || 14}`, () => new THREE.SphereGeometry(r, o.seg || 14, Math.max(8, (o.seg || 14) - 4))), mat(couleur, o)), o.ombre ?? true);
        m.position.set(x, y, z);
        if (o.ecrase) {
            m.scale.y = o.ecrase;
        }
        g.add(m);
        return m;
    };
    const tore = (g, R, r, couleur, x, y, z, rot = [Math.PI / 2, 0, 0], o = {}) => {
        const m = ombre(new THREE.Mesh(geo(`t${R}|${r}`, () => new THREE.TorusGeometry(R, r, 10, 28)), mat(couleur, o)));
        m.position.set(x, y, z);
        m.rotation.set(...rot);
        g.add(m);
        return m;
    };
    /** Une barre entre deux points (un tube, une jambe de pylône…). */
    const barre = (g, a, b, r, couleur, o = {}) => {
        const va = new THREE.Vector3(...a), vb = new THREE.Vector3(...b);
        const l = va.distanceTo(vb);
        const m = ombre(new THREE.Mesh(geo(`b${r}|${l.toFixed(2)}`, () => new THREE.CylinderGeometry(r, r, l, 8)), mat(couleur, o)), o.ombre ?? true);
        m.position.copy(va).add(vb).multiplyScalar(0.5);
        m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), vb.clone().sub(va).normalize());
        g.add(m);
        return m;
    };
    const roue = (g, r, l, x, y, z, jante = T.gris) => {
        const s = new THREE.Group();
        s.name = "roue";
        cyl(s, r, r, l, T.pneu, 0, 0, 0, "z", { r: 0.9 });
        cyl(s, r * 0.55, r * 0.55, l + 0.02, jante, 0, 0, 0, "z", { r: 0.4, m: 0.4 });
        cyl(s, r * 0.16, r * 0.16, l + 0.05, T.anthracite, 0, 0, 0, "z", { r: 0.5 });
        s.position.set(x, y, z);
        s.userData.rayon = r;
        g.add(s);
        return s;
    };
    const groupe = () => new THREE.Group();

    const M = {};

    // ---------------------------------------------------------------- les gens
    M.personne = (o = {}) => {
        const g = groupe();
        const pantalon = o.pantalon ?? T.anthracite, chemise = o.chemise ?? T.bleu;
        bloc(g, 0.16, 0.8, 0.16, pantalon, 0, 0, -0.1, { rayon: 0.07 });
        bloc(g, 0.16, 0.8, 0.16, pantalon, 0, 0, 0.1, { rayon: 0.07 });
        bloc(g, 0.3, 0.62, 0.48, chemise, 0, 0.76, 0, { rayon: 0.13 });
        bloc(g, 0.13, 0.55, 0.13, chemise, 0, 0.82, -0.31, { rayon: 0.06 });
        bloc(g, 0.13, 0.55, 0.13, chemise, 0, 0.82, 0.31, { rayon: 0.06 });
        boule(g, 0.16, T.peau, 0, 1.55, 0);
        if (o.casque) {
            boule(g, 0.18, T.jaune, 0, 1.62, 0, { ecrase: 0.6 });
        } else {
            boule(g, 0.165, o.cheveux ?? 0x4a3527, -0.02, 1.6, 0, { ecrase: 0.55 });
        }
        return g;
    };

    // ---------------------------------------------------------------- les véhicules
    M.utilitaire = (o = {}) => {
        // la camionnette d'intervention : caisse blanche, bandeau à la couleur, cabine vitrée, quatre roues
        const g = groupe();
        const c = o.couleur ?? T.bleu;
        bloc(g, 3.2, 1.75, 1.9, T.blanc, -0.55, 0.42, 0, { rayon: 0.18 });
        bloc(g, 1.4, 1.25, 1.86, T.blanc, 1.55, 0.42, 0, { rayon: 0.3 });
        bloc(g, 0.06, 0.62, 1.6, T.vitreFoncee, 2.2, 1.0, 0, { rayon: 0.03, r: 0.2, m: 0.3 });
        bloc(g, 0.9, 0.5, 0.05, T.vitreFoncee, 1.5, 1.08, 0.94, { rayon: 0.02, r: 0.2 });
        bloc(g, 0.9, 0.5, 0.05, T.vitreFoncee, 1.5, 1.08, -0.94, { rayon: 0.02, r: 0.2 });
        bloc(g, 4.5, 0.32, 1.94, c, 0.1, 0.62, 0, { rayon: 0.05 });
        bloc(g, 0.18, 0.28, 1.9, T.anthracite, 2.27, 0.32, 0, { rayon: 0.06 });
        bloc(g, 0.18, 0.28, 1.9, T.anthracite, -2.2, 0.32, 0, { rayon: 0.06 });
        bloc(g, 0.05, 0.14, 0.3, 0xfff6c8, 2.25, 0.85, 0.65, { e: 0.8 });
        bloc(g, 0.05, 0.14, 0.3, 0xfff6c8, 2.25, 0.85, -0.65, { e: 0.8 });
        bloc(g, 0.05, 0.2, 0.18, T.rouge, -2.17, 1.2, 0.82, { e: 0.4 });
        bloc(g, 0.05, 0.2, 0.18, T.rouge, -2.17, 1.2, -0.82, { e: 0.4 });
        for (const x of [1.45, -1.4]) {
            roue(g, 0.36, 0.26, x, 0.36, 0.88);
            roue(g, 0.36, 0.26, x, 0.36, -0.88);
        }
        if (o.gyrophare) {
            bloc(g, 0.5, 0.14, 0.22, T.orange, 0.6, 2.17, 0, { e: 0.6 });
        }
        return g;
    };
    M.semi = (o = {}) => {
        // le semi-remorque d'un fournisseur : tracteur à cabine haute, remorque bâchée à la couleur, trois essieux
        const g = groupe();
        const c = o.couleur ?? T.bleuRoi;
        bloc(g, 2.3, 2.3, 2.45, c, 5.0, 0.8, 0, { rayon: 0.22 });
        bloc(g, 0.06, 0.95, 2.1, T.vitreFoncee, 6.15, 2.0, 0, { rayon: 0.04, r: 0.2 });
        bloc(g, 0.08, 0.6, 1.6, T.grisFonce, 6.17, 1.0, 0, { rayon: 0.04, m: 0.5, r: 0.4 });
        bloc(g, 1.1, 0.6, 2.4, T.blanc, 4.6, 3.1, 0, { rayon: 0.2 });
        cyl(g, 0.07, 0.07, 1.4, T.gris, 3.8, 2.6, 1.15, "y", { m: 0.7, r: 0.3 });
        cyl(g, 0.3, 0.3, 1.0, T.gris, 4.6, 0.75, 1.15, "x", { m: 0.6, r: 0.3 });
        bloc(g, 0.05, 0.14, 0.4, 0xfff6c8, 6.18, 0.75, 0.85, { e: 0.8 });
        bloc(g, 0.05, 0.14, 0.4, 0xfff6c8, 6.18, 0.75, -0.85, { e: 0.8 });
        bloc(g, 9.6, 0.25, 2.2, T.anthracite, -0.9, 0.95, 0, { vif: true });
        bloc(g, 9.4, 2.75, 2.5, T.blanc, -1.0, 1.2, 0, { rayon: 0.1 });
        bloc(g, 9.42, 0.5, 2.52, c, -1.0, 3.2, 0, { rayon: 0.08 });
        for (const x of [5.4, 3.6]) {
            roue(g, 0.5, 0.36, x, 0.5, 1.05);
            roue(g, 0.5, 0.36, x, 0.5, -1.05);
        }
        for (const x of [-3.4, -4.5, -5.6]) {
            roue(g, 0.48, 0.36, x, 0.48, 1.0);
            roue(g, 0.48, 0.36, x, 0.48, -1.0);
        }
        return g;
    };
    M.voiture = (o = {}) => {
        const g = groupe();
        const c = o.couleur ?? T.rouge;
        if (o.pickup) {
            bloc(g, 4.6, 0.75, 1.8, c, 0, 0.4, 0, { rayon: 0.2 });
            bloc(g, 1.9, 0.75, 1.7, c, 0.5, 1.1, 0, { rayon: 0.25 });
            bloc(g, 1.7, 0.55, 1.74, T.vitreFoncee, 0.5, 1.2, 0, { rayon: 0.2, r: 0.2 });
            bloc(g, 1.6, 0.4, 1.6, T.anthracite, -1.4, 1.1, 0, { rayon: 0.05 });
        } else {
            bloc(g, 4.0, 0.7, 1.75, c, 0, 0.35, 0, { rayon: 0.25 });
            bloc(g, 2.2, 0.62, 1.6, c, -0.2, 1.0, 0, { rayon: 0.28 });
            bloc(g, 2.0, 0.48, 1.64, T.vitreFoncee, -0.2, 1.06, 0, { rayon: 0.22, r: 0.2 });
        }
        bloc(g, 0.05, 0.12, 0.3, 0xfff6c8, o.pickup ? 2.3 : 2.0, 0.75, 0.6, { e: 0.7 });
        bloc(g, 0.05, 0.12, 0.3, 0xfff6c8, o.pickup ? 2.3 : 2.0, 0.75, -0.6, { e: 0.7 });
        const ex = o.pickup ? 1.5 : 1.3;
        for (const x of [ex, -ex]) {
            roue(g, 0.34, 0.24, x, 0.34, 0.82);
            roue(g, 0.34, 0.24, x, 0.34, -0.82);
        }
        return g;
    };
    M.tracteur = (o = {}) => {
        // un tracteur de ferme : long capot, masses à l'avant, cabine vitrée, grandes roues arrière à jantes jaunes, pot qui fume
        const g = groupe();
        const c = o.couleur ?? 0x2f9a3e;
        const jante = o.jante ?? 0xf2c230;
        bloc(g, 2.0, 0.82, 0.95, c, 1.0, 0.72, 0, { rayon: 0.2 });
        bloc(g, 0.05, 0.55, 0.75, T.anthracite, 2.0, 0.84, 0, { rayon: 0.02 });
        bloc(g, 0.32, 0.42, 1.0, T.anthracite, 2.18, 0.5, 0, { rayon: 0.06 });
        bloc(g, 0.05, 0.12, 0.22, 0xfff6c8, 2.02, 1.3, 0.3, { e: 0.8 });
        bloc(g, 0.05, 0.12, 0.22, 0xfff6c8, 2.02, 1.3, -0.3, { e: 0.8 });
        bloc(g, 1.45, 0.9, 1.3, c, -0.55, 0.75, 0, { rayon: 0.12 });
        bloc(g, 1.32, 1.2, 1.26, T.vitre, -0.55, 1.65, 0, { rayon: 0.08, o: 0.5, r: 0.1 });
        for (const [x, z] of [[0.08, 0.6], [0.08, -0.6], [-1.18, 0.6], [-1.18, -0.6]]) {
            bloc(g, 0.08, 1.2, 0.08, c, x, 1.65, z, { rayon: 0.02 });
        }
        bloc(g, 1.62, 0.14, 1.5, c, -0.55, 2.85, 0, { rayon: 0.06 });
        bloc(g, 0.06, 0.14, 0.4, T.orange, -0.55, 2.99, 0, { e: 0.5 });
        for (const z of [1.0, -1.0]) {
            bloc(g, 1.5, 0.1, 0.62, c, -0.6, 1.62, z, { rayon: 0.04 });
            roue(g, 0.82, 0.58, -0.6, 0.82, z, jante);
        }
        for (const z of [0.72, -0.72]) {
            roue(g, 0.48, 0.36, 1.45, 0.48, z, jante);
        }
        cyl(g, 0.06, 0.06, 1.15, T.anthracite, 0.55, 2.0, 0.32, "y", { m: 0.5, r: 0.4 });
        const fumee = groupe();
        fumee.name = "fumee";
        fumee.position.set(0.55, 2.6, 0.32);
        for (let i = 0; i < 3; i++) {
            boule(fumee, 0.16, 0xb9c0c6, 0, 0, 0, { o: 0.6, ombre: false });
        }
        g.add(fumee);
        return g;
    };
    M.fourgonnette = (o = {}) => {
        // la fourgonnette d'un artisan (Partner, Berlingo) : capot court, caisse haute, galerie, échelle ou bande à la couleur
        const g = groupe();
        const c = o.couleur ?? T.blanc;
        bloc(g, 4.3, 0.72, 1.8, c, 0, 0.32, 0, { rayon: 0.2 });
        bloc(g, 2.75, 0.88, 1.76, c, -0.72, 0.98, 0, { rayon: 0.24 });
        const pare = bloc(g, 0.9, 0.62, 1.7, c, 0.95, 0.98, 0, { rayon: 0.24 });
        pare.rotation.z = -0.22;
        bloc(g, 0.06, 0.5, 1.5, T.vitreFoncee, 1.42, 1.05, 0, { rayon: 0.03, r: 0.2, m: 0.3 }).rotation.z = -0.55;
        for (const z of [0.89, -0.89]) {
            bloc(g, 0.78, 0.42, 0.05, T.vitreFoncee, 0.82, 1.18, z, { rayon: 0.02, r: 0.2 });
            if (o.bande) {
                bloc(g, 2.6, 0.24, 0.04, o.bande, -0.72, 1.22, z * 1.005, { rayon: 0.02, e: o.bande === T.blanc ? 0.15 : 0 });
            }
        }
        bloc(g, 0.18, 0.26, 1.82, T.anthracite, 2.12, 0.3, 0, { rayon: 0.06 });
        bloc(g, 0.18, 0.26, 1.82, T.anthracite, -2.12, 0.3, 0, { rayon: 0.06 });
        bloc(g, 0.05, 0.12, 0.3, 0xfff6c8, 2.13, 0.78, 0.6, { e: 0.8 });
        bloc(g, 0.05, 0.12, 0.3, 0xfff6c8, 2.13, 0.78, -0.6, { e: 0.8 });
        bloc(g, 0.05, 0.22, 0.14, T.rouge, -2.14, 1.1, 0.78, { e: 0.4 });
        bloc(g, 0.05, 0.22, 0.14, T.rouge, -2.14, 1.1, -0.78, { e: 0.4 });
        for (const x of [1.35, -1.35]) {
            roue(g, 0.34, 0.24, x, 0.34, 0.86);
            roue(g, 0.34, 0.24, x, 0.34, -0.86);
        }
        if (o.galerie || o.echelle || o.tuyaux) {
            for (const z of [0.68, -0.68]) {
                bloc(g, 2.8, 0.06, 0.06, T.anthracite, -0.6, 1.92, z, { vif: true });
            }
            for (const x of [-1.8, -0.6, 0.6]) {
                bloc(g, 0.06, 0.06, 1.42, T.anthracite, x, 1.92, 0, { vif: true });
            }
        }
        if (o.tuyaux) {
            // les tuyaux du plombier : PVC bleu et cuivre, plus longs que la galerie
            [[0x2f7fc1, 0.38], [0xc57a3a, 0.16], [0x2f7fc1, -0.06], [0xc57a3a, -0.28], [0x2f7fc1, -0.48]].forEach(([couleur, z], i) => {
                cyl(g, 0.075, 0.075, 3.9 - (i % 2) * 0.5, couleur, -0.45, 2.06, z, "x", { r: 0.35, m: couleur === 0xc57a3a ? 0.6 : 0.05 });
            });
        }
        if (o.echelle) {
            // l'échelle de piscine en inox, couchée sur la galerie, rampes cintrées vers l'avant
            for (const z of [0.32, -0.32]) {
                barre(g, [-1.6, 2.02, z], [0.2, 2.02, z], 0.045, 0xdfe5ea, { m: 0.8, r: 0.25 });
                barre(g, [0.2, 2.02, z], [0.45, 2.42, z], 0.045, 0xdfe5ea, { m: 0.8, r: 0.25 });
                barre(g, [0.45, 2.42, z], [0.75, 2.3, z], 0.045, 0xdfe5ea, { m: 0.8, r: 0.25 });
            }
            for (const x of [-1.3, -0.8, -0.3]) {
                barre(g, [x, 2.02, 0.32], [x, 2.02, -0.32], 0.05, 0xdfe5ea, { m: 0.8, r: 0.25 });
            }
        }
        return g;
    };
    M.plateau = (o = {}) => {
        // le camion plateau : cabine à l'avant, plateau à l'arrière ; chargé d'herbe et de branches (paysagiste)
        // ou d'une benne (services techniques), avec gyrophare et bande tricolore pour la collectivité
        const g = groupe();
        const c = o.couleur ?? T.orange;
        bloc(g, 4.9, 0.24, 1.5, T.anthracite, -0.1, 0.42, 0, { vif: true });
        bloc(g, 1.45, 1.42, 1.95, c, 1.55, 0.55, 0, { rayon: 0.22 });
        bloc(g, 0.06, 0.62, 1.7, T.vitreFoncee, 2.29, 1.25, 0, { rayon: 0.03, r: 0.2, m: 0.3 });
        for (const z of [0.98, -0.98]) {
            bloc(g, 0.88, 0.5, 0.05, T.vitreFoncee, 1.62, 1.35, z, { rayon: 0.02, r: 0.2 });
            if (o.tricolore) {
                [[0x1f4ea1, 0.66], [0xf7f6f2, 0.82], [0xd94f45, 0.98]].forEach(([couleur, y]) => bloc(g, 1.2, 0.16, 0.04, couleur, 1.55, y, z * 1.005, { vif: true }));
            }
        }
        bloc(g, 0.2, 0.28, 2.0, T.anthracite, 2.32, 0.42, 0, { rayon: 0.06 });
        bloc(g, 0.05, 0.14, 0.3, 0xfff6c8, 2.31, 0.85, 0.65, { e: 0.8 });
        bloc(g, 0.05, 0.14, 0.3, 0xfff6c8, 2.31, 0.85, -0.65, { e: 0.8 });
        bloc(g, 3.35, 0.16, 2.0, T.grisFonce, -0.95, 0.66, 0, { rayon: 0.03 });
        for (const z of [0.96, -0.96]) {
            bloc(g, 3.35, 0.2, 0.06, T.gris, -0.95, 0.82, z, { vif: true });
        }
        if (o.charge === "vert") {
            bloc(g, 3.1, 0.34, 1.8, T.herbe, -0.95, 0.82, 0, { rayon: 0.16 });
            for (const [x, z, h, penche] of [[-2.0, 0.3, 1.3, 0.35], [-1.3, -0.4, 1.5, -0.3], [-0.6, 0.45, 1.2, 0.25], [0.1, -0.2, 1.1, -0.2]]) {
                const haut = [x + penche * 0.6, 1.16 + h, z + penche * 0.5];
                barre(g, [x, 1.1, z], haut, 0.05, T.terre);
                barre(g, [x + penche * 0.3, 1.1 + h * 0.55, z], [x + penche * 0.3 + 0.35, 1.3 + h * 0.6, z - 0.3], 0.035, T.terre);
                boule(g, 0.32, T.feuillage, haut[0], haut[1], haut[2]);
                boule(g, 0.24, T.feuillageFonce, haut[0] + 0.25, haut[1] - 0.15, haut[2] - 0.2);
                boule(g, 0.2, T.feuillage, x + penche * 0.3 + 0.38, 1.3 + h * 0.6, z - 0.32);
            }
        } else if (o.charge === "benne") {
            bloc(g, 3.15, 0.85, 1.95, o.benne ?? 0x7d8fa3, -0.95, 0.82, 0, { rayon: 0.06 });
            bloc(g, 2.95, 0.05, 1.75, 0x5c6b7b, -0.95, 1.63, 0, { vif: true });
            for (const x of [-2.1, -1.35, -0.6, 0.15]) {
                for (const z of [0.99, -0.99]) {
                    bloc(g, 0.08, 0.7, 0.03, 0x96a6b8, x, 0.9, z, { vif: true });
                }
            }
        }
        if (o.gyrophare) {
            const gyro = groupe();
            gyro.name = "gyrophare";
            gyro.position.set(1.55, 1.98, 0);
            cyl(gyro, 0.17, 0.2, 0.22, T.orange, 0, 0.11, 0, "y", { e: 0.6, o: 0.9 });
            bloc(gyro, 0.05, 0.16, 0.3, 0xffffff, 0.12, 0.03, 0, { e: 0.9 });
            g.add(gyro);
        }
        for (const z of [0.88, -0.88]) {
            roue(g, 0.4, 0.28, 1.55, 0.4, z);
            roue(g, 0.4, 0.36, -1.55, 0.4, z);
        }
        return g;
    };
    M.chariot = () => {
        // le chariot élévateur, jaune, mât et fourches
        const g = groupe();
        bloc(g, 1.7, 0.75, 1.1, T.jaune, -0.1, 0.3, 0, { rayon: 0.12 });
        bloc(g, 0.6, 0.65, 1.12, T.anthracite, -0.75, 0.4, 0, { rayon: 0.15 });
        bloc(g, 0.5, 0.45, 0.6, T.anthracite, -0.2, 1.05, 0, { rayon: 0.1 });
        for (const z of [0.5, -0.5]) {
            barre(g, [-0.75, 1.0, z], [-0.7, 2.1, z], 0.04, T.anthracite);
            barre(g, [0.45, 1.0, z], [0.4, 2.1, z], 0.04, T.anthracite);
        }
        bloc(g, 1.3, 0.06, 1.1, T.anthracite, -0.15, 2.1, 0, { rayon: 0.02 });
        bloc(g, 0.12, 2.6, 0.9, T.grisFonce, 0.85, 0.05, 0, { rayon: 0.03, m: 0.5 });
        bloc(g, 1.0, 0.06, 0.12, T.grisFonce, 1.4, 0.12, 0.3, { vif: true, m: 0.5 });
        bloc(g, 1.0, 0.06, 0.12, T.grisFonce, 1.4, 0.12, -0.3, { vif: true, m: 0.5 });
        roue(g, 0.28, 0.22, 0.45, 0.28, 0.5);
        roue(g, 0.28, 0.22, 0.45, 0.28, -0.5);
        roue(g, 0.24, 0.2, -0.65, 0.24, 0.5);
        roue(g, 0.24, 0.2, -0.65, 0.24, -0.5);
        const pilote = M.personne({ chemise: T.orange });
        pilote.scale.setScalar(0.85);
        pilote.position.set(-0.2, 0.25, 0);
        g.add(pilote);
        return g;
    };
    M.minipelle = (o = {}) => {
        // la mini-pelle du chantier : chenilles, tourelle, bras et godet
        const g = groupe();
        const c = o.couleur ?? T.orange;
        for (const z of [0.55, -0.55]) {
            bloc(g, 2.0, 0.45, 0.4, T.anthracite, 0, 0, z, { rayon: 0.2, r: 0.9 });
        }
        bloc(g, 1.6, 0.55, 1.3, c, -0.1, 0.5, 0, { rayon: 0.18 });
        bloc(g, 0.9, 0.95, 0.9, T.vitre, -0.25, 1.05, 0.15, { rayon: 0.1, o: 0.6 });
        bloc(g, 1.0, 0.1, 1.0, c, -0.25, 2.0, 0.15, { rayon: 0.05 });
        barre(g, [0.5, 1.0, -0.3], [1.6, 2.0, -0.3], 0.1, c);
        barre(g, [1.6, 2.0, -0.3], [2.2, 0.6, -0.3], 0.08, c);
        bloc(g, 0.4, 0.35, 0.5, T.anthracite, 2.25, 0.25, -0.3, { rayon: 0.06 });
        return g;
    };

    // ---------------------------------------------------------------- l'irrigation
    M.enrouleur = (o = {}) => {
        // l'enrouleur : châssis sur deux roues, grand tambour couvert de tuyau PE noir, flasques à la couleur, timon
        const g = groupe();
        const c = o.couleur ?? T.rouge;
        bloc(g, 2.6, 0.18, 1.5, c, 0, 0.55, 0, { rayon: 0.04 });
        roue(g, 0.55, 0.32, -0.4, 0.55, 1.0);
        roue(g, 0.55, 0.32, -0.4, 0.55, -1.0);
        barre(g, [1.3, 0.65, 0], [2.6, 0.35, 0], 0.06, c);
        cyl(g, 0.6, 0.65, 0.18, c, 0, 0.82, 0, "y");
        const tambour = groupe();
        tambour.name = "tambour";
        cyl(tambour, 1.0, 1.0, 1.0, T.noir, 0, 0, 0, "z", { r: 0.6, seg: 28 });
        for (let k = -2; k <= 2; k++) {
            tore(tambour, 1.0, 0.07, 0x111417, 0, 0, k * 0.2, [0, 0, 0], { r: 0.5 });
        }
        cyl(tambour, 1.25, 1.25, 0.08, c, 0, 0, 0.55, "z", { seg: 28 });
        cyl(tambour, 1.25, 1.25, 0.08, c, 0, 0, -0.55, "z", { seg: 28 });
        cyl(tambour, 0.15, 0.15, 1.3, T.grisFonce, 0, 0, 0, "z", { m: 0.5 });
        tambour.position.set(0, 2.15, 0);
        g.add(tambour);
        for (const z of [0.68, -0.68]) {
            barre(g, [-0.7, 0.9, z], [0, 2.15, z], 0.06, c);
            barre(g, [0.7, 0.9, z], [0, 2.15, z], 0.06, c);
        }
        bloc(g, 0.5, 0.45, 0.5, T.grisFonce, 0.95, 0.9, 0.45, { rayon: 0.08, m: 0.4 });
        if (o.tuyau) {
            // le tuyau déroulé jusqu'au chariot-canon
            barre(g, [0.6, 1.4, 0], [o.tuyau, 0.12, 0], 0.07, T.noir, { r: 0.6 });
        }
        return g;
    };
    M.canon = () => {
        // le chariot porte-canon au bout du tuyau
        const g = groupe();
        bloc(g, 1.2, 0.12, 0.9, T.grisFonce, 0, 0.35, 0, { rayon: 0.03, m: 0.4 });
        roue(g, 0.32, 0.18, 0, 0.32, 0.55);
        roue(g, 0.32, 0.18, 0, 0.32, -0.55);
        cyl(g, 0.06, 0.06, 0.8, T.grisFonce, 0, 0.85, 0, "y", { m: 0.5 });
        const canon = barre(g, [0, 1.2, 0], [-0.7, 1.75, 0], 0.08, T.gris, { m: 0.6, r: 0.3 });
        canon.name = "canon";
        return g;
    };
    M.pivot = (o = {}) => {
        // le pivot : tour centrale, une longue rampe galvanisée en treillis, deux tours à roues, cannes de descente,
        // et le cercle arrosé dans la culture
        const g = groupe();
        const c = o.couleur ?? 0xb9c2c9;
        const L = o.longueur ?? 7;
        const cercle = ombre(new THREE.Mesh(geo(`disque${L}`, () => new THREE.CircleGeometry(L + 0.3, 48)), mat(0x9fd27a, { r: 1 })), false);
        cercle.rotation.x = -Math.PI / 2;
        cercle.position.y = 0.13;
        g.add(cercle);
        for (const [x, z] of [[-0.7, -0.7], [0.7, -0.7], [0.7, 0.7], [-0.7, 0.7]]) {
            barre(g, [x, 0.1, z], [0, 2.5, 0], 0.06, c, { m: 0.5, r: 0.4 });
        }
        cyl(g, 0.22, 0.22, 0.5, T.grisFonce, 0, 2.55, 0, "y", { m: 0.4 });
        bloc(g, 0.4, 0.5, 0.3, T.grisFonce, 0.5, 0.2, 0.5, { rayon: 0.05 });
        const bras = groupe();
        bras.name = "bras";
        const tours = [L * 0.5, L];
        let x0 = 0;
        const hTube = 2.35;
        for (const xt of tours) {
            barre(bras, [x0, hTube + 0.15, 0], [xt, hTube, 0], 0.09, c, { m: 0.5, r: 0.35 });
            // le treillis sous la rampe : deux tirants et des montants
            const mi = (x0 + xt) / 2;
            barre(bras, [x0 + 0.2, hTube, 0], [mi, hTube - 0.55, 0], 0.025, c, { m: 0.5 });
            barre(bras, [xt - 0.2, hTube, 0], [mi, hTube - 0.55, 0], 0.025, c, { m: 0.5 });
            for (let k = 1; k < 5; k++) {
                const xd = x0 + ((xt - x0) * k) / 5;
                const creux = hTube - 0.55 * (1 - Math.abs(xd - mi) / ((xt - x0) / 2));
                barre(bras, [xd, hTube, 0], [xd, creux, 0], 0.02, c, { m: 0.5 });
                barre(bras, [xd, creux, 0], [xd, 0.9, 0], 0.012, T.anthracite);
                cyl(bras, 0.07, 0.03, 0.08, T.bleu, xd, 0.86, 0);
            }
            // la tour : un A sur un chariot à deux roues
            barre(bras, [xt, hTube, 0], [xt, 0.55, 0.75], 0.05, c, { m: 0.5 });
            barre(bras, [xt, hTube, 0], [xt, 0.55, -0.75], 0.05, c, { m: 0.5 });
            bloc(bras, 0.18, 0.18, 1.7, c, xt, 0.42, 0, { m: 0.5 });
            bloc(bras, 0.25, 0.25, 0.3, T.grisFonce, xt, 0.55, 0, { rayon: 0.04 });
            roue(bras, 0.42, 0.26, xt, 0.42, 0.95);
            roue(bras, 0.42, 0.26, xt, 0.42, -0.95);
            x0 = xt;
        }
        // le porte-à-faux et son canon d'extrémité
        barre(bras, [L, hTube, 0], [L + 0.9, hTube - 0.15, 0], 0.05, c, { m: 0.5 });
        cyl(bras, 0.06, 0.06, 0.25, T.bleu, L + 0.95, hTube - 0.25, 0);
        g.add(bras);
        return g;
    };
    M.asperseur = () => {
        const g = groupe();
        cyl(g, 0.025, 0.025, 1.0, T.grisFonce, 0, 0.5, 0, "y", { m: 0.5 });
        cyl(g, 0.07, 0.07, 0.12, T.bleu, 0, 1.05, 0);
        barre(g, [0, 1.1, 0], [0.18, 1.2, 0], 0.025, T.grisFonce);
        return g;
    };
    M.culture = (o = {}) => {
        // une parcelle et sa culture : rangs de maïs, de vigne ou d'arbres ; la terre nue d'un projet
        const g = groupe();
        const L = o.l ?? 8, P = o.p ?? 6.4;
        bloc(g, L, 0.12, P, o.nu ? T.terre : 0x7fb85a, 0, 0, 0, { rayon: 0.05, r: 0.95 });
        if (o.nu) {
            for (let k = 0; k < 6; k++) {
                bloc(g, L - 0.6, 0.05, 0.12, 0x946640, 0, 0.12, -P / 2 + 0.7 + k * ((P - 1.4) / 5), { vif: true });
            }
            return g;
        }
        const rangs = o.genre === "verger" ? 3 : 5;
        for (let r = 0; r < rangs; r++) {
            const z = -P / 2 + 0.8 + (r * (P - 1.6)) / (rangs - 1);
            if (o.goutte) {
                barre(g, [-L / 2 + 0.3, 0.16, z + 0.15], [L / 2 - 0.3, 0.16, z + 0.15], 0.02, T.noir);
            }
            const pas = o.genre === "verger" ? 1.6 : o.genre === "vigne" ? 0.8 : 0.55;
            for (let x = -L / 2 + 0.5; x < L / 2 - 0.3; x += pas) {
                if (o.genre === "verger") {
                    cyl(g, 0.07, 0.09, 0.8, 0x7a5434, x, 0.52, z);
                    boule(g, 0.6, T.feuillage, x, 1.25, z, { ecrase: 0.85 });
                } else if (o.genre === "vigne") {
                    cyl(g, 0.04, 0.05, 0.5, 0x7a5434, x, 0.37, z);
                    bloc(g, 0.6, 0.45, 0.35, T.feuillageFonce, x, 0.5, z, { rayon: 0.15 });
                } else {
                    bloc(g, 0.18, 0.9, 0.18, T.feuillage, x, 0.12, z, { rayon: 0.08 });
                    bloc(g, 0.08, 0.25, 0.08, 0xe8c25a, x + 0.05, 0.95, z, { rayon: 0.03 });
                }
            }
        }
        return g;
    };

    // ---------------------------------------------------------------- l'atelier et le stock
    M.pompe = (o = {}) => {
        // une pompe : moteur à ailettes, volute, socle, brides
        const g = groupe();
        const c = o.couleur ?? T.bleuRoi;
        bloc(g, 1.4, 0.12, 0.6, T.grisFonce, 0, 0, 0, { rayon: 0.03, m: 0.4 });
        cyl(g, 0.24, 0.24, 0.7, c, -0.3, 0.42, 0, "x", { r: 0.5, m: 0.2 });
        for (let k = 0; k < 5; k++) {
            cyl(g, 0.26, 0.26, 0.03, c, -0.55 + k * 0.12, 0.42, 0, "x", { r: 0.5 });
        }
        cyl(g, 0.2, 0.22, 0.12, T.grisFonce, -0.68, 0.42, 0, "x");
        cyl(g, 0.28, 0.28, 0.24, c, 0.3, 0.42, 0, "z", { r: 0.5 });
        cyl(g, 0.09, 0.09, 0.5, T.gris, 0.55, 0.42, 0, "x", { m: 0.6 });
        cyl(g, 0.09, 0.09, 0.45, T.gris, 0.3, 0.7, 0, "y", { m: 0.6 });
        cyl(g, 0.14, 0.14, 0.04, T.gris, 0.8, 0.42, 0, "x", { m: 0.6 });
        return g;
    };
    M.rack = (o = {}) => {
        // un rack à palettes : échelles bleues, lisses orange, palettes filmées dont la couleur dit la famille
        const g = groupe();
        const L = 3.6, P = 1.1, H = 3.4;
        for (const x of [-L / 2, 0, L / 2]) {
            for (const z of [-P / 2, P / 2]) {
                bloc(g, 0.08, H, 0.08, T.bleuRoi, x, 0, z, { vif: true, m: 0.3 });
            }
        }
        let n = 0;
        for (let niveau = 0; niveau < 3; niveau++) {
            const y = 0.12 + niveau * 1.12;
            if (niveau) {
                bloc(g, L, 0.12, 0.06, T.orange, 0, y - 0.12, -P / 2, { vif: true });
                bloc(g, L, 0.12, 0.06, T.orange, 0, y - 0.12, P / 2, { vif: true });
            }
            for (const x of [-L / 4, L / 4]) {
                if (n++ < (o.remplissage ?? 6)) {
                    bloc(g, 1.2, 0.14, 1.0, T.boisClair, x, y, 0, { rayon: 0.02 });
                    bloc(g, 1.1, 0.7, 0.9, niveau % 2 ? T.carton : 0xe2b06a, x, y + 0.14, 0, { rayon: 0.05 });
                    bloc(g, 1.12, 0.16, 0.92, o.couleur ?? T.bleu, x, y + 0.5, 0, { rayon: 0.04 });
                }
            }
        }
        return g;
    };
    M.gondole = (o = {}) => {
        // une gondole du libre-service : étagères blanches et petites boîtes colorées
        const g = groupe();
        bloc(g, 4.0, 1.6, 0.2, T.blanc, 0, 0, 0, { rayon: 0.04 });
        bloc(g, 4.0, 0.12, 1.0, T.blanc, 0, 0, 0, { rayon: 0.04 });
        bloc(g, 4.06, 0.22, 0.24, o.couleur ?? T.bleu, 0, 1.6, 0, { rayon: 0.05 });
        const teintes = [o.couleur ?? T.bleu, T.blanc, T.orange, T.vert, T.jaune];
        for (const y of [0.15, 0.6, 1.05]) {
            bloc(g, 4.0, 0.04, 0.95, T.gris, 0, y, 0, { vif: true });
            for (let k = 0; k < 9; k++) {
                for (const s of [-1, 1]) {
                    bloc(g, 0.3, 0.26 + ((k * 7) % 3) * 0.04, 0.3, teintes[(k + (s > 0 ? 2 : 0) + Math.round(y * 3)) % teintes.length], -1.8 + k * 0.45, y + 0.04, s * 0.27, { rayon: 0.03, ombre: false });
                }
            }
        }
        return g;
    };
    M.comptoir = () => {
        const g = groupe();
        bloc(g, 1.0, 1.0, 6.0, T.marine, 0, 0, 0, { rayon: 0.06 });
        bloc(g, 1.15, 0.08, 6.1, T.boisClair, 0, 1.0, 0, { rayon: 0.03 });
        bloc(g, 0.04, 0.3, 4.5, T.bleu, -0.52, 0.55, 0, { e: 0.2 });
        bloc(g, 0.45, 0.3, 0.4, T.anthracite, 0.1, 1.08, -1.5, { rayon: 0.05 });
        bloc(g, 0.05, 0.35, 0.5, T.anthracite, 0.25, 1.38, -1.5, { rayon: 0.02 });
        bloc(g, 0.02, 0.28, 0.42, T.bleu, 0.22, 1.42, -1.5, { e: 0.5 });
        bloc(g, 0.08, 0.35, 0.5, T.anthracite, 0.2, 1.08, 1.4, { rayon: 0.02 });
        bloc(g, 0.02, 0.3, 0.44, 0x9ee6f5, 0.15, 1.1, 1.4, { e: 0.5 });
        return g;
    };
    M.bureau = (o = {}) => {
        const g = groupe();
        const L = o.l ?? 1.8;
        bloc(g, L, 0.05, 0.85, T.boisClair, 0, 0.72, 0, { rayon: 0.02 });
        for (const x of [-L / 2 + 0.06, L / 2 - 0.06]) {
            bloc(g, 0.05, 0.72, 0.8, T.gris, x, 0, 0, { vif: true });
        }
        bloc(g, 0.6, 0.38, 0.04, T.anthracite, 0, 0.9, -0.25, { rayon: 0.02 });
        bloc(g, 0.55, 0.32, 0.02, T.bleu, 0, 0.93, -0.22, { e: 0.35 });
        bloc(g, 0.08, 0.15, 0.08, T.anthracite, 0, 0.77, -0.27, { vif: true });
        bloc(g, 0.45, 0.02, 0.15, T.gris, 0, 0.77, 0.05, { vif: true });
        const chaise = M.chaise();
        chaise.position.set(0, 0, 0.75);
        g.add(chaise);
        return g;
    };
    M.chaise = () => {
        const g = groupe();
        cyl(g, 0.25, 0.25, 0.05, T.anthracite, 0, 0.05, 0);
        cyl(g, 0.03, 0.03, 0.4, T.grisFonce, 0, 0.27, 0);
        bloc(g, 0.48, 0.08, 0.46, T.anthracite, 0, 0.47, 0, { rayon: 0.04 });
        bloc(g, 0.48, 0.5, 0.06, T.anthracite, 0, 0.55, 0.22, { rayon: 0.04 });
        return g;
    };
    M.table = (o = {}) => {
        const g = groupe();
        const L = o.l ?? 4, P = o.p ?? 1.6;
        bloc(g, L, 0.06, P, T.boisClair, 0, 0.72, 0, { rayon: 0.05 });
        bloc(g, 0.12, 0.72, P * 0.6, T.gris, -L / 2 + 0.4, 0, 0, { rayon: 0.03 });
        bloc(g, 0.12, 0.72, P * 0.6, T.gris, L / 2 - 0.4, 0, 0, { rayon: 0.03 });
        const n = Math.max(2, Math.round(L / 1.2));
        for (let k = 0; k < n; k++) {
            const x = -L / 2 + 0.6 + (k * (L - 1.2)) / (n - 1);
            for (const s of [-1, 1]) {
                const c = M.chaise();
                c.position.set(x, 0, s * (P / 2 + 0.25));
                c.rotation.y = s > 0 ? 0 : Math.PI;
                g.add(c);
            }
        }
        return g;
    };
    M.plans = () => {
        // la table à dessin du bureau d'étude, couverte de plans
        const g = groupe();
        bloc(g, 2.6, 0.06, 1.4, T.blanc, 0, 0.9, 0, { rayon: 0.03 });
        for (const x of [-1.2, 1.2]) {
            bloc(g, 0.06, 0.9, 1.2, T.gris, x, 0, 0, { vif: true });
        }
        for (const [x, z, r] of [[-0.6, -0.2, 0.1], [0.4, 0.15, -0.15], [0.8, -0.3, 0.3]]) {
            const f = bloc(g, 0.9, 0.01, 0.62, 0xdbeaf7, x, 0.96, z, { vif: true, ombre: false });
            f.rotation.y = r;
        }
        return g;
    };
    M.borne = () => {
        // le coin conseil : grand écran sur pied, la 3D du réseau à l'écran
        const g = groupe();
        bloc(g, 0.6, 0.05, 0.6, T.anthracite, 0, 0, 0, { rayon: 0.02 });
        bloc(g, 0.12, 1.1, 0.12, T.anthracite, 0, 0.05, 0, { vif: true });
        bloc(g, 0.08, 1.0, 1.6, T.anthracite, 0, 1.0, 0, { rayon: 0.03 });
        bloc(g, 0.02, 0.86, 1.46, 0x9ee6f5, 0.05, 1.07, 0, { e: 0.6 });
        bloc(g, 0.02, 0.3, 0.3, T.bleu, 0.07, 1.3, 0.2, { e: 0.8 });
        bloc(g, 0.02, 0.2, 0.5, T.vert, 0.07, 1.2, -0.3, { e: 0.6 });
        return g;
    };
    M.armoire = () => {
        const g = groupe();
        bloc(g, 0.6, 2.0, 2.0, T.gris, 0, 0, 0, { rayon: 0.04 });
        bloc(g, 0.02, 1.8, 0.92, 0xd5dade, 0.31, 0.1, -0.48, { vif: true });
        bloc(g, 0.02, 1.8, 0.92, 0xd5dade, 0.31, 0.1, 0.48, { vif: true });
        bloc(g, 0.03, 0.3, 0.3, T.jaune, 0.33, 1.4, -0.48, { vif: true });
        return g;
    };
    M.etabli = () => {
        const g = groupe();
        bloc(g, 3.0, 0.08, 0.9, T.bois, 0, 0.85, 0, { rayon: 0.02 });
        for (const x of [-1.4, 1.4]) {
            bloc(g, 0.08, 0.85, 0.85, T.grisFonce, x, 0, 0, { vif: true });
        }
        bloc(g, 3.0, 1.0, 0.05, T.gris, 0, 0.93, -0.43, { vif: true });
        bloc(g, 0.3, 0.2, 0.25, T.bleuRoi, -1.0, 0.93, 0.1, { rayon: 0.03 });
        cyl(g, 0.06, 0.06, 0.6, T.gris, 0.5, 0.98, 0.05, "x", { m: 0.6 });
        return g;
    };
    M.bac = () => {
        // le banc d'essai : la bâche d'eau en circuit fermé, une pompe en essai, un manomètre
        const g = groupe();
        bloc(g, 4.0, 0.8, 1.8, T.grisFonce, 0, 0, 0, { rayon: 0.05, m: 0.3 });
        bloc(g, 3.8, 0.04, 1.6, T.eau, 0, 0.72, 0, { vif: true, o: 0.85, r: 0.1, ombre: false });
        cyl(g, 0.15, 0.15, 0.05, T.blanc, 1.6, 1.2, -0.85, "z");
        cyl(g, 0.03, 0.03, 0.4, T.gris, 1.6, 1.0, -0.85, "y");
        return g;
    };
    M.soudeuse = () => {
        const g = groupe();
        bloc(g, 2.4, 0.15, 0.8, T.grisFonce, 0, 0.75, 0, { rayon: 0.03 });
        for (const x of [-1.1, 1.1]) {
            bloc(g, 0.08, 0.75, 0.7, T.grisFonce, x, 0, 0, { vif: true });
        }
        cyl(g, 0.16, 0.16, 2.2, T.noir, 0, 1.05, 0, "x", { r: 0.5 });
        bloc(g, 0.15, 0.5, 0.6, T.jaune, 0, 0.9, 0, { rayon: 0.03 });
        bloc(g, 0.5, 0.45, 0.4, T.rouge, 1.6, 0, 0.2, { rayon: 0.05 });
        return g;
    };
    M.prefa = () => {
        // une station de tête en préfabrication : collecteur, vannes à volant rouge, filtre, compteur
        const g = groupe();
        bloc(g, 4.2, 0.15, 2.0, T.grisFonce, 0, 0, 0, { rayon: 0.03, m: 0.3 });
        cyl(g, 0.16, 0.16, 3.8, T.bleuRoi, 0, 0.6, -0.4, "x", { m: 0.3, r: 0.4 });
        for (const x of [-1.2, 0, 1.2]) {
            cyl(g, 0.1, 0.1, 0.8, T.bleuRoi, x, 0.6, 0.0, "z", { m: 0.3, r: 0.4 });
            cyl(g, 0.12, 0.12, 0.25, T.grisFonce, x, 0.6, 0.35, "z", { m: 0.5 });
            tore(g, 0.14, 0.025, T.rouge, x, 0.9, 0.35, [Math.PI / 2, 0, 0]);
            cyl(g, 0.02, 0.02, 0.25, T.grisFonce, x, 0.78, 0.35, "y");
        }
        cyl(g, 0.32, 0.32, 1.0, T.vert, 1.6, 0.65, 0.5, "y", { r: 0.5 });
        cyl(g, 0.34, 0.3, 0.12, T.grisFonce, 1.6, 1.2, 0.5, "y");
        return g;
    };
    M.bobines = () => {
        // les couronnes de tube PE, à plat et empilées
        const g = groupe();
        for (let k = 0; k < 4; k++) {
            for (let n = 0; n < (k % 2 ? 3 : 4); n++) {
                tore(g, 0.62, 0.2, T.noir, -2.4 + k * 1.6, 0.2 + n * 0.38, 0, [Math.PI / 2, 0, 0], { r: 0.55 });
                tore(g, 0.62, 0.035, T.bleu, -2.4 + k * 1.6, 0.39 + n * 0.38, 0, [Math.PI / 2, 0, 0], { r: 0.5, ombre: false });
            }
        }
        return g;
    };
    M.cantilever = (o = {}) => {
        // un rack cantilever sous auvent : colonnes, bras, fagots de tubes PVC gris et PE noirs à bandes bleues
        const g = groupe();
        const L = o.l ?? 8;
        for (const x of [-L / 2 + 0.3, 0, L / 2 - 0.3]) {
            bloc(g, 0.2, 2.6, 0.25, T.bleuRoi, x, 0, -0.6, { vif: true, m: 0.3 });
            bloc(g, 0.6, 0.1, 1.6, T.bleuRoi, x, 0, 0, { vif: true });
            for (const y of [0.5, 1.2, 1.9]) {
                bloc(g, 0.12, 0.1, 1.3, T.bleuRoi, x, y, 0.05, { vif: true });
            }
        }
        for (const [y, couleur] of [[0.6, o.couleur ?? 0x9aa3ab], [1.3, T.noir], [2.0, o.couleur ?? 0x9aa3ab]]) {
            for (let k = 0; k < 5; k++) {
                cyl(g, 0.08, 0.08, L, couleur, 0, y + 0.08 + (k % 2) * 0.12, -0.4 + k * 0.22, "x", { r: 0.45, seg: 10, ombre: k === 0 });
            }
        }
        return g;
    };
    M.benne = (o = {}) => {
        const g = groupe();
        const forme = new THREE.Shape([new THREE.Vector2(-1.1, 0), new THREE.Vector2(1.1, 0), new THREE.Vector2(1.5, 1.1), new THREE.Vector2(-1.5, 1.1)]);
        const m = ombre(new THREE.Mesh(geo("benne", () => new THREE.ExtrudeGeometry(forme, { depth: 1.5, bevelEnabled: true, bevelSize: 0.05, bevelThickness: 0.05, bevelSegments: 2 })),
                                       mat(o.couleur ?? T.vert)));
        m.position.z = -0.75;
        g.add(m);
        return g;
    };
    M.palette = (o = {}) => {
        const g = groupe();
        bloc(g, 1.2, 0.14, 1.0, T.boisClair, 0, 0, 0, { rayon: 0.02 });
        bloc(g, 1.1, 0.5 + (o.h ?? 0.3), 0.9, T.carton, 0, 0.14, 0, { rayon: 0.04 });
        bloc(g, 0.6, 0.02, 0.4, T.blanc, 0.1, 0.64 + (o.h ?? 0.3), 0, { vif: true, ombre: false });
        return g;
    };
    M.liasse = (o = {}) => {
        const g = groupe();
        bloc(g, 0.45, o.h ?? 0.2, 0.32, T.papier, 0, 0, 0, { rayon: 0.01 });
        bloc(g, 0.46, 0.04, 0.12, o.couleur ?? T.bleu, 0, (o.h ?? 0.2) - 0.02, -0.1, { vif: true, ombre: false });
        return g;
    };
    M.dossiers = (o = {}) => {
        const g = groupe();
        bloc(g, 0.7, 0.04, 0.5, o.couleur ?? T.jaune, 0, 0, 0, { vif: true });
        bloc(g, 0.6, 0.02, 0.42, T.papier, 0, 0.04, 0, { vif: true, ombre: false });
        return g;
    };

    // ---------------------------------------------------------------- les abords
    M.arbre = (o = {}) => {
        const g = groupe();
        const h = o.h ?? 4;
        cyl(g, 0.12, 0.18, h * 0.45, 0x7a5434, 0, h * 0.22, 0);
        if (o.sapin) {
            for (let k = 0; k < 3; k++) {
                const m = ombre(new THREE.Mesh(geo(`cone${k}${h}`, () => new THREE.ConeGeometry(h * (0.32 - k * 0.07), h * 0.4, 9)), mat(T.feuillageFonce)));
                m.position.y = h * (0.45 + k * 0.17);
                g.add(m);
            }
        } else {
            boule(g, h * 0.3, o.couleur ?? T.feuillage, 0, h * 0.68, 0, { seg: 12 });
            boule(g, h * 0.2, o.couleur ?? T.feuillage, h * 0.18, h * 0.55, h * 0.1, { seg: 10 });
            boule(g, h * 0.22, teinteClaire(o.couleur ?? T.feuillage), -h * 0.12, h * 0.82, -h * 0.05, { seg: 10 });
        }
        return g;
    };
    const teinteClaire = (c) => new THREE.Color(c).offsetHSL(0, 0, 0.06).getHex();
    M.haie = (o = {}) => {
        const g = groupe();
        bloc(g, o.l ?? 6, 0.9, 0.8, T.feuillageFonce, 0, 0, 0, { rayon: 0.35 });
        return g;
    };
    M.panneau = (o = {}) => {
        // le panneau de chantier ou de parcelle
        const g = groupe();
        cyl(g, 0.05, 0.05, 2.2, T.grisFonce, -0.5, 1.1, 0, "y", { m: 0.4 });
        cyl(g, 0.05, 0.05, 2.2, T.grisFonce, 0.5, 1.1, 0, "y", { m: 0.4 });
        bloc(g, 1.4, 0.9, 0.06, T.blanc, 0, 1.4, 0, { rayon: 0.04 });
        bloc(g, 1.42, 0.25, 0.08, o.couleur ?? T.orange, 0, 2.05, 0, { rayon: 0.03 });
        return g;
    };
    M.totem = () => {
        // l'enseigne Cultiveau à l'entrée : un totem marine, bande turquoise et goutte
        const g = groupe();
        bloc(g, 0.5, 4.0, 1.4, T.marine, 0, 0, 0, { rayon: 0.12 });
        bloc(g, 0.52, 0.5, 1.42, T.bleu, 0, 3.0, 0, { rayon: 0.08, e: 0.15 });
        boule(g, 0.32, T.eau, 0.28, 2.2, 0, { e: 0.3, ecrase: 1.25 });
        return g;
    };
    M.lampadaire = () => {
        const g = groupe();
        cyl(g, 0.06, 0.08, 5, T.grisFonce, 0, 2.5, 0, "y", { m: 0.5 });
        barre(g, [0, 5, 0], [0.8, 5.1, 0], 0.05, T.grisFonce);
        bloc(g, 0.5, 0.12, 0.25, 0xfff3c4, 0.9, 4.95, 0, { rayon: 0.04, e: 0.6 });
        return g;
    };
    M.quai = () => {
        const g = groupe();
        bloc(g, 2.4, 1.2, 10, T.beton, 0, 0, 0, { rayon: 0.04, r: 0.95 });
        for (let k = -4; k <= 4; k++) {
            bloc(g, 0.1, 0.35, 0.5, T.noir, 1.22, 0.6, k * 1.1, { rayon: 0.04 });
        }
        bloc(g, 0.04, 0.1, 10, T.jaune, 1.2, 1.15, 0, { vif: true });
        return g;
    };
    M.nettoyeur = () => {
        const g = groupe();
        bloc(g, 0.6, 0.8, 0.5, T.jaune, 0, 0, 0, { rayon: 0.08 });
        cyl(g, 0.02, 0.02, 1.2, T.noir, 0.4, 0.4, 0.2, "x");
        return g;
    };
    M.machineCafe = () => {
        const g = groupe();
        bloc(g, 0.6, 1.8, 0.6, T.anthracite, 0, 0, 0, { rayon: 0.05 });
        bloc(g, 0.02, 0.6, 0.45, T.bleu, 0.31, 1.0, 0, { e: 0.5 });
        return g;
    };
    M.plante = () => {
        const g = groupe();
        cyl(g, 0.22, 0.17, 0.42, 0xd9d2c4, 0, 0.21, 0);
        boule(g, 0.36, T.feuillage, 0, 0.75, 0, { seg: 10 });
        return g;
    };

    return { M, mat, geoRonde, bloc, cyl, boule, barre };
}
