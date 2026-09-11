"""Combine les indicateurs individuels en une opportunité éventuelle."""

from dataclasses import dataclass, field

from .indicators import find_support_resistance, volume_signal, valuation_signal, horizon_bucket


@dataclass
class Opportunity:
    ticker: str
    name: str
    price: float
    support: float
    resistance: float
    upside_pct: float
    horizon: str
    score: int
    signals: list = field(default_factory=list)
    volume_ratio: float = None
    pe: float = None
    peer_median_pe: float = None


def evaluate(ticker, name, df, pe, peer_median_pe, cfg):
    """Retourne une Opportunity si les critères sont réunis, sinon None."""
    if df is None or df.empty:
        return None

    price = float(df["Close"].iloc[-1])

    sr = find_support_resistance(df, price, cfg.SR_ORDER, cfg.SR_CLUSTER_PCT)
    if not sr or sr["support"] is None or sr["resistance"] is None:
        return None

    support, resistance = sr["support"], sr["resistance"]
    if resistance <= price or support <= 0:
        return None

    distance_above_support_pct = (price - support) / support * 100
    if distance_above_support_pct > cfg.NEAR_SUPPORT_MAX_PCT:
        return None  # le prix n'est pas assez proche d'un support pour parler de point d'entrée

    signals = ["proximité d'un support technique"]
    score = 1
    volume_ratio = None

    vol = volume_signal(df, cfg.VOLUME_LOOKBACK, cfg.VOLUME_RATIO_THRESHOLD)
    if vol:
        volume_ratio = vol["ratio"]
        if vol["is_anomalous"]:
            signals.append("volume d'échange anormalement élevé")
            score += 1

    val = valuation_signal(pe, peer_median_pe, cfg.VALUATION_DISCOUNT)
    if val and val["is_undervalued"]:
        signals.append("valorisation (PER) inférieure à la moyenne du CAC 40")
        score += 1

    if score < cfg.MIN_SCORE:
        return None

    upside_pct = (resistance - price) / price * 100
    horizon = horizon_bucket(upside_pct)

    return Opportunity(
        ticker=ticker,
        name=name,
        price=price,
        support=support,
        resistance=resistance,
        upside_pct=upside_pct,
        horizon=horizon,
        score=score,
        signals=signals,
        volume_ratio=volume_ratio,
        pe=pe,
        peer_median_pe=peer_median_pe,
    )
