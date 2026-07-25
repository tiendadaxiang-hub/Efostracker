import sqlite3
import logging
from pathlib import Path
from core import config

logger = logging.getLogger(__name__)
DB_PATH = config.BASE_DIR / "efos_tracker.db"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfc TEXT UNIQUE NOT NULL,
            alias TEXT,
            categoria TEXT DEFAULT 'Proveedor',
            notas TEXT,
            fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo INTEGER DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sat_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_descarga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_registros INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sat_registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfc TEXT NOT NULL,
            nombre TEXT,
            situacion TEXT,
            fecha_primera_publicacion TEXT,
            numero_oficio TEXT,
            snapshot_id INTEGER,
            FOREIGN KEY (snapshot_id) REFERENCES sat_snapshots(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rfc ON sat_registros(rfc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_rfc ON watchlist(rfc)")
    conn.commit()
    conn.close()
    logger.info(f"[database] BD inicializada: {DB_PATH}")

init_db()
