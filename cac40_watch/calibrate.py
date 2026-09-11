"""Outil de calibration : calcule la distribution réelle des scores de confiance
sur l'historique récent, pour choisir un seuil de déclenchement justifié par les
données plutôt qu'arbitraire (voir README.md, section calibration).

Usage :
    python -m cac40_watch.calibrate

Ne nécessite aucun secret de notification : ce script n'envoie jamais
d'alerte, il se contente d'imprimer un rapport dans les logs.
"""

import statistics
import time
from collections import defaultdict

from . import config as cfg
from .tickers import CAC40_TICKERS
from .data import fetch_history, fetch_fundamentals, fetch_index_history
from .scoring import compute_opportunity, blended_reference_pe

LOOKBACK_DAYS = 90  # nombre de jours (les plus récents) rejoués pour la calibration
CANDIDATE_THRESHOLDS = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]


def _collect():
    collected = {}
    for ticker, name in CAC40_TICKERS:
        try:
            df = fetch_history(ticker, cfg.HISTORY_PERIOD)
            if df is None or df.empty or len(df) < 100:
                continue
            fundamentals = fetch_fundamentals(ticker)
            collected[ticker] = {"name": name, "df": df, "pe": fundamentals.get("trailing_pe"), "sector": fundamentals.get("sector")}
        except Exception as exc:
            print(f"[avertissement] {ticker} : {exc}")
        time.sleep(cfg.REQUEST_DELAY_SECONDS)

    try:
        index_df = fetch_index_history(cfg.INDEX_TICKER, cfg.HISTORY_PERIOD)
    except Exception as exc:
        print(f"[avertissement] indice : {exc}")
        index_df = None

    return collected, index_df


def _reference_medians_for_day(collected, day_idx):
    """Recalcule les médianes sectorielles/globales en utilisant seulement les données
    disponibles jusqu'au jour `day_idx` (pas de données futures)."""
    sector_pes = defaultdict(list)
    global_pes = []
    for item in collected.values():
        df = item["df"]
        if day_idx >= len(df):
            continue
        pe = item["pe"]  # le PER courant de yfinance ne peut pas être reconstitué a posteriori ;
        # on utilise le PER actuel comme approximation pour toute la période rejouée.
        if pe and pe > 0:
            global_pes.append(pe)
            if item["sector"]:
                sector_pes[item["sector"]].append(pe)
    sector_median = {s: statistics.median(p) for s, p in sector_pes.items()}
    sector_count = {s: len(p) for s, p in sector_pes.items()}
    global_median = statistics.median(global_pes) if global_pes else None
    return sector_median, sector_count, global_median


def _report_sector_coverage(collected):
    """Affiche la couverture sectorielle réelle et le poids qu'elle obtient dans la
    référence pondérée (rétrécissement statistique, voir config.PER_SHRINKAGE_K),
    pour vérifier honnêtement si la comparaison au secteur pèse effectivement quelque chose."""
    sector_pes = defaultdict(list)
    no_sector = []
    no_pe = []
    for ticker, item in collected.items():
        if not item["sector"]:
            no_sector.append(ticker)
            continue
        if item["pe"] and item["pe"] > 0:
            sector_pes[item["sector"]].append(ticker)
        else:
            no_pe.append(ticker)

    print(f"\nCouverture sectorielle ({len(collected)} valeurs au total, k={cfg.PER_SHRINKAGE_K}) :")
    for sector, members in sorted(sector_pes.items(), key=lambda kv: -len(kv[1])):
        n = len(members)
        weight_pct = 100 * n / (n + cfg.PER_SHRINKAGE_K)
        print(f"  {sector:<30} {n:>2} valeur(s) avec PER valide -> poids du secteur dans la référence : {weight_pct:.0f}%")
    if no_sector:
        print(f"  Secteur inconnu (non fourni par Yahoo Finance) : {', '.join(no_sector)}")
    if no_pe:
        print(f"  PER indisponible ou négatif (exclu du calcul) : {', '.join(no_pe)}")


def run():
    print(f"Calibration sur les {LOOKBACK_DAYS} derniers jours de bourse, {len(CAC40_TICKERS)} valeurs suivies.")
    collected, index_df = _collect()
    if not collected:
        print("Aucune donnée récupérée, calibration impossible.")
        return

    _report_sector_coverage(collected)

    all_scores = []
    per_ticker_alert_days = defaultdict(int)

    min_len = min(len(item["df"]) for item in collected.values())
    start = max(cfg.MACD_SLOW + cfg.MACD_SIGNAL + 5, min_len - LOOKBACK_DAYS)

    for day_idx in range(start, min_len):
        sector_median, sector_count, global_median = _reference_medians_for_day(collected, day_idx)
        for ticker, item in collected.items():
            df_slice = item["df"].iloc[: day_idx + 1]
            if len(df_slice) < 60:
                continue
            sector = item["sector"]
            n = sector_count.get(sector, 0) if sector else 0
            reference_median_pe = blended_reference_pe(sector_median.get(sector), n, global_median, cfg.PER_SHRINKAGE_K)
            sector_name = sector or "inconnu"

            opp = compute_opportunity(
                ticker, item["name"], df_slice, item["pe"], reference_median_pe, sector_name,
                n, index_df, cfg,
            )
            if opp is None:
                continue
            all_scores.append(opp.total_score)
            for threshold in CANDIDATE_THRESHOLDS:
                if opp.total_score >= threshold:
                    per_ticker_alert_days[(ticker, threshold)] += 1

    if not all_scores:
        print("Aucun score calculable (support/résistance non détectés) sur la période.")
        return

    all_scores.sort()
    n = len(all_scores)
    print(f"\n{n} scores calculés (toutes valeurs, tous jours confondus, {min_len - start} jours rejoués).")
    print("Distribution :")
    for p in [50, 75, 90, 95, 99]:
        idx = min(n - 1, int(n * p / 100))
        print(f"  percentile {p:>2} : {all_scores[idx]:.2f}/10")
    print(f"  maximum observé : {all_scores[-1]:.2f}/10")

    weeks_covered = (min_len - start) / 5  # ~5 séances de bourse par semaine
    print("\nEstimation du nombre d'alertes par semaine, par seuil candidat :")
    for threshold in CANDIDATE_THRESHOLDS:
        total_alert_days = sum(v for (t, th), v in per_ticker_alert_days.items() if th == threshold)
        per_week = total_alert_days / weeks_covered if weeks_covered else 0
        print(f"  seuil {threshold:.1f}/10 -> ~{per_week:.1f} alertes/semaine (toutes valeurs confondues)")


if __name__ == "__main__":
    run()
