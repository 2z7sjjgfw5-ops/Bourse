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

# --- Historique utilisé pour l'analyse --------------------------------------

# 1 an de données quotidiennes : sert à la fois aux indicateurs habituels
# (support/résistance, RSI, MACD, volume) et au calcul du bêta (rendements
# hebdomadaires sur 1 an), sans avoir à faire une deuxième requête réseau.
HISTORY_PERIOD = "1y"

# --- Signal 1 : support technique (fenêtres multiples) ----------------------

SR_WINDOWS = [2, 4, 8]           # fenêtres courte / moyenne / longue (bougies de chaque côté d'un pivot)
SR_CLUSTER_PCT = 0.015           # regroupe les niveaux proches (+/-1.5%) en une seule zone
SR_CONFIRM_CLUSTER_PCT = 0.02    # tolérance pour dire que deux fenêtres pointent vers le même niveau

# Distance (en %) entre le prix et le support : sous ce seuil, le signal
# support rapporte son maximum ; au-delà du second seuil, il rapporte 0.
# Entre les deux, la note décroît linéairement.
SUPPORT_FULL_CREDIT_PCT = 0.3
SUPPORT_ZERO_CREDIT_PCT = 3.0

# --- Signal 2 : MACD ---------------------------------------------------------

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
# Histogramme (MACD - ligne de signal), exprimé en % du prix : au-dessus de ce
# seuil, note maximale ; à 0 ou en dessous (histogramme négatif), note nulle.
MACD_FULL_CREDIT_PCT = 0.5
MACD_ZERO_CREDIT_PCT = 0.0

# --- Signal 3 : RSI -----------------------------------------------------------

RSI_PERIOD = 14
# RSI au ou sous ce niveau : note maximale (zone de survente classique).
# RSI à ce niveau ou au-dessus : note nulle. Décroissance linéaire entre les deux.
RSI_FULL_CREDIT = 30.0
RSI_ZERO_CREDIT = 50.0

# --- Signal 4 : volume anormal ------------------------------------------------

VOLUME_LOOKBACK = 20             # nombre de jours pour la moyenne de volume
# Ratio volume du jour / moyenne 20j : au ou au-dessus de ce ratio, note
# maximale ; à 1.0 (aucune anomalie) ou en dessous, note nulle.
VOLUME_FULL_CREDIT_RATIO = 3.0
VOLUME_ZERO_CREDIT_RATIO = 1.0

# --- Signal 5 : PER comparé au secteur ---------------------------------------

# Ratio PER de la valeur / PER médian de son secteur : à ce ratio ou en
# dessous, note maximale (forte décote) ; à 1.0 (valorisation dans la
# moyenne du secteur) ou au-dessus, note nulle.
PER_FULL_CREDIT_RATIO = 0.5
PER_ZERO_CREDIT_RATIO = 1.0
# Nombre minimum de valeurs comparables dans un secteur pour que la médiane
# sectorielle soit jugée statistiquement utilisable ; en dessous, on bascule
# sur la médiane de tout le CAC 40 et l'alerte le signale explicitement.
MIN_SECTOR_SAMPLE = 4

# --- Pondération et score total (sur 10) -------------------------------------

WEIGHT_SUPPORT = 3.5
WEIGHT_MACD = 2.5
WEIGHT_RSI = 1.8
WEIGHT_VOLUME = 1.2
WEIGHT_PER = 1.0

# Seuil de déclenchement d'une alerte (score total sur 10).
# PROVISOIRE : valeur de départ le temps de calculer la distribution réelle
# des scores sur données historiques (voir cac40_watch/calibrate.py) et de
# la faire valider — ne pas considérer ce chiffre comme définitif.
SCORE_THRESHOLD = 5.0

ALERT_COOLDOWN_DAYS = 3          # ne pas ré-alerter sur la même valeur avant N jours

# --- Bêta ---------------------------------------------------------------------

INDEX_TICKER = "^FCHI"           # indice CAC 40 sur Yahoo Finance
BETA_MIN_POINTS = 10             # nombre minimum de rendements hebdomadaires alignés requis

# --- Historique de suivi des alertes -----------------------------------------

ALERT_HISTORY_FILE = "state/alert_history.json"
FOLLOWUP_WEEKS = [1, 4, 6]       # échéances de revérification du prix après une alerte

# --- Fonctionnement -----------------------------------------------------------

STATE_FILE = "state/last_alerts.json"
REQUEST_DELAY_SECONDS = 1.0      # pause entre deux requêtes réseau (courtoisie envers Yahoo Finance)
