# Veille CAC 40 — alertes techniques automatiques

Ce projet surveille en continu les valeurs du CAC 40 et vous envoie une
**notification sur votre téléphone** lorsqu'une configuration technique
intéressante est détectée : prix proche d'un support, volume d'échange
anormal, ou valorisation basse par rapport aux autres valeurs de l'indice.

## ⚠️ Ce que ce système fait — et ne fait jamais

- Il **analyse** des données publiques de marché et **vous informe**.
- Il **estime** un potentiel de hausse en pourcentage et un horizon indicatif
  (ex. "+5,7 % d'ici la fin de la semaine").
- Il **ne passe et ne passera jamais d'ordre d'achat ou de vente**. Aucune
  connexion à un compte de courtage n'existe dans ce code. La décision et
  l'exécution restent entièrement entre vos mains.
- Chaque alerte rappelle explicitement qu'il s'agit d'une **estimation
  probabiliste basée sur l'analyse technique**, pas d'un conseil financier
  ni d'une garantie de résultat. Les marchés financiers comportent un risque
  de perte, y compris en capital.

## Comment ça marche (en résumé)

Pour chaque valeur du CAC 40, le programme calcule un **score de confiance
continu sur 10**, à partir de cinq signaux, chacun rapportant un nombre de
points proportionnel à son intensité (jamais tout-ou-rien) :

| Signal | Poids max | Ce qu'il mesure |
|---|---|---|
| Support technique | 3,5 | Proximité d'un niveau de prix déjà "rebondi" par le passé, confirmé par 3 fenêtres de détection différentes (courte/moyenne/longue) |
| MACD | 2,5 | Momentum de tendance (moyennes mobiles exponentielles) |
| RSI | 1,8 | Zone de survente (RSI bas = signal plus fort) |
| Volume d'échange | 1,2 | Volume du jour anormalement élevé vs moyenne 20 jours |
| PER sectoriel | 1,0 | Valorisation plus basse que la médiane du secteur (bonus de contexte, jamais déclencheur à lui seul) |

