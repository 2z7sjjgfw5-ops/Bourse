"""Historique de suivi des alertes envoyées, pour calculer à terme un taux de
réussite réel du système.

Chaque alerte envoyée est enregistrée avec le prix du moment ; son prix réel
est ensuite revérifié automatiquement à 1, 4 et 6 semaines (voir
config.FOLLOWUP_WEEKS), sans aucune action manuelle : main.py balaie ce
fichier à chaque exécution et complète les échéances atteintes.

Fichier utilisé : state/alert_history.json (voir config.ALERT_HISTORY_FILE).
Il est committé par le workflow GitHub Actions exactement comme
state/last_alerts.json, avec les mêmes permissions ("contents: write") déjà
activées — aucune configuration supplémentaire n'est nécessaire.
"""

from datetime import date, timedelta


def _followup_key(weeks):
    return f"{weeks}_semaine" if weeks == 1 else f"{weeks}_semaines"


def record_alert(history, opportunity, alert_date, followup_weeks):
    """Ajoute une entrée d'historique pour une alerte qui vient d'être envoyée."""
    alert_id = f"{opportunity.ticker}_{alert_date.isoformat()}"
    followups = {
        _followup_key(weeks): {
            "due_date": (alert_date + timedelta(weeks=weeks)).isoformat(),
            "done": False,
            "price": None,
            "actual_change_pct": None,
            "checked_date": None,
        }
        for weeks in followup_weeks
    }
    history[alert_id] = {
        "ticker": opportunity.ticker,
        "name": opportunity.name,
        "alert_date": alert_date.isoformat(),
        "price_at_alert": opportunity.price,
        "score": opportunity.total_score,
        "upside_announced_pct": opportunity.upside_pct,
        "followups": followups,
    }
    return alert_id


def due_followups(history, today=None):
    """Liste les échéances de suivi atteintes et pas encore renseignées.

    Retourne une liste de tuples (alert_id, entry, followup_key).
    """
    today = today or date.today()
    due = []
    for alert_id, entry in history.items():
        for key, followup in entry.get("followups", {}).items():
            if followup["done"]:
                continue
            due_date = date.fromisoformat(followup["due_date"])
            if today >= due_date:
                due.append((alert_id, entry, key))
    return due


def apply_followup(history, alert_id, followup_key, price_now, checked_date=None):
    """Renseigne le résultat d'une échéance de suivi avec le prix réel observé."""
    checked_date = checked_date or date.today()
    entry = history[alert_id]
    followup = entry["followups"][followup_key]
    price_at_alert = entry["price_at_alert"]
    actual_change_pct = (price_now - price_at_alert) / price_at_alert * 100
    followup.update(
        {
            "done": True,
            "price": price_now,
            "actual_change_pct": actual_change_pct,
            "checked_date": checked_date.isoformat(),
        }
    )
