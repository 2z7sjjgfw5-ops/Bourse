"""Persistance de l'état d'armement des alertes, pour n'alerter qu'une fois
par franchissement de seuil (et non à chaque run tant que le score reste
au-dessus du seuil).

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


def is_armed(state, ticker):
    """Une valeur est "armée" si elle peut déclencher une nouvelle alerte —
    par défaut (jamais vue), elle l'est toujours."""
    return state.get(ticker, {}).get("armed", True)


def rearm_if_below_threshold(state, ticker, total_score, threshold):
    """À appeler à chaque run pour CHAQUE valeur dont le score a pu être calculé,
    qu'une alerte soit envoyée ou non : dès que le score repasse sous le seuil,
    la valeur est réarmée pour pouvoir re-déclencher au prochain franchissement."""
    if total_score < threshold:
        state.setdefault(ticker, {})["armed"] = True
        state[ticker]["last_score"] = total_score


def disarm(state, ticker, score):
    """À appeler quand une alerte vient d'être envoyée : désarme la valeur pour
    qu'elle ne redéclenche pas tant que le score reste au-dessus du seuil."""
    state[ticker] = {"armed": False, "last_score": score, "date": date.today().isoformat()}
