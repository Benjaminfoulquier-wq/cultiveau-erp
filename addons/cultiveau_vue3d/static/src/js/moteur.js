/** @odoo-module **/
// Le moteur de la Map vivante : la scène construite depuis le plan JSON, la caméra (vue maquette, vol, suivi, visite guidée),
// la sélection (crochets, halo, étiquettes projetées), les marcheurs (A* sur une grille de navigation), les véhicules
// (courbes de Catmull-Rom), les animations d'objets et l'éditeur de plan. `frame(dt)` est séparée de requestAnimationFrame.

const FOV = 26;
const POLAIRE = [0.28, 1.18];
const DISTANCE = [12, 190];
const PAS = 0.5; // la grille de navigation et la grille magnétique de l'éditeur
const MUR_H = 3.2, MUR_BAS = 0.7, MUR_E = 0.22;
const SOL_PAR_TYPE = { accueil: "carrelage", magasin: "carrelage", stockage: "beton", atelier: "beton_marque", bureau: "parquet", reunion: "moquette", pause: "carrelage_chaud",
                       parking: "enrobe", cour: "beton_ext", champs: "terre" };
const TAILLE = { personne: 1.9, camion: 5.5, voiture: 4.4, dossier: 9, zone: 14, rayon: 4, objet: 3, borne: 1.6, livraison: 7, client: 4.4, machine: 1.5, intervention: 5.5, chantier: 9 };
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const lerp = (a, b, k) => a + (b - a) * k;
const angleVers = (a, b) => { let d = b - a; while (d > Math.PI) { d -= 2 * Math.PI; } while (d < -Math.PI) { d += 2 * Math.PI; } return d; };

export class Moteur {
    constructor(THREE, kit, hote, calque, options = {}) {
        this.THREE = THREE;
        this.kit = kit;
        this.hote = hote;
        this.calque = calque;
        this.options = options;
        this.accent = options.accent || "#0b9bb8";
        this.objets = new Map(); // clé -> { groupe, genre, id, nom, sousTitre, priorite, rayon, meta }
        this.cibles = []; // les maillages cliquables
        this.marcheurs = new Map(); // clé -> marcheur
        this.vehicules = new Map();
        this.animes = []; // { objet, animer(dt, t) }
        this.murs = [];
        this.etiquettes = new Map();
        this.temps = 0;
        this.edition = false;
        this.selection = null;
        this.survol = null;
        this.visite = null;
        this.suivi = null;
        this.vol = null;
        this.pointeur = { x: 0, y: 0, bouton: -1, deplace: 0, debut: null };
        this.taille = { w: 1, h: 1 };
        this._initialiser();
    }

    // ------------------------------------------------------------------ le rendu

