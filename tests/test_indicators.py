"""Tests avec des données synthétiques (aucun accès réseau requis)."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cac40_watch.indicators import (
    find_support_resistance,
    find_multi_window_levels,
    volume_signal,
    valuation_ratio,
    rsi,
    macd,
    compute_beta,
    horizon_bucket,
    horizon_trading_days,
    atr_multiplier,
    atr,
)
from cac40_watch.scoring import (
    _linear_fraction,
    blended_reference_pe,
    compute_opportunity,
    evaluate,
    family_scores,
    families_confirm,
)
from cac40_watch import config as cfg
from cac40_watch import predictions
from cac40_watch import check_predictions
from cac40_watch import generate_report
from cac40_watch import state as state_module


def make_df(closes, volumes=None, high_pad=0.5, low_pad=0.5):
    volumes = volumes or [1_000_000] * len(closes)
    data = {
        "Open": closes,
        "High": [c + high_pad for c in closes],
        "Low": [c - low_pad for c in closes],
        "Close": closes,
        "Volume": volumes,
    }
    return pd.DataFrame(data)


def make_dated_df(closes, freq="D"):
    index = pd.date_range(start="2024-01-01", periods=len(closes), freq=freq)
    return pd.DataFrame({"Close": closes}, index=index)


def ranging_closes(cycles=6, extra_tail=None):
    closes = []
    for _ in range(cycles):
        closes += [100, 96, 100, 104, 100]
    if extra_tail is not None:
        closes += extra_tail
    return closes


# --- support / résistance (single & multi-fenêtres) -------------------------------


def test_find_support_resistance_detects_range():
    closes = ranging_closes(extra_tail=[96.5])
    df = make_df(closes)

    result = find_support_resistance(df, current_price=closes[-1], order=2, cluster_pct=0.02)

    assert result is not None
    assert result["support"] < closes[-1] < result["resistance"]


def test_find_multi_window_levels_confirms_across_windows():
    closes = ranging_closes(cycles=10, extra_tail=[96.5])
    df = make_df(closes)

    levels = find_multi_window_levels(df, closes[-1], windows=[2, 3, 4], cluster_pct=0.02, confirm_cluster_pct=0.02)

    assert levels is not None
    assert levels["support"] is not None
    assert levels["resistance"] is not None
    assert 1 <= levels["support"]["confirmations"] <= 3
    assert levels["support"]["total_windows"] == 3


def test_find_multi_window_levels_none_when_too_short():
    df = make_df([100, 101, 99])
    assert find_multi_window_levels(df, 100, [2, 4, 8], 0.02, 0.02) is None


# --- volume -------------------------------------------------------------------------


def test_volume_signal_ratio():
    volumes = [1_000_000] * 20 + [3_000_000]
    df = make_df([100] * len(volumes), volumes=volumes)

    result = volume_signal(df, lookback=20)

    assert result is not None
    assert result["ratio"] == pytest.approx(3.0)


def test_volume_signal_insufficient_data():
    df = make_df([100] * 5, volumes=[1_000_000] * 5)
    assert volume_signal(df, lookback=20) is None


# --- PER ------------------------------------------------------------------------------


def test_blended_reference_pe_weights_by_sample_size():
    # Grand échantillon sectoriel : la référence est proche de la médiane du secteur.
    ref_large = blended_reference_pe(sector_median_pe=10.0, sector_sample_size=20, global_median_pe=20.0, k=4.0)
    assert ref_large == pytest.approx(10.0 * 20 / 24 + 20.0 * 4 / 24)
    assert ref_large < 12.0

    # Petit échantillon : la référence reste proche de la médiane globale.
    ref_small = blended_reference_pe(sector_median_pe=10.0, sector_sample_size=1, global_median_pe=20.0, k=4.0)
    assert ref_small == pytest.approx(10.0 * 1 / 5 + 20.0 * 4 / 5)
    assert ref_small > 17.0


def test_blended_reference_pe_handles_missing_data():
    assert blended_reference_pe(None, 0, 20.0, 4.0) == pytest.approx(20.0)
    assert blended_reference_pe(10.0, 5, None, 4.0) == pytest.approx(10.0)
    assert blended_reference_pe(None, 0, None, 4.0) is None


def test_valuation_ratio():
    assert valuation_ratio(10, 20) == pytest.approx(0.5)
    assert valuation_ratio(None, 20) is None
    assert valuation_ratio(10, None) is None
    assert valuation_ratio(-5, 20) is None


# --- RSI --------------------------------------------------------------------------------


def test_rsi_monotonic_increase_is_100():
    closes = [100 + i for i in range(30)]
    df = make_df(closes)
    assert rsi(df, period=14) == pytest.approx(100.0)


def test_rsi_monotonic_decrease_is_0():
    closes = [100 - i for i in range(30)]
    df = make_df(closes)
    assert rsi(df, period=14) == pytest.approx(0.0)


def test_rsi_insufficient_data_returns_none():
    df = make_df([100, 101, 102])
    assert rsi(df, period=14) is None


# --- MACD -------------------------------------------------------------------------------


def test_macd_recent_uptrend_has_positive_histogram():
    # Plat puis forte accélération haussière récente : le MACD doit monter plus
    # vite que sa propre moyenne (ligne de signal) -> histogramme positif.
    closes = [100.0] * 30 + [100 * (1.03 ** i) for i in range(1, 31)]
    df = make_df(closes)
    result = macd(df)
    assert result is not None
    assert result["histogram"] > 0


def test_macd_recent_downtrend_has_negative_histogram():
    # Plat puis forte accélération baissière récente : histogramme négatif.
    closes = [100.0] * 30 + [100 * (0.97 ** i) for i in range(1, 31)]
    df = make_df(closes)
    result = macd(df)
    assert result is not None
    assert result["histogram"] < 0


def test_macd_insufficient_data_returns_none():
    df = make_df([100] * 10)
    assert macd(df) is None


# --- bêta -------------------------------------------------------------------------------


def test_compute_beta_matches_known_slope():
    n_weeks = 16
    index_returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, 0.0, 0.03, -0.015, 0.01, 0.02, -0.005, 0.01, -0.02, 0.015]
    assert len(index_returns) == n_weeks - 1

    index_prices = [100.0]
    stock_prices = [50.0]
    for r in index_returns:
        index_prices.append(index_prices[-1] * (1 + r))
        stock_prices.append(stock_prices[-1] * (1 + 2 * r))  # bêta théorique = 2, sans bruit

    index_df = make_dated_df(index_prices, freq="W")
    stock_df = make_dated_df(stock_prices, freq="W")

    beta = compute_beta(stock_df, index_df, min_points=10)

    assert beta == pytest.approx(2.0, rel=1e-6)


def test_compute_beta_none_when_too_few_points():
    index_df = make_dated_df([100, 101, 102], freq="W")
    stock_df = make_dated_df([50, 51, 52], freq="W")
    assert compute_beta(stock_df, index_df, min_points=10) is None


# --- horizon ------------------------------------------------------------------------------


def test_horizon_bucket_scales_with_upside():
    assert "semaine" in horizon_bucket(2)
    assert "2 à 3 semaines" in horizon_bucket(5)
    assert "4 à 6 semaines" in horizon_bucket(10)


# --- fraction linéaire (cœur du score continu) ---------------------------------------------


def test_linear_fraction_increasing():
    # plus `value` est grand, plus la fraction est grande (ex. ratio de volume)
    assert _linear_fraction(1.0, full_credit_value=3.0, zero_credit_value=1.0) == pytest.approx(0.0)
    assert _linear_fraction(3.0, full_credit_value=3.0, zero_credit_value=1.0) == pytest.approx(1.0)
    assert _linear_fraction(2.0, full_credit_value=3.0, zero_credit_value=1.0) == pytest.approx(0.5)


def test_linear_fraction_decreasing():
    # plus `value` est petit, plus la fraction est grande (ex. distance au support, RSI)
    assert _linear_fraction(0.3, full_credit_value=0.3, zero_credit_value=3.0) == pytest.approx(1.0)
    assert _linear_fraction(3.0, full_credit_value=0.3, zero_credit_value=3.0) == pytest.approx(0.0)


def test_linear_fraction_clamped_outside_range():
    assert _linear_fraction(-10, full_credit_value=3.0, zero_credit_value=1.0) == pytest.approx(0.0)
    assert _linear_fraction(100, full_credit_value=3.0, zero_credit_value=1.0) == pytest.approx(1.0)


# --- score composite / evaluate ------------------------------------------------------------


def test_compute_opportunity_end_to_end():
    closes = ranging_closes(cycles=10, extra_tail=[96.5])
    volumes = [1_000_000] * (len(closes) - 1) + [3_000_000]
    df = make_df(closes, volumes=volumes)

    opp = compute_opportunity(
        "TEST.PA", "Test SA", df, pe=10, reference_median_pe=20, sector_name="Test",
        sector_sample_size=6, index_df=None, cfg=cfg,
    )

    assert opp is not None
    assert 0 <= opp.total_score <= 10
    assert opp.scores["support"] > 0
    assert opp.scores["volume"] > 0
    assert opp.scores["per"] > 0
    assert opp.beta is None  # pas d'indice fourni dans ce test


def test_evaluate_none_below_threshold():
    # Score volontairement faible : prix loin de tout support (peu de fenêtres/faible ratio)
    closes = ranging_closes(cycles=3, extra_tail=[103.9])  # proche de la résistance, pas du support
    df = make_df(closes)

    result = evaluate(
        "TEST.PA", "Test SA", df, pe=None, reference_median_pe=None, sector_name="inconnu",
        sector_sample_size=0, index_df=None, cfg=cfg,
    )
    assert result is None


# --- horizon en jours de bourse (pour l'échéance des prédictions) --------------------------


def test_horizon_trading_days_matches_horizon_bucket_thresholds():
    assert horizon_trading_days(2, cfg) == cfg.HORIZON_DAYS_SHORT
    assert horizon_trading_days(5, cfg) == cfg.HORIZON_DAYS_MEDIUM
    assert horizon_trading_days(10, cfg) == cfg.HORIZON_DAYS_LONG


# --- suivi des prédictions (CSV) ------------------------------------------------------------


class _FakeOpportunity:
    def __init__(self, ticker, name, price, upside_pct, resistance_level):
        self.ticker = ticker
        self.name = name
        self.price = price
        self.upside_pct = upside_pct
        self.resistance_level = resistance_level


def test_compute_echeance_skips_weekends():
    # Vendredi 2024-01-05 + 1 séance de bourse -> lundi 2024-01-08 (pas samedi).
    assert predictions.compute_echeance(date(2024, 1, 5), 1) == date(2024, 1, 8)


def test_record_and_read_prediction(tmp_path):
    csv_path = str(tmp_path / "predictions.csv")
    opp = _FakeOpportunity("TEST.PA", "Test SA", price=100.0, upside_pct=5.0, resistance_level=105.0)
    alert_dt = datetime(2024, 1, 2, 10, 30)

    predictions.record_prediction(csv_path, opp, alert_dt, trading_days=5, market_label="CAC40")
    rows = predictions.read_rows(csv_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "TEST.PA"
    assert row["marche"] == "CAC40"
    assert float(row["cours_depart"]) == pytest.approx(100.0)
    assert float(row["cours_cible"]) == pytest.approx(105.0)
    assert row["cours_reel_echeance"] == ""


def test_check_predictions_is_due():
    row_due = {"echeance_prevue": "2024-01-01", "cours_reel_echeance": ""}
    row_not_yet = {"echeance_prevue": "2099-01-01", "cours_reel_echeance": ""}
    row_already_done = {"echeance_prevue": "2024-01-01", "cours_reel_echeance": "12.0"}

    today = date(2024, 6, 1)
    assert check_predictions._is_due(row_due, today) is True
    assert check_predictions._is_due(row_not_yet, today) is False
    assert check_predictions._is_due(row_already_done, today) is False


def test_generate_report_classifies_rows(tmp_path):
    csv_path = str(tmp_path / "predictions.csv")
    output_path = str(tmp_path / "report.html")
    rows = [
        # Objectif largement atteint -> vert
        {"horodatage_alerte": "2024-01-03 10:00", "marche": "CAC40", "ticker": "AAA.PA", "nom": "A SA",
         "cours_depart": "100", "pourcentage_predit": "5.0", "cours_cible": "105", "echeance_prevue": "2024-01-10",
         "cours_reel_echeance": "110", "ecart_reel_pct": "10.0", "objectif_atteint": "Oui"},
        # Objectif manqué nettement -> rouge
        {"horodatage_alerte": "2024-01-02 10:00", "marche": "CAC40", "ticker": "BBB.PA", "nom": "B SA",
         "cours_depart": "100", "pourcentage_predit": "5.0", "cours_cible": "105", "echeance_prevue": "2024-01-09",
         "cours_reel_echeance": "100", "ecart_reel_pct": "0.0", "objectif_atteint": "Non"},
        # Manqué de peu -> orange
        {"horodatage_alerte": "2024-01-01 10:00", "marche": "CAC40", "ticker": "CCC.PA", "nom": "C SA",
         "cours_depart": "100", "pourcentage_predit": "5.0", "cours_cible": "105", "echeance_prevue": "2024-01-08",
         "cours_reel_echeance": "104.8", "ecart_reel_pct": "4.8", "objectif_atteint": "Non"},
        # Encore en attente
        {"horodatage_alerte": "2024-01-04 10:00", "marche": "CAC40", "ticker": "DDD.PA", "nom": "D SA",
         "cours_depart": "100", "pourcentage_predit": "5.0", "cours_cible": "105", "echeance_prevue": "2099-01-01",
         "cours_reel_echeance": "", "ecart_reel_pct": "", "objectif_atteint": ""},
    ]
    predictions.write_rows(csv_path, rows)

    generate_report.generate(csv_path=csv_path, output_path=output_path)

    with open(output_path, encoding="utf-8") as f:
        html_content = f.read()

    assert "pill-atteint" in html_content
    assert "pill-manque" in html_content
    assert "pill-justesse" in html_content
    assert "pill-attente" in html_content
    # 1 atteint sur 3 vérifiées (AAA Oui, BBB Non, CCC Non) -> 33%
    assert "33%" in html_content
    # Tri par date décroissante : AAA (03) avant DDD n'est pas vérifié mais doit apparaître avant BBB (02) et CCC (01)
    assert html_content.index("AAA.PA") < html_content.index("BBB.PA") < html_content.index("CCC.PA")


# --- ATR et cible plafonnée (point 3) ------------------------------------------------------


def test_atr_constant_true_range():
    df = make_df([100.0] * 30, high_pad=1.0, low_pad=1.0)  # TR constant = 2.0 chaque jour
    assert atr(df, period=14) == pytest.approx(2.0)


def test_atr_insufficient_data_returns_none():
    df = make_df([100.0] * 5)
    assert atr(df, period=14) is None


def test_atr_multiplier_matches_horizon_buckets():
    assert atr_multiplier(2, cfg) == cfg.ATR_MULTIPLIER_SHORT
    assert atr_multiplier(5, cfg) == cfg.ATR_MULTIPLIER_MEDIUM
    assert atr_multiplier(10, cfg) == cfg.ATR_MULTIPLIER_LONG


def test_compute_opportunity_caps_upside_with_atr():
    # Résistance technique lointaine (canal haut ~109, touché plusieurs fois) suivie
    # d'une pente monotone (donc sans extremum parasite) jusqu'à un petit canal bas
    # à faible volatilité (~97-98, ATR minuscule) : la cible brute (~12%) doit être
    # plafonnée très en dessous par la volatilité réelle du titre.
    high_channel = [109.0, 108.5, 109.0, 109.3, 108.8, 109.2] * 3
    n_decline = 40
    decline = [108.5 - i * (108.5 - 98.0) / n_decline for i in range(n_decline)]
    tail = [98.0, 97.3, 98.0, 98.2, 97.8, 97.6]
    closes = high_channel + decline + tail
    df = make_df(closes, high_pad=0.1, low_pad=0.1)
    price = closes[-1]

    levels = find_multi_window_levels(df, price, cfg.SR_WINDOWS, cfg.SR_CLUSTER_PCT, cfg.SR_CONFIRM_CLUSTER_PCT)
    raw_upside_pct = (levels["resistance"]["level"] - price) / price * 100

    atr_value = atr(df, cfg.ATR_PERIOD)
    atr_pct = atr_value / price * 100
    expected_atr_upside = atr_multiplier(raw_upside_pct, cfg) * atr_pct
    expected_upside = min(raw_upside_pct, expected_atr_upside)

    opp = compute_opportunity(
        "TEST.PA", "Test SA", df, pe=None, reference_median_pe=None, sector_name="inconnu",
        sector_sample_size=0, index_df=None, cfg=cfg,
    )

    assert opp is not None
    assert opp.upside_pct == pytest.approx(expected_upside, rel=1e-6)
    # Confirme que le plafond ATR joue bien un rôle ici (résistance technique nettement
    # plus loin que ce que la volatilité du titre justifie).
    assert opp.upside_pct < raw_upside_pct
    assert opp.resistance_level == pytest.approx(price * (1 + opp.upside_pct / 100))


# --- Confirmation par familles de signaux indépendantes (point 2) -------------------------


def test_family_scores_groups_signals():
    opp = SimpleNamespace(scores={"support": 3.0, "macd": 2.0, "rsi": 1.0, "volume": 0.5, "per": 0.2})
    families = family_scores(opp, cfg)

    assert families["prix"] == pytest.approx((6.0, cfg.WEIGHT_SUPPORT + cfg.WEIGHT_MACD + cfg.WEIGHT_RSI))
    assert families["volume"] == pytest.approx((0.5, cfg.WEIGHT_VOLUME))
    assert families["valorisation"] == pytest.approx((0.2, cfg.WEIGHT_PER))


def test_families_confirm_requires_two_of_three():
    # Famille "prix" au maximum + volume au maximum -> 2 familles sur 3 -> confirmé
    opp_ok = SimpleNamespace(scores={
        "support": cfg.WEIGHT_SUPPORT, "macd": cfg.WEIGHT_MACD, "rsi": cfg.WEIGHT_RSI,
        "volume": cfg.WEIGHT_VOLUME, "per": 0.0,
    })
    assert families_confirm(opp_ok, cfg) is True

    # Seule la famille "prix" est forte -> 1 famille sur 3 -> pas confirmé
    opp_ko = SimpleNamespace(scores={
        "support": cfg.WEIGHT_SUPPORT, "macd": cfg.WEIGHT_MACD, "rsi": cfg.WEIGHT_RSI,
        "volume": 0.0, "per": 0.0,
    })
    assert families_confirm(opp_ko, cfg) is False


# --- Franchissement de seuil / armement (point 1) -----------------------------------------


def test_state_rearm_and_disarm_cycle():
    state = {}
    assert state_module.is_armed(state, "TEST.PA") is True

    state_module.disarm(state, "TEST.PA", score=6.0)
    assert state_module.is_armed(state, "TEST.PA") is False

    # Reste désarmé tant que le score reste au-dessus du seuil
    state_module.rearm_if_below_threshold(state, "TEST.PA", total_score=5.5, threshold=5.0)
    assert state_module.is_armed(state, "TEST.PA") is False

    # Repasse sous le seuil -> réarmé
    state_module.rearm_if_below_threshold(state, "TEST.PA", total_score=4.0, threshold=5.0)
    assert state_module.is_armed(state, "TEST.PA") is True
