"""Calcul des indicateurs techniques : support/résistance, volume, valorisation.

Ces fonctions n'ont volontairement aucune dépendance exotique (pas de
scipy/ta-lib) : elles restent lisibles et faciles à auditer pour quelqu'un
qui n'est pas développeur.
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
    """Cherche le support le plus proche sous le prix et la résistance la plus proche au-dessus.

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


def volume_signal(df, lookback=20, threshold=1.8):
    """Détecte un volume d'échange anormalement élevé sur la dernière séance."""
    volumes = df["Volume"].tolist()
    if len(volumes) < lookback + 1:
        return None
    recent = volumes[-1]
    baseline = volumes[-(lookback + 1) : -1]
    avg = sum(baseline) / len(baseline)
    if avg <= 0:
        return None
    ratio = recent / avg
    return {"ratio": ratio, "is_anomalous": ratio >= threshold}


def valuation_signal(pe, peer_median_pe, discount_threshold=0.70):
    """Compare le PER (price/earnings) d'une valeur à la médiane du CAC 40 du jour."""
    if not pe or pe <= 0 or not peer_median_pe or peer_median_pe <= 0:
        return None
    ratio = pe / peer_median_pe
    return {"ratio": ratio, "is_undervalued": ratio <= discount_threshold}


def horizon_bucket(upside_pct):
    """Horizon indicatif basé sur l'ampleur du mouvement visé (heuristique simple)."""
    if upside_pct <= 3:
        return "d'ici la fin de la semaine (environ 5 séances de bourse)"
    if upside_pct <= 6:
        return "sous 2 à 3 semaines"
    return "sous 4 à 6 semaines"
