"""Ayar dosyalarını ve gizli anahtarları okur."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def settings() -> dict:
    return load_yaml("settings.yaml")


def destinations() -> dict:
    return load_yaml("destinations.yaml")


def seasons() -> list[dict]:
    return load_yaml("seasons.yaml").get("seasons", [])


def secret(name: str, required: bool = True) -> str | None:
    """GitHub Secrets'tan gelen ortam değişkenini okur."""
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise SystemExit(
            f"'{name}' bulunamadı. GitHub'da Settings → Secrets and variables → Actions "
            f"bölümüne '{name}' adıyla eklendiğinden emin ol."
        )
    return value or None
