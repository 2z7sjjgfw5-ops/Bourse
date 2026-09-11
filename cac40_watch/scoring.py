"""Combine les indicateurs bruts en un score de confiance continu (sur 10) et,
le cas échéant, une opportunité d'alerte.

Chaque signal rapporte un nombre de points proportionnel à son intensité
(jamais tout-ou-rien) : une fonction linéaire simple convertit une valeur
brute (distance au support, RSI, ratio de volume...) en une fraction entre 0
et 1, multipliée par le poids maximal du signal.
"""

from dataclasses import dataclass, field

from .indicators import (
    find_multi_window_levels,
    volume_signal,
    valuation_ratio,
    rsi as compute_rsi,
    macd as compute_macd,
    compute_beta,
    horizon_bucket,
)


def _linear_fraction(value, full_credit_value, zero_credit_value):
    """Fraction dans [0, 1] : 1 à `full_credit_value`, 0 à `zero_credit_value`,
    interpolation linéaire entre les deux (fonctionne dans les deux sens,
    que la note augmente ou diminue avec `value`)."""
    if full_credit_value == zero_credit_value:
        return 1.0 if value == full_credit_value else 0.0
    fraction = (value - zero_credit_value) / (full_credit_value - zero_credit_value)
    return max(0.0, min(1.0, fraction))


def blended_reference_pe(sector_median_pe, sector_sample_size, global_median_pe, k):
    """Moyenne pondérée entre la médiane du secteur et celle de tout le CAC 40 :
    le poids du secteur croît avec son nombre de valeurs comparables (voir
    config.PER_SHRINKAGE_K). Jamais de bascule binaire "secteur ou repli"."""
    if sector_median_pe is None or sector_sample_size <= 0:
        return global_median_pe
    if global_median_pe is None:
        return sector_median_pe
    return (sector_sample_size * sector_median_pe + k * global_median_pe) / (sector_sample_size + k)


@dataclass
class Opportunity:
    ticker: str
    name: str
    price: float
    support_level: float
    support_confirmations: int
    support_total_windows: int
    resistance_level: float
    upside_pct: float
    horizon: str
    rsi_value: float
    macd_data: dict
    volume_ratio: float
    pe: float
    reference_median_pe: float
    sector_name: str
    sector_sample_size: int
    beta: float
    scores: dict = field(default_factory=dict)  # {"support":..,"macd":..,"rsi":..,"volume":..,"per":..}
    total_score: float = 0.0


def compute_opportunity(ticker, name, df, pe, reference_median_pe, sector_name, sector_sample_size, index_df, cfg):
    """Calcule le score complet d'une valeur, indépendamment du seuil de déclenchement.

    Retourne None uniquement si aucun support/résistance exploitable n'a pu être
    détecté (dans ce cas, aucune alerte cohérente n'est possible : pas de niveau
    à afficher, pas de potentiel de hausse calculable). Sinon, retourne toujours
    une Opportunity, même avec un score très bas — c'est ce que calibrate.py
    utilise pour étudier la distribution réelle des scores.
    """
    if df is None or df.empty:
        return None

    price = float(df["Close"].iloc[-1])

    levels = find_multi_window_levels(df, price, cfg.SR_WINDOWS, cfg.SR_CLUSTER_PCT, cfg.SR_CONFIRM_CLUSTER_PCT)
    if not levels or not levels["support"] or not levels["resistance"]:
        return None

    support = levels["support"]
    resistance = levels["resistance"]
    if resistance["level"] <= price or support["level"] <= 0:
        return None

    # --- Signal support (multi-fenêtres) ---
    distance_pct = (price - support["level"]) / support["level"] * 100
    distance_fraction = _linear_fraction(distance_pct, cfg.SUPPORT_FULL_CREDIT_PCT, cfg.SUPPORT_ZERO_CREDIT_PCT)
    window_multiplier = support["confirmations"] / support["total_windows"]
    support_score = cfg.WEIGHT_SUPPORT * distance_fraction * window_multiplier

    # --- Signal MACD ---
    macd_data = compute_macd(df, cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    if macd_data:
        histogram_pct = macd_data["histogram"] / price * 100
        macd_fraction = _linear_fraction(histogram_pct, cfg.MACD_FULL_CREDIT_PCT, cfg.MACD_ZERO_CREDIT_PCT)
        macd_score = cfg.WEIGHT_MACD * macd_fraction
    else:
        macd_score = 0.0

    # --- Signal RSI ---
    rsi_value = compute_rsi(df, cfg.RSI_PERIOD)
    if rsi_value is not None:
        rsi_fraction = _linear_fraction(rsi_value, cfg.RSI_FULL_CREDIT, cfg.RSI_ZERO_CREDIT)
        rsi_score = cfg.WEIGHT_RSI * rsi_fraction
    else:
        rsi_score = 0.0

    # --- Signal volume ---
    vol = volume_signal(df, cfg.VOLUME_LOOKBACK)
    volume_ratio = vol["ratio"] if vol else None
    if volume_ratio is not None:
        volume_fraction = _linear_fraction(volume_ratio, cfg.VOLUME_FULL_CREDIT_RATIO, cfg.VOLUME_ZERO_CREDIT_RATIO)
        volume_score = cfg.WEIGHT_VOLUME * volume_fraction
    else:
        volume_score = 0.0

    # --- Signal PER (comparé au secteur, ou à défaut à tout le CAC 40) ---
    per_ratio = valuation_ratio(pe, reference_median_pe)
    if per_ratio is not None:
        per_fraction = _linear_fraction(per_ratio, cfg.PER_FULL_CREDIT_RATIO, cfg.PER_ZERO_CREDIT_RATIO)
        per_score = cfg.WEIGHT_PER * per_fraction
    else:
        per_score = 0.0

    total_score = support_score + macd_score + rsi_score + volume_score + per_score

    upside_pct = (resistance["level"] - price) / price * 100
    horizon = horizon_bucket(upside_pct)

    beta = compute_beta(df, index_df, cfg.BETA_MIN_POINTS) if index_df is not None else None

    return Opportunity(
        ticker=ticker,
        name=name,
        price=price,
        support_level=support["level"],
        support_confirmations=support["confirmations"],
        support_total_windows=support["total_windows"],
        resistance_level=resistance["level"],
        upside_pct=upside_pct,
        horizon=horizon,
        rsi_value=rsi_value,
        macd_data=macd_data,
        volume_ratio=volume_ratio,
        pe=pe,
        reference_median_pe=reference_median_pe,
        sector_name=sector_name,
        sector_sample_size=sector_sample_size,
        beta=beta,
        scores={
            "support": support_score,
            "macd": macd_score,
            "rsi": rsi_score,
            "volume": volume_score,
            "per": per_score,
        },
        total_score=total_score,
    )


def evaluate(ticker, name, df, pe, reference_median_pe, sector_name, sector_sample_size, index_df, cfg):
    """Comme compute_opportunity, mais retourne None si le score est sous le seuil
    de déclenchement — c'est cette version que main.py utilise pour décider
    d'envoyer une alerte ou non."""
    opportunity = compute_opportunity(
        ticker, name, df, pe, reference_median_pe, sector_name, sector_sample_size, index_df, cfg
    )
    if opportunity is None or opportunity.total_score < cfg.SCORE_THRESHOLD:
        return None
    return opportunity
