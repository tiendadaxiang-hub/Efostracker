"""
watchlist.py — Gestión de RFCs a monitorear (Proveedores, Socios, Clientes)
"""
import logging
from core.database import get_connection
from core.parser import cargar_procesado, registros_a_dict_rfc
from core import config

logger = logging.getLogger(__name__)

def agregar_rfc(rfc: str, alias: str = "", categoria: str = "Proveedor", notas: str = "") -> bool:
    """Agrega un RFC a la lista de monitoreo persistente."""
    rfc = rfc.strip().upper()
    if len(rfc) < 12 or len(rfc) > 13:
        logger.warning(f"[watchlist] RFC inválido: {rfc}")
        return False
        
    conn = get_connection()
    try:
        # INSERT OR IGNORE evita errores si el RFC ya existe
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (rfc, alias, categoria, notas) VALUES (?, ?, ?, ?)",
            (rfc, alias, categoria, notas)
        )
        conn.commit()
        logger.info(f"[watchlist] RFC {rfc} ({categoria}) agregado a la watchlist.")
        return True
    except Exception as e:
        logger.error(f"[watchlist] Error al agregar RFC: {e}")
        return False
    finally:
        conn.close()

def listar_watchlist() -> list[dict]:
    """Retorna todos los RFCs activos en la watchlist."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM watchlist WHERE activo = 1 ORDER BY categoria, rfc")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def eliminar_rfc(rfc: str) -> bool:
    """Desactiva un RFC de la watchlist (soft delete para mantener historial)."""
    rfc = rfc.strip().upper()
    conn = get_connection()
    try:
        conn.execute("UPDATE watchlist SET activo = 0 WHERE rfc = ?", (rfc,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"[watchlist] Error al eliminar RFC: {e}")
        return False
    finally:
        conn.close()

def verificar_alertas_watchlist() -> list[dict]:
    """
    Cruza la watchlist con el último snapshot del SAT.
    Retorna una lista de RFCs de tu radar que están en el listado 69-B.
    """
    ruta_latest = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
    if not ruta_latest.exists():
        logger.warning("[watchlist] No hay listado del SAT para verificar alertas.")
        return []

    # Cargamos el último SAT en memoria para el cruce
    indice_sat = registros_a_dict_rfc(cargar_procesado(ruta_latest))
    watchlist = listar_watchlist()
    
    alertas = []
    for item in watchlist:
        rfc = item["rfc"]
        if rfc in indice_sat:
            sat_data = indice_sat[rfc]
            alertas.append({
                "rfc": rfc,
                "alias": item["alias"],
                "categoria": item["categoria"],
                "situacion": sat_data["situacion"],
                "nombre_sat": sat_data["nombre"],
                "fecha_publicacion": sat_data["fecha_primera_publicacion"]
            })
            
    if alertas:
        logger.warning(f"[watchlist] ⚠️ ALERTA CRÍTICA: {len(alertas)} RFCs de tu radar están en el listado 69-B!")
    else:
        logger.info("[watchlist] ✅ Todos los RFCs monitoreados están limpios.")
        
    return alertas