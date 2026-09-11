"""Récupération des données de marché via Yahoo Finance (yfinance)."""

import yfinance as yf


def fetch_history(ticker, period="6mo"):
    """Retourne l'historique quotidien (Open/High/Low/Close/Volume) d'une valeur."""
    return yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)


def fetch_fundamentals(ticker):
    """Retourne quelques données fondamentales simples (peuvent être absentes)."""
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        info = {}
    return {
        "trailing_pe": info.get("trailingPE"),
    }
