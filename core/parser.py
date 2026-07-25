from __future__ import annotations
"""
parser.py — Limpieza y normalización del CSV del SAT (Art. 69-B CFF)

El SAT publica el CSV con:
  - Encoding windows-1250
  - 3 filas de metadatos al inicio (se saltan)
  - Columnas sin nombres garantizados (se mapean por posición)
  - Datos inconsistentes en mayúsculas/espacios
"""

import csv
import logging
from datetime import datetime
from itertools import islice
from pathlib import Path

from core import config

logger = logging.getLogger(__name__)


# ─── Normalización ───────────────────────────────────────────────────────────

def _limpiar_rfc(rfc: str) -> str:
    return rfc.strip().upper()


def _limpiar_nombre(nombre: str) -> str:
    return " ".join(nombre.strip().upper().split())


def _normalizar_situacion(situacion: str) -> str:
    s = situacion.strip().lower()
    mapeo = {
        "presunto": config.SITUACION_PRESUNTO,
        "definitivo": config.SITUACION_DEFINITIVO,
        "desvirtuado": config.SITUACION_DESVIRTUADO,
        "sentencia favorable": config.SITUACION_SENTENCIA,
        "sentencia": config.SITUACION_SENTENCIA,
    }
    for clave, valor in mapeo.items():
        if clave in s:
            return valor
    return s  # devolver tal cual si no coincide


def _limpiar_fecha(fecha: str) -> str:
    """Intenta normalizar fechas DD/MM/YYYY → YYYY-MM-DD. Si falla, devuelve original."""
    fecha = fecha.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return fecha


# ─── Parser principal ────────────────────────────────────────────────────────

def parse_csv(ruta: Path) -> list[dict]:
    """
    Lee el CSV raw del SAT y retorna una lista de dicts normalizados.

    Cada dict tiene las claves definidas en config.COL_MAP.
    Filas con RFC vacío o inválido se descartan con advertencia.
    """
    if not ruta.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    registros: list[dict] = []
    errores = 0

    with open(ruta, "rb") as f:
        contenido = f.read().decode(config.SAT_CSV_ENCODING, errors="replace")

    lineas = contenido.splitlines(keepends=True)
    # Saltar las primeras N filas de metadatos del SAT
    lineas_datos = list(islice(lineas, config.SAT_CSV_HEADER_SKIP, None))

    reader = csv.reader(
        lineas_datos,
        delimiter=config.SAT_CSV_DELIMITER,
        quotechar=config.SAT_CSV_QUOTECHAR,
    )

    for num_linea, fila in enumerate(reader, start=config.SAT_CSV_HEADER_SKIP + 1):
        # Saltar filas vacías o de encabezado repetido
        if not fila or not any(c.strip() for c in fila):
            continue
        # El SAT a veces repite la fila de encabezado mid-file
        if fila[0].strip().lower() in ("n°", "no.", "numero", "#", "num"):
            continue

        try:
            # Mapear columnas por posición según config.COL_MAP
            registro = {}
            for idx, clave in config.COL_MAP.items():
                registro[clave] = fila[idx].strip() if idx < len(fila) else ""

            # Validar RFC mínimamente (persona física: 13 chars, moral: 12)
            rfc = _limpiar_rfc(registro.get("rfc", ""))
            if len(rfc) < 12 or len(rfc) > 13:
                logger.debug(f"[parser] Línea {num_linea}: RFC inválido '{rfc}' — descartado")
                errores += 1
                continue

            registro["rfc"]                    = rfc
            registro["nombre"]                 = _limpiar_nombre(registro.get("nombre", ""))
            registro["situacion"]              = _normalizar_situacion(registro.get("situacion", ""))
            registro["fecha_primera_publicacion"] = _limpiar_fecha(registro.get("fecha_primera_publicacion", ""))
            registro["numero_oficio"]          = registro.get("numero_oficio", "").strip()

            registros.append(registro)

        except (IndexError, KeyError) as e:
            logger.warning(f"[parser] Línea {num_linea}: error de estructura — {e}")
            errores += 1
            continue

    logger.info(
        f"[parser] Parseados {len(registros):,} registros válidos. "
        f"Descartados: {errores}"
    )
    return registros


def registros_a_dict_rfc(registros: list[dict]) -> dict[str, dict]:
    """
    Convierte la lista de registros en un dict indexado por RFC.
    Si un RFC aparece más de una vez, prevalece el registro con
    situación más grave (definitivo > presunto > desvirtuado).
    """
    PESO = {
        config.SITUACION_DEFINITIVO:  3,
        config.SITUACION_PRESUNTO:    2,
        config.SITUACION_SENTENCIA:   1,
        config.SITUACION_DESVIRTUADO: 0,
    }
    resultado: dict[str, dict] = {}
    for r in registros:
        rfc = r["rfc"]
        if rfc not in resultado:
            resultado[rfc] = r
        else:
            peso_nuevo   = PESO.get(r["situacion"], -1)
            peso_actual  = PESO.get(resultado[rfc]["situacion"], -1)
            if peso_nuevo > peso_actual:
                resultado[rfc] = r
    return resultado


def guardar_procesado(registros: list[dict], fecha: str | None = None) -> Path:
    """Guarda los registros normalizados como CSV en data/processed/."""
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    if fecha is None:
        fecha = datetime.now().strftime("%Y%m%d_%H%M")

    nombre = config.PROCESSED_CSV_NAME.format(fecha=fecha)
    destino = config.DATA_PROCESSED / nombre

    claves = list(config.COL_MAP.values())
    with open(destino, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=claves)
        writer.writeheader()
        writer.writerows(registros)

    # Actualizar latest procesado
    latest = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
    with open(latest, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=claves)
        writer.writeheader()
        writer.writerows(registros)

    logger.info(f"[parser] CSV procesado guardado: {destino}")

    # --- NUEVO: Guardar en SQLite ---
    from database import get_connection
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO sat_snapshots (total_registros) VALUES (?)",
            (len(registros),)
        )
        snapshot_id = cursor.lastrowid
        
        # Preparar datos para inserción masiva
        datos = [
            (
                r["rfc"],
                r["nombre"],
                r["situacion"],
                r["fecha_primera_publicacion"],
                r["numero_oficio"],
                snapshot_id
            )
            for r in registros
        ]
        
        conn.executemany("""
            INSERT INTO sat_registros 
            (rfc, nombre, situacion, fecha_primera_publicacion, numero_oficio, snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, datos)
        
        conn.commit()
        logger.info(f"[parser] {len(registros)} registros guardados en SQLite (Snapshot ID: {snapshot_id})")
    except Exception as e:
        logger.error(f"[parser] Error al guardar en SQLite: {e}")
    finally:
        conn.close()
    return destino


def cargar_procesado(ruta: Path | None = None) -> list[dict]:
    """Carga el último CSV procesado disponible."""
    if ruta is None:
        ruta = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
