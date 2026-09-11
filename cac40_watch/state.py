"""Persistance simple de l'historique des alertes, pour éviter les doublons.

L'état est un fichier JSON committé dans le dépôt par le workflow GitHub
Actions après chaque exécution (voir .github/workflows/cac40_monitor.yml).
"""

import json
import os
from datetime import date


def load_state(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_state(path, state):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def should_alert(state, ticker, score, cooldown_days):
    """Autorise une alerte si aucune n'a été envoyée récemment, ou si le signal s'est renforcé."""
    last = state.get(ticker)
    if not last:
        return True
    try:
        last_date = date.fromisoformat(last["date"])
    except (KeyError, ValueError):
        return True
    days_since = (date.today() - last_date).days
    if days_since >= cooldown_days:
        return True
    return score > last.get("score", 0)


def record_alert(state, ticker, score):
    state[ticker] = {"date": date.today().isoformat(), "score": score}
