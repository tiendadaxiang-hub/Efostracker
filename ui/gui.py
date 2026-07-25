"""
gui.py — Interfaz Gráfica Cyberpunk para sat-efos-tracker
Usa CustomTkinter para tema oscuro moderno con estética hacker
"""
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import logging
from pathlib import Path
from datetime import datetime
import subprocess
import sys

# Importar módulos del proyecto
from core.watchlist import listar_watchlist, verificar_alertas_watchlist, agregar_rfc, eliminar_rfc
from core.checker import consultar_rfc, consultar_desde_csv
from core.scheduler import ejecutar_ciclo
from core.database import get_connection
from core import config

# Configuración de tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Colores cyberpunk
COLORS = {
    "bg_dark": "#0d1117",
    "bg_medium": "#161b22",
    "bg_light": "#21262d",
    "green_neon": "#00ff00",
    "cyan_neon": "#00ffff",
    "magenta_neon": "#ff00ff",
    "yellow_neon": "#ffff00",
    "red_neon": "#ff0055",
    "text_primary": "#c9d1d9",
    "text_secondary": "#8b949e",
}


class QueueLogHandler(logging.Handler):
    """Handler para redirigir logs a la GUI con colores."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        self.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put((record.levelname, msg))


class CyberpunkGUI(ctk.CTk):
    """Aplicación GUI principal con estética cyberpunk."""
    
    def __init__(self):
        super().__init__()
        
        # Configuración de ventana
        self.title("SAT EFOS Tracker // RADAR 69-B")
        self.geometry("1400x900")
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Variables de estado
        self.log_queue = queue.Queue()
        self.is_running_cycle = False
        self.current_view = "estado"
        
        # Configurar logging
        self._setup_logging()
        
        # Construir UI
        self._build_ui()
        
        # Iniciar pollers
        self._poll_logs()
        self._update_radar_count()
        
        # Log inicial
        self._add_log("INFO", "Sistema iniciado. GUI Cyberpunk activa.")
    
    def _setup_logging(self):
        """Configura el handler de logs para la GUI."""
        self.queue_handler = QueueLogHandler(self.log_queue)
        root_logger = logging.getLogger()
        root_logger.addHandler(self.queue_handler)
        root_logger.setLevel(logging.INFO)
    
    def _build_ui(self):
        """Construye la interfaz completa."""
        # Grid principal
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Sidebar izquierdo
        self._build_sidebar()
        
        # Área central
        self._build_central_area()
        
        # Panel inferior (logs + comandos)
        self._build_bottom_panel()
    
    def _build_sidebar(self):
        """Sidebar con menú de navegación."""
        sidebar = ctk.CTkFrame(
            self,
            width=250,
            fg_color=COLORS["bg_medium"],
            corner_radius=0
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        
        # Título
        title_label = ctk.CTkLabel(
            sidebar,
            text="⚡ EFOS TRACKER",
            font=("Consolas", 20, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        title_label.pack(pady=20, padx=20)
        
        # Subtítulo
        subtitle = ctk.CTkLabel(
            sidebar,
            text="RADAR 69-B // SAT",
            font=("Consolas", 12),
            text_color=COLORS["text_secondary"]
        )
        subtitle.pack(pady=(0, 30))
        
        # Botones de navegación
        nav_buttons = [
            ("🔄 Estado / Ejecución", "estado"),
            ("🔍 Consultar RFCs", "consulta"),
            ("⚡ Watchlist (Radar)", "watchlist"),
            ("📧 Configuración SMTP", "config"),
            ("🔌 Daemon Windows", "daemon"),
            ("🗄️ Base de Datos", "database"),
        ]
        
        for text, view in nav_buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                font=("Consolas", 14),
                fg_color=COLORS["bg_light"],
                hover_color=COLORS["green_neon"],
                text_color=COLORS["green_neon"],
                height=40,
                corner_radius=8,
                command=lambda v=view: self._switch_view(v)
            )
            btn.pack(pady=5, padx=20, fill="x")
        
        # Contador de radar
        self.radar_count_label = ctk.CTkLabel(
            sidebar,
            text=f"RFCs en Radar: {len(listar_watchlist())}",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["yellow_neon"]
        )
        self.radar_count_label.pack(pady=30)
    
    def _build_central_area(self):
        """Área central que cambia según la vista seleccionada."""
        self.central_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_dark"],
            corner_radius=0
        )
        self.central_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Mostrar vista por defecto
        self._switch_view("estado")
    
    def _build_bottom_panel(self):
        """Panel inferior con logs y barra de comandos."""
        bottom = ctk.CTkFrame(
            self,
            height=200,
            fg_color=COLORS["bg_medium"],
            corner_radius=0
        )
        bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 10))
        bottom.grid_propagate(False)
        
        # Logs
        log_label = ctk.CTkLabel(
            bottom,
            text="📋 LOG CENTRAL",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["yellow_neon"]
        )
        log_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        self.log_text = scrolledtext.ScrolledText(
            bottom,
            wrap="word",
            font=("Consolas", 10),
            bg=COLORS["bg_dark"],
            fg=COLORS["green_neon"],
            insertbackground=COLORS["green_neon"],
            height=8
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Configurar tags para colores
        self.log_text.tag_config("INFO", foreground=COLORS["green_neon"])
        self.log_text.tag_config("WARNING", foreground=COLORS["yellow_neon"])
        self.log_text.tag_config("ERROR", foreground=COLORS["red_neon"])
        self.log_text.tag_config("DEBUG", foreground=COLORS["text_secondary"])
        
        # Barra de comandos
        cmd_frame = ctk.CTkFrame(bottom, fg_color=COLORS["bg_light"], height=40)
        cmd_frame.pack(fill="x", padx=10, pady=(0, 10))
        cmd_frame.pack_propagate(False)
        
        cmd_label = ctk.CTkLabel(
            cmd_frame,
            text=">",
            font=("Consolas", 14, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        cmd_label.pack(side="left", padx=10)
        
        self.cmd_entry = ctk.CTkEntry(
            cmd_frame,
            placeholder_text="Escribe un comando (ej: help, check RFC123, run)",
            font=("Consolas", 12),
            fg_color=COLORS["bg_dark"],
            text_color=COLORS["green_neon"],
            height=30
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.cmd_entry.bind("<Return>", self._execute_command)
    
    def _switch_view(self, view_name: str):
        """Cambia la vista central."""
        # Limpiar área central
        for widget in self.central_frame.winfo_children():
            widget.destroy()
        
        self.current_view = view_name
        
        # Construir vista según selección
        if view_name == "estado":
            self._build_estado_view()
        elif view_name == "consulta":
            self._build_consulta_view()
        elif view_name == "watchlist":
            self._build_watchlist_view()
        elif view_name == "config":
            self._build_config_view()
        elif view_name == "daemon":
            self._build_daemon_view()
        elif view_name == "database":
            self._build_database_view()
    
    def _build_estado_view(self):
        """Vista de Estado y Ejecución."""
        title = ctk.CTkLabel(
            self.central_frame,
            text="🔄 ESTADO Y EJECUCIÓN",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        title.pack(pady=20)
        
        # Botón ejecutar ciclo
        run_btn = ctk.CTkButton(
            self.central_frame,
            text="▶️ Ejecutar Ciclo Ahora",
            font=("Consolas", 14, "bold"),
            fg_color=COLORS["green_neon"],
            hover_color=COLORS["cyan_neon"],
            text_color=COLORS["bg_dark"],
            height=50,
            width=300,
            command=self._run_cycle
        )
        run_btn.pack(pady=20)
        
        # Estado del sistema
        latest_path = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
        if latest_path.exists():
            mtime = datetime.fromtimestamp(latest_path.stat().st_mtime)
            size_kb = latest_path.stat().st_size / 1024
            status_text = f"✅ Último listado: {mtime:%Y-%m-%d %H:%M} ({size_kb:.1f} KB)"
            status_color = COLORS["green_neon"]
        else:
            status_text = "⚠️ Sin datos. Ejecuta un ciclo primero."
            status_color = COLORS["yellow_neon"]
        
        status_label = ctk.CTkLabel(
            self.central_frame,
            text=status_text,
            font=("Consolas", 12),
            text_color=status_color
        )
        status_label.pack(pady=10)
        
        # Alertas de watchlist
        alertas = verificar_alertas_watchlist()
        if alertas:
            alert_label = ctk.CTkLabel(
                self.central_frame,
                text=f"⚠️ ALERTA: {len(alertas)} proveedores en lista negra",
                font=("Consolas", 12, "bold"),
                text_color=COLORS["red_neon"]
            )
            alert_label.pack(pady=10)
        else:
            clean_label = ctk.CTkLabel(
                self.central_frame,
                text="✅ Todos los proveedores monitoreados están limpios",
                font=("Consolas", 12),
                text_color=COLORS["green_neon"]
            )
            clean_label.pack(pady=10)
    
    def _build_consulta_view(self):
        """Vista de Consulta RFCs."""
        title = ctk.CTkLabel(
            self.central_frame,
            text="🔍 CONSULTA DE RFCs",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        title.pack(pady=20)
        
        # Consulta individual
        frame_individual = ctk.CTkFrame(self.central_frame, fg_color=COLORS["bg_medium"])
        frame_individual.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(
            frame_individual,
            text="Consulta Individual:",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=10, pady=10)
        
        input_frame = ctk.CTkFrame(frame_individual, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=10)
        
        self.rfc_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="RFC (ej: AAA010101AAA)",
            font=("Consolas", 12),
            width=300
        )
        self.rfc_entry.pack(side="left", padx=(0, 10))
        self.rfc_entry.bind("<Return>", lambda e: self._check_rfc())
        
        check_btn = ctk.CTkButton(
            input_frame,
            text="Consultar",
            font=("Consolas", 12),
            command=self._check_rfc
        )
        check_btn.pack(side="left")
        
        # Resultados
        ctk.CTkLabel(
            self.central_frame,
            text="Resultados:",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=20, pady=(20, 5))
        
        self.results_text = scrolledtext.ScrolledText(
            self.central_frame,
            wrap="word",
            font=("Consolas", 10),
            bg=COLORS["bg_dark"],
            fg=COLORS["green_neon"],
            height=15
        )
        self.results_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    def _build_watchlist_view(self):
        """Vista de Watchlist."""
        title = ctk.CTkLabel(
            self.central_frame,
            text="⚡ WATCHLIST - RFCs MONITOREADOS",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        title.pack(pady=20)
        
        # Agregar nuevo RFC
        add_frame = ctk.CTkFrame(self.central_frame, fg_color=COLORS["bg_medium"])
        add_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(
            add_frame,
            text="Agregar nuevo RFC:",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=10, pady=10)
        
        input_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=10)
        
        self.new_rfc_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="RFC",
            font=("Consolas", 12),
            width=200
        )
        self.new_rfc_entry.pack(side="left", padx=(0, 10))
        
        self.new_alias_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Alias (opcional)",
            font=("Consolas", 12),
            width=200
        )
        self.new_alias_entry.pack(side="left", padx=(0, 10))
        
        add_btn = ctk.CTkButton(
            input_frame,
            text="➕ Agregar",
            font=("Consolas", 12),
            command=self._add_to_watchlist
        )
        add_btn.pack(side="left")
        
        # Tabla de watchlist
        ctk.CTkLabel(
            self.central_frame,
            text="Lista de RFCs monitoreados:",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=20, pady=(20, 5))
        
        # Crear Treeview para la tabla
        table_frame = ctk.CTkFrame(self.central_frame, fg_color=COLORS["bg_medium"])
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        columns = ("RFC", "Alias", "Categoría", "Fecha", "Estado")
        self.watchlist_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=15
        )
        
        for col in columns:
            self.watchlist_tree.heading(col, text=col)
            self.watchlist_tree.column(col, width=150)
        
        # Estilo para Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=COLORS["bg_dark"],
            foreground=COLORS["green_neon"],
            fieldbackground=COLORS["bg_dark"],
            font=("Consolas", 10)
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["bg_medium"],
            foreground=COLORS["cyan_neon"],
            font=("Consolas", 11, "bold")
        )
        
        self.watchlist_tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Cargar datos
        self._load_watchlist()
    
    def _build_config_view(self):
        """Vista de Configuración SMTP."""
        title = ctk.CTkLabel(
            self.central_frame,
            text="📧 CONFIGURACIÓN SMTP",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        title.pack(pady=20)
        
        # Campos de configuración
        config_frame = ctk.CTkFrame(self.central_frame, fg_color=COLORS["bg_medium"])
        config_frame.pack(pady=10, padx=20, fill="x")
        
        fields = [
            ("Servidor SMTP:", "smtp_host", config.SMTP_HOST),
            ("Puerto:", "smtp_port", str(config.SMTP_PORT)),
            ("Usuario:", "smtp_user", config.SMTP_USER),
            ("Contraseña:", "smtp_pass", config.SMTP_PASSWORD),
            ("Remitente:", "notify_from", config.NOTIFY_FROM),
            ("Destinatarios:", "notify_to", config.NOTIFY_TO),
        ]
        
        self.config_entries = {}
        
        for i, (label_text, key, default_value) in enumerate(fields):
            ctk.CTkLabel(
                config_frame,
                text=label_text,
                font=("Consolas", 11),
                text_color=COLORS["text_primary"]
            ).grid(row=i, column=0, padx=10, pady=5, sticky="w")
            
            entry = ctk.CTkEntry(
                config_frame,
                font=("Consolas", 11),
                width=400,
                show="*" if "pass" in key else ""
            )
            entry.insert(0, default_value)
            entry.grid(row=i, column=1, padx=10, pady=5)
            
            self.config_entries[key] = entry
        
        # Botones
        btn_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="💾 Guardar en .env",
            font=("Consolas", 12),
            command=self._save_env
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="📧 Enviar Prueba",
            font=("Consolas", 12),
            command=self._test_email
        ).pack(side="left", padx=5)
    
    def _build_daemon_view(self):
        """Vista de gestión del Daemon Windows."""
        title = ctk.CTkLabel(
            self.central_frame,
            text="🔌 DAEMON WINDOWS (Task Scheduler)",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        title.pack(pady=20)
        
        info_label = ctk.CTkLabel(
            self.central_frame,
            text="El daemon ejecuta el monitoreo en segundo plano al iniciar sesión.\nRequiere permisos de Administrador.",
            font=("Consolas", 11),
            text_color=COLORS["text_secondary"],
            justify="left"
        )
        info_label.pack(pady=10)
        
        # Botones
        btn_frame = ctk.CTkFrame(self.central_frame, fg_color=COLORS["bg_medium"])
        btn_frame.pack(pady=20, padx=20)
        
        ctk.CTkButton(
            btn_frame,
            text="🔌 Instalar Daemon",
            font=("Consolas", 12),
            command=self._install_daemon
        ).pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="▶️ Ejecutar Ahora",
            font=("Consolas", 12),
            command=self._run_daemon
        ).pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="🗑️ Eliminar Daemon",
            font=("Consolas", 12),
            command=self._delete_daemon
        ).pack(side="left", padx=10, pady=10)
        
        # Estado
        try:
            result = subprocess.run(
                ['schtasks', '/Query', '/TN', 'SatEfosTracker_Daemon'],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                status_text = "✅ Daemon instalado y activo"
                status_color = COLORS["green_neon"]
            else:
                status_text = "❌ Daemon no instalado"
                status_color = COLORS["red_neon"]
        except Exception as e:
            status_text = f"⚠️ Error verificando: {e}"
            status_color = COLORS["yellow_neon"]
        
        status_label = ctk.CTkLabel(
            self.central_frame,
            text=f"Estado: {status_text}",
            font=("Consolas", 12, "bold"),
            text_color=status_color
        )
        status_label.pack(pady=20)
    
    def _build_database_view(self):
        """Vista de visualización de base de datos."""
        title = ctk.CTkLabel(
            self.central_frame,
            text="🗄️ BASE DE DATOS SQLite",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["cyan_neon"]
        )
        title.pack(pady=20)
        
        # Botones de tablas
        btn_frame = ctk.CTkFrame(self.central_frame, fg_color=COLORS["bg_medium"])
        btn_frame.pack(pady=10, padx=20)
        
        ctk.CTkButton(
            btn_frame,
            text="📋 watchlist",
            font=("Consolas", 12),
            command=lambda: self._show_db_table("watchlist")
        ).pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="📊 sat_snapshots",
            font=("Consolas", 12),
            command=lambda: self._show_db_table("sat_snapshots")
        ).pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="📄 sat_registros",
            font=("Consolas", 12),
            command=lambda: self._show_db_table("sat_registros")
        ).pack(side="left", padx=10, pady=10)
        
        # Tabla de resultados
        table_frame = ctk.CTkFrame(self.central_frame, fg_color=COLORS["bg_medium"])
        table_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.db_tree = ttk.Treeview(table_frame, show="headings", height=20)
        self.db_tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # ─── Métodos de acción ─────────────────────────────────────────────
    
    def _run_cycle(self):
        """Ejecuta un ciclo completo."""
        if self.is_running_cycle:
            self._add_log("WARNING", "Ya hay un ciclo en ejecución.")
            return
        
        self.is_running_cycle = True
        self._add_log("INFO", "Iniciando ciclo de descarga y procesamiento...")
        
        def worker():
            try:
                ejecutar_ciclo()
                self._add_log("INFO", "✅ Ciclo completado exitosamente.")
            except Exception as e:
                self._add_log("ERROR", f"💥 Error en ciclo: {e}")
            finally:
                self.is_running_cycle = False
                self.after(0, self._switch_view, "estado")
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _check_rfc(self):
        """Consulta un RFC individual."""
        rfc = self.rfc_entry.get().strip()
        if not rfc:
            self._add_log("WARNING", "Ingresa un RFC para consultar.")
            return
        
        self._add_log("INFO", f"Consultando RFC: {rfc}")
        res = consultar_rfc(rfc)
        
        self.results_text.delete("1.0", "end")
        
        if res["encontrado"]:
            self.results_text.insert("end", f"⚠️ EN LISTA NEGRA (ART. 69-B)\n\n", "ERROR")
            self.results_text.insert("end", f"RFC: {res['rfc']}\n")
            self.results_text.insert("end", f"Situación: {res['situacion'].upper()}\n")
            self.results_text.insert("end", f"Nombre: {res['nombre']}\n")
            self.results_text.insert("end", f"Publicado: {res['fecha_primera_publicacion']}\n")
            self.results_text.insert("end", f"Oficio: {res['numero_oficio']}\n")
        else:
            self.results_text.insert("end", f"✅ RFC LIMPIO\n\n", "INFO")
            self.results_text.insert("end", f"RFC: {res['rfc']}\n")
            self.results_text.insert("end", "No se encuentra en el listado actual del Art. 69-B.\n")
    
    def _add_to_watchlist(self):
        """Agrega un RFC a la watchlist."""
        rfc = self.new_rfc_entry.get().strip()
        alias = self.new_alias_entry.get().strip()
        
        if not rfc:
            self._add_log("WARNING", "Ingresa un RFC para agregar.")
            return
        
        if agregar_rfc(rfc, alias=alias):
            self._add_log("INFO", f"✅ RFC {rfc} agregado a la watchlist.")
            self.new_rfc_entry.delete(0, "end")
            self.new_alias_entry.delete(0, "end")
            self._load_watchlist()
            self._update_radar_count()
        else:
            self._add_log("ERROR", f"❌ No se pudo agregar {rfc} (inválido o ya existe).")
    
    def _load_watchlist(self):
        """Carga la watchlist en la tabla."""
        for item in self.watchlist_tree.get_children():
            self.watchlist_tree.delete(item)
        
        watchlist = listar_watchlist()
        alertas_rfcs = {a["rfc"] for a in verificar_alertas_watchlist()}
        
        for item in watchlist:
            rfc = item["rfc"]
            estado = "⚠️ LISTA" if rfc in alertas_rfcs else "✅ LIMPIO"
            fecha = item.get("fecha_agregado", "N/A")[:10] if item.get("fecha_agregado") else "N/A"
            
            self.watchlist_tree.insert(
                "",
                "end",
                values=(rfc, item.get("alias", ""), item.get("categoria", "Proveedor"), fecha, estado)
            )
    
    def _save_env(self):
        """Guarda la configuración en .env."""
        env_content = f"""# Configuración generada por GUI
       EFOS_SMTP_HOST={self.config_entries['smtp_host'].get()}
       EFOS_SMTP_PORT={self.config_entries['smtp_port'].get()}
       EFOS_SMTP_USER={self.config_entries['smtp_user'].get()}
       EFOS_SMTP_PASS={self.config_entries['smtp_pass'].get()}
       EFOS_NOTIFY_FROM={self.config_entries['notify_from'].get()}
       EFOS_NOTIFY_TO={self.config_entries['notify_to'].get()}
       EFOS_NOTIFY_ON_NEW=true
       """
        try:
            with open(".env", "w", encoding="utf-8") as f:
                f.write(env_content)
            
            # Recargar configuración
            import config
            config.reload_config()
            
            self._add_log("INFO", "✅ Configuración guardada y recargada en .env")
            messagebox.showinfo("Éxito", "Configuración guardada y aplicada correctamente.")
        except Exception as e:
            self._add_log("ERROR", f"Error guardando .env: {e}")
            messagebox.showerror("Error", f"No se pudo guardar: {e}")
    
    def _test_email(self):
        """Envía un correo de prueba."""
        from notifier import enviar_correo_prueba
        
        # Actualizar config temporalmente
        config.SMTP_HOST = self.config_entries['smtp_host'].get()
        config.SMTP_PORT = int(self.config_entries['smtp_port'].get())
        config.SMTP_USER = self.config_entries['smtp_user'].get()
        config.SMTP_PASSWORD = self.config_entries['smtp_pass'].get()
        config.NOTIFY_FROM = self.config_entries['notify_from'].get()
        config.NOTIFY_TO = self.config_entries['notify_to'].get()
        
        self._add_log("INFO", "Enviando correo de prueba...")
        
        def worker():
            exito, mensaje = enviar_correo_prueba()
            if exito:
                self._add_log("INFO", f"✅ {mensaje}")
                self.after(0, lambda: messagebox.showinfo("Éxito", mensaje))
            else:
                self._add_log("ERROR", f"❌ {mensaje}")
                self.after(0, lambda: messagebox.showerror("Error", mensaje))
        
        threading.Thread(target=worker, daemon=True).start()

    def _install_daemon(self):
        """Instala el daemon de Windows."""
        script_path = Path("scheduler.py").resolve()
        cmd = f'schtasks /Create /TN "SatEfosTracker_Daemon" /TR "pyw.exe {script_path}" /SC ONLOGON /RL HIGHEST /F'
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                self._add_log("INFO", "✅ Daemon instalado correctamente.")
                messagebox.showinfo("Éxito", "Daemon instalado. Se ejecutará al iniciar sesión.")
            else:
                self._add_log("ERROR", f"Error: {result.stderr}")
                messagebox.showerror("Error", f"Falló la instalación:\n{result.stderr}")
        except Exception as e:
            self._add_log("ERROR", f"Error: {e}")
            messagebox.showerror("Error", f"Error: {e}")
    
    def _run_daemon(self):
        """Ejecuta el daemon manualmente."""
        cmd = 'schtasks /Run /TN "SatEfosTracker_Daemon"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                self._add_log("INFO", "✅ Daemon ejecutándose.")
            else:
                self._add_log("ERROR", f"Error: {result.stderr}")
        except Exception as e:
            self._add_log("ERROR", f"Error: {e}")
    
    def _delete_daemon(self):
        """Elimina el daemon."""
        if not messagebox.askyesno("Confirmar", "¿Estás seguro de eliminar el daemon?"):
            return
        
        cmd = 'schtasks /Delete /TN "SatEfosTracker_Daemon" /F'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                self._add_log("INFO", "✅ Daemon eliminado.")
                messagebox.showinfo("Éxito", "Daemon eliminado correctamente.")
            else:
                self._add_log("ERROR", f"Error: {result.stderr}")
        except Exception as e:
            self._add_log("ERROR", f"Error: {e}")
    
    def _show_db_table(self, table_name: str):
        """Muestra una tabla de la base de datos."""
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
        
        self.db_tree["columns"] = []
        
        try:
            conn = get_connection()
            
            # Definir columnas específicas según la tabla
            if table_name == "watchlist":
                columns = ("RFC", "Alias", "Categoría", "Fecha Agregado")
                query = "SELECT rfc, alias, categoria, fecha_agregado FROM watchlist LIMIT 100"
            elif table_name == "sat_snapshots":
                columns = ("ID", "Fecha Descarga", "Total Registros")
                query = "SELECT id, fecha_descarga, total_registros FROM sat_snapshots LIMIT 100"
            elif table_name == "sat_registros":
                columns = ("RFC", "Nombre", "Situación", "Fecha Publicación")
                query = "SELECT rfc, nombre, situacion, fecha_primera_publicacion FROM sat_registros LIMIT 100"
            else:
                columns = ("Columna 1", "Columna 2", "Columna 3")
                query = f"SELECT * FROM {table_name} LIMIT 100"
            
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                self._add_log("WARNING", f"La tabla {table_name} está vacía")
                conn.close()
                return
            
            # Configurar columnas
            self.db_tree["columns"] = columns
            
            for col in columns:
                self.db_tree.heading(col, text=col)
                self.db_tree.column(col, width=200 if col == "Nombre" else 150)
            
            # Agregar filas con datos formateados
            for row in rows:
                formatted_row = []
                for val in row:
                    if val is None:
                        formatted_row.append("N/A")
                    elif isinstance(val, str):
                        # Truncar strings largos
                        formatted_row.append(val[:60] if len(val) > 60 else val)
                    else:
                        formatted_row.append(str(val))
                self.db_tree.insert("", "end", values=formatted_row)
            
            self._add_log("INFO", f"Mostrando {len(rows)} registros de {table_name}")
            conn.close()
        except Exception as e:
            self._add_log("ERROR", f"Error consultando {table_name}: {e}")
    
    def _execute_command(self, event=None):
        """Ejecuta un comando de la barra de comandos."""
        cmd = self.cmd_entry.get().strip().lower()
        self.cmd_entry.delete(0, "end")
        
        if cmd == "help":
            self._add_log("INFO", "Comandos: check RFC, run, status, watchlist, alertas")
        elif cmd.startswith("check "):
            rfc = cmd.split()[1].upper()
            res = consultar_rfc(rfc)
            if res["encontrado"]:
                self._add_log("ERROR", f"⚠️ {rfc} EN LISTA: {res['situacion'].upper()}")
            else:
                self._add_log("INFO", f"✅ {rfc} LIMPIO")
        elif cmd == "run":
            if not self.is_running_cycle:
                threading.Thread(target=ejecutar_ciclo, daemon=True).start()
                self._add_log("INFO", "Ciclo iniciado...")
            else:
                self._add_log("WARNING", "Ya hay un ciclo en ejecución.")
        elif cmd == "status":
            self._switch_view("estado")
        elif cmd == "watchlist":
            self._switch_view("watchlist")
        elif cmd == "alertas":
            alertas = verificar_alertas_watchlist()
            if alertas:
                self._add_log("ERROR", f"⚠️ ALERTAS: {len(alertas)}")
                for a in alertas:
                    self._add_log("ERROR", f"  {a['rfc']} - {a['situacion']}")
            else:
                self._add_log("INFO", "✅ Sin alertas")
        else:
            self._add_log("WARNING", f"Comando no reconocido: {cmd}")
    
    def _poll_logs(self):
        """Procesa los logs de la cola."""
        while True:
            try:
                level, msg = self.log_queue.get_nowait()
                self._add_log(level, msg)
            except queue.Empty:
                break
        self.after(100, self._poll_logs)
    
    def _add_log(self, level: str, message: str):
        """Agrega un mensaje al log con color."""
        self.log_text.insert("end", f"{message}\n", level)
        self.log_text.see("end")
    
    def _update_radar_count(self):
        """Actualiza el contador de RFCs en el radar."""
        count = len(listar_watchlist())
        self.radar_count_label.configure(text=f"RFCs en Radar: {count}")
        self.after(2000, self._update_radar_count)


if __name__ == "__main__":
    app = CyberpunkGUI()
    app.mainloop()
