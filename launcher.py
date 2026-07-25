"""
launcher_ui.py — Interfaz Gráfica MVP para sat-efos-tracker
Incluye: Ejecución, Consulta RFCs y Gestión de Configuración/Notificaciones.
"""
import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
import os

# Asegurar imports locales
sys.path.insert(0, str(Path(__file__).parent))

try:
    import config
    from scheduler import ejecutar_ciclo
    from checker import consultar_rfc, consultar_desde_csv
    from notifier import enviar_reporte, _smtp_configurado
except ImportError as e:
    print(f"ERROR CRÍTICO: {e}")
    sys.exit(1)


class QueueLogHandler(logging.Handler):
    """Handler para redirigir logs del backend al widget de texto."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class SatTrackerUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SAT EFOS Tracker - Monitor Art. 69-B")
        self.root.geometry("900x650")
        
        # Variables de estado
        self.log_queue = queue.Queue()
        self.is_running_cycle = False
        self.daemon_thread = None
        self.is_daemon_running = False

        # Configurar Logging
        self._setup_logging()

        # Construir UI
        self._build_widgets()
        
        # Cargar configuración actual en los campos
        self._load_config_to_ui()

        # Iniciar pollers
        self._poll_log_queue()
        self._update_status_labels()

    def _setup_logging(self):
        self.queue_handler = QueueLogHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')
        self.queue_handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(self.queue_handler)
        root_logger.setLevel(logging.INFO)

    def _build_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Pestaña 1: Estado y Ejecución ---
        tab_exec = ttk.Frame(notebook, padding=10)
        notebook.add(tab_exec, text="Estado y Ejecución")
        self._build_tab_execution(tab_exec)

        # --- Pestaña 2: Consulta RFCs ---
        tab_query = ttk.Frame(notebook, padding=10)
        notebook.add(tab_query, text="Consulta RFCs")
        self._build_tab_query(tab_query)

        # --- Pestaña 3: Configuración y Notificaciones ---
        tab_config = ttk.Frame(notebook, padding=10)
        notebook.add(tab_config, text="Configuración y Alertas")
        self._build_tab_config(tab_config)

    def _build_tab_execution(self, parent):
        frame_controls = ttk.Frame(parent)
        frame_controls.pack(fill=tk.X, pady=(0, 10))

        self.btn_run_cycle = ttk.Button(frame_controls, text="🔄 Ejecutar Ciclo Ahora", command=self._on_run_cycle, style="Action.TButton")
        self.btn_run_cycle.pack(side=tk.LEFT, padx=5)

        self.btn_daemon = ttk.Button(frame_controls, text="▶️ Iniciar Daemon", command=self._toggle_daemon)
        self.btn_daemon.pack(side=tk.LEFT, padx=5)

        # Etiquetas de estado
        frame_status = ttk.LabelFrame(parent, text="Estado del Sistema", padding=10)
        frame_status.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_last_date = ttk.Label(frame_status, text="Último listado: Cargando...")
        self.lbl_last_date.pack(anchor=tk.W)
        self.lbl_daemon_status = ttk.Label(frame_status, text="Daemon: Detenido", foreground="gray")
        self.lbl_daemon_status.pack(anchor=tk.W)

        # Logs
        ttk.Label(parent, text="Registro de Actividad:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.txt_logs = scrolledtext.ScrolledText(parent, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.txt_logs.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _build_tab_query(self, parent):
        # Consulta Individual
        frame_single = ttk.LabelFrame(parent, text="Consulta Individual", padding=10)
        frame_single.pack(fill=tk.X, pady=(0, 10))

        row_single = ttk.Frame(frame_single)
        row_single.pack(fill=tk.X)
        ttk.Label(row_single, text="RFC:").pack(side=tk.LEFT)
        self.ent_rfc = ttk.Entry(row_single, width=20)
        self.ent_rfc.pack(side=tk.LEFT, padx=5)
        self.ent_rfc.bind("<Return>", lambda e: self._on_query_single())
        ttk.Button(row_single, text="Consultar", command=self._on_query_single).pack(side=tk.LEFT)

        # Consulta Masiva
        frame_bulk = ttk.LabelFrame(parent, text="Consulta Masiva (CSV)", padding=10)
        frame_bulk.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(frame_bulk, text="📂 Seleccionar CSV y Consultar", command=self._on_query_csv).pack(side=tk.LEFT)

        # Resultados
        ttk.Label(parent, text="Resultados:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.txt_results = scrolledtext.ScrolledText(parent, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.txt_results.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _build_tab_config(self, parent):
        # Frame SMTP
        frame_smtp = ttk.LabelFrame(parent, text="Configuración de Notificaciones (SMTP)", padding=15)
        frame_smtp.pack(fill=tk.X, pady=10)

        grid_opts = {'sticky': 'w', 'padx': 5, 'pady': 2}
        
        # Host
        ttk.Label(frame_smtp, text="Servidor SMTP:").grid(row=0, column=0, **grid_opts)
        self.ent_smtp_host = ttk.Entry(frame_smtp, width=40)
        self.ent_smtp_host.grid(row=0, column=1, **grid_opts)

        # Puerto
        ttk.Label(frame_smtp, text="Puerto:").grid(row=1, column=0, **grid_opts)
        self.ent_smtp_port = ttk.Entry(frame_smtp, width=10)
        self.ent_smtp_port.grid(row=1, column=1, **grid_opts)

        # Usuario
        ttk.Label(frame_smtp, text="Usuario Email:").grid(row=2, column=0, **grid_opts)
        self.ent_smtp_user = ttk.Entry(frame_smtp, width=40)
        self.ent_smtp_user.grid(row=2, column=1, **grid_opts)

        # Password
        ttk.Label(frame_smtp, text="Contraseña/App Pass:").grid(row=3, column=0, **grid_opts)
        self.ent_smtp_pass = ttk.Entry(frame_smtp, width=40, show="*")
        self.ent_smtp_pass.grid(row=3, column=1, **grid_opts)

        # Destinatarios
        ttk.Label(frame_smtp, text="Enviar a (separado por comas):").grid(row=4, column=0, **grid_opts)
        self.ent_notify_to = ttk.Entry(frame_smtp, width=40)
        self.ent_notify_to.grid(row=4, column=1, **grid_opts)

        # Remitente
        ttk.Label(frame_smtp, text="Remitente:").grid(row=5, column=0, **grid_opts)
        self.ent_notify_from = ttk.Entry(frame_smtp, width=40)
        self.ent_notify_from.grid(row=5, column=1, **grid_opts)

        # Botones de acción
        frame_actions = ttk.Frame(frame_smtp)
        frame_actions.grid(row=6, column=0, columnspan=2, pady=10)
        
        ttk.Button(frame_actions, text="💾 Guardar Configuración", command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_actions, text="📧 Enviar Prueba", command=self._test_email).pack(side=tk.LEFT, padx=5)

        # Info Legal
        info_text = ("Nota: La contraseña se guarda en texto plano en el archivo .env local. "
                     "Para Gmail, usa una 'Contraseña de Aplicación'.")
        ttk.Label(frame_smtp, text=info_text, foreground="gray", font=("Segoe UI", 8)).grid(row=7, column=0, columnspan=2, sticky='w')

    # ─── Lógica de Negocio ──────────────────────────────────────────────

    def _load_config_to_ui(self):
        """Carga las variables de entorno actuales en los entries."""
        self.ent_smtp_host.insert(0, config.SMTP_HOST)
        self.ent_smtp_port.insert(0, str(config.SMTP_PORT))
        self.ent_smtp_user.insert(0, config.SMTP_USER)
        self.ent_smtp_pass.insert(0, config.SMTP_PASSWORD)
        self.ent_notify_to.insert(0, config.NOTIFY_TO)
        self.ent_notify_from.insert(0, config.NOTIFY_FROM)

    def _save_config(self):
        """Guarda la configuración en un archivo .env local."""
        env_path = Path(".env")
        content = f"""
