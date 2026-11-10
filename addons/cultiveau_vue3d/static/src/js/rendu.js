/** @odoo-module **/
// Le rendu « photo » de la Map vivante (10/11/2026, « beaucoup plus réel »). Sans dépendance : tout est écrit sur le
// cœur de three.js. La scène est rendue en haute dynamique, puis :
//   - l'occlusion ambiante (les creux, les pieds de meubles, les angles de murs s'assombrissent comme en vrai) ;
//   - le halo des lumières vives (suspensions, écrans, reflets du soleil) ;
//   - l'étalonnage : courbe filmique, contraste, saturation, vignette, grain fin.
// Le ciel éclaire la scène par une carte d'environnement calculée (reflets sur l'inox, les vitres, les carrosseries).
// La qualité s'adapte : si la machine peine, on retire l'occlusion, puis tout le post-traitement (rendu direct).

const VERTEX = "varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";

const FRAG_AO = `
precision highp float;
#define N 14
varying vec2 vUv;
uniform sampler2D tDepth;
uniform mat4 projInv;
uniform float p11, rayon, intensite;
uniform vec2 res;
vec3 posVue(vec2 uv) {
    float d = texture2D(tDepth, uv).x;
    vec4 v = projInv * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
    return v.xyz / v.w;
}
void main() {
    float d = texture2D(tDepth, vUv).x;
    if (d >= 0.9999) { gl_FragColor = vec4(1.0); return; }
    vec3 p = posVue(vUv);
    vec2 px = 1.0 / res;
    vec3 pr = posVue(vUv + vec2(px.x, 0.0)), pl = posVue(vUv - vec2(px.x, 0.0));
    vec3 pu = posVue(vUv + vec2(0.0, px.y)), pd = posVue(vUv - vec2(0.0, px.y));
    vec3 dx = abs(pr.z - p.z) < abs(p.z - pl.z) ? pr - p : p - pl;
    vec3 dy = abs(pu.z - p.z) < abs(p.z - pd.z) ? pu - p : p - pd;
    vec3 n = normalize(cross(dx, dy));
    float bruit = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
    float rUv = clamp(rayon * p11 * 0.5 / -p.z, 2.0 * px.y, 0.14);
    float r2 = rayon * rayon, occ = 0.0;
    for (int i = 0; i < N; i++) {
        float fi = float(i) + 0.5;
        float a = fi * 2.399963 + bruit * 6.2831853;
        vec2 off = vec2(cos(a), sin(a)) * sqrt(fi / float(N)) * rUv;
        off.x *= res.y / res.x;
        vec3 v = posVue(vUv + off) - p;
        float vv = dot(v, v), vn = dot(v, n);
        float f = max(r2 - vv, 0.0);
        occ += f * f * f * max((vn - 0.03) / (0.01 + vv), 0.0);
    }
    float ao = max(0.0, 1.0 - intensite * 5.0 * occ / (r2 * r2 * r2 * float(N)));
    gl_FragColor = vec4(vec3(ao), 1.0);
}`;

const FRAG_FLOU_AO = `
precision highp float;
varying vec2 vUv;
uniform sampler2D tAO, tDepth;
uniform vec2 pas;
uniform float near, far;
float zVue(vec2 uv) { float d = texture2D(tDepth, uv).x; return near * far / (far - d * (far - near)); }
void main() {
    float z0 = zVue(vUv), somme = 0.0, poids = 0.0;
    for (int i = -4; i <= 4; i++) {
        vec2 uv = vUv + pas * float(i);
        float w = exp(-float(i * i) / 10.0) * exp(-abs(zVue(uv) - z0) * 2.5);
        somme += texture2D(tAO, uv).r * w;
        poids += w;
    }
    gl_FragColor = vec4(vec3(somme / poids), 1.0);
}`;

