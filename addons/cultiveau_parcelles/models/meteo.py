"""La météo réelle des parcelles : ETo et pluie du jour, des trois dernières semaines et de la semaine à venir (Open-Meteo, gratuit, sans clé)."""

import logging
from datetime import date, timedelta

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ADRESSE = "https://api.open-meteo.com/v1/forecast"
JOURS_PASSES = 21
JOURS_A_VENIR = 7


def station(lat, lon):
    """Les parcelles à moins de 1 km partagent la même météo : une station par carré de 0,01°."""
    return f"{round(lat, 2):.2f},{round(lon, 2):.2f}"


class MeteoJour(models.Model):
    _name = "cultiveau.meteo.jour"
    _description = "Météo d'un jour pour une station"
    _order = "station, date"

    station = fields.Char("Station", required=True, index=True)
    date = fields.Date("Jour", required=True, index=True)
    eto = fields.Float("ETo (mm)", digits=(5, 2))
    pluie = fields.Float("Pluie (mm)", digits=(5, 1))
    prevision = fields.Boolean("Prévision", help="Vrai tant que le jour n'est pas passé : la valeur est celle du modèle, elle sera remplacée par la mesure.")

    _sql_constraints = [("station_jour", "unique(station, date)", "Un seul relevé par station et par jour.")]

    @api.model
    def actualiser(self, stations, aujourdhui=None):
        """Va chercher, pour chaque station, les 21 jours passés et les 7 à venir. Renvoie le nombre de stations mises à jour."""
        aujourdhui = aujourdhui or fields.Date.context_today(self)
        faites = 0
        for st in sorted(set(stations)):
            lat, lon = (float(x) for x in st.split(","))
            try:
                reponse = requests.get(ADRESSE, params={"latitude": lat, "longitude": lon, "daily": "et0_fao_evapotranspiration,precipitation_sum",
                                                         "past_days": JOURS_PASSES, "forecast_days": JOURS_A_VENIR, "timezone": "Europe/Paris"}, timeout=25)
                reponse.raise_for_status()
                donnees = reponse.json()["daily"]
            except Exception as e:  # noqa: BLE001 — réseau, format : on garde les anciennes valeurs
                _logger.warning("Météo de la station %s : %s", st, e)
                continue
            jours = [date.fromisoformat(t[:10]) for t in donnees.get("time", [])]
            if not jours:
                continue
            existants = {r.date: r for r in self.search([("station", "=", st), ("date", ">=", min(jours)), ("date", "<=", max(jours))])}
            a_creer = []
            for jour, eto, pluie in zip(jours, donnees.get("et0_fao_evapotranspiration", []), donnees.get("precipitation_sum", [])):
                valeurs = {"eto": eto or 0.0, "pluie": pluie or 0.0, "prevision": jour >= aujourdhui}
                if jour in existants:
                    existants[jour].write(valeurs)
                else:
                    a_creer.append({"station": st, "date": jour, **valeurs})
            if a_creer:
                self.create(a_creer)
            faites += 1
        return faites

    @api.model
    def serie(self, st, debut, fin):
        """{date: (eto, pluie, prevision)} pour la station entre deux dates."""
        return {r.date: (r.eto, r.pluie, r.prevision) for r in self.search([("station", "=", st), ("date", ">=", debut), ("date", "<=", fin)])}

    @api.model
    def _cron_menage(self):
        self.search([("date", "<", fields.Date.context_today(self) - timedelta(days=400))]).unlink()
