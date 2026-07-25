"""
tui.py — Interfaz de Terminal COMPLETA para sat-efos-tracker
Con log central, BD visualizable, .env persistente y comandos funcionales
"""
from textual.app import App, ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, DataTable, Static, RichLog, Input, Button, Label
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual import on
import subprocess
import threading
import queue
import logging
from pathlib import Path
from datetime import datetime

from core.watchlist import listar_watchlist, verificar_alertas_watchlist, agregar_rfc
from core.checker import consultar_rfc, consultar_desde_csv
from core.scheduler import ejecutar_ciclo
from core import config


class QueueLogHandler(logging.Handler):
    """Handler para redirigir logs a la TUI."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        self.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class DatabaseScreen(Screen):
    """Pantalla para visualizar la base de datos SQLite."""
    
    CSS = """
    DatabaseScreen {
        background: #0d1117;
        color: #00ff00;
    }
    
    .view-title {
        text-style: bold;
        color: #00ffff;
        margin-bottom: 1;
    }
    
    #db-container {
        height: 1fr;
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
        border: tall #00ff00;
    }
    
    DataTable > .datatable--cursor {
        background: #00ff00;
        color: #0d1117;
    }
    
    Button {
        background: #161b22;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 1 1 0;
    }
    
    Button:hover {
        background: #00ff00;
        color: #0d1117;
    }
    """
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("q", "app.quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("🗄️ BASE DE DATOS SQLite", classes="view-title")
        
        with Vertical(id="db-container"):
            yield Static("Selecciona una tabla para visualizar:", classes="view-title")
            
            with Horizontal():
                yield Button("📋 watchlist", id="btn-show-watchlist")
                yield Button("📊 sat_snapshots", id="btn-show-snapshots")
                yield Button("📄 sat_registros", id="btn-show-registros")
            
            yield Static("", classes="view-title")
            yield DataTable(id="db-table")

    def on_mount(self) -> None:
        table = self.query_one("#db-table", DataTable)
        table.add_columns("Columna 1", "Columna 2", "Columna 3", "Columna 4")

    def show_table(self, table_name: str):
        try:
            from database import get_connection
        except ImportError:
            self.app.log_queue.put("[ERROR] No se encontró database.py")
            return
        
        table_widget = self.query_one("#db-table", DataTable)
        table_widget.clear(columns=True)
        
        try:
            conn = get_connection()
            cursor = conn.execute(f"SELECT * FROM {table_name} LIMIT 100")
            rows = cursor.fetchall()
            
            if not rows:
                table_widget.add_columns("Mensaje")
                table_widget.add_row("No hay datos en esta tabla")
                self.app.log_queue.put(f"[WARNING] La tabla {table_name} está vacía")
                conn.close()
                return
            
            columns = [description[0] for description in cursor.description]
            table_widget.add_columns(*columns[:4])
            
            for row in rows:
                table_widget.add_row(*[str(val)[:30] for val in row[:4]])
            
            self.app.log_queue.put(f"[INFO] Mostrando {len(rows)} registros de {table_name}")
            conn.close()
        except Exception as e:
            self.app.log_queue.put(f"[ERROR] Error consultando {table_name}: {e}")

    @on(Button.Pressed, "#btn-show-watchlist")
    def on_btn_show_watchlist(self):
        self.show_table("watchlist")

    @on(Button.Pressed, "#btn-show-snapshots")
    def on_btn_show_snapshots(self):
        self.show_table("sat_snapshots")

    @on(Button.Pressed, "#btn-show-registros")
    def on_btn_show_registros(self):
        self.show_table("sat_registros")


class WatchlistScreen(Screen):
    """Pantalla para ver y gestionar la Watchlist."""
    
    CSS = """
    WatchlistScreen {
        background: #0d1117;
        color: #00ff00;
    }
    
    .view-title {
        text-style: bold;
        color: #00ffff;
        margin-bottom: 1;
    }
    
    #watchlist-container {
        height: 1fr;
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
        border: tall #00ff00;
    }
    
    DataTable > .datatable--cursor {
        background: #00ff00;
        color: #0d1117;
    }
    
    Input {
        background: #0d1117;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 0;
    }
    
    Button {
        background: #161b22;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 1 1 0;
    }
    
    Button:hover {
        background: #00ff00;
        color: #0d1117;
    }
    """
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("q", "app.quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("⚡ WATCHLIST - RFCs MONITOREADOS", classes="view-title")
        
        with Vertical(id="watchlist-container"):
            yield Static("Agregar nuevo RFC:", classes="view-title")
            with Horizontal():
                yield Input(placeholder="RFC (ej: AAA010101AAA)", id="new-rfc-input")
                yield Input(placeholder="Alias (opcional)", id="new-alias-input")
                yield Button("➕ Agregar", id="btn-add-rfc")
            
            yield Static("", classes="view-title")
            yield Static("Lista de RFCs monitoreados:", classes="view-title")
            yield DataTable(id="watchlist-table")

    def on_mount(self) -> None:
        table = self.query_one("#watchlist-table", DataTable)
        table.add_columns("RFC", "Alias", "Categoría", "Fecha Agregado", "Estado SAT")
        self.load_watchlist()

    def load_watchlist(self):
        table = self.query_one("#watchlist-table", DataTable)
        table.clear()
        
        watchlist = listar_watchlist()
        alertas_rfcs = {a["rfc"] for a in verificar_alertas_watchlist()}
        
        for item in watchlist:
            rfc = item["rfc"]
            estado = "[red]⚠️ LISTA[/]" if rfc in alertas_rfcs else "[green]✅ LIMPIO[/]"
            fecha = item.get("fecha_agregado", "N/A")[:10] if item.get("fecha_agregado") else "N/A"
            table.add_row(
                rfc,
                item.get("alias", ""),
                item.get("categoria", "Proveedor"),
                fecha,
                estado,
                key=rfc
            )

    @on(Button.Pressed, "#btn-add-rfc")
    def on_btn_add_rfc(self):
        rfc_input = self.query_one("#new-rfc-input", Input)
        alias_input = self.query_one("#new-alias-input", Input)
        
        rfc = rfc_input.value.strip()
        alias = alias_input.value.strip()
        
        if not rfc:
            self.app.log_queue.put("[WARNING] Ingresa un RFC para agregar.")
            return
        
        if agregar_rfc(rfc, alias=alias):
            self.app.log_queue.put(f"[INFO] ✅ RFC {rfc} agregado a la watchlist.")
            rfc_input.value = ""
            alias_input.value = ""
            self.load_watchlist()
        else:
            self.app.log_queue.put(f"[ERROR] ❌ No se pudo agregar {rfc} (inválido o ya existe).")


class EstadoScreen(Screen):
    """Pantalla de Estado y Ejecución."""
    
    CSS = """
    EstadoScreen {
        background: #0d1117;
        color: #00ff00;
    }
    
    .view-title {
        text-style: bold;
        color: #00ffff;
        margin-bottom: 1;
    }
    
    #status-container {
        height: 1fr;
        padding: 1;
    }
    
    Button {
        background: #161b22;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 0;
        width: 100%;
    }
    
    Button:hover {
        background: #00ff00;
        color: #0d1117;
    }
    """
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("q", "app.quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("🔄 ESTADO Y EJECUCIÓN", classes="view-title")
        
        with Vertical(id="status-container"):
            yield Button("▶️ Ejecutar Ciclo Ahora", id="btn-run-cycle", variant="primary")
            yield Static("", classes="view-title")
            
            latest_path = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
            if latest_path.exists():
                mtime = datetime.fromtimestamp(latest_path.stat().st_mtime)
                size_kb = latest_path.stat().st_size / 1024
                status_text = f"✅ Último listado: {mtime:%Y-%m-%d %H:%M} ({size_kb:.1f} KB)"
            else:
                status_text = "⚠️ Sin datos. Ejecuta un ciclo primero."
            
            yield Static(status_text, id="system-status")
            yield Static("", classes="view-title")
            
            alertas = verificar_alertas_watchlist()
            if alertas:
                yield Static(f"[red]⚠️ ALERTA: {len(alertas)} proveedores en lista negra[/]")
            else:
                yield Static("[green]✅ Todos los proveedores monitoreados están limpios[/]")

    @on(Button.Pressed, "#btn-run-cycle")
    def on_btn_run_cycle(self):
        app = self.app
        if app.is_running_cycle:
            app.log_queue.put("[WARNING] Ya hay un ciclo en ejecución.")
            return
        
        app.is_running_cycle = True
        app.log_queue.put("[INFO] Iniciando ciclo de descarga y procesamiento...")
        
        def worker():
            try:
                ejecutar_ciclo()
                app.log_queue.put("[INFO] ✅ Ciclo completado exitosamente.")
            except Exception as e:
                app.log_queue.put(f"[ERROR] 💥 Error en ciclo: {e}")
            finally:
                app.is_running_cycle = False
        
        threading.Thread(target=worker, daemon=True).start()


class ConsultaScreen(Screen):
    """Pantalla de Consulta RFCs."""
    
    CSS = """
    ConsultaScreen {
        background: #0d1117;
        color: #00ff00;
    }
    
    .view-title {
        text-style: bold;
        color: #00ffff;
        margin-bottom: 1;
    }
    
    #consulta-container {
        height: 1fr;
        padding: 1;
    }
    
    Input {
        background: #0d1117;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 0;
    }
    
    Button {
        background: #161b22;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 0;
    }
    
    Button:hover {
        background: #00ff00;
        color: #0d1117;
    }
    
    DataTable {
        height: 1fr;
        border: tall #00ff00;
        margin-top: 1;
    }
    
    DataTable > .datatable--cursor {
        background: #00ff00;
        color: #0d1117;
    }
    """
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("q", "app.quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("🔍 CONSULTA DE RFCs", classes="view-title")
        
        with Vertical(id="consulta-container"):
            yield Static("Consulta Individual:", classes="view-title")
            
            with Horizontal():
                yield Input(placeholder="RFC (ej: AAA010101AAA)", id="rfc-input")
                yield Button("Consultar", id="btn-check-rfc")
            
            yield Static("", classes="view-title")
            yield Static("Resultados:", classes="view-title")
            yield DataTable(id="results-table")

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Campo", "Valor")

    @on(Button.Pressed, "#btn-check-rfc")
    def on_btn_check_rfc(self):
        rfc_input = self.query_one("#rfc-input", Input)
        rfc = rfc_input.value.strip()
        if not rfc:
            self.app.log_queue.put("[WARNING] Ingresa un RFC para consultar.")
            return
        
        self.app.log_queue.put(f"[INFO] Consultando RFC: {rfc}")
        res = consultar_rfc(rfc)
        
        table = self.query_one("#results-table", DataTable)
        table.clear()
        
        if res["encontrado"]:
            table.add_row("Estado", "⚠️ EN LISTA")
            table.add_row("RFC", res["rfc"])
            table.add_row("Situación", res["situacion"].upper())
            table.add_row("Nombre", res["nombre"])
            table.add_row("Publicado", res["fecha_primera_publicacion"])
            table.add_row("Oficio", res["numero_oficio"])
        else:
            table.add_row("Estado", "✅ LIMPIO")
            table.add_row("RFC", res["rfc"])
            table.add_row("Nota", "No encontrado en listado 69-B")

    @on(Input.Submitted, "#rfc-input")
    def on_rfc_submitted(self, event: Input.Submitted):
        self.on_btn_check_rfc()


class ConfigScreen(Screen):
    """Pantalla de Configuración SMTP."""
    
    CSS = """
    ConfigScreen {
        background: #0d1117;
        color: #00ff00;
    }
    
    .view-title {
        text-style: bold;
        color: #00ffff;
        margin-bottom: 1;
    }
    
    #config-container {
        height: 1fr;
        padding: 1;
    }
    
    Input {
        background: #0d1117;
        color: #00ff00;
        border: tall #00ff00;
        margin: 0 0 1 0;
    }
    
    Button {
        background: #161b22;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 1 1 0;
    }
    
    Button:hover {
        background: #00ff00;
        color: #0d1117;
    }
    """
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("q", "app.quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("📧 CONFIGURACIÓN SMTP", classes="view-title")
        
        with Vertical(id="config-container"):
            yield Static("Servidor SMTP:")
            yield Input(value=config.SMTP_HOST, id="smtp-host")
            
            yield Static("Puerto:")
            yield Input(value=str(config.SMTP_PORT), id="smtp-port")
            
            yield Static("Usuario:")
            yield Input(value=config.SMTP_USER, id="smtp-user")
            
            yield Static("Contraseña:")
            yield Input(value=config.SMTP_PASSWORD, password=True, id="smtp-pass")
            
            yield Static("Remitente:")
            yield Input(value=config.NOTIFY_FROM, id="notify-from")
            
            yield Static("Destinatarios (separados por coma):")
            yield Input(value=config.NOTIFY_TO, id="notify-to")
            
            yield Static("", classes="view-title")
            with Horizontal():
                yield Button("💾 Guardar en .env", id="btn-save-env")
                yield Button("📂 Cargar .env", id="btn-load-env")
                yield Button("📧 Enviar Prueba", id="btn-test-email")

    @on(Button.Pressed, "#btn-save-env")
    def on_btn_save_env(self):
        env_path = Path(".env")
        env_content = f"""# Configuración generada por TUI
