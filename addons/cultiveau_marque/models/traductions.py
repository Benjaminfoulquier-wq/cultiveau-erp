"""Le nom de l'éditeur n'apparaît dans aucune phrase traduite, ni côté navigateur (« Odoo enverra des notifications à ce
périphérique ! ») ni côté serveur (messages, courriels, erreurs) : les traductions chargées depuis les fichiers .po des
modules sont réécrites une fois, au chargement, et l'empreinte des traductions web change avec elles, donc le navigateur
les recharge. Tout module, présent ou futur, est couvert sans rien lister."""
import re

from odoo.tools import translate
from odoo.tools.misc import ReadonlyDict

EDITEUR = re.compile(r"\b(Odoo|ODOO)\b")
SITE_EDITEUR = re.compile(r"(?i)(https?://)?(www\.)?odoo\.com[^\s\"'<>)]*")


def sans_editeur_phrase(texte):
    if not isinstance(texte, str) or "odoo" not in texte.lower():
        return texte
    texte = SITE_EDITEUR.sub("https://www.cultiveau.fr", texte)
    return EDITEUR.sub("Cultiveau", texte)


_charger_python = translate.CodeTranslations._load_python_translations
_charger_web = translate.CodeTranslations._load_web_translations


def _load_python_translations(self, module_name, lang):
    _charger_python(self, module_name, lang)
    cle = (module_name, lang)
    self.python_translations[cle] = ReadonlyDict({src: sans_editeur_phrase(val) for src, val in self.python_translations[cle].items()})


def _load_web_translations(self, module_name, lang):
    _charger_web(self, module_name, lang)
    cle = (module_name, lang)
    messages = self.web_translations[cle].get("messages", ())
    self.web_translations[cle] = ReadonlyDict({"messages": tuple(ReadonlyDict({"id": m["id"], "string": sans_editeur_phrase(m["string"])}) for m in messages)})


if not getattr(translate.CodeTranslations, "_cultiveau_sans_editeur", False):
    translate.CodeTranslations._load_python_translations = _load_python_translations
    translate.CodeTranslations._load_web_translations = _load_web_translations
    translate.CodeTranslations._cultiveau_sans_editeur = True
    # ce qui a déjà été chargé avant ce module l'a été avec le nom de l'éditeur : on repart de zéro
    translate.code_translations.python_translations.clear()
    translate.code_translations.web_translations.clear()
