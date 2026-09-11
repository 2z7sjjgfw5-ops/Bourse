"""Calcul des indicateurs techniques bruts : support/résistance (multi-fenêtres),
volume, PER, RSI, MACD, bêta.

Ce module renvoie des valeurs brutes (niveaux de prix, ratios, RSI, MACD...).
La conversion en points de score pondérés se fait dans scoring.py.

Ces fonctions n'ont volontairement aucune dépendance exotique (pas de
scipy/ta-lib) : elles restent lisibles et faciles à auditer pour quelqu'un
qui n'est pas développeur. Seul le calcul du bêta s'appuie sur pandas (déjà
une dépendance du projet), car il a besoin d'aligner deux séries par date.
"""


def _local_extrema(values, order, kind):
    """Indices où `values[i]` est un minimum/maximum local sur `order` voisins de chaque côté."""
    n = len(values)
    idx = []
    for i in range(order, n - order):
        window = values[i - order : i + order + 1]
        center = values[i]
        if kind == "min" and center == min(window):
            idx.append(i)
        elif kind == "max" and center == max(window):
            idx.append(i)
    return idx


def _cluster_levels(levels, cluster_pct):
    """Regroupe des niveaux de prix proches (+/- cluster_pct) en zones uniques.

    Retourne une liste de dicts {"level": prix moyen, "touches": nb de points}.
    """
    if not levels:
        return []
    levels = sorted(levels)
    clusters = []
    current = [levels[0]]
    for lvl in levels[1:]:
        if (lvl - current[-1]) / current[-1] <= cluster_pct:
            current.append(lvl)
        else:
            clusters.append(current)
            current = [lvl]
    clusters.append(current)
    return [{"level": sum(c) / len(c), "touches": len(c)} for c in clusters]


def find_support_resistance(df, current_price, order=3, cluster_pct=0.015):
    """Cherche le support le plus proche sous le prix et la résistance la plus proche au-dessus,
    pour une seule fenêtre de détection (voir find_multi_window_levels pour la version combinée).

    Retourne {"support": float|None, "resistance": float|None} ou None si
    l'historique est trop court pour être analysé.
    """
    if len(df) < order * 2 + 5:
        return None

    lows = df["Low"].tolist()
    highs = df["High"].tolist()

    low_idx = _local_extrema(lows, order, "min")
    high_idx = _local_extrema(highs, order, "max")

    low_levels = [lows[i] for i in low_idx]
    high_levels = [highs[i] for i in high_idx]

    low_clusters = _cluster_levels(low_levels, cluster_pct)
    high_clusters = _cluster_levels(high_levels, cluster_pct)

    support_candidates = [c for c in low_clusters if c["level"] < current_price]
    resistance_candidates = [c for c in high_clusters if c["level"] > current_price]

    support = max(support_candidates, key=lambda c: c["level"])["level"] if support_candidates else None
    resistance = min(resistance_candidates, key=lambda c: c["level"])["level"] if resistance_candidates else None

    return {"support": support, "resistance": resistance}


def find_multi_window_levels(df, current_price, windows, cluster_pct, confirm_cluster_pct):
    """Combine plusieurs fenêtres de détection (courte/moyenne/longue) pour un support
    et une résistance plus robustes.

    Pour chaque fenêtre, on calcule le support/résistance "single-window" le plus proche
    du prix. Les niveaux obtenus par les différentes fenêtres sont ensuite regroupés :
    plus un niveau est retrouvé par un grand nombre de fenêtres différentes, plus il est
    considéré comme confirmé.

    Retourne None si aucune fenêtre n'a rien trouvé, sinon un dict :
        {
          "support": {"level": float, "confirmations": int, "total_windows": int} | None,
          "resistance": {"level": float, "confirmations": int, "total_windows": int} | None,
        }
    """
    support_candidates = []
    resistance_candidates = []
    for order in windows:
        sr = find_support_resistance(df, current_price, order=order, cluster_pct=cluster_pct)
        if not sr:
            continue
        if sr["support"] is not None:
            support_candidates.append(sr["support"])
        if sr["resistance"] is not None:
            resistance_candidates.append(sr["resistance"])

    total_windows = len(windows)

    def _best_cluster(candidates):
        if not candidates:
            return None
        clusters = _cluster_levels(candidates, confirm_cluster_pct)
        best = max(clusters, key=lambda c: (c["touches"], -abs(current_price - c["level"])))
        return {
            "level": best["level"],
            "confirmations": best["touches"],
            "total_windows": total_windows,
        }

    support = _best_cluster(support_candidates)
    resistance = _best_cluster(resistance_candidates)

    if support is None and resistance is None:
        return None

    return {"support": support, "resistance": resistance}


def volume_signal(df, lookback=20):
    """Calcule le ratio volume du jour / moyenne des `lookback` jours précédents."""
    volumes = df["Volume"].tolist()
    if len(volumes) < lookback + 1:
        return None
    recent = volumes[-1]
    baseline = volumes[-(lookback + 1) : -1]
    avg = sum(baseline) / len(baseline)
    if avg <= 0:
        return None
    return {"ratio": recent / avg}


def valuation_ratio(pe, reference_median_pe):
    """Ratio PER de la valeur / PER médian de référence (secteur ou, à défaut, tout l'indice)."""
    if not pe or pe <= 0 or not reference_median_pe or reference_median_pe <= 0:
        return None
    return pe / reference_median_pe


def rsi(df, period=14):
    """RSI (Relative Strength Index) selon la méthode de lissage de Wilder."""
    closes = df["Close"].tolist()
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _ema_series(values, period):
    """Série de moyennes mobiles exponentielles (amorcée par une moyenne simple)."""
    if len(values) < period:
        return []
    multiplier = 2 / (period + 1)
    ema_values = [sum(values[:period]) / period]
    for value in values[period:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def macd(df, fast=12, slow=26, signal=9):
    """MACD standard : ligne MACD (EMA rapide - EMA lente), ligne de signal, histogramme."""
    closes = df["Close"].tolist()
    if len(closes) < slow + signal:
        return None

    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)
    n = min(len(ema_fast), len(ema_slow))
    if n < signal:
        return None

    macd_line = [f - s for f, s in zip(ema_fast[-n:], ema_slow[-n:])]
    signal_line = _ema_series(macd_line, signal)
    if not signal_line:
        return None

    macd_value = macd_line[-1]
    signal_value = signal_line[-1]
    return {"macd": macd_value, "signal": signal_value, "histogram": macd_value - signal_value}


def weekly_returns(df):
    """Rendements hebdomadaires (variation en %) à partir d'un historique quotidien."""
    weekly_close = df["Close"].resample("W").last().dropna()
    return weekly_close.pct_change().dropna()


def compute_beta(stock_df, index_df, min_points=10):
    """Bêta d'une valeur par rapport à un indice, à partir des rendements hebdomadaires alignés."""
    stock_weekly = weekly_returns(stock_df)
    index_weekly = weekly_returns(index_df)

    combined = stock_weekly.to_frame("stock").join(index_weekly.to_frame("index"), how="inner").dropna()
    if len(combined) < min_points:
        return None

    variance = combined["index"].var()
    if not variance:
        return None
    covariance = combined["stock"].cov(combined["index"])
    return covariance / variance


def horizon_bucket(upside_pct):
    """Horizon indicatif basé sur l'ampleur du mouvement visé (heuristique simple)."""
    if upside_pct <= 3:
        return "d'ici la fin de la semaine (environ 5 séances de bourse)"
    if upside_pct <= 6:
        return "sous 2 à 3 semaines"
    return "sous 4 à 6 semaines"
