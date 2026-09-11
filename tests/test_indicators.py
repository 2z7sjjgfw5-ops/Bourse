"""Tests avec des données synthétiques (aucun accès réseau requis)."""

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cac40_watch.indicators import (
    find_support_resistance,
    volume_signal,
    valuation_signal,
    horizon_bucket,
)
from cac40_watch.scoring import evaluate
from cac40_watch import config as cfg


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


def test_find_support_resistance_detects_range():
    # Prix oscillant entre ~95 (support) et ~105 (résistance), retour vers 96.
    closes = []
    for _ in range(6):
        closes += [100, 96, 100, 104, 100]
    closes += [96.5]  # prix courant proche du support
    df = make_df(closes)

    result = find_support_resistance(df, current_price=closes[-1], order=2, cluster_pct=0.02)

    assert result is not None
    assert result["support"] is not None
    assert result["resistance"] is not None
    assert result["support"] < closes[-1] < result["resistance"]


def test_volume_signal_flags_spike():
    volumes = [1_000_000] * 20 + [3_000_000]
    df = make_df([100] * len(volumes), volumes=volumes)

    result = volume_signal(df, lookback=20, threshold=1.8)

    assert result is not None
    assert result["is_anomalous"] is True
    assert math.isclose(result["ratio"], 3.0, rel_tol=1e-6)


def test_volume_signal_no_data_returns_none():
    df = make_df([100] * 5, volumes=[1_000_000] * 5)
    assert volume_signal(df, lookback=20) is None


def test_valuation_signal_flags_discount():
    result = valuation_signal(pe=10, peer_median_pe=20, discount_threshold=0.7)
    assert result is not None
    assert result["is_undervalued"] is True

    result_expensive = valuation_signal(pe=19, peer_median_pe=20, discount_threshold=0.7)
    assert result_expensive["is_undervalued"] is False


def test_valuation_signal_handles_missing_data():
    assert valuation_signal(None, 20) is None
    assert valuation_signal(10, None) is None
    assert valuation_signal(-5, 20) is None


def test_horizon_bucket_scales_with_upside():
    assert "semaine" in horizon_bucket(2)
    assert "2 à 3 semaines" in horizon_bucket(5)
    assert "4 à 6 semaines" in horizon_bucket(10)


def test_evaluate_end_to_end_triggers_opportunity():
    closes = []
    for _ in range(6):
        closes += [100, 96, 100, 104, 100]
    closes += [96.5]
    volumes = [1_000_000] * (len(closes) - 1) + [3_000_000]
    df = make_df(closes, volumes=volumes)

    opp = evaluate("TEST.PA", "Test SA", df, pe=10, peer_median_pe=20, cfg=cfg)

    assert opp is not None
    assert opp.score >= cfg.MIN_SCORE
    assert opp.upside_pct > 0
    assert "volume d'échange anormalement élevé" in opp.signals
    assert "valorisation (PER) inférieure à la moyenne du CAC 40" in opp.signals


def test_evaluate_returns_none_when_price_far_from_support():
    closes = []
    for _ in range(6):
        closes += [100, 96, 100, 104, 100]
    closes += [103]  # loin du support, proche de la résistance
    df = make_df(closes)

    opp = evaluate("TEST.PA", "Test SA", df, pe=10, peer_median_pe=20, cfg=cfg)

    assert opp is None
