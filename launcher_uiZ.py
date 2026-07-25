"""
launcher_ui.py — Interfaz Gráfica MVP para sat-efos-tracker
Requiere: Python 3.9+, tkinter (incluido en stdlib), y los módulos del proyecto.
"""
import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys

# Asegurar que los módulos locales sean visibles si se ejecuta fuera del directorio
sys.path.insert(0, str(Path(__file__).parent))

try:
    import config
    from scheduler import ejecutar_ciclo
    from checker import consultar_rfc, consultar_desde_csv
except ImportError as e:
    print(f"ERROR CRÍTICO: No se pudieron importar los módulos del backend: {e}")
    print("Asegúrate de ejecutar este script desde la raíz del proyecto.")
    sys.exit(1)


class QueueLogHandler(logging.Handler):
    """Handler personalizado para enviar logs a un widget Text de Tkinter de forma segura."""
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
        self.root.geometry("850x600")
        self.root.minsize(700, 500)

        # Configuración de estilo
        style = ttk.Style()
        style.configure("TNotebook.Tab", padding=[12, 4])
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"))

        # Variables compartidas
        self.log_queue = queue.Queue()
        self.is_running = False
        
        # Configurar Logging Global para capturar todo en la UI
        self._setup_logging()

        # Construir UI
        self._build_widgets()
        
        # Iniciar monitoreo de logs y estado
        self._poll_log_queue()
        self._update_status_labels()

    def _setup_logging(self):
        """Configura el logger root para que tanto la consola como la UI reciban logs."""
        self.queue_handler = QueueLogHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')
        self.queue_handler.setFormatter(formatter)
        
        # Añadir handler al logger root y al del scheduler
        logging.getLogger().addHandler(self.queue_handler)
        logging.getLogger("scheduler").addHandler(self.queue_handler)
        logging.getLogger("checker").addHandler(self.queue_handler)
        
        # Nivel mínimo para la UI
        logging.getLogger().setLevel(logging.INFO)

    def _build_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Pestaña 1: Estado y Ejecución ---
        tab_exec = ttk.Frame(notebook, padding=10)
        notebook.add(tab_exec, text="Estado y Ejecución")

        frame_controls = ttk.Frame(tab_exec)
        frame_controls.pack(fill=tk.X, pady=(0, 10))

        self.btn_run_cycle = ttk.Button(
            frame_controls, 
            text="🔄 Ejecutar Ciclo Completo", 
            command=self._on_run_cycle,
            style="Action.TButton"
        )
        self.btn_run_cycle.pack(side=tk.LEFT)

        # Etiquetas de estado
        frame_status = ttk.LabelFrame(tab_exec, text="Estado Actual", padding=10)
        frame_status.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_last_date = ttk.Label(frame_status, text="Último listado: Cargando...")
        self.lbl_last_date.pack(anchor=tk.W)
        self.lbl_last_status = ttk.Label(frame_status, text="Estado: Desconocido")
        self.lbl_last_status.pack(anchor=tk.W)

        # Área de Logs
        ttk.Label(tab_exec, text="Registro de Actividad:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.txt_logs = scrolledtext.ScrolledText(tab_exec, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.txt_logs.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # --- Pestaña 2: Consulta RFCs ---
        tab_query = ttk.Frame(notebook, padding=10)
        notebook.add(tab_query, text="Consulta RFCs")

        # Consulta Individual
        frame_single = ttk.LabelFrame(tab_query, text="Consulta Individual", padding=10)
        frame_single.pack(fill=tk.X, pady=(0, 10))

        row_single = ttk.Frame(frame_single)
        row_single.pack(fill=tk.X)
        
        ttk.Label(row_single, text="RFC:").pack(side=tk.LEFT)
        self.ent_rfc = ttk.Entry(row_single, width=20)
        self.ent_rfc.pack(side=tk.LEFT, padx=5)
        self.ent_rfc.bind("<Return>", lambda e: self._on_query_single())
        
        self.btn_query_single = ttk.Button(row_single, text="Consultar", command=self._on_query_single)
        self.btn_query_single.pack(side=tk.LEFT)

        # Consulta Masiva
        frame_bulk = ttk.LabelFrame(tab_query, text="Consulta Masiva (CSV)", padding=10)
        frame_bulk.pack(fill=tk.X, pady=(0, 10))

        row_bulk = ttk.Frame(frame_bulk)
        row_bulk.pack(fill=tk.X)

        self.btn_query_csv = ttk.Button(row_bulk, text="📂 Seleccionar CSV y Consultar", command=self._on_query_csv)
        self.btn_query_csv.pack(side=tk.LEFT)

        # Resultados
        ttk.Label(tab_query, text="Resultados:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.txt_results = scrolledtext.ScrolledText(tab_query, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.txt_results.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    # ─── Lógica de Negocio (Thread-Safe) ──────────────────────────────────────

    def _on_run_cycle(self):
        if self.is_running:
            messagebox.showwarning("En progreso", "Ya hay una tarea ejecutándose.")
            return
        
        self.is_running = True
        self.btn_run_cycle.config(state=tk.DISABLED)
        self._append_log_ui(">>> Iniciando ciclo manual de descarga y procesamiento...")
        
        threading.Thread(target=self._worker_run_cycle, daemon=True).start()

    def _worker_run_cycle(self):
        try:
            success = ejecutar_ciclo()
            result_msg = "✅ Ciclo completado exitosamente." if success else "❌ Ciclo finalizado con errores. Revisa el log."
            self.log_queue.put(result_msg)
        except Exception as e:
            self.log_queue.put(f"💥 ERROR INESPERADO EN CICLO: {e}")
        finally:
            # Programar actualización de UI en hilo principal
            self.root.after(0, self._cycle_finished)

    def _cycle_finished(self):
        self.is_running = False
        self.btn_run_cycle.config(state=tk.NORMAL)
        self._update_status_labels()

    def _on_query_single(self):
        rfc = self.ent_rfc.get().strip()
        if not rfc:
            messagebox.showinfo("Atención", "Ingresa un RFC para consultar.")
            return
        
        self._set_results_text(f"Consultando RFC: {rfc}...\n")
        threading.Thread(target=self._worker_query_single, args=(rfc,), daemon=True).start()

    def _worker_query_single(self, rfc: str):
        try:
            res = consultar_rfc(rfc)
            output = self._format_checker_result(res)
            self.root.after(0, self._set_results_text, output)
        except Exception as e:
            self.root.after(0, self._set_results_text, f"Error al consultar: {e}")

    def _on_query_csv(self):
        path = filedialog.askopenfilename(
            title="Seleccionar CSV con RFCs",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
            
        self._set_results_text(f"Procesando archivo: {path}\nEsto puede tardar unos segundos...\n")
        threading.Thread(target=self._worker_query_csv, args=(path,), daemon=True).start()

    def _worker_query_csv(self, path_str: str):
        try:
            ruta = Path(path_str)
            resultados = consultar_desde_csv(ruta)
            
            encontrados = [r for r in resultados if r.get("encontrado")]
            lines = [
                f"RESUMEN DE CONSULTA MASIVA",
                f"Total procesados: {len(resultados)}",
                f"Coincidencias en lista 69-B: {len(encontrados)}",
                "-" * 50
            ]
            
            if encontrados:
                for r in encontrados:
                    lines.append(self._format_checker_result(r))
            else:
                lines.append("\nNo se encontraron RFCs coincidentes en el listado local.")
                
            self.root.after(0, self._set_results_text, "\n".join(lines))
            
        except FileNotFoundError:
            self.root.after(0, self._set_results_text, "Error: Archivo no encontrado.")
        except KeyError as e:
            self.root.after(0, self._set_results_text, f"Error: El CSV no tiene la columna esperada ('rfc'). Detalle: {e}")
        except Exception as e:
            self.root.after(0, self._set_results_text, f"Error inesperado procesando CSV: {e}")

    # ─── Utilidades de UI ─────────────────────────────────────────────────────

    def _poll_log_queue(self):
        """Revisa la cola de logs cada 100ms y actualiza el widget."""
        while True:
            try:
                msg = self.log_queue.get_nowait()
                self._append_log_ui(msg)
            except queue.Empty:
                break
        self.root.after(100, self._poll_log_queue)

    def _append_log_ui(self, message: str):
        self.txt_logs.config(state=tk.NORMAL)
        self.txt_logs.insert(tk.END, message + "\n")
        self.txt_logs.see(tk.END)
        self.txt_logs.config(state=tk.DISABLED)

    def _set_results_text(self, content: str):
        self.txt_results.config(state=tk.NORMAL)
        self.txt_results.delete("1.0", tk.END)
        self.txt_results.insert(tk.END, content)
        self.txt_results.config(state=tk.DISABLED)

    def _update_status_labels(self):
        """Actualiza las etiquetas de la pestaña 1 leyendo el sistema de archivos."""
        try:
            latest_path = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
            if latest_path.exists():
                mtime = datetime.fromtimestamp(latest_path.stat().st_mtime)
                size_kb = latest_path.stat().st_size / 1024
                self.lbl_last_date.config(text=f"Último listado: {mtime:%Y-%m-%d %H:%M} ({size_kb:.1f} KB)")
                self.lbl_last_status.config(text="Estado: ✅ Datos locales disponibles", foreground="green")
            else:
                self.lbl_last_date.config(text="Último listado: Sin datos")
                self.lbl_last_status.config(text="Estado: ⚠️ Ejecuta un ciclo primero", foreground="orange")
        except Exception as e:
            self.lbl_last_status.config(text=f"Estado: Error leyendo datos ({e})", foreground="red")

    @staticmethod
    def _format_checker_result(r: dict) -> str:
        if r.get("encontrado"):
            sit = (r.get("situacion") or "DESCONOCIDA").upper()
            return (
                f"\n⚠️  ENCONTRADO: {r['rfc']}\n"
                f"   Situación : {sit}\n"
                f"   Nombre    : {r.get('nombre', 'N/D')}\n"
                f"   Publicado : {r.get('fecha_primera_publicacion', 'N/D')}\n"
                f"   Oficio    : {r.get('numero_oficio', 'N/D')}\n"
                f"{'─'*40}"
            )
        return f"\n✅ NO ENCONTRADO: {r.get('rfc', 'N/A')} (Fuente: Listado Local)\n{'─'*40}"


def main():
    root = tk.Tk()
    # Intentar mejorar resolución en Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    app = SatTrackerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()