const FRAG_SEUIL = `
precision highp float;
varying vec2 vUv;
uniform sampler2D tColor;
uniform float seuil;
void main() {
    vec3 c = texture2D(tColor, vUv).rgb;
    float l = max(c.r, max(c.g, c.b));
    float k = clamp((l - seuil) / max(l, 0.0001), 0.0, 1.0);
    gl_FragColor = vec4(min(c * k * k, vec3(12.0)), 1.0);
}`;

const FRAG_BAS = `
precision highp float;
varying vec2 vUv;
uniform sampler2D tSrc;
uniform vec2 px;
void main() {
    vec3 c = texture2D(tSrc, vUv + px * vec2(-1.0, -1.0)).rgb + texture2D(tSrc, vUv + px * vec2(1.0, -1.0)).rgb
           + texture2D(tSrc, vUv + px * vec2(-1.0, 1.0)).rgb + texture2D(tSrc, vUv + px * vec2(1.0, 1.0)).rgb;
    gl_FragColor = vec4(c * 0.25, 1.0);
}`;

const FRAG_HAUT = `
precision highp float;
varying vec2 vUv;
uniform sampler2D tSrc;
uniform vec2 px;
void main() {
    vec3 c = texture2D(tSrc, vUv).rgb * 4.0;
    c += (texture2D(tSrc, vUv + px * vec2(1.0, 0.0)).rgb + texture2D(tSrc, vUv - px * vec2(1.0, 0.0)).rgb
        + texture2D(tSrc, vUv + px * vec2(0.0, 1.0)).rgb + texture2D(tSrc, vUv - px * vec2(0.0, 1.0)).rgb) * 2.0;
    c += texture2D(tSrc, vUv + px).rgb + texture2D(tSrc, vUv - px).rgb
       + texture2D(tSrc, vUv + px * vec2(1.0, -1.0)).rgb + texture2D(tSrc, vUv + px * vec2(-1.0, 1.0)).rgb;
    gl_FragColor = vec4(c / 16.0, 1.0);
}`;

const FRAG_FINAL = `
precision highp float;
varying vec2 vUv;
uniform sampler2D tColor, tAO, tHalo;
uniform float aoForce, halo, exposition, contraste, saturation, vignette, temps;
uniform vec3 teinteOmbre;
vec3 filmique(vec3 x) {
    // la courbe ACES (ajustement de Narkowicz) : les hautes lumières s'enroulent au lieu de brûler
    return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
void main() {
    vec3 c = texture2D(tColor, vUv).rgb;
    float ao = mix(1.0, texture2D(tAO, vUv).r, aoForce);
    // l'occlusion teinte l'ombre (un peu de bleu du ciel) au lieu de la noircir
    c *= mix(teinteOmbre, vec3(1.0), ao);
    c += texture2D(tHalo, vUv).rgb * halo;
    c = filmique(c * exposition);
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c = mix(vec3(l), c, saturation);
    c = (c - 0.5) * contraste + 0.5;
    vec2 q = vUv - 0.5;
    c *= 1.0 - vignette * smoothstep(0.25, 0.95, dot(q, q) * 2.0);
    c = pow(max(c, 0.0), vec3(1.0 / 2.2));
    float g = fract(sin(dot(gl_FragCoord.xy + temps * 61.0, vec2(12.9898, 78.233))) * 43758.5453);
    c += (g - 0.5) / 170.0;
    gl_FragColor = vec4(c, 1.0);
}`;

const FRAG_CIEL = `
precision highp float;
varying vec3 vDir;
uniform vec3 zenith, horizon, sol, soleilDir, soleilCouleur;
void main() {
    vec3 d = normalize(vDir);
    vec3 c = d.y > 0.0 ? mix(horizon, zenith, pow(d.y, 0.45)) : mix(horizon, sol, pow(min(-d.y * 3.0, 1.0), 0.6));
    float s = max(dot(d, normalize(soleilDir)), 0.0);
    c += soleilCouleur * (pow(s, 900.0) * 60.0 + pow(s, 12.0) * 0.6);
    gl_FragColor = vec4(c, 1.0);
}`;

