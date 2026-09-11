"""Paramètres du système de veille.

Les valeurs sensibles (identifiants de notification) sont lues depuis les
variables d'environnement, elles-mêmes définies via les "secrets" du dépôt
GitHub (voir README.md). Les seuils d'analyse ci-dessous ont des valeurs par
défaut raisonnables ; ils peuvent être ajustés sans risque.
"""

import os

# --- Notification --------------------------------------------------------

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_APP_TOKEN = os.environ.get("PUSHOVER_APP_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Le fournisseur peut être forcé via la variable NOTIFY_PROVIDER
# ("ntfy", "pushover" ou "telegram"). À défaut, il est déduit des secrets
# renseignés.
_explicit_provider = os.environ.get("NOTIFY_PROVIDER")
if _explicit_provider:
    NOTIFY_PROVIDER = _explicit_provider
elif NTFY_TOPIC:
    NOTIFY_PROVIDER = "ntfy"
elif PUSHOVER_USER_KEY and PUSHOVER_APP_TOKEN:
    NOTIFY_PROVIDER = "pushover"
elif TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    NOTIFY_PROVIDER = "telegram"
else:
    NOTIFY_PROVIDER = None

# --- Analyse technique ----------------------------------------------------

HISTORY_PERIOD = "6mo"          # profondeur d'historique utilisée
SR_ORDER = 3                     # bougies de chaque côté pour définir un point pivot
SR_CLUSTER_PCT = 0.015           # regroupe les niveaux proches (+/-1.5%) en une seule zone
NEAR_SUPPORT_MAX_PCT = 2.0       # le prix doit être à moins de X% au-dessus du support
VOLUME_LOOKBACK = 20             # nombre de jours pour la moyenne de volume
VOLUME_RATIO_THRESHOLD = 1.8     # volume du jour >= X fois la moyenne => signal
VALUATION_DISCOUNT = 0.70        # PER <= 70% de la médiane du CAC 40 => signal
MIN_SCORE = 2                    # score minimum pour déclencher une alerte
ALERT_COOLDOWN_DAYS = 3          # ne pas ré-alerter sur la même valeur avant N jours

# --- Fonctionnement ---------------------------------------------------------

STATE_FILE = "state/last_alerts.json"
REQUEST_DELAY_SECONDS = 1.0      # pause entre deux requêtes réseau (courtoisie envers Yahoo Finance)
