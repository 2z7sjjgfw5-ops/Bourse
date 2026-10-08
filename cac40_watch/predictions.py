"""Suivi des prédictions dans un fichier CSV lisible (state/predictions.csv).

À chaque alerte envoyée, une ligne est enregistrée avec le prix de départ, le
pourcentage de hausse prédit, le cours cible correspondant et une échéance
précise (calculée à partir de l'horizon indicatif de l'alerte). Une fois
l'échéance passée, check_predictions.py va chercher le cours réel à cette
date (historique Yahoo Finance) et complète la ligne : cours réellement
atteint, écart réel en %, objectif atteint (oui/non). generate_report.py
transforme ensuite ce CSV en page HTML (docs/index.html).
"""

import csv
import os
from datetime import datetime

import pandas as pd

COLUMNS = [
    "horodatage_alerte",
    "marche",
    "ticker",
    "nom",
    "cours_depart",
    "pourcentage_predit",
    "cours_cible",
    "echeance_prevue",
    "cours_reel_echeance",
    "ecart_reel_pct",
    "objectif_atteint",
]


def compute_echeance(alert_date, trading_days):
    """Date de l'échéance : `trading_days` séances de bourse après `alert_date`
    (approximation simple par jours ouvrés, sans tenir compte des jours fériés)."""
    bdays = pd.bdate_range(start=alert_date, periods=trading_days + 1)
    return bdays[-1].date()


def read_rows(path):
    """Lit toutes les lignes du CSV ; liste vide si le fichier n'existe pas encore."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    """Réécrit le CSV en entier (utilisé pour compléter des lignes existantes)."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in COLUMNS})


def append_row(path, row):
    """Ajoute une ligne à la fin du CSV (crée le fichier avec son en-tête si besoin)."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({col: row.get(col, "") for col in COLUMNS})


def record_prediction(path, opportunity, alert_datetime, trading_days, market_label):
    """Enregistre une nouvelle prédiction à partir d'une Opportunity (voir scoring.py)."""
    echeance = compute_echeance(alert_datetime.date(), trading_days)
    row = {
        "horodatage_alerte": alert_datetime.strftime("%Y-%m-%d %H:%M"),
        "marche": market_label,
        "ticker": opportunity.ticker,
        "nom": opportunity.name,
        "cours_depart": f"{opportunity.price:.4f}",
        "pourcentage_predit": f"{opportunity.upside_pct:.4f}",
        "cours_cible": f"{opportunity.resistance_level:.4f}",
        "echeance_prevue": echeance.isoformat(),
        "cours_reel_echeance": "",
        "ecart_reel_pct": "",
        "objectif_atteint": "",
    }
    append_row(path, row)
    return row
