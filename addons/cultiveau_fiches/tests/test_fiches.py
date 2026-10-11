import base64
import io
import json
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import lecture

def _pdf(lignes):
    """Un PDF d'une page, écrit à la main avec une table xref juste, lisible par PyPDF2."""
    contenu = "BT /F1 12 Tf 50 780 Td " + " 0 -20 Td ".join(f"({l}) Tj" for l in lignes) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(contenu)} >>\nstream\n{contenu}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


PDF = _pdf(["Pompe immergee serie E6S - fiche technique", "E6S30 debit 30 m3/h HMT 45 m puissance 7.5 kW 400 V",
            "E6S50 debit 50 m3/h HMT 60 m puissance 15 kW 400 V", "Refoulement DN 80 rendement 72 pourcent"])

REPONSE = {"resume": "Pompes immergées série E6S, 30 à 50 m³/h.", "references": [
    {"reference": "E6S30", "caracteristiques": {"debit_m3h": {"valeur": 30, "page": 1}, "hmt_m": {"valeur": 45, "page": 1}, "puissance_kw": {"valeur": 7.5, "page": 1}, "tension_v": {"valeur": 400, "page": 1}, "invente": {"valeur": 1}}},
    {"reference": "E6S50", "caracteristiques": {"debit_m3h": {"valeur": 50, "page": 1}, "hmt_m": {"valeur": 60, "page": 1}, "puissance_kw": {"valeur": 15, "page": 1}, "tension_v": {"valeur": 400, "page": 1}}}]}


@tagged("post_install", "-at_install")
class TestFiches(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fiche = cls.env["cultiveau.fiche"].create({"name": "Pompes E6S", "famille": "Pompes", "fichier": base64.b64encode(PDF), "fichier_nom": "e6s.pdf"})
        cls.p30 = cls.env["product.template"].create({"name": "Pompe immergée E6S30", "default_code": "E6S30", "cultiveau_fiche_id": cls.fiche.id, "list_price": 2500})
        cls.p50 = cls.env["product.template"].create({"name": "Pompe immergée E6S50", "default_code": "E6S50", "cultiveau_fiche_id": cls.fiche.id, "list_price": 3900})

    def test_texte_et_lecture(self):
        texte = self.fiche.extraire_texte()
        self.assertIn("E6S30", texte)
        self.assertIn("page 1", texte)
        with self.assertRaises(UserError):  # pas de clé
            self.fiche.action_lire()
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "cle-test")
        reponse = mock.Mock(status_code=200, json=lambda: {"choices": [{"message": {"content": json.dumps(REPONSE)}}]}, raise_for_status=lambda: None)
        with mock.patch.object(lecture.requests, "post", return_value=reponse) as post:
            self.fiche.action_lire()
        self.assertEqual(post.call_args.args[0], lecture.MISTRAL + "/chat/completions")
        self.assertIn("debit_m3h: Débit (m³/h)", post.call_args.kwargs["json"]["messages"][1]["content"])
        self.assertEqual(self.fiche.lecture_etat, "lue")
        self.assertEqual(self.fiche.famille_carac_id.name, "Pompes")
        self.assertEqual(self.p30.cultiveau_caracteristiques["debit_m3h"]["valeur"], 30)
        self.assertEqual(self.p50.cultiveau_caracteristiques["hmt_m"], {"valeur": 60, "page": 1, "fiche": self.fiche.id})
        self.assertNotIn("invente", self.p30.cultiveau_caracteristiques, "une clé hors liste est ignorée")
        self.assertIn("Débit (m³/h)", str(self.p30.cultiveau_caracteristiques_html))
        self.assertIn("p. 1", str(self.p30.cultiveau_caracteristiques_html))
        # recherche par caractéristique
        self.assertIn(self.p50, self.env["product.template"].search([("cultiveau_caracteristiques_texte", "ilike", "debit_m3h=50")]))
        # comparateur
        action = (self.p30 + self.p50).action_comparer()
        html = str(self.env["cultiveau.comparateur"].browse(action["res_id"]).html)
        self.assertIn("Hauteur manométrique", html)
        self.assertIn("table-warning", html)  # les débits diffèrent
        self.assertIn("2 500,00 €", html)
        with self.assertRaises(UserError):
            self.p30.action_comparer()

    def test_cron_sans_cle(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "")
        self.assertEqual(self.env["cultiveau.fiche"]._cron_lire(), 0)
        self.assertEqual(self.fiche.lecture_etat, "a_lire")
