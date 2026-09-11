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


def format_message(opp):
    lines = [
        f"{opp.name} ({opp.ticker})",
        f"Prix actuel : {opp.price:.2f} EUR",
        f"Support proche : {opp.support:.2f} EUR (prix à +{(opp.price - opp.support) / opp.support * 100:.1f}% du support)",
        f"Résistance visée : {opp.resistance:.2f} EUR",
        f"Potentiel de hausse estimé : +{opp.upside_pct:.1f}%",
        f"Horizon indicatif : {opp.horizon}",
        "Signaux détectés : " + ", ".join(opp.signals),
    ]
    if opp.volume_ratio:
        lines.append(f"Volume du jour : x{opp.volume_ratio:.1f} la moyenne 20 jours")
    if opp.pe and opp.peer_median_pe:
        lines.append(f"PER : {opp.pe:.1f} (médiane CAC 40 : {opp.peer_median_pe:.1f})")
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
