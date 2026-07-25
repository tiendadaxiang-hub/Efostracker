from __future__ import annotations
"""
downloader.py — Descarga del CSV oficial del SAT con reintentos y verificación
"""

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path

import requests

from core import config

logger = logging.getLogger(__name__)


# ─── Utilidades ──────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    """Calcula el SHA-256 de un archivo para detectar cambios reales."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})
    return session


# ─── Descarga principal ──────────────────────────────────────────────────────

def download_csv(url: str = config.SAT_CSV_URL) -> Path | None:
    """
    Descarga el CSV del SAT con backoff exponencial.

    Retorna la ruta al archivo RAW guardado, o None si falló todo.
    Si el contenido es idéntico al último descargado, retorna la ruta
    del archivo existente sin crear uno nuevo (evita duplicados).
    """
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    session = _get_session()

    raw_content: bytes | None = None

    for intento in range(1, config.MAX_RETRIES + 1):
        try:
            logger.info(f"[descarga] Intento {intento}/{config.MAX_RETRIES} → {url}")
            resp = session.get(url, timeout=config.REQUEST_TIMEOUT, stream=True)
            resp.raise_for_status()

            raw_content = resp.content
            logger.info(
                f"[descarga] OK — {len(raw_content):,} bytes recibidos"
            )
            break

        except requests.RequestException as e:
            wait = config.RETRY_BACKOFF ** intento
            logger.warning(f"[descarga] Error intento {intento}: {e}. Reintento en {wait:.0f}s")
            if intento < config.MAX_RETRIES:
                time.sleep(wait)
            else:
                logger.error("[descarga] Se agotaron los reintentos. Abortando.")
                return None

    if raw_content is None:
        return None

    # ── Comparar con el último archivo para detectar si hubo cambio ──────────
    latest = config.DATA_RAW / config.LAST_SNAPSHOT_NAME
    if latest.exists():
        nuevo_hash = hashlib.sha256(raw_content).hexdigest()
        viejo_hash = _sha256(latest)
        if nuevo_hash == viejo_hash:
            logger.info("[descarga] Contenido idéntico al anterior — sin cambios en el SAT.")
            return latest

    # ── Guardar archivo con timestamp ─────────────────────────────────────────
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    nombre = config.RAW_CSV_NAME.format(fecha=fecha)
    destino = config.DATA_RAW / nombre

    destino.write_bytes(raw_content)
    logger.info(f"[descarga] Guardado: {destino}")

    # Actualizar symlink/copia "latest"
    latest.write_bytes(raw_content)
    logger.info(f"[descarga] Snapshot latest actualizado: {latest}")

    return destino


def get_latest_raw() -> Path | None:
    """Retorna la ruta al CSV raw más reciente disponible localmente."""
    latest = config.DATA_RAW / config.LAST_SNAPSHOT_NAME
    if latest.exists():
        return latest
    # Fallback: buscar por nombre
    archivos = sorted(config.DATA_RAW.glob("listado_69b_raw_*.csv"))
    return archivos[-1] if archivos else None
