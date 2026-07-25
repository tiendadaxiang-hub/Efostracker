from __future__ import annotations
"""
checker.py — Consulta de RFC(s) contra el listado local 69-B
Uso CLI:
    python checker.py RFC1 [RFC2 RFC3 ...]
Uso como módulo:
    from checker import consultar_rfc, consultar_lote
"""
import csv
import logging
import sys
from pathlib import Path

from core import config
from core.parser import cargar_procesado, registros_a_dict_rfc

logger = logging.getLogger(__name__)

# Cache en memoria para evitar releer el CSV en cada consulta
_CACHE: dict[str, dict] | None = None
_CACHE_MTIME: float = 0.0


def _cargar_cache(forzar: bool = False) -> dict[str, dict]:
    """Carga o refresca el índice RFC→registro desde el CSV procesado."""
    global _CACHE, _CACHE_MTIME
    ruta = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
    
    if not ruta.exists():
        logger.warning("[checker] No hay listado procesado disponible. Ejecuta el scheduler primero.")
        return {}
    
    mtime = ruta.stat().st_mtime
    if _CACHE is None or forzar or mtime != _CACHE_MTIME:
        registros = cargar_procesado(ruta)
        _CACHE = registros_a_dict_rfc(registros)
        _CACHE_MTIME = mtime
        logger.info(f"[checker] Índice cargado: {len(_CACHE):,} RFCs")
    
    return _CACHE


# ─── API pública ─────────────────────────────────────────────────────────────

def consultar_rfc(rfc: str) -> dict:
    """
    Consulta un RFC individual.
    
    Returns
    -------
    dict con claves:
        rfc         str
        encontrado  bool
        situacion   str | None   (solo si encontrado)
        nombre      str | None
        fecha_primera_publicacion  str | None
        numero_oficio  str | None
        fuente      str   "local" siempre (consulta offline)
    """
    rfc = rfc.strip().upper()
    indice = _cargar_cache()
    
    if rfc in indice:
        r = indice[rfc]
        return {
            "rfc": rfc,
            "encontrado": True,
            "situacion": r.get("situacion"),
            "nombre": r.get("nombre"),
            "fecha_primera_publicacion": r.get("fecha_primera_publicacion"),
            "numero_oficio": r.get("numero_oficio"),
            "fuente": "local",
        }
    
    return {
        "rfc": rfc,
        "encontrado": False,
        "situacion": None,
        "nombre": None,
        "fecha_primera_publicacion": None,
        "numero_oficio": None,
        "fuente": "local",
    }


def consultar_lote(rfcs: list[str]) -> list[dict]:
    """Consulta una lista de RFCs y retorna una lista de resultados."""
    return [consultar_rfc(r) for r in rfcs]


def consultar_desde_csv(ruta_entrada: Path, columna_rfc: str = "rfc") -> list[dict]:
    """
    Lee un CSV con una columna de RFCs y retorna los resultados de consulta.
    Útil para verificar lotes de proveedores de forma masiva.
    """
    resultados = []
    with open(ruta_entrada, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            rfc = fila.get(columna_rfc, "").strip().upper()
            if rfc:
                resultado = consultar_rfc(rfc)
                # Preservar columnas originales del CSV de entrada
                resultados.append({**fila, **resultado})
    return resultados


def _imprimir_resultado(r: dict) -> None:
    """Imprime un resultado de consulta en formato legible."""
    estado = "⚠️  EN LISTA " if r["encontrado"] else "✅  NO encontrado "
    print(f"\n{'─'*50} ")
    print(f"  RFC       : {r['rfc']} ")
    print(f"  Estado    : {estado} ")
    if r["encontrado"]:
        sit = r["situacion"].upper() if r["situacion"] else "DESCONOCIDA "
        print(f"  Situación : {sit} ")
        print(f"  Nombre    : {r['nombre'] or 'N/D'} ")
        print(f"  Publicado : {r['fecha_primera_publicacion'] or 'N/D'} ")
        print(f"  Oficio    : {r['numero_oficio'] or 'N/D'} ")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)   # silenciar INFO en modo CLI
    
    if len(sys.argv) < 2:
        print("Uso: python checker.py RFC1 [RFC2 RFC3 ...]")
        print("     python checker.py --csv proveedores.csv [--col rfc]")
        sys.exit(1)
    
    args = sys.argv[1:]
    
    if args[0] == "--csv":
        # Modo lote desde CSV
        ruta = Path(args[1])
        col = args[3] if len(args) > 3 and args[2] == "--col" else "rfc"
        resultados = consultar_desde_csv(ruta, columna_rfc=col)
        en_lista = [r for r in resultados if r["encontrado"]]
        print(f"\nTotal consultados : {len(resultados)}")
        print(f"En lista 69-B     : {len(en_lista)}")
        for r in en_lista:
            _imprimir_resultado(r)
    else:
        # Modo individual por argumentos
        for rfc_arg in args:
            resultado = consultar_rfc(rfc_arg)
            _imprimir_resultado(resultado)
    
    print(f"\n{'─'*50}")
    print("Fuente: listado local (Art. 69-B CFF) — sat.gob.mx")