"""Le téléphone-douchette : une page mobile qui lit les codes-barres et les pousse au comptoir du bureau.

L'utilisateur ouvre /comptoir/scanner sur son téléphone (même compte que le bureau). Chaque code lu part
au serveur, qui retrouve l'article et l'envoie en direct, par le bus, à l'écran du comptoir ouvert ailleurs.
"""
import json

from odoo import http
from odoo.http import request

PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"/>
<meta name="theme-color" content="#1d3a52"/>
<title>Scanner — Comptoir</title>
<style>
 :root{color-scheme:dark}
 *{box-sizing:border-box}
 body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1b26;color:#eef3f7}
 header{padding:14px 16px;background:#1d3a52;display:flex;align-items:center;gap:10px;position:sticky;top:0}
 header b{font-size:17px}
 header .cpt{margin-left:auto;background:#2a7f8f;border-radius:999px;padding:3px 11px;font-weight:700;font-size:14px}
 #vue{position:relative;width:100%;aspect-ratio:3/4;background:#000;overflow:hidden}
 #cam{width:100%;height:100%;object-fit:cover}
 #viseur{position:absolute;inset:18% 12%;border:3px solid rgba(255,255,255,.85);border-radius:16px;box-shadow:0 0 0 2000px rgba(0,0,0,.28)}
 #flash{position:absolute;inset:0;background:#2ec28b;opacity:0;transition:opacity .25s}
 #flash.on{opacity:.55}
 .corps{padding:16px}
 .msg{min-height:52px;display:flex;flex-direction:column;justify-content:center;background:#17293a;border-radius:12px;padding:10px 14px;margin-bottom:14px}
 .msg .nom{font-weight:700;font-size:16px}
 .msg .sous{color:#9fb4c4;font-size:13px}
 .msg.ok{background:#14402f}
 .msg.ko{background:#4a1f24}
 form{display:flex;gap:8px}
 input{flex:1;font-size:17px;padding:12px 14px;border-radius:12px;border:1px solid #2c4050;background:#0c1620;color:#eef3f7}
 button{font-size:16px;font-weight:700;padding:12px 16px;border-radius:12px;border:0;background:#2a7f8f;color:#fff}
 .aide{color:#7f95a6;font-size:13px;margin-top:14px;line-height:1.5}
</style>
</head>
<body>
<header><b>📱 Scanner</b><span id="client"></span><span class="cpt" id="cpt">0</span></header>
<div id="vue"><video id="cam" playsinline muted autoplay></video><div id="viseur"></div><div id="flash"></div></div>
<div class="corps">
 <div class="msg" id="msg"><div class="nom">Visez un code-barres</div><div class="sous">ou saisissez-le à la main ci-dessous</div></div>
 <form id="saisie"><input id="code" inputmode="text" autocomplete="off" placeholder="Code-barres ou référence" autofocus/><button type="submit">Ajouter</button></form>
 <p class="aide">Le comptoir doit être ouvert sur l'ordinateur, sur le même compte. Chaque code lu s'ajoute au panier là-bas, en direct. La douchette Bluetooth marche aussi : elle écrit dans le champ et valide.</p>
</div>
<script>
const $=s=>document.querySelector(s);
let envoi=0, dernier="", dernierT=0;
function flash(){const f=$("#flash");f.classList.add("on");setTimeout(()=>f.classList.remove("on"),220);}
function afficher(cls,nom,sous){const m=$("#msg");m.className="msg "+cls;m.innerHTML='<div class="nom">'+nom+'</div><div class="sous">'+(sous||"")+'</div>';}
async function pousser(code){
  code=(code||"").trim(); if(!code) return;
  const t=Date.now(); if(code===dernier && t-dernierT<1500) return; dernier=code; dernierT=t;
  try{
    const r=await fetch('/comptoir/scanner/push',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jsonrpc:"2.0",method:"call",params:{code:code}})});
    const d=(await r.json()).result||{};
    if(d.ok){flash(); if(navigator.vibrate)navigator.vibrate(60); envoi++; $("#cpt").textContent=envoi;
      afficher("ok","✓ "+d.nom, (d.stock!=null?("stock "+d.stock+" · "):"")+"ajouté au comptoir");}
    else if(d.raison==="introuvable"){if(navigator.vibrate)navigator.vibrate([40,60,40]); afficher("ko","Introuvable", "aucun article pour « "+code+" »");}
  }catch(e){afficher("ko","Hors ligne","réessayez");}
}
$("#saisie").addEventListener("submit",e=>{e.preventDefault();const c=$("#code");pousser(c.value);c.value="";c.focus();});
// caméra + lecture native des codes-barres (Chrome Android)
(async()=>{
  if(!('BarcodeDetector' in window)){afficher("", "Caméra non disponible", "saisissez le code à la main, la douchette marche aussi");return;}
  try{
    const flux=await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});
    const v=$("#cam"); v.srcObject=flux; await v.play();
    const det=new BarcodeDetector({formats:["ean_13","ean_8","code_128","code_39","upc_a","upc_e","itf","codabar"]});
    const boucle=async()=>{
      try{const codes=await det.detect(v); if(codes && codes.length){pousser(codes[0].rawValue);}}catch(e){}
      setTimeout(boucle,350);
    };
    boucle();
  }catch(e){afficher("", "Caméra refusée", "autorisez la caméra, ou saisissez à la main");}
})();
</script>
</body>
</html>"""


class ScannerComptoir(http.Controller):
    @http.route("/comptoir/scanner", type="http", auth="user", website=False)
    def page(self, **kw):
        nom = request.env.company.name
        html = PAGE.replace('<span id="client"></span>', f'<span id="client" style="color:#9fb4c4;font-size:13px">{nom}</span>')
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/comptoir/scanner/push", type="json", auth="user")
    def push(self, code=None, partner_id=None, **kw):
        return request.env["cultiveau.comptoir"].scanner_pousser(code, partner_id)
