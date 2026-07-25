import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Asegurar que el path del proyecto esté disponible
sys.path.insert(0, str(Path(__file__).parent))

try:
    import config
    from scheduler import ejecutar_ciclo, mostrar_status
    from checker import consultar_rfc, consultar_desde_csv
except ImportError as e:
    print(f"ERROR CRÍTICO: No se pueden importar los módulos del backend. {e}")
    sys.exit(1)


class QueueLogHandler(logging.Handler):
    """Handler personalizado para redirigir logs de Python al widget Text de la UI."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class SatEfosTrackerUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SAT EFOS Tracker - Panel de Control")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)

        # Configuración de estilo
        style = ttk.Style()
        style.theme_use('clam') 
        
        # Variables de estado
        self.is_running = False
        self.log_queue = queue.Queue()
        
        # Configurar Logging para capturar salida del backend
        self._setup_logging()

        # Construir UI
        self._build_ui()
        
        # Cargar estado inicial
        self._update_status_labels()
        
        # Iniciar bucle de lectura de logs
        self._poll_log_queue()

    def _setup_logging(self):
        """Configura el logging para que duplique la salida a la UI."""
        self.ui_log_handler = QueueLogHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
        self.ui_log_handler.setFormatter(formatter)
        
        # Añadir handler al logger raíz y al del scheduler
        logging.getLogger().addHandler(self.ui_log_handler)
        logging.getLogger("scheduler").addHandler(self.ui_log_handler)
        logging.getLogger("checker").addHandler(self.ui_log_handler)

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Pestaña 1: Estado y Ejecución ---
        tab_exec = ttk.Frame(notebook, padding=10)
        notebook.add(tab_exec, text="Estado y Ejecución")
        self._build_exec_tab(tab_exec)

        # --- Pestaña 2: Consulta RFCs ---
        tab_query = ttk.Frame(notebook, padding=10)
        notebook.add(tab_query, text="Consulta RFCs")
        self._build_query_tab(tab_query)

    def _build_exec_tab(self, parent):
        # Marco de Estado
        status_frame = ttk.LabelFrame(parent, text="Estado Actual", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_last_date = ttk.Label(status_frame, text="Último listado: --")
        self.lbl_last_date.pack(anchor=tk.W)
        
        self.lbl_last_status = ttk.Label(status_frame, text="Estado: Desconocido")
        self.lbl_last_status.pack(anchor=tk.W)

        btn_refresh_status = ttk.Button(status_frame, text="Actualizar Estado", command=self._update_status_labels)
        btn_refresh_status.pack(anchor=tk.E, pady=(5,0))

        # Botón de Acción Principal
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=10)
        
        self.btn_run_cycle = ttk.Button(
            action_frame, 
            text="🚀 Ejecutar Ciclo Completo Ahora", 
            command=self._run_scheduler_threaded
        )
        self.btn_run_cycle.pack(fill=tk.X, ipady=5)

        # Consola de Logs
        log_frame = ttk.LabelFrame(parent, text="Consola de Ejecución", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.txt_logs = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.txt_logs.pack(fill=tk.BOTH, expand=True)

    def _build_query_tab(self, parent):
        # Consulta Individual
        single_frame = ttk.LabelFrame(parent, text="Consulta Individual", padding=10)
        single_frame.pack(fill=tk.X, pady=(0, 10))

        row = ttk.Frame(single_frame)
        row.pack(fill=tk.X)
        
        ttk.Label(row, text="RFC:").pack(side=tk.LEFT)
        self.ent_rfc = ttk.Entry(row, width=20)
        self.ent_rfc.pack(side=tk.LEFT, padx=5)
        self.ent_rfc.bind("<Return>", lambda e: self._query_single_rfc())
        
        ttk.Button(row, text="Consultar", command=self._query_single_rfc).pack(side=tk.LEFT)

        # Consulta Masiva
        batch_frame = ttk.LabelFrame(parent, text="Consulta Masiva (CSV)", padding=10)
        batch_frame.pack(fill=tk.X, pady=(0, 10))

        batch_row = ttk.Frame(batch_frame)
        batch_row.pack(fill=tk.X)
        
        self.lbl_csv_path = ttk.Label(batch_row, text="Ningún archivo seleccionado", foreground="gray")
        self.lbl_csv_path.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(batch_row, text="Seleccionar CSV", command=self._select_csv_for_batch).pack(side=tk.RIGHT)
        
        self.btn_batch_query = ttk.Button(batch_frame, text="Procesar CSV", command=self._run_batch_query_threaded, state=tk.DISABLED)
        self.btn_batch_query.pack(fill=tk.X, pady=(5,0))
        self.batch_csv_path = None

        # Resultados
        res_frame = ttk.LabelFrame(parent, text="Resultados", padding=5)
        res_frame.pack(fill=tk.BOTH, expand=True)
        
        self.txt_results = scrolledtext.ScrolledText(res_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        self.txt_results.pack(fill=tk.BOTH, expand=True)

    # --- Lógica de Negocio y Threading ---

    def _update_status_labels(self):
        """Lee el sistema de archivos para actualizar las etiquetas de estado."""
        try:
            latest_file = config.DATA_PROCESSED / config.LAST_SNAPSHOT_NAME
            if latest_file.exists():
                mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
                size_kb = latest_file.stat().st_size / 1024
                self.lbl_last_date.config(text=f"Último listado: {mtime.strftime('%Y-%m-%d %H:%M')} ({size_kb:.1f} KB)")
                self.lbl_last_status.config(text="Estado: ✅ Listado local disponible", foreground="green")
            else:
                self.lbl_last_date.config(text="Último listado: N/A")
                self.lbl_last_status.config(text="Estado: ⚠️ Sin datos locales (Ejecuta ciclo primero)", foreground="orange")
        except Exception as e:
            self.lbl_last_status.config(text=f"Error leyendo estado: {e}", foreground="red")

    def _run_scheduler_threaded(self):
        if self.is_running:
            messagebox.showwarning("En progreso", "Ya hay una tarea ejecutándose.")
            return
        
        self.is_running = True
        self.btn_run_cycle.config(state=tk.DISABLED)
        self._clear_log()
        self._append_log("--- INICIANDO CICLO DE ACTUALIZACIÓN ---\n")
        
        def worker():
            try:
                # Llamada directa al backend
                success = ejecutar_ciclo()
                result_msg = "\n✅ CICLO COMPLETADO CON ÉXITO\n" if success else "\n❌ CICLO FINALIZADO CON ERRORES\n"
                self.log_queue.put(result_msg)
            except Exception as e:
                self.log_queue.put(f"\n💥 ERROR FATAL EN SCHEDULER: {e}\n")
            finally:
                self.root.after(0, self._on_task_complete)

        threading.Thread(target=worker, daemon=True).start()

    def _query_single_rfc(self):
        rfc = self.ent_rfc.get().strip().upper()
        if not rfc:
            messagebox.showinfo("Info", "Ingresa un RFC válido.")
            return
            
        self._clear_results()
        self._append_result(f"Buscando RFC: {rfc}...\n")
        
        try:
            # La consulta individual es rápida, puede ir en hilo principal o background
            # Usamos background para mantener consistencia y no congelar si el cache es grande
            def worker():
                res = consultar_rfc(rfc)
                output = self._format_checker_result(res)
                self.root.after(0, lambda: self._append_result(output))
            
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self._append_result(f"Error consultando: {e}\n")

    def _select_csv_for_batch(self):
        path = filedialog.askopenfilename(
            title="Seleccionar CSV de RFCs",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        if path:
            self.batch_csv_path = path
            self.lbl_csv_path.config(text=os.path.basename(path), foreground="black")
            self.btn_batch_query.config(state=tk.NORMAL)

    def _run_batch_query_threaded(self):
        if self.is_running:
            messagebox.showwarning("En progreso", "Espera a que termine la tarea actual.")
            return
        if not self.batch_csv_path:
            return

        self.is_running = True
        self.btn_batch_query.config(state=tk.DISABLED)
        self._clear_results()
        self._append_result(f"Procesando archivo: {self.batch_csv_path}\n...\n")

        def worker():
            try:
                resultados = consultar_desde_csv(Path(self.batch_csv_path))
                encontrados = [r for r in resultados if r.get("encontrado")]
                
                summary = f"\n--- RESUMEN ---\nTotal consultados: {len(resultados)}\nCoincidencias en lista 69-B: {len(encontrados)}\n\n"
                self.root.after(0, lambda: self._append_result(summary))
                
                if encontrados:
                    header = "--- DETALLE DE COINCIDENCIAS ---\n"
                    self.root.after(0, lambda: self._append_result(header))
                    for r in encontrados:
                        line = f"[{r['rfc']}] {r.get('nombre', 'S/N')} | Sit: {r.get('situacion', '?')}\n"
                        self.root.after(0, lambda l=line: self._append_result(l))
                else:
                    self.root.after(0, lambda: self._append_result("No se encontraron coincidencias.\n"))

            except Exception as e:
                err = f"Error procesando CSV: {e}\n"
                self.root.after(0, lambda: self._append_result(err))
            finally:
                self.root.after(0, self._on_task_complete)

        threading.Thread(target=worker, daemon=True).start()

    # --- Helpers de UI ---

    def _on_task_complete(self):
        self.is_running = False
        self.btn_run_cycle.config(state=tk.NORMAL)
        self.btn_batch_query.config(state=tk.NORMAL if self.batch_csv_path else tk.DISABLED)
        self._update_status_labels()

    def _poll_log_queue(self):
        """Revisa la cola de logs cada 100ms y actualiza el widget."""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg + "\n")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _append_log(self, text: str):
        self.txt_logs.config(state=tk.NORMAL)
        self.txt_logs.insert(tk.END, text)
        self.txt_logs.see(tk.END)
        self.txt_logs.config(state=tk.DISABLED)

    def _clear_log(self):
        self.txt_logs.config(state=tk.NORMAL)
        self.txt_logs.delete(1.0, tk.END)
        self.txt_logs.config(state=tk.DISABLED)

    def _append_result(self, text: str):
        self.txt_results.config(state=tk.NORMAL)
        self.txt_results.insert(tk.END, text)
        self.txt_results.see(tk.END)
        self.txt_results.config(state=tk.DISABLED)

    def _clear_results(self):
        self.txt_results.config(state=tk.NORMAL)
        self.txt_results.delete(1.0, tk.END)
        self.txt_results.config(state=tk.DISABLED)

    def _format_checker_result(self, r: dict) -> str:
        """Formatea el diccionario de checker.py a texto legible."""
        if r["encontrado"]:
            sit = (r.get("situacion") or "DESCONOCIDA").upper()
            return (
                f"{'─'*40}\n"
                f"⚠️  ENCONTRADO EN LISTA 69-B\n"
                f"RFC      : {r['rfc']}\n"
                f"Situación: {sit}\n"
                f"Nombre   : {r.get('nombre') or 'N/D'}\n"
                f"Publicado: {r.get('fecha_primera_publicacion') or 'N/D'}\n"
                f"Oficio   : {r.get('numero_oficio') or 'N/D'}\n"
                f"{'─'*40}\n"
            )
        else:
            return (
                f"{'─'*40}\n"
                f"✅ NO ENCONTRADO\n"
                f"RFC: {r['rfc']} no aparece en el listado local.\n"
                f"{'─'*40}\n"
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = SatEfosTrackerUI(root)
    root.mainloop()