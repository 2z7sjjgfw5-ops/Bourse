"""Point d'entrée : analyse les valeurs du CAC 40 et envoie les alertes.

Usage :
    python -m cac40_watch.main            # ne fait rien si le marché parisien est fermé
    python -m cac40_watch.main --force     # force l'analyse (utile pour tester manuellement)
"""

import statistics
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config as cfg
from .tickers import CAC40_TICKERS
from .data import fetch_history, fetch_fundamentals
from .scoring import evaluate
from .notify import send_notification
from .state import load_state, save_state, should_alert, record_alert


def is_market_hours(now=None):
    now = now or datetime.now(ZoneInfo("Europe/Paris"))
    if now.weekday() >= 5:  # samedi=5, dimanche=6
        return False
    open_t = now.replace(hour=9, minute=0, second=0, microsecond=0)
    close_t = now.replace(hour=17, minute=30, second=0, microsecond=0)
    return open_t <= now <= close_t


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    force = "--force" in argv

    if not force and not is_market_hours():
        print("Marché parisien fermé : aucune analyse effectuée.")
        return

    if not cfg.NOTIFY_PROVIDER:
        print(
            "Aucun fournisseur de notification n'est configuré "
            "(secret NTFY_TOPIC, ou PUSHOVER_*, ou TELEGRAM_* manquant). "
            "Voir README.md pour la configuration."
        )
        return

    collected = {}
    pe_values = []

    for ticker, name in CAC40_TICKERS:
        try:
            df = fetch_history(ticker, cfg.HISTORY_PERIOD)
            if df is None or df.empty or len(df) < 40:
                print(f"[info] {ticker} : historique insuffisant, ignoré.")
                continue
            fundamentals = fetch_fundamentals(ticker)
            pe = fundamentals.get("trailing_pe")
            collected[ticker] = {"name": name, "df": df, "pe": pe}
            if pe and pe > 0:
                pe_values.append(pe)
        except Exception as exc:
            print(f"[avertissement] {ticker} : échec de récupération des données ({exc})")
        time.sleep(cfg.REQUEST_DELAY_SECONDS)

    peer_median_pe = statistics.median(pe_values) if pe_values else None

    state = load_state(cfg.STATE_FILE)
    alerts_sent = 0

    for ticker, item in collected.items():
        opportunity = evaluate(ticker, item["name"], item["df"], item["pe"], peer_median_pe, cfg)
        if not opportunity:
            continue
        if not should_alert(state, ticker, opportunity.score, cfg.ALERT_COOLDOWN_DAYS):
            print(f"[info] {ticker} : signal déjà notifié récemment, pas de renvoi.")
            continue
        try:
            send_notification(opportunity, cfg)
            record_alert(state, ticker, opportunity.score)
            alerts_sent += 1
            print(f"[alerte] Notification envoyée pour {ticker}.")
        except Exception as exc:
            print(f"[erreur] Échec d'envoi de la notification pour {ticker} : {exc}")

    save_state(cfg.STATE_FILE, state)
    print(f"Analyse terminée : {len(collected)} valeur(s) analysée(s), {alerts_sent} alerte(s) envoyée(s).")


if __name__ == "__main__":
    main()
