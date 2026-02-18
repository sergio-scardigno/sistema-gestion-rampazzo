# -*- mode: python ; coding: utf-8 -*-
import importlib, os

_pyside6_path = os.path.dirname(importlib.import_module('PySide6').__file__)
_pyside6_plugins = os.path.join(_pyside6_path, 'plugins')

_extra_datas = [
    ('resources', 'resources'),
    ('anses_oficinas', 'anses_oficinas'),
]

# En Windows, incluir plugins de PySide6 explicitamente.
# En Linux/macOS los hooks de PyInstaller los resuelven automaticamente.
if os.path.isdir(_pyside6_plugins):
    _extra_datas.append((_pyside6_plugins, os.path.join('PySide6', 'plugins')))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=_extra_datas,
    hiddenimports=['build_info'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6', 'PyQt5.sip',
        'tkinter', '_tkinter',
        'IPython', 'jupyter', 'notebook', 'nbformat', 'nbconvert',
        'sphinx', 'docutils', 'babel',
        'black', 'yapf', 'pylint', 'astroid', 'isort',
        'pytest', 'pytest_cov', 'pytest_qt', 'pytest_mock',
        'jedi', 'parso',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SistemaRampazzo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SistemaRampazzo',
)
