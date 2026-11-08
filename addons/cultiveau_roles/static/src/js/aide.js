/** @odoo-module **/
// Le « ? » de chaque écran : le tuto en VIDÉO d'abord (le vrai film s'il existe, sinon la page lue à voix haute, pas à pas, dans une
// scène animée), puis le texte. Jamais de lien vers l'extérieur (ni GitHub ni documentation du dépôt).
import { Component, useState, markup, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

function segmentsDepuis(aide) {
    // Ce que la voix lit, dans l'ordre : la phrase, puis chaque étape, puis chaque « par où commencer ».
    const segs = [];
    if (aide.resume) {
        segs.push(aide.resume);
    }
    const ajouter = (html) => {
        if (!html) {
            return;
        }
        const doc = new DOMParser().parseFromString(html, "text/html");
        doc.querySelectorAll("li").forEach((li) => {
            const t = li.textContent.trim();
            if (t) {
                segs.push(t);
            }
        });
    };
    ajouter(aide.etapes);
    ajouter(aide.texte);
    return segs;
}

function estYoutube(url) {
    return /youtu\.?be/i.test(url || "");
}
function embedYoutube(url) {
    const m = (url || "").match(/(?:youtu\.be\/|[?&]v=|embed\/)([A-Za-z0-9_-]{6,})/);
    return m ? `https://www.youtube-nocookie.com/embed/${m[1]}?rel=0` : url;
}

class AideDialog extends Component {
    static template = "cultiveau_roles.AideDialog";
    static components = { Dialog };
    static props = { aide: Object, close: Function };
    setup() {
        this.action = useService("action");
        this.etapesHtml = markup(this.props.aide.etapes || "");
        this.texteHtml = markup(this.props.aide.texte || "");
        this.piegesHtml = markup(this.props.aide.pieges || "");
        this.segments = segmentsDepuis(this.props.aide);
        this.video = this.props.aide.video || "";
        this.estYoutube = estYoutube(this.video);
        this.videoEmbed = this.estYoutube ? embedYoutube(this.video) : this.video;
        this.parleSupporte = typeof window !== "undefined" && "speechSynthesis" in window;
        this.state = useState({ lecture: false, index: -1, termine: false });
        onMounted(() => {
            // La vidéo à chaque fois : sans film produit pour la page, le tuto est lu à voix haute tout de suite.
            if (!this.video && this.parleSupporte && this.segments.length) {
                this.jouer();
            }
        });
        onWillUnmount(() => {
            if (this.parleSupporte) {
                window.speechSynthesis.cancel();
            }
        });
    }
    get segmentCourant() {
        return this.state.index >= 0 && this.state.index < this.segments.length ? this.segments[this.state.index] : "";
    }
    get etapeAffichee() {
        return this.state.index < 0 ? 0 : this.state.index + 1;
    }
    get progression() {
        return this.segments.length ? Math.round((this.etapeAffichee / this.segments.length) * 100) : 0;
    }
    jouer() {
        if (!this.parleSupporte || !this.segments.length) {
            return;
        }
        window.speechSynthesis.cancel();
        this.state.lecture = true;
        this.state.termine = false;
        this.state.index = -1;
        this.segments.forEach((texte, i) => {
            const u = new SpeechSynthesisUtterance(texte);
            u.lang = "fr-FR";
            u.rate = 1.0;
            u.onstart = () => { this.state.index = i; };
            if (i === this.segments.length - 1) {
                u.onend = () => { this.state.lecture = false; this.state.termine = true; };
            }
            window.speechSynthesis.speak(u);
        });
    }
    pause() {
        if (this.parleSupporte) {
            window.speechSynthesis.cancel();
        }
        this.state.lecture = false;
    }
    modifier() {
        this.pause();
        this.props.close();
        this.action.doAction({ type: "ir.actions.act_window", res_model: "cultiveau.aide", res_id: this.props.aide.id, views: [[false, "form"]], target: "new" });
    }
    fermer() {
        this.pause();
        this.props.close();
    }
}

export class AideSystray extends Component {
    static template = "cultiveau_roles.AideSystray";
    static props = {};
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ occupe: false });
    }
    get courant() {
        const c = this.action.currentController;
        const a = c && c.action;
        if (!a) {
            return { xmlid: null, modele: null, id: null, type: null };
        }
        return { xmlid: a.xml_id || a.xmlId || null, modele: a.res_model || null, id: typeof a.id === "number" ? a.id : null, type: a.type || null };
    }
    async ouvrir() {
        if (this.state.occupe) {
            return;
        }
        this.state.occupe = true;
        try {
            const { xmlid, modele, id, type } = this.courant;
            const aide = await this.orm.call("cultiveau.aide", "pour", [xmlid, modele, id, type]);
            if (!aide) {
                this.notification.add("Pas encore de tuto pour cet écran.", { type: "info" });
                return;
            }
            this.dialog.add(AideDialog, { aide });
        } finally {
            this.state.occupe = false;
        }
    }
}

registry.category("systray").add("cultiveau_roles.aide", { Component: AideSystray }, { sequence: 1 });
