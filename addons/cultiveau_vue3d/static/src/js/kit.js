/** @odoo-module **/
// Le kit de la Map vivante : ce que la bibliothèque des modèles ne sait pas encore faire. Des personnages articulés qui marchent,
// s'assoient, boivent un café ; des textures procédurales dessinées en canvas (parquet, carrelage, béton, enduit, marquages,
// textes peints au sol) ; des écrans d'ordinateur dont l'image dit l'application ouverte ; des épingles, des ombres de contact,
// des étincelles et des jets d'arrosage. Tout est procédural : rien n'est téléchargé.
import { TEINTES, bibliotheque } from "./modeles";

const T = TEINTES;
const PEAUX = [0xf0c3a3, 0xe8b08a, 0xc68c5a, 0x9a6b43, 0x6d4a2f, 0xf6d4bb];
const CHEVEUX = [0x4a3527, 0x1f1a17, 0xb98a4d, 0x8c5a3c, 0xd9d2c5, 0x3a2b24];
const TENUES = {
    chemise: [[0x9fd3e3, 0xffffff, 0xe9e3d6, 0x1d4550], T.anthracite],
    polo: [[0x0b9bb8, 0x2a63b0, 0x4fa83a], T.anthracite],
    travail: [[0x2a63b0, 0x3a4a56, 0xf28c28], 0x3a4a56],
    client: [[0x6c7883, 0x8a7fd0, 0xd27a97, 0x4fa83a, 0xc89a62], 0x2c3a43],
    livreur: [[0xf2c230], 0x2c3a43],
};

