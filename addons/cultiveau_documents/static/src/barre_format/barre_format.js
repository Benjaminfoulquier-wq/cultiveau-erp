/** @odoo-module **/
// La petite barre de mise en forme qui flotte au-dessus du devis et qu'on déplace à la souris.
// Elle agit sur le texte sélectionné dans le dernier éditeur riche touché (les lignes « Mise en forme »,
// les notes, les CGV) : gras, italique, souligné, couleur, police, taille. Les commandes standard passent
// par execCommand ; la police et la taille enveloppent la sélection dans un span (styles conservés à
// l'enregistrement). On mémorise la sélection pour la retrouver même après un clic sur la barre.
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";

const POLICES = [
    ["", "Police"],
    ["sans", "Moderne"], ["serif", "Classique"], ["humaniste", "Humaniste"], ["condensee", "Condensée"],
    ["bookman", "Élégante"], ["gothic", "Géométrique"], ["palatino", "Livre"], ["manuscrite", "Manuscrite"], ["mono", "Machine à écrire"],
];
const POLICES_CSS = {
    sans: "Helvetica, Arial, 'Nimbus Sans', 'DejaVu Sans', sans-serif",
    serif: "Georgia, 'Times New Roman', 'Nimbus Roman', 'DejaVu Serif', serif",
    humaniste: "'Segoe UI', Roboto, 'Noto Sans', 'DejaVu Sans', sans-serif",
    condensee: "'Roboto Condensed', 'Nimbus Sans Narrow', 'Arial Narrow', sans-serif",
    bookman: "'URW Bookman', 'Bookman Old Style', Georgia, serif",
    gothic: "'URW Gothic', 'Century Gothic', 'Nimbus Sans', 'DejaVu Sans', sans-serif",
    palatino: "P052, Palatino, 'Palatino Linotype', 'URW Palladio L', Georgia, serif",
    manuscrite: "Z003, 'URW Chancery L', 'Apple Chancery', cursive",
    mono: "'Courier New', 'Nimbus Mono PS', 'DejaVu Sans Mono', monospace",
};
const TAILLES = [["", "Taille"], ["0.8em", "Petit"], ["1em", "Normal"], ["1.25em", "Grand"], ["1.6em", "Très grand"]];

export class BarreFormat extends Component {
    static template = "cultiveau_documents.BarreFormat";
    static props = { "*": true };

    setup() {
        this.state = useState({ x: 28, y: 150, ouverte: true, drag: false });
        this.POLICES = POLICES;
        this.TAILLES = TAILLES;
        this.editeur = null; // le dernier éditeur riche touché
        this.selection = null; // la dernière sélection dans cet éditeur

        this._focusin = (ev) => {
            const ed = ev.target.closest && ev.target.closest(".odoo-editor-editable");
            if (ed) {
                this.editeur = ed;
            }
        };
        this._selchange = () => {
            const sel = window.getSelection();
            if (sel && sel.rangeCount && this.editeur && this.editeur.isConnected && this.editeur.contains(sel.getRangeAt(0).commonAncestorContainer)) {
                this.selection = sel.getRangeAt(0).cloneRange();
            }
        };
        this._move = (ev) => {
            if (this.state.drag) {
                this.state.x = Math.max(4, ev.clientX - this._dx);
                this.state.y = Math.max(4, ev.clientY - this._dy);
            }
        };
        this._up = () => (this.state.drag = false);

        onMounted(() => {
            document.addEventListener("focusin", this._focusin, true);
            document.addEventListener("selectionchange", this._selchange);
            window.addEventListener("pointermove", this._move);
            window.addEventListener("pointerup", this._up);
        });
        onWillUnmount(() => {
            document.removeEventListener("focusin", this._focusin, true);
            document.removeEventListener("selectionchange", this._selchange);
            window.removeEventListener("pointermove", this._move);
            window.removeEventListener("pointerup", this._up);
        });
    }

    demarrerDrag(ev) {
        this.state.drag = true;
        this._dx = ev.clientX - this.state.x;
        this._dy = ev.clientY - this.state.y;
    }

    // --- retrouver l'éditeur et y remettre la sélection mémorisée (perdue au clic sur la barre)
    _reprendre() {
        const ed = this.editeur && this.editeur.isConnected ? this.editeur : null;
        if (!ed || !this.selection) {
            return null;
        }
        ed.focus();
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(this.selection);
        return ed;
    }
    _enregistrer(ed) {
        ed.dispatchEvent(new InputEvent("input", { bubbles: true }));
    }

    commande(nom, valeur = null) {
        const ed = this._reprendre();
        if (!ed) {
            return;
        }
        document.execCommand("styleWithCSS", false, true);
        document.execCommand(nom, false, valeur);
        this.selection = window.getSelection().rangeCount ? window.getSelection().getRangeAt(0).cloneRange() : this.selection;
        this._enregistrer(ed);
    }
    couleur(ev) {
        this.commande("foreColor", ev.target.value);
    }
    police(ev) {
        const css = POLICES_CSS[ev.target.value];
        ev.target.value = "";
        if (css) {
            this._envelopper(`font-family: ${css};`);
        }
    }
    taille(ev) {
        const v = ev.target.value;
        ev.target.value = "";
        if (v) {
            this._envelopper(`font-size: ${v};`);
        }
    }
    _envelopper(style) {
        const ed = this._reprendre();
        if (!ed) {
            return;
        }
        const sel = window.getSelection();
        if (!sel.rangeCount || sel.isCollapsed) {
            return;
        }
        const r = sel.getRangeAt(0);
        if (!ed.contains(r.commonAncestorContainer)) {
            return;
        }
        const span = document.createElement("span");
        span.setAttribute("style", style);
        try {
            r.surroundContents(span);
        } catch {
            // sélection à cheval sur plusieurs nœuds : on enveloppe le contenu extrait
            span.appendChild(r.extractContents());
            r.insertNode(span);
        }
        const nr = document.createRange();
        nr.selectNodeContents(span);
        sel.removeAllRanges();
        sel.addRange(nr);
        this.selection = nr.cloneRange();
        this._enregistrer(ed);
    }
}

registry.category("view_widgets").add("cultiveau_barre_format", { component: BarreFormat });