const CIELS = {
    jour: { zenith: [0.2, 0.42, 0.95], horizon: [0.95, 1.05, 1.15], sol: [0.3, 0.3, 0.22], soleil: [1.6, 1.45, 1.2], force: 0.62 },
    crepuscule: { zenith: [0.18, 0.28, 0.6], horizon: [1.25, 0.8, 0.5], sol: [0.24, 0.2, 0.15], soleil: [1.6, 0.95, 0.5], force: 0.55 },
    soir: { zenith: [0.02, 0.035, 0.09], horizon: [0.08, 0.1, 0.18], sol: [0.02, 0.02, 0.025], soleil: [0.35, 0.42, 0.6], force: 0.25 },
};

export class Rendu {
    constructor(THREE, renderer, scene, camera) {
        Object.assign(this, { THREE, renderer, scene, camera });
        this.niveau = this._niveauInitial();
        this.mesures = { somme: 0, n: 0, saut: 60, lents: 0 };
        this.reglages = { aoForce: 1.0, halo: 0.28, exposition: 0.78, contraste: 1.08, saturation: 1.15, vignette: 0.28 };
        this.cam2d = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
        this.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
        this.quad.frustumCulled = false;
        const mat = (fragmentShader, uniforms, extra = {}) => new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader, uniforms, depthTest: false, depthWrite: false, toneMapped: false, ...extra });
        const u = (v) => ({ value: v });
        this.m = {
            ao: mat(FRAG_AO, { tDepth: u(null), projInv: u(new THREE.Matrix4()), p11: u(1), rayon: u(1.2), intensite: u(1.6), res: u(new THREE.Vector2()) }),
            flou: mat(FRAG_FLOU_AO, { tAO: u(null), tDepth: u(null), pas: u(new THREE.Vector2()), near: u(0.5), far: u(900) }),
            seuil: mat(FRAG_SEUIL, { tColor: u(null), seuil: u(1.15) }),
            bas: mat(FRAG_BAS, { tSrc: u(null), px: u(new THREE.Vector2()) }),
            haut: mat(FRAG_HAUT, { tSrc: u(null), px: u(new THREE.Vector2()) }, { blending: THREE.AdditiveBlending, transparent: true }),
            final: mat(FRAG_FINAL, { tColor: u(null), tAO: u(null), tHalo: u(null), aoForce: u(0.9), halo: u(0.22), exposition: u(0.92), contraste: u(1.07), saturation: u(1.1),
                                     vignette: u(0.22), temps: u(0), teinteOmbre: u(new THREE.Vector3(0.1, 0.13, 0.2)) }),
        };
        this.blanc = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1);
        this.blanc.needsUpdate = true;
        this.noir = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1);
        this.noir.needsUpdate = true;
        this.cibles = null;
    }

    // Les niveaux : 3 = tout, à la finesse de l'écran ; 2 = tout, à un point par pixel ; 1 = sans occlusion ; 0 = rendu direct.
    _niveauInitial() {
        const ext = this.renderer.extensions;
        const hdr = this.renderer.capabilities.isWebGL2 && (ext.has("EXT_color_buffer_float") || ext.has("EXT_color_buffer_half_float"));
        if (!hdr) {
            return 0;
        }
        this.finesse = this.renderer.getPixelRatio();
        let memo = null;
        try {
            memo = window.sessionStorage.getItem("cultiveau_map_rendu");
        } catch {
            /* pas de stockage : on mesure */
        }
        const n = memo !== null && ["0", "1", "2", "3"].includes(memo) ? +memo : window.innerWidth < 768 ? 2 : 3;
        if (n === 2 || n === 1) {
            this.renderer.setPixelRatio(1);
        }
        return n;
    }

    /** La lumière du ciel : une carte d'environnement calculée depuis un dôme (dégradé, soleil), selon le moment. */
    ciel(mode = "jour", soleilDir = [-0.4, 0.7, 0.35]) {
        const { THREE } = this;
        const c = CIELS[mode] || CIELS.jour;
        try {
            const sceneCiel = new THREE.Scene();
            const dome = new THREE.Mesh(new THREE.SphereGeometry(50, 32, 16), new THREE.ShaderMaterial({
                side: THREE.BackSide, depthWrite: false,
                vertexShader: "varying vec3 vDir; void main() { vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
                fragmentShader: FRAG_CIEL,
                uniforms: { zenith: { value: new THREE.Vector3(...c.zenith).multiplyScalar(c.force) }, horizon: { value: new THREE.Vector3(...c.horizon).multiplyScalar(c.force) },
                            sol: { value: new THREE.Vector3(...c.sol).multiplyScalar(c.force) }, soleilDir: { value: new THREE.Vector3(...soleilDir) },
                            soleilCouleur: { value: new THREE.Vector3(...c.soleil).multiplyScalar(c.force) } },
            }));
            sceneCiel.add(dome);
            const pmrem = new THREE.PMREMGenerator(this.renderer);
            const cible = pmrem.fromScene(sceneCiel, 0.01);
            this._env?.dispose();
            this._env = cible;
            this.scene.environment = cible.texture;
            pmrem.dispose();
            dome.geometry.dispose();
            dome.material.dispose();
            this.m.final.uniforms.teinteOmbre.value.set(...(mode === "soir" ? [0.04, 0.05, 0.09] : mode === "crepuscule" ? [0.16, 0.11, 0.12] : [0.1, 0.13, 0.2]));
            return true;
        } catch (e) {
            console.warn("[Map vivante] ciel :", e);
            return false;
        }
    }

    _creerCibles() {
        const { THREE, renderer } = this;
        const t = renderer.getDrawingBufferSize(new THREE.Vector2());
        const w = Math.max(2, t.x), h = Math.max(2, t.y);
        this._liberer();
        const profondeur = new THREE.DepthTexture(w, h);
        const scene = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: 4, depthTexture: profondeur });
        const demi = (d, type = THREE.UnsignedByteType) => new THREE.WebGLRenderTarget(Math.max(2, Math.round(w / d)), Math.max(2, Math.round(h / d)), { type, depthBuffer: false });
        const halo = [2, 4, 8, 16, 32].map((d) => demi(d, THREE.HalfFloatType));
        this.cibles = { w, h, scene, profondeur, ao: demi(2), ao2: demi(2), halo };
    }
    _liberer() {
        const c = this.cibles;
        if (c) {
            [c.scene, c.ao, c.ao2, ...c.halo].forEach((r) => r.dispose());
            c.profondeur.dispose();
        }
        this.cibles = null;
    }
    mesurer() {
        this._liberer();
    }
    detruire() {
        this._liberer();
        this._env?.dispose();
        Object.values(this.m).forEach((m) => m.dispose());
        this.quad.geometry.dispose();
    }

    _passe(materiau, cible) {
        this.quad.material = materiau;
        this.renderer.setRenderTarget(cible);
        this.renderer.render(this.quad, this.cam2d);
    }

    /** Baisse la qualité d'un cran si la machine ne tient pas ~25 images par seconde, trois mesures de suite. On ne mesure
     *  que la fenêtre active (un onglet en arrière-plan est bridé par le navigateur : ce n'est pas la machine qui peine). */
    _surveiller(ms) {
        const m = this.mesures;
        if (this.niveau === 0 || ms > 200 || document.visibilityState !== "visible" || !document.hasFocus()) {
            return;
        }
        if (m.saut > 0) {
            m.saut--;
            return;
        }
        m.somme += ms;
        m.n++;
        if (m.n < 60) {
            return;
        }
        const moyenne = m.somme / m.n;
        m.somme = 0;
        m.n = 0;
        m.lents = moyenne > 40 ? (m.lents || 0) + 1 : 0;
        if (m.lents >= 3) {
            m.lents = 0;
            m.saut = 40;
            this.niveau--;
            this.renderer.setPixelRatio(this.niveau === 0 ? this.finesse : 1);
            this._liberer();
            try {
                window.sessionStorage.setItem("cultiveau_map_rendu", String(this.niveau));
            } catch {
                /* tant pis */
            }
        }
    }

    render(temps = 0, dtMs = 16) {
        const { renderer, scene, camera, m } = this;
        this._surveiller(dtMs);
        if (this.niveau === 0) {
            renderer.setRenderTarget(null);
            renderer.render(scene, camera);
            return;
        }
        try {
            if (!this.cibles) {
                this._creerCibles();
            }
            const c = this.cibles;
            const auto = renderer.autoClear;
            renderer.autoClear = true;
            renderer.setRenderTarget(c.scene);
            renderer.render(scene, camera);
            renderer.autoClear = false;
            // l'occlusion ambiante, à mi-résolution, puis un flou qui respecte les arêtes
            if (this.niveau >= 2) {
                m.ao.uniforms.tDepth.value = c.profondeur;
                m.ao.uniforms.projInv.value.copy(camera.projectionMatrixInverse);
                m.ao.uniforms.p11.value = camera.projectionMatrix.elements[5];
                m.ao.uniforms.res.value.set(c.ao.width, c.ao.height);
                this._passe(m.ao, c.ao);
                m.flou.uniforms.tDepth.value = c.profondeur;
                m.flou.uniforms.near.value = camera.near;
                m.flou.uniforms.far.value = camera.far;
                m.flou.uniforms.tAO.value = c.ao.texture;
                m.flou.uniforms.pas.value.set(1 / c.ao.width, 0);
                this._passe(m.flou, c.ao2);
                m.flou.uniforms.tAO.value = c.ao2.texture;
                m.flou.uniforms.pas.value.set(0, 1 / c.ao.height);
                this._passe(m.flou, c.ao);
            }
            // le halo : on isole le très lumineux, on le descend en cascade, on le remonte en l'additionnant
            m.seuil.uniforms.tColor.value = c.scene.texture;
            this._passe(m.seuil, c.halo[0]);
            for (let i = 1; i < c.halo.length; i++) {
                m.bas.uniforms.tSrc.value = c.halo[i - 1].texture;
                m.bas.uniforms.px.value.set(0.5 / c.halo[i - 1].width, 0.5 / c.halo[i - 1].height);
                this._passe(m.bas, c.halo[i]);
            }
            for (let i = c.halo.length - 1; i > 0; i--) {
                m.haut.uniforms.tSrc.value = c.halo[i].texture;
                m.haut.uniforms.px.value.set(1 / c.halo[i].width, 1 / c.halo[i].height);
                this._passe(m.haut, c.halo[i - 1]);
            }
            const f = m.final.uniforms, r = this.reglages;
            f.tColor.value = c.scene.texture;
            f.tAO.value = this.niveau >= 2 ? c.ao.texture : this.blanc;
            f.tHalo.value = c.halo[0].texture;
            f.aoForce.value = r.aoForce;
            f.halo.value = r.halo;
            f.exposition.value = r.exposition;
            f.contraste.value = r.contraste;
            f.saturation.value = r.saturation;
            f.vignette.value = r.vignette;
            f.temps.value = temps % 100;
            this._passe(m.final, null);
            renderer.autoClear = auto;
        } catch (e) {
            console.warn("[Map vivante] rendu photo indisponible, rendu direct :", e);
            this.niveau = 0;
            this._liberer();
            renderer.setPixelRatio(this.finesse || 1);
            renderer.autoClear = true;
            renderer.setRenderTarget(null);
            renderer.render(scene, camera);
        }
    }
}
