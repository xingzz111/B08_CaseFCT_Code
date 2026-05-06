# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

py_files = ['..\\main.py']

add_files = [
    ('..\\gui\\img\\*.png', 'img'),
]

binaries = []
datas = []
hiddenimports = []

# Ensure Qt/PySide6 runtime libraries and plugins are bundled.
binaries += collect_dynamic_libs('PySide6')
binaries += collect_dynamic_libs('shiboken6')
datas += collect_data_files('PySide6')
hiddenimports += collect_submodules('PySide6')

# Ensure pyzmq ships its native libs (.pyd/.dll) + hidden imports.
binaries += collect_dynamic_libs('zmq')
datas += collect_data_files('zmq')
hiddenimports += collect_submodules('zmq')

a = Analysis(py_files,
             pathex=[],
             binaries=binaries,
             datas=add_files + datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OSENSTester',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=['..\\gui\\img\\ossns_icon.ico']
)