    _initialiser() {
        const { THREE } = this;
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.toneMapping = THREE.NeutralToneMapping ?? THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.0;
        this.hote.appendChild(renderer.domElement);
        this.renderer = renderer;
        const scene = new THREE.Scene();
        scene.background = null;
        scene.fog = new THREE.Fog(0xece6d8, 120, 260);
        this.scene = scene;
        this.camera = new THREE.PerspectiveCamera(FOV, 1, 0.5, 600);
        this.cam = { cible: new THREE.Vector3(32, 0, 26), distance: 70, azimut: 0.66, polaire: 0.86, vel: { x: 0, z: 0, azimut: 0, polaire: 0, distance: 0 } };
        // la lumière : un ciel, un soleil avec des ombres douces, un appoint froid
        scene.add(new THREE.HemisphereLight(0xf4f8ff, 0xd9cdb2, 1.9));
        const soleil = new THREE.DirectionalLight(0xfff1d6, 2.8);
        soleil.position.set(-18, 60, 10);
        soleil.target.position.set(30, 0, 30);
        soleil.castShadow = true;
        soleil.shadow.mapSize.set(4096, 4096);
        Object.assign(soleil.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 1, far: 180 });
        soleil.shadow.bias = -0.0004;
        soleil.shadow.normalBias = 0.03;
        soleil.shadow.radius = 3;
        scene.add(soleil, soleil.target);
        const appoint = new THREE.DirectionalLight(0xcfe3ff, 0.6);
        appoint.position.set(40, 30, -30);
        scene.add(appoint);
        if (THREE.PMREMGenerator && THREE.RoomEnvironment) {
            try {
                const pmrem = new THREE.PMREMGenerator(renderer);
                scene.environment = pmrem.fromScene(new THREE.RoomEnvironment(), 0.04).texture;
                scene.environmentIntensity = 0.4;
            } catch {
                /* pas d'environnement : la lumière suffit */
            }
        }
        this.raycaster = new THREE.Raycaster();
        this.plan3d = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.statique = new THREE.Group();
        this.dynamique = new THREE.Group();
        scene.add(this.statique, this.dynamique);
        this.marqueurs = { crochets: this.kit.crochets(this.accent), halo: this.kit.halo(this.accent) };
        this.marqueurs.crochets.visible = this.marqueurs.halo.visible = false;
        scene.add(this.marqueurs.crochets, this.marqueurs.halo);
        this._ecouter(renderer.domElement);
        this._observateur = new ResizeObserver(() => this.mesurer());
        this._observateur.observe(this.hote);
        this.mesurer();
    }

    mesurer() {
        const w = Math.max(1, this.hote.clientWidth), h = Math.max(1, this.hote.clientHeight);
        this.taille = { w, h };
        this.renderer.setSize(w, h, false);
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
    }

    detruire() {
        this._observateur?.disconnect();
        this.scene.traverse((o) => {
            o.geometry?.dispose?.();
            if (o.material) {
                [].concat(o.material).forEach((m) => { m.map?.dispose?.(); m.dispose?.(); });
            }
        });
        this.renderer.dispose();
        this.renderer.domElement.remove();
        for (const e of this.etiquettes.values()) {
            e.el.remove();
        }
    }

    // ------------------------------------------------------------------ la scène depuis le plan

    construire(plan) {
        const { THREE, kit } = this;
        this.plan = plan;
        this.statique.clear();
        this.cibles = [];
        this.murs = [];
        this.animes = this.animes.filter((a) => !a.statique);
        for (const [cle, o] of [...this.objets]) {
            if (o.statique) {
                this.objets.delete(cle);
            }
        }
        const ext = plan.exterieur || {};
        const [[x0, z0], [x1, z1]] = ext.sol || [[-8, -2], [72, 66]];
        // la plaine
        const plaine = new THREE.Mesh(new THREE.PlaneGeometry(900, 900), new THREE.MeshStandardMaterial({ color: 0xcfe3ad, roughness: 1 }));
        plaine.rotation.x = -Math.PI / 2;
        plaine.position.set((x0 + x1) / 2, -0.06, (z0 + z1) / 2);
        plaine.receiveShadow = true;
        this.statique.add(plaine);
        const herbe = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, z1 - z0), new THREE.MeshStandardMaterial({ map: kit.sol("herbe", x1 - x0, z1 - z0), roughness: 1 }));
        herbe.rotation.x = -Math.PI / 2;
        herbe.position.set((x0 + x1) / 2, -0.04, (z0 + z1) / 2);
        herbe.receiveShadow = true;
        this.statique.add(herbe);
        // les zones : le sol peint et le nom
        for (const z of plan.zones || []) {
            this._zone(z);
        }
        // la dalle du bâtiment, les murs, les portes, les cloisons
        this._batiment(plan);
        // l'extérieur : route, accès, clôtures, haies, arbres
        this._exterieur(ext);
        // le mobilier
        for (const o of plan.objets || []) {
            this._objetDuPlan(o);
        }
        // les places : invisibles, sauf en édition (un disque)
        this.places = new Map((plan.places || []).map((p) => [p.cle, p]));
        this._placesVisuelles();
        this._grilleNavigation();
        if (plan.camera) {
            this.cam.azimut = plan.camera.azimut ?? this.cam.azimut;
            this.cam.polaire = plan.camera.polaire ?? this.cam.polaire;
            this.cam.cible.set(...(plan.camera.cible || [32, 0, 26]));
            this.cam.distance = plan.camera.distance ?? this.cam.distance;
        }
        this.vue = { cible: this.cam.cible.clone(), distance: this.cam.distance, azimut: this.cam.azimut, polaire: this.cam.polaire };
    }

    _polygone(points) {
        const { THREE } = this;
        const forme = new THREE.Shape();
        points.forEach(([x, z], i) => (i ? forme.lineTo(x, -z) : forme.moveTo(x, -z)));
        return forme;
    }
    _centre(points) {
        const n = points.length;
        return [points.reduce((s, p) => s + p[0], 0) / n, points.reduce((s, p) => s + p[1], 0) / n];
    }
    _zone(z) {
        const { THREE, kit } = this;
        const xs = z.polygone.map((p) => p[0]), zs = z.polygone.map((p) => p[1]);
        const l = Math.max(...xs) - Math.min(...xs), p = Math.max(...zs) - Math.min(...zs);
        const geo = new THREE.ShapeGeometry(this._polygone(z.polygone));
        // les UV à l'échelle du monde (4 m par répétition)
        const uv = geo.attributes.uv, pos = geo.attributes.position;
        for (let i = 0; i < uv.count; i++) {
            uv.setXY(i, pos.getX(i) / 4, pos.getY(i) / 4);
        }
        const texture = kit.sol(z.sol || SOL_PAR_TYPE[z.type] || "beton", 4, 4);
        texture.repeat.set(1, 1);
        const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: texture, roughness: 0.92 }));
        m.rotation.x = -Math.PI / 2;
        m.position.y = z.exterieur ? -0.02 : 0.0;
        m.receiveShadow = true;
        m.userData.cle = `zone:${z.cle}`;
        m.userData.priorite = 0;
        this.statique.add(m);
        this.cibles.push(m);
        const [cx, cz] = this._centre(z.polygone);
        const texte = kit.textePeint((z.nom || z.cle).toUpperCase(), Math.min(l * 0.8, 9), { couleur: z.exterieur ? "rgba(255,255,255,0.55)" : "rgba(40,60,70,0.4)", taille: 48 });
        texte.position.set(cx, 0.03, cz + (z.exterieur ? 0 : Math.min(p * 0.3, 2.5)));
        this.statique.add(texte);
        this.objets.set(`zone:${z.cle}`, { groupe: m, genre: "zone", id: z.cle, nom: z.nom, sousTitre: "", priorite: 0, rayon: Math.max(l, p) / 2, centre: new THREE.Vector3(cx, 0, cz),
                                             statique: true, zone: z, boite: new THREE.Box3(new THREE.Vector3(Math.min(...xs), 0, Math.min(...zs)), new THREE.Vector3(Math.max(...xs), 0.1, Math.max(...zs))) });
    }
    _batiment(plan) {
        const { THREE, kit } = this;
        const contour = plan.contour;
        const [cx, cz] = this._centre(contour);
        // la dalle et le toit (le toit est invisible : vue en coupe), le soubassement
        const dalle = new THREE.Mesh(new THREE.ExtrudeGeometry(this._polygone(contour), { depth: 0.25, bevelEnabled: false }), new THREE.MeshStandardMaterial({ color: 0xd6d2c8, roughness: 0.9 }));
        dalle.rotation.x = -Math.PI / 2;
        dalle.position.y = -0.3;
        dalle.receiveShadow = true;
        this.statique.add(dalle);
        const matMur = new THREE.MeshStandardMaterial({ map: kit.SOLS.enduit([1, 1]), roughness: 0.9 });
        const matMurExt = new THREE.MeshStandardMaterial({ map: kit.SOLS.bardage([1, 1]), roughness: 0.85 });
        const portes = plan.portes || [];
        for (const mur of plan.murs || []) {
            // le mur est découpé autour des portes qui sont sur son segment
            const segments = this._decouper(mur.a, mur.b, portes.filter((p) => this._surSegment(mur.a, mur.b, p.a) && this._surSegment(mur.a, mur.b, p.b)).map((p) => [p.a, p.b]));
            const dx = mur.b[0] - mur.a[0], dz = mur.b[1] - mur.a[1];
            const longueur = Math.hypot(dx, dz);
            const nx = dz / longueur, nz = -dx / longueur; // une normale
            const versCentre = (cx - (mur.a[0] + mur.b[0]) / 2) * nx + (cz - (mur.a[1] + mur.b[1]) / 2) * nz;
            const normale = versCentre > 0 ? [-nx, -nz] : [nx, nz]; // vers l'extérieur
            for (const [a, b] of segments) {
                const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
                if (l < 0.05) {
                    continue;
                }
                const g = new THREE.Group();
                const int = new THREE.Mesh(new THREE.BoxGeometry(l, MUR_H, MUR_E), [matMur, matMur, matMur, matMur, matMurExt, matMur]);
                int.castShadow = int.receiveShadow = true;
                int.position.y = MUR_H / 2;
                const map = matMur.map.clone();
                map.repeat.set(l / 4, 1);
                map.needsUpdate = true;
                int.material = [matMur, matMur, matMur, matMur, new THREE.MeshStandardMaterial({ map: kit.SOLS.bardage([l / 2, 1]), roughness: 0.85 }), new THREE.MeshStandardMaterial({ map, roughness: 0.9 })];
                g.add(int);
                g.position.set((a[0] + b[0]) / 2, 0, (a[1] + b[1]) / 2);
                g.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]);
                g.userData.normale = normale;
                g.userData.echelle = 1;
                this.statique.add(g);
                this.murs.push(g);
            }
            // les linteaux au-dessus des portes
            for (const p of portes.filter((p) => this._surSegment(mur.a, mur.b, p.a) && this._surSegment(mur.a, mur.b, p.b))) {
                const l = Math.hypot(p.b[0] - p.a[0], p.b[1] - p.a[1]);
                const h = p.grande ? 2.8 : 2.2;
                const g = new THREE.Group();
                const linteau = new THREE.Mesh(new THREE.BoxGeometry(l, MUR_H - h, MUR_E), matMur);
                linteau.position.y = h + (MUR_H - h) / 2;
                linteau.castShadow = true;
                g.add(linteau);
                // la porte : un cadre et un vantail vitré ou un rideau métallique
                const cadre = new THREE.Mesh(new THREE.BoxGeometry(l, 0.08, MUR_E + 0.06), new THREE.MeshStandardMaterial({ color: new THREE.Color(this.accent), roughness: 0.5 }));
                cadre.position.y = h;
                g.add(cadre);
                const vantail = new THREE.Mesh(new THREE.BoxGeometry(l - 0.1, h - 0.1, 0.05),
                    p.grande ? new THREE.MeshStandardMaterial({ color: 0xb8bec4, roughness: 0.6, metalness: 0.4 }) : new THREE.MeshPhysicalMaterial({ color: 0x9fd3e3, transparent: true, opacity: 0.35, roughness: 0.1 }));
                vantail.position.y = h / 2;
                vantail.name = "vantail";
                vantail.userData.ouverture = p.grande ? "haut" : "cote";
                vantail.userData.hauteur = h;
                vantail.userData.largeur = l;
                g.add(vantail);
                g.position.set((p.a[0] + p.b[0]) / 2, 0, (p.a[1] + p.b[1]) / 2);
                g.rotation.y = -Math.atan2(p.b[1] - p.a[1], p.b[0] - p.a[0]);
                g.userData.normale = normale;
                g.userData.echelle = 1;
                g.userData.porte = p;
                this.statique.add(g);
                this.murs.push(g);
                this.objets.set(`porte:${p.nom}`, { groupe: g, genre: "porte", id: p.nom, statique: true, porte: p, vantail });
            }
        }
        // les cloisons vitrées
        const matVerre = new THREE.MeshPhysicalMaterial({ color: 0xbfe6f0, transparent: true, opacity: 0.28, roughness: 0.05, metalness: 0.0, depthWrite: false });
        const matCadre = new THREE.MeshStandardMaterial({ color: 0x3a4a56, roughness: 0.5, metalness: 0.3 });
        for (const c of plan.cloisons || []) {
            const l = Math.hypot(c.b[0] - c.a[0], c.b[1] - c.a[1]);
            const h = c.basse ? 1.2 : 2.6;
            const g = new THREE.Group();
            const pleins = this._complement(c.ouvertures || [], l);
            for (const [t0, t1] of pleins) {
                const lon = (t1 - t0) * l;
                if (lon < 0.05) {
                    continue;
                }
                const x = (t0 + t1) / 2 * l - l / 2;
                if (c.basse) {
                    const m = new THREE.Mesh(new THREE.BoxGeometry(lon, h, 0.18), new THREE.MeshStandardMaterial({ map: kit.SOLS.enduit([lon / 4, 1]), roughness: 0.9 }));
                    m.position.set(x, h / 2, 0);
                    m.castShadow = m.receiveShadow = true;
                    g.add(m);
                } else {
                    const v = new THREE.Mesh(new THREE.BoxGeometry(lon, h - 0.1, 0.04), matVerre);
                    v.position.set(x, h / 2, 0);
                    g.add(v);
                    for (const y of [0.05, h - 0.05]) {
                        const r = new THREE.Mesh(new THREE.BoxGeometry(lon, 0.06, 0.08), matCadre);
                        r.position.set(x, y, 0);
                        g.add(r);
                    }
                    for (const xx of [x - lon / 2, x + lon / 2]) {
                        const p = new THREE.Mesh(new THREE.BoxGeometry(0.06, h, 0.08), matCadre);
                        p.position.set(xx, h / 2, 0);
                        g.add(p);
                    }
                }
            }
            g.position.set((c.a[0] + c.b[0]) / 2, 0, (c.a[1] + c.b[1]) / 2);
            g.rotation.y = -Math.atan2(c.b[1] - c.a[1], c.b[0] - c.a[0]);
            this.statique.add(g);
        }
        // le logo et le nom sur la façade
        if (this.options.logo) {
            const face = (plan.murs || []).find((m) => m.a[1] === m.b[1] && m.a[1] === Math.max(...contour.map((p) => p[1])));
            if (face) {
                const x = Math.min(face.a[0], face.b[0]) + 10, z = face.a[1];
                const logo = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 1.4), new THREE.MeshBasicMaterial({ map: kit.logoTexture(this.options.logo, this.accent), transparent: true }));
                logo.position.set(x - 1.2, 2.5, z + MUR_E / 2 + 0.02);
                this.statique.add(logo);
                const nom = new THREE.Mesh(new THREE.PlaneGeometry(8, 2), new THREE.MeshBasicMaterial({ map: kit.texteTexture(this.options.nom || "", { couleur: "#1d4550", taille: 60 }), transparent: true }));
                nom.position.set(x + 3.6, 2.5, z + MUR_E / 2 + 0.02);
                this.statique.add(nom);
            }
        }
    }
    _surSegment(a, b, p) {
        const cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
        if (Math.abs(cross) > 0.05) {
            return false;
        }
        const dot = (p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1]);
        return dot >= -0.01 && dot <= (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + 0.01;
    }
    _decouper(a, b, trous) {
        const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
        const t = (p) => ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (l * l);
        const ouvertures = trous.map(([p, q]) => [Math.min(t(p), t(q)), Math.max(t(p), t(q))]);
        return this._complement(ouvertures, l).map(([t0, t1]) => [[a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0], [a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1]]);
    }
    _complement(ouvertures) {
        const tri = [...ouvertures].sort((u, v) => u[0] - v[0]);
        const pleins = [];
        let t = 0;
        for (const [t0, t1] of tri) {
            if (t0 > t) {
                pleins.push([t, t0]);
            }
            t = Math.max(t, t1);
        }
        if (t < 1) {
            pleins.push([t, 1]);
        }
        return pleins;
    }
    _exterieur(ext) {
        const { THREE, kit } = this;
        const M = kit.M;
        if (ext.route) {
            const [a, b] = ext.route;
            const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
            const route = new THREE.Mesh(new THREE.PlaneGeometry(l, 6), new THREE.MeshStandardMaterial({ map: kit.sol("enrobe", l, 6), roughness: 1 }));
            route.rotation.x = -Math.PI / 2;
            route.rotation.z = -Math.atan2(b[1] - a[1], b[0] - a[0]);
            route.position.set((a[0] + b[0]) / 2, -0.01, (a[1] + b[1]) / 2);
            route.receiveShadow = true;
            this.statique.add(route);
            for (let x = 0; x < l; x += 4) {
                const trait = new THREE.Mesh(new THREE.PlaneGeometry(2, 0.14), new THREE.MeshBasicMaterial({ color: 0xf2eee4 }));
                trait.rotation.x = -Math.PI / 2;
                trait.position.set(a[0] + x + 1, 0.0, a[1]);
                this.statique.add(trait);
            }
            this.route = { a, b };
        }
        for (const [a, b] of ext.acces || []) {
            const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
            const m = new THREE.Mesh(new THREE.PlaneGeometry(6, l + 0.5), new THREE.MeshStandardMaterial({ map: kit.sol("enrobe", 6, l), roughness: 1 }));
            m.rotation.x = -Math.PI / 2;
            m.position.set((a[0] + b[0]) / 2, -0.015, (a[1] + b[1]) / 2);
            m.receiveShadow = true;
            this.statique.add(m);
        }
        const matCloture = new THREE.MeshStandardMaterial({ color: 0x6c7883, roughness: 0.6, metalness: 0.4 });
        for (const [a, b] of ext.clotures || []) {
            const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
            const g = new THREE.Group();
            for (let x = 0; x <= l; x += 2.5) {
                const p = new THREE.Mesh(new THREE.BoxGeometry(0.08, 1.6, 0.08), matCloture);
                p.position.set(x - l / 2, 0.8, 0);
                p.castShadow = true;
                g.add(p);
            }
            for (const y of [0.5, 1.0, 1.5]) {
                const r = new THREE.Mesh(new THREE.BoxGeometry(l, 0.04, 0.04), matCloture);
                r.position.set(0, y, 0);
                g.add(r);
            }
            const grille = new THREE.Mesh(new THREE.PlaneGeometry(l, 1.5), new THREE.MeshStandardMaterial({ color: 0x8a97a3, transparent: true, opacity: 0.25, side: THREE.DoubleSide }));
            grille.position.y = 0.8;
            g.add(grille);
            g.position.set((a[0] + b[0]) / 2, 0, (a[1] + b[1]) / 2);
            g.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]);
            this.statique.add(g);
        }
        for (const [a, b] of ext.haies || []) {
            const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
            const h = M.haie({ l });
            h.position.set((a[0] + b[0]) / 2, 0, (a[1] + b[1]) / 2);
            h.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]);
            this.statique.add(h);
        }
        for (const [x, z, taille] of ext.arbres || []) {
            const a = M.arbre({ h: 3.2 + (taille || 1) * 1.6, sapin: (x * 7 + z * 3) % 5 === 0 });
            a.position.set(x, 0, z);
            a.rotation.y = (x * 13 + z * 7) % 6;
            this.statique.add(a);
        }
        // les places de parking : des bandes peintes
        for (const p of (this.plan.places || []).filter((p) => p.usage === "parking" || p.usage === "camion")) {
            const bande = new THREE.Mesh(new THREE.PlaneGeometry(p.usage === "camion" ? 3.2 : 2.6, p.usage === "camion" ? 7 : 5.2), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.0 }));
            const cadre = new THREE.LineSegments(new THREE.EdgesGeometry(bande.geometry), new THREE.LineBasicMaterial({ color: 0xf4f1ea, transparent: true, opacity: 0.8 }));
            cadre.rotation.x = -Math.PI / 2;
            cadre.rotation.z = ((p.rot || 0) * Math.PI) / 180;
            cadre.position.set(p.x, 0.0, p.z);
            this.statique.add(cadre);
        }
    }
    _objetDuPlan(o) {
        const { THREE, kit } = this;
        const params = { ...(o.params || {}) };
        if (o.type === "rack") {
            params.remplissage = params.remplissage ?? 6;
        }
        if (o.type === "cantilever") {
            params.l = params.longueur ?? params.l;
        }
        const g = kit.fabriquer(o.type, params);
        g.position.set(o.x, 0, o.z);
        g.rotation.y = ((o.rot || 0) * Math.PI) / 180;
        g.userData.plan = o;
        this.statique.add(g);
        const boite = new THREE.Box3().setFromObject(g);
        const taille = boite.getSize(new THREE.Vector3());
        const cle = `objet:${o.id}`;
        g.traverse((m) => {
            if (m.isMesh) {
                m.userData.cle = cle;
                m.userData.priorite = 1;
                this.cibles.push(m);
            }
        });
        const entree = { groupe: g, genre: this._genreObjet(o), id: o.id, nom: this._nomObjet(o), sousTitre: o.zone || "", priorite: 1, rayon: Math.max(taille.x, taille.z) / 2 + 0.3,
                         centre: boite.getCenter(new THREE.Vector3()), boite, statique: true, plan: o, taille };
        this.objets.set(cle, entree);
        if (o.type === "bureau") {
            kit.allumerEcran(g, params.ecran || "eteint");
        }
        if (o.type === "panneau" && params.texte) {
            const t = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 0.24), new THREE.MeshBasicMaterial({ map: kit.texteTexture(params.texte, { couleur: "#ffffff", taille: 54 }), transparent: true }));
            t.position.set(0, 2.17, 0.05);
            g.add(t);
        }
        if (o.type === "totem" && params.logo && this.options.logo) {
            const l = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.9), new THREE.MeshBasicMaterial({ map: kit.logoTexture(this.options.logo, this.accent), transparent: true }));
            l.position.set(0, 2.4, 0.2);
            g.add(l);
        }
        // les animations d'ambiance des objets
        if (o.type === "serveur") {
            const leds = [];
            g.traverse((m) => m.name === "led" && leds.push(m));
            this.animes.push({ statique: true, animer: (dt, t) => leds.forEach((l, i) => (l.visible = Math.sin(t * (3 + i) + i) > -0.3)) });
        }
        if (o.type === "imprimante") {
            const feuille = g.getObjectByName("feuille");
            this.animes.push({ statique: true, animer: (dt, t) => { const s = (t % 9) / 9; feuille.visible = s < 0.5; feuille.position.x = 0.2 + s * 0.6; } });
        }
        if (o.type === "soudeuse") {
            const e = kit.etincelles(40);
            e.position.set(0.3, 0, 0.4);
            e.userData.actif = false;
            g.add(e);
            entree.etincelles = e;
            this.animes.push({ statique: true, animer: (dt, t) => e.userData.animer(dt, t) });
        }
        return entree;
    }
    _genreObjet(o) {
        return { borne: "borne", bureau: "poste", rack: "rayon_fixe", gondole: "rayon_fixe", comptoir: "comptoir", etabli: "etabli" }[o.type] || "objet";
    }
    _nomObjet(o) {
        const noms = { bureau: "Poste de travail", rack: "Rayonnage", gondole: "Gondole", comptoir: "Comptoir", borne: "Badgeuse", etabli: "Établi", soudeuse: "Poste à souder",
                       machine_cafe: "Machine à café", babyfoot: "Baby-foot", ecran_mural: "Écran", serveur: "Serveur", imprimante: "Imprimante", quai: "Quai de livraison",
                       cantilever: "Tubes et barres", bobines: "Bobines de PE", prefa: "Cuves", benne: "Benne", tracteur: "Tracteur", minipelle: "Mini-pelle", chariot: "Chariot élévateur",
                       plans: "Table à plans", totem: "Totem", panneau: "Panneau", canape: "Canapé", table: "Table", armoire: "Armoire", plante: "Plante", lampadaire: "Lampadaire",
                       palette: "Palette", liasse: "Dossiers", dossiers: "Dossiers", bac: "Bac de lavage", nettoyeur: "Nettoyeur haute pression", pompe: "Pompe" };
        return noms[o.type] || o.type;
    }
    _placesVisuelles() {
        const { THREE } = this;
        this.placesGroupe = new THREE.Group();
        this.placesGroupe.visible = false;
        for (const p of this.places.values()) {
            const d = new THREE.Mesh(new THREE.CircleGeometry(0.6, 20), new THREE.MeshBasicMaterial({ color: new THREE.Color(this.accent), transparent: true, opacity: 0.35 }));
            d.rotation.x = -Math.PI / 2;
            d.position.set(p.x, 0.04, p.z);
            this.placesGroupe.add(d);
        }
        this.statique.add(this.placesGroupe);
    }

    // ------------------------------------------------------------------ la grille de navigation et A*

    _grilleNavigation() {
        const plan = this.plan;
        const [[x0, z0], [x1, z1]] = plan.exterieur?.sol || [[-8, -2], [72, 66]];
        const nx = Math.ceil((x1 - x0) / PAS), nz = Math.ceil((z1 - z0) / PAS);
        const bloque = new Uint8Array(nx * nz);
        const idx = (x, z) => Math.floor((z - z0) / PAS) * nx + Math.floor((x - x0) / PAS);
        const bloquerSegment = (a, b, epaisseur = 0.3) => {
            const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
            for (let s = 0; s <= l; s += PAS / 2) {
                const x = a[0] + (b[0] - a[0]) * (s / l || 0), z = a[1] + (b[1] - a[1]) * (s / l || 0);
                for (let dx = -epaisseur; dx <= epaisseur; dx += PAS / 2) {
                    for (let dz = -epaisseur; dz <= epaisseur; dz += PAS / 2) {
                        const i = idx(x + dx, z + dz);
                        if (i >= 0 && i < bloque.length) {
                            bloque[i] = 1;
                        }
                    }
                }
            }
        };
        const portes = plan.portes || [];
        for (const m of plan.murs || []) {
            for (const [a, b] of this._decouper(m.a, m.b, portes.filter((p) => this._surSegment(m.a, m.b, p.a) && this._surSegment(m.a, m.b, p.b)).map((p) => [p.a, p.b]))) {
                bloquerSegment(a, b, 0.3);
            }
        }
        for (const c of plan.cloisons || []) {
            const l = Math.hypot(c.b[0] - c.a[0], c.b[1] - c.a[1]);
            for (const [t0, t1] of this._complement(c.ouvertures || [], l)) {
                bloquerSegment([c.a[0] + (c.b[0] - c.a[0]) * t0, c.a[1] + (c.b[1] - c.a[1]) * t0], [c.a[0] + (c.b[0] - c.a[0]) * t1, c.a[1] + (c.b[1] - c.a[1]) * t1], 0.25);
            }
        }
        for (const [a, b] of plan.exterieur?.clotures || []) {
            bloquerSegment(a, b, 0.3);
        }
        for (const [a, b] of plan.exterieur?.haies || []) {
            bloquerSegment(a, b, 0.6);
        }
        for (const o of this.objets.values()) {
            if (o.statique && o.boite && o.genre !== "zone" && o.genre !== "porte" && !["plante", "lampadaire"].includes(o.plan?.type)) {
                const b = o.boite;
                for (let x = b.min.x - 0.2; x <= b.max.x + 0.2; x += PAS / 2) {
                    for (let z = b.min.z - 0.2; z <= b.max.z + 0.2; z += PAS / 2) {
                        const i = idx(x, z);
                        if (i >= 0 && i < bloque.length) {
                            bloque[i] = 1;
                        }
                    }
                }
            }
        }
        this.nav = { x0, z0, nx, nz, bloque, idx };
    }
    /** Le chemin au sol de a vers b (points [x, z]), par A* sur la grille ; les objets sont contournés. */
    chemin(a, b) {
        const { x0, z0, nx, nz, bloque } = this.nav;
        const cell = (p) => [Math.min(nx - 1, Math.max(0, Math.floor((p[0] - x0) / PAS))), Math.min(nz - 1, Math.max(0, Math.floor((p[1] - z0) / PAS)))];
        const [sx, sz] = cell(a), [tx, tz] = cell(b);
        const libre = (x, z) => x >= 0 && z >= 0 && x < nx && z < nz && !bloque[z * nx + x];
        // on tolère un départ ou une arrivée dans un objet (une chaise, un bureau) : on cherche la case libre la plus proche
        const proche = (x, z) => {
            if (libre(x, z)) {
                return [x, z];
            }
            for (let r = 1; r < 8; r++) {
                for (let dx = -r; dx <= r; dx++) {
                    for (let dz = -r; dz <= r; dz++) {
                        if (libre(x + dx, z + dz)) {
                            return [x + dx, z + dz];
                        }
                    }
                }
            }
            return [x, z];
        };
        const [ax, az] = proche(sx, sz), [bx, bz] = proche(tx, tz);
        const cle = (x, z) => z * nx + x;
        const ouvert = new Map([[cle(ax, az), { x: ax, z: az, g: 0, f: Math.hypot(bx - ax, bz - az), p: null }]]);
        const ferme = new Set();
        let fin = null, iterations = 0;
        while (ouvert.size && iterations++ < 40000) {
            let courant = null;
            for (const n of ouvert.values()) {
                if (!courant || n.f < courant.f) {
                    courant = n;
                }
            }
            if (courant.x === bx && courant.z === bz) {
                fin = courant;
                break;
            }
            ouvert.delete(cle(courant.x, courant.z));
            ferme.add(cle(courant.x, courant.z));
            for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]]) {
                const x = courant.x + dx, z = courant.z + dz;
                if (!libre(x, z) || ferme.has(cle(x, z))) {
                    continue;
                }
                if (dx && dz && (!libre(courant.x + dx, courant.z) || !libre(courant.x, courant.z + dz))) {
                    continue; // pas de coupe de coin
                }
                const g = courant.g + (dx && dz ? 1.414 : 1);
                const existant = ouvert.get(cle(x, z));
                if (!existant || g < existant.g) {
                    ouvert.set(cle(x, z), { x, z, g, f: g + Math.hypot(bx - x, bz - z), p: courant });
                }
            }
        }
        if (!fin) {
            return [a, b];
        }
        const points = [];
        for (let n = fin; n; n = n.p) {
            points.push([x0 + (n.x + 0.5) * PAS, z0 + (n.z + 0.5) * PAS]);
        }
        points.reverse();
        points[0] = a;
        points[points.length - 1] = b;
        // on lisse : on retire les points intermédiaires quand la ligne droite est libre
        const visible = (p, q) => {
            const l = Math.hypot(q[0] - p[0], q[1] - p[1]);
            for (let s = 0; s <= l; s += PAS / 2) {
                const [cx, cz] = cell([p[0] + (q[0] - p[0]) * (s / l || 0), p[1] + (q[1] - p[1]) * (s / l || 0)]);
                if (!libre(cx, cz)) {
                    return false;
                }
            }
            return true;
        };
        const lisse = [points[0]];
        let i = 0;
        while (i < points.length - 1) {
            let j = points.length - 1;
            while (j > i + 1 && !visible(points[i], points[j])) {
                j--;
            }
            lisse.push(points[j]);
            i = j;
        }
        return lisse;
    }

    // ------------------------------------------------------------------ les objets vivants

    /** Enregistre (ou retrouve) un objet dynamique : cliquable, avec sa fiche. */
    _objetVivant(cle, genre, id, nom, sousTitre, fabrique, meta = {}) {
        let o = this.objets.get(cle);
        if (!o) {
            const groupe = fabrique();
            groupe.traverse((m) => {
                if (m.isMesh) {
                    m.userData.cle = cle;
                    m.userData.priorite = 2;
                    this.cibles.push(m);
                }
            });
            this.dynamique.add(groupe);
            const boite = new this.THREE.Box3().setFromObject(groupe);
            const taille = boite.getSize(new this.THREE.Vector3());
            o = { groupe, genre, id, priorite: 2, rayon: Math.max(taille.x, taille.z, 1) / 2 + 0.3, taille, hauteur: taille.y };
            this.objets.set(cle, o);
        }
        Object.assign(o, { nom, sousTitre, meta });
        o.vu = this._generation;
        return o;
    }
    _retirer(cle) {
        const o = this.objets.get(cle);
        if (!o) {
            return;
        }
        this.dynamique.remove(o.groupe);
        this.cibles = this.cibles.filter((m) => m.userData.cle !== cle);
        this.objets.delete(cle);
        this.marcheurs.delete(cle);
        this.vehicules.delete(cle);
        this.animes = this.animes.filter((a) => a.cle !== cle);
        if (this.selection === cle) {
            this.deselectionner();
        }
    }
    place(cle) {
        return this.places.get(cle);
    }
    /** Une place libre d'un usage donné (la première non occupée). */
    placeLibre(usage, occupees) {
        for (const p of this.places.values()) {
            if (p.usage === usage && !occupees.has(p.cle)) {
                occupees.add(p.cle);
                return p;
            }
        }
        return null;
    }
    porte(nom) {
        const p = (this.plan.portes || []).find((p) => p.nom === nom) || (this.plan.portes || [])[0];
        return p ? [(p.a[0] + p.b[0]) / 2, (p.a[1] + p.b[1]) / 2] : [this.cam.cible.x, this.cam.cible.z];
    }
    /** Un point un peu à l'extérieur d'une porte, et un peu à l'intérieur. */
    seuil(nom, cote = 1) {
        const p = (this.plan.portes || []).find((p) => p.nom === nom);
        if (!p) {
            return this.porte(nom);
        }
        const [cx, cz] = this._centre(this.plan.contour);
        const m = [(p.a[0] + p.b[0]) / 2, (p.a[1] + p.b[1]) / 2];
        const dx = p.b[0] - p.a[0], dz = p.b[1] - p.a[1];
        const l = Math.hypot(dx, dz);
        let nx = dz / l, nz = -dx / l;
        if ((cx - m[0]) * nx + (cz - m[1]) * nz > 0) {
            nx = -nx; nz = -nz;
        }
        return [m[0] + nx * 1.2 * cote, m[1] + nz * 1.2 * cote];
    }

    /** Peuple la scène avec les données vivantes : l'équipe, les camions, les clients, les champs, l'atelier, les rayons. */
    peupler(v, premiere = false) {
        this._generation = (this._generation || 0) + 1;
        const { THREE, kit } = this;
        this.vivant = v;
        const occupees = new Set();
        for (const p of this.places.values()) {
            p.occupants = 0;
        }
        // --- l'équipe
        const postes = {};
        for (const p of v.personnes) {
            const cle = `personne:${p.id}`;
            const o = this._objetVivant(cle, "personne", p.id, p.nom, p.statut_nom, () => kit.personnage({
                tenue: p.tenue, casquette: p.role === "technicien", gilet: false, accessoire: p.role === "technicien" ? "outil" : (p.role === "comptoir" ? null : "tablette"),
                cheveuxLongs: (p.id * 7) % 3 === 0, peau: undefined }), p);
            o.groupe.userData.phase = (p.id * 1.7) % 6.28;
            const visible = !["pas_arrive", "absent", "parti", "en_route", "en_rendez_vous"].includes(p.statut);
            const dehors = ["en_intervention", "sur_chantier"].includes(p.statut);
            let cible = null, pose = "debout", orientation = 0;
            if (p.statut === "au_poste" || p.statut === "en_reunion" || p.statut === "en_pause" || p.statut === "en_visio") {
                const usage = p.statut === "en_reunion" ? "reunion" : p.statut === "en_pause" ? "pause" : "poste";
                let place = null;
                if (usage === "poste") {
                    // le poste de sa zone, dans l'ordre d'arrivée ; à défaut un poste libre n'importe où
                    const candidats = [...this.places.values()].filter((pl) => pl.usage === "poste" && pl.zone === p.zone && !occupees.has(pl.cle));
                    place = candidats[0] || this.placeLibre("poste", occupees);
                    if (place) {
                        occupees.add(place.cle);
                    }
                } else {
                    place = this.placeLibre(usage, occupees);
                }
                if (place) {
                    cible = [place.x, place.z];
                    orientation = ((place.rot || 0) * Math.PI) / 180;
                    pose = usage === "reunion" ? "assis_reunion" : usage === "pause" ? (place.cle.endsWith("3") ? "babyfoot" : "cafe")
                        : p.statut === "en_visio" ? (p.zone === "atelier" || p.zone === "accueil" ? "telephone" : "assis_reunion")
                        : (p.zone === "atelier" ? "outil" : p.zone === "accueil" ? "comptoir" : "assis_bureau");
                    if (usage === "poste") {
                        postes[place.cle] = p;
                    }
                } else {
                    cible = this.porte("entree_equipe");
                    pose = "discussion";
                }
            } else if (dehors) {
                // sur la parcelle de son intervention ou de son chantier, si elle est sur la map ; sinon invisible (parti)
                const inst = (p.tache || p.chantier || {}).installation;
                const champ = inst && this._champPour(inst);
                if (champ) {
                    const n = (champ.occupants = (champ.occupants || 0) + 1);
                    cible = [champ.x - 2 + ((n - 1) % 3) * 1.3, champ.z + 0.9 + Math.floor((n - 1) / 3) * 1.6];
                    pose = p.chantier ? (n % 2 ? "accroupi" : "outil") : "outil";
                    orientation = Math.PI / 2;
                }
            }
            o.groupe.visible = visible && !!cible;
            if (cible) {
                this._marcher(cle, o, cible, pose, orientation, premiere || !o.place);
                o.place = cible;
            }
            o.statut = p.statut;
        }
        // --- l'assistant (Mathis) à l'accueil, s'il est installé
        if (v.assistant) {
            const place = this.place("mathis");
            if (place) {
                const o = this._objetVivant("assistant", "assistant", 0, v.assistant.prenom, "Assistant Cultiveau · au téléphone et dans l'ERP", () => {
                    const g = kit.personnage({ tenue: "polo", haut: new THREE.Color(this.accent).getHex(), accessoire: "tablette", cheveux: 0x3a2b24 });
                    const badge = kit.epingle(this.accent);
                    badge.scale.setScalar(0.45);
                    badge.position.set(0, 2.1, 0);
                    badge.name = "badge";
                    g.add(badge);
                    return g;
                }, v.assistant);
                o.groupe.userData.phase = 2.4;
                o.groupe.visible = true;
                if (!o.pose3d) {
                    o.groupe.position.set(place.x, 0, place.z);
                    o.groupe.rotation.y = ((place.rot || 0) * Math.PI) / 180;
                    o.pose3d = true;
                }
                const m = this.marcheurs.get("assistant");
                if (!m) {
                    this.marcheurs.set("assistant", { cle: "assistant", o, chemin: [], i: 0, pose: "comptoir", orientation: ((place.rot || 0) * Math.PI) / 180, arrive: true });
                }
            }
        }
        // --- les camions
        for (const c of v.vehicules) {
            const cle = `camion:${c.id}`;
            const o = this._objetVivant(cle, "camion", c.id, c.nom, c.parti ? `Parti · ${c.destination || "intervention"}` : "Au dépôt", () => {
                const g = kit.M.fourgonnette({ couleur: kit.TEINTES.blanc, bande: new THREE.Color(this.accent).getHex(), galerie: true, tuyaux: true });
                g.add(kit.ombreContact(2.2));
                return g;
            }, c);
            const place = this.place(c.place) || this.placeLibre("camion", occupees);
            o.placeCle = place?.cle;
            if (place) {
                if (!o.pose3d) {
                    o.groupe.position.set(place.x, 0, place.z);
                    o.groupe.rotation.y = ((place.rot || 0) * Math.PI) / 180 + Math.PI / 2;
                    o.pose3d = true;
                }
                const etait = o.parti;
                o.parti = c.parti;
                if (!premiere && etait !== undefined && etait !== c.parti) {
                    this._conduire(cle, o, c.parti ? "sortir" : "rentrer", place);
                } else if (!this.vehicules.has(cle)) {
                    o.groupe.visible = !c.parti;
                }
            }
        }
        // --- les voitures des clients au parking
        for (const c of v.clients) {
            const cle = `client:${c.id}`;
            const o = this._objetVivant(cle, "client", c.id, c.nom, c.devis ? `${c.devis.nom} · ${c.devis.montant.toLocaleString("fr-FR")} €` : "Sur place", () => {
                const teintes = [0xd94f45, 0x2a63b0, 0x6c7883, 0xf2c230, 0x4fa83a, 0xe9e3d6];
                const g = kit.M.voiture({ couleur: teintes[c.id % teintes.length], pickup: c.type === "agriculteur" });
                g.add(kit.ombreContact(1.8));
                return g;
            }, c);
            const place = this.place(c.place) || this.placeLibre("parking", occupees);
            if (place && !o.pose3d) {
                o.groupe.position.set(place.x, 0, place.z);
                o.groupe.rotation.y = ((place.rot || 0) * Math.PI) / 180 + Math.PI / 2;
                o.pose3d = true;
            }
            // le client lui-même : à l'accueil
            const clePers = `visiteur:${c.id}`;
            const attente = this.placeLibre("attente", occupees);
            const pers = this._objetVivant(clePers, "client", c.id, c.nom, "Client sur place", () => kit.personnage({ tenue: "client", casquette: c.type === "agriculteur" ? 0x4fa83a : false }), c);
            pers.groupe.userData.phase = c.id % 6;
            if (attente) {
                this._marcher(clePers, pers, [attente.x, attente.z], "assis_detendu", ((attente.rot || 0) * Math.PI) / 180, premiere || !pers.place);
                pers.place = [attente.x, attente.z];
            }
        }
        // --- les champs : chantiers, dossiers en réalisation, parcelles en service
        const champs = [...this.places.values()].filter((p) => p.usage === "champ");
        const candidats = [];
        for (const c of v.chantiers) {
            candidats.push({ cle: `chantier:${c.id}`, genre: "chantier", id: c.id, nom: c.nom, sous: `${c.client} · ${c.etat_nom} · ${c.avancement} %`, champ: c.champ, chantier: true, installation: c.installation, meta: c });
        }
        for (const d of v.dossiers.filter((d) => d.etat === "realisation" && !candidats.some((c) => c.installation === d.id))) {
            candidats.push({ cle: `dossier:${d.id}`, genre: "dossier", id: d.id, nom: d.nom, sous: `${d.client} · ${d.etapes[d.etape].nom}`, champ: d.champ, chantier: true, installation: d.id, meta: d });
        }
        for (const p of v.parcelles) {
            candidats.push({ cle: `dossier:${p.id}`, genre: "dossier", id: p.id, nom: p.nom, sous: `${p.client} · ${p.type_nom}` + (p.echeance ? ` · ${p.echeance}` : ""), champ: p.champ, chantier: false,
                             installation: p.id, arrose: p.arrose, eau: p.eau, meta: p });
        }
        this.champs = new Map();
        candidats.slice(0, champs.length).forEach((c, i) => {
            const place = champs[i];
            this.champs.set(c.installation, place);
            const o = this._objetVivant(c.cle, c.genre, c.id, c.nom, c.sous, () => this._champ(c), c.meta);
            if (!o.pose3d) {
                o.groupe.position.set(place.x, 0, place.z);
                o.pose3d = true;
            }
            o.chantier = c.chantier;
        });
        // --- l'atelier : une pompe par intervention d'atelier, sur un établi
        for (const a of v.atelier) {
            const cle = `machine:${a.id}`;
            const o = this._objetVivant(cle, "machine", a.id, a.equipement || a.nom, `${a.client} · ${a.nature_nom}`, () => kit.M.pompe({ couleur: 0x2a63b0 }), a);
            const place = this.place(a.place);
            if (place && !o.pose3d) {
                o.groupe.position.set(place.x, 0.9, place.z);
                o.groupe.scale.setScalar(0.6);
                o.pose3d = true;
            }
        }
        // --- les livraisons : un camion fournisseur à quai
        for (const l of v.livraisons) {
            const cle = `livraison:${l.id}`;
            const o = this._objetVivant(cle, "livraison", l.id, `${l.fournisseur}`, l.recue ? `${l.nom} · reçue` : `${l.nom} · ${l.lignes} ligne(s) attendues`, () => {
                const g = kit.M.plateau({ couleur: 0xf28c28, charge: "vert" });
                g.add(kit.ombreContact(3));
                return g;
            }, l);
            const place = this.place("livraison");
            if (place && !o.pose3d) {
                o.groupe.position.set(place.x, 0, place.z);
                o.groupe.rotation.y = ((place.rot || 0) * Math.PI) / 180 + Math.PI / 2;
                o.pose3d = true;
                o.groupe.visible = !l.recue;
            }
        }
        // --- les rayons : le remplissage et le nom de la famille
        for (const s of v.stock) {
            const place = this.place(s.place);
            if (!place) {
                continue;
            }
            const rack = [...this.objets.values()].find((o) => o.statique && o.plan?.type === "rack" && Math.hypot(o.plan.x - place.x, o.plan.z - place.z) < 0.5);
            if (rack) {
                rack.nom = s.nom;
                rack.sousTitre = `${s.stock.toLocaleString("fr-FR")} en stock · ${s.mien} article(s)` + (s.bas ? ` · ${s.bas} en alerte` : "");
                rack.genre = "rayon";
                rack.id = s.id;
                rack.meta = s;
                if (!rack.rempli) {
                    const g = kit.M.rack({ remplissage: Math.max(1, Math.round(s.taux * 6)), couleur: [0x0b9bb8, 0xc89a62, 0x4fa83a, 0xf28c28, 0x8a7fd0, 0xd94f45][(s.place.slice(-1) - 1) % 6] });
                    g.position.copy(rack.groupe.position);
                    g.rotation.copy(rack.groupe.rotation);
                    this.statique.remove(rack.groupe);
                    this.cibles = this.cibles.filter((m) => m.userData.cle !== `objet:${rack.plan.id}`);
                    g.traverse((m) => { if (m.isMesh) { m.userData.cle = `objet:${rack.plan.id}`; m.userData.priorite = 1; this.cibles.push(m); } });
                    this.statique.add(g);
                    rack.groupe = g;
                    rack.rempli = true;
                    const etiquette = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.8), new THREE.MeshBasicMaterial({ map: kit.texteTexture(s.nom.toUpperCase(), { couleur: "#ffffff", taille: 56 }), transparent: true }));
                    etiquette.position.set(0, 3.55, 0);
                    const fond = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 0.5), new THREE.MeshBasicMaterial({ color: new THREE.Color(this.accent) }));
                    fond.position.set(0, 3.55, -0.01);
                    g.add(fond, etiquette);
                }
                if (s.bas && !rack.epingle) {
                    rack.epingle = kit.epingle("#f28c28");
                    rack.epingle.position.set(0, 4.2, 0);
                    rack.groupe.add(rack.epingle);
                } else if (!s.bas && rack.epingle) {
                    rack.groupe.remove(rack.epingle);
                    rack.epingle = null;
                }
            }
        }
        // --- les écrans des postes : allumés si quelqu'un y est
        for (const [cle, o] of this.objets) {
            if (o.statique && o.plan?.type === "bureau") {
                const poste = [...this.places.values()].find((p) => p.usage === "poste" && Math.hypot(p.x - o.plan.x, p.z - o.plan.z) < 1.6);
                const pers = poste && postes[poste.cle];
                kit.allumerEcran(o.groupe, pers ? (pers.statut === "en_visio" ? "visio" : (o.plan.params?.ecran || "crm")) : "verrouille");
                o.genre = "poste";
                o.id = pers ? pers.id : 0;
                o.nom = pers ? `Poste de ${pers.nom}` : "Poste libre";
                o.sousTitre = pers ? (o.plan.params?.ecran || "crm").toUpperCase() : "Verrouillé";
            }
        }
        // --- l'écran de la salle de réunion : la visio quand une réunion s'y tient
        const salleOccupee = !!(v.reunion && v.reunion.salle && v.reunion.salle.en_cours);
        for (const o of this.objets.values()) {
            if (o.statique && o.plan?.type === "ecran_mural" && o.plan.params?.salle) {
                if (o.salleOccupee !== salleOccupee) {
                    kit.allumerEcran(o.groupe, salleOccupee ? "visio" : "presentation");
                    o.salleOccupee = salleOccupee;
                }
                o.nom = (v.reunion && v.reunion.salle_nom) || "Salle de réunion";
                o.sousTitre = salleOccupee ? `Occupée · ${v.reunion.salle.en_cours.titre}` : "Libre";
                o.genre = "salle";
            }
        }
        // --- ce qui n'est plus là
        for (const [cle, o] of [...this.objets]) {
            if (!o.statique && o.vu !== this._generation) {
                this._retirer(cle);
            }
        }
        // --- l'ambiance : la soudure quand un technicien est à l'atelier, l'arrosage des parcelles
        const atelierOccupe = v.personnes.some((p) => p.zone === "atelier" && p.statut === "au_poste");
        for (const o of this.objets.values()) {
            if (o.etincelles) {
                o.etincelles.userData.actif = atelierOccupe;
            }
        }
        this._circulation();
    }
    _champPour(installation) {
        return this.champs?.get(installation);
    }
    /** La parcelle d'un champ : la culture et son matériel d'irrigation (pivot, enrouleur, goutte à goutte, aspersion), ou le chantier. */
    _champ(c) {
        const { THREE, kit } = this;
        const g = new THREE.Group();
        const M = kit.M;
        if (c.chantier) {
            g.add(M.culture({ l: 9, p: 7, nu: true }));
            const pelle = M.minipelle({ couleur: 0xf28c28 });
            pelle.position.set(-2.5, 0, 1.5);
            pelle.rotation.y = 0.6;
            g.add(pelle);
            const tubes = M.cantilever({ l: 3 });
            tubes.position.set(2.5, 0, -2);
            tubes.scale.setScalar(0.6);
            g.add(tubes);
            for (let i = 0; i < 3; i++) {
                const p = M.palette({ h: 0.2 });
                p.position.set(1.5 + i * 1.2, 0, 2.6);
                g.add(p);
            }
            const panneau = M.panneau({ couleur: 0xf28c28 });
            panneau.position.set(-4, 0, 3.2);
            g.add(panneau);
            const tranchee = new THREE.Mesh(new THREE.BoxGeometry(7, 0.05, 0.5), new THREE.MeshStandardMaterial({ color: 0x6b4a2c, roughness: 1 }));
            tranchee.position.set(0, 0.14, 0);
            g.add(tranchee);
            return g;
        }
        if (c.champ === "pivot") {
            g.add(M.culture({ l: 10, p: 8, genre: "mais" }));
            const pivot = M.pivot({ longueur: 4.2 });
            pivot.position.set(0, 0.12, 0);
            g.add(pivot);
            g.userData.bras = pivot.getObjectByName("bras");
            if (c.arrose) {
                const j = kit.jet({ portee: 4, hauteur: 2.2, tourne: true, n: 70 });
                j.position.set(0, 0.5, 0);
                g.add(j);
                g.userData.jet = j;
            }
        } else if (c.champ === "enrouleur") {
            g.add(M.culture({ l: 10, p: 8, genre: "mais" }));
            const e = M.enrouleur({ tuyau: 3.5 });
            e.position.set(-3.5, 0.12, 2.5);
            g.add(e);
            g.userData.tambour = e.getObjectByName("tambour");
            const canon = M.canon();
            canon.position.set(2.5, 0.12, -1);
            g.add(canon);
            g.userData.canon = canon.getObjectByName("canon");
            if (c.arrose) {
                const j = kit.jet({ portee: 5, hauteur: 1.6, secteur: 0.9, n: 60 });
                j.position.set(2.5, 1.0, -1);
                g.add(j);
                g.userData.jet = j;
            }
        } else if (c.champ === "goutte") {
            g.add(M.culture({ l: 10, p: 8, genre: (c.id % 2) ? "vigne" : "verger", goutte: true }));
        } else {
            g.add(kit.modeles.aspersion({ l: 10, p: 8 }));
            if (c.arrose) {
                for (const [x, z] of [[-3, -2], [3, 2]]) {
                    const j = kit.jet({ portee: 2.2, hauteur: 0.6, tourne: true, n: 30 });
                    j.position.set(x, 0.4, z);
                    g.add(j);
                }
                g.userData.jets = true;
            }
        }
        if (c.eau && c.eau.etat && ["sec", "stress", "deficit"].includes(c.eau.etat)) {
            const e = kit.epingle("#d94f45");
            e.position.set(0, 3.2, 0);
            g.add(e);
        }
        g.add(kit.ombreContact(0.01));
        return g;
    }

    // ------------------------------------------------------------------ les marcheurs et les véhicules

    _marcher(cle, o, cible, pose, orientation, immediat) {
        const g = o.groupe;
        const depart = [g.position.x, g.position.z];
        if (immediat || !g.visible) {
            g.position.set(cible[0], 0, cible[1]);
            g.rotation.y = orientation;
            g.visible = true;
            this.marcheurs.set(cle, { cle, o, chemin: [], i: 0, pose, orientation, arrive: true });
            return;
        }
        if (Math.hypot(cible[0] - depart[0], cible[1] - depart[1]) < 0.3) {
            const m = this.marcheurs.get(cle);
            if (m) {
                m.pose = pose;
                m.orientation = orientation;
            }
            return;
        }
        this.marcheurs.set(cle, { cle, o, chemin: this.chemin(depart, cible), i: 1, pose, orientation, arrive: false, vitesse: 1.35 });
    }
    /** Fait marcher une personne d'une porte vers sa place (une arrivée), ou de sa place vers une porte (un départ). */
    entrer(cle, porte = "entree_equipe", rappel = null) {
        const o = this.objets.get(cle);
        if (!o) {
            return;
        }
        const m = this.marcheurs.get(cle);
        const cible = o.place || [o.groupe.position.x, o.groupe.position.z];
        const [ex, ez] = this.seuil(porte, 1);
        o.groupe.position.set(ex, 0, ez);
        o.groupe.visible = true;
        const chemin = [[ex, ez], this.seuil(porte, -1), ...this.chemin(this.seuil(porte, -1), cible).slice(1)];
        this.marcheurs.set(cle, { cle, o, chemin, i: 1, pose: m?.pose || "debout", orientation: m?.orientation || 0, arrive: false, vitesse: 1.4, rappel, porte });
        this._ouvrirPorte(porte);
    }
    sortir(cle, porte = "entree_equipe", rappel = null) {
        const o = this.objets.get(cle);
        if (!o || !o.groupe.visible) {
            rappel?.();
            return;
        }
        const depart = [o.groupe.position.x, o.groupe.position.z];
        const chemin = [...this.chemin(depart, this.seuil(porte, -1)), this.seuil(porte, 1)];
        this.marcheurs.set(cle, { cle, o, chemin, i: 1, pose: "debout", orientation: 0, arrive: false, vitesse: 1.4, porte, rappel: () => { o.groupe.visible = false; rappel?.(); } });
        this._ouvrirPorte(porte);
    }
    /** Un détour : marcher jusqu'à un point (la badgeuse), puis continuer vers la place. */
    passerPar(cle, point, rappelPoint, porte = "entree_equipe") {
        const o = this.objets.get(cle);
        if (!o) {
            return;
        }
        const [ex, ez] = this.seuil(porte, 1);
        o.groupe.position.set(ex, 0, ez);
        o.groupe.visible = true;
        const m = this.marcheurs.get(cle);
        const cible = o.place || point;
        const chemin = [[ex, ez], this.seuil(porte, -1), ...this.chemin(this.seuil(porte, -1), point).slice(1)];
        this.marcheurs.set(cle, { cle, o, chemin, i: 1, pose: "debout", orientation: 0, arrive: false, vitesse: 1.4, porte, rappel: () => {
            rappelPoint?.();
            this.marcheurs.set(cle, { cle, o, chemin: this.chemin(point, cible), i: 1, pose: m?.pose || "assis_bureau", orientation: m?.orientation || 0, arrive: false, vitesse: 1.3, attente: 1.2 });
        } });
        this._ouvrirPorte(porte);
    }
    /** L'assistant décroche : la pose « téléphone » pendant quelques secondes, puis retour au comptoir. */
    assistantDecroche(secondes = 25) {
        const m = this.marcheurs.get("assistant");
        if (!m) {
            return;
        }
        m.pose = "telephone";
        clearTimeout(this._assistantMinuterie);
        this._assistantMinuterie = setTimeout(() => { m.pose = "comptoir"; }, secondes * 1000);
    }
    _ouvrirPorte(nom) {
        const p = this.objets.get(`porte:${nom}`);
        if (p) {
            p.ouverte = this.temps + 3.5;
        }
    }
    _conduire(cle, o, sens, place) {
        const { THREE } = this;
        const g = o.groupe;
        const route = this.route || { a: [-6, 44.5], b: [70, 44.5] };
        const acces = (this.plan.exterieur?.acces || [])[1] || (this.plan.exterieur?.acces || [])[0] || [[place.x, place.z + 8], [place.x, route.a[1]]];
        const garage = new THREE.Vector3(place.x, 0, place.z);
        const sortieCour = new THREE.Vector3(acces[0][0], 0, acces[0][1] - 1);
        const bordRoute = new THREE.Vector3(acces[1][0], 0, acces[1][1] - 1.6);
        const loin = new THREE.Vector3(route.b[0] + 6, 0, route.a[1] - 1.6);
        const points = sens === "sortir" ? [garage, new THREE.Vector3(place.x, 0, place.z + 4), sortieCour, bordRoute, loin]
            : [loin, bordRoute, sortieCour, new THREE.Vector3(place.x, 0, place.z + 4), garage];
        const courbe = new THREE.CatmullRomCurve3(points, false, "centripetal");
        g.visible = true;
        this.vehicules.set(cle, { cle, o, courbe, s: 0, longueur: courbe.getLength(), vitesse: 0, vmax: 7, recule: sens === "rentrer", rappel: () => { if (sens === "sortir") { g.visible = false; } } });
    }
    /** Un camion fournisseur qui arrive de la route, se gare à quai, puis repart. */
    livrer(cle, rappel) {
        const { THREE, kit } = this;
        const o = this._objetVivant(cle, "livraison", 0, "Livraison", "Fournisseur à quai", () => { const g = kit.M.plateau({ couleur: 0xf28c28, charge: "vert" }); g.add(kit.ombreContact(3)); return g; }, {});
        const place = this.place("livraison") || { x: 46, z: 25.5, rot: 90 };
        const route = this.route || { a: [-6, 44.5], b: [70, 44.5] };
        const acces = (this.plan.exterieur?.acces || [])[1] || [[place.x, place.z + 8], [place.x, route.a[1]]];
        const points = [new THREE.Vector3(route.a[0] - 4, 0, route.a[1] + 1.6), new THREE.Vector3(acces[1][0] - 6, 0, route.a[1] + 1.6), new THREE.Vector3(acces[1][0], 0, acces[1][1] - 3),
                        new THREE.Vector3(acces[0][0], 0, acces[0][1] - 3), new THREE.Vector3(place.x + 1, 0, place.z + 6), new THREE.Vector3(place.x, 0, place.z)];
        const courbe = new THREE.CatmullRomCurve3(points, false, "centripetal");
        o.groupe.visible = true;
        this.vehicules.set(cle, { cle, o, courbe, s: 0, longueur: courbe.getLength(), vitesse: 0, vmax: 8, rappel: () => {
            rappel?.();
            setTimeout(() => {
                const retour = new THREE.CatmullRomCurve3([...points].reverse(), false, "centripetal");
                this.vehicules.set(cle, { cle, o, courbe: retour, s: 0, longueur: retour.getLength(), vitesse: 0, vmax: 7, recule: true, rappel: () => this._retirer(cle) });
            }, 9000);
        } });
    }
    _circulation() {
        const { THREE, kit } = this;
        if (this.trafic || !this.route) {
            return;
        }
        this.trafic = [];
        const { a, b } = this.route;
        for (let i = 0; i < 3; i++) {
            const v = i === 1 ? kit.M.utilitaire({ couleur: 0xe9e3d6 }) : kit.M.voiture({ couleur: [0x6c7883, 0x2a63b0, 0xd94f45][i] });
            v.add(kit.ombreContact(1.8));
            this.dynamique.add(v);
            const sens = i % 2 ? -1 : 1;
            this.trafic.push({ g: v, x: a[0] + ((b[0] - a[0]) * (i + 0.3)) / 3, z: a[1] + sens * 1.6, sens, v: 6 + i * 1.5 });
        }
    }

    // ------------------------------------------------------------------ l'image

    frame(dt) {
        let reste = Math.min(dt, 0.5);
        while (reste > 0) {
            const pas = Math.min(0.05, reste);
            reste -= pas;
            this._simuler(pas);
        }
        this._animerCamera(Math.min(dt, 0.05));
        this._animerMarqueurs(this.temps);
        this._placerEtiquettes();
        this.renderer.render(this.scene, this.camera);
    }
    _simuler(dt) {
        this.temps += dt;
        const t = this.temps;
        const { THREE, kit } = this;
        // les marcheurs
        for (const m of this.marcheurs.values()) {
            const g = m.o.groupe;
            if (m.attente > 0) {
                m.attente -= dt;
                kit.poser(g, "debout", t, 0.15);
                continue;
            }
            if (!m.arrive && m.chemin.length > m.i) {
                const [tx, tz] = m.chemin[m.i];
                const dx = tx - g.position.x, dz = tz - g.position.z;
                const d = Math.hypot(dx, dz);
                const pas = (m.vitesse || 1.3) * dt;
                const cap = Math.atan2(dx, dz);
                g.rotation.y += angleVers(g.rotation.y, cap) * Math.min(1, dt * 9);
                if (d <= pas) {
                    g.position.set(tx, 0, tz);
                    m.i++;
                    if (m.i >= m.chemin.length) {
                        m.arrive = true;
                        m.rappel?.();
                    }
                } else {
                    g.position.x += (dx / d) * pas;
                    g.position.z += (dz / d) * pas;
                }
                kit.poser(g, "marche", t, 0.25);
            } else {
                g.rotation.y += angleVers(g.rotation.y, m.orientation) * Math.min(1, dt * 6);
                kit.poser(g, m.pose, t, 0.12);
            }
        }
        // les véhicules
        for (const v of [...this.vehicules.values()]) {
            const g = v.o.groupe;
            const reste = v.longueur - v.s;
            v.vitesse = Math.min(v.vmax, v.vitesse + 4 * dt, Math.max(1.2, Math.sqrt(2 * 3 * reste)));
            v.s += v.vitesse * dt;
            const u = Math.min(1, v.s / v.longueur);
            const p = v.courbe.getPointAt(u);
            const tangente = v.courbe.getTangentAt(Math.min(0.999, u));
            g.position.copy(p);
            const cap = Math.atan2(tangente.x, tangente.z) + (v.recule ? Math.PI : 0) - Math.PI / 2;
            g.rotation.y += angleVers(g.rotation.y, cap) * Math.min(1, dt * 6);
            g.traverse((r) => { if (r.name === "roue") { r.rotation.z -= (v.vitesse * dt) / (r.userData.rayon || 0.4) * (v.recule ? -1 : 1); } });
            if (u >= 1) {
                this.vehicules.delete(v.cle);
                v.rappel?.();
            }
        }
        // la circulation de fond
        for (const c of this.trafic || []) {
            c.x += c.sens * c.v * dt;
            const { a, b } = this.route;
            if (c.x > b[0] + 10) { c.x = a[0] - 10; }
            if (c.x < a[0] - 10) { c.x = b[0] + 10; }
            c.g.position.set(c.x, 0, c.z);
            c.g.rotation.y = c.sens > 0 ? 0 : Math.PI;
            c.g.traverse((r) => { if (r.name === "roue") { r.rotation.z -= (c.v * dt) / (r.userData.rayon || 0.35); } });
        }
        // les objets animés
        for (const a of this.animes) {
            a.animer(dt, t);
        }
        for (const o of this.objets.values()) {
            const u = o.groupe.userData;
            if (u.bras) { u.bras.rotation.y += dt * 0.08; }
            if (u.tambour) { u.tambour.rotation.z += dt * 0.5; }
            if (u.canon) { u.canon.rotation.y = Math.sin(t * 0.8) * 0.9; }
            if (u.jet) { u.jet.userData.animer(dt, t); }
            if (u.jets) { o.groupe.traverse((j) => j.userData.animer && j.userData.animer(dt, t)); }
            if (o.epingle) { o.epingle.position.y = 4.2 + Math.sin(t * 2) * 0.12; o.epingle.rotation.y = t * 0.8; }
            if (o.genre === "assistant") { const b = o.groupe.getObjectByName("badge"); if (b) { b.position.y = 2.1 + Math.sin(t * 2.2) * 0.06; b.rotation.y = t; } }
            if (o.genre === "porte") {
                const ouverte = o.ouverte && o.ouverte > t;
                const v = o.vantail;
                const cible = ouverte ? 1 : 0;
                v.userData.k = lerp(v.userData.k || 0, cible, Math.min(1, dt * 4));
                if (v.userData.ouverture === "haut") {
                    v.position.y = v.userData.hauteur / 2 + v.userData.k * v.userData.hauteur * 0.9;
                } else {
                    v.position.x = -v.userData.k * v.userData.largeur * 0.9;
                }
            }
        }
        for (const o of this.objets.values()) {
            if (o.groupe.userData.epingle) { o.groupe.rotation.y = t; }
        }
        // les murs côté caméra se baissent (maison de poupée)
        const dirCam = new THREE.Vector3().subVectors(this.camera.position, this.cam.cible).setY(0).normalize();
        for (const m of this.murs) {
            const [nx, nz] = m.userData.normale;
            const face = nx * dirCam.x + nz * dirCam.z;
            const cible = face > 0.15 ? MUR_BAS / MUR_H : 1;
            m.userData.echelle = lerp(m.userData.echelle, cible, Math.min(1, dt * 5));
            m.scale.y = m.userData.echelle;
        }
    }

    // ------------------------------------------------------------------ la caméra

    _appliquerCamera() {
        const c = this.cam;
        c.polaire = Math.min(POLAIRE[1], Math.max(POLAIRE[0], c.polaire));
        c.distance = Math.min(DISTANCE[1], Math.max(DISTANCE[0], c.distance));
        const x = c.cible.x + c.distance * Math.sin(c.polaire) * Math.sin(c.azimut);
        const z = c.cible.z + c.distance * Math.sin(c.polaire) * Math.cos(c.azimut);
        const y = c.cible.y + c.distance * Math.cos(c.polaire);
        this.camera.position.set(x, y, z);
        this.camera.lookAt(c.cible);
    }
    _animerCamera(dt) {
        const c = this.cam;
        if (this.vol) {
            const v = this.vol;
            // le temps réel, pas le pas de temps borné : un vol dure ce qu'il doit durer même quand l'image est lente
            v.t = Math.min(1, (performance.now() - v.debut) / 1000 / v.duree);
            const k = ease(v.t);
            c.cible.lerpVectors(v.de.cible, v.vers.cible, k);
            c.distance = lerp(v.de.distance, v.vers.distance, k);
            c.azimut = lerp(v.de.azimut, v.vers.azimut, k);
            c.polaire = lerp(v.de.polaire, v.vers.polaire, k);
            if (v.t >= 1) {
                const fin = v.rappel;
                this.vol = null;
                fin?.();
            }
        } else if (this.visite) {
            c.azimut += dt * 0.08;
            if (this.visite.cible) {
                c.cible.lerp(this.visite.cible.groupe.position, Math.min(1, dt * 3));
            }
        } else {
            if (this.suivi) {
                const o = this.objets.get(this.suivi);
                if (o) {
                    c.cible.lerp(new this.THREE.Vector3(o.groupe.position.x, 0, o.groupe.position.z), Math.min(1, dt * 4));
                }
            }
            // l'amortissement des gestes
            const a = Math.pow(0.075, dt * 10);
            c.cible.x += c.vel.x; c.cible.z += c.vel.z; c.azimut += c.vel.azimut; c.polaire += c.vel.polaire; c.distance *= 1 + c.vel.distance;
            c.vel.x *= a; c.vel.z *= a; c.vel.azimut *= a; c.vel.polaire *= a; c.vel.distance *= a;
        }
        this._appliquerCamera();
    }
    voler(vers, duree = 1.25, rappel = null) {
        const c = this.cam;
        this.vol = { t: 0, duree, debut: performance.now(), de: { cible: c.cible.clone(), distance: c.distance, azimut: c.azimut, polaire: c.polaire },
                     vers: { cible: vers.cible ? vers.cible.clone() : c.cible.clone(), distance: vers.distance ?? c.distance, azimut: vers.azimut ?? c.azimut, polaire: vers.polaire ?? c.polaire }, rappel };
        c.vel = { x: 0, z: 0, azimut: 0, polaire: 0, distance: 0 };
    }
    intro(rappel) {
        const v = this.vue;
        this.cam.cible.copy(v.cible);
        this.cam.distance = 190;
        this.cam.polaire = 0.3;
        this.cam.azimut = v.azimut - 0.8;
        this._appliquerCamera();
        this.voler({ cible: v.cible, distance: v.distance, azimut: v.azimut, polaire: v.polaire }, 3, rappel);
    }
    vueEnsemble() {
        this.suivi = null;
        this.voler({ cible: this.vue.cible, distance: this.vue.distance, polaire: this.vue.polaire }, 1.1);
    }
    volerVers(cle, decalage = 0) {
        const o = this.objets.get(cle);
        if (!o || !o.groupe.visible) {
            return false;
        }
        const taille = o.rayon * 2;
        const distance = Math.min(70, Math.max(26, taille * 3.2 + (o.genre === "zone" ? 10 : 0)));
        const centre = o.centre ? o.centre.clone().setY(0) : new this.THREE.Vector3(o.groupe.position.x, 0, o.groupe.position.z);
        // on garde l'objet un peu à gauche quand une fiche s'ouvre à droite
        if (decalage) {
            const droite = new this.THREE.Vector3(Math.cos(this.cam.azimut), 0, -Math.sin(this.cam.azimut));
            centre.addScaledVector(droite, decalage * distance * 0.12);
        }
        this.voler({ cible: centre, distance, polaire: Math.min(this.cam.polaire, 0.95) }, 1.25);
        return true;
    }
    tourner(sens) {
        this.voler({ azimut: this.cam.azimut + (sens * Math.PI) / 4 }, 0.6);
    }
    zoomer(facteur) {
        this.voler({ distance: this.cam.distance * facteur }, 0.35);
    }
    suivre(cle) {
        this.suivi = this.suivi === cle ? null : cle;
        return this.suivi;
    }
    /** La visite guidée : des plans enchaînés, chacun ~5,5 s, avec une lente rotation. */
    demarrerVisite(plans, surPlan, fin) {
        this.arreterVisite();
        this.visite = { plans, i: -1, surPlan, fin };
        this._planSuivant();
    }
    _planSuivant() {
        const v = this.visite;
        if (!v) {
            return;
        }
        v.i++;
        if (v.i >= v.plans.length) {
            this.arreterVisite(true);
            return;
        }
        const plan = v.plans[v.i];
        const o = plan.cle ? this.objets.get(plan.cle) : null;
        v.cible = o && !o.statique ? o : null;
        const cible = o ? (o.centre ? o.centre.clone().setY(0) : new this.THREE.Vector3(o.groupe.position.x, 0, o.groupe.position.z)) : this.vue.cible.clone();
        const distance = plan.distance ?? (o ? Math.min(70, Math.max(26, o.rayon * 2 * 3.2)) : this.vue.distance);
        this.voler({ cible, distance, polaire: plan.polaire ?? 0.8 }, 1.6, () => {
            this.visite && (this.visite.minuterie = setTimeout(() => this._planSuivant(), (plan.duree ?? 5.5) * 1000));
        });
        v.surPlan?.(plan, v.i, v.plans.length);
    }
    arreterVisite(finie = false) {
        if (!this.visite) {
            return;
        }
        clearTimeout(this.visite.minuterie);
        const fin = this.visite.fin;
        this.visite = null;
        fin?.(finie);
    }

    // ------------------------------------------------------------------ la sélection, le survol, les étiquettes

    _ndc(ev) {
        const r = this.renderer.domElement.getBoundingClientRect();
        return new this.THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    }
    auSol(ev) {
        this.raycaster.setFromCamera(this._ndc(ev), this.camera);
        const p = new this.THREE.Vector3();
        return this.raycaster.ray.intersectPlane(this.plan3d, p) ? p : null;
    }
    viser(ev) {
        this.raycaster.setFromCamera(this._ndc(ev), this.camera);
        const hits = this.raycaster.intersectObjects(this.cibles, false);
        let meilleur = null;
        for (const h of hits) {
            const cle = h.object.userData.cle;
            const o = this.objets.get(cle);
            if (!o) {
                continue;
            }
            const priorite = h.object.userData.priorite || 0;
            if (!meilleur || priorite > meilleur.priorite) {
                meilleur = { cle, o, priorite, point: h.point };
            }
            if (priorite >= 2) {
                break;
            }
        }
        return meilleur;
    }
    selectionner(cle, voler = true) {
        const o = this.objets.get(cle);
        if (!o) {
            return null;
        }
        this.selection = cle;
        const visible = o.groupe.visible;
        this.marqueurs.crochets.visible = visible && o.genre !== "zone";
        this.marqueurs.halo.visible = visible;
        if (voler && visible) {
            this.volerVers(cle, 1);
        }
        this.options.onSelection?.(cle, o, visible);
        return o;
    }
    deselectionner() {
        this.selection = null;
        this.marqueurs.crochets.visible = this.marqueurs.halo.visible = false;
        this.suivi = null;
        this.options.onSelection?.(null, null);
    }
    _animerMarqueurs(t) {
        const o = this.selection && this.objets.get(this.selection);
        if (!o) {
            return;
        }
        const boite = new this.THREE.Box3().setFromObject(o.groupe);
        if (boite.isEmpty()) {
            return;
        }
        const centre = boite.getCenter(new this.THREE.Vector3());
        const taille = boite.getSize(new this.THREE.Vector3());
        const pulse = 1 + Math.sin(t * 4) * 0.04;
        const c = this.marqueurs.crochets;
        c.position.copy(centre);
        for (const coin of c.children) {
            const [sx, sy, sz] = coin.userData.signe;
            coin.position.set((sx * taille.x * pulse) / 2, (sy * taille.y * pulse) / 2, (sz * taille.z * pulse) / 2);
        }
        const h = this.marqueurs.halo;
        const r = Math.max(taille.x, taille.z) * 1.4 + 0.6;
        h.scale.set(r, r, 1);
        h.position.set(centre.x, 0.03, centre.z);
        h.material.opacity = 0.8 + Math.sin(t * 3) * 0.2;
    }
    /** La position écran d'un point du monde (ou null derrière la caméra). */
    projeter(v3) {
        const p = v3.clone().project(this.camera);
        if (p.z > 1) {
            return null;
        }
        return { x: ((p.x + 1) / 2) * this.taille.w, y: ((1 - p.y) / 2) * this.taille.h };
    }
    /** Une étiquette HTML projetée, repositionnée à chaque image. */
    etiquette(cle, html, classe = "", ancre = null) {
        let e = this.etiquettes.get(cle);
        if (!e) {
            const el = document.createElement("div");
            this.calque.appendChild(el);
            e = { el, cle };
            this.etiquettes.set(cle, e);
        }
        e.el.className = `o_cv_etiquette ${classe}`;
        if (e.html !== html) {
            e.el.innerHTML = html;
            e.html = html;
        }
        e.ancre = ancre;
        return e;
    }
    retirerEtiquette(cle) {
        const e = this.etiquettes.get(cle);
        if (e) {
            e.el.remove();
            this.etiquettes.delete(cle);
        }
    }
    _placerEtiquettes() {
        for (const e of this.etiquettes.values()) {
            const o = this.objets.get(e.cle.replace(/^(survol|selection):/, ""));
            let point = e.ancre;
            if (!point && o) {
                const boite = new this.THREE.Box3().setFromObject(o.groupe);
                point = boite.isEmpty() ? o.groupe.position.clone() : new this.THREE.Vector3((boite.min.x + boite.max.x) / 2, boite.max.y + 0.3, (boite.min.z + boite.max.z) / 2);
            }
            const p = point && this.projeter(point);
            if (!p) {
                e.el.style.display = "none";
                continue;
            }
            e.el.style.display = "";
            e.el.style.transform = `translate(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px)`;
        }
    }

    // ------------------------------------------------------------------ les gestes

    _ecouter(canvas) {
        const p = this.pointeur;
        canvas.addEventListener("contextmenu", (ev) => ev.preventDefault());
        canvas.addEventListener("pointerdown", (ev) => {
            canvas.setPointerCapture(ev.pointerId);
            p.bouton = ev.button;
            p.x = ev.clientX; p.y = ev.clientY; p.deplace = 0;
            p.debut = { x: ev.clientX, y: ev.clientY, sol: this.auSol(ev), ctrl: ev.ctrlKey || ev.metaKey };
            if (this.edition && ev.button === 0) {
                const vise = this.viser(ev);
                if (vise && vise.o.statique && vise.o.plan) {
                    p.glisse = { cle: vise.cle, o: vise.o, dx: vise.o.groupe.position.x - (p.debut.sol?.x || 0), dz: vise.o.groupe.position.z - (p.debut.sol?.z || 0) };
                    this.selectionner(vise.cle, false);
                }
            }
            this.arreterVisite();
        });
        canvas.addEventListener("pointermove", (ev) => {
            if (p.bouton < 0) {
                const vise = this.viser(ev);
                const cle = vise?.cle || null;
                if (cle !== this.survol) {
                    this.survol = cle;
                    canvas.style.cursor = cle ? "pointer" : "grab";
                    this.options.onSurvol?.(cle, vise?.o || null);
                }
                return;
            }
            const dx = ev.clientX - p.x, dy = ev.clientY - p.y;
            p.x = ev.clientX; p.y = ev.clientY;
            p.deplace += Math.abs(dx) + Math.abs(dy);
            if (p.glisse) {
                const sol = this.auSol(ev);
                if (sol) {
                    const x = Math.round((sol.x + p.glisse.dx) / PAS) * PAS, z = Math.round((sol.z + p.glisse.dz) / PAS) * PAS;
                    this.deplacerObjet(p.glisse.o, x, z);
                }
                return;
            }
            this.vol = null;
            this.suivi = null;
            const c = this.cam;
            if (p.bouton === 2 || p.debut?.ctrl) {
                c.vel.azimut = -dx * 0.004;
                c.vel.polaire = -dy * 0.003;
            } else {
                // déplacer la carte : le point du sol sous le pointeur reste sous le pointeur
                const avant = p.debut?.sol;
                const apres = this.auSol(ev);
                if (avant && apres) {
                    c.cible.x += avant.x - apres.x;
                    c.cible.z += avant.z - apres.z;
                    c.vel.x = (avant.x - apres.x) * 0.15;
                    c.vel.z = (avant.z - apres.z) * 0.15;
                    this._appliquerCamera();
                    p.debut.sol = this.auSol(ev);
                }
            }
        });
        const fin = (ev) => {
            if (p.bouton < 0) {
                return;
            }
            const clic = p.deplace < 5;
            const glisse = p.glisse;
            p.bouton = -1;
            p.glisse = null;
            if (glisse) {
                this.options.onObjetDeplace?.(glisse.o);
                return;
            }
            if (clic && ev.button === 0) {
                const vise = this.viser(ev);
                if (vise) {
                    this.selectionner(vise.cle, !this.edition);
                } else {
                    this.deselectionner();
                    this.options.onClicVide?.(this.auSol(ev));
                }
            }
        };
        canvas.addEventListener("pointerup", fin);
        canvas.addEventListener("pointercancel", fin);
        canvas.addEventListener("wheel", (ev) => {
            ev.preventDefault();
            this.vol = null;
            this.cam.vel.distance += ev.deltaY > 0 ? 0.03 : -0.03;
        }, { passive: false });
        document.addEventListener("visibilitychange", () => { this.enPause = document.hidden; });
    }

    // ------------------------------------------------------------------ l'éditeur de plan

    modeEdition(actif) {
        this.edition = actif;
        this.placesGroupe.visible = actif;
        if (!actif) {
            this.deselectionner();
        }
    }
    deplacerObjet(o, x, z) {
        o.groupe.position.set(x, 0, z);
        o.plan.x = x;
        o.plan.z = z;
        o.boite = new this.THREE.Box3().setFromObject(o.groupe);
        o.centre = o.boite.getCenter(new this.THREE.Vector3());
    }
    tournerObjet(cle, pas = 15) {
        const o = this.objets.get(cle);
        if (!o || !o.plan) {
            return;
        }
        o.plan.rot = ((o.plan.rot || 0) + pas + 360) % 360;
        o.groupe.rotation.y = (o.plan.rot * Math.PI) / 180;
        o.boite = new this.THREE.Box3().setFromObject(o.groupe);
    }
    ajouterObjet(type, x, z) {
        const id = `${type}-${Date.now().toString(36)}`;
        const o = { id, type, x: Math.round(x / PAS) * PAS, z: Math.round(z / PAS) * PAS, rot: 0, zone: null, params: {}, entite: null };
        this.plan.objets.push(o);
        const entree = this._objetDuPlan(o);
        this.selectionner(`objet:${id}`, false);
        return entree;
    }
    supprimerObjet(cle) {
        const o = this.objets.get(cle);
        if (!o || !o.plan) {
            return;
        }
        this.plan.objets = this.plan.objets.filter((p) => p.id !== o.plan.id);
        this.statique.remove(o.groupe);
        this.cibles = this.cibles.filter((m) => m.userData.cle !== cle);
        this.objets.delete(cle);
        this.deselectionner();
    }
    lierObjet(cle, entite) {
        const o = this.objets.get(cle);
        if (o?.plan) {
            o.plan.entite = entite;
        }
    }
    etatCamera() {
        const c = this.cam;
        return { cible: [c.cible.x, c.cible.z], distance: c.distance, azimut: c.azimut, polaire: c.polaire, selection: this.selection, quand: Date.now() };
    }
    restaurerCamera(e) {
        this.cam.cible.set(e.cible[0], 0, e.cible[1]);
        this.cam.distance = e.distance;
        this.cam.azimut = e.azimut;
        this.cam.polaire = e.polaire;
        this._appliquerCamera();
    }
    planCourant() {
        return JSON.parse(JSON.stringify({ ...this.plan, camera: { ...this.plan.camera, azimut: +this.cam.azimut.toFixed(3), polaire: +this.cam.polaire.toFixed(3) } }));
    }
    chargerPlan(plan) {
        this.construire(plan);
        if (this.vivant) {
            for (const [cle] of [...this.objets]) {
                if (!this.objets.get(cle).statique) {
                    this._retirer(cle);
                }
            }
            this.trafic = null;
            this.peupler(this.vivant, true);
        }
    }
}
