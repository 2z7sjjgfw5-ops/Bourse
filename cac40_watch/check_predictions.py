"""Deuxième script du suivi des prédictions : une fois l'échéance d'une
prédiction passée, va chercher le cours réel du titre à cette date précise
(historique Yahoo Finance) et complète la ligne correspondante dans
state/predictions.csv.

Usage :
    python -m cac40_watch.check_predictions

Ne nécessite aucun secret de notification : ce script ne fait qu'enregistrer
des résultats, il n'envoie jamais rien.
"""

import time
from datetime import date, timedelta

from . import config as cfg
from .data import fetch_history_range
from .predictions import read_rows, write_rows


def _is_due(row, today):
    if row.get("cours_reel_echeance"):
        return False  # déjà renseignée
    if not row.get("echeance_prevue"):
        return False
    return date.fromisoformat(row["echeance_prevue"]) <= today


def _fetch_price_on_or_after(ticker, echeance):
    end = echeance + timedelta(days=cfg.ECHEANCE_LOOKAHEAD_DAYS)
    df = fetch_history_range(ticker, echeance, end)
    if df is None or df.empty:
        return None
    return float(df["Close"].iloc[0])


def run():
    rows = read_rows(cfg.PREDICTIONS_CSV_FILE)
    if not rows:
        print("Aucune prédiction enregistrée pour le moment.")
        return

    today = date.today()
    due_rows = [r for r in rows if _is_due(r, today)]
    print(f"{len(rows)} prédiction(s) au total, {len(due_rows)} échéance(s) à vérifier aujourd'hui.")

    updated = 0
    for row in due_rows:
        ticker = row["ticker"]
        echeance = date.fromisoformat(row["echeance_prevue"])
        try:
            price_now = _fetch_price_on_or_after(ticker, echeance)
        except Exception as exc:
            print(f"[avertissement] {ticker} : échec de récupération du cours à l'échéance ({exc})")
            price_now = None

        if price_now is None:
            print(f"[info] {ticker} : pas encore de cours disponible pour l'échéance {echeance}, réessai au prochain passage.")
            continue

        cours_depart = float(row["cours_depart"])
        cours_cible = float(row["cours_cible"])
        ecart_reel_pct = (price_now - cours_depart) / cours_depart * 100
        atteint = "Oui" if price_now >= cours_cible else "Non"

        row["cours_reel_echeance"] = f"{price_now:.4f}"
        row["ecart_reel_pct"] = f"{ecart_reel_pct:.4f}"
        row["objectif_atteint"] = atteint
        updated += 1
        print(f"[résultat] {ticker} ({echeance}) : {ecart_reel_pct:+.1f}% réel, objectif {atteint.lower()}.")

        time.sleep(cfg.REQUEST_DELAY_SECONDS)

    if updated:
        write_rows(cfg.PREDICTIONS_CSV_FILE, rows)

    print(f"Vérification terminée : {updated} prédiction(s) complétée(s), {len(due_rows) - updated} en attente de données.")


if __name__ == "__main__":
    run()
