"""
notifier.py — Notificaciones opcionales por correo cuando hay cambios en el listado

Configura mediante variables de entorno (ver config.py):
    EFOS_SMTP_HOST, EFOS_SMTP_PORT, EFOS_SMTP_USER, EFOS_SMTP_PASS
    EFOS_NOTIFY_FROM, EFOS_NOTIFY_TO
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core import config
from core.differ import resumen_texto

logger = logging.getLogger(__name__)


def _smtp_configurado() -> bool:
    """Verifica que todas las credenciales SMTP estén configuradas."""
    return all([
        config.SMTP_HOST,
        config.SMTP_USER,
        config.SMTP_PASSWORD,
        config.NOTIFY_FROM,
        config.NOTIFY_TO,
    ])


def enviar_reporte(diff: dict) -> bool:
    """
    Envía un correo con el resumen de cambios si hay novedades.
    
    Returns True si el correo se envió, False si no había config o no había cambios.
    """
    if not config.NOTIFY_ON_NEW:
        logger.info("[notifier] Notificaciones desactivadas.")
        return False

    if not _smtp_configurado():
        logger.info("[notifier] SMTP no configurado — omitiendo notificación.")
        return False

    n_nuevos = len(diff.get("nuevos", []))
    n_cambios = len(diff.get("cambios", []))
    n_bajas = len(diff.get("bajas", []))

    if n_nuevos + n_cambios + n_bajas == 0:
        logger.info("[notifier] Sin cambios relevantes — no se envía correo.")
        return False

    asunto = (
        f"[SAT 69-B] Cambios detectados: "
        f"+{n_nuevos} nuevos | {n_cambios} cambios | -{n_bajas} bajas"
    )
    cuerpo_texto = resumen_texto(diff)
    cuerpo_html = _texto_a_html(cuerpo_texto)

    destinatarios = [d.strip() for d in config.NOTIFY_TO.split(",") if d.strip()]

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = config.NOTIFY_FROM
        msg["To"] = ", ".join(destinatarios)

        msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.NOTIFY_FROM, destinatarios, msg.as_string())

        logger.info(f"[notifier] Correo enviado a: {destinatarios}")
        return True

    except Exception as e:
        logger.error(f"[notifier] Error al enviar correo: {e}")
        return False


def _texto_a_html(texto: str) -> str:
    """Convierte el resumen de texto plano a HTML básico para el correo."""
    lineas = []
    for linea in texto.split("\n"):
        linea_esc = (
            linea
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        
        if linea.startswith("="):
            lineas.append("<hr>")
        elif linea.startswith("──"):
            lineas.append(f"<h3 style='color: #00ffff;'>{linea_esc}</h3>")
        elif "NUEVO" in linea or "⚠" in linea:
            lineas.append(f"<p style='color: #ff0055; font-weight: bold;'>{linea_esc}</p>")
        elif "→" in linea:
            lineas.append(f"<p style='color: #ffff00;'>{linea_esc}</p>")
        elif linea.strip():
            lineas.append(f"<p>{linea_esc}</p>")

    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Consolas', 'Courier New', monospace; background: #0d1117; color: #00ff00; padding: 20px; }}
            h2 {{ color: #00ffff; }}
            hr {{ border: 1px solid #00ff00; }}
        </style>
    </head>
    <body>
        <h2>SAT Art. 69-B CFF — Reporte de cambios</h2>
        {''.join(lineas)}
        <hr>
        <p style="color: #8b949e; font-size: 12px;">
            Fuente: <a href="{config.SAT_PORTAL_URL}" style="color: #00ffff;">portal SAT</a> — descarga automatizada.<br>
            Este reporte es de referencia operativa; verifica siempre en la fuente oficial.
        </p>
    </body>
    </html>
    """


def enviar_correo_prueba() -> tuple[bool, str]:
    """
    Envía un correo de prueba simple para verificar que todo funciona.
    Retorna (exito, mensaje).
    """
    if not _smtp_configurado():
        return False, "SMTP no configurado. Revisa las variables de entorno."
    
    destinatarios = [d.strip() for d in config.NOTIFY_TO.split(",") if d.strip()]
    
    if not destinatarios:
        return False, "No hay destinatarios configurados."
    
    destinatarios_str = ", ".join(destinatarios)
    
    asunto = "[SAT 69-B] Correo de Prueba - EFOS Tracker"
    cuerpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #00ff00;">✅ Correo de Prueba Exitoso</h2>
        <p>Si recibiste este correo, la configuración SMTP de <strong>SAT EFOS Tracker</strong> funciona correctamente.</p>
        <hr>
        <p><strong>Configuración actual:</strong></p>
        <ul>
            <li>Servidor SMTP: {config.SMTP_HOST}:{config.SMTP_PORT}</li>
            <li>Usuario: {config.SMTP_USER}</li>
            <li>Remitente: {config.NOTIFY_FROM}</li>
            <li>Destinatarios: {destinatarios_str}</li>
        </ul>
        <hr>
        <p style="color: #888; font-size: 12px;">
            Este es un correo automático generado por SAT EFOS Tracker.<br>
            Fuente: <a href="{config.SAT_PORTAL_URL}">Portal SAT</a>
        </p>
    </body>
    </html>
    """
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = config.NOTIFY_FROM
        msg["To"] = destinatarios_str
        
        msg.attach(MIMEText("Correo de prueba de SAT EFOS Tracker", "plain", "utf-8"))
        msg.attach(MIMEText(cuerpo, "html", "utf-8"))
        
        logger.info(f"[notifier] Enviando correo de prueba a: {destinatarios}")
        
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.NOTIFY_FROM, destinatarios, msg.as_string())
        
        logger.info(f"[notifier] ✅ Correo de prueba enviado a: {destinatarios}")
        return True, f"Correo enviado a: {destinatarios_str}"
    
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"[notifier] Error de autenticación: {e}")
        return False, f"Error de autenticación SMTP: {e}"
    
    except smtplib.SMTPException as e:
        logger.error(f"[notifier] Error SMTP: {e}")
        return False, f"Error SMTP: {e}"
    
    except Exception as e:
        logger.error(f"[notifier] Error inesperado: {e}")
        return False, f"Error inesperado: {e}"