EFOS_SMTP_HOST={self.ent_smtp_host.get().strip()}
EFOS_SMTP_PORT={self.ent_smtp_port.get().strip()}
EFOS_SMTP_USER={self.ent_smtp_user.get().strip()}
EFOS_SMTP_PASS={self.ent_smtp_pass.get().strip()}
EFOS_NOTIFY_FROM={self.ent_notify_from.get().strip()}
EFOS_NOTIFY_TO={self.ent_notify_to.get().strip()}
EFOS_NOTIFY_ON_NEW=true
"""
        try:
            with open(env_path, "w") as f:
                f.write(content)
            messagebox.showinfo("Éxito", "Configuración guardada en .env.\nReinicia la aplicación para aplicar cambios completos.")
            self._append_log_ui("✅ Configuración guardada en .env")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar .env: {e}")

    def _test_email(self):
        """Envía un correo de prueba usando la configuración actual de la UI."""
        # Actualizamos temporalmente el módulo config para la prueba
        config.SMTP_HOST = self.ent_smtp_host.get().strip()
        config.SMTP_PORT = int(self.ent_smtp_port.get().strip())
        config.SMTP_USER = self.ent_smtp_user.get().strip()
        config.SMTP_PASSWORD = self.ent_smtp_pass.get().strip()
        config.NOTIFY_FROM = self.ent_notify_from.get().strip()
        config.NOTIFY_TO = self.ent_notify_to.get().strip()

        if not all([config.SMTP_HOST, config.SMTP_USER, config.NOTIFY_FROM, config.NOTIFY_TO]):
            messagebox.showwarning("Faltan Datos", "Completa todos los campos SMTP antes de probar.")
            return

        diff_prueba = {
            "nuevos": [{"rfc": "TEST010101TEST", "situacion": "presunto", "nombre": "PRUEBA UI"}],
            "cambios": [],
            "bajas": []
        }

        self._append_log_ui("📤 Enviando correo de prueba...")
        threading.Thread(target=self._worker_test_email, args=(diff_prueba,), daemon=True).start()

    def _worker_test_email(self, diff):
        success = enviar_reporte(diff)
        if success:
            self.root.after(0, lambda: messagebox.showinfo("Éxito", "Correo de prueba enviado correctamente."))
            self.root.after(0, lambda: self._append_log_ui("✅ Correo de prueba enviado."))
        else:
            self.root.after(0, lambda: messagebox.showerror("Error", "Falló el envío. Revisa los logs."))
            self.root.after(0, lambda: self._append_log_ui("❌ Falló envío de correo de prueba."))

    def _toggle_daemon(self):
        if self.is_daemon_running:
            self.is_daemon_running = False
            self.btn_daemon.config(text="▶️ Iniciar Daemon")
            self.lbl_daemon_status.config(text="Daemon: Deteniendo...", foreground="orange")
        else:
            self.is_daemon_running = True
            self.btn_daemon.config(text="⏹️ Detener Daemon")
            self.lbl_daemon_status.config(text="Daemon: Ejecutando...", foreground="green")
            threading.Thread(target=self._worker_daemon, daemon=True).start()

    def _worker_daemon(self):
        import schedule
        import time
        self._append_log_ui(f"🕒 Daemon iniciado. Programado para: {config.SCHEDULE_TIME}")
        schedule.every().day.at(config.SCHEDULE_TIME).do(ejecutar_ciclo)
        
        while self.is_daemon_running:
            schedule.run_pending()
            time.sleep(10) # Chequear cada 10s
        
        self.root.after(0, lambda: self.lbl_daemon_status.config(text="Daemon: Detenido", foreground="gray"))

    def _on_run_cycle(self):
        if self.is_running_cycle: return
        self.is_running_cycle = True
        self.btn_run_cycle.config(state=tk.DISABLED)
        threading.Thread(target=self._worker_run_cycle, daemon=True).start()

    def _worker_run_cycle(self):
        try:
            ejecutar_ciclo()
        except Exception as e:
            self.log_queue.put(f"💥 ERROR EN CICLO: {e}")
        finally:
            self.root.after(0, self._cycle_finished)

    def _cycle_finished(self):
        self.is_running_cycle = False
        self.btn_run_cycle.config(state=tk.NORMAL)
        self._update_status_labels()

    def _on_query_single(self):
        rfc = self.ent_rfc.get().strip()
        if not rfc: return
        self._set_results_text(f"Consultando {rfc}...\n")
        threading.Thread(target=self._worker_query_single, args=(rfc,), daemon=True).start()

    def _worker_query_single(self, rfc):
        try:
            res = consultar_rfc(rfc)
            output = self._format_result(res)
            self.root.after(0, self._set_results_text, output)
        except Exception as e:
            self.root.after(0, self._set_results_text, f"Error: {e}")

    def _on_query_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path: return
        self._set_results_text(f"Procesando {path}...\n")
        threading.Thread(target=self._worker_query_csv, args=(path,), daemon=True).start()

    def _worker_query_csv(self, path_str):
        try:
            resultados = consultar_desde_csv(Path(path_str))
            encontrados = [r for r in resultados if r.get("encontrado")]
            lines = [f"Total: {len(resultados)} | Coincidencias: {len(encontrados)}", "-"*40]
            for r in encontrados:
                lines.append(self._format_result(r))
            self.root.after(0, self._set_results_text, "\n".join(lines))
        except Exception as e:
            self.root.after(0, self._set_results_text, f"Error CSV: {e}")

    # ─── Utilidades UI ──────────────────────────────────────────────────

    def _poll_log_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
                self._append_log_ui(msg)
            except queue.Empty:
                break
        self.root.after(100, self._poll_log_queue)

    def _append_log_ui(self, message):
        self.txt_logs.config(state=tk.NORMAL)
        self.txt_logs.insert(tk.END, message + "\n")
        self.txt_logs.see(tk.END)
        self.txt_logs.config(state=tk.DISABLED)

    def _set_results_text(self, content):
        self.txt_results.config(state=tk.NORMAL)
        self.txt_results.delete("1.0", tk.END)
        self.txt_results.insert(tk.END, content)
        self.txt_results.config(state=tk.DISABLED)

    def _update_status_labels(self):
        try:
            latest_path = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
            if latest_path.exists():
                mtime = datetime.fromtimestamp(latest_path.stat().st_mtime)
                self.lbl_last_date.config(text=f"Último listado: {mtime:%Y-%m-%d %H:%M}")
            else:
                self.lbl_last_date.config(text="Último listado: Sin datos")
        except: pass

    @staticmethod
    def _format_result(r):
        if r.get("encontrado"):
            return (f"\n⚠️ {r['rfc']} | {r['situacion'].upper()}\n   {r.get('nombre', 'N/D')}\n{'─'*40}")
        return f"\n✅ {r.get('rfc')} - Limpio"

def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    SatTrackerUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()