Une alerte est envoyée quand le score total dépasse un seuil (actuellement
**5,0/10**, une valeur de départ en attente d'une calibration sur données
réelles — voir `cac40_watch/calibrate.py`). L'alerte indique aussi :
- le potentiel de hausse estimé jusqu'à la résistance la plus proche (en %),
- un horizon indicatif (plus le mouvement visé est grand, plus l'horizon
  annoncé est long — c'est une heuristique simple, pas une prédiction),
- le **bêta** de la valeur par rapport au CAC 40 (calibrer son niveau de
  confiance dans l'estimation chiffrée).

Une même valeur n'est pas ré-notifiée plus d'une fois tous les 3 jours, sauf
si le score se renforce entre-temps.

Chaque alerte envoyée est aussi enregistrée dans `state/alert_history.json` :
le programme revérifie automatiquement le prix réel 1, 4 et 6 semaines après
chaque alerte, pour permettre de calculer à terme un taux de réussite réel du
système — entièrement automatique, aucune action de votre part.

Tous les poids et seuils sont modifiables dans `cac40_watch/config.py`.

## Mise en place — étape par étape (aucune compétence de développeur requise)

Le système tourne **gratuitement et automatiquement sur les serveurs de
GitHub** (GitHub Actions), pendant les heures d'ouverture d'Euronext Paris,
sans que votre téléphone ou votre ordinateur ait besoin d'être allumé.
C'est l'option la plus simple et la moins chère qui existe (0 €, pas de
serveur à louer, pas de carte bancaire à fournir), puisque le code est déjà
hébergé sur GitHub.

### Étape 1 — Installer l'application de notification (5 minutes)

Par défaut, ce projet utilise **ntfy** : gratuit, sans compte à créer.

1. Installez l'application **ntfy** sur votre téléphone :
   - Android : disponible sur le Google Play Store ("ntfy").
   - iPhone : disponible sur l'App Store ("ntfy").
2. Choisissez un **nom de canal secret**, unique et difficile à deviner
   (par exemple `cac40-alertes-x7k2m9`). N'importe qui connaissant ce nom
   pourrait en théorie lire vos alertes (ntfy est un service public), donc
   choisissez quelque chose de suffisamment long et aléatoire — n'utilisez
   pas simplement "cac40".
3. Dans l'application ntfy, appuyez sur "+" (s'abonner à un topic) et entrez
   ce nom de canal.

*Alternative plus confidentielle :* si vous préférez, vous pouvez utiliser
[Pushover](https://pushover.net) (environ 5 $ une seule fois pour
l'application, notifications privées et illimitées ensuite) ou
[Telegram](https://telegram.org) (gratuit, via un bot personnel). Voir la
section "Fournisseurs de notification alternatifs" plus bas.

### Étape 2 — Enregistrer votre canal secret dans GitHub

1. Ouvrez ce dépôt sur github.com.
2. Allez dans **Settings** (Paramètres) → **Secrets and variables** →
   **Actions**.
3. Cliquez sur **New repository secret**.
4. Nom : `NTFY_TOPIC` — Valeur : le nom de canal choisi à l'étape 1.
5. Cliquez sur **Add secret**.

### Étape 3 — Autoriser le programme à sauvegarder son historique

1. Toujours dans **Settings**, allez dans **Actions** → **General**.
2. Descendez jusqu'à **Workflow permissions**.
3. Sélectionnez **Read and write permissions**.
4. Cliquez sur **Save**.

(Cette autorisation sert uniquement à ce que le programme retienne quelles
alertes ont déjà été envoyées, pour ne pas vous notifier deux fois la même
chose.)

### Étape 4 — Vérifier que les exécutions automatiques sont actives

1. Allez dans l'onglet **Actions** du dépôt.
2. S'il est proposé, cliquez sur **"I understand my workflows, go ahead and
   enable them"**.
3. Le programme s'exécutera désormais automatiquement toutes les 30 minutes
   pendant les heures de marché (jours ouvrés, 9h00-17h30 heure de Paris).

### Étape 5 — Faire un test manuel immédiat

1. Dans l'onglet **Actions**, cliquez sur le workflow **"Veille CAC 40"**
   dans la liste à gauche.
2. Cliquez sur **Run workflow** (bouton à droite) → **Run workflow**.
3. Attendez 1 à 2 minutes, puis cliquez sur l'exécution pour voir les
   journaux (logs) : vous devriez voir "Analyse terminée : X valeur(s)
   analysée(s), Y alerte(s) envoyée(s)".
4. Si une opportunité est détectée à ce moment précis, vous recevrez une
   notification de test sur votre téléphone. C'est normal de ne pas
   recevoir d'alerte à chaque test : cela signifie simplement qu'aucune
   configuration technique intéressante n'est présente à l'instant T.

**C'est terminé.** Le système tourne maintenant seul, en continu, sur un
serveur externe (GitHub), indépendamment de votre téléphone ou de votre
ordinateur.

## Personnalisation

- **Liste des valeurs surveillées** : fichier `cac40_watch/tickers.py`,
  une ligne par valeur, facile à modifier (ajouter/retirer une entreprise).
- **Sensibilité des alertes** : fichier `cac40_watch/config.py` — par
  exemple, augmenter `NEAR_SUPPORT_MAX_PCT` déclenche plus d'alertes (moins
  strict), le réduire en déclenche moins (plus strict).
- **Fréquence** : modifiable dans
  `.github/workflows/cac40_monitor.yml` (ligne `cron`).

## Fournisseurs de notification alternatifs

Vous pouvez utiliser Pushover ou Telegram à la place de ntfy en ajoutant les
secrets correspondants (étape 2 ci-dessus) au lieu de `NTFY_TOPIC` :

- **Pushover** : `PUSHOVER_USER_KEY` et `PUSHOVER_APP_TOKEN` (obtenus sur
  votre compte pushover.net après avoir créé une "Application").
- **Telegram** : `TELEGRAM_BOT_TOKEN` (créé via [@BotFather](https://t.me/BotFather)
  en discutant avec lui sur Telegram) et `TELEGRAM_CHAT_ID` (votre identifiant
  de conversation avec le bot).

Vous pouvez aussi forcer explicitement le fournisseur avec le secret
`NOTIFY_PROVIDER` (`ntfy`, `pushover` ou `telegram`).

## Coût

- **0 €** dans la configuration par défaut : GitHub Actions offre 2 000
  minutes gratuites par mois pour un dépôt privé (chaque exécution dure
  moins d'une minute ; environ 300 à 400 minutes sont utilisées par mois
  avec la fréquence par défaut), et un temps illimité si le dépôt est public.
- ntfy est entièrement gratuit. Pushover coûte environ 5 $ une seule fois
  (par plateforme). Telegram est gratuit.

Aucun serveur à louer, aucune carte bancaire à fournir pour l'option par
défaut.

## Limites à connaître

- Les données proviennent de Yahoo Finance ; elles peuvent occasionnellement
  manquer ou être légèrement retardées.
- Les niveaux de support/résistance et l'horizon indicatif sont calculés par
  des règles simples et documentées (voir `cac40_watch/indicators.py`) : ce
  sont des heuristiques d'aide à la décision, pas des prédictions garanties.
- La composition du CAC 40 change chaque trimestre ; pensez à vérifier de
  temps en temps la liste dans `cac40_watch/tickers.py` par rapport à la
  [composition officielle Euronext](https://live.euronext.com/en/product/indices/FR0003500008-XPAR).
- GitHub peut désactiver automatiquement les tâches planifiées (`cron`) d'un
  dépôt resté inactif plus de 60 jours ; il suffit de relancer manuellement
  (étape 5) pour les réactiver.

## Pour aller plus loin (optionnel)

Si vous souhaitez un jour sortir de GitHub Actions (par exemple pour une
surveillance également active en dehors des heures de marché, avec plus de
contrôle), l'option la plus simple et la moins chère est un petit serveur
virtuel (VPS) à environ 4-5 €/mois (Hetzner, DigitalOcean...), sur lequel ce
même code tournerait via une tâche planifiée (`cron`) du système. Ce n'est
pas nécessaire dans l'usage normal : GitHub Actions suffit largement pour ce
projet.

## Tests

Le comportement des indicateurs est couvert par des tests automatiques (sans
connexion internet nécessaire) :

```bash
pip install -r requirements-dev.txt
pytest
```
