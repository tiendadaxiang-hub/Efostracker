# 🇲🇽 Efostracker

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Fuente SAT](https://img.shields.io/badge/fuente-SAT%20México-red)](https://www.sat.gob.mx)
[![Art. 69-B CFF](https://img.shields.io/badge/Art.-69--B%20CFF-orange)](https://www.dof.gob.mx)
[![SQLite](https://img.shields.io/badge/database-SQLite-blue)](https://www.sqlite.org/)

Tracker automático, consultor offline y **radar de cumplimiento** del Listado de Contribuyentes Incumplidos (EFOS/EDOS) publicado por el SAT bajo el Art. 69-B del Código Fiscal de la Federación.

## 🚀 Características Principales

### Core (Backend)
- **Descarga inteligente**: HTTP con reintentos y verificación SHA-256
- **Detección de cambios**: Compara snapshots (NUEVO / CAMBIO / BAJA)
- **Consulta offline**: Índice local indexado por RFC
- **Notificaciones SMTP**: Reportes HTML automáticos
- **🆕 Base de datos SQLite**: Persistencia completa con historial
- **🆕 Radar de proveedores**: Watchlist persistente de RFCs monitoreados
- **🆕 Alertas críticas**: Notificación inmediata si un proveedor cae en lista negra

### Interfaces de Usuario (3 opciones)
1. **🆕 TUI Hacker (`ui/tui.py`)**: Terminal interactiva estilo Matrix con Textual
   - Navegación por teclado y mouse
   - Logs con colores semánticos
   - Barra de comandos integrada
2. **🆕 GUI Cyberpunk (`ui/gui.py`)**: Ventanas modernas con CustomTkinter
   - Tema oscuro con acentos neón
   - Dashboard visual completo
   - Ideal para uso diario en desktop
3. **Tkinter Clásico (`ui/launcher_ui.py`)**: UI MVP original
   - Simple y funcional
   - Compatibilidad total

### Herramientas
- **🆕 Empaquetado portable**: Genera `.exe` standalone con PyInstaller
- **🆕 Daemon Windows**: Instalación como tarea programada (sin ventana negra)
- **CLI tradicional**: Uso desde terminal para scripts y automatización

## 📂 Estructura del Proyecto

```
Efostracker/
├── core/           # Lógica de negocio (backend)
├── ui/             # Interfaces gráficas (3 opciones)
├── data/           # Datos locales (no subir a git)
├── logs/           # Registros de operación
├── tests/          # Pruebas unitarias
├── tools/          # Herramientas auxiliares
└── examples/       # Archivos de ejemplo
```

Ver [INSTALL.md](INSTALL.md) para detalles de instalación.

## ⚡ Inicio Rápido

### 1. Instalación
```bash
git clone https://github.com/TU_USUARIO/Efostracker.git
cd Efostracker
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configuración inicial
```bash
cp .env.example .env
# Editar .env con tus credenciales SMTP (opcional)
```

### 3. Primera ejecución
```bash
# Desde la raíz del proyecto
python -m core.scheduler --now
```

### 4. Lanzar interfaz gráfica
```bash
# Opción A: TUI Hacker (recomendada para power users)
python -m ui.tui

# Opción B: GUI Cyberpunk (recomendada para uso diario)
python -m ui.gui

# Opción C: Tkinter clásico
python -m ui.launcher_ui
```

## 🎯 Casos de Uso

### Caso 1: Monitoreo diario automático
```bash
# Instalar como daemon de Windows (desde la UI)
# O ejecutar manualmente
python -m core.scheduler
```
El sistema descargará el listado diariamente a las 06:00 y enviará correo si hay cambios.

### Caso 2: Due Diligence de proveedores
1. Agregar RFCs de proveedores al **Radar** (watchlist) desde la UI
2. El sistema monitorea persistentemente esos RFCs
3. Si alguno aparece en el listado 69-B, recibirás alerta inmediata
4. Los RFCs persisten aunque cierres la aplicación

### Caso 3: Consulta masiva
```bash
python -m core.checker --csv proveedores.csv --col rfc
```

### Caso 4: Generar ejecutable portable
```bash
python tools/crear_portable.py
# Genera: SAT_EFOS_Tracker_Portable.zip
```

## 🗄️ Arquitectura de Datos

### Base de Datos SQLite (`efos_tracker.db`)

**Tablas principales:**

| Tabla | Propósito |
|-------|-----------|
| `watchlist` | RFCs monitoreados (proveedores, socios, clientes) |
| `sat_snapshots` | Historial de descargas del SAT |
| `sat_registros` | Listado completo 69-B con historial |

**Ventajas sobre el sistema anterior (solo CSV):**
- ✅ Historial completo: puedes ver cuándo un RFC entró/salió de la lista
- ✅ Consultas complejas: filtrar por situación, fecha, etc.
- ✅ Persistencia robusta: transacciones atómicas
- ✅ Multi-usuario: varias UIs pueden acceder simultáneamente
- ✅ Portable: un solo archivo `.db` viaja con tu proyecto

## 🖥️ Interfaces de Usuario

### TUI Hacker (`ui/tui.py`)
Interfaz de terminal interactiva con estética cyberpunk.

**Características:**
- Navegación completa con teclado y mouse
- Logs en tiempo real con colores semánticos
- Barra de comandos (presiona `/` para enfocar)
- 6 vistas: Estado, Consulta, Watchlist, Config, Daemon, BD

**Comandos disponibles:**
```
help              - Mostrar ayuda
check RFC123      - Consultar RFC individual
run               - Ejecutar ciclo completo
status            - Ver estado del sistema
watchlist         - Ver RFCs en radar
alertas           - Ver alertas críticas
```

### GUI Cyberpunk (`ui/gui.py`)
Interfaz gráfica moderna con tema oscuro.

**Características:**
- Sidebar de navegación
- Dashboard visual con métricas
- Tablas interactivas (Treeview)
- Logs con colores
- Compatible con mouse y teclado

## 🔌 Daemon Windows (Tarea Programada)

Desde cualquier UI puedes instalar el tracker como tarea programada de Windows:

```powershell
# Instalación manual (requiere admin)
schtasks /Create /TN "EfosTracker_Daemon" /TR "pyw.exe C:\ruta\scheduler.py" /SC ONLOGON /RL HIGHEST

# Ejecutar inmediatamente
schtasks /Run /TN "EfosTracker_Daemon"

# Eliminar
schtasks /Delete /TN "EfosTracker_Daemon" /F
```

**Ventajas:**
- ✅ Sin ventana negra (`pyw.exe`)
- ✅ Inicio automático al iniciar sesión
- ✅ Permisos elevados para operaciones completas
- ✅ Totalmente invisible para el usuario

## 📦 Empaquetado Portable

Genera un ejecutable standalone que funciona en cualquier PC con Windows:

```bash
python tools/crear_portable.py
```

**Genera:**
- `SAT_EFOS_Tracker.exe` (ejecutable principal)
- `data/` (estructura de carpetas)
- `logs/` (estructura de carpetas)
- `.env` (tu configuración)
- `SAT_EFOS_Tracker_Portable.zip` (paquete completo)

**Uso:**
1. Descomprimir el ZIP en cualquier PC con Windows
2. Ejecutar `SAT_EFOS_Tracker.exe`
3. No requiere Python instalado

## 🧪 Pruebas Unitarias

```bash
# Con pytest
python -m pytest tests/ -v
```

## 📊 Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `EFOS_SCHEDULE_TIME` | `06:00` | Hora de descarga diaria (HH:MM) |
| `EFOS_RUN_ON_START` | `true` | Ejecutar ciclo al iniciar |
| `EFOS_NOTIFY_ON_NEW` | `true` | Enviar correo si hay cambios |
| `EFOS_SMTP_HOST` | — | Servidor SMTP (ej: `smtp.gmail.com`) |
| `EFOS_SMTP_PORT` | `587` | Puerto SMTP (STARTTLS) |
| `EFOS_SMTP_USER` | — | Usuario SMTP |
| `EFOS_SMTP_PASS` | — | Contraseña SMTP / App Password |
| `EFOS_NOTIFY_FROM` | — | Dirección remitente |
| `EFOS_NOTIFY_TO` | — | Destinatarios (separados por coma) |

## ⚖️ Aviso Legal

Este repositorio descarga y procesa datos públicos del SAT para facilitar la consulta operativa. **No sustituye la consulta directa al portal oficial del SAT.** Ante cualquier discrepancia, prevalece siempre la información publicada por el SAT en su portal y en el DOF. El uso de esta herramienta no exime al contribuyente de sus obligaciones fiscales ni constituye asesoría legal o fiscal.

## 🤝 Autor y Licencia

**Desarrollado por**: Paimon... {completar después}  
**Especialidad**: Derecho fiscal, tributario y penal  
**Investigación**: IA, Administraciones Tributarias y Derechos Humanos

**Licencia**: MIT — libre para usar, modificar y distribuir citando al autor.