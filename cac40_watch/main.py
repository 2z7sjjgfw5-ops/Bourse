"""Point d'entrée : analyse les valeurs du CAC 40 et envoie les alertes.

Usage :
    python -m cac40_watch.main            # ne fait rien si le marché parisien est fermé
    python -m cac40_watch.main --force     # force l'analyse (utile pour tester manuellement)
"""

import statistics
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import config as cfg
from .tickers import CAC40_TICKERS
from .data import fetch_history, fetch_fundamentals, fetch_index_history
from .scoring import evaluate
from .notify import send_notification
from .state import load_state, save_state, should_alert, record_alert
from . import history as history_module


def is_market_hours(now=None):
    now = now or datetime.now(ZoneInfo("Europe/Paris"))
    if now.weekday() >= 5:  # samedi=5, dimanche=6
        return False
    open_t = now.replace(hour=9, minute=0, second=0, microsecond=0)
    close_t = now.replace(hour=17, minute=30, second=0, microsecond=0)
    return open_t <= now <= close_t


def _collect_market_data():
    """Récupère l'historique et les fondamentaux de chaque valeur, plus l'indice CAC 40."""
    collected = {}
    for ticker, name in CAC40_TICKERS:
        try:
            df = fetch_history(ticker, cfg.HISTORY_PERIOD)
            if df is None or df.empty or len(df) < 60:
                print(f"[info] {ticker} : historique insuffisant, ignoré.")
                continue
            fundamentals = fetch_fundamentals(ticker)
            collected[ticker] = {"name": name, "df": df, "pe": fundamentals.get("trailing_pe"), "sector": fundamentals.get("sector")}
        except Exception as exc:
            print(f"[avertissement] {ticker} : échec de récupération des données ({exc})")
        time.sleep(cfg.REQUEST_DELAY_SECONDS)

    try:
        index_df = fetch_index_history(cfg.INDEX_TICKER, cfg.HISTORY_PERIOD)
    except Exception as exc:
        print(f"[avertissement] {cfg.INDEX_TICKER} : échec de récupération de l'indice ({exc})")
        index_df = None

    return collected, index_df


def _compute_reference_medians(collected):
    """Calcule la médiane du PER par secteur (si assez de valeurs) et une médiane globale de repli."""
    sector_pes = defaultdict(list)
    global_pes = []
    for item in collected.values():
        pe = item["pe"]
        if pe and pe > 0:
            global_pes.append(pe)
            if item["sector"]:
                sector_pes[item["sector"]].append(pe)

    sector_median = {
        sector: statistics.median(pes) for sector, pes in sector_pes.items() if len(pes) >= cfg.MIN_SECTOR_SAMPLE
    }
    global_median = statistics.median(global_pes) if global_pes else None
    return sector_median, global_median


def _reference_for(item, sector_median, global_median):
    sector = item["sector"]
    if sector and sector in sector_median:
        return sector_median[sector], sector, False
    return global_median, (sector or "inconnu"), True


def _process_followups(collected, hist, today=None):
    """Revérifie automatiquement le prix des alertes dont une échéance (1/4/6 semaines) est atteinte."""
    for alert_id, entry, followup_key in history_module.due_followups(hist, today):
        ticker = entry["ticker"]
        price_now = None
        if ticker in collected:
            price_now = float(collected[ticker]["df"]["Close"].iloc[-1])
        else:
            try:
                df = fetch_history(ticker, period="5d")
                if df is not None and not df.empty:
                    price_now = float(df["Close"].iloc[-1])
            except Exception as exc:
                print(f"[avertissement] {ticker} : échec de la revérification de prix ({exc})")
        if price_now is None:
            continue
        history_module.apply_followup(hist, alert_id, followup_key, price_now)
        print(f"[suivi] {ticker} : échéance '{followup_key}' renseignée ({price_now:.2f} EUR).")


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

    collected, index_df = _collect_market_data()
    sector_median, global_median = _compute_reference_medians(collected)

    alert_state = load_state(cfg.STATE_FILE)
    alert_hist = load_state(cfg.ALERT_HISTORY_FILE)
    alerts_sent = 0
    today = date.today()

    for ticker, item in collected.items():
        reference_median_pe, sector_name, sector_is_fallback = _reference_for(item, sector_median, global_median)
        opportunity = evaluate(
            ticker, item["name"], item["df"], item["pe"], reference_median_pe, sector_name, sector_is_fallback,
            index_df, cfg,
        )
        if not opportunity:
            continue
        if not should_alert(alert_state, ticker, opportunity.total_score, cfg.ALERT_COOLDOWN_DAYS):
            print(f"[info] {ticker} : signal déjà notifié récemment, pas de renvoi.")
            continue
        try:
            send_notification(opportunity, cfg)
            record_alert(alert_state, ticker, opportunity.total_score)
            history_module.record_alert(alert_hist, opportunity, today, cfg.FOLLOWUP_WEEKS)
            alerts_sent += 1
            print(f"[alerte] Notification envoyée pour {ticker} (score {opportunity.total_score:.1f}/10).")
        except Exception as exc:
            print(f"[erreur] Échec d'envoi de la notification pour {ticker} : {exc}")

    _process_followups(collected, alert_hist, today)

    save_state(cfg.STATE_FILE, alert_state)
    save_state(cfg.ALERT_HISTORY_FILE, alert_hist)
    print(f"Analyse terminée : {len(collected)} valeur(s) analysée(s), {alerts_sent} alerte(s) envoyée(s).")


if __name__ == "__main__":
    main()
