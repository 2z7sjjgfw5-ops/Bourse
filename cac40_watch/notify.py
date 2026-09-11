"""Envoi des notifications vers le téléphone de l'utilisateur.

Trois fournisseurs sont pris en charge, du plus simple au plus élaboré :
- ntfy (https://ntfy.sh) : gratuit, sans inscription, juste une application
  et un nom de "topic" secret.
- Pushover : application payante une fois (~5 $), notifications illimitées
  ensuite, plus fiable pour un usage sérieux.
- Telegram : gratuit, nécessite de créer un bot via @BotFather.
"""

import requests

DISCLAIMER = (
    "Estimation probabiliste basée sur une analyse technique automatisée. "
    "Ce n'est ni un conseil financier ni une garantie de résultat. "
    "Aucun ordre n'est jamais passé automatiquement : la décision et "
    "l'exécution vous appartiennent entièrement."
)


def _fr(value, decimals=1):
    """Formate un nombre avec une virgule décimale (convention française)."""
    return f"{value:.{decimals}f}".replace(".", ",")


def _score_line(opp):
    s = opp.scores
    return (
        f"Score de confiance {_fr(opp.total_score)}/10 — "
        f"support {_fr(s['support'])} · MACD {_fr(s['macd'])} · "
        f"RSI {_fr(s['rsi'])} · volume {_fr(s['volume'])} · PER {_fr(s['per'])}"
    )


def format_message(opp):
    distance_pct = (opp.price - opp.support_level) / opp.support_level * 100
    lines = [
        _score_line(opp),
        "",
        f"{opp.name} ({opp.ticker})",
        f"Prix actuel : {opp.price:.2f} EUR",
        (
            f"Support proche : {opp.support_level:.2f} EUR (prix à +{distance_pct:.1f}% du support, "
            f"confirmé par {opp.support_confirmations}/{opp.support_total_windows} fenêtres)"
        ),
        f"Résistance visée : {opp.resistance_level:.2f} EUR",
        f"Potentiel de hausse estimé : +{opp.upside_pct:.1f}%",
        f"Horizon indicatif : {opp.horizon}",
        f"Bêta (1 an vs CAC 40) : {opp.beta:.2f}" if opp.beta is not None else "Bêta (1 an vs CAC 40) : non disponible",
    ]

    if opp.rsi_value is not None:
        lines.append(f"RSI (14 jours) : {opp.rsi_value:.0f}")
    else:
        lines.append("RSI (14 jours) : non disponible")

    if opp.macd_data is not None:
        position = "au-dessus" if opp.macd_data["histogram"] > 0 else "en dessous"
        lines.append(f"MACD : ligne {position} du signal (histogramme {opp.macd_data['histogram']:.2f})")
    else:
        lines.append("MACD : non disponible")

    if opp.volume_ratio is not None:
        lines.append(f"Volume du jour : x{opp.volume_ratio:.1f} la moyenne 20 jours")
    else:
        lines.append("Volume du jour : non disponible")

    if opp.pe and opp.reference_median_pe:
        n = opp.sector_sample_size
        peers = "valeur comparable" if n == 1 else "valeurs comparables"
        lines.append(
            f"PER : {opp.pe:.1f} (secteur {opp.sector_name} : {n} {peers}, référence pondérée : {opp.reference_median_pe:.1f})"
        )
    else:
        lines.append("PER : non disponible")

    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def send_ntfy(topic, message, priority="default"):
    if not topic:
        raise ValueError("NTFY_TOPIC n'est pas configuré")
    response = requests.post(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": "Alerte CAC 40",
            "Priority": priority,
            "Tags": "chart_with_upwards_trend",
        },
        timeout=15,
    )
    response.raise_for_status()


def send_pushover(user_key, app_token, title, message):
    if not user_key or not app_token:
        raise ValueError("PUSHOVER_USER_KEY / PUSHOVER_APP_TOKEN ne sont pas configurés")
    response = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={"token": app_token, "user": user_key, "title": title, "message": message},
        timeout=15,
    )
    response.raise_for_status()


def send_telegram(bot_token, chat_id, message):
    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ne sont pas configurés")
    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data={"chat_id": chat_id, "text": message},
        timeout=15,
    )
    response.raise_for_status()


def send_notification(opp, cfg):
    message = format_message(opp)
    provider = cfg.NOTIFY_PROVIDER

    if provider == "ntfy":
        send_ntfy(cfg.NTFY_TOPIC, message)
    elif provider == "pushover":
        send_pushover(cfg.PUSHOVER_USER_KEY, cfg.PUSHOVER_APP_TOKEN, "Alerte CAC 40", message)
    elif provider == "telegram":
        send_telegram(cfg.TELEGRAM_BOT_TOKEN, cfg.TELEGRAM_CHAT_ID, message)
    else:
        raise ValueError(f"Fournisseur de notification inconnu ou non configuré : {provider!r}")
