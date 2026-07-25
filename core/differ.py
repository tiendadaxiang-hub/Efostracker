from __future__ import annotations
"""
differ.py — Detección de cambios entre snapshots del listado 69-B

Compara el snapshot anterior contra el nuevo y clasifica los movimientos:
  - NUEVO:    RFC aparece por primera vez
  - CAMBIO:   RFC ya existía pero cambió de situación (p.ej. presunto → definitivo)
  - BAJA:     RFC desapareció del listado (raro, pero ocurre cuando el SAT lo retira)
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from core import config

logger = logging.getLogger(__name__)


# ─── Tipos de movimiento ─────────────────────────────────────────────────────
TIPO_NUEVO   = "NUEVO"
TIPO_CAMBIO  = "CAMBIO"
TIPO_BAJA    = "BAJA"


def comparar(
    anterior: dict[str, dict],
    nuevo: dict[str, dict],
) -> dict:
    """
    Recibe dos dicts {rfc: registro} y retorna un resumen de diferencias.

    Returns
    -------
    dict con claves:
        fecha_comparacion   str  ISO datetime
        total_anterior      int
        total_nuevo         int
        nuevos              list[dict]   RFCs que aparecen por primera vez
        cambios             list[dict]   RFCs cuya situación cambió
        bajas               list[dict]   RFCs que ya no aparecen
        sin_cambio          int          Cantidad sin modificación
    """
    rfcs_ant = set(anterior.keys())
    rfcs_nvo = set(nuevo.keys())

    nuevos  = []
    cambios = []
    bajas   = []
    sin_cambio = 0

    # RFCs nuevos
    for rfc in rfcs_nvo - rfcs_ant:
        nuevos.append(nuevo[rfc])

    # RFCs que desaparecieron
    for rfc in rfcs_ant - rfcs_nvo:
        bajas.append(anterior[rfc])

    # RFCs en ambos: revisar si cambió la situación
    for rfc in rfcs_ant & rfcs_nvo:
        sit_ant = anterior[rfc].get("situacion", "")
        sit_nvo = nuevo[rfc].get("situacion", "")
        if sit_ant != sit_nvo:
            cambios.append({
                **nuevo[rfc],
                "situacion_anterior": sit_ant,
                "situacion_nueva": sit_nvo,
            })
        else:
            sin_cambio += 1

    resumen = {
        "fecha_comparacion": datetime.now().isoformat(),
        "total_anterior": len(anterior),
        "total_nuevo": len(nuevo),
        "nuevos": nuevos,
        "cambios": cambios,
        "bajas": bajas,
        "sin_cambio": sin_cambio,
    }

    logger.info(
        f"[differ] Nuevos: {len(nuevos)} | "
        f"Cambios: {len(cambios)} | "
        f"Bajas: {len(bajas)} | "
        f"Sin cambio: {sin_cambio}"
    )
    return resumen


def guardar_diff(diff: dict, fecha: str | None = None) -> Path:
    """Persiste el diff como JSON en logs/."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if fecha is None:
        fecha = datetime.now().strftime("%Y%m%d_%H%M")

    nombre = config.DIFF_LOG_NAME.format(fecha=fecha)
    destino = config.LOGS_DIR / nombre

    with open(destino, "w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)

    logger.info(f"[differ] Diff guardado: {destino}")
    return destino


def cargar_ultimo_diff() -> dict | None:
    """Carga el diff más reciente disponible en logs/."""
    archivos = sorted(config.LOGS_DIR.glob("diff_*.json"))
    if not archivos:
        return None
    with open(archivos[-1], encoding="utf-8") as f:
        return json.load(f)


def resumen_texto(diff: dict) -> str:
    """Genera un resumen legible en texto plano del diff."""
    lines = [
        "=" * 60,
        f"SAT 69-B — Reporte de cambios",
        f"Fecha: {diff['fecha_comparacion']}",
        "=" * 60,
        f"Total anterior : {diff['total_anterior']:,}",
        f"Total actual   : {diff['total_nuevo']:,}",
        f"Nuevos         : {len(diff['nuevos']):,}",
        f"Cambios        : {len(diff['cambios']):,}",
        f"Bajas          : {len(diff['bajas']):,}",
        f"Sin cambio     : {diff['sin_cambio']:,}",
    ]

    if diff["nuevos"]:
        lines.append("\n── NUEVOS EN LISTA ──────────────────────────────────")
        for r in diff["nuevos"][:50]:   # limitar a 50 en el resumen
            lines.append(
                f"  {r['rfc']:<15} [{r['situacion'].upper():<12}] {r['nombre'][:60]}"
            )
        if len(diff["nuevos"]) > 50:
            lines.append(f"  ... y {len(diff['nuevos']) - 50} más (ver JSON)")

    if diff["cambios"]:
        lines.append("\n── CAMBIOS DE SITUACIÓN ─────────────────────────────")
        for r in diff["cambios"][:30]:
            lines.append(
                f"  {r['rfc']:<15} "
                f"{r['situacion_anterior'].upper()} → {r['situacion_nueva'].upper()} "
                f"| {r['nombre'][:40]}"
            )
        if len(diff["cambios"]) > 30:
            lines.append(f"  ... y {len(diff['cambios']) - 30} más (ver JSON)")

    if diff["bajas"]:
        lines.append("\n── BAJAS DEL LISTADO ────────────────────────────────")
        for r in diff["bajas"][:20]:
            lines.append(f"  {r['rfc']:<15} {r['nombre'][:60]}")
        if len(diff["bajas"]) > 20:
            lines.append(f"  ... y {len(diff['bajas']) - 20} más (ver JSON)")

    lines.append("=" * 60)
    return "\n".join(lines)
