"""
crear_portable_gui.py — Generador de paquete portable para la GUI de sat-efos-tracker
Este script:
1. Compila ui/gui.py en un único .exe usando PyInstaller.
2. Crea una carpeta de distribución con la estructura necesaria.
3. Copia el .exe, el .env y archivos de ejemplo.
4. Comprime todo en un archivo .zip listo para distribuir.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Configuración del proyecto
PROJECT_NAME = "EfosTracker_GUI"
BUILD_DIR = Path("build")
DIST_DIR = Path("dist")
OUTPUT_ZIP = f"{PROJECT_NAME}_Portable.zip"

def clean_up():
    """Limpia carpetas de compilación anteriores."""
    print("🧹 Limpiando carpetas de compilación anteriores...")
    for folder in [BUILD_DIR, DIST_DIR]:
        if folder.exists():
            shutil.rmtree(folder)

def build_exe():
    """Ejecuta PyInstaller para crear el ejecutable de la GUI."""
    print("🔨 Compilando ejecutable con PyInstaller...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",       # Sin ventana negra de consola
        "--name", PROJECT_NAME,
        "--add-data", f"core{os.pathsep}core",
        "--hidden-import", "requests",
        "--hidden-import", "schedule",
        "--hidden-import", "tkinter",
        "--hidden-import", "customtkinter",
        "--hidden-import", "sqlite3",
        "ui/gui.py"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Compilación exitosa.")
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Error durante la compilación:")
        print(e.stderr)
        return False

def create_distribution():
    """Prepara la carpeta final con la estructura necesaria."""
    print("📦 Preparando carpeta de distribución...")
    
    final_folder = DIST_DIR / "EfosTracker_Portable"
    if final_folder.exists():
        shutil.rmtree(final_folder)
    final_folder.mkdir(parents=True)

    # 1. Copiar EXE
    exe_source = DIST_DIR / f"{PROJECT_NAME}.exe"
    if not exe_source.exists():
        print(f"❌ No se encontró {exe_source}")
        return None
    shutil.copy(exe_source, final_folder)

    # 2. Crear estructura de datos vacía
    (final_folder / "data" / "raw").mkdir(parents=True)
    (final_folder / "data" / "processed").mkdir(parents=True)
    (final_folder / "logs").mkdir(parents=True)

    # 3. Copiar archivos de configuración y ejemplos
    files_to_copy = [".env", ".env.example", "examples/mis_35_rfcs.csv", "README.md", "INSTALL.md"]
    for file_name in files_to_copy:
        src = Path(file_name)
        if src.exists():
            shutil.copy(src, final_folder)
            print(f"   📄 Incluido: {file_name}")

    # 4. Crear LEEME.txt
    readme_content = """
    EfosTracker GUI - Versión Portable
    ===================================
    1. Ejecuta 'EfosTracker_GUI.exe'.
    2. Ve a la pestaña 'Configuración SMTP' para revisar tu correo.
    3. Usa 'Ejecutar Ciclo Ahora' para descargar los datos del SAT.
    4. Para consultar tus RFCs, ve a 'Watchlist (Radar)' o 'Consultar RFCs'.
    
    Nota: La primera vez tardará unos segundos en descargar el listado oficial.
    Los datos se guardan en la carpeta 'data' junto al ejecutable.
    """
    with open(final_folder / "LEEME.txt", "w", encoding="utf-8") as f:
        f.write(readme_content.strip())

    return final_folder

def create_zip(folder_path):
    """Comprime la carpeta de distribución en un ZIP."""
    print(f"🗜️  Creando archivo ZIP: {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DIST_DIR)
                zipf.write(file_path, arcname)
    print(f"✅ ¡LISTO! Tu paquete portable está en: {Path.cwd() / OUTPUT_ZIP}")

if __name__ == "__main__":
    print("--- Iniciando generador de paquete portable GUI ---")
    clean_up()
    if build_exe():
        dist_folder = create_distribution()
        if dist_folder:
            create_zip(dist_folder)
    else:
        print("⚠️ El proceso se detuvo debido a errores en la compilación.")
    print("--- Proceso finalizado ---")