export function creerKit(THREE) {
    const base = bibliotheque(THREE);
    const { M, mat, bloc, cyl, boule } = base;
    const groupe = () => new THREE.Group();
    const textures = new Map();

    // ------------------------------------------------------------------ les textures en canvas

    function canvas(w, h, dessiner) {
        const c = document.createElement("canvas");
        c.width = w;
        c.height = h;
        const ctx = c.getContext("2d");
        dessiner(ctx, w, h);
        return c;
    }
    function texture(cle, w, h, dessiner, repeat = [1, 1]) {
        const id = `${cle}|${repeat.join("x")}`;
        if (!textures.has(id)) {
            const t = new THREE.CanvasTexture(canvas(w, h, dessiner));
            t.wrapS = t.wrapT = THREE.RepeatWrapping;
            t.repeat.set(repeat[0], repeat[1]);
            t.anisotropy = 4;
            t.colorSpace = THREE.SRGBColorSpace;
            textures.set(id, t);
        }
        return textures.get(id);
    }
    const bruit = (ctx, w, h, n, alpha, teinte = "0,0,0") => {
        for (let i = 0; i < n; i++) {
            ctx.fillStyle = `rgba(${teinte},${Math.random() * alpha})`;
            ctx.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * 3, 1 + Math.random() * 3);
        }
    };
    const SOLS = {
        parquet: (rep) => texture("parquet", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#d9b98a";
            ctx.fillRect(0, 0, w, h);
            for (let y = 0; y < h; y += 32) {
                const decal = (y / 32) % 2 ? 64 : 0;
                for (let x = -128; x < w; x += 128) {
                    const l = 60 + Math.random() * 20;
                    ctx.fillStyle = `hsl(32, 45%, ${l}%)`;
                    ctx.fillRect(x + decal, y, 126, 30);
                }
            }
            ctx.strokeStyle = "rgba(90,60,30,0.35)";
            for (let y = 0; y < h; y += 32) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
            }
            bruit(ctx, w, h, 600, 0.08);
        }, rep),
        carrelage: (rep) => texture("carrelage", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#ece9e1";
            ctx.fillRect(0, 0, w, h);
            ctx.strokeStyle = "rgba(120,115,105,0.35)";
            ctx.lineWidth = 2;
            for (let i = 0; i <= w; i += 64) {
                ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, h); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(w, i); ctx.stroke();
            }
            bruit(ctx, w, h, 300, 0.05);
        }, rep),
        carrelage_chaud: (rep) => texture("carrelage_chaud", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#e6d6c3";
            ctx.fillRect(0, 0, w, h);
            ctx.strokeStyle = "rgba(120,90,60,0.35)";
            ctx.lineWidth = 2;
            for (let i = 0; i <= w; i += 64) {
                ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, h); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(w, i); ctx.stroke();
            }
            bruit(ctx, w, h, 300, 0.06);
        }, rep),
        beton: (rep) => texture("beton", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#cfcbc2";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 1500, 0.12);
            bruit(ctx, w, h, 400, 0.08, "255,255,255");
        }, rep),
        beton_marque: (rep) => texture("beton_marque", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#c9c6bf";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 1500, 0.12);
            ctx.strokeStyle = "rgba(242,196,48,0.9)";
            ctx.lineWidth = 6;
            ctx.setLineDash([24, 14]);
            ctx.strokeRect(14, 14, w - 28, h - 28);
        }, rep),
        moquette: (rep) => texture("moquette", 128, 128, (ctx, w, h) => {
            ctx.fillStyle = "#8aa9b4";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 2500, 0.15);
            bruit(ctx, w, h, 800, 0.12, "255,255,255");
        }, rep),
        enrobe: (rep) => texture("enrobe", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#6f7378";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 2500, 0.2);
            bruit(ctx, w, h, 600, 0.12, "255,255,255");
        }, rep),
        beton_ext: (rep) => texture("beton_ext", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#bdb8ad";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 2000, 0.14);
            ctx.strokeStyle = "rgba(90,85,80,0.3)";
            ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(w / 2, 0); ctx.lineTo(w / 2, h); ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2); ctx.stroke();
        }, rep),
        terre: (rep) => texture("terre", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#a9774a";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 2000, 0.18);
            for (let y = 8; y < h; y += 16) {
                ctx.fillStyle = "rgba(60,35,15,0.25)";
                ctx.fillRect(0, y, w, 3);
            }
        }, rep),
        herbe: (rep) => texture("herbe", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#9ccd77";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 2500, 0.12, "40,90,20");
            bruit(ctx, w, h, 700, 0.1, "255,255,200");
        }, rep),
        enduit: (rep) => texture("enduit", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#f1ece2";
            ctx.fillRect(0, 0, w, h);
            bruit(ctx, w, h, 1200, 0.07);
            ctx.fillStyle = "#c89a62";
            ctx.fillRect(0, h * 0.72, w, h * 0.28);
            ctx.strokeStyle = "rgba(90,60,30,0.3)";
            for (let x = 0; x < w; x += 24) {
                ctx.beginPath(); ctx.moveTo(x, h * 0.72); ctx.lineTo(x, h); ctx.stroke();
            }
        }, rep),
        bardage: (rep) => texture("bardage", 256, 256, (ctx, w, h) => {
            ctx.fillStyle = "#dedad0";
            ctx.fillRect(0, 0, w, h);
            for (let x = 0; x < w; x += 32) {
                ctx.fillStyle = (x / 32) % 2 ? "#d2cec4" : "#e4e0d6";
                ctx.fillRect(x, 0, 32, h);
                ctx.fillStyle = "rgba(0,0,0,0.12)";
                ctx.fillRect(x + 28, 0, 4, h);
            }
        }, rep),
    };
    function sol(type, l, p) {
        const f = SOLS[type] || SOLS.beton;
        return f([Math.max(1, l / 4), Math.max(1, p / 4)]);
    }
    /** Un texte peint : la texture d'un plan (fond transparent). */
    function texteTexture(texte, o = {}) {
        const cle = `txt|${texte}|${o.couleur || ""}|${o.taille || ""}`;
        if (!textures.has(cle)) {
            const w = 512, h = 128;
            const t = new THREE.CanvasTexture(canvas(w, h, (ctx) => {
                ctx.clearRect(0, 0, w, h);
                let taille = o.taille || 56;
                ctx.font = `800 ${taille}px Inter, "Segoe UI", Arial, sans-serif`;
                while (taille > 14 && ctx.measureText(texte).width > w - 24) {
                    taille -= 2;
                    ctx.font = `800 ${taille}px Inter, "Segoe UI", Arial, sans-serif`;
                }
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillStyle = o.couleur || "rgba(40,60,70,0.55)";
                ctx.fillText(texte, w / 2, h / 2);
            }));
            t.colorSpace = THREE.SRGBColorSpace;
            textures.set(cle, t);
        }
        return textures.get(cle);
    }
    /** Un texte peint au sol (ou sur un mur, à plat) : un plan avec la texture du texte. */
    function textePeint(texte, l = 6, o = {}) {
        const m = new THREE.Mesh(new THREE.PlaneGeometry(l, l / 4), new THREE.MeshBasicMaterial({ map: texteTexture(texte, o), transparent: true, depthWrite: false }));
        m.rotation.x = -Math.PI / 2;
        m.position.y = 0.02;
        return m;
    }
    /** Le logo de l'adhérent : un monogramme dans un carré arrondi, à l'accent. */
    function logoTexture(lettre, accent) {
        const cle = `logo|${lettre}|${accent}`;
        if (!textures.has(cle)) {
            const t = new THREE.CanvasTexture(canvas(256, 256, (ctx, w, h) => {
                ctx.clearRect(0, 0, w, h);
                ctx.fillStyle = accent;
                ctx.beginPath();
                ctx.roundRect(16, 16, w - 32, h - 32, 48);
                ctx.fill();
                ctx.fillStyle = "#ffffff";
                ctx.font = "900 150px Inter, Arial, sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(lettre, w / 2, h / 2 + 8);
            }));
            t.colorSpace = THREE.SRGBColorSpace;
            textures.set(cle, t);
        }
        return textures.get(cle);
    }

    // ------------------------------------------------------------------ les écrans

    const ECRANS = {
        cao: (ctx, w, h) => {
            ctx.fillStyle = "#1c2733"; ctx.fillRect(0, 0, w, h);
            ctx.strokeStyle = "#5fd1e6"; ctx.lineWidth = 2;
            for (let i = 0; i < 6; i++) { ctx.strokeRect(10 + i * 14, 12 + i * 8, 80 - i * 8, 48 - i * 4); }
            ctx.fillStyle = "#f2c230"; ctx.fillRect(100, 14, 20, 20);
        },
        tableur: (ctx, w, h) => {
            ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, w, h);
            ctx.strokeStyle = "#cbd5de";
            for (let y = 10; y < h; y += 10) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
            for (let x = 0; x < w; x += 24) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
            ctx.fillStyle = "#4fa83a"; ctx.fillRect(0, 0, w, 10);
            ctx.fillStyle = "#2a63b0"; for (let i = 0; i < 5; i++) { ctx.fillRect(26, 14 + i * 10, 30 + i * 9, 6); }
        },
        crm: (ctx, w, h) => {
            ctx.fillStyle = "#f4f1ea"; ctx.fillRect(0, 0, w, h);
            ctx.fillStyle = "#0b9bb8"; ctx.fillRect(0, 0, 28, h);
            for (let i = 0; i < 4; i++) { ctx.fillStyle = "#ffffff"; ctx.fillRect(36, 8 + i * 17, 80, 13); ctx.fillStyle = "#0b9bb8"; ctx.fillRect(40, 11 + i * 17, 20, 7); }
        },
        compta: (ctx, w, h) => {
            ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, w, h);
            ctx.fillStyle = "#1d4550"; ctx.fillRect(0, 0, w, 12);
            for (let i = 0; i < 6; i++) { ctx.fillStyle = i % 2 ? "#eef2f4" : "#ffffff"; ctx.fillRect(0, 16 + i * 9, w, 9); ctx.fillStyle = "#2c3a43"; ctx.fillRect(6, 18 + i * 9, 50, 5); ctx.fillStyle = i === 4 ? "#d94f45" : "#4fa83a"; ctx.fillRect(92, 18 + i * 9, 26, 5); }
        },
        code: (ctx, w, h) => {
            ctx.fillStyle = "#1e1e24"; ctx.fillRect(0, 0, w, h);
            const c = ["#c586c0", "#9cdcfe", "#ce9178", "#dcdcaa", "#6a9955"];
            for (let i = 0; i < 8; i++) { ctx.fillStyle = c[i % c.length]; ctx.fillRect(8 + (i % 3) * 10, 8 + i * 8, 30 + ((i * 37) % 60), 4); }
        },
        verrouille: (ctx, w, h) => {
            ctx.fillStyle = "#2c3a43"; ctx.fillRect(0, 0, w, h);
            ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 3; ctx.strokeRect(w / 2 - 10, h / 2 - 2, 20, 16);
            ctx.beginPath(); ctx.arc(w / 2, h / 2 - 4, 7, Math.PI, 0); ctx.stroke();
        },
        eteint: (ctx, w, h) => { ctx.fillStyle = "#15191c"; ctx.fillRect(0, 0, w, h); },
        bienvenue: (ctx, w, h) => {
            ctx.fillStyle = "#0b9bb8"; ctx.fillRect(0, 0, w, h);
            ctx.fillStyle = "#ffffff"; ctx.font = "800 18px Inter, Arial"; ctx.textAlign = "center"; ctx.fillText("BIENVENUE", w / 2, h / 2 - 6);
            ctx.font = "500 11px Inter, Arial"; ctx.fillText("Irrigation · conseil · pièces", w / 2, h / 2 + 12);
        },
        presentation: (ctx, w, h) => {
            ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, w, h);
            ctx.fillStyle = "#1d4550"; ctx.fillRect(10, 10, 60, 8);
            ctx.fillStyle = "#0b9bb8"; for (let i = 0; i < 5; i++) { ctx.fillRect(14 + i * 22, 60 - i * 8, 14, 10 + i * 8); }
        },
        visio: (ctx, w, h) => {
            ctx.fillStyle = "#1c2733"; ctx.fillRect(0, 0, w, h);
            for (let i = 0; i < 4; i++) { ctx.fillStyle = ["#4a6b7a", "#6b5a4a", "#4a5a6b", "#5a6b4a"][i]; ctx.fillRect(6 + (i % 2) * 60, 6 + Math.floor(i / 2) * 36, 56, 32); ctx.fillStyle = "#f0c3a3"; ctx.beginPath(); ctx.arc(34 + (i % 2) * 60, 24 + Math.floor(i / 2) * 36, 8, 0, 7); ctx.fill(); }
        },
    };
    function ecranTexture(type) {
        const cle = `ecran|${type}`;
        if (!textures.has(cle)) {
            const t = new THREE.CanvasTexture(canvas(128, 80, ECRANS[type] || ECRANS.eteint));
            t.colorSpace = THREE.SRGBColorSpace;
            textures.set(cle, t);
        }
        return textures.get(cle);
    }
    /** Change l'image de l'écran d'un poste (bureau) : l'application ouverte, verrouillé, éteint. */
    function allumerEcran(objet, type) {
        objet.traverse((m) => {
            if (m.name === "ecran") {
                m.material = new THREE.MeshBasicMaterial({ map: ecranTexture(type) });
            }
        });
    }

    // ------------------------------------------------------------------ les personnages articulés

    /** Un personnage : jambes et bras sur pivots, tête, cheveux, casquette ou casque, accessoire. Les membres portent un nom. */
    function personnage(o = {}) {
        const g = groupe();
        const tenue = TENUES[o.tenue] || TENUES.chemise;
        const haut = o.haut ?? tenue[0][Math.floor(Math.random() * tenue[0].length)];
        const bas = o.bas ?? tenue[1];
        const peau = o.peau ?? PEAUX[Math.floor(Math.random() * PEAUX.length)];
        const cheveux = o.cheveux ?? CHEVEUX[Math.floor(Math.random() * CHEVEUX.length)];
        const r = o.rayon ?? 0.06;
        // le bassin et le torse
        const torse = groupe();
        torse.name = "torse";
        torse.position.y = 0.78;
        bloc(torse, 0.32, 0.6, 0.46, haut, 0, 0, 0, { rayon: 0.12 });
        bloc(torse, 0.3, 0.1, 0.44, bas, 0, -0.06, 0, { rayon: 0.05 });
        if (o.gilet) {
            bloc(torse, 0.34, 0.36, 0.48, T.jaune, 0, 0.2, 0, { rayon: 0.1, e: 0.15 });
        }
        // la tête
        const tete = groupe();
        tete.name = "tete";
        tete.position.y = 0.64;
        boule(tete, 0.16, peau, 0, 0.12, 0);
        if (o.casque) {
            boule(tete, 0.185, o.casque === true ? T.jaune : o.casque, 0, 0.17, 0, { ecrase: 0.6 });
        } else if (o.casquette) {
            boule(tete, 0.168, o.casquette === true ? 0x1d4550 : o.casquette, 0, 0.17, 0, { ecrase: 0.5 });
            bloc(tete, 0.16, 0.03, 0.2, o.casquette === true ? 0x1d4550 : o.casquette, 0.13, 0.19, 0, { rayon: 0.01 });
        } else {
            boule(tete, 0.165, cheveux, -0.02, 0.17, 0, { ecrase: o.cheveuxLongs ? 0.9 : 0.55 });
        }
        torse.add(tete);
        // les bras (pivot à l'épaule)
        for (const cote of [-1, 1]) {
            const bras = groupe();
            bras.name = cote < 0 ? "brasG" : "brasD";
            bras.position.set(0, 0.26, cote * 0.3);
            bloc(bras, 0.12, 0.3, 0.12, haut, 0, -0.3, 0, { rayon: r });
            bloc(bras, 0.11, 0.26, 0.11, peau, 0, -0.56, 0, { rayon: r });
            torse.add(bras);
        }
        g.add(torse);
        // les jambes (pivot à la hanche)
        for (const cote of [-1, 1]) {
            const jambe = groupe();
            jambe.name = cote < 0 ? "jambeG" : "jambeD";
            jambe.position.set(0, 0.78, cote * 0.1);
            bloc(jambe, 0.16, 0.78, 0.16, bas, 0, -0.78, 0, { rayon: 0.07 });
            bloc(jambe, 0.22, 0.08, 0.16, T.anthracite, 0.03, -0.8, 0, { rayon: 0.03 });
            g.add(jambe);
        }
        // l'accessoire dans la main droite
        if (o.accessoire) {
            const brasD = g.getObjectByName("brasD");
            const acc = groupe();
            acc.name = "accessoire";
            acc.position.set(0.02, -0.72, 0);
            if (o.accessoire === "tablette") {
                bloc(acc, 0.02, 0.22, 0.16, T.anthracite, 0.08, -0.1, 0, { rayon: 0.01 });
            } else if (o.accessoire === "carton") {
                bloc(acc, 0.4, 0.3, 0.35, T.carton, 0.2, -0.15, 0, { rayon: 0.02 });
            } else if (o.accessoire === "outil") {
                cyl(acc, 0.02, 0.02, 0.3, T.gris, 0.05, -0.02, 0, "x", { m: 0.5 });
            } else if (o.accessoire === "tasse") {
                cyl(acc, 0.05, 0.04, 0.09, T.blanc, 0.05, -0.02, 0);
            }
            brasD.add(acc);
        }
        g.userData.personnage = true;
        g.userData.ombre = ombreContact(0.32);
        g.add(g.userData.ombre);
        return g;
    }
    const membres = (p) => ({
        bg: p.getObjectByName("brasG"), bd: p.getObjectByName("brasD"), jg: p.getObjectByName("jambeG"), jd: p.getObjectByName("jambeD"),
        torse: p.getObjectByName("torse"), tete: p.getObjectByName("tete"),
    });
    const lerp = (a, b, k) => a + (b - a) * k;
    /** Applique une pose à un personnage. t : le temps (s) pour les poses animées ; k : le fondu vers la pose (0-1). */
    function poser(p, pose, t = 0, k = 1) {
        const m = membres(p);
        if (!m.torse) {
            return;
        }
        const cible = { bg: 0, bd: 0, jg: 0, jd: 0, torseY: 0.78, torseX: 0, teteY: 0, bgZ: 0, bdZ: 0, jgK: 0, jdK: 0, bob: 0 };
        const phase = (p.userData.phase ?? 0) + t * 7.5;
        switch (pose) {
            case "marche":
                cible.bg = Math.sin(phase) * 0.7; cible.bd = -Math.sin(phase) * 0.7;
                cible.jg = -Math.sin(phase) * 0.75; cible.jd = Math.sin(phase) * 0.75;
                cible.bob = Math.abs(Math.sin(phase)) * 0.035;
                break;
            case "debout":
                cible.bob = Math.sin(t * 1.4) * 0.008; cible.bg = 0.05; cible.bd = -0.05;
                break;
            case "assis":
            case "assis_bureau":
                cible.jg = cible.jd = -Math.PI / 2; cible.torseY = 0.52; cible.bg = cible.bd = -0.95 + Math.sin(t * 9 + (p.userData.phase ?? 0)) * 0.05;
                cible.teteY = Math.sin(t * 0.7) * 0.08;
                break;
            case "assis_reunion":
                cible.jg = cible.jd = -Math.PI / 2; cible.torseY = 0.52; cible.bg = -0.5; cible.bd = -0.5 + Math.max(0, Math.sin(t * 1.3 + (p.userData.phase ?? 0))) * 0.6;
                cible.teteY = Math.sin(t * 0.9 + 1) * 0.25;
                break;
            case "assis_detendu":
                cible.jg = cible.jd = -Math.PI / 2 + 0.3; cible.torseY = 0.52; cible.torseX = -0.15; cible.bg = cible.bd = -0.25;
                break;
            case "cafe":
                cible.bd = -1.9 + Math.sin(t * 1.1) * 0.25; cible.bg = 0.1; cible.bob = Math.sin(t * 1.4) * 0.006;
                break;
            case "telephone":
                cible.bd = -2.4; cible.bdZ = -0.5; cible.teteY = 0.2;
                break;
            case "discussion":
                cible.bg = -0.4 + Math.sin(t * 2.1) * 0.2; cible.bd = -0.6 + Math.sin(t * 1.7 + 1) * 0.3; cible.teteY = Math.sin(t * 0.8) * 0.15;
                break;
            case "accroupi":
                cible.jg = cible.jd = -2.0; cible.jgK = cible.jdK = 1.8; cible.torseY = 0.35; cible.torseX = 0.35; cible.bg = cible.bd = -1.0;
                break;
            case "soudure":
                cible.jg = cible.jd = -1.5; cible.torseY = 0.42; cible.torseX = 0.5; cible.bd = -1.3 + Math.sin(t * 6) * 0.08; cible.bg = -0.9;
                break;
            case "outil":
                cible.bd = -1.1 + Math.sin(t * 5) * 0.25; cible.bg = -0.3; cible.torseX = 0.25;
                break;
            case "comptoir":
                cible.bg = -0.9; cible.bd = -0.8 + Math.sin(t * 4) * 0.08; cible.teteY = Math.sin(t * 0.6) * 0.1;
                break;
            case "babyfoot":
                cible.torseX = 0.35; cible.bg = -1.2 + Math.sin(t * 9) * 0.2; cible.bd = -1.2 - Math.sin(t * 9) * 0.2;
                break;
            case "porte":
                cible.bg = cible.bd = -0.9; cible.jg = -Math.sin(phase) * 0.6; cible.jd = Math.sin(phase) * 0.6; cible.bob = Math.abs(Math.sin(phase)) * 0.03;
                break;
            default:
                break;
        }
        const e = p.userData.pose = p.userData.pose || { bg: 0, bd: 0, jg: 0, jd: 0, torseY: 0.78, torseX: 0, teteY: 0, bgZ: 0, bdZ: 0, jgK: 0, jdK: 0, bob: 0 };
        for (const cle of Object.keys(cible)) {
            e[cle] = lerp(e[cle], cible[cle], k);
        }
        m.bg.rotation.z = e.bg; m.bd.rotation.z = e.bd; m.bg.rotation.x = e.bgZ; m.bd.rotation.x = e.bdZ;
        m.jg.rotation.z = e.jg; m.jd.rotation.z = e.jd;
        m.torse.position.y = e.torseY + e.bob; m.torse.rotation.z = e.torseX; m.tete.rotation.y = e.teteY;
        if (p.userData.ombre) {
            p.userData.ombre.scale.setScalar(1 - e.bob * 4);
        }
    }

    // ------------------------------------------------------------------ les marqueurs, ombres, particules

    function ombreContact(r = 0.4) {
        const t = texture("ombre", 64, 64, (ctx, w, h) => {
            const grad = ctx.createRadialGradient(w / 2, h / 2, 2, w / 2, h / 2, w / 2);
            grad.addColorStop(0, "rgba(20,30,40,0.45)");
            grad.addColorStop(1, "rgba(20,30,40,0)");
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, w, h);
        });
        const m = new THREE.Mesh(new THREE.PlaneGeometry(r * 2.2, r * 2.2), new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false }));
        m.rotation.x = -Math.PI / 2;
        m.position.y = 0.015;
        m.renderOrder = 1;
        return m;
    }
    /** L'épingle 3D : une boule et un cône à l'accent, qui flotte. */
    function epingle(accent) {
        const g = groupe();
        const c = new THREE.Color(accent);
        const cone = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.6, 16), mat(c.getHex(), { r: 0.4, e: 0.25 }));
        cone.rotation.x = Math.PI;
        cone.position.y = 0.3;
        g.add(cone);
        const tete = new THREE.Mesh(new THREE.SphereGeometry(0.3, 18, 14), mat(c.getHex(), { r: 0.4, e: 0.25 }));
        tete.position.y = 0.75;
        g.add(tete);
        const point = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 10), mat(0xffffff, { r: 0.5 }));
        point.position.set(0.12, 0.8, 0.22);
        g.add(point);
        g.userData.epingle = true;
        return g;
    }
    /** Les crochets d'angle de la sélection : 8 coins, à l'accent, visibles à travers les objets. */
    function crochets(accent) {
        const g = groupe();
        const m = new THREE.MeshBasicMaterial({ color: new THREE.Color(accent), depthTest: false, transparent: true, opacity: 0.95 });
        const l = 0.3, e = 0.05;
        for (const sx of [-1, 1]) {
            for (const sy of [-1, 1]) {
                for (const sz of [-1, 1]) {
                    const coin = groupe();
                    coin.name = `coin${sx}${sy}${sz}`;
                    for (const [w, h, d, x, y, z] of [[l, e, e, -sx * l / 2, 0, 0], [e, l, e, 0, -sy * l / 2, 0], [e, e, l, 0, 0, -sz * l / 2]]) {
                        const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
                        b.position.set(x, y, z);
                        b.renderOrder = 20;
                        coin.add(b);
                    }
                    coin.userData.signe = [sx, sy, sz];
                    g.add(coin);
                }
            }
        }
        g.renderOrder = 20;
        return g;
    }
    /** Le halo radial au sol sous la sélection. */
    function halo(accent) {
        const c = new THREE.Color(accent);
        const t = texture(`halo|${accent}`, 128, 128, (ctx, w, h) => {
            const grad = ctx.createRadialGradient(w / 2, h / 2, 10, w / 2, h / 2, w / 2);
            grad.addColorStop(0, `rgba(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)},0.35)`);
            grad.addColorStop(0.7, `rgba(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)},0.12)`);
            grad.addColorStop(1, "rgba(0,0,0,0)");
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, w, h);
        });
        const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false }));
        m.rotation.x = -Math.PI / 2;
        m.position.y = 0.03;
        m.renderOrder = 2;
        return m;
    }
    /** Des étincelles (soudure) : des points additifs avec gravité et rebond. */
    function etincelles(n = 40) {
        const positions = new Float32Array(n * 3);
        const vitesses = [];
        for (let i = 0; i < n; i++) {
            vitesses.push([0, 0, 0, 1e9]);
        }
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        const pts = new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xffd36b, size: 0.09, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false }));
        pts.userData.vitesses = vitesses;
        pts.userData.actif = true;
        pts.frustumCulled = false;
        const lumiere = new THREE.PointLight(0xffc24d, 0, 4);
        lumiere.position.y = 0.9;
        pts.add(lumiere);
        pts.userData.lumiere = lumiere;
        pts.userData.animer = (dt, t) => {
            const p = pts.geometry.attributes.position.array;
            const salve = Math.sin(t * 2.3) > 0.2 && pts.userData.actif;
            for (let i = 0; i < n; i++) {
                const v = vitesses[i];
                if (v[3] > 0.6) {
                    if (salve && Math.random() < 0.25) {
                        p[i * 3] = 0; p[i * 3 + 1] = 0.9; p[i * 3 + 2] = 0;
                        v[0] = (Math.random() - 0.5) * 3; v[1] = Math.random() * 2.5; v[2] = (Math.random() - 0.5) * 3; v[3] = 0;
                    } else {
                        p[i * 3 + 1] = -5;
                        continue;
                    }
                }
                v[1] -= 9.8 * dt;
                p[i * 3] += v[0] * dt; p[i * 3 + 1] += v[1] * dt; p[i * 3 + 2] += v[2] * dt;
                if (p[i * 3 + 1] < 0.02) {
                    p[i * 3 + 1] = 0.02; v[1] = -v[1] * 0.35; v[0] *= 0.6; v[2] *= 0.6;
                }
                v[3] += dt;
            }
            pts.geometry.attributes.position.needsUpdate = true;
            lumiere.intensity = salve ? 1.2 + Math.random() * 1.5 : 0;
        };
        return pts;
    }
    /** Un jet d'arrosage : des gouttes en arc, depuis un canon ou un asperseur. */
    function jet(o = {}) {
        const n = o.n ?? 60, portee = o.portee ?? 6, hauteur = o.hauteur ?? 1.2;
        const positions = new Float32Array(n * 3);
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        const pts = new THREE.Points(geo, new THREE.PointsMaterial({ color: 0x9fe0f2, size: 0.14, transparent: true, opacity: 0.8, depthWrite: false }));
        pts.frustumCulled = false;
        pts.userData.animer = (dt, t) => {
            const p = pts.geometry.attributes.position.array;
            const angle = o.tourne ? t * 0.6 : 0;
            for (let i = 0; i < n; i++) {
                const s = ((i / n) + t * 0.5) % 1;
                const d = s * portee;
                const y = hauteur + Math.sin(s * Math.PI) * portee * 0.25 - s * hauteur * 0.9;
                const a = angle + (o.secteur ? Math.sin(t * 0.8) * o.secteur : 0) + (i % 3) * 0.04;
                p[i * 3] = Math.cos(a) * d; p[i * 3 + 1] = Math.max(0.02, y); p[i * 3 + 2] = Math.sin(a) * d;
            }
            pts.geometry.attributes.position.needsUpdate = true;
        };
        return pts;
    }

    // ------------------------------------------------------------------ le mobilier qui manquait

    const modeles = {
        canape: (o = {}) => {
            const g = groupe();
            const c = o.couleur ?? 0x5d8aa8;
            bloc(g, 1.8, 0.42, 0.85, c, 0, 0, 0, { rayon: 0.12 });
            bloc(g, 1.8, 0.42, 0.22, c, 0, 0.42, -0.32, { rayon: 0.1 });
            bloc(g, 0.2, 0.26, 0.85, c, -0.8, 0.42, 0, { rayon: 0.08 });
            bloc(g, 0.2, 0.26, 0.85, c, 0.8, 0.42, 0, { rayon: 0.08 });
            return g;
        },
        babyfoot: () => {
            const g = groupe();
            bloc(g, 1.4, 0.3, 0.75, T.rouge, 0, 0.65, 0, { rayon: 0.05 });
            bloc(g, 1.3, 0.02, 0.65, 0x4fa83a, 0, 0.95, 0, { vif: true });
            for (const x of [-0.6, 0.6]) {
                for (const z of [-0.3, 0.3]) {
                    bloc(g, 0.07, 0.65, 0.07, T.bois, x, 0, z, { vif: true });
                }
            }
            for (let i = 0; i < 4; i++) {
                cyl(g, 0.015, 0.015, 1.0, T.gris, -0.45 + i * 0.3, 0.84, 0, "z", { m: 0.6 });
            }
            return g;
        },
        ecran_mural: (o = {}) => {
            const g = groupe();
            bloc(g, 0.06, 1.1, 1.9, T.noir, 0, 1.3, 0, { rayon: 0.02 });
            const e = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 1.0), new THREE.MeshBasicMaterial({ map: ecranTexture(o.contenu || "presentation") }));
            e.name = "ecran";
            e.rotation.y = Math.PI / 2;
            e.position.set(0.035, 1.85, 0);
            g.add(e);
            return g;
        },
        serveur: () => {
            const g = groupe();
            bloc(g, 0.6, 1.9, 0.8, T.anthracite, 0, 0, 0, { rayon: 0.03, m: 0.3 });
            for (let i = 0; i < 6; i++) {
                bloc(g, 0.02, 0.05, 0.05, i % 2 ? 0x4fa83a : 0x0b9bb8, 0.31, 0.4 + i * 0.22, -0.25, { vif: true, e: 0.9, ombre: false }).name = "led";
                bloc(g, 0.02, 0.12, 0.55, 0x3a4a56, 0.31, 0.36 + i * 0.22, 0.08, { vif: true, ombre: false });
            }
            return g;
        },
        imprimante: () => {
            const g = groupe();
            bloc(g, 0.7, 0.75, 0.6, T.blanc, 0, 0, 0, { rayon: 0.04 });
            bloc(g, 0.72, 0.3, 0.62, T.gris, 0, 0.75, 0, { rayon: 0.05 });
            bloc(g, 0.4, 0.04, 0.3, T.anthracite, 0.1, 1.05, 0, { rayon: 0.01 });
            const feuille = bloc(g, 0.3, 0.01, 0.3, T.papier, 0.45, 0.7, 0, { vif: true, ombre: false });
            feuille.name = "feuille";
            return g;
        },
        pot_cafe: () => M.machineCafe(),
        goutte: (o = {}) => M.culture({ ...o, goutte: true, genre: o.genre || "vigne" }),
        aspersion: (o = {}) => {
            const g = M.culture({ l: o.l ?? 9, p: o.p ?? 7, genre: "mais" });
            for (const [x, z] of [[-3, -2], [0, -2], [3, -2], [-3, 2], [0, 2], [3, 2]]) {
                const a = M.asperseur();
                a.position.set(x, 0.1, z);
                g.add(a);
            }
            return g;
        },
    };

    /** Un objet du kit par son type : la bibliothèque de base d'abord, puis le mobilier de la map. */
    function fabriquer(type, params = {}) {
        const noms = { machine_cafe: "machineCafe", place: null };
        const nom = noms[type] === undefined ? type : noms[type];
        if (!nom) {
            return groupe();
        }
        if (modeles[nom]) {
            return modeles[nom](params);
        }
        if (M[nom]) {
            return M[nom](params);
        }
        return M.palette(params);
    }

    /** La liste du kit pour la palette de l'éditeur. */
    const PALETTE = [
        { type: "bureau", nom: "Bureau", categorie: "Bureaux" }, { type: "chaise", nom: "Chaise", categorie: "Bureaux" }, { type: "table", nom: "Table", categorie: "Bureaux" },
        { type: "armoire", nom: "Armoire", categorie: "Bureaux" }, { type: "imprimante", nom: "Imprimante", categorie: "Bureaux" }, { type: "serveur", nom: "Serveur", categorie: "Bureaux" },
        { type: "plans", nom: "Table à plans", categorie: "Bureaux" }, { type: "ecran_mural", nom: "Écran mural", categorie: "Bureaux" }, { type: "plante", nom: "Plante", categorie: "Bureaux" },
        { type: "canape", nom: "Canapé", categorie: "Détente" }, { type: "babyfoot", nom: "Baby-foot", categorie: "Détente" }, { type: "machine_cafe", nom: "Machine à café", categorie: "Détente" },
        { type: "comptoir", nom: "Comptoir", categorie: "Magasin" }, { type: "gondole", nom: "Gondole", categorie: "Magasin" }, { type: "rack", nom: "Rayonnage", categorie: "Magasin" },
        { type: "palette", nom: "Palette", categorie: "Magasin" }, { type: "chariot", nom: "Chariot élévateur", categorie: "Magasin" }, { type: "borne", nom: "Badgeuse", categorie: "Magasin" },
        { type: "etabli", nom: "Établi", categorie: "Atelier" }, { type: "soudeuse", nom: "Poste à souder", categorie: "Atelier" }, { type: "bac", nom: "Bac", categorie: "Atelier" },
        { type: "nettoyeur", nom: "Nettoyeur", categorie: "Atelier" }, { type: "pompe", nom: "Pompe", categorie: "Atelier" },
        { type: "cantilever", nom: "Cantilever tubes", categorie: "Cour" }, { type: "bobines", nom: "Bobines", categorie: "Cour" }, { type: "prefa", nom: "Cuves", categorie: "Cour" },
        { type: "benne", nom: "Benne", categorie: "Cour" }, { type: "quai", nom: "Quai", categorie: "Cour" }, { type: "tracteur", nom: "Tracteur", categorie: "Cour" },
        { type: "minipelle", nom: "Mini-pelle", categorie: "Cour" }, { type: "lampadaire", nom: "Lampadaire", categorie: "Cour" }, { type: "panneau", nom: "Panneau", categorie: "Cour" },
        { type: "totem", nom: "Totem", categorie: "Cour" }, { type: "arbre", nom: "Arbre", categorie: "Cour" }, { type: "haie", nom: "Haie", categorie: "Cour" },
    ];

    return { ...base, THREE, texture, sol, SOLS, texteTexture, textePeint, logoTexture, ecranTexture, allumerEcran, personnage, poser, ombreContact, epingle, crochets, halo,
             etincelles, jet, fabriquer, modeles, PALETTE, TEINTES: T };
}
