"""
crear_portable.py — Generador de paquete portable para sat-efos-tracker
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Configuración
PROJECT_NAME = "SAT_EFOS_Tracker"
BUILD_DIR = Path("build")
DIST_DIR = Path("dist")
OUTPUT_ZIP = f"{PROJECT_NAME}_Portable.zip"

def clean_up():
    print("🧹 Limpiando carpetas anteriores...")
    for folder in [BUILD_DIR, DIST_DIR]:
        if folder.exists():
            shutil.rmtree(folder)

def build_exe():
    print("🔨 Compilando ejecutable...")
    
    # Usamos sys.executable para asegurar que usamos el Python activo
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", PROJECT_NAME,
        # En Windows el separador para add-data es ;
        "--add-data", "core/config.py;core",
        "--add-data", "core/downloader.py;core",
        "--add-data", "core/parser.py;core",
        "--add-data", "core/differ.py;core",
        "--add-data", "core/checker.py;core",
        "--add-data", "core/notifier.py;core",
        "--add-data", "core/scheduler.py;core",
        "--add-data", "core/database.py;core",
        "--add-data", "core/watchlist.py;core",
        "--hidden-import", "requests",
        "--hidden-import", "schedule",
        "--hidden-import", "tkinter",
        "--hidden-import", "core.config",
        "ui/launcher_ui.py"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Compilación exitosa.")
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Error en compilación:")
        print(e.stderr)
        return False

def create_distribution():
    print("📦 Empaquetando archivos...")
    final_folder = DIST_DIR / "SAT_EFOS_Portable"
    if final_folder.exists():
        shutil.rmtree(final_folder)
    final_folder.mkdir(parents=True)

    # 1. Copiar EXE
    exe_source = DIST_DIR / f"{PROJECT_NAME}.exe"
    if not exe_source.exists():
        print(f"❌ No se encontró {exe_source}")
        return None
    shutil.copy(exe_source, final_folder)

    # 2. Crear estructura de carpetas vacías
    (final_folder / "data" / "raw").mkdir(parents=True)
    (final_folder / "data" / "processed").mkdir(parents=True)
    (final_folder / "logs").mkdir(parents=True)

    # 3. Copiar archivos de configuración y CSV
    files_to_copy = [".env", "mis_35_rfcs.csv"]
    for file_name in files_to_copy:
        if Path(file_name).exists():
            shutil.copy(file_name, final_folder)
            print(f"   📄 Incluido: {file_name}")

    return final_folder

def create_zip(folder_path):
    print(f"🗜️  Creando ZIP: {OUTPUT_ZIP}...")
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DIST_DIR)
                zipf.write(file_path, arcname)
    print(f"✅ ¡LISTO! Busca el archivo {OUTPUT_ZIP} en tu carpeta.")

if __name__ == "__main__":
    print("--- Iniciando generador portable ---")
    clean_up()
    if build_exe():
        dist_folder = create_distribution()
        if dist_folder:
            create_zip(dist_folder)
    else:
        print("⚠️ El proceso se detuvo debido a errores en la compilación.")