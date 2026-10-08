"""Génère une page HTML lisible (docs/index.html) à partir de state/predictions.csv.

Usage :
    python -m cac40_watch.generate_report

Cette page est statique (pas de JavaScript) : elle est régénérée à chaque
exécution du workflow GitHub Actions, après check_predictions.py, puis
committée — c'est ce qui la fait "se mettre à jour automatiquement" une fois
publiée via GitHub Pages (voir README.md pour l'activer).
"""

import html
from datetime import datetime, timezone

from . import config as cfg
from .predictions import read_rows

PAGE_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Suivi des prédictions — Veille CAC 40</title>
<style>
  :root {{
    --bg: #f7f7f5;
    --card-bg: #ffffff;
    --text: #1f2430;
    --muted: #6b7280;
    --border: #e5e7eb;
    --vert: #d9f0df;
    --vert-text: #1e6b3a;
    --rouge: #fbdede;
    --rouge-text: #9c2a2a;
    --orange: #fbe8d2;
    --orange-text: #9a5b13;
    --attente-bg: #f0f0f0;
    --attente-text: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px 16px 48px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); margin: 0 0 24px; font-size: 0.9rem; }}
  .stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 24px;
  }}
  .stat-card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 18px;
    min-width: 150px;
    flex: 1;
  }}
  .stat-value {{ font-size: 1.6rem; font-weight: 600; }}
  .stat-label {{ color: var(--muted); font-size: 0.8rem; margin-top: 2px; }}
  .table-container {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow-x: auto;
  }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; white-space: nowrap; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.02em; }}
  tr:last-child td {{ border-bottom: none; }}
  .pill {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
  }}
  .pill-atteint {{ background: var(--vert); color: var(--vert-text); }}
  .pill-manque {{ background: var(--rouge); color: var(--rouge-text); }}
  .pill-justesse {{ background: var(--orange); color: var(--orange-text); }}
  .pill-attente {{ background: var(--attente-bg); color: var(--attente-text); }}
  .footer {{ color: var(--muted); font-size: 0.78rem; margin-top: 20px; }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #15171c;
      --card-bg: #1d2027;
      --text: #e8e9ec;
      --muted: #9aa0ab;
      --border: #2d313a;
      --vert: #1c3b28; --vert-text: #8fd9a8;
      --rouge: #3e2020; --rouge-text: #f0a3a3;
      --orange: #3d2e15; --orange-text: #f0c57e;
      --attente-bg: #2a2d34; --attente-text: #9aa0ab;
    }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Suivi des prédictions — Veille CAC 40</h1>
  <p class="subtitle">Mis à jour automatiquement à chaque exécution du système. Dernière génération : {generated_at}.</p>

  <div class="stats">
    <div class="stat-card">
      <div class="stat-value">{taux_reussite}</div>
      <div class="stat-label">Taux de réussite (objectifs atteints)</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{nb_verifiees}</div>
      <div class="stat-label">Prédictions vérifiées</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{nb_attente}</div>
      <div class="stat-label">En attente d'échéance</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{nb_total}</div>
      <div class="stat-label">Total enregistré</div>
    </div>
  </div>

  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>Date alerte</th>
          <th>Marché</th>
          <th>Valeur</th>
          <th>Cours départ</th>
          <th>% prédit</th>
          <th>Cours cible</th>
          <th>Échéance</th>
          <th>Cours réel</th>
          <th>Écart réel</th>
          <th>Résultat</th>
        </tr>
      </thead>
      <tbody>
{rows_html}
      </tbody>
    </table>
  </div>

  <p class="footer">
    Rappel : ces résultats mesurent uniquement la performance technique du système d'alertes,
    ce n'est ni un conseil financier ni une garantie pour l'avenir.
  </p>
</div>
</body>
</html>
"""

ROW_TEMPLATE = """        <tr>
          <td>{horodatage_alerte}</td>
          <td>{marche}</td>
          <td>{nom} ({ticker})</td>
          <td>{cours_depart} €</td>
          <td>+{pourcentage_predit}%</td>
          <td>{cours_cible} €</td>
          <td>{echeance_prevue}</td>
          <td>{cours_reel}</td>
          <td>{ecart_reel}</td>
          <td>{resultat_pill}</td>
        </tr>"""


def _classify(row):
    """Détermine la catégorie d'une ligne vérifiée : atteint / manque / justesse."""
    atteint = row.get("objectif_atteint", "")
    if not atteint:
        return "attente"

    try:
        predit = float(row["pourcentage_predit"])
        reel = float(row["ecart_reel_pct"])
    except (KeyError, ValueError):
        return "atteint" if atteint == "Oui" else "manque"

    if predit > 0:
        ratio = reel / predit
        if cfg.JUSTESSE_RATIO_LOW <= ratio <= cfg.JUSTESSE_RATIO_HIGH:
            return "justesse"
    return "atteint" if atteint == "Oui" else "manque"


_PILL_LABELS = {
    "atteint": "Atteint",
    "manque": "Manqué",
    "justesse": "De justesse",
    "attente": "En attente",
}


def _format_row(row):
    category = _classify(row)
    pill = f'<span class="pill pill-{category}">{_PILL_LABELS[category]}</span>'

    cours_reel = f"{float(row['cours_reel_echeance']):.2f} €" if row.get("cours_reel_echeance") else "—"
    ecart_reel = f"{float(row['ecart_reel_pct']):+.1f}%" if row.get("ecart_reel_pct") else "—"

    return ROW_TEMPLATE.format(
        horodatage_alerte=html.escape(row["horodatage_alerte"]),
        marche=html.escape(row.get("marche", "")),
        nom=html.escape(row["nom"]),
        ticker=html.escape(row["ticker"]),
        cours_depart=f"{float(row['cours_depart']):.2f}",
        pourcentage_predit=f"{float(row['pourcentage_predit']):.1f}",
        cours_cible=f"{float(row['cours_cible']):.2f}",
        echeance_prevue=html.escape(row["echeance_prevue"]),
        cours_reel=cours_reel,
        ecart_reel=ecart_reel,
        resultat_pill=pill,
    ), category


def generate(csv_path=None, output_path=None):
    csv_path = csv_path or cfg.PREDICTIONS_CSV_FILE
    output_path = output_path or cfg.PREDICTIONS_REPORT_FILE

    rows = read_rows(csv_path)
    rows.sort(key=lambda r: r["horodatage_alerte"], reverse=True)

    rows_html_parts = []
    categories = []
    for row in rows:
        row_html, category = _format_row(row)
        rows_html_parts.append(row_html)
        categories.append(category)

    nb_total = len(rows)
    nb_attente = categories.count("attente")
    nb_verifiees = nb_total - nb_attente
    nb_atteints = sum(1 for r in rows if r.get("objectif_atteint") == "Oui")
    taux_reussite = f"{100 * nb_atteints / nb_verifiees:.0f}%" if nb_verifiees else "—"

    html_content = PAGE_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        taux_reussite=taux_reussite,
        nb_verifiees=nb_verifiees,
        nb_attente=nb_attente,
        nb_total=nb_total,
        rows_html="\n".join(rows_html_parts) if rows_html_parts else "        <tr><td colspan=\"10\">Aucune prédiction enregistrée pour le moment.</td></tr>",
    )

    import os
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Page générée : {output_path} ({nb_total} prédiction(s), {nb_verifiees} vérifiée(s), taux de réussite {taux_reussite}).")


if __name__ == "__main__":
    generate()
