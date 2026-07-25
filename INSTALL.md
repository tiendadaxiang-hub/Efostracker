# 📥 Guía de Instalación — Efostracker

## Requisitos Previos

- **Python 3.9 o superior** ([descargar](https://www.python.org/downloads/))
- **Git** (opcional, para clonar el repositorio)
- **Windows 10/11** (para daemon y empaquetado portable)

## Instalación Paso a Paso

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/Efostracker.git
cd Efostracker
```

**O descargar ZIP:**
1. Ir a la página del repositorio
2. Click en "Code" → "Download ZIP"
3. Descomprimir en tu carpeta de proyectos

### 2. Crear entorno virtual

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Deberías ver `(.venv)` al inicio de tu prompt.

### 3. Instalar dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Dependencias adicionales para UIs:**
```bash
# Para TUI Hacker
pip install textual rich

# Para GUI Cyberpunk
pip install customtkinter

# Para empaquetado portable
pip install pyinstaller
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tu editor preferido:

```ini
# Configuración básica
EFOS_SCHEDULE_TIME=06:00
EFOS_RUN_ON_START=true
EFOS_NOTIFY_ON_NEW=true

# Configuración SMTP (opcional)
EFOS_SMTP_HOST=smtp.gmail.com
EFOS_SMTP_PORT=587
EFOS_SMTP_USER=tu_correo@gmail.com
EFOS_SMTP_PASS=tu_contraseña_de_aplicacion
EFOS_NOTIFY_FROM=tu_correo@gmail.com
EFOS_NOTIFY_TO=admin@empresa.com, contador@empresa.com
```

**⚠️ Importante para Gmail:**
- Usa una **Contraseña de Aplicación** (no tu contraseña normal)
- Genera una en: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- Requiere verificación en 2 pasos activada

### 5. Primera ejecución

```bash
python -m core.scheduler --now
```

Esto:
1. Descarga el listado completo del SAT (~14,000 RFCs)
2. Crea la base de datos SQLite
3. Genera el primer snapshot
4. Crea las carpetas `data/` y `logs/`

**Tiempo estimado:** 30-60 segundos (dependiendo de tu conexión)

### 6. Lanzar interfaz gráfica

**Opción A: TUI Hacker (recomendada)**
```bash
python -m ui.tui
```

**Opción B: GUI Cyberpunk**
```bash
python -m ui.gui
```

**Opción C: Tkinter clásico**
```bash
python -m ui.launcher_ui
```

## Verificación de Instalación

### Test 1: Consulta de RFC
```bash
python -m core.checker AAA010101AAA
```
Debería mostrar si el RFC está en la lista o no.

### Test 2: Pruebas unitarias
```bash
python -m pytest tests/ -v
```
Deberían pasar los 22 tests.

### Test 3: Estado del sistema
```bash
python -m core.scheduler --status
```
Debería mostrar el resumen del último diff.

## Solución de Problemas Comunes

### ❌ "ModuleNotFoundError: No module named 'requests'"
**Solución:**
```bash
pip install -r requirements.txt
```

### ❌ "Permission denied" al crear carpetas
**Solución:** Ejecuta como administrador o verifica permisos de la carpeta.

### ❌ Error de SMTP al enviar correo
**Soluciones:**
1. Verifica que usas **Contraseña de Aplicación** (no contraseña normal)
2. Confirma que el puerto es correcto (587 para STARTTLS, 465 para SSL)
3. Prueba con la función "Enviar Prueba" desde la UI

### ❌ "No hay listado procesado disponible"
**Solución:**
```bash
python -m core.scheduler --now
```

### ❌ Daemon de Windows no se instala
**Solución:**
1. Abre PowerShell como **Administrador**
2. Ejecuta el comando `schtasks` manualmente
3. Confirma el prompt UAC

### ❌ TUI no muestra colores
**Solución:**
- Windows Terminal: funciona nativamente
- CMD antiguo: actualiza a Windows Terminal
- PowerShell: funciona nativamente

## Estructura de Archivos Creados

Después de la instalación tendrás:

```
Efostracker/
├── .venv/                    # Entorno virtual (no subir a git)
├── .env                      # Tu configuración local (no subir a git)
├── data/
│   ├── raw/
│   │   └── listado_69b_raw_*.csv
│   ├── processed/
│   │   ├── listado_69b_*.csv
│   │   └── listado_69b_latest.csv
│   └── efos_tracker.db       # Base de datos SQLite
├── logs/
│   ├── tracker.log
│   └── diff_*.json
└── [resto de archivos del proyecto]
```

## Siguientes Pasos

1. **Configurar SMTP** (opcional) para recibir notificaciones
2. **Agregar RFCs** a tu Radar (watchlist) desde la UI
3. **Instalar daemon** para monitoreo automático
4. **Explorar las 3 interfaces** y elegir tu favorita

## Soporte

- **Issues**: [github.com/TU_USUARIO/Efostracker/issues](https://github.com/TU_USUARIO/Efostracker/issues)
- **Documentación**: Ver [README.md](README.md)
- **Tests**: `python -m pytest tests/ -v`