# Le devis simple : stock, phases, matériel

Module `cultiveau_phases_devis` (07/11/2026). Demande de Benjamin : l'adhérent doit pouvoir faire un devis simple en
interrogeant son stock, créer des phases directement dans le devis, puis la liste du matériel ; les phases servent ensuite au
chantier.

- **Le stock sur la ligne** : colonnes « Disponible » (en stock aujourd'hui, hors ce que d'autres commandes réservent) et
  « Manque », vertes ou rouges. Bouton **Depuis mon stock** : le catalogue d'Odoo filtré sur les articles en stock, on clique, la
  ligne se pose.
- **Les phases dans le devis** : « Ajouter une phase » sous les lignes crée une section de chantier ; en ouvrant la ligne : jours
  prévus et jalon (% du devis). Le matériel et la pose se mettent dessous, comme dans un lot. L'onglet Lots et sous-totaux montre
  le tableau des phases (jours, jalon, articles, heures de pose) et permet de régler jours et jalons en ligne. Les lots et
  sous-lots ordinaires continuent d'exister ; un lot ordinaire ferme la phase en cours.
- **Le chantier reprend tout** : à la confirmation (ou « Lancer le chantier »), les phases du devis remplacent les quatre phases
  type : ordre, dates à la suite à partir de la date d'engagement du devis (jours ouvrés simplifiés en jours), jalon, heures
  prévues (lignes de pose en heures sous la phase), et le matériel de chaque phase lui est rattaché ; les dates de besoin pour les
  achats et la facturation à l'avancement en découlent.

Sans phase dans le devis, rien ne change : le chantier prend les quatre phases type.
