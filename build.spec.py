# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['launcher_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.py', '.'),
        ('downloader.py', '.'),
        ('parser.py', '.'),
        ('differ.py', '.'),
        ('checker.py', '.'),
        ('notifier.py', '.'),
        ('scheduler.py', '.'),
    ],
    hiddenimports=[
        'requests',
        'schedule',
        'csv',
        'logging',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SAT_EFOS_Tracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # False para que no salga la ventana negra (modo GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Puedes poner 'icono.ico' si tienes uno
)