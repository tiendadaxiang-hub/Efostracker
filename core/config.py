"""
config.py — Configuración central del tracker EFOS/EDOS SAT
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar archivo .env si existe
load_dotenv()

# ─── Rutas base ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
LOGS_DIR = BASE_DIR / "logs"

# ─── URLs oficiales SAT ───────────────────────────────────────────────────────
SAT_PORTAL_URL = (
    "https://www.sat.gob.mx/minisitio/DatosAbiertos/contribuyentes_publicados.html"
)
SAT_CSV_URL = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos/Documents_AGAFF/Listado_completo_69-B.csv"
)
SAT_CSV_DEFINITIVOS = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos/Documents_AGAFF/Definitivos.csv"
)
SAT_CSV_PRESUNTOS = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos/Documents_AGAFF/Presuntos.csv"
)
SAT_CSV_DESVIRTUADOS = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos/Documents_AGAFF/Desvirtuados.csv"
)
SAT_CSV_SENTENCIAS = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos/Documents_AGAFF/SentenciasFavorables.csv"
)
SAT_CSV_69B_BIS = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos/Documents_AGGC/Listado_69_B_Bis_Completo.csv"
)
SAT_CSV_URL_LEGACY = (
    "http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv"
)
DOF_BASE_URL = "https://www.dof.gob.mx/nota_detalle.php"

# ─── Encoding del archivo SAT ─────────────────────────────────────────────────
SAT_CSV_ENCODING = "windows-1250"
SAT_CSV_HEADER_SKIP = 3
SAT_CSV_DELIMITER = ","
SAT_CSV_QUOTECHAR = '"'

# ─── Columnas esperadas ───────────────────────────────────────────────────────
COL_MAP = {
    0: "numero",
    1: "rfc",
    2: "nombre",
    3: "situacion",
    4: "fecha_primera_publicacion",
    5: "numero_oficio",
}

SITUACION_PRESUNTO = "presunto"
SITUACION_DEFINITIVO = "definitivo"
SITUACION_DESVIRTUADO = "desvirtuado"
SITUACION_SENTENCIA = "sentencia favorable"

# ─── Nombres de archivos ──────────────────────────────────────────────────────
RAW_CSV_NAME = "listado_69b_raw_{fecha}.csv"
PROCESSED_CSV_NAME = "listado_69b_{fecha}.csv"
LAST_SNAPSHOT_NAME = "listado_69b_latest.csv"
DIFF_LOG_NAME = "diff_{fecha}.json"

# ─── Scheduler ────────────────────────────────────────────────────────────────
SCHEDULE_TIME = os.getenv("EFOS_SCHEDULE_TIME", "06:00")
RUN_ON_START = os.getenv("EFOS_RUN_ON_START", "true").lower() == "true"

# ─── Red y reintentos ─────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 60
MAX_RETRIES = 5
RETRY_BACKOFF = 2.0
USER_AGENT = (
    "sat-efos-tracker/1.0 (github.com/Ar0d3x/sat-efos-tracker; "
    "dr.nietodavid@protonmail.com)"
)

# ─── Notificaciones ───────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("EFOS_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("EFOS_SMTP_PORT", "587"))
SMTP_USER = os.getenv("EFOS_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("EFOS_SMTP_PASS", "")
NOTIFY_FROM = os.getenv("EFOS_NOTIFY_FROM", "")
NOTIFY_TO = os.getenv("EFOS_NOTIFY_TO", "")
NOTIFY_ON_NEW = os.getenv("EFOS_NOTIFY_ON_NEW", "true").lower() == "true"


def reload_config():
    """Recarga las variables de entorno desde .env (útil después de guardar cambios)."""
    load_dotenv(override=True)
    global SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_FROM, NOTIFY_TO, NOTIFY_ON_NEW
    SMTP_HOST = os.getenv("EFOS_SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("EFOS_SMTP_PORT", "587"))
    SMTP_USER = os.getenv("EFOS_SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("EFOS_SMTP_PASS", "")
    NOTIFY_FROM = os.getenv("EFOS_NOTIFY_FROM", "")
    NOTIFY_TO = os.getenv("EFOS_NOTIFY_TO", "")
    NOTIFY_ON_NEW = os.getenv("EFOS_NOTIFY_ON_NEW", "true").lower() == "true"