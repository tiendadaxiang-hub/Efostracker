"""
launcher_ui.py — Interfaz Gráfica MVP para sat-efos-tracker
Incluye: Ejecución, Consulta RFCs, Gestión de Configuración (.env) y Control de Daemon Windows.
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
import subprocess
import ctypes

# Asegurar imports locales
sys.path.insert(0, str(Path(__file__).parent))

try:
    import config
    from scheduler import ejecutar_ciclo
    from checker import consultar_rfc, consultar_desde_csv
    from notifier import enviar_reporte, _smtp_configurado
    from parser import cargar_procesado
except ImportError as e:
    print(f"ERROR CRÍTICO: {e}")
    sys.exit(1)


class QueueLogHandler(logging.Handler):
    """Handler para redirigir logs del backend al widget de texto con formato oficial."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        # Formato idéntico al de scheduler.py para consistencia visual
        self.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s", 
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class SatTrackerUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SAT EFOS Tracker - Monitor Art. 69-B")
        self.root.geometry("950x700")
        
        # Variables de estado
        self.log_queue = queue.Queue()
        self.is_running_cycle = False
        
        # Rutas importantes
        self.project_root = Path(__file__).parent
        self.env_file = self.project_root / ".env"
        self.scheduler_script = self.project_root / "scheduler.py"
        
        # Configurar Logging
        self._setup_logging()

        # Construir UI
        self._build_widgets()
        
        # Cargar configuración actual en los campos
        self._load_env_to_ui()

        # Iniciar pollers
        self._poll_log_queue()
        self._update_status_labels()

    def _setup_logging(self):
        self.queue_handler = QueueLogHandler(self.log_queue)
        
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

        # --- Pestaña 3: Configuración y Daemon ---
        tab_config = ttk.Frame(notebook, padding=10)
        notebook.add(tab_config, text="Configuración y Daemon")
        self._build_tab_config(tab_config)

    def _build_tab_execution(self, parent):
        frame_controls = ttk.Frame(parent)
        frame_controls.pack(fill=tk.X, pady=(0, 10))

        self.btn_run_cycle = ttk.Button(frame_controls, text="🔄 Ejecutar Ciclo Ahora", command=self._on_run_cycle, style="Action.TButton")
        self.btn_run_cycle.pack(side=tk.LEFT, padx=5)

        # Etiquetas de estado
        frame_status = ttk.LabelFrame(parent, text="Estado del Sistema", padding=10)
        frame_status.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_last_date = ttk.Label(frame_status, text="Último listado: Cargando...")
        self.lbl_last_date.pack(anchor=tk.W)
        self.lbl_daemon_status = ttk.Label(frame_status, text="Daemon Windows: No verificado", foreground="gray")
        self.lbl_daemon_status.pack(anchor=tk.W)
        
        btn_check_daemon = ttk.Button(frame_status, text="Verificar Estado Daemon", command=self._check_windows_daemon)
        btn_check_daemon.pack(anchor=tk.E, pady=5)

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
        
        ttk.Label(frame_smtp, text="Servidor SMTP:").grid(row=0, column=0, **grid_opts)
        self.ent_smtp_host = ttk.Entry(frame_smtp, width=40)
        self.ent_smtp_host.grid(row=0, column=1, **grid_opts)

        ttk.Label(frame_smtp, text="Puerto:").grid(row=1, column=0, **grid_opts)
        self.ent_smtp_port = ttk.Entry(frame_smtp, width=10)
        self.ent_smtp_port.grid(row=1, column=1, **grid_opts)

        ttk.Label(frame_smtp, text="Usuario Email:").grid(row=2, column=0, **grid_opts)
        self.ent_smtp_user = ttk.Entry(frame_smtp, width=40)
        self.ent_smtp_user.grid(row=2, column=1, **grid_opts)

        ttk.Label(frame_smtp, text="Contraseña/App Pass:").grid(row=3, column=0, **grid_opts)
        self.ent_smtp_pass = ttk.Entry(frame_smtp, width=40, show="*")
        self.ent_smtp_pass.grid(row=3, column=1, **grid_opts)

        ttk.Label(frame_smtp, text="Enviar a (separado por comas):").grid(row=4, column=0, **grid_opts)
        self.ent_notify_to = ttk.Entry(frame_smtp, width=40)
        self.ent_notify_to.grid(row=4, column=1, **grid_opts)

        ttk.Label(frame_smtp, text="Remitente:").grid(row=5, column=0, **grid_opts)
        self.ent_notify_from = ttk.Entry(frame_smtp, width=40)
        self.ent_notify_from.grid(row=5, column=1, **grid_opts)

        frame_actions = ttk.Frame(frame_smtp)
        frame_actions.grid(row=6, column=0, columnspan=2, pady=10)
        
        ttk.Button(frame_actions, text="💾 Guardar en .env", command=self._save_env).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_actions, text="📧 Enviar Prueba", command=self._test_email).pack(side=tk.LEFT, padx=5)

        # Frame Daemon Windows
        frame_daemon = ttk.LabelFrame(parent, text="Gestión de Daemon Windows (Task Scheduler)", padding=15)
        frame_daemon.pack(fill=tk.X, pady=10)

        info_text = (
            "El daemon de Windows ejecuta el monitoreo en segundo plano (sin ventana negra) "
            "cada vez que inicias sesión. Requiere permisos de Administrador."
        )
        ttk.Label(frame_daemon, text=info_text, wraplength=800, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))

        frame_daemon_btns = ttk.Frame(frame_daemon)
        frame_daemon_btns.pack(fill=tk.X)

        ttk.Button(frame_daemon_btns, text="🔌 Instalar Daemon", command=self._install_daemon).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_daemon_btns, text="▶️ Ejecutar Ahora (Task)", command=self._run_daemon_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_daemon_btns, text="🗑️ Eliminar Daemon", command=self._delete_daemon).pack(side=tk.LEFT, padx=5)

    # ─── Lógica de Negocio ──────────────────────────────────────────────

    def _is_admin(self):
        """Verifica si el script tiene privilegios de administrador."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def _load_env_to_ui(self):
        """Lee el archivo .env y llena los campos si existen."""
        env_vars = {}
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        
        # Rellenar campos con valores del .env o dejar vacíos
        self.ent_smtp_host.insert(0, env_vars.get('EFOS_SMTP_HOST', ''))
        self.ent_smtp_port.insert(0, env_vars.get('EFOS_SMTP_PORT', '587'))
        self.ent_smtp_user.insert(0, env_vars.get('EFOS_SMTP_USER', ''))
        self.ent_smtp_pass.insert(0, env_vars.get('EFOS_SMTP_PASS', ''))
        self.ent_notify_to.insert(0, env_vars.get('EFOS_NOTIFY_TO', ''))
        self.ent_notify_from.insert(0, env_vars.get('EFOS_NOTIFY_FROM', ''))

    def _save_env(self):
        """Guarda la configuración actual en el archivo .env."""
        content = f"""# Configuración generada por launcher_ui.py
