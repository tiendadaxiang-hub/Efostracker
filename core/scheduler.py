from __future__ import annotations
"""
scheduler.py — Orquestador principal del tracker SAT 69-B

Flujo por ejecución:
  1. Descargar CSV del SAT
  2. Comparar hash con snapshot anterior
  3. Si hubo cambio: parsear → normalizar → diff → log → notificar
  4. Si no hubo cambio: registrar en log y dormir hasta próxima ejecución

Uso:
    python scheduler.py              # Inicia el loop (descarga diaria a la hora de config)
    python scheduler.py --now        # Ejecuta UNA vez inmediatamente y sale
    python scheduler.py --status     # Muestra resumen del último diff guardado
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule

from core import config
from core.downloader import download_csv, get_latest_raw
from core.parser import parse_csv, registros_a_dict_rfc, guardar_procesado, cargar_procesado
from core.differ import comparar, guardar_diff, cargar_ultimo_diff, resumen_texto
from core.notifier import enviar_reporte

# ─── Logging ─────────────────────────────────────────────────────────────────
config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            config.LOGS_DIR / "tracker.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("scheduler")


# ─── Pipeline principal ──────────────────────────────────────────────────────

def ejecutar_ciclo() -> bool:
    """
    Ejecuta un ciclo completo de descarga, parseo, diff y notificación.

    Returns True si el ciclo completó sin errores críticos.
    """
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    logger.info(f"{'='*60}")
    logger.info(f"CICLO INICIADO — {fecha}")
    logger.info(f"{'='*60}")

    # ── 1. Descarga ───────────────────────────────────────────────────────────
    ruta_raw = download_csv()
    if ruta_raw is None:
        logger.error("Descarga fallida. Ciclo abortado.")
        return False

    # ── 2. Cargar snapshot anterior (antes de sobreescribir) ──────────────────
    anterior: dict[str, dict] = {}
    ruta_latest = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
    if ruta_latest.exists():
        anterior = registros_a_dict_rfc(cargar_procesado(ruta_latest))
        logger.info(f"Snapshot anterior cargado: {len(anterior):,} RFCs")
    else:
        logger.info("No hay snapshot anterior — primera ejecución.")

    # ── 3. Parsear CSV raw ────────────────────────────────────────────────────
    try:
        registros = parse_csv(ruta_raw)
    except Exception as e:
        logger.error(f"Error al parsear CSV: {e}")
        return False

    if not registros:
        logger.error("El parser no devolvió registros. Revisa el CSV raw.")
        return False

    # ── 4. Guardar CSV procesado ──────────────────────────────────────────────
    guardar_procesado(registros, fecha=fecha)
    nuevo = registros_a_dict_rfc(registros)

    # ── 5. Diff ───────────────────────────────────────────────────────────────
    if anterior:
        diff = comparar(anterior, nuevo)
        guardar_diff(diff, fecha=fecha)

        resumen = resumen_texto(diff)
        logger.info(f"\n{resumen}")

        # ── 6. Notificación ───────────────────────────────────────────────────
        enviado = enviar_reporte(diff)
        if enviado:
            logger.info("Notificación enviada.")
    else:
        logger.info(
            f"Primera ejecución — {len(nuevo):,} RFCs indexados. "
            "No hay diff (no hay snapshot anterior)."
        )

    logger.info(f"{'='*60}")
    logger.info("CICLO COMPLETADO")
    logger.info(f"{'='*60}")
    return True


# ─── Modo --status ────────────────────────────────────────────────────────────

def mostrar_status() -> None:
    """Imprime el resumen del último diff disponible."""
    diff = cargar_ultimo_diff()
    if diff is None:
        print("No hay diffs guardados. Ejecuta el tracker al menos una vez.")
        return
    print(resumen_texto(diff))

    # Resumen del índice actual
    ruta = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
    if ruta.exists():
        from parser import cargar_procesado, registros_a_dict_rfc
        registros = cargar_procesado(ruta)
        por_situacion: dict[str, int] = {}
        for r in registros:
            s = r.get("situacion", "desconocida")
            por_situacion[s] = por_situacion.get(s, 0) + 1

        print("\n── Distribución actual por situación ─────────────────")
        for sit, cnt in sorted(por_situacion.items(), key=lambda x: -x[1]):
            print(f"  {sit.upper():<20} : {cnt:,}")
        print(f"  {'TOTAL':<20} : {len(registros):,}")

        mtime = datetime.fromtimestamp(ruta.stat().st_mtime)
        print(f"\n  Última actualización del snapshot: {mtime:%Y-%m-%d %H:%M}")


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Tracker automático del listado SAT Art. 69-B CFF"
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Ejecutar un ciclo inmediatamente y salir",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostrar resumen del último diff y salir",
    )
    args = parser.parse_args()

    if args.status:
        mostrar_status()
        sys.exit(0)

    if args.now:
        ok = ejecutar_ciclo()
        sys.exit(0 if ok else 1)

    # ── Modo daemon: descarga diaria programada ───────────────────────────────
    logger.info(f"Tracker iniciado. Descarga programada: {config.SCHEDULE_TIME} (hora local)")

    if config.RUN_ON_START:
        logger.info("RUN_ON_START=true — ejecutando ciclo inicial...")
        ejecutar_ciclo()

    schedule.every().day.at(config.SCHEDULE_TIME).do(ejecutar_ciclo)
    logger.info("Esperando próxima ejecución programada. Ctrl+C para detener.")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
