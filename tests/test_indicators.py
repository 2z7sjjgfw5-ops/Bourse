"""Tests avec des données synthétiques (aucun accès réseau requis)."""

import sys
from datetime import date, timedelta
from pathlib import Path

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
)
from cac40_watch.scoring import _linear_fraction, blended_reference_pe, compute_opportunity, evaluate
from cac40_watch import config as cfg
from cac40_watch import history as history_module


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


# --- historique de suivi ---------------------------------------------------------------------


class _FakeOpportunity:
    def __init__(self, ticker, name, price, total_score, upside_pct):
        self.ticker = ticker
        self.name = name
        self.price = price
        self.total_score = total_score
        self.upside_pct = upside_pct


def test_history_record_and_due_followups():
    hist = {}
    alert_date = date(2024, 1, 1)
    opp = _FakeOpportunity("TEST.PA", "Test SA", price=100.0, total_score=6.5, upside_pct=5.0)

    alert_id = history_module.record_alert(hist, opp, alert_date, followup_weeks=[1, 4, 6])

    assert alert_id in hist
    assert hist[alert_id]["followups"]["1_semaine"]["due_date"] == (alert_date + timedelta(weeks=1)).isoformat()

    # Rien n'est dû juste après l'alerte
    assert history_module.due_followups(hist, today=alert_date) == []

    # Une semaine plus tard, l'échéance à 1 semaine est due (pas les autres)
    due = history_module.due_followups(hist, today=alert_date + timedelta(weeks=1))
    assert len(due) == 1
    assert due[0][2] == "1_semaine"


def test_history_apply_followup_computes_change():
    hist = {}
    alert_date = date(2024, 1, 1)
    opp = _FakeOpportunity("TEST.PA", "Test SA", price=100.0, total_score=6.5, upside_pct=5.0)
    alert_id = history_module.record_alert(hist, opp, alert_date, followup_weeks=[1, 4, 6])

    history_module.apply_followup(hist, alert_id, "1_semaine", price_now=105.0, checked_date=alert_date + timedelta(weeks=1))

    followup = hist[alert_id]["followups"]["1_semaine"]
    assert followup["done"] is True
    assert followup["actual_change_pct"] == pytest.approx(5.0)

    # Une fois traitée, elle ne doit plus apparaître comme due
    due = history_module.due_followups(hist, today=alert_date + timedelta(weeks=6))
    keys_due = [key for _, _, key in due]
    assert "1_semaine" not in keys_due
    assert "4_semaines" in keys_due
    assert "6_semaines" in keys_due