EFOS_SMTP_HOST={self.ent_smtp_host.get().strip()}
EFOS_SMTP_PORT={self.ent_smtp_port.get().strip()}
EFOS_SMTP_USER={self.ent_smtp_user.get().strip()}
EFOS_SMTP_PASS={self.ent_smtp_pass.get().strip()}
EFOS_NOTIFY_FROM={self.ent_notify_from.get().strip()}
EFOS_NOTIFY_TO={self.ent_notify_to.get().strip()}
EFOS_NOTIFY_ON_NEW=true
EFOS_SCHEDULE_TIME=06:00
EFOS_RUN_ON_START=false
"""
        try:
            with open(self.env_file, "w") as f:
                f.write(content)
            messagebox.showinfo("Éxito", "Configuración guardada en .env.\nReinicia la aplicación para aplicar cambios completos.")
            self._append_log_ui("✅ Configuración guardada en .env")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar .env: {e}")

    def _test_email(self):
        """Envía un correo de prueba usando datos reales del sistema."""
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

        # Generar un diff "falso" pero con estructura real para probar el HTML
        ruta_latest = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
        diff_prueba = {
            "fecha_comparacion": datetime.now().isoformat(),
            "total_anterior": 0,
            "total_nuevo": 0,
            "nuevos": [],
            "cambios": [],
            "bajas": [],
            "sin_cambio": 0
        }

        if ruta_latest.exists():
            try:
                regs = cargar_procesado(ruta_latest)
                # Tomamos los primeros 3 como ejemplo de "Nuevos" para la prueba visual
                sample = regs[:3] if len(regs) >= 3 else regs
                diff_prueba["nuevos"] = sample
                diff_prueba["total_nuevo"] = len(regs)
            except Exception:
                pass

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

    def _check_windows_daemon(self):
        """Verifica si la tarea programada existe en Windows."""
        try:
            result = subprocess.run(['schtasks', '/Query', '/TN', 'SatEfosTracker_Daemon'], 
                                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                self.lbl_daemon_status.config(text="Daemon Windows: ✅ Instalado y Activo", foreground="green")
            else:
                self.lbl_daemon_status.config(text="Daemon Windows: ❌ No instalado", foreground="red")
        except Exception as e:
            self.lbl_daemon_status.config(text=f"Error verificando daemon: {e}", foreground="orange")

    def _install_daemon(self):
        """Crea la tarea programada en Windows usando pyw.exe para modo invisible."""
        if not self._is_admin():
            resp = messagebox.askyesno(
                "Permisos Requeridos", 
                "Para instalar el daemon necesitas permisos de Administrador.\n\n"
                "¿Deseas abrir una ventana de PowerShell elevada para completar la instalación?"
            )
            if not resp:
                return
            # Abrir PowerShell elevado para ejecutar el comando
            script_path = self.scheduler_script.resolve()
            cmd = f'schtasks /Create /TN "SatEfosTracker_Daemon" /TR "pyw.exe {script_path}" /SC ONLOGON /RL HIGHEST /F'
            ps_cmd = f'Start-Process powershell -Verb RunAs -ArgumentList "-NoExit -Command \\"{cmd}\\""'
            subprocess.Popen(["powershell", "-Command", ps_cmd])
            messagebox.showinfo("Instrucción", "Se ha abierto una ventana de PowerShell. Por favor confirma la instalación allí.")
            return

        script_path = self.scheduler_script.resolve()
        cmd = f'schtasks /Create /TN "SatEfosTracker_Daemon" /TR "pyw.exe {script_path}" /SC ONLOGON /RL HIGHEST /F'
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                messagebox.showinfo("Éxito", "Daemon instalado correctamente.\nSe ejecutará al iniciar sesión.")
                self._check_windows_daemon()
            else:
                messagebox.showerror("Error", f"Falló la instalación:\n{result.stderr}")
        except Exception as e:
            messagebox.showerror("Error", f"Error ejecutando schtasks: {e}")

    def _run_daemon_task(self):
        """Fuerza la ejecución inmediata de la tarea programada."""
        cmd = 'schtasks /Run /TN "SatEfosTracker_Daemon"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                messagebox.showinfo("Éxito", "Tarea programada ejecutándose en segundo plano.")
            else:
                messagebox.showerror("Error", f"Falló la ejecución:\n{result.stderr}")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    def _delete_daemon(self):
        """Elimina la tarea programada."""
        if not messagebox.askyesno("Confirmar", "¿Estás seguro de que deseas eliminar el daemon del sistema?"):
            return
            
        cmd = 'schtasks /Delete /TN "SatEfosTracker_Daemon" /F'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                messagebox.showinfo("Éxito", "Daemon eliminado correctamente.")
                self._check_windows_daemon()
            else:
                messagebox.showerror("Error", f"Falló la eliminación:\n{result.stderr}")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

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
            output = self._format_result_table([res])
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
            lines = [f"Total consultados: {len(resultados)}"]
            lines.append(self._format_result_table(resultados))
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
    def _format_result_table(resultados: list[dict]) -> str:
        """Formatea los resultados en una tabla legible."""
        if not resultados:
            return "No se encontraron resultados."
        
        header = f"{'RFC':<15} | {'ESTADO':<12} | {'SITUACIÓN':<15} | {'NOMBRE'}\n"
        header += "-" * 100 + "\n"
        
        rows = []
        for r in resultados:
            rfc = r.get('rfc', 'N/A')
            encontrado = "⚠️ LISTA" if r.get('encontrado') else "✅ LIMPIO"
            situacion = r.get('situacion', 'N/A').upper() if r.get('situacion') else 'N/A'
            nombre = r.get('nombre', 'N/A')[:50]
            
            rows.append(f"{rfc:<15} | {encontrado:<12} | {situacion:<15} | {nombre}")
            
        return header + "\n".join(rows)

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