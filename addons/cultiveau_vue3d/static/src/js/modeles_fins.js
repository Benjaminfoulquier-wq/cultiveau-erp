/** @odoo-module **/
// Le dessin fin, lot 2 (10/11/2026) : rayonnages et palettes, mobilier, matériel d'irrigation, mini-pelle, semi-remorque.
// Même règle que le lot 1 : tout est dessiné ici, rien n'est téléchargé. Les pièces fixes d'un objet sont fondues en un seul
// maillage coloré par sommet : plus de détail à l'œil, moins de travail pour la carte graphique.

export function modelesFins(THREE, outils) {
    const { T, M, mat, geo, geoRonde, bloc, cyl, boule, tore, barre, capsule, matiere, peinture, verre, verreClair, teintes, fusion, pose, profil, arc, roue, groupe, ombre, feuillage } = outils;

    const C = (hex, dl = 0, ds = 0, dh = 0) => new THREE.Color(hex).offsetHSL(dh, ds, dl);
    const boite = (w, h, d) => new THREE.BoxGeometry(w, h, d);
    const tube = (r, l, seg = 10, r2 = r) => new THREE.CylinderGeometry(r2, r, l, seg);
    const QUART = Math.PI / 2;
    const alea = (s) => () => ((s = (s * 16807) % 2147483647) / 2147483647);
    const teintesMetal = () => matiere("teintesMetal", () => new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.45, metalness: 0.35 }));
    const teintesLisses = () => matiere("teintesLisses", () => new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.5, metalness: 0.05 }));
    const film = () => matiere("film", () => new THREE.MeshPhysicalMaterial({ color: 0xeaf4f8, roughness: 0.16, metalness: 0, transparent: true, opacity: 0.2, depthWrite: false }));
    const chrome = () => mat(0xd9dee3, { r: 0.16, m: 0.95 });
    /** Une pièce à fondre : une géométrie, sa place, sa couleur. */
    const P = (g, x, y, z, c, rx = 0, ry = 0, rz = 0) => ({ g, m: pose(x, y, z, rx, ry, rz), c: c instanceof THREE.Color ? c : new THREE.Color(c) });
    /** Une tige entre deux points, à fondre. */
    const tige = (a, b, r, c, seg = 6) => {
        const va = new THREE.Vector3(...a), vb = new THREE.Vector3(...b), l = va.distanceTo(vb);
        const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), vb.clone().sub(va).normalize());
        return { g: tube(r, l, seg), m: new THREE.Matrix4().compose(va.add(vb).multiplyScalar(0.5), q, new THREE.Vector3(1, 1, 1)), c: c instanceof THREE.Color ? c : new THREE.Color(c) };
    };
    /** Ajoute à g le maillage fondu des pièces (mis en cache sous `cle`). */
    const fondu = (g, cle, pieces, materiau, porte = true) => {
        const m = ombre(new THREE.Mesh(geo(cle, () => fusion(pieces())), materiau || teintes()), porte);
        g.add(m);
        return m;
    };
    /** Une masse de feuillage bosselée, plus sombre dessous. */
    const bosse = (r, c, rnd, detail = 2, ecrase = 0.9) => {
        const q = new THREE.IcosahedronGeometry(r, detail), p = q.attributes.position, n = q.attributes.normal;
        const base = C(c, (rnd() - 0.5) * 0.09, (rnd() - 0.5) * 0.1, (rnd() - 0.5) * 0.04);
        const col = new Float32Array(p.count * 3), f1 = 5 + rnd() * 4, f2 = 6 + rnd() * 5, ph = rnd() * 6;
        for (let j = 0; j < p.count; j++) {
            const dx = p.getX(j) / r, dy = p.getY(j) / r, dz = p.getZ(j) / r;
            const k = 1 + 0.15 * Math.sin(dx * f1 + ph) * Math.sin(dy * f2 + ph * 1.7) + 0.09 * Math.sin(dz * f1 * 1.3 + dx * 3 + ph);
            p.setXYZ(j, dx * r * k, dy * r * k * ecrase, dz * r * k);
            n.setXYZ(j, dx, dy, dz);
            const o = 0.6 + 0.5 * (dy * 0.5 + 0.5);
            col[j * 3] = base.r * o;
            col[j * 3 + 1] = base.g * o;
            col[j * 3 + 2] = base.b * o;
        }
        q.setAttribute("color", new THREE.BufferAttribute(col, 3));
        return q;
    };

    // ---------------------------------------------------------------- les gens (figurant fixe, face à +x)
    M.personne = (o = {}) => {
        const g = groupe();
        const pantalon = o.pantalon ?? T.anthracite, chemise = o.chemise ?? T.bleu;
        for (const z of [-0.1, 0.1]) {
            capsule(g, 0.075, 0.8, pantalon, 0, 0.04, z);
            bloc(g, 0.24, 0.085, 0.115, 0x23272b, 0.045, 0, z, { rayon: 0.04 });
        }
        capsule(g, 0.21, 0.64, chemise, 0, 0.8, 0).scale.set(0.72, 1, 1.05);
        for (const z of [-0.275, 0.275]) {
            capsule(g, 0.055, 0.34, chemise, 0, 1.0, z);
            capsule(g, 0.048, 0.3, T.peau, 0, 0.74, z);
        }
        cyl(g, 0.055, 0.06, 0.1, T.peau, 0, 1.44, 0);
        boule(g, 0.15, T.peau, 0, 1.58, 0).scale.set(0.92, 1.08, 0.9);
        if (o.casque) {
            boule(g, 0.18, T.jaune, 0, 1.63, 0, { ecrase: 0.62 });
        } else {
            boule(g, 0.158, o.cheveux ?? 0x4a3527, -0.02, 1.62, 0, { ecrase: 0.72 });
        }
        return g;
    };

    // ---------------------------------------------------------------- les palettes et les rayonnages
    /** Une palette Europe (1,2 × 1,0 m, dessus à y + 0,144) : semelles, dés, traverses, planches. */
    const piecesPalette = (x, y, z, s = 1) => {
        const r = alea(s * 97 + 3), out = [], bc = () => C(0xd9b47e, (r() - 0.5) * 0.1, (r() - 0.5) * 0.1);
        for (const dz of [-0.45, 0, 0.45]) {
            out.push(P(boite(1.2, 0.022, 0.1), x, y + 0.011, z + dz, bc()));
            for (const dx of [-0.5275, 0, 0.5275]) {
                out.push(P(boite(0.145, 0.078, 0.1), x + dx, y + 0.061, z + dz, bc()));
            }
        }
        for (const dx of [-0.5275, 0, 0.5275]) {
            out.push(P(boite(0.145, 0.022, 1.0), x + dx, y + 0.111, z, bc()));
        }
        for (let k = 0; k < 7; k++) {
            out.push(P(boite(1.2, 0.022, k % 3 === 0 ? 0.145 : 0.1), x, y + 0.133, z - 0.4275 + k * 0.1425, bc()));
        }
        return out;
    };
    /** La charge d'une palette : des cartons en lits croisés, leur ruban adhésif, une étiquette, un bandeau à la couleur de la famille. */
    const piecesCharge = (x, y, z, h, s, couleur) => {
        const r = alea(s * 131 + 7), out = [];
        const nl = Math.max(1, Math.round(h / 0.3)), hl = h / nl;
        for (let n = 0; n < nl; n++) {
            const nx = n % 2 ? 2 : 3, nz = n % 2 ? 3 : 2, w = 1.12 / nx, d = 0.92 / nz;
            for (let i = 0; i < nx; i++) {
                for (let j = 0; j < nz; j++) {
                    const cx = x - 0.56 + w * (i + 0.5), cz = z - 0.46 + d * (j + 0.5), cy = y + hl * (n + 0.5);
                    out.push(P(boite(w - 0.012, hl - 0.008, d - 0.012), cx, cy, cz, C(0xcf9b58, (r() - 0.5) * 0.09, (r() - 0.5) * 0.08)));
                    if (n === nl - 1) {
                        out.push(P(boite(w - 0.012, 0.003, 0.05), cx, y + h - 0.002, cz, C(0xe6cfa0)));
                    }
                    if (j === nz - 1 && r() > 0.45) {
                        out.push(P(boite(0.14, 0.09, 0.004), cx, cy, cz + d / 2 - 0.004, C(0xf6f4ee)));
                    }
                }
            }
        }
        if (couleur !== undefined) {
            out.push(P(boite(1.136, 0.1, 0.936), x, y + h * 0.55, z, C(couleur)));
        }
        return out;
    };
    M.palette = (o = {}) => {
        const g = groupe();
        const h = 0.5 + (o.h ?? 0.3);
        fondu(g, `palette${h}|${o.couleur}`, () => [...piecesPalette(0, 0, 0, 1), ...piecesCharge(0, 0.144, 0, h, Math.round(h * 100), o.couleur)]);
        fondu(g, `paletteFilm${h}`, () => [P(boite(1.15, h + 0.01, 0.95), 0, 0.144 + h / 2, 0, 0xffffff)], film(), false);
        return g;
    };
    M.rack = (o = {}) => {
        // un rack à palettes : échelles bleues contreventées, lisses orange, palettes filmées dont le bandeau dit la famille
        const g = groupe();
        const L = 3.6, H = 3.4, rempl = Math.max(0, Math.min(6, o.remplissage ?? 6)), c = o.couleur ?? T.bleu;
        const niveaux = [0.01, 1.24, 2.36];
        fondu(g, "rackStructure", () => {
            const p = [], bleu = C(T.bleuRoi), orange = C(T.orange), gris = C(0x8f969c);
            for (const x of [-L / 2, 0, L / 2]) {
                for (const z of [-0.5, 0.5]) {
                    p.push(P(boite(0.09, H, 0.07), x, H / 2, z, bleu), P(boite(0.15, 0.012, 0.13), x, 0.006, z, gris));
                }
                const noeuds = [0.15, 0.95, 1.75, 2.55, 3.3];
                noeuds.forEach((y, i) => {
                    p.push(P(boite(0.03, 0.03, 1.0), x, y, 0, bleu));
                    if (i) {
                        const dy = y - noeuds[i - 1], sens = i % 2 ? 1 : -1;
                        p.push(P(boite(0.03, 0.03, Math.hypot(dy, 1.0) - 0.04), x, y - dy / 2, 0, bleu, -sens * Math.atan2(dy, 1.0)));
                    }
                });
                p.push(P(boite(0.13, 0.4, 0.02), x, 0.2, 0.545, C(T.jaune)));
            }
            for (const y of niveaux.slice(1)) {
                for (const z of [-0.47, 0.47]) {
                    p.push(P(boite(L - 0.09, 0.12, 0.05), 0, y - 0.06, z, orange));
                }
            }
            p.push(P(boite(L - 0.09, 0.08, 0.05), 0, H - 0.1, -0.47, orange), P(boite(L - 0.09, 0.08, 0.05), 0, H - 0.1, 0.47, orange));
            return p;
        }, teintesMetal());
        if (rempl) {
            const cases = [];
            niveaux.forEach((y, n) => [-L / 4, L / 4].forEach((x, k) => cases.push([x, y, n * 2 + k])));
            const pleines = cases.slice(0, rempl);
            fondu(g, `rackCharge${rempl}|${c}`, () => pleines.flatMap(([x, y, s]) => [...piecesPalette(x, y, 0, s + 2), ...piecesCharge(x, y + 0.144, 0, 0.6 + ((s * 5) % 3) * 0.09, s + 2, c)]));
            fondu(g, `rackFilm${rempl}`, () => pleines.map(([x, y, s]) => {
                const h = 0.6 + ((s * 5) % 3) * 0.09;
                return P(boite(1.15, h + 0.01, 0.95), x, y + 0.144 + h / 2, 0, 0xffffff);
            }), film(), false);
        }
        return g;
    };
    M.cantilever = (o = {}) => {
        // un rack cantilever : colonnes contreventées, bras à butée, lits de tubes PVC gris et PE noirs à liseré bleu, creux en bout
        const g = groupe();
        const L = o.l ?? 8, cTube = o.couleur ?? 0x9aa3ab;
        fondu(g, `cantilever${L}|${cTube}`, () => {
            const p = [], bleu = C(T.bleuRoi), xs = [-L / 2 + 0.3, 0, L / 2 - 0.3];
            for (const x of xs) {
                p.push(P(boite(0.2, 2.6, 0.25), x, 1.3, -0.6, bleu), P(boite(0.5, 0.1, 1.6), x, 0.05, 0, bleu));
                for (const y of [0.5, 1.2, 1.9]) {
                    p.push(P(boite(0.12, 0.1, 1.3), x, y + 0.05, 0.05, bleu), P(boite(0.12, 0.22, 0.05), x, y + 0.11, 0.7, bleu));
                }
            }
            p.push(P(boite(L - 0.6, 0.1, 0.1), 0, 2.5, -0.6, bleu));
            for (let k = 0; k < 2; k++) {
                const x0 = xs[k], x1 = xs[k + 1];
                p.push(tige([x0, 0.3, -0.6], [x1, 2.3, -0.6], 0.022, bleu), tige([x0, 2.3, -0.6], [x1, 0.3, -0.6], 0.022, bleu));
            }
            const r = alea(41);
            [[0.6, cTube], [1.3, 0x17191c], [2.0, cTube]].forEach(([y, couleur], n) => {
                for (let lit = 0; lit < 2; lit++) {
                    for (let k = 0; k < 6 - lit; k++) {
                        const ty = y + 0.085 + lit * 0.147, tz = -0.4 + k * 0.17 + lit * 0.085, l = L - 0.2 - (n === 1 ? 0 : Math.floor(r() * 3) * 0.12);
                        p.push(P(tube(0.08, l, 12), 0, ty, tz, C(couleur, (r() - 0.5) * 0.04), 0, 0, QUART));
                        for (const s of [1, -1]) {
                            p.push(P(new THREE.CircleGeometry(0.066, 12), s * (l / 2 + 0.002), ty, tz, 0x0c0d0e, 0, s * QUART, 0));
                        }
                        if (n === 1) {
                            p.push(P(boite(l, 0.004, 0.022), 0, ty + 0.08, tz, C(T.bleu)));
                        }
                    }
                }
            });
            return p;
        }, teintesLisses());
        return g;
    };
    M.bobines = () => {
        // les couronnes de tube PE, à plat et empilées, cerclées et marquées d'un liseré bleu
        const g = groupe();
        fondu(g, "bobines", () => {
            const p = [], r = alea(17);
            for (let k = 0; k < 4; k++) {
                for (let n = 0; n < (k % 2 ? 3 : 4); n++) {
                    const x = -2.4 + k * 1.6 + (r() - 0.5) * 0.05, y = 0.2 + n * 0.385, z = (r() - 0.5) * 0.06, a0 = r() * 3;
                    p.push(P(new THREE.TorusGeometry(0.62, 0.2, 10, 30), x, y, z, 0x16181b, QUART));
                    p.push(P(new THREE.TorusGeometry(0.62, 0.016, 4, 30), x, y + 0.192, z, C(T.bleu), QUART));
                    for (let i = 0; i < 4; i++) {
                        const a = a0 + (i * Math.PI) / 2;
                        p.push(P(new THREE.TorusGeometry(0.208, 0.013, 5, 14), x + Math.cos(a) * 0.62, y, z + Math.sin(a) * 0.62, 0xe9e7df, 0, -a, 0));
                    }
                }
            }
            return p;
        }, teintesLisses());
        return g;
    };

    // ---------------------------------------------------------------- le mobilier
    M.chaise = (o = {}) => {
        // un siège de bureau : piétement cinq branches à roulettes, vérin, assise et dossier galbés, accoudoirs. Il regarde vers -z.
        const g = groupe();
        const c = o.couleur ?? 0x2f3a44;
        fondu(g, `chaise${c}`, () => {
            const p = [], sombre = C(0x24282c), tissu = C(c);
            for (let i = 0; i < 5; i++) {
                const a = (i / 5) * Math.PI * 2 + 0.3;
                p.push(P(boite(0.3, 0.03, 0.05), Math.cos(a) * 0.15, 0.075, Math.sin(a) * 0.15, sombre, 0, -a, 0));
                p.push(P(new THREE.SphereGeometry(0.035, 8, 6), Math.cos(a) * 0.29, 0.035, Math.sin(a) * 0.29, 0x121416));
            }
            p.push(P(tube(0.026, 0.3, 8), 0, 0.22, 0, 0xaab0b6), P(boite(0.2, 0.04, 0.22), 0, 0.36, 0, sombre));
            p.push(P(geoRonde(0.48, 0.085, 0.46, 0.04), 0, 0.42, 0, tissu));
            p.push(P(boite(0.06, 0.28, 0.03), 0, 0.5, 0.245, sombre), P(geoRonde(0.44, 0.5, 0.07, 0.035), 0, 0.8, 0.25, tissu, 0.1));
            for (const x of [-0.26, 0.26]) {
                p.push(P(boite(0.03, 0.22, 0.03), x, 0.52, 0.04, sombre), P(geoRonde(0.06, 0.03, 0.26, 0.012), x, 0.64, 0.02, sombre));
            }
            return p;
        });
        return g;
    };
    /** Un moniteur posé sur un plan à la hauteur y, face à +z : pied, col, dalle. */
    const piecesEcran = (x, y, z) => [
        P(geoRonde(0.24, 0.012, 0.18, 0.005), x, y + 0.006, z, 0x24282c), P(boite(0.04, 0.16, 0.02), x, y + 0.08, z - 0.02, 0x24282c),
        P(geoRonde(0.62, 0.37, 0.025, 0.01), x, y + 0.325, z, 0x1a1d20),
    ];
    M.bureau = (o = {}) => {
        // un poste de travail : plateau bois sur piétement métal, caisson à tiroirs, écran (nommé « ecran », allumé par le moteur),
        // clavier, souris, tasse, papiers et son siège
        const g = groupe();
        const L = o.l ?? 1.8;
        fondu(g, `bureau${L}`, () => {
            const blanc = C(0xe6e8ea), gris = C(0xd0d5d9), p = [P(geoRonde(L, 0.035, 0.85, 0.012), 0, 0.7375, 0, C(0xdcb98a))];
            for (const x of [-L / 2 + 0.08, L / 2 - 0.08]) {
                p.push(P(boite(0.05, 0.69, 0.05), x, 0.375, -0.36, blanc), P(boite(0.05, 0.69, 0.05), x, 0.375, 0.36, blanc));
                p.push(P(boite(0.06, 0.03, 0.8), x, 0.015, 0, blanc), P(boite(0.05, 0.04, 0.74), x, 0.7, 0, blanc));
            }
            p.push(P(boite(L - 0.22, 0.3, 0.018), 0, 0.52, -0.38, gris));
            const xc = L / 2 - 0.36;
            p.push(P(boite(0.42, 0.56, 0.55), xc, 0.31, 0.05, gris));
            for (const y of [0.13, 0.31, 0.49]) {
                p.push(P(boite(0.4, 0.006, 0.004), xc, y + 0.09, 0.327, 0x8f969c), P(boite(0.12, 0.012, 0.016), xc, y, 0.333, 0x4a5157));
            }
            p.push(...piecesEcran(0, 0.755, -0.25));
            p.push(P(boite(0.42, 0.015, 0.14), 0, 0.763, 0.08, 0x2a2e33), P(geoRonde(0.06, 0.025, 0.1, 0.012), 0.32, 0.768, 0.1, 0x2a2e33));
            p.push(P(tube(0.04, 0.09, 10), -L / 2 + 0.5, 0.8, 0.18, 0xf4f2ec), P(boite(0.21, 0.012, 0.3), -L / 2 + 0.26, 0.761, 0.02, 0xf7f6f2, 0, 0.2, 0));
            p.push(P(boite(0.21, 0.006, 0.3), -L / 2 + 0.28, 0.77, 0.03, 0xdfeaf5, 0, -0.1, 0));
            return p;
        });
        const e = new THREE.Mesh(geo("dalleEcran", () => new THREE.PlaneGeometry(0.58, 0.33)), mat(0x0e1418, { r: 0.2 }));
        e.name = "ecran";
        e.position.set(0, 1.08, -0.236);
        g.add(e);
        const chaise = M.chaise();
        chaise.position.set(0, 0, 0.75);
        g.add(chaise);
        return g;
    };
    M.table = (o = {}) => {
        // la table de réunion : plateau bois, deux pieds en T reliés, les sièges autour
        const g = groupe();
        const L = o.l ?? 4, Pr = o.p ?? 1.6;
        fondu(g, `table${L}|${Pr}`, () => {
            const p = [P(geoRonde(L, 0.045, Pr, 0.02), 0, 0.7275, 0, C(0xdcb98a))], metal = C(0x3a4046);
            for (const x of [-L / 2 + 0.45, L / 2 - 0.45]) {
                p.push(P(boite(0.1, 0.67, 0.1), x, 0.37, 0, metal), P(boite(0.08, 0.035, Pr * 0.72), x, 0.018, 0, metal), P(boite(0.08, 0.03, Pr * 0.6), x, 0.69, 0, metal));
            }
            p.push(P(boite(L - 0.9, 0.06, 0.04), 0, 0.62, 0, metal));
            p.push(P(tube(0.11, 0.035, 14, 0.07), 0, 0.768, 0, 0x24282c), P(boite(0.21, 0.008, 0.3), L / 4, 0.755, 0.2, 0xf7f6f2, 0, 0.3, 0));
            return p;
        });
        const n = Math.max(2, Math.round(L / 1.2));
        for (let k = 0; k < n; k++) {
            const x = -L / 2 + 0.6 + (k * (L - 1.2)) / (n - 1);
            for (const s of [-1, 1]) {
                const c = M.chaise();
                c.position.set(x, 0, s * (Pr / 2 + 0.25));
                c.rotation.y = s > 0 ? 0 : Math.PI;
                g.add(c);
            }
        }
        return g;
    };
    M.comptoir = () => {
        // le comptoir d'accueil : façade habillée de tasseaux bois, plinthe en retrait, plateau débordant, liseré lumineux,
        // deux écrans, un terminal de paiement et un présentoir
        const g = groupe();
        bloc(g, 0.86, 0.08, 5.94, 0x15181b, 0.02, 0, 0, { vif: true });
        bloc(g, 0.92, 0.9, 6.0, T.marine, 0, 0.08, 0, { rayon: 0.03, r: 0.5 });
        bloc(g, 1.15, 0.06, 6.1, T.boisClair, 0, 0.98, 0, { rayon: 0.02, r: 0.4 });
        bloc(g, 0.02, 0.03, 5.9, T.bleu, -0.5, 0.94, 0, { vif: true, e: 0.7, ombre: false });
        fondu(g, "comptoirDetails", () => {
            const p = [], r = alea(5);
            for (let k = 0; k < 40; k++) {
                p.push(P(boite(0.022, 0.8, 0.06), -0.468, 0.5, -2.925 + k * 0.15, C(0xd4a971, (r() - 0.5) * 0.07)));
            }
            p.push(...piecesEcran(0, 1.04, -0.18).map((q) => ({ ...q, m: pose(0, 0, -1.5, 0, -QUART, 0).multiply(q.m) })));
            p.push(...piecesEcran(0, 1.04, -0.18).map((q) => ({ ...q, m: pose(0, 0, 1.4, 0, -QUART, 0).multiply(q.m) })));
            p.push(P(geoRonde(0.09, 0.05, 0.17, 0.015), -0.3, 1.065, 0.4, 0x2a2e33, 0.25), P(boite(0.02, 0.26, 0.2), -0.36, 1.17, -0.5, 0xf7f6f2, 0, 0, 0.2));
            p.push(P(boite(0.24, 0.02, 0.3), -0.3, 1.05, -0.5, 0x8f969c));
            return p;
        });
        bloc(g, 0.004, 0.31, 0.56, T.bleu, 0.166, 1.21, -1.5, { vif: true, e: 0.5, ombre: false });
        bloc(g, 0.004, 0.31, 0.56, 0x9ee6f5, 0.166, 1.21, 1.4, { vif: true, e: 0.5, ombre: false });
        return g;
    };
    M.armoire = () => {
        // l'armoire à portes battantes : socle, deux portes à poignée, des boîtes d'archives dessus
        const g = groupe();
        bloc(g, 0.56, 0.08, 1.96, 0x30353a, 0, 0, 0, { vif: true });
        bloc(g, 0.6, 1.92, 2.0, T.gris, 0, 0.08, 0, { rayon: 0.03, r: 0.5, m: 0.2 });
        fondu(g, "armoireDetails", () => {
            const p = [];
            for (const z of [-0.495, 0.495]) {
                p.push(P(geoRonde(0.02, 1.82, 0.96, 0.008), 0.305, 1.04, z, 0xdde1e4), P(boite(0.025, 0.3, 0.02), 0.325, 1.0, z * 0.14, 0x30353a));
            }
            p.push(P(boite(0.012, 0.06, 0.09), 0.318, 1.6, -0.5, 0xf7f6f2));
            [[-0.6, 0xcf9b58], [-0.2, 0xd9a35a], [0.5, 0xf7f6f2]].forEach(([z, c]) => p.push(P(boite(0.4, 0.27, 0.34), 0, 2.135, z, c)));
            return p;
        });
        return g;
    };
    M.etabli = () => {
        // l'établi : plateau bois épais, bloc tiroirs, tablette basse, panneau perforé garni d'outils, étau
        const g = groupe();
        fondu(g, "etabli", () => {
            const p = [P(boite(3.0, 0.07, 0.9), 0, 0.885, 0, C(0xb98a55))], acier = C(0x3f4850), outil = C(0xb9c0c6), r = alea(9);
            for (const x of [-1.42, 1.42]) {
                for (const z of [-0.38, 0.38]) {
                    p.push(P(boite(0.07, 0.85, 0.07), x, 0.425, z, acier));
                }
            }
            p.push(P(boite(2.8, 0.03, 0.75), 0, 0.2, 0, acier), P(boite(3.0, 1.0, 0.03), 0, 1.43, -0.44, 0xcfd4d8));
            p.push(P(boite(0.8, 0.5, 0.8), -0.95, 0.6, 0, C(T.bleuRoi)));
            for (const y of [0.45, 0.6, 0.75]) {
                p.push(P(boite(0.76, 0.006, 0.004), -0.95, y + 0.075, 0.402, 0x16335f), P(boite(0.3, 0.014, 0.018), -0.95, y, 0.41, outil));
            }
            // les outils au mur : marteau, clés plates, scie, tournevis, bacs à bec
            p.push(P(boite(0.03, 0.3, 0.02), -1.2, 1.55, -0.415, 0xb98a55), P(boite(0.12, 0.045, 0.04), -1.2, 1.71, -0.41, outil));
            for (let k = 0; k < 4; k++) {
                p.push(P(boite(0.028, 0.2 + k * 0.035, 0.01), -0.95 + k * 0.09, 1.6, -0.42, outil, 0, 0, 0.06));
                p.push(P(tube(0.013, 0.17, 6), 0.55 + k * 0.08, 1.6, -0.41, C([T.rouge, T.jaune, T.bleu, T.vert][k])));
            }
            p.push(P(boite(0.42, 0.11, 0.008), -0.25, 1.62, -0.42, outil), P(boite(0.1, 0.13, 0.025), 0.0, 1.62, -0.415, C(T.orange)));
            for (let k = 0; k < 7; k++) {
                p.push(P(boite(0.17, 0.1, 0.13), -1.2 + k * 0.19, 1.14, -0.36, C([T.rouge, T.bleu, T.jaune][k % 3], (r() - 0.5) * 0.05)));
            }
            // l'étau et un tube en cours de coupe
            p.push(P(boite(0.2, 0.08, 0.26), 1.0, 0.96, 0.2, C(T.bleuRoi)), P(boite(0.2, 0.15, 0.05), 1.0, 1.075, 0.13, C(T.bleuRoi)), P(boite(0.2, 0.15, 0.05), 1.0, 1.075, 0.29, C(T.bleuRoi)));
            p.push(P(tube(0.012, 0.34, 6), 1.0, 1.04, 0.36, outil, QUART), P(tube(0.008, 0.2, 6), 1.0, 1.04, 0.53, outil));
            p.push(P(tube(0.055, 0.9, 12), 0.7, 1.11, 0.21, 0x9aa3ab, 0, 0, QUART));
            return p;
        }, teintesLisses());
        return g;
    };
    M.plans = () => {
        // la table à dessin du bureau d'étude : tréteaux bois, plans déroulés, rouleaux, règle
        const g = groupe();
        fondu(g, "plans", () => {
            const p = [P(geoRonde(2.6, 0.04, 1.4, 0.015), 0, 0.92, 0, 0xf2f1ec)], boisC = C(0xc89a62);
            for (const x of [-1.05, 1.05]) {
                p.push(tige([x, 0.9, 0], [x - 0.02, 0, -0.45], 0.03, boisC), tige([x, 0.9, 0], [x - 0.02, 0, 0.45], 0.03, boisC), P(boite(0.05, 0.04, 0.6), x - 0.01, 0.35, 0, boisC));
            }
            [[-0.6, -0.2, 0.1, 0xdbeaf7], [0.4, 0.15, -0.15, 0xe8f0f7], [0.8, -0.3, 0.3, 0xf7f6f2]].forEach(([x, z, r, c], i) => p.push(P(boite(0.9, 0.004, 0.62), x, 0.944 + i * 0.004, z, c, 0, r, 0)));
            p.push(P(tube(0.035, 0.9, 10), -0.3, 0.98, 0.55, 0xf7f6f2, 0, 0, QUART), P(tube(0.03, 0.8, 10), -0.2, 0.975, 0.47, 0xdbeaf7, 0, 0.1, QUART));
            p.push(P(boite(0.6, 0.006, 0.04), 0.3, 0.96, -0.1, C(T.jaune), 0, 0.5, 0), P(tube(0.035, 0.1, 10), 1.1, 0.99, 0.5, 0x2a2e33));
            return p;
        });
        return g;
    };
    M.machineCafe = () => {
        const g = groupe();
        bloc(g, 0.6, 1.8, 0.6, 0, 0, 0, 0, { rayon: 0.04, mat: peinture(0x23282d) });
        bloc(g, 0.012, 0.45, 0.46, 0x0f1114, 0.3, 0.55, 0, { vif: true, ombre: false });
        bloc(g, 0.012, 0.42, 0.46, T.bleu, 0.3, 1.25, 0, { vif: true, e: 0.55, ombre: false });
        cyl(g, 0.035, 0.03, 0.08, T.blanc, 0.26, 0.6, 0);
        for (let k = 0; k < 3; k++) {
            bloc(g, 0.014, 0.04, 0.04, 0xf7f6f2, 0.3, 1.1, -0.12 + k * 0.12, { vif: true, e: 0.3, ombre: false });
        }
        return g;
    };
    M.plante = () => {
        const g = groupe();
        cyl(g, 0.22, 0.16, 0.42, 0xd9d2c4, 0, 0.21, 0, "y", { r: 0.55 });
        cyl(g, 0.2, 0.2, 0.02, 0x4a3628, 0, 0.415, 0, "y", { ombre: false });
        cyl(g, 0.02, 0.03, 0.3, 0x6a4a30, 0, 0.55, 0);
        const f = ombre(new THREE.Mesh(geo(`houppier1|${T.feuillage}`, () => feuillage(1, T.feuillage)), teintes()));
        f.scale.setScalar(1.05);
        f.position.y = 0.12;
        g.add(f);
        return g;
    };
    M.haie = (o = {}) => {
        // une haie taillée : des masses de feuillage serrées, jamais deux fois la même
        const g = groupe();
        const l = Math.round((o.l ?? 6) * 2) / 2;
        fondu(g, `haie${l}`, () => {
            const p = [], r = alea(Math.round(l * 10) + 3), n = Math.max(2, Math.ceil(l / 0.42));
            for (let i = 0; i < n; i++) {
                const x = -l / 2 + 0.3 + (i * (l - 0.6)) / (n - 1);
                p.push({ g: bosse(0.46 + r() * 0.06, 0x4c9440, r, 2, 1.0), m: pose(x, 0.46 + r() * 0.05, (r() - 0.5) * 0.12, 0, r() * 6, 0) });
            }
            return p;
        });
        return g;
    };

    // ---------------------------------------------------------------- l'irrigation
    M.pompe = (o = {}) => {
        // une pompe de surface : moteur à ailettes et capot de ventilateur, boîte à bornes, protège-accouplement, volute,
        // brides boulonnées à l'aspiration et au refoulement, châssis
        const g = groupe();
        const c = o.couleur ?? T.bleuRoi;
        cyl(g, 0.24, 0.24, 0.6, c, -0.32, 0.42, 0, "x", { mat: peinture(c), seg: 24 });
        cyl(g, 0.3, 0.3, 0.22, c, 0.3, 0.42, 0, "x", { mat: peinture(c), seg: 26 });
        tore(g, 0.3, 0.085, c, 0.3, 0.42, 0, [0, QUART, 0], { r: 0.42, m: 0.3 });
        fondu(g, `pompe${c}`, () => {
            const p = [], cc = C(c), acier = C(0x4a5157), clair = C(0xb9c0c6);
            p.push(P(boite(1.5, 0.06, 0.62), 0, 0.03, 0, acier), P(boite(1.5, 0.08, 0.06), 0, 0.1, 0.25, acier), P(boite(1.5, 0.08, 0.06), 0, 0.1, -0.25, acier));
            for (let k = 0; k < 18; k++) {
                const a = (k / 18) * Math.PI * 2;
                p.push(P(boite(0.52, 0.04, 0.012), -0.32, 0.42 + Math.cos(a) * 0.25, Math.sin(a) * 0.25, cc, a));
            }
            p.push(P(tube(0.255, 0.14, 20), -0.69, 0.42, 0, 0x24282c, 0, 0, QUART), P(new THREE.SphereGeometry(0.255, 16, 8, 0, Math.PI * 2, 0, QUART), -0.76, 0.42, 0, 0x24282c, 0, 0, QUART));
            p.push(P(boite(0.22, 0.1, 0.2), -0.3, 0.72, 0, acier), P(boite(0.14, 0.2, 0.2), -0.32, 0.24, 0, cc), P(boite(0.2, 0.24, 0.3), 0.3, 0.22, 0, cc));
            p.push(P(geoRonde(0.16, 0.32, 0.38, 0.06), 0.06, 0.44, 0, C(T.jaune)));
            p.push(P(tube(0.1, 0.3, 14), 0.56, 0.42, 0, clair, 0, 0, QUART), P(tube(0.17, 0.035, 16), 0.72, 0.42, 0, clair, 0, 0, QUART));
            p.push(P(tube(0.09, 0.36, 14), 0.3, 0.86, 0, clair), P(tube(0.155, 0.035, 16), 0.3, 1.04, 0, clair));
            for (let k = 0; k < 8; k++) {
                const a = (k / 8) * Math.PI * 2;
                p.push(P(tube(0.014, 0.06, 6), 0.72, 0.42 + Math.cos(a) * 0.14, Math.sin(a) * 0.14, acier, 0, 0, QUART));
                p.push(P(tube(0.013, 0.06, 6), 0.3 + Math.cos(a) * 0.125, 1.04, Math.sin(a) * 0.125, acier));
            }
            p.push(P(boite(0.12, 0.07, 0.004), -0.3, 0.5, 0.243, clair));
            return p;
        }, teintesMetal());
        return g;
    };
    M.enrouleur = (o = {}) => {
        // l'enrouleur : châssis sur roues à crampons, tourelle, grand tambour à flasques ajourés chargé de tube PE, timon et béquille
        const g = groupe();
        const c = o.couleur ?? T.rouge;
        fondu(g, `enrouleur${c}`, () => {
            const p = [], cc = C(c), acier = C(0x4a5157);
            for (const z of [-0.5, 0.5]) {
                p.push(P(boite(2.6, 0.14, 0.1), 0, 0.6, z, cc), tige([-0.7, 0.66, z * 1.36], [0, 2.15, z * 1.36], 0.05, cc), tige([0.7, 0.66, z * 1.36], [0, 2.15, z * 1.36], 0.05, cc));
                p.push(P(boite(1.6, 0.1, 0.1), 0, 0.66, z * 1.36, cc), P(tube(0.1, 0.1, 12), 0, 2.15, z * 1.5, acier, QUART));
            }
            for (const x of [-1.25, -0.4, 0.5, 1.25]) {
                p.push(P(boite(0.1, 0.12, 1.36), x, 0.6, 0, cc));
            }
            p.push(P(tube(0.07, 2.2, 10), -0.4, 0.55, 0, acier, QUART), P(tube(0.5, 0.1, 22), 0, 0.72, 0, acier));
            p.push(tige([1.3, 0.6, 0.3], [2.7, 0.42, 0], 0.05, cc), tige([1.3, 0.6, -0.3], [2.7, 0.42, 0], 0.05, cc), P(tube(0.07, 0.06, 10), 2.74, 0.42, 0, acier));
            p.push(P(tube(0.035, 0.5, 8), 2.1, 0.25, 0, acier), P(boite(0.16, 0.02, 0.16), 2.1, 0.01, 0, acier));
            p.push(P(geoRonde(0.5, 0.42, 0.42, 0.07), 0.95, 0.9, 0.42, acier), P(tube(0.16, 0.2, 14), 0.95, 0.9, 0.72, C(0xb9c0c6), QUART));
            p.push(P(boite(0.3, 0.36, 0.06), 0.4, 1.0, 0.66, C(T.jaune)));
            return p;
        }, teintesMetal());
        roue(g, 0.55, 0.32, -0.4, 0.55, 1.0, c, { crampons: true });
        roue(g, 0.55, 0.32, -0.4, 0.55, -1.0, c, { crampons: true });
        const tambour = groupe();
        tambour.name = "tambour";
        fondu(tambour, `tambour${c}`, () => {
            const p = [], cc = C(c), noir = C(0x15171a);
            p.push(P(tube(0.92, 0.94, 30), 0, 0, 0, noir, QUART), P(tube(0.13, 1.3, 12), 0, 0, 0, 0x4a5157, QUART));
            for (let k = 0; k < 11; k++) {
                p.push(P(new THREE.TorusGeometry(0.96 + (k % 2) * 0.012, 0.047, 6, 40), 0, 0, -0.45 + k * 0.09, C(0x15171a, (k % 3) * 0.012)));
            }
            for (let k = 0; k < 6; k++) {
                p.push(P(new THREE.TorusGeometry(1.045, 0.047, 6, 40), 0, 0, -0.45 + k * 0.09, noir));
            }
            for (const z of [-0.55, 0.55]) {
                p.push(P(new THREE.TorusGeometry(1.25, 0.045, 6, 44), 0, 0, z, cc), P(new THREE.TorusGeometry(0.7, 0.03, 5, 32), 0, 0, z, cc), P(tube(0.2, 0.06, 14), 0, 0, z, cc, QUART));
                for (let k = 0; k < 10; k++) {
                    const a = (k / 10) * Math.PI * 2;
                    p.push(P(boite(1.12, 0.07, 0.035), Math.cos(a) * 0.69, Math.sin(a) * 0.69, z, cc, 0, 0, a));
                }
            }
            return p;
        }, teintesLisses());
        tambour.position.set(0, 2.15, 0);
        g.add(tambour);
        if (o.tuyau) {
            // le tube déroulé jusqu'au chariot-canon
            barre(g, [0.75, 1.5, 0], [1.6, 0.14, 0], 0.055, 0x15171a, { r: 0.5 });
            barre(g, [1.6, 0.14, 0], [o.tuyau, 0.12, 0], 0.055, 0x15171a, { r: 0.5 });
        }
        return g;
    };
    M.canon = () => {
        // le chariot porte-canon au bout du tube : traîneau à deux roues, colonne, canon à retour lent (nommé « canon », il balaie)
        const g = groupe();
        fondu(g, "chariotCanon", () => {
            const acier = C(0x8f969c), p = [];
            for (const z of [-0.4, 0.4]) {
                p.push(tige([-0.7, 0.3, z], [0.7, 0.3, z], 0.03, acier), tige([0.7, 0.3, z], [0.95, 0.5, z * 0.4], 0.03, acier), tige([-0.3, 0.3, z], [0, 1.1, 0], 0.025, acier), tige([0.4, 0.3, z], [0, 1.1, 0], 0.025, acier));
            }
            p.push(tige([0, 0.32, -0.55], [0, 0.32, 0.55], 0.03, acier), tige([-0.7, 0.3, -0.4], [-0.7, 0.3, 0.4], 0.03, acier), P(tube(0.05, 0.3, 10), 0, 1.05, 0, 0x4a5157));
            return p;
        }, teintesMetal());
        roue(g, 0.32, 0.18, 0, 0.32, 0.6);
        roue(g, 0.32, 0.18, 0, 0.32, -0.6);
        const canon = groupe();
        canon.name = "canon";
        canon.position.set(0, 1.2, 0);
        fondu(canon, "canon", () => {
            const alu = C(0xc3c9cf), p = [];
            p.push(P(tube(0.075, 0.12, 12), 0, 0.03, 0, 0x4a5157), tige([0, 0.05, 0], [-0.75, 0.52, 0], 0.055, alu, 12), tige([-0.75, 0.52, 0], [-0.95, 0.645, 0], 0.035, C(T.bleu), 12));
            p.push(tige([-0.3, 0.3, 0], [-0.75, 0.75, 0.06], 0.012, alu), P(boite(0.1, 0.05, 0.03), -0.78, 0.76, 0.06, alu, 0, 0, -0.5), P(tube(0.05, 0.1, 8), 0.12, 0.02, 0, C(T.rouge)));
            return p;
        }, teintesMetal());
        g.add(canon);
        return g;
    };
    M.pivot = (o = {}) => {
        // le pivot : tour centrale et son coffret, travées cintrées en treillis, tours motrices à roues à crampons,
        // cannes de descente à asperseur, porte-à-faux et canon d'extrémité ; le cercle arrosé dans la culture
        const g = groupe();
        const c = o.couleur ?? 0xb9c2c9, L = o.longueur ?? 7, hTube = 2.35;
        const cercle = ombre(new THREE.Mesh(geo(`disque${L}`, () => new THREE.CircleGeometry(L + 0.3, 48)), mat(0x9fd27a, { r: 1 })), false);
        cercle.rotation.x = -Math.PI / 2;
        cercle.position.y = 0.13;
        g.add(cercle);
        fondu(g, `pivotCentre${c}`, () => {
            const galva = C(c), p = [];
            for (const [x, z] of [[-0.7, -0.7], [0.7, -0.7], [0.7, 0.7], [-0.7, 0.7]]) {
                p.push(tige([x, 0.1, z], [0, 2.5, 0], 0.05, galva), P(boite(0.3, 0.06, 0.3), x, 0.1, z, 0xdcd6ca));
            }
            for (const y of [0.9, 1.7]) {
                const d = 0.7 * (1 - (y - 0.1) / 2.4);
                p.push(tige([-d, y, -d], [d, y, -d], 0.02, galva), tige([d, y, -d], [d, y, d], 0.02, galva), tige([d, y, d], [-d, y, d], 0.02, galva), tige([-d, y, d], [-d, y, -d], 0.02, galva));
            }
            p.push(P(tube(0.11, 2.5, 12), 0, 1.25, 0, galva), P(tube(0.2, 0.3, 14), 0, 2.55, 0, 0x4a5157), P(boite(0.42, 0.55, 0.22), 0.5, 1.2, 0.42, 0xd5d9dd), P(boite(0.1, 0.1, 0.01), 0.5, 1.3, 0.532, C(T.rouge)));
            return p;
        }, teintesMetal());
        const bras = groupe();
        bras.name = "bras";
        const tours = [L * 0.5, L];
        fondu(bras, `pivotBras${c}|${L}`, () => {
            const galva = C(c), sombre = C(0x4a5157), p = [];
            let x0 = 0;
            for (const xt of tours) {
                const n = 6, port = xt - x0, haut = (k) => hTube + 0.28 * Math.sin((k / n) * Math.PI), bas = (k) => hTube - 0.5 * Math.sin((k / n) * Math.PI);
                for (let k = 0; k < n; k++) {
                    const xa = x0 + (port * k) / n, xb = x0 + (port * (k + 1)) / n;
                    p.push(tige([xa, haut(k), 0], [xb, haut(k + 1), 0], 0.085, galva, 10));
                    for (const z of [-0.32, 0.32]) {
                        const za = k ? z : 0, zb = k + 1 < n ? z : 0;
                        p.push(tige([xa, bas(k), za], [xb, bas(k + 1), zb], 0.02, galva));
                        if (k) {
                            p.push(tige([xa, haut(k), 0], [xa, bas(k), z], 0.016, galva));
                        }
                    }
                    if (k) {
                        p.push(tige([xa, bas(k), -0.32], [xa, bas(k), 0.32], 0.014, galva));
                        p.push(tige([xa, haut(k) + 0.08, 0], [xa + 0.12, haut(k) + 0.2, 0], 0.014, sombre), tige([xa + 0.12, haut(k) + 0.2, 0], [xa + 0.2, 1.0, 0], 0.011, sombre, 5));
                        p.push(P(tube(0.02, 0.1, 8, 0.05), xa + 0.2, 0.95, 0, C(T.bleu)), P(tube(0.035, 0.1, 8), xa + 0.2, 1.08, 0, 0x2a2e33));
                    }
                }
                // la tour motrice : un A sur une poutre, un motoréducteur par roue
                p.push(tige([xt, hTube, 0], [xt, 0.55, 0.85], 0.045, galva), tige([xt, hTube, 0], [xt, 0.55, -0.85], 0.045, galva), tige([xt, 1.4, 0.38], [xt, 1.4, -0.38], 0.025, galva));
                p.push(P(boite(0.14, 0.14, 1.9), xt, 0.5, 0, galva), P(geoRonde(0.22, 0.24, 0.3, 0.04), xt, 0.62, 0, sombre), P(boite(0.2, 0.3, 0.14), xt, hTube - 0.05, 0.16, 0xd5d9dd));
                for (const z of [-0.78, 0.78]) {
                    p.push(P(tube(0.09, 0.16, 10), xt, 0.44, z, sombre, QUART));
                }
                x0 = xt;
            }
            p.push(tige([L, hTube, 0], [L + 1.0, hTube - 0.12, 0], 0.05, galva, 8), tige([L, hTube + 0.5, 0], [L + 0.95, hTube - 0.08, 0], 0.012, galva), tige([L, hTube, 0], [L, hTube + 0.5, 0], 0.02, galva));
            p.push(tige([L + 1.0, hTube - 0.12, 0], [L + 1.3, hTube + 0.1, 0], 0.035, C(0xc3c9cf), 8), P(tube(0.03, 0.2, 8), L + 0.6, hTube - 0.2, 0, C(T.bleu)));
            return p;
        }, teintesMetal());
        for (const xt of tours) {
            roue(bras, 0.42, 0.26, xt, 0.42, 0.95, c, { crampons: true });
            roue(bras, 0.42, 0.26, xt, 0.42, -0.95, c, { crampons: true });
        }
        g.add(bras);
        return g;
    };
    M.asperseur = () => {
        // un asperseur à batteur sur sa canne, piqué dans le rang
        const g = groupe();
        fondu(g, "asperseur", () => {
            const galva = C(0xb9c2c9), laiton = C(0xc9a24a);
            return [P(tube(0.02, 1.0, 8), 0, 0.5, 0, galva), tige([0, 0.3, 0], [0.22, 0, 0.12], 0.012, galva), tige([0, 0.3, 0], [-0.22, 0, 0.1], 0.012, galva), tige([0, 0.3, 0], [0, 0, -0.25], 0.012, galva),
                    P(tube(0.035, 0.1, 8), 0, 1.05, 0, laiton), tige([0, 1.08, 0], [0.2, 1.2, 0], 0.02, laiton, 8), tige([0, 1.1, 0], [-0.1, 1.16, 0.05], 0.012, laiton),
                    P(boite(0.16, 0.012, 0.04), 0.06, 1.17, 0.03, laiton, 0, 0.4, 0)];
        }, teintesMetal());
        return g;
    };
    M.culture = (o = {}) => {
        // une parcelle et sa culture : maïs feuillu et en fleur, vigne palissée sur fil, verger en fruits ; la terre nue d'un projet
        const g = groupe();
        const L = o.l ?? 8, Pr = o.p ?? 6.4, genre = o.genre || "mais";
        bloc(g, L, 0.12, Pr, o.nu ? T.terre : (genre === "mais" ? 0x8a9a5a : 0x7fb85a), 0, 0, 0, { rayon: 0.05, r: 0.95 });
        fondu(g, `culture${genre}|${L}|${Pr}|${o.nu ? 1 : 0}|${o.goutte ? 1 : 0}`, () => {
            const p = [], r = alea(Math.round(L * 13 + Pr * 7) + genre.length);
            if (o.nu) {
                for (let k = 0; k < 9; k++) {
                    p.push(P(tube(0.07, L - 0.6, 6), 0, 0.11, -Pr / 2 + 0.6 + k * ((Pr - 1.2) / 8), C(0x946640, (r() - 0.5) * 0.05), 0, 0, QUART));
                }
                return p;
            }
            const rangs = genre === "verger" ? 3 : genre === "vigne" ? 5 : 7;
            for (let rg = 0; rg < rangs; rg++) {
                const z = -Pr / 2 + 0.7 + (rg * (Pr - 1.4)) / (rangs - 1);
                if (o.goutte) {
                    p.push(P(tube(0.018, L - 0.6, 6), 0, genre === "vigne" ? 0.5 : 0.15, z + (genre === "vigne" ? 0 : 0.18), 0x15171a, 0, 0, QUART));
                }
                if (genre === "vigne") {
                    for (let x = -L / 2 + 0.3; x <= L / 2 - 0.25; x += (L - 0.6) / 4) {
                        p.push(P(boite(0.06, 1.3, 0.06), x, 0.77, z, C(0x9a744a)));
                    }
                    for (const y of [0.85, 1.25]) {
                        p.push(P(boite(L - 0.6, 0.008, 0.008), 0, y, z, 0xb9c0c6));
                    }
                }
                const pas = genre === "verger" ? 1.6 : genre === "vigne" ? 0.8 : 0.45;
                for (let x = -L / 2 + 0.5; x < L / 2 - 0.3; x += pas) {
                    const dx = (r() - 0.5) * 0.06;
                    if (genre === "verger") {
                        p.push(P(tube(0.08, 0.85, 7, 0.055), x, 0.54, z, C(0x6f4e33)));
                        p.push({ g: bosse(0.62, T.feuillage, r, 2, 0.88), m: pose(x, 1.35, z, 0, r() * 6, 0) });
                        for (let f = 0; f < 5; f++) {
                            const a = r() * 6.28, e = r() * 0.5;
                            p.push(P(new THREE.IcosahedronGeometry(0.055, 0), x + Math.cos(a) * 0.56 * Math.cos(e), 1.2 + Math.sin(e) * 0.45, z + Math.sin(a) * 0.56 * Math.cos(e), C(r() > 0.5 ? 0xd9442e : 0xe8a02c)));
                        }
                    } else if (genre === "vigne") {
                        p.push(P(tube(0.035, 0.5, 6, 0.025), x + dx, 0.37, z, C(0x5f4530)));
                        p.push({ g: bosse(0.33, 0x4f9a3c, r, 2, 0.95), m: new THREE.Matrix4().makeTranslation(x + dx, 0.98, z).multiply(new THREE.Matrix4().makeScale(1.5, 1.2, 0.62)) });
                        p.push(P(new THREE.IcosahedronGeometry(0.06, 0), x + dx + 0.1, 0.68, z + 0.12, 0x4b2a5c), P(new THREE.IcosahedronGeometry(0.055, 0), x + dx - 0.12, 0.7, z - 0.12, 0x4b2a5c));
                    } else {
                        const h = 0.95 + r() * 0.25, vert = C(0x5fa33a, (r() - 0.5) * 0.08, 0, (r() - 0.5) * 0.02);
                        p.push(P(tube(0.02, h, 5, 0.012), x + dx, 0.12 + h / 2, z, vert));
                        for (let f = 0; f < 4; f++) {
                            const a = f * 1.9 + r() * 0.8, yf = 0.3 + f * 0.2 * h;
                            p.push(P(boite(0.46, 0.006, 0.07), x + dx + Math.cos(a) * 0.19, yf + 0.12, z - Math.sin(a) * 0.19, vert, 0, a, 0.5));
                        }
                        p.push(P(tube(0.004, 0.2, 4, 0.03), x + dx, 0.12 + h + 0.08, z, C(0xd9c27a)), P(tube(0.035, 0.2, 6, 0.02), x + dx + 0.04, 0.12 + h * 0.52, z + 0.03, C(0xb5c95a), 0, 0, -0.35));
                    }
                }
            }
            return p;
        });
        return g;
    };
    M.prefa = () => {
        // une station de tête en préfabrication sur son châssis : collecteur bridé, trois départs à vanne papillon,
        // filtre à tamis, compteur, manomètres et ventouse
        const g = groupe();
        cyl(g, 0.16, 0.16, 3.8, 0, 0, 0.6, -0.4, "x", { mat: peinture(T.bleuRoi), seg: 18 });
        cyl(g, 0.32, 0.32, 0.95, 0, 1.6, 0.68, 0.5, "y", { mat: peinture(T.vert), seg: 22 });
        fondu(g, "prefa", () => {
            const bleu = C(T.bleuRoi), acier = C(0x4a5157), clair = C(0xb9c0c6), rouge = C(T.rouge), p = [];
            p.push(P(boite(4.2, 0.08, 0.1), 0, 0.04, -0.9, acier), P(boite(4.2, 0.08, 0.1), 0, 0.04, 0.9, acier), P(boite(4.2, 0.03, 2.0), 0, 0.095, 0, C(0x6c7883)));
            for (const x of [-1.9, -0.6, 0.6, 1.9]) {
                p.push(P(boite(0.1, 0.08, 1.9), x, 0.04, 0, acier), P(boite(0.08, 0.34, 0.08), x * 0.8, 0.27, -0.4, acier));
            }
            for (const x of [-1.92, 1.92]) {
                p.push(P(tube(0.24, 0.04, 16), x, 0.6, -0.4, clair, 0, 0, QUART));
            }
            for (const x of [-1.2, 0, 1.2]) {
                p.push(P(tube(0.1, 1.0, 12), x, 0.6, 0.1, bleu, QUART), P(tube(0.16, 0.1, 14), x, 0.6, 0.3, acier, QUART), P(tube(0.16, 0.03, 14), x, 0.6, 0.58, clair, QUART));
                p.push(P(tube(0.025, 0.2, 8), x, 0.78, 0.3, acier), P(boite(0.34, 0.035, 0.05), x + 0.12, 0.89, 0.3, rouge), P(boite(0.14, 0.02, 0.14), x, 0.865, 0.3, clair));
            }
            p.push(P(new THREE.SphereGeometry(0.32, 18, 8, 0, Math.PI * 2, 0, QUART), 1.6, 1.15, 0.5, C(T.vert)), P(tube(0.335, 0.05, 20), 1.6, 1.15, 0.5, clair), P(tube(0.03, 0.12, 8), 1.6, 1.5, 0.5, acier));
            p.push(P(tube(0.1, 0.9, 12), 1.6, 0.6, 0.05, bleu, QUART), P(tube(0.06, 0.2, 10), 1.6, 0.28, 0.5, acier));
            p.push(P(geoRonde(0.3, 0.3, 0.36, 0.06), -1.6, 0.6, 0.1, bleu), P(tube(0.1, 0.9, 12), -1.6, 0.6, 0.05, bleu, QUART), P(tube(0.1, 0.07, 14), -1.6, 0.79, 0.1, 0xe9e7df), P(tube(0.1, 0.005, 14), -1.6, 0.83, 0.1, 0x24282c));
            for (const x of [-0.6, 0.6]) {
                p.push(P(tube(0.015, 0.2, 6), x, 0.86, -0.4, clair), P(tube(0.075, 0.035, 14), x, 1.02, -0.4, 0x24282c, QUART), P(tube(0.065, 0.004, 14), x, 1.02, -0.38, 0xf7f6f2, QUART));
            }
            p.push(P(tube(0.02, 0.14, 6), 0, 0.83, -0.4, clair), P(tube(0.07, 0.16, 10, 0.045), 0, 0.98, -0.4, 0x24282c));
            return p;
        }, teintesMetal());
        return g;
    };

    // ---------------------------------------------------------------- les engins
    M.minipelle = (o = {}) => {
        // la mini-pelle : chenilles caoutchouc sur barbotin et galets, lame, tourelle à contrepoids, cabine vitrée,
        // flèche coudée, balancier, vérins chromés et godet à dents
        const g = groupe();
        const c = o.couleur ?? T.orange, laque = peinture(c), zb = -0.32;
        for (const z of [0.55, -0.55]) {
            profil(g, [[-1.0, 0, 0.21], [1.0, 0, 0.21], [1.0, 0.44, 0.21], [-1.0, 0.44, 0.21]], 0.36, 0x191b1e, { r: 0.92, biseau: 0.03, z });
        }
        fondu(g, `minipelle${c}`, () => {
            const p = [], cc = C(c), sombre = C(0x24282c), gomme = C(0x121416);
            for (const z of [0.55, -0.55]) {
                for (let k = 0; k < 13; k++) {
                    const x = -0.78 + k * 0.13;
                    p.push(P(boite(0.055, 0.03, 0.38), x, 0.445, z, gomme), P(boite(0.055, 0.03, 0.38), x, -0.003, z, gomme));
                }
                for (const s of [1, -1]) {
                    p.push(P(tube(0.17, 0.4, 14), s * 0.78, 0.22, z, s > 0 ? sombre : cc, QUART));
                }
                for (const x of [-0.35, 0, 0.35]) {
                    p.push(P(tube(0.08, 0.4, 10), x, 0.1, z, sombre, QUART));
                }
                p.push(P(boite(1.3, 0.14, 0.3), 0, 0.26, z * 0.96, sombre));
            }
            p.push(P(boite(1.0, 0.24, 0.8), 0, 0.3, 0, sombre), P(tube(0.42, 0.1, 20), -0.05, 0.47, 0, sombre));
            // la lame de remblayage
            p.push(P(boite(0.07, 0.4, 1.5), 1.32, 0.24, 0, cc, 0, 0, -0.15), P(boite(0.05, 0.05, 1.5), 1.37, 0.05, 0, sombre));
            p.push(tige([0.7, 0.3, 0.3], [1.3, 0.22, 0.3], 0.04, cc), tige([0.7, 0.3, -0.3], [1.3, 0.22, -0.3], 0.04, cc));
            // le capot moteur, ses ouïes, l'échappement, le siège et les leviers
            for (let k = 0; k < 5; k++) {
                p.push(P(boite(0.012, 0.035, 0.7), -1.004, 0.68 + k * 0.07, 0, sombre));
            }
            p.push(P(tube(0.03, 0.3, 8), -0.75, 1.25, -0.4, sombre), P(geoRonde(0.42, 0.12, 0.44, 0.04), -0.35, 1.18, 0.15, sombre), P(geoRonde(0.1, 0.46, 0.44, 0.04), -0.56, 1.4, 0.15, sombre, 0, 0, 0.12));
            p.push(tige([0.05, 1.1, 0.02], [0.14, 1.42, 0.02], 0.012, sombre), tige([0.05, 1.1, 0.28], [0.14, 1.42, 0.28], 0.012, sombre));
            // la cabine : quatre montants, toit, gyrophare
            for (const [x, z] of [[-0.68, -0.27], [-0.68, 0.57], [0.3, -0.27], [0.3, 0.57]]) {
                p.push(P(boite(0.055, 1.06, 0.055), x, 1.6, z, sombre));
            }
            p.push(P(geoRonde(1.12, 0.07, 0.98, 0.03), -0.19, 2.16, 0.15, cc), P(tube(0.045, 0.08, 10), -0.55, 2.24, 0.45, C(T.orange)));
            // les vérins : corps sombre et tige chromée
            const verin = (a, b, r = 0.045) => {
                const m = [a[0] + (b[0] - a[0]) * 0.58, a[1] + (b[1] - a[1]) * 0.58, a[2]];
                p.push(tige(a, m, r, sombre, 8), tige(m, b, r * 0.55, C(0xe6eaee), 8));
            };
            verin([0.86, 1.02, zb], [1.08, 1.82, zb]);
            verin([1.0, 2.2, zb], [1.82, 2.42, zb], 0.04);
            verin([1.92, 1.95, zb], [2.36, 1.02, zb + 0.0], 0.035);
            for (let k = 0; k < 4; k++) {
                p.push(P(boite(0.1, 0.035, 0.05), 2.4, 0.11, zb - 0.165 + k * 0.11, C(0xb9c0c6), 0, 0, 0.5));
            }
            return p;
        }, teintesMetal());
        profil(g, [[-1.0, 0.52, 0.1], [-1.0, 1.02, 0.24], [-0.4, 1.1, 0.08], [0.72, 0.96, 0.1], [0.8, 0.52, 0.08]], 1.3, laque, { biseau: 0.06 });
        for (const [x, l] of [[-0.68, 0], [0.3, 0]]) {
            bloc(g, 0.012, 1.0, 0.8, 0, x, 1.12, 0.15 + l, { vif: true, mat: verreClair(), ombre: false });
        }
        for (const z of [-0.27, 0.57]) {
            bloc(g, 0.94, 1.0, 0.012, 0, -0.19, 1.12, z, { vif: true, mat: verreClair(), ombre: false });
        }
        // la flèche coudée, le balancier, le godet
        profil(g, [[0.5, 0.95, 0.05], [0.74, 1.92, 0.22], [1.78, 2.3, 0.12], [1.9, 2.12, 0.06], [1.0, 1.74, 0.3], [0.76, 0.95, 0.05]], 0.17, laque, { biseau: 0.03, z: zb });
        profil(g, [[1.7, 2.28, 0.05], [1.92, 2.3, 0.08], [2.4, 0.84, 0.05], [2.24, 0.78, 0.05]], 0.13, laque, { biseau: 0.025, z: zb });
        profil(g, [[2.18, 0.82, 0.05], [2.44, 0.74, 0.08], [2.62, 0.36, 0.16], [2.38, 0.1, 0.04], [2.0, 0.2, 0.16], [1.98, 0.52, 0.2]], 0.46, 0x3a4046, { r: 0.5, m: 0.5, biseau: 0.03, z: zb });
        return g;
    };
    M.semi = (o = {}) => {
        // le semi-remorque d'un fournisseur : tracteur à cabine avancée et déflecteur, réservoir, échappement, sellette ;
        // remorque à rideaux coulissants, portes arrière à crémones, barres anti-encastrement, béquilles, trois essieux
        const g = groupe();
        const c = o.couleur ?? T.bleuRoi, alu = 0xcfd4d8;
        profil(g, [[3.85, 0.75, 0.05], [3.85, 3.0, 0.12], [4.15, 3.6, 0.3], [5.3, 3.62, 0.3], [6.02, 2.95, 0.3], [6.2, 1.95, 0.16], [6.2, 0.75, 0.1]], 2.45, peinture(c), { biseau: 0.1 });
        profil(g, [[6.13, 1.98, 0.02], [6.2, 2.0, 0.02], [6.06, 2.9, 0.02], [5.99, 2.88, 0.02]], 2.16, verre(), { biseau: 0.012, ombre: false });
        profil(g, [[5.05, 2.0, 0.05], [5.05, 2.82, 0.05], [5.82, 2.82, 0.12], [6.02, 2.0, 0.05]], 2.464, verre(), { biseau: 0.004, ombre: false });
        for (const x of [5.5, 3.5]) {
            roue(g, 0.5, 0.36, x, 0.5, 1.05, alu);
            roue(g, 0.5, 0.36, x, 0.5, -1.05, alu);
        }
        for (const x of [-3.4, -4.5, -5.6]) {
            roue(g, 0.48, 0.36, x, 0.48, 1.0, alu);
            roue(g, 0.48, 0.36, x, 0.48, -1.0, alu);
        }
        for (const z of [1.05, -1.05]) {
            profil(g, arc(3.5, 0.5, 0.66, 0.05, 0.25, Math.PI - 0.25, 10), 0.42, 0x1b1e21, { biseau: 0.01, z });
            profil(g, arc(5.5, 0.5, 0.64, 0.05, 0.3, Math.PI - 0.1, 10), 0.4, 0x1b1e21, { biseau: 0.01, z });
            for (const x of [-3.4, -4.5, -5.6]) {
                profil(g, arc(x, 0.48, 0.62, 0.04, 0.35, Math.PI - 0.35, 8), 0.42, 0x1b1e21, { biseau: 0.01, z: z * 0.96 });
            }
        }
        bloc(g, 9.4, 2.75, 2.5, T.blanc, -1.0, 1.2, 0, { rayon: 0.06, r: 0.6 });
        bloc(g, 9.42, 0.5, 2.52, c, -1.0, 3.2, 0, { rayon: 0.06, r: 0.5 });
        for (const z of [0.82, -0.82]) {
            bloc(g, 0.05, 0.16, 0.42, 0xfff6c8, 6.19, 0.82, z, { rayon: 0.03, e: 0.9 });
            bloc(g, 0.04, 0.3, 0.16, T.rouge, -5.71, 1.0, z * 1.3, { rayon: 0.02, e: 0.5 });
        }
        cyl(g, 0.06, 0.06, 2.6, 0, 3.72, 2.35, 1.0, "y", { mat: chrome(), seg: 12 });
        cyl(g, 0.3, 0.3, 1.0, 0, 4.5, 0.72, 1.12, "x", { mat: mat(0xc9ced3, { r: 0.25, m: 0.85 }), seg: 20 });
        fondu(g, `semi${c}`, () => {
            const p = [], sombre = C(0x1b1e21), chassis = C(0x2c3339), clair = C(0xcfd4d8), gris = C(0xdfe2e4);
            // le tracteur : châssis, calandre, pare-chocs, visière, rétroviseurs, marchepieds, sellette
            p.push(P(boite(3.6, 0.26, 1.0), 4.3, 0.66, 0, chassis), P(geoRonde(0.3, 0.42, 2.5, 0.1), 6.12, 0.52, 0, sombre), P(boite(0.05, 0.85, 1.7), 6.19, 1.36, 0, sombre));
            for (let k = 0; k < 5; k++) {
                p.push(P(boite(0.012, 0.03, 1.6), 6.218, 1.05 + k * 0.15, 0, clair));
            }
            p.push(P(geoRonde(0.42, 0.07, 2.3, 0.03), 6.12, 2.98, 0, sombre, 0, 0, -0.25), P(tube(0.55, 0.06, 20), 3.3, 1.0, 0, sombre));
            for (const z of [1.3, -1.3]) {
                p.push(P(geoRonde(0.12, 0.42, 0.2, 0.04), 5.95, 2.3, z, sombre), tige([5.98, 2.6, z * 0.94], [5.95, 2.5, z], 0.018, sombre), P(boite(0.5, 0.05, 0.24), 5.2, 0.62, z * 0.9, clair), P(boite(0.5, 0.05, 0.24), 5.2, 0.98, z * 0.9, clair));
            }
            // la remorque : châssis, rideaux à sangles, portes à crémones, anti-encastrement, béquilles
            p.push(P(boite(9.6, 0.24, 2.3), -0.9, 1.08, 0, chassis), P(boite(8.0, 0.3, 0.14), -1.6, 0.82, 0.5, chassis), P(boite(8.0, 0.3, 0.14), -1.6, 0.82, -0.5, chassis));
            for (const z of [1.256, -1.256]) {
                for (let x = -5.3; x <= 3.4; x += 0.58) {
                    p.push(P(boite(0.035, 2.5, 0.008), x, 2.52, z, gris), P(boite(0.07, 0.1, 0.014), x, 1.3, z, sombre));
                }
                p.push(P(boite(9.3, 0.07, 0.014), -1.0, 1.24, z, clair), P(boite(4.6, 0.12, 0.03), -0.6, 0.66, z * 0.97, clair), P(boite(4.6, 0.12, 0.03), -0.6, 0.42, z * 0.97, clair));
                for (const x of [-2.6, -0.6, 1.4]) {
                    p.push(P(boite(0.06, 0.6, 0.04), x, 0.7, z * 0.96, chassis));
                }
                p.push(P(boite(0.14, 0.9, 0.14), 1.9, 0.5, z * 0.7, chassis), P(boite(0.26, 0.03, 0.26), 1.9, 0.045, z * 0.7, chassis));
            }
            p.push(P(boite(0.014, 2.6, 0.02), -5.706, 2.55, 0, sombre), P(boite(0.02, 2.7, 2.44), -5.7, 2.56, 0, C(0xf1f0ec)));
            for (const z of [-0.85, -0.3, 0.3, 0.85]) {
                p.push(P(tube(0.02, 2.64, 6), -5.725, 2.55, z, clair), P(boite(0.03, 0.05, 0.22), -5.74, 2.1, z + 0.08, clair));
            }
            p.push(P(boite(0.1, 0.12, 2.4), -5.62, 0.55, 0, clair), P(boite(0.02, 0.13, 0.52), -5.722, 1.35, 0, 0xf4f4f0), P(boite(0.03, 0.5, 0.6), -5.64, 0.75, 0.9, sombre), P(boite(0.03, 0.5, 0.6), -5.64, 0.75, -0.9, sombre));
            return p;
        }, teintesMetal());
        return g;
    };

    // ---------------------------------------------------------------- lot 3 : détente, bureautique, cour, atelier
    M.canape = (o = {}) => {
        // un canapé deux places : socle sur pieds, coussins d'assise et de dossier, accoudoirs, un coussin jeté
        const g = groupe();
        const c = o.couleur ?? 0x5d8aa8;
        fondu(g, `canape${c}`, () => {
            const p = [], tissu = C(c), fonce = C(c, -0.05);
            for (const x of [-0.8, 0.8]) {
                for (const z of [-0.34, 0.34]) {
                    p.push(P(tube(0.025, 0.1, 8), x, 0.05, z, 0x2a2e33));
                }
                p.push(P(geoRonde(0.2, 0.46, 0.85, 0.08), x, 0.4, 0, tissu));
            }
            p.push(P(geoRonde(1.5, 0.2, 0.85, 0.06), 0, 0.2, 0, fonce), P(geoRonde(1.5, 0.5, 0.16, 0.06), 0, 0.5, -0.345, fonce));
            for (const x of [-0.355, 0.355]) {
                p.push(P(geoRonde(0.69, 0.16, 0.62, 0.06), x, 0.38, 0.08, tissu), P(geoRonde(0.69, 0.42, 0.17, 0.07), x, 0.62, -0.22, tissu, -0.16));
            }
            p.push(P(geoRonde(0.34, 0.3, 0.12, 0.05), 0.48, 0.6, -0.08, C(T.orange, 0.05), -0.5, 0.3, 0));
            return p;
        });
        return g;
    };
    M.babyfoot = () => {
        // le baby-foot : caisse laquée sur pieds fuselés, terrain, huit barres chromées, joueurs, poignées
        const g = groupe();
        bloc(g, 1.4, 0.3, 0.75, 0, 0, 0.62, 0, { rayon: 0.04, mat: peinture(T.rouge) });
        fondu(g, "babyfoot", () => {
            const p = [P(boite(1.28, 0.012, 0.63), 0, 0.925, 0, C(0x3f9a45))], boisC = C(0xb98a55), acier = C(0xdfe3e6);
            for (const x of [-0.6, 0.6]) {
                for (const z of [-0.3, 0.3]) {
                    p.push(tige([x, 0.64, z], [x * 1.08, 0, z * 1.12], 0.035, boisC, 8));
                }
                p.push(P(boite(0.02, 0.1, 0.2), x * 1.07, 0.87, 0, 0x16181b));
            }
            p.push(P(boite(1.28, 0.004, 0.01), 0, 0.932, 0, 0xf7f6f2), P(new THREE.TorusGeometry(0.1, 0.005, 4, 20), 0, 0.932, 0, 0xf7f6f2, QUART));
            for (let i = 0; i < 8; i++) {
                const x = -0.525 + i * 0.15, rouge = [0, 1, 3, 5].includes(i), n = [1, 2, 3, 5, 5, 3, 2, 1][i], cote = i % 2 ? 1 : -1;
                p.push(P(tube(0.008, 1.06, 6), x, 0.975, cote * 0.05, acier, QUART), P(tube(0.02, 0.11, 8), x, 0.975, cote * 0.63, 0x16181b, QUART));
                for (let k = 0; k < n; k++) {
                    p.push(P(boite(0.03, 0.09, 0.03), x, 0.955, (k - (n - 1) / 2) * (0.5 / Math.max(n - 1, 1.5)), C(rouge ? T.rouge : T.bleuRoi), 0, 0, (i % 3) * 0.15));
                }
            }
            return p;
        }, teintesLisses());
        return g;
    };
    M.imprimante = () => {
        // le copieur multifonction : meuble à bacs papier, scanner à capot, pupitre incliné, plateau de sortie (la feuille sort)
        const g = groupe();
        bloc(g, 0.7, 0.75, 0.6, T.blanc, 0, 0, 0, { rayon: 0.03, r: 0.5 });
        bloc(g, 0.72, 0.3, 0.62, 0xdfe2e5, 0, 0.75, 0, { rayon: 0.04, r: 0.45 });
        fondu(g, "imprimante", () => {
            const p = [], sombre = C(0x2a2e33);
            for (const y of [0.16, 0.36, 0.56]) {
                p.push(P(boite(0.006, 0.006, 0.54), 0.352, y + 0.08, 0, 0x9aa1a7), P(boite(0.012, 0.022, 0.16), 0.356, y, 0, 0x9aa1a7));
            }
            p.push(P(geoRonde(0.5, 0.035, 0.6, 0.012), -0.08, 1.068, 0, sombre), P(boite(0.2, 0.012, 0.3), 0.25, 1.07, 0.1, sombre, 0, 0, 0.35));
            p.push(P(boite(0.3, 0.012, 0.36), 0.46, 0.68, 0, 0xdfe2e5, 0, 0, -0.12), P(boite(0.012, 0.05, 0.36), 0.36, 0.72, 0, sombre));
            return p;
        });
        bloc(g, 0.1, 0.004, 0.14, 0x9ee6f5, 0.26, 1.085, 0.1, { vif: true, e: 0.5, ombre: false }).rotation.z = 0.35;
        const feuille = bloc(g, 0.3, 0.004, 0.21, T.papier, 0.45, 0.7, 0, { vif: true, ombre: false });
        feuille.name = "feuille";
        return g;
    };
    M.serveur = () => {
        // la baie informatique : armoire laquée, porte vitrée, serveurs empilés, voyants (nommés « led », ils clignotent)
        const g = groupe();
        bloc(g, 0.6, 1.9, 0.8, 0, 0, 0, 0, { rayon: 0.02, mat: peinture(0x23282d) });
        fondu(g, "serveur", () => {
            const p = [];
            for (let i = 0; i < 9; i++) {
                p.push(P(boite(0.012, 0.13, 0.66), 0.296, 0.3 + i * 0.165, 0, i % 3 === 2 ? 0x30363c : 0x4a5157), P(boite(0.014, 0.012, 0.6), 0.298, 0.3 + i * 0.165, 0, 0x16181b));
                p.push(P(boite(0.016, 0.03, 0.08), 0.3, 0.3 + i * 0.165 + 0.035, 0.24, 0x8f969c));
            }
            p.push(P(boite(0.5, 0.02, 0.6), 0, 1.905, 0, 0x16181b), P(boite(0.022, 0.2, 0.02), 0.322, 1.0, 0.34, 0x8f969c));
            return p;
        }, teintesMetal(), false);
        bloc(g, 0.008, 1.78, 0.7, 0, 0.312, 0.06, 0, { vif: true, mat: verreClair(), ombre: false });
        for (let i = 0; i < 6; i++) {
            bloc(g, 0.01, 0.025, 0.035, i % 2 ? 0x4fa83a : 0x0b9bb8, 0.305, 0.34 + i * 0.25, -0.25, { vif: true, e: 0.95, ombre: false }).name = "led";
        }
        return g;
    };
    M.benne = (o = {}) => {
        // la benne à gravats : caisse trapézoïdale laquée, raidisseurs, rebord, crochets de levage, gravats
        const g = groupe();
        const c = o.couleur ?? T.vert;
        const forme = new THREE.Shape([new THREE.Vector2(-1.1, 0), new THREE.Vector2(1.1, 0), new THREE.Vector2(1.5, 1.1), new THREE.Vector2(-1.5, 1.1)]);
        const m = ombre(new THREE.Mesh(geo("benne", () => new THREE.ExtrudeGeometry(forme, { depth: 1.5, bevelEnabled: true, bevelSize: 0.05, bevelThickness: 0.05, bevelSegments: 2 })), peinture(c)));
        m.position.z = -0.75;
        g.add(m);
        fondu(g, `benne${c}`, () => {
            const p = [], cc = C(c, -0.04), r = alea(23);
            for (const z of [-0.815, 0.815]) {
                for (const x of [-0.85, 0, 0.85]) {
                    p.push(P(boite(0.07, 1.0, 0.035), x, 0.58, z, cc));
                }
                p.push(P(boite(3.12, 0.07, 0.07), 0, 1.13, z, cc));
                for (const x of [-1.2, 1.2]) {
                    p.push(P(new THREE.TorusGeometry(0.07, 0.018, 5, 12), x, 0.85, z * 1.03, 0x4a5157));
                }
            }
            for (const x of [-1.56, 1.56]) {
                p.push(P(boite(0.07, 0.07, 1.7), x, 1.13, 0, cc));
            }
            p.push(P(boite(2.9, 0.06, 1.52), 0, 1.04, 0, 0x8a8378));
            for (let k = 0; k < 16; k++) {
                p.push(P(boite(0.2 + r() * 0.25, 0.1 + r() * 0.1, 0.15 + r() * 0.25), (r() - 0.5) * 2.5, 1.1, (r() - 0.5) * 1.2, C(r() > 0.6 ? 0xb9774a : 0x9a948a, (r() - 0.5) * 0.1), r(), r() * 3, r()));
            }
            return p;
        }, teintesLisses());
        return g;
    };
    M.quai = () => {
        // le quai de chargement : dalle béton, butoirs caoutchouc, niveleurs acier bordés de jaune, garde-corps, escalier
        const g = groupe();
        bloc(g, 2.4, 1.2, 10, T.beton, 0, 0, 0, { rayon: 0.04, r: 0.95 });
        fondu(g, "quai", () => {
            const p = [], jaune = C(T.jaune), acier = C(0x7a828a);
            for (let k = -4; k <= 4; k++) {
                p.push(P(geoRonde(0.12, 0.4, 0.5, 0.03), 1.24, 0.78, k * 1.1, 0x16181b));
            }
            p.push(P(boite(0.04, 0.1, 10), 1.2, 1.2, 0, jaune));
            for (const z of [-3.3, 0, 3.3]) {
                p.push(P(boite(1.3, 0.025, 1.9), 0.52, 1.212, z, acier), P(boite(0.06, 0.03, 1.9), 1.14, 1.214, z, jaune), P(boite(1.3, 0.03, 0.05), 0.52, 1.214, z - 0.95, jaune), P(boite(1.3, 0.03, 0.05), 0.52, 1.214, z + 0.95, jaune));
            }
            for (let k = 0; k <= 10; k++) {
                p.push(P(tube(0.025, 1.0, 6), -1.12, 1.7, -5 + k + (k === 0 ? 0.05 : k === 10 ? -0.05 : 0), jaune));
            }
            for (const y of [1.7, 2.2]) {
                p.push(P(tube(0.025, 9.9, 6), -1.12, y, 0, jaune, QUART));
            }
            for (let k = 0; k < 5; k++) {
                p.push(P(boite(1.0, 0.24, 0.3), 0.5, 0.12 + k * 0.24, 5.15 + (4 - k) * 0.3, 0xcfc8ba));
            }
            return p;
        }, teintesLisses());
        return g;
    };
    M.pont = (o = {}) => {
        // un pont élévateur deux colonnes : platines, colonnes laquées, chariots, traverse et câbles, groupe hydraulique,
        // quatre bras télescopiques à tampon ; au besoin un tracteur levé dessus (o.charge === "tracteur")
        const g = groupe();
        const c = o.couleur ?? 0xef7d1a, laque = peinture(c);
        const h = o.charge ? 1.55 : 0.32; // la hauteur des bras : levé si une machine est dessus
        for (const z of [-1.2, 1.2]) {
            bloc(g, 0.34, 2.7, 0.34, 0, 0, 0.06, z, { rayon: 0.04, mat: laque });
        }
        bloc(g, 0.3, 0.3, 2.96, 0, 0, 2.76, 0, { rayon: 0.04, mat: laque });
        bloc(g, 0.1, 0.16, 0.2, 0xffd34d, 0.0, 1.05, 1.42, { e: 0.5, rayon: 0.02 });
        fondu(g, `pont${h}`, () => {
            const p = [], sombre = C(0x2c3339), acier = C(0x6c7883);
            for (const z of [-1.2, 1.2]) {
                const vers = z > 0 ? -1 : 1;
                p.push(P(boite(0.8, 0.03, 0.74), 0, 0.015, z, sombre), P(boite(0.14, 2.5, 0.06), 0, 1.33, z + vers * 0.17, sombre), P(boite(0.3, 0.4, 0.1), 0, h + 0.12, z + vers * 0.2, acier));
                p.push(P(tube(0.008, 2.5, 5), 0.12, 1.4, z + vers * 0.19, 0x16181b));
                for (const x of [-1, 1]) {
                    p.push(P(boite(0.95, 0.1, 0.14), x * 0.52, h + 0.03, z + vers * 0.34, acier, 0, x * vers * 0.28, 0), P(boite(0.6, 0.07, 0.1), x * 1.1, h + 0.03, z + vers * 0.52, sombre, 0, x * vers * 0.28, 0));
                    p.push(P(tube(0.09, 0.06, 12), x * 1.36, h + 0.1, z + vers * 0.6, 0x16181b));
                    for (const dz of [-0.28, 0.28]) {
                        p.push(P(tube(0.02, 0.03, 6), x * 0.3, 0.045, z + dz, acier));
                    }
                }
            }
            p.push(P(geoRonde(0.22, 0.42, 0.24, 0.04), 0.0, 1.5, 1.5, C(0x30363c)), P(tube(0.07, 0.3, 10), 0.0, 1.86, 1.5, C(0x8f969c)), P(tube(0.012, 2.9, 5), 0.1, 2.93, 0, 0x16181b, QUART));
            return p;
        }, teintesMetal());
        if (o.charge === "tracteur") {
            const t = M.tracteur({ couleur: o.couleurTracteur });
            t.position.y = h + 0.2;
            t.rotation.y = Math.PI / 2; // de profil entre les colonnes
            g.add(t);
        }
        return g;
    };
    M.presse = (o = {}) => {
        // une presse à balles rondes : chambre cylindrique laquée et ses courroies, porte arrière à vérins, carters latéraux,
        // ramasseur à dents, boîte à filet, timon, cardan et béquille
        const g = groupe();
        const c = o.couleur ?? 0x3a7d3a, laque = peinture(c);
        cyl(g, 0.95, 0.95, 1.6, 0, 0.1, 1.08, 0, "z", { seg: 30, mat: laque });
        profil(g, [[-0.2, 0.25, 0.1], [-1.05, 0.5, 0.35], [-1.2, 1.4, 0.4], [-0.6, 2.05, 0.3], [-0.2, 2.05, 0.05]], 1.7, laque, { biseau: 0.06 });
        for (const z of [-0.87, 0.87]) {
            profil(g, [[-0.5, 0.35, 0.15], [-0.6, 1.75, 0.3], [0.85, 1.75, 0.3], [1.0, 0.6, 0.2], [0.5, 0.35, 0.1]], 0.08, laque, { biseau: 0.02, z });
        }
        roue(g, 0.56, 0.3, 0.1, 0.56, 1.12, 0xe6c84a);
        roue(g, 0.56, 0.3, 0.1, 0.56, -1.12, 0xe6c84a);
        fondu(g, `presse${c}`, () => {
            const p = [], sombre = C(0x23272b), acier = C(0x8f969c), jaune = C(0xffd34d), cc = C(c);
            for (const z of [-0.6, -0.2, 0.2, 0.6]) {
                p.push(P(tube(0.957, 0.28, 30), 0.1, 1.08, z, sombre, QUART));
            }
            p.push(P(tube(0.2, 1.5, 12), 1.05, 0.34, 0, sombre, QUART));
            for (let k = 0; k < 13; k++) {
                for (let a = 0; a < 4; a++) {
                    const an = a * QUART + (k % 2) * 0.6;
                    p.push(tige([1.05, 0.34, -0.72 + k * 0.12], [1.05 + Math.cos(an) * 0.3, 0.34 + Math.sin(an) * 0.3, -0.72 + k * 0.12], 0.008, acier, 4));
                }
            }
            p.push(P(geoRonde(0.4, 0.3, 1.5, 0.05), 0.95, 1.55, 0, cc), P(boite(0.02, 0.1, 1.72), -1.19, 1.0, 0, jaune));
            for (const z of [-0.915, 0.915]) {
                p.push(P(boite(1.2, 0.08, 0.006), 0.15, 1.5, z, jaune), tige([-0.1, 1.5, z], [-0.75, 0.9, z], 0.035, sombre, 8), tige([-0.45, 1.18, z], [-0.85, 0.8, z], 0.02, C(0xe6eaee), 8));
            }
            p.push(tige([0.9, 0.75, 0.35], [2.6, 0.45, 0], 0.05, cc), tige([0.9, 0.75, -0.35], [2.6, 0.45, 0], 0.05, cc), P(tube(0.07, 0.06, 10), 2.64, 0.45, 0, acier));
            p.push(tige([1.0, 0.9, 0], [2.5, 0.62, 0], 0.035, jaune, 8), P(tube(0.03, 0.42, 6), 2.1, 0.24, 0, sombre), P(boite(0.14, 0.02, 0.14), 2.1, 0.01, 0, sombre));
            return p;
        }, teintesMetal());
        return g;
    };
    M.soudeuse = () => {
        // le poste de soudage bout à bout du PE : bâti, tube pris dans quatre mors, miroir chauffant sur son support,
        // groupe hydraulique à manomètre
        const g = groupe();
        fondu(g, "soudeuse", () => {
            const p = [], acier = C(0x3f4850), jaune = C(T.jaune), noir = C(0x15171a);
            p.push(P(boite(2.4, 0.1, 0.8), 0, 0.8, 0, acier), P(boite(2.2, 0.03, 0.7), 0, 0.3, 0, acier));
            for (const x of [-1.12, 1.12]) {
                for (const z of [-0.34, 0.34]) {
                    p.push(P(boite(0.07, 0.8, 0.07), x, 0.4, z, acier));
                }
            }
            for (const s of [-1, 1]) {
                p.push(P(tube(0.16, 1.05, 18), s * 0.56, 1.1, 0, noir, 0, 0, QUART), P(new THREE.CircleGeometry(0.135, 16), s * 0.032, 1.1, 0, 0x0a0b0c, 0, -s * QUART, 0), P(boite(1.05, 0.004, 0.03), s * 0.56, 1.26, 0, C(T.bleu)));
                p.push(P(new THREE.CircleGeometry(0.135, 16), s * 1.087, 1.1, 0, 0x0a0b0c, 0, s * QUART, 0));
                for (const x of [0.25, 0.75]) {
                    p.push(P(new THREE.TorusGeometry(0.185, 0.035, 6, 20), s * x, 1.1, 0, jaune, 0, QUART, 0), P(boite(0.1, 0.12, 0.3), s * x, 0.91, 0, jaune));
                }
                p.push(P(tube(0.02, 2.0, 8), 0, 0.95, s * 0.28, C(0xdfe3e6), 0, 0, QUART));
            }
            p.push(P(tube(0.2, 0.03, 20), 0, 1.1, 0.42, C(0x8a3b2e), 0, 0, QUART), P(boite(0.04, 0.3, 0.04), 0, 0.98, 0.42, acier), P(tube(0.02, 0.2, 6), 0, 1.38, 0.42, noir));
            p.push(P(geoRonde(0.5, 0.45, 0.4, 0.05), 1.6, 0.225, 0.2, C(T.rouge)), P(tube(0.07, 0.03, 12), 1.6, 0.5, 0.2, 0xf7f6f2), P(tube(0.025, 0.3, 6), 1.45, 0.55, 0.2, noir));
            return p;
        }, teintesLisses());
        return g;
    };
    M.bac = () => {
        // le banc d'essai : bâche d'eau en circuit fermé, raidisseurs, boucle d'essai bridée, débitmètre, manomètre
        const g = groupe();
        bloc(g, 4.0, 0.8, 1.8, T.grisFonce, 0, 0, 0, { rayon: 0.04, m: 0.4, r: 0.5 });
        bloc(g, 3.8, 0.04, 1.6, T.eau, 0, 0.72, 0, { vif: true, o: 0.85, r: 0.08, ombre: false });
        fondu(g, "bac", () => {
            const p = [], acier = C(0x4a5157), bleu = C(T.bleuRoi), clair = C(0xb9c0c6);
            for (const z of [-0.905, 0.905]) {
                for (let k = 0; k < 5; k++) {
                    p.push(P(boite(0.06, 0.74, 0.03), -1.6 + k * 0.8, 0.4, z, acier));
                }
                p.push(P(boite(4.04, 0.06, 0.08), 0, 0.8, z, clair));
            }
            for (const x of [-2.0, 2.0]) {
                p.push(P(boite(0.08, 0.06, 1.84), x, 0.8, 0, clair));
            }
            p.push(tige([-1.4, 0.6, -0.5], [-1.4, 1.25, -0.5], 0.06, bleu, 10), tige([-1.4, 1.25, -0.5], [1.4, 1.25, -0.5], 0.06, bleu, 10), tige([1.4, 1.25, -0.5], [1.4, 0.6, -0.5], 0.06, bleu, 10));
            for (const x of [-0.7, 0.7]) {
                p.push(P(tube(0.11, 0.04, 14), x, 1.25, -0.5, clair, 0, 0, QUART));
            }
            p.push(P(geoRonde(0.3, 0.26, 0.24, 0.05), 0, 1.25, -0.5, C(0xe9e7df)), P(boite(0.16, 0.1, 0.006), 0, 1.3, -0.378, 0x16181b));
            p.push(P(tube(0.015, 0.2, 6), 1.0, 1.4, -0.5, clair), P(tube(0.09, 0.04, 14), 1.0, 1.56, -0.5, 0x16181b, QUART), P(tube(0.078, 0.004, 14), 1.0, 1.56, -0.478, 0xf7f6f2, QUART));
            p.push(P(new THREE.TorusGeometry(0.1, 0.02, 5, 14), -1.0, 1.42, -0.5, C(T.rouge), QUART), P(tube(0.015, 0.14, 6), -1.0, 1.35, -0.5, acier));
            return p;
        }, teintesMetal());
        return g;
    };
    M.nettoyeur = () => {
        // le nettoyeur haute pression : capot jaune, poignée, deux roues, flexible lové, lance
        const g = groupe();
        bloc(g, 0.5, 0.62, 0.46, 0, 0, 0.12, 0, { rayon: 0.1, mat: peinture(T.jaune) });
        fondu(g, "nettoyeur", () => {
            const p = [], noir = C(0x16181b);
            for (const z of [-0.26, 0.26]) {
                p.push(P(tube(0.13, 0.06, 14), -0.12, 0.13, z, noir, QUART), tige([-0.22, 0.6, z * 0.8], [-0.32, 1.02, z * 0.8], 0.016, noir));
            }
            p.push(tige([-0.32, 1.02, -0.21], [-0.32, 1.02, 0.21], 0.018, noir), P(boite(0.1, 0.12, 0.3), 0.22, 0.06, 0, noir));
            for (let k = 0; k < 3; k++) {
                p.push(P(new THREE.TorusGeometry(0.15, 0.018, 5, 18), 0.262 + k * 0.02, 0.5, 0, noir, 0, QUART, 0));
            }
            p.push(tige([0.3, 0.75, 0.2], [1.3, 0.5, 0.25], 0.012, C(0x8f969c)), tige([0.3, 0.75, 0.2], [0.18, 0.62, 0.2], 0.025, noir), P(boite(0.012, 0.12, 0.2), 0.253, 0.3, 0, C(0xf7f6f2)));
            return p;
        }, teintesLisses());
        return g;
    };
    M.lampadaire = () => {
        // le lampadaire de cour : embase, fût conique, crosse, lanterne à diodes
        const g = groupe();
        cyl(g, 0.05, 0.085, 5, T.grisFonce, 0, 2.5, 0, "y", { m: 0.6, r: 0.4, seg: 12 });
        cyl(g, 0.14, 0.16, 0.3, T.grisFonce, 0, 0.15, 0, "y", { m: 0.6, r: 0.4, seg: 12 });
        barre(g, [0, 5, 0], [0.35, 5.22, 0], 0.04, T.grisFonce, { m: 0.6, r: 0.4 });
        barre(g, [0.35, 5.22, 0], [0.75, 5.2, 0], 0.035, T.grisFonce, { m: 0.6, r: 0.4 });
        bloc(g, 0.62, 0.09, 0.3, 0x30363c, 1.0, 5.14, 0, { rayon: 0.04, m: 0.5, r: 0.4 });
        bloc(g, 0.5, 0.02, 0.22, 0xfff3c4, 1.0, 5.125, 0, { vif: true, e: 0.9, ombre: false });
        return g;
    };
    M.totem = () => {
        // l'enseigne Cultiveau à l'entrée : un totem marine laqué sur socle, bande turquoise lumineuse et goutte
        const g = groupe();
        bloc(g, 0.6, 0.12, 1.5, 0x30363c, 0, 0, 0, { rayon: 0.03 });
        bloc(g, 0.5, 3.9, 1.4, 0, 0, 0.1, 0, { rayon: 0.12, mat: peinture(T.marine) });
        bloc(g, 0.52, 0.5, 1.42, T.bleu, 0, 3.0, 0, { rayon: 0.08, e: 0.25 });
        boule(g, 0.32, T.eau, 0.28, 2.2, 0, { e: 0.3, ecrase: 1.25, r: 0.15 });
        return g;
    };
    /** Un sapin (hauteur 1) : tronc et étages de branches aux bords irréguliers, plus sombres vers le cœur. */
    const sapin = (v) => {
        const r = alea(71 + v * 13), p = [P(tube(0.035, 0.3, 7, 0.028), 0, 0.15, 0, C(0x5f4530))];
        for (let k = 0; k < 6; k++) {
            const R = 0.3 - k * 0.043, hC = 0.26 - k * 0.012, q = new THREE.ConeGeometry(R, hC, 14, 2), pos = q.attributes.position;
            const base = C(0x2f6f3c, (r() - 0.5) * 0.05, 0, (r() - 0.5) * 0.03), col = new Float32Array(pos.count * 3);
            for (let j = 0; j < pos.count; j++) {
                const x = pos.getX(j), y = pos.getY(j), z = pos.getZ(j), d = Math.hypot(x, z) / R, a = Math.atan2(z, x);
                const k2 = 1 + (d > 0.4 ? 0.16 * Math.sin(a * 7 + k) : 0);
                pos.setXYZ(j, x * k2, y - (d > 0.8 ? 0.03 * Math.sin(a * 7 + k) + 0.02 : 0), z * k2);
                const o2 = 0.55 + 0.5 * d;
                col[j * 3] = base.r * o2;
                col[j * 3 + 1] = base.g * o2;
                col[j * 3 + 2] = base.b * o2;
            }
            q.computeVertexNormals();
            q.setAttribute("color", new THREE.BufferAttribute(col, 3));
            p.push({ g: q, m: pose(0, 0.34 + k * 0.118, 0, 0, r() * 3, 0) });
        }
        return p;
    };
    const arbreFeuillu = M.arbre;
    M.arbre = (o = {}) => {
        if (!o.sapin) {
            return arbreFeuillu(o);
        }
        const g = groupe(), h = o.h ?? 4, v = Math.round(h * 10) % 3;
        fondu(g, `sapin${v}`, () => sapin(v)).scale.setScalar(h);
        return g;
    };
}
