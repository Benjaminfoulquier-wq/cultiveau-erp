/** @odoo-module **/
// Les modèles 3D de la vue d'ensemble : ce qu'on voit dans un magasin d'irrigation, dessiné proprement (angles arrondis,
// roues, vitres, phares). Unités : le mètre. Chaque modèle est un THREE.Group posé au sol (y = 0), centré sur son
// emprise, sa longueur le long de l'axe x. Les pièces animées portent un nom : « bras » (pivot), « roue » (véhicules).

import { modelesFins } from "./modeles_fins";

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
        const m = ombre(new THREE.Mesh(o.vif ? new THREE.BoxGeometry(w, h, d) : geoRonde(w, h, d, o.rayon ?? Math.min(0.06, w / 5, h / 5, d / 5)), o.mat ?? mat(couleur, o)), o.ombre ?? true);
        m.position.set(x, y + h / 2, z);
        g.add(m);
        return m;
    };
    /** Un cylindre d'axe vertical (axe « y »), horizontal (« x » ou « z »), posé avec son centre en (x, y, z). */
    const cyl = (g, r1, r2, h, couleur, x = 0, y = 0, z = 0, axe = "y", o = {}) => {
        const m = ombre(new THREE.Mesh(geo(`c${r1}|${r2}|${h}|${o.seg || 20}`, () => new THREE.CylinderGeometry(r1, r2, h, o.seg || 20)), o.mat ?? mat(couleur, o)), o.ombre ?? true);
        m.position.set(x, y, z);
        if (axe === "x") {
            m.rotation.z = Math.PI / 2;
        } else if (axe === "z") {
            m.rotation.x = Math.PI / 2;
        }
        g.add(m);
        return m;
    };
    /** Une gélule verticale (un membre, un buste) de hauteur h, posée avec son bas en (x, y, z). */
    const capsule = (g, r, h, couleur, x = 0, y = 0, z = 0, o = {}) => {
        const m = ombre(new THREE.Mesh(geo(`cap${r}|${h}`, () => new THREE.CapsuleGeometry(r, Math.max(0.001, h - 2 * r), 5, 12)), o.mat ?? mat(couleur, o)), o.ombre ?? true);
        m.position.set(x, y + h / 2, z);
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
    // ------------------------------------------------------------ le dessin fin (10/11/2026, « beaucoup plus réel »)
    const matiere = (cle, fabrique) => {
        if (!materiaux.has(cle)) {
            materiaux.set(cle, fabrique());
        }
        return materiaux.get(cle);
    };
    /** La peinture de carrosserie : une laque sous vernis, qui prend les reflets du ciel. */
    const peinture = (c) => matiere(`laque${c}`, () => new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.42, metalness: 0.3, clearcoat: 1, clearcoatRoughness: 0.07 }));
    /** Le vitrage teinté des véhicules, et le vitrage clair des cabines. */
    const verre = () => matiere("verre", () => new THREE.MeshPhysicalMaterial({ color: 0x1b2931, roughness: 0.04, metalness: 0.55, transparent: true, opacity: 0.86, envMapIntensity: 1.8 }));
    const verreClair = () => matiere("verreClair", () => new THREE.MeshPhysicalMaterial({ color: 0xa9d6e4, roughness: 0.04, metalness: 0.3, transparent: true, opacity: 0.38, envMapIntensity: 1.8 }));
    const teintes = () => matiere("teintes", () => new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.78, metalness: 0.02 }));
    /** Plusieurs pièces en un seul maillage (positions, normales, couleur par pièce ou par sommet). */
    const fusion = (pieces) => {
        let n = 0;
        const parts = pieces.map((p) => {
            const q = p.g.index ? p.g.toNonIndexed() : p.g.clone();
            if (p.m) {
                q.applyMatrix4(p.m);
            }
            n += q.attributes.position.count;
            return [q, p.c];
        });
        const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), col = new Float32Array(n * 3);
        let k = 0;
        for (const [q, c] of parts) {
            const nb = q.attributes.position.count;
            pos.set(q.attributes.position.array, k * 3);
            nor.set(q.attributes.normal.array, k * 3);
            if (q.attributes.color) {
                col.set(q.attributes.color.array, k * 3);
            } else {
                for (let i = 0; i < nb; i++) {
                    col[(k + i) * 3] = c ? c.r : 1;
                    col[(k + i) * 3 + 1] = c ? c.g : 1;
                    col[(k + i) * 3 + 2] = c ? c.b : 1;
                }
            }
            k += nb;
            q.dispose();
        }
        const out = new THREE.BufferGeometry();
        out.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        out.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
        out.setAttribute("color", new THREE.BufferAttribute(col, 3));
        return out;
    };
    const pose = (x, y, z, rx = 0, ry = 0, rz = 0) => new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz)), new THREE.Vector3(1, 1, 1));
    /** Une pièce tirée de son profil de côté (points [x, y, rayon d'angle]), large de `l` le long de z, aux arêtes adoucies :
     *  une vraie silhouette de carrosserie au lieu d'un empilement de pavés. */
    const profil = (g, pts, l, materiau, o = {}) => {
        const r0 = o.rayon ?? 0.08, bev = Math.min(o.biseau ?? 0.05, l / 2.5);
        const m = ombre(new THREE.Mesh(geo(`pf${JSON.stringify(pts)}|${l}|${r0}|${bev}`, () => {
            const s = new THREE.Shape(), n = pts.length;
            for (let i = 0; i < n; i++) {
                const q = pts[i], a = pts[(i + n - 1) % n], b = pts[(i + 1) % n], r = q[2] ?? r0;
                const da = Math.hypot(a[0] - q[0], a[1] - q[1]), db = Math.hypot(b[0] - q[0], b[1] - q[1]);
                const ra = Math.min(r, da / 2.2), rb = Math.min(r, db / 2.2);
                const p1 = [q[0] + ((a[0] - q[0]) / da) * ra, q[1] + ((a[1] - q[1]) / da) * ra], p2 = [q[0] + ((b[0] - q[0]) / db) * rb, q[1] + ((b[1] - q[1]) / db) * rb];
                i ? s.lineTo(p1[0], p1[1]) : s.moveTo(p1[0], p1[1]);
                s.quadraticCurveTo(q[0], q[1], p2[0], p2[1]);
            }
            s.closePath();
            const e = new THREE.ExtrudeGeometry(s, { depth: l - 2 * bev, bevelEnabled: true, bevelSize: bev, bevelOffset: -bev, bevelThickness: bev, bevelSegments: 3, curveSegments: 6 });
            e.translate(0, 0, -(l - 2 * bev) / 2);
            return e;
        }), typeof materiau === "number" ? mat(materiau, o) : materiau), o.ombre ?? true);
        m.position.z = o.z ?? 0;
        g.add(m);
        return m;
    };
    /** Les points d'un arc épais (une aile, un garde-boue), à donner à `profil`. */
    const arc = (cx, cy, r, e, a0, a1, n = 12) => {
        const p = [];
        for (let i = 0; i <= n; i++) {
            const a = a0 + ((a1 - a0) * i) / n;
            p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r, 0.005]);
        }
        for (let i = n; i >= 0; i--) {
            const a = a0 + ((a1 - a0) * i) / n;
            p.push([cx + Math.cos(a) * (r - e), cy + Math.sin(a) * (r - e), 0.005]);
        }
        return p;
    };
    /** Une roue : pneu aux flancs bombés, jante ajourée, moyeu ; des crampons pour les engins agricoles. */
    const roue = (g, r, l, x, y, z, jante = T.gris, o = {}) => {
        const s = new THREE.Group();
        s.name = "roue";
        const h = l / 2;
        s.add(ombre(new THREE.Mesh(geo(`pneu${r}|${l}`, () => {
            const ri = r * 0.6;
            const pts = [[ri, -h * 0.82], [r * 0.82, -h], [r * 0.96, -h * 0.86], [r, -h * 0.5], [r, h * 0.5], [r * 0.96, h * 0.86], [r * 0.82, h], [ri, h * 0.82]].map(([a, b]) => new THREE.Vector2(a, b));
            const q = new THREE.LatheGeometry(pts, 30);
            q.rotateX(Math.PI / 2);
            return q;
        }), mat(T.pneu, { r: 0.93 }))));
        if (o.crampons) {
            s.add(ombre(new THREE.Mesh(geo(`crampons${r}|${l}`, () => {
                const boite = new THREE.BoxGeometry(r * 0.2, r * 0.1, l * 0.56), n = Math.max(12, Math.round(r * 22)), pieces = [];
                for (let i = 0; i < n; i++) {
                    const a = (i / n) * Math.PI * 2, cote = i % 2 ? 1 : -1;
                    pieces.push({ g: boite, m: new THREE.Matrix4().makeRotationZ(a).multiply(pose(0, r * 1.0, cote * l * 0.2, 0, cote * 0.5, 0)) });
                }
                const f = fusion(pieces);
                boite.dispose();
                return f;
            }), mat(T.pneu, { r: 0.93 }))));
        }
        s.add(ombre(new THREE.Mesh(geo(`jante${r}|${l}`, () => {
            const R = r * 0.62, f = new THREE.Shape();
            f.absarc(0, 0, R, 0, Math.PI * 2, false);
            for (let i = 0; i < 5; i++) {
                const a = (i / 5) * Math.PI * 2, trou = new THREE.Path();
                trou.absarc(Math.cos(a) * R * 0.62, Math.sin(a) * R * 0.62, R * 0.2, 0, Math.PI * 2, true);
                f.holes.push(trou);
            }
            const e = new THREE.ExtrudeGeometry(f, { depth: l * 0.74, bevelEnabled: true, bevelSize: 0.012, bevelOffset: -0.012, bevelThickness: 0.02, bevelSegments: 2, curveSegments: 10 });
            e.translate(0, 0, -l * 0.37);
            return e;
        }), mat(jante, { r: 0.32, m: 0.7 })), false));
        cyl(s, r * 0.17, r * 0.17, l * 0.86, 0x1d2023, 0, 0, 0, "z", { r: 0.5, m: 0.6, seg: 12, ombre: false });
        s.position.set(x, y, z);
        s.userData.rayon = r;
        g.add(s);
        return s;
    };
    /** Le socle commun d'un véhicule routier : caisse profilée et laquée, soubassement, passages de roue, roues, vitrage,
     *  pare-chocs, calandre, phares, feux, plaques, rétroviseurs. */
    const vehicule = (g, d) => {
        const xs = d.pts.map((q) => q[0]), xa = Math.max(...xs), xr = Math.min(...xs), y0 = Math.min(...d.pts.map((q) => q[1]));
        const l = d.l, rr = d.rr, lr = d.lr ?? rr * 0.72, sombre = 0x1b1e21;
        profil(g, d.pts, l, peinture(d.couleur), { rayon: d.rayon ?? 0.14, biseau: 0.09 });
        bloc(g, xa - xr - 0.3, 0.2, l - 0.3, sombre, (xa + xr) / 2, y0 - 0.14, 0, { vif: true, r: 0.9 });
        for (const x of d.roues) {
            cyl(g, rr * 1.2, rr * 1.2, l + 0.012, 0x121416, x, rr, 0, "z", { seg: 26, r: 0.95, ombre: false });
            for (const cote of [1, -1]) {
                roue(g, rr, lr, x, rr, cote * (l / 2 - lr / 2 + 0.03), d.jante ?? 0xcfd4d8);
            }
        }
        for (const v of d.vitres || []) {
            profil(g, v, l + 0.014, verre(), { rayon: 0.05, biseau: 0.004, ombre: false });
        }
        if (d.parebrise) {
            profil(g, d.parebrise, l - 0.24, verre(), { rayon: 0.02, biseau: 0.012, ombre: false });
        }
        bloc(g, 0.2, 0.26, l + 0.02, sombre, xa - 0.07, y0 - 0.06, 0, { rayon: 0.08, r: 0.75 });
        bloc(g, 0.2, 0.26, l + 0.02, sombre, xr + 0.07, y0 - 0.06, 0, { rayon: 0.08, r: 0.75 });
        bloc(g, 0.05, 0.17, l * 0.44, 0x0e1012, xa - 0.015, y0 + (d.yCalandre ?? 0.3), 0, { rayon: 0.02, r: 0.6 });
        bloc(g, 0.02, 0.11, 0.5, 0xf4f4f0, xa + 0.035, y0 - 0.02, 0, { vif: true });
        bloc(g, 0.02, 0.11, 0.5, 0xf4f4f0, xr - 0.035, y0 + 0.02, 0, { vif: true });
        for (const cote of [1, -1]) {
            bloc(g, 0.07, 0.15, 0.34, 0xfff6c8, xa - (d.reculPhare ?? 0.06), d.yPhare, cote * (l / 2 - 0.27), { rayon: 0.05, e: 0.9 });
            bloc(g, 0.05, d.hFeu ?? 0.24, 0.13, T.rouge, xr + 0.005, d.yFeu, cote * (l / 2 - 0.13), { rayon: 0.02, e: 0.5 });
            if (d.xRetro !== undefined) {
                bloc(g, 0.1, 0.17, 0.2, sombre, d.xRetro, d.yRetro, cote * (l / 2 + 0.1), { rayon: 0.04 });
            }
        }
    };
    const groupe = () => new THREE.Group();

    const M = {};

    // ---------------------------------------------------------------- les gens

    // ---------------------------------------------------------------- les véhicules
    M.utilitaire = (o = {}) => {
        // la camionnette d'intervention (un fourgon tôlé) : caisse blanche laquée, bandeau à la couleur, pare-brise incliné
        const g = groupe();
        const c = o.couleur ?? T.bleu;
        vehicule(g, { pts: [[-2.3, 0.4], [-2.3, 2.08, 0.22], [0.8, 2.15, 0.3], [1.3, 1.92, 0.2], [1.78, 1.24, 0.18], [2.24, 1.04, 0.2], [2.33, 0.4, 0.1]], l: 1.9, couleur: T.blanc,
                      roues: [1.45, -1.4], rr: 0.36, lr: 0.26, vitres: [[[0.86, 1.3], [0.86, 1.84], [1.22, 1.84], [1.62, 1.3]]],
                      parebrise: [[1.27, 1.9], [1.34, 1.93], [1.8, 1.27], [1.73, 1.23]], yPhare: 0.86, yFeu: 1.2, xRetro: 1.72, yRetro: 1.3 });
        bloc(g, 4.4, 0.3, 1.916, c, 0.0, 0.62, 0, { rayon: 0.04, r: 0.4, m: 0.2 });
        for (const z of [0.953, -0.953]) {
            bloc(g, 0.012, 1.4, 0.012, 0x8f969c, 0.78, 0.5, z, { vif: true, ombre: false });
            bloc(g, 0.012, 1.5, 0.012, 0x8f969c, -0.55, 0.5, z, { vif: true, ombre: false });
            bloc(g, 0.14, 0.035, 0.025, 0x1b1e21, 0.6, 1.14, z, { vif: true, ombre: false });
            bloc(g, 1.2, 0.03, 0.02, 0x8f969c, -1.25, 1.5, z, { vif: true, ombre: false });
        }
        bloc(g, 0.012, 1.55, 0.014, 0x8f969c, -2.303, 0.5, 0, { vif: true, ombre: false });
        for (const x of [-1.8, -1.1, -0.4, 0.3]) {
            bloc(g, 0.07, 0.03, 1.5, T.blanc, x, 2.1, 0, { rayon: 0.012 });
        }
        if (o.gyrophare) {
            bloc(g, 0.5, 0.14, 0.22, T.orange, 0.6, 2.17, 0, { e: 0.6 });
        }
        return g;
    };
    M.voiture = (o = {}) => {
        const g = groupe();
        const c = o.couleur ?? T.rouge;
        if (o.pickup) {
            vehicule(g, { pts: [[-2.3, 0.42], [-2.3, 1.12, 0.1], [-0.42, 1.12, 0.05], [-0.36, 1.78, 0.2], [0.85, 1.78, 0.25], [1.4, 1.2, 0.15], [2.25, 1.08, 0.22], [2.33, 0.42, 0.1]], l: 1.8, couleur: c,
                          roues: [1.5, -1.5], rr: 0.37, lr: 0.27, vitres: [[[-0.25, 1.24], [-0.25, 1.7], [0.82, 1.7], [1.22, 1.24]]],
                          parebrise: [[0.88, 1.76], [0.94, 1.79], [1.43, 1.22], [1.37, 1.19]], yPhare: 0.9, yFeu: 0.82, hFeu: 0.3, xRetro: 1.3, yRetro: 1.28 });
            bloc(g, 1.7, 0.05, 1.5, 0x1b1e21, -1.38, 1.1, 0, { vif: true, r: 0.9 });
        } else {
            vehicule(g, { pts: [[-2.0, 0.38], [-2.0, 0.96, 0.2], [-1.5, 1.04, 0.12], [-0.98, 1.44, 0.25], [0.32, 1.44, 0.25], [0.98, 1.02, 0.14], [1.93, 0.88, 0.25], [2.03, 0.38, 0.1]], l: 1.75, couleur: c,
                          roues: [1.3, -1.3], rr: 0.33, lr: 0.23, vitres: [[[-0.9, 1.04], [-0.78, 1.37], [0.28, 1.37], [0.8, 1.04]]],
                          parebrise: [[0.36, 1.42], [0.42, 1.45], [1.02, 1.03], [0.96, 1.0]], yPhare: 0.74, yFeu: 0.84, hFeu: 0.14, xRetro: 0.9, yRetro: 1.06, yCalandre: 0.22 });
            profil(g, [[-1.46, 1.05], [-1.4, 1.08], [-0.98, 1.42], [-1.04, 1.39]], 1.5, verre(), { rayon: 0.02, biseau: 0.012, ombre: false });
            for (const z of [0.878, -0.878]) {
                bloc(g, 0.012, 0.62, 0.012, 0x00000, -0.2, 0.42, z, { vif: true, ombre: false, o: 0.35 });
                bloc(g, 0.12, 0.03, 0.02, 0x1b1e21, -0.42, 0.95, z, { vif: true, ombre: false });
                bloc(g, 0.12, 0.03, 0.02, 0x1b1e21, 0.55, 0.95, z, { vif: true, ombre: false });
            }
        }
        return g;
    };
    M.tracteur = (o = {}) => {
        // un tracteur de ferme : capot plongeant laqué, calandre, masses à l'avant, cabine vitrée à montants, ailes arrondies,
        // grandes roues arrière à crampons et jantes de couleur, pot chromé qui fume
        const g = groupe();
        const c = o.couleur ?? 0x2f9a3e;
        const jante = o.jante ?? 0xf2c230;
        const P = peinture(c), fonte = 0x23272a;
        bloc(g, 3.3, 0.4, 0.62, fonte, 0.35, 0.5, 0, { rayon: 0.08, m: 0.4, r: 0.6 });
        bloc(g, 1.5, 0.34, 0.8, 0x1b1e21, 1.15, 0.66, 0, { rayon: 0.05, m: 0.5, r: 0.5 });
        profil(g, [[0.08, 0.92], [0.08, 1.56, 0.1], [1.55, 1.48, 0.2], [2.08, 1.3, 0.22], [2.12, 0.92, 0.08]], 0.94, P, { rayon: 0.12, biseau: 0.11 });
        bloc(g, 0.04, 0.44, 0.66, 0x0e1012, 2.118, 0.98, 0, { rayon: 0.02 });
        for (let i = 0; i < 4; i++) {
            bloc(g, 0.05, 0.022, 0.6, 0x4a5056, 2.13, 1.04 + i * 0.09, 0, { vif: true, m: 0.6, ombre: false });
        }
        for (const z of [0.3, -0.3]) {
            bloc(g, 0.06, 0.1, 0.17, 0xfff6c8, 2.09, 1.4, z, { rayon: 0.03, e: 0.9 });
            bloc(g, 1.1, 0.5, 0.012, 0x1b1e21, 1.05, 0.95, z * 1.58, { vif: true, ombre: false, r: 0.6 });
        }
        for (let k = 0; k < 6; k++) {
            bloc(g, 0.34, 0.4, 0.105, fonte, 2.36, 0.42, -0.3125 + k * 0.125, { rayon: 0.04, m: 0.3 });
        }
        cyl(g, 0.07, 0.07, 1.5, fonte, 1.45, 0.5, 0, "z", { m: 0.4 });
        // la cabine : plancher, montants, vitrage clair, toit
        bloc(g, 1.45, 0.9, 1.3, c, -0.55, 0.75, 0, { rayon: 0.12, mat: P });
        bloc(g, 1.3, 1.2, 1.24, T.vitre, -0.55, 1.65, 0, { rayon: 0.06, mat: verreClair(), ombre: false });
        for (const [x, z] of [[0.08, 0.6], [0.08, -0.6], [-1.18, 0.6], [-1.18, -0.6]]) {
            bloc(g, 0.08, 1.22, 0.08, 0x1d2023, x, 1.64, z, { rayon: 0.025 });
        }
        bloc(g, 0.42, 0.12, 0.46, 0x1d2023, -0.72, 1.66, 0, { rayon: 0.05 });
        bloc(g, 0.1, 0.5, 0.44, 0x1d2023, -0.93, 1.7, 0, { rayon: 0.04 });
        tore(g, 0.17, 0.02, 0x1d2023, -0.3, 2.05, 0, [0.9, Math.PI / 2, 0]);
        bloc(g, 1.64, 0.16, 1.5, c, -0.55, 2.84, 0, { rayon: 0.07, mat: P });
        bloc(g, 1.3, 0.04, 1.2, T.blanc, -0.55, 2.99, 0, { rayon: 0.015 });
        cyl(g, 0.07, 0.08, 0.13, T.orange, -1.0, 3.09, 0.45, "y", { e: 0.6 });
        // les ailes arrière, les roues
        for (const z of [1.0, -1.0]) {
            profil(g, arc(-0.6, 0.82, 0.98, 0.06, 0.2, 2.9), 0.64, P, { biseau: 0.02, z });
            roue(g, 0.82, 0.56, -0.6, 0.82, z, jante, { crampons: true });
            bloc(g, 0.1, 0.18, 0.16, 0x1b1e21, 0.2, 2.35, z * 0.86, { rayon: 0.03 });
        }
        for (const z of [0.74, -0.74]) {
            roue(g, 0.5, 0.36, 1.45, 0.5, z, jante, { crampons: true });
            profil(g, arc(1.45, 0.5, 0.6, 0.035, 0.5, 2.6, 8), 0.36, 0x1b1e21, { biseau: 0.01, z, r: 0.7 });
        }
        // le relevage arrière, le marchepied, l'échappement chromé et sa fumée
        for (const z of [0.36, -0.36]) {
            barre(g, [-1.3, 0.72, z], [-1.95, 0.48, z * 1.15], 0.045, fonte, { m: 0.4 });
        }
        bloc(g, 0.4, 0.04, 0.3, fonte, 0.3, 0.45, 0.72, { vif: true });
        cyl(g, 0.055, 0.055, 1.2, 0xd5dade, 0.55, 2.05, 0.34, "y", { m: 1, r: 0.15 });
        cyl(g, 0.075, 0.075, 0.3, 0x2a2d30, 0.55, 1.75, 0.34, "y", { m: 0.6, r: 0.4 });
        const fumee = groupe();
        fumee.name = "fumee";
        fumee.position.set(0.55, 2.7, 0.34);
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
        vehicule(g, { pts: [[-2.15, 0.4], [-2.15, 1.84, 0.25], [0.5, 1.88, 0.3], [1.18, 1.3, 0.15], [2.05, 1.04, 0.25], [2.16, 0.4, 0.1]], l: 1.8, couleur: c,
                      roues: [1.35, -1.35], rr: 0.34, lr: 0.24, vitres: [[[0.36, 1.26], [0.36, 1.74], [0.56, 1.74], [1.02, 1.26]]],
                      parebrise: [[0.55, 1.85], [0.61, 1.88], [1.22, 1.3], [1.16, 1.27]], yPhare: 0.8, yFeu: 1.1, xRetro: 1.08, yRetro: 1.3 });
        for (const z of [0.903, -0.903]) {
            bloc(g, 0.012, 1.3, 0.012, 0x8f969c, 0.3, 0.48, z, { vif: true, ombre: false });
            bloc(g, 0.012, 1.3, 0.012, 0x8f969c, -0.75, 0.48, z, { vif: true, ombre: false });
            bloc(g, 0.13, 0.035, 0.025, 0x1b1e21, 0.14, 1.12, z, { vif: true, ombre: false });
            if (o.bande) {
                bloc(g, 2.6, 0.24, 0.02, o.bande, -0.72, 1.22, z * 1.005, { vif: true, ombre: false, e: o.bande === T.blanc ? 0.15 : 0 });
            }
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
        profil(g, [[0.84, 0.55], [0.84, 1.97, 0.2], [1.85, 1.97, 0.25], [2.24, 1.34, 0.2], [2.36, 1.1, 0.1], [2.36, 0.55, 0.1]], 1.95, peinture(c), { rayon: 0.12, biseau: 0.09 });
        profil(g, [[1.87, 1.93], [1.93, 1.96], [2.3, 1.36], [2.24, 1.33]], 1.7, verre(), { rayon: 0.02, biseau: 0.012, ombre: false });
        profil(g, [[1.15, 1.32], [1.15, 1.84], [1.8, 1.84], [2.1, 1.32]], 1.964, verre(), { rayon: 0.05, biseau: 0.004, ombre: false });
        for (const z of [0.98, -0.98]) {
            bloc(g, 0.1, 0.17, 0.2, 0x1b1e21, 2.02, 1.4, z * 1.1, { rayon: 0.04 });
            if (o.tricolore) {
                [[0x1f4ea1, 0.66], [0xf7f6f2, 0.82], [0xd94f45, 0.98]].forEach(([couleur, y]) => bloc(g, 1.2, 0.16, 0.02, couleur, 1.55, y, z * 1.005, { vif: true, ombre: false }));
            }
        }
        bloc(g, 0.2, 0.28, 2.0, 0x1b1e21, 2.32, 0.42, 0, { rayon: 0.08 });
        bloc(g, 0.05, 0.18, 0.9, 0x0e1012, 2.365, 0.78, 0, { rayon: 0.02 });
        bloc(g, 0.06, 0.15, 0.32, 0xfff6c8, 2.34, 0.9, 0.7, { rayon: 0.05, e: 0.9 });
        bloc(g, 0.06, 0.15, 0.32, 0xfff6c8, 2.34, 0.9, -0.7, { rayon: 0.05, e: 0.9 });
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
        // le chariot élévateur : caisse jaune laquée, contrepoids, protège-conducteur, mât double, tablier et fourches
        const g = groupe();
        const P = peinture(T.jaune), acier = 0x2a2d30;
        profil(g, [[-1.08, 0.2], [-1.08, 0.98, 0.3], [-0.52, 1.1, 0.12], [-0.46, 0.8, 0.05], [0.5, 0.8, 0.1], [0.7, 0.2, 0.08]], 1.12, P, { rayon: 0.1, biseau: 0.08 });
        bloc(g, 0.05, 0.5, 0.8, 0x15181b, -1.085, 0.35, 0, { rayon: 0.02 });
        bloc(g, 0.5, 0.12, 0.52, 0x1b1e21, -0.2, 0.8, 0, { rayon: 0.05 });
        bloc(g, 0.12, 0.5, 0.5, 0x1b1e21, -0.44, 0.9, 0, { rayon: 0.05 });
        barre(g, [0.42, 0.8, 0], [0.22, 1.32, 0], 0.03, acier);
        tore(g, 0.16, 0.022, 0x15181b, 0.2, 1.34, 0, [0.35, Math.PI / 2, 0]);
        for (const z of [0.5, -0.5]) {
            barre(g, [-0.85, 1.02, z], [-0.72, 2.12, z], 0.04, acier);
            barre(g, [0.5, 0.8, z], [0.42, 2.12, z], 0.04, acier);
            barre(g, [-0.72, 2.12, z], [0.42, 2.12, z], 0.04, acier);
        }
        for (const x of [-0.5, -0.15, 0.2]) {
            barre(g, [x, 2.12, -0.5], [x, 2.12, 0.5], 0.025, acier);
        }
        cyl(g, 0.07, 0.08, 0.12, T.orange, -0.6, 2.22, 0, "y", { e: 0.6 });
        // le mât, le vérin, le tablier, les fourches
        for (const z of [0.36, -0.36]) {
            bloc(g, 0.12, 2.75, 0.1, T.grisFonce, 0.84, 0.06, z, { vif: true, m: 0.6, r: 0.4 });
            bloc(g, 1.05, 0.05, 0.12, acier, 1.48, 0.1, z * 0.85, { rayon: 0.015, m: 0.5 });
            bloc(g, 0.06, 0.5, 0.12, acier, 0.98, 0.1, z * 0.85, { rayon: 0.015, m: 0.5 });
        }
        for (const y of [0.4, 1.5, 2.72]) {
            bloc(g, 0.1, 0.09, 0.82, T.grisFonce, 0.84, y, 0, { vif: true, m: 0.6, r: 0.4 });
        }
        cyl(g, 0.045, 0.045, 2.2, 0xd5dade, 0.84, 1.3, 0, "y", { m: 1, r: 0.15 });
        bloc(g, 0.05, 0.42, 0.95, acier, 0.94, 0.3, 0, { rayon: 0.02 });
        for (let k = 0; k < 5; k++) {
            bloc(g, 0.03, 0.7, 0.03, acier, 0.95, 0.72, -0.44 + k * 0.22, { vif: true });
        }
        bloc(g, 0.03, 0.03, 0.95, acier, 0.95, 1.4, 0, { vif: true });
        for (const z of [0.5, -0.5]) {
            roue(g, 0.28, 0.22, 0.42, 0.28, z, T.jaune);
            roue(g, 0.24, 0.2, -0.72, 0.24, z, T.jaune);
        }
        const pilote = M.personne({ chemise: T.orange });
        pilote.scale.setScalar(0.85);
        pilote.position.set(-0.2, 0.3, 0);
        g.add(pilote);
        return g;
    };

    // ---------------------------------------------------------------- le concessionnaire agricole (démonstration)

    // ---------------------------------------------------------------- l'atelier de câblage électrique
    M.armoire_elec = (o = {}) => {
        // une armoire électrique ouverte, portes battantes : la tôle, la platine de montage, les rails DIN, les rangées
        // de disjoncteurs modulaires, les goulottes, un jeu de fils de couleur et l'interrupteur général. Le cœur de
        // l'espace de câblage : on clique dessus pour ouvrir le schéma.
        const g = groupe();
        const toleE = 0xb9c0c6, toleI = 0x9aa2a8, platine = 0xdfe3e6;
        // --- le caisson (fond, côtés, chapeau, socle), face avant ouverte
        bloc(g, 0.44, 0.12, 1.24, T.grisFonce, 0, 0, 0, { rayon: 0.02, m: 0.3 });          // socle
        bloc(g, 0.05, 2.0, 1.24, toleI, -0.19, 0.12, 0, { rayon: 0.02, m: 0.3 });          // fond
        bloc(g, 0.44, 0.08, 1.24, toleE, 0, 2.04, 0, { rayon: 0.02, m: 0.3 });             // chapeau
        for (const z of [-0.6, 0.6]) {
            bloc(g, 0.44, 1.92, 0.05, toleI, 0, 0.12, z, { rayon: 0.02, m: 0.3 });          // flancs
        }
        // --- la platine de montage (tôle claire du fond)
        bloc(g, 0.03, 1.74, 1.08, platine, -0.15, 0.2, 0, { vif: true, m: 0.35, r: 0.5 });
        // --- goulottes verticales de câblage (passage des fils, gris clair)
        for (const z of [-0.5, 0.5]) {
            bloc(g, 0.07, 1.62, 0.11, 0xcfd4d8, -0.11, 0.26, z, { rayon: 0.015 });
        }
        // --- trois rails DIN et leurs rangées de disjoncteurs modulaires
        const rails = [0.55, 1.0, 1.45];
        rails.forEach((y, ri) => {
            bloc(g, 0.04, 0.055, 0.86, 0xaab1b7, -0.125, y, 0, { vif: true, m: 0.7 });       // rail DIN
            bloc(g, 0.075, 0.12, 0.9, 0xeef1f3, -0.09, y + 0.005, 0, { rayon: 0.01 });        // bandeau de modules
            for (let k = 0; k < 10; k++) {
                const z = -0.4 + k * 0.09;
                bloc(g, 0.085, 0.145, 0.078, k % 3 === 0 ? 0xf3f4f5 : 0xe7e9eb, -0.085, y, z, { rayon: 0.006 }); // module
                bloc(g, 0.02, 0.05, 0.03, [T.bleu, T.vert, T.orange, T.rouge][(ri + k) % 4], -0.04, y + 0.055, z, { vif: true, e: 0.25 }); // manette
            }
        });
        // --- l'interrupteur général, plus gros, en haut à gauche
        bloc(g, 0.11, 0.26, 0.2, T.grisFonce, -0.075, 1.72, -0.46, { rayon: 0.02 });
        cyl(g, 0.045, 0.045, 0.05, T.rouge, -0.02, 1.85, -0.46, "x", { e: 0.3 });
        bloc(g, 0.02, 0.06, 0.02, T.jaune, 0.01, 1.85, -0.46, { vif: true });
        // --- le bornier en bas (rangée de bornes)
        bloc(g, 0.05, 0.1, 0.9, 0x3a4149, -0.12, 0.24, 0, { rayon: 0.008 });
        for (let k = 0; k < 16; k++) {
            bloc(g, 0.055, 0.1, 0.03, k % 2 ? 0x8a949c : 0xd7dbdf, -0.1, 0.24, -0.42 + k * 0.056, { vif: true });
        }
        // --- un faisceau de fils de couleur reliant goulottes, rails et bornier
        const fils = [[T.bleu, 0.55], [0x7a4a2a, 1.0], [0x3f8f3a, 1.45], [T.rouge, 0.78], [T.jaune, 1.22]];
        fils.forEach(([c, y], i) => {
            cyl(g, 0.009, 0.009, 0.84, c, -0.085, y + 0.09, 0, "z", { ombre: false, r: 0.4 });     // courant le long du rail
            cyl(g, 0.009, 0.009, Math.abs(y - 0.3), c, -0.085, (y + 0.3) / 2 + 0.05, -0.5 + i * 0.012, "y", { ombre: false, r: 0.4 }); // descente vers le bornier
        });
        // --- deux portes battantes grandes ouvertes
        [[-0.6, -1], [0.6, 1]].forEach(([zc, sens]) => {
            const porte = groupe();
            bloc(porte, 0.035, 1.88, 0.56, toleE, 0, 0, sens * 0.29, { rayon: 0.02, m: 0.3 });        // vantail (gond en z = 0)
            bloc(porte, 0.015, 1.4, 0.4, T.vitre, 0.028, 0, sens * 0.3, { vif: true, o: 0.35, ombre: false }); // fenêtre
            cyl(porte, 0.012, 0.012, 0.18, T.grisFonce, 0.07, 0, sens * 0.5, "y", { m: 0.6 });          // poignée
            porte.position.set(0.2, 1.06, zc);
            porte.rotation.y = sens * 1.85; // grand ouvert vers l'avant
            g.add(porte);
        });
        // --- la pochette à schéma collée dans la porte gauche
        bloc(g, 0.01, 0.34, 0.26, T.papier, 0.42, 1.2, -1.02, { vif: true, ombre: false });
        return g;
    };
    M.touret = (o = {}) => {
        // un touret de câble électrique : deux flasques, le moyeu et le câble enroulé, sur son axe
        const g = groupe();
        for (const z of [-0.34, 0.34]) {
            cyl(g, 0.62, 0.62, 0.07, o.flasque ?? T.bois, 0, 0.64, z, "z", { seg: 22, r: 0.6 });
        }
        cyl(g, 0.46, 0.46, 0.58, o.couleur ?? 0x2c2f33, 0, 0.64, 0, "z", { seg: 22, r: 0.7 });   // câble enroulé
        cyl(g, 0.12, 0.12, 0.8, T.anthracite, 0, 0.64, 0, "z", { seg: 12, m: 0.5 });              // axe
        for (const x of [-0.5, 0.5]) {
            barre(g, [x, 0.64, 0.42], [x, 0.02, 0.5], 0.04, T.grisFonce);
            barre(g, [x, 0.64, -0.42], [x, 0.02, -0.5], 0.04, T.grisFonce);
        }
        return g;
    };
    M.coffret = (o = {}) => {
        // un coffret de commande sur pied : boîtier, voyants, boutons et un petit écran, l'automate de l'installation
        const g = groupe();
        const c = o.couleur ?? 0x3a4149;
        bloc(g, 0.5, 0.04, 0.5, T.grisFonce, 0, 0, 0, { rayon: 0.02 });
        bloc(g, 0.1, 1.0, 0.1, T.grisFonce, 0, 0.04, 0, { vif: true });
        bloc(g, 0.26, 0.6, 0.46, c, 0.03, 1.02, 0, { rayon: 0.03 });
        bloc(g, 0.02, 0.22, 0.3, 0x7fd4e8, 0.17, 1.28, 0, { vif: true, e: 0.5, ombre: false });     // écran
        for (let k = 0; k < 3; k++) {
            cyl(g, 0.025, 0.025, 0.03, [T.vert, T.jaune, T.rouge][k], 0.17, 1.12, -0.12 + k * 0.12, "x", { e: 0.6, ombre: false });
        }
        for (let k = 0; k < 2; k++) {
            cyl(g, 0.03, 0.03, 0.04, k ? T.rouge : T.vert, 0.17, 0.92, -0.08 + k * 0.16, "x", { e: 0.3 });
        }
        return g;
    };

    // ---------------------------------------------------------------- l'irrigation

    // ---------------------------------------------------------------- l'atelier et le stock
    M.gondole = (o = {}) => {
        // une gondole du libre-service : étagères blanches et petites boîtes colorées
        const g = groupe();
        bloc(g, 4.0, 1.6, 0.2, T.blanc, 0, 0, 0, { rayon: 0.04 });
        bloc(g, 4.0, 0.12, 1.0, T.blanc, 0, 0, 0, { rayon: 0.04 });
        bloc(g, 4.06, 0.22, 0.24, o.couleur ?? T.bleu, 0, 1.6, 0, { rayon: 0.05 });
        const palette = [o.couleur ?? T.bleu, T.blanc, T.orange, T.vert, T.jaune];
        for (const y of [0.15, 0.6, 1.05]) {
            bloc(g, 4.0, 0.04, 0.95, T.gris, 0, y, 0, { vif: true });
            bloc(g, 4.0, 0.05, 0.012, 0xf4f4f0, 0, y - 0.01, 0.48, { vif: true, ombre: false });
            bloc(g, 4.0, 0.05, 0.012, 0xf4f4f0, 0, y - 0.01, -0.48, { vif: true, ombre: false });
        }
        g.add(ombre(new THREE.Mesh(geo(`boites${o.couleur ?? T.bleu}`, () => {
            const pieces = [];
            for (const y of [0.15, 0.6, 1.05]) {
                for (let k = 0; k < 13; k++) {
                    for (const cote of [-1, 1]) {
                        const hb = 0.2 + ((k * 7 + Math.round(y * 5)) % 4) * 0.045, lb = 0.2 + ((k * 3) % 3) * 0.03;
                        const boite = new THREE.BoxGeometry(lb, hb, 0.26);
                        const c = new THREE.Color(palette[(k + (cote > 0 ? 2 : 0) + Math.round(y * 3)) % palette.length]).offsetHSL(0, 0, ((k * 5) % 3 - 1) * 0.03);
                        pieces.push({ g: boite, m: pose(-1.83 + k * 0.305, y + 0.04 + hb / 2, cote * 0.3), c });
                    }
                }
            }
            const f = fusion(pieces);
            pieces.forEach((q) => q.g.dispose());
            return f;
        }), teintes()), false));
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
            const c = o.couleur ?? T.feuillage, v = Math.round(h * 10) % 4;
            const houppier = ombre(new THREE.Mesh(geo(`houppier${v}|${c}`, () => feuillage(v, c)), teintes()));
            houppier.scale.setScalar(h);
            g.add(houppier);
            barre(g, [0, h * 0.3, 0], [h * 0.14, h * 0.5, h * 0.06], h * 0.018, 0x6a4a30);
            barre(g, [0, h * 0.26, 0], [-h * 0.12, h * 0.48, -h * 0.08], h * 0.016, 0x6a4a30);
        }
        return g;
    };
    const teinteClaire = (c) => new THREE.Color(c).offsetHSL(0, 0, 0.06).getHex();
    /** Le houppier d'un feuillu (hauteur 1) : des masses bosselées fondues en un maillage, plus sombres dessous. */
    const feuillage = (v, c) => {
        let graine = 11 + v * 37;
        const alea = () => ((graine = (graine * 16807) % 2147483647) / 2147483647);
        const masses = [[0, 0.68, 0, 0.3]];
        for (let k = 0; k < 7; k++) {
            const a = (k / 7) * Math.PI * 2 + alea(), d = 0.14 + alea() * 0.1;
            masses.push([Math.cos(a) * d, 0.52 + alea() * 0.34, Math.sin(a) * d, 0.15 + alea() * 0.09]);
        }
        const pieces = masses.map(([x, y, z, r], i) => {
            const q = new THREE.IcosahedronGeometry(r, 3), p = q.attributes.position, n = q.attributes.normal;
            const base = new THREE.Color(c).offsetHSL((alea() - 0.5) * 0.04, (alea() - 0.5) * 0.1, (alea() - 0.5) * 0.09);
            const col = new Float32Array(p.count * 3), f1 = 5 + alea() * 4, f2 = 6 + alea() * 5, ph = alea() * 6;
            for (let j = 0; j < p.count; j++) {
                const dx = p.getX(j) / r, dy = p.getY(j) / r, dz = p.getZ(j) / r;
                const k = 1 + 0.16 * Math.sin(dx * f1 + ph) * Math.sin(dy * f2 + ph * 1.7) + 0.1 * Math.sin(dz * f1 * 1.3 + dx * 3 + ph);
                p.setXYZ(j, dx * r * k, dy * r * k * 0.92, dz * r * k);
                n.setXYZ(j, dx, dy, dz);
                const ombrage = 0.62 + 0.5 * (dy * 0.5 + 0.5) + 0.08 * Math.sin(dx * 19 + dz * 23 + ph);
                col[j * 3] = base.r * ombrage;
                col[j * 3 + 1] = base.g * ombrage;
                col[j * 3 + 2] = base.b * ombrage;
            }
            q.setAttribute("color", new THREE.BufferAttribute(col, 3));
            return { g: q, m: pose(x, y, z, 0, i * 1.3, 0) };
        });
        const f = fusion(pieces);
        pieces.forEach((q) => q.g.dispose());
        return f;
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

    // le lot 2 du dessin fin : rayonnages, mobilier, irrigation, engins
    modelesFins(THREE, { T, M, mat, geo, geoRonde, bloc, cyl, boule, tore, barre, capsule, matiere, peinture, verre, verreClair, teintes, fusion, pose, profil, arc, roue, groupe, ombre, feuillage });

    return { M, mat, geo, geoRonde, bloc, cyl, boule, barre, capsule };
}
