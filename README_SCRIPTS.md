# 📜 Referencia Técnica de Scripts — sat-efos-tracker

Este documento detalla el funcionamiento individual de cada módulo Python del proyecto. Está diseñado para desarrolladores o administradores que necesiten integrar estas funciones en otros sistemas o ejecutar tareas específicas desde la terminal.

## 🏗️ Arquitectura Modular

El proyecto sigue un flujo lineal de procesamiento de datos:
`Downloader` → `Parser` → `Differ` → `Notifier`

### 1. `config.py` — Configuración Central
No es ejecutable directamente. Define las constantes globales, rutas de archivos (`data/`, `logs/`) y variables de entorno.
*   **Variables clave:** `SAT_CSV_URL`, `COL_MAP` (mapeo de columnas del SAT), `SCHEDULE_TIME`.
*   **Uso:** Importado por todos los demás módulos para mantener la consistencia de rutas y parámetros.

### 2. `downloader.py` — Gestión de Descargas
Maneja la obtención del CSV oficial desde los servidores del SAT (Azure Blob Storage).
*   **Características:**
    *   Reintentos automáticos con backoff exponencial.
    *   Verificación de integridad vía SHA-256 para evitar procesar archivos idénticos.
*   **Funciones públicas:**
    *   `download_csv()`: Retorna la ruta del archivo descargado o `None` si falla.
    *   `get_latest_raw()`: Retorna la ruta del último archivo crudo disponible localmente.

### 3. `parser.py` — Normalización de Datos
Convierte el CSV "sucio" del SAT (encoding `windows-1250`, metadatos iniciales) en una estructura limpia y usable.
*   **Procesos:**
    *   Limpieza de RFCs (mayúsculas, sin espacios).
    *   Mapeo de situaciones fiscales (`presunto`, `definitivo`, etc.).
    *   Indexación por RFC para consultas rápidas ($O(1)$).
*   **Funciones públicas:**
    *   `parse_csv(ruta)`: Retorna lista de diccionarios normalizados.
    *   `registros_a_dict_rfc(lista)`: Crea un índice `{rfc: datos}`.
    *   `guardar_procesado(registros)`: Guarda el CSV limpio en `data/processed/`.

### 4. `differ.py` — Detección de Cambios
Compara dos snapshots (anterior vs. nuevo) para identificar movimientos en la lista.
*   **Clasificación:**
    *   `NUEVO`: RFC que aparece por primera vez.
    *   `CAMBIO`: RFC existente que cambió de situación fiscal.
    *   `BAJA`: RFC que fue retirado del listado.
*   **Funciones públicas:**
    *   `comparar(anterior, nuevo)`: Retorna un diccionario con las diferencias.
    *   `resumen_texto(diff)`: Genera un reporte legible en texto plano.
    *   `guardar_diff(diff)`: Persiste el resultado en `logs/diff_*.json`.

### 5. `checker.py` — Motor de Consultas
Permite verificar el estatus de contribuyentes contra la base de datos local.
*   **Modo CLI:**
    ```bash
    # Consulta individual
    python checker.py RFC123456789

    # Consulta masiva desde CSV
    python checker.py --csv proveedores.csv --col rfc
    ```
*   **Modo Módulo:**
    ```python
    from checker import consultar_rfc
    resultado = consultar_rfc("RFC123456789")
    print(resultado['situacion'])
    ```

### 6. `notifier.py` — Sistema de Alertas
Envía reportes por correo electrónico cuando se detectan cambios relevantes.
*   **Requisitos:** Variables de entorno SMTP configuradas en `.env`.
*   **Funciones públicas:**
    *   `enviar_reporte(diff)`: Envía el correo HTML si `NOTIFY_ON_NEW` es verdadero.

### 7. `scheduler.py` — Orquestador Principal
Coordina la ejecución de todo el pipeline.
*   **Argumentos de línea de comandos:**
    | Argumento | Descripción |
    | :--- | :--- |
    | `--now` | Ejecuta un ciclo completo inmediatamente y termina. |
    | `--status` | Muestra el resumen del último diff guardado en logs. |
    | *(ninguno)* | Inicia el modo Daemon (loop infinito programado). |

*   **Ejemplos de uso:**
    ```bash
    # Ejecución manual única
    python scheduler.py --now

    # Ver estado actual del sistema
    python scheduler.py --status
    ```

### 8. `launcher_ui.py` — Interfaz Gráfica (Tkinter)
Panel de control visual para usuarios no técnicos.
*   **Pestañas:**
    1.  **Estado:** Ejecución de ciclos y visualización de logs en tiempo real.
    2.  **Consulta:** Búsqueda individual o masiva de RFCs.
    3.  **Configuración:** Gestión de credenciales SMTP e instalación del Daemon de Windows.

## 🧪 Pruebas Unitarias (`test_core.py`)
Suite de 22 tests para validar la lógica de negocio sin depender de conexiones externas.
```bash
python -m pytest test_core.py -v