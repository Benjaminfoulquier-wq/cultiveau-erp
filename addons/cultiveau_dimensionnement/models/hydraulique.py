"""Les formules de l'hydraulique du réseau : vitesse, pertes de charge (Hazen-Williams), choix du diamètre, puissance de pompe."""

import math

# Diamètres du commerce, extérieur → intérieur (mm). PE 100 PN10 (SDR 17) et PVC pression PN10.
PE = {25: 20.4, 32: 26.2, 40: 32.6, 50: 40.8, 63: 51.4, 75: 61.4, 90: 73.6, 110: 90.0, 125: 102.2, 140: 114.6, 160: 130.8, 180: 147.2, 200: 163.6, 225: 184.0,
      250: 204.6, 280: 229.2, 315: 257.8}
PVC = {50: 45.2, 63: 57.0, 75: 67.8, 90: 81.4, 110: 99.4, 125: 113.0, 140: 126.6, 160: 144.6, 200: 180.8, 250: 226.2, 315: 285.0}
COEFFICIENT = 150  # Hazen-Williams, PE et PVC neufs
VITESSE_MAX = 1.5  # m/s dans les conduites enterrées
METRE_PAR_BAR = 10.2


def diametres(materiau):
    return PVC if materiau == "pvc" else PE


def vitesse(debit_m3h, d_int_mm):
    """m/s."""
    if not d_int_mm:
        return 0.0
    return (debit_m3h / 3600) / (math.pi * (d_int_mm / 1000) ** 2 / 4)


def pertes_de_charge(debit_m3h, d_int_mm, longueur_m, coefficient=COEFFICIENT, singularites=0.10):
    """Pertes linéaires de Hazen-Williams (m), majorées des singularités (coudes, tés, vannes : 10 % par défaut)."""
    if not (debit_m3h and d_int_mm and longueur_m):
        return 0.0
    q = debit_m3h / 3600
    d = d_int_mm / 1000
    lineaires = 10.67 * longueur_m * q ** 1.852 / (coefficient ** 1.852 * d ** 4.8704)
    return lineaires * (1 + singularites)


def diametre_conseille(debit_m3h, materiau="pe", vitesse_max=VITESSE_MAX):
    """Le plus petit diamètre extérieur du commerce qui tient la vitesse sous la limite ; (ext, int) en mm."""
    for ext, interieur in sorted(diametres(materiau).items()):
        if vitesse(debit_m3h, interieur) <= vitesse_max:
            return ext, interieur
    ext = max(diametres(materiau))
    return ext, diametres(materiau)[ext]


def puissance_kw(debit_m3h, hmt_m, rendement=0.65):
    """Puissance à l'arbre d'une pompe : ρ g Q H / rendement (kW)."""
    if not (debit_m3h and hmt_m):
        return 0.0
    return 1000 * 9.81 * (debit_m3h / 3600) * hmt_m / (rendement or 0.65) / 1000