EFOS_SMTP_HOST={self.query_one('#smtp-host', Input).value}
EFOS_SMTP_PORT={self.query_one('#smtp-port', Input).value}
EFOS_SMTP_USER={self.query_one('#smtp-user', Input).value}
EFOS_SMTP_PASS={self.query_one('#smtp-pass', Input).value}
EFOS_NOTIFY_FROM={self.query_one('#notify-from', Input).value}
EFOS_NOTIFY_TO={self.query_one('#notify-to', Input).value}
EFOS_NOTIFY_ON_NEW=true
"""
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            self.app.log_queue.put(f"[INFO] ✅ Configuración guardada en: {env_path.absolute()}")
        except Exception as e:
            self.app.log_queue.put(f"[ERROR] Error guardando .env: {e}")

    @on(Button.Pressed, "#btn-load-env")
    def on_btn_load_env(self):
        env_path = Path(".env")
        if not env_path.exists():
            self.app.log_queue.put("[WARNING] No existe archivo .env")
            return
        
        try:
            with open(env_path, 'r', encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == "EFOS_SMTP_HOST":
                            self.query_one('#smtp-host', Input).value = value
                        elif key == "EFOS_SMTP_PORT":
                            self.query_one('#smtp-port', Input).value = value
                        elif key == "EFOS_SMTP_USER":
                            self.query_one('#smtp-user', Input).value = value
                        elif key == "EFOS_SMTP_PASS":
                            self.query_one('#smtp-pass', Input).value = value
                        elif key == "EFOS_NOTIFY_FROM":
                            self.query_one('#notify-from', Input).value = value
                        elif key == "EFOS_NOTIFY_TO":
                            self.query_one('#notify-to', Input).value = value
            
            self.app.log_queue.put(f"[INFO] ✅ Configuración cargada desde: {env_path.absolute()}")
        except Exception as e:
            self.app.log_queue.put(f"[ERROR] Error cargando .env: {e}")

    @on(Button.Pressed, "#btn-test-email")
    def on_btn_test_email(self):
        from notifier import enviar_reporte
        
        config.SMTP_HOST = self.query_one('#smtp-host', Input).value
        config.SMTP_PORT = int(self.query_one('#smtp-port', Input).value)
        config.SMTP_USER = self.query_one('#smtp-user', Input).value
        config.SMTP_PASSWORD = self.query_one('#smtp-pass', Input).value
        config.NOTIFY_FROM = self.query_one('#notify-from', Input).value
        config.NOTIFY_TO = self.query_one('#notify-to', Input).value
        
        diff_prueba = {
            "nuevos": [{"rfc": "TEST010101TEST", "situacion": "presunto", "nombre": "PRUEBA"}],
            "cambios": [],
            "bajas": []
        }
        
        self.app.log_queue.put("[INFO] Enviando correo de prueba...")
        
        def worker():
            success = enviar_reporte(diff_prueba)
            if success:
                self.app.log_queue.put("[INFO] ✅ Correo de prueba enviado.")
            else:
                self.app.log_queue.put("[ERROR] ❌ Falló el envío.")
        
        threading.Thread(target=worker, daemon=True).start()


class DaemonScreen(Screen):
    """Pantalla de gestión del Daemon Windows."""
    
    CSS = """
    DaemonScreen {
        background: #0d1117;
        color: #00ff00;
    }
    
    .view-title {
        text-style: bold;
        color: #00ffff;
        margin-bottom: 1;
    }
    
    #daemon-container {
        height: 1fr;
        padding: 1;
    }
    
    Button {
        background: #161b22;
        color: #00ff00;
        border: tall #00ff00;
        margin: 1 1 1 0;
    }
    
    Button:hover {
        background: #00ff00;
        color: #0d1117;
    }
    """
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("q", "app.quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("🔌 DAEMON WINDOWS (Task Scheduler)", classes="view-title")
        
        with Vertical(id="daemon-container"):
            yield Static(
                "El daemon ejecuta el monitoreo en segundo plano al iniciar sesión.\n"
                "Requiere permisos de Administrador.",
                classes="view-title"
            )
            
            yield Static("", classes="view-title")
            with Horizontal():
                yield Button("🔌 Instalar Daemon", id="btn-install-daemon")
                yield Button("▶️ Ejecutar Ahora", id="btn-run-daemon")
                yield Button("🗑️ Eliminar Daemon", id="btn-delete-daemon")
            
            yield Static("", classes="view-title")
            yield Static("Estado:", classes="view-title")
            
            try:
                result = subprocess.run(
                    ['schtasks', '/Query', '/TN', 'SatEfosTracker_Daemon'],
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    yield Static("[green]✅ Daemon instalado y activo[/]", id="daemon-status")
                else:
                    yield Static("[red]❌ Daemon no instalado[/]", id="daemon-status")
            except Exception as e:
                yield Static(f"[yellow]⚠️ Error verificando: {e}[/]", id="daemon-status")

    @on(Button.Pressed, "#btn-install-daemon")
    def on_btn_install_daemon(self):
        script_path = Path("scheduler.py").resolve()
        cmd = f'schtasks /Create /TN "SatEfosTracker_Daemon" /TR "pyw.exe {script_path}" /SC ONLOGON /RL HIGHEST /F'
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                self.app.log_queue.put("[INFO] ✅ Daemon instalado correctamente.")
            else:
                self.app.log_queue.put(f"[ERROR] Error: {result.stderr}")
        except Exception as e:
            self.app.log_queue.put(f"[ERROR] Error: {e}")

    @on(Button.Pressed, "#btn-run-daemon")
    def on_btn_run_daemon(self):
        cmd = 'schtasks /Run /TN "SatEfosTracker_Daemon"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                self.app.log_queue.put("[INFO] ✅ Daemon ejecutándose.")
            else:
                self.app.log_queue.put(f"[ERROR] Error: {result.stderr}")
        except Exception as e:
            self.app.log_queue.put(f"[ERROR] Error: {e}")

    @on(Button.Pressed, "#btn-delete-daemon")
    def on_btn_delete_daemon(self):
        cmd = 'schtasks /Delete /TN "SatEfosTracker_Daemon" /F'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                self.app.log_queue.put("[INFO] ✅ Daemon eliminado.")
            else:
                self.app.log_queue.put(f"[ERROR] Error: {result.stderr}")
        except Exception as e:
            self.app.log_queue.put(f"[ERROR] Error: {e}")


class MenuScreen(Screen):
    """Pantalla del menú principal con log central."""
    
    CSS = """
    MenuScreen {
        background: #0d1117;
        color: #00ff00;
    }
    
    #menu-container {
        height: 1fr;
        padding: 1;
    }
    
    .menu-button {
        width: 100%;
        margin-bottom: 1;
        background: #161b22;
        color: #00ff00;
        border: tall #00ff00;
        height: 3;
    }
    
    .menu-button:hover {
        background: #00ff00;
        color: #0d1117;
    }
    
    .view-title {
        text-style: bold;
        color: #00ffff;
        margin-bottom: 1;
    }
    
    #radar-count {
        text-style: bold;
        color: #ffff00;
        margin-top: 1;
    }
    
    #log-panel {
        height: 15;
        border: tall #ffff00;
        background: #000000;
        color: #ffff00;
        padding: 1;
    }
    
    #command-bar {
        dock: bottom;
        height: 3;
        background: #161b22;
        border: tall #00ff00;
        padding: 0 1;
    }
    
    #command-input {
        width: 1fr;
        background: #0d1117;
        color: #00ff00;
    }
    """
    
    BINDINGS = [
        Binding("q", "app.quit", "Salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal():
            with Vertical(id="menu-container"):
                yield Static("⚡ MENÚ PRINCIPAL", classes="view-title")
                
                yield Button("🔄 Estado / Ejecución", id="btn-estado", classes="menu-button")
                yield Button("🔍 Consultar RFCs", id="btn-consulta", classes="menu-button")
                yield Button("⚡ Watchlist (Radar)", id="btn-watchlist", classes="menu-button")
                yield Button("📧 Configuración SMTP", id="btn-config", classes="menu-button")
                yield Button("🔌 Daemon Windows", id="btn-daemon", classes="menu-button")
                yield Button("🗄️ Ver Base de Datos", id="btn-database", classes="menu-button")
                
                yield Static("", classes="view-title")
                yield Static(f"RFCs en Radar: {len(listar_watchlist())}", id="radar-count")
            
            with Vertical():
                yield Static("📋 LOG CENTRAL", classes="view-title")
                yield RichLog(id="log-panel", highlight=True, markup=True)
        
        with Horizontal(id="command-bar"):
            yield Static("> ", classes="view-title")
            yield Input(placeholder="Escribe un comando (ej: help, check RFC123, run)", id="command-input")
        
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.1, self.poll_logs)
        self.set_interval(2, self.update_radar_count)
        
        log = self.query_one("#log-panel", RichLog)
        log.write("[bold green]Sistema iniciado.[/] Escribe 'help' para ver comandos.")
        
        # Enfocar el input de comandos automáticamente
        self.query_one("#command-input", Input).focus()

    def poll_logs(self):
        log = self.query_one("#log-panel", RichLog)
        app = self.app
        while True:
            try:
                msg = app.log_queue.get_nowait()
                if "[ERROR]" in msg or "💥" in msg:
                    log.write(f"[red]{msg}[/]")
                elif "[WARNING]" in msg or "⚠️" in msg:
                    log.write(f"[yellow]{msg}[/]")
                elif "[INFO]" in msg:
                    log.write(f"[green]{msg}[/]")
                else:
                    log.write(msg)
            except queue.Empty:
                break

    def update_radar_count(self):
        count_widget = self.query_one("#radar-count", Static)
        count = len(listar_watchlist())
        count_widget.update(f"RFCs en Radar: {count}")

    @on(Button.Pressed, "#btn-estado")
    def on_btn_estado(self):
        self.app.push_screen(EstadoScreen())

    @on(Button.Pressed, "#btn-consulta")
    def on_btn_consulta(self):
        self.app.push_screen(ConsultaScreen())

    @on(Button.Pressed, "#btn-watchlist")
    def on_btn_watchlist(self):
        self.app.push_screen(WatchlistScreen())

    @on(Button.Pressed, "#btn-config")
    def on_btn_config(self):
        self.app.push_screen(ConfigScreen())

    @on(Button.Pressed, "#btn-daemon")
    def on_btn_daemon(self):
        self.app.push_screen(DaemonScreen())

    @on(Button.Pressed, "#btn-database")
    def on_btn_database(self):
        self.app.push_screen(DatabaseScreen())

    @on(Input.Submitted, "#command-input")
    def on_command_submitted(self, event: Input.Submitted):
        cmd = event.value.strip().lower()
        input_widget = self.query_one("#command-input", Input)
        input_widget.value = ""
        
        app = self.app
        
        if cmd == "help":
            app.log_queue.put("[cyan]Comandos disponibles:[/]")
            app.log_queue.put("  check RFC123  - Consultar RFC")
            app.log_queue.put("  run           - Ejecutar ciclo")
            app.log_queue.put("  status        - Ver estado")
            app.log_queue.put("  watchlist     - Ver RFCs en radar")
            app.log_queue.put("  alertas       - Ver alertas críticas")
        
        elif cmd.startswith("check "):
            rfc = cmd.split()[1].upper()
            res = consultar_rfc(rfc)
            if res["encontrado"]:
                app.log_queue.put(f"[red]⚠️ {rfc} EN LISTA: {res['situacion'].upper()}[/]")
            else:
                app.log_queue.put(f"[green]✅ {rfc} LIMPIO[/]")
        
        elif cmd == "run":
            if not app.is_running_cycle:
                threading.Thread(target=ejecutar_ciclo, daemon=True).start()
                app.log_queue.put("[cyan]Ciclo iniciado...[/]")
            else:
                app.log_queue.put("[yellow]Ya hay un ciclo en ejecución.[/]")
        
        elif cmd == "status":
            self.app.push_screen(EstadoScreen())
        
        elif cmd == "watchlist":
            self.app.push_screen(WatchlistScreen())
        
        elif cmd == "alertas":
            alertas = verificar_alertas_watchlist()
            if alertas:
                app.log_queue.put(f"[red]⚠️ ALERTAS: {len(alertas)}[/]")
                for a in alertas:
                    app.log_queue.put(f"  {a['rfc']} - {a['situacion']}")
            else:
                app.log_queue.put("[green]✅ Sin alertas[/]")
        
        else:
            app.log_queue.put(f"[yellow]Comando no reconocido: {cmd}. Escribe 'help'.[/]")


class EfosTrackerTUI(App):
    """Aplicación TUI principal."""
    CSS_PATH = None
    TITLE = "SAT EFOS Tracker // RADAR 69-B"
    
    def __init__(self):
        super().__init__()
        self.log_queue = queue.Queue()
        self.is_running_cycle = False
        
        self.queue_handler = QueueLogHandler(self.log_queue)
        root_logger = logging.getLogger()
        root_logger.addHandler(self.queue_handler)
        root_logger.setLevel(logging.INFO)

    def on_mount(self) -> None:
        self.push_screen(MenuScreen())
        self.log_queue.put("[INFO] Sistema iniciado. Escribe comandos abajo.")


if __name__ == "__main__":
    app = EfosTrackerTUI()
    app.run()