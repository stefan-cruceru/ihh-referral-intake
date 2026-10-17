# PyInstaller spec for ihh-care-bridge.exe. Run through build.ps1, which first renders the
# invented demo packets and the icon into build/stage.
# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

APP = Path(SPECPATH)
REPO = APP.parent
STAGE = APP / "build" / "stage"
CHALLENGE1 = REPO / "challenges" / "1-referral-intake"
CHALLENGE2 = REPO / "challenges" / "2-finding-the-right-resource"

datas = [
    (str(APP / "carebridge" / "web"), "web"),
    (str(CHALLENGE1 / "criteria" / "admission-criteria.json"), "data"),
    (str(CHALLENGE2 / "data" / "oc-resources.seed.json"), "data"),
    (str(CHALLENGE2 / "scenarios" / "client-scenarios.json"), "data"),
    (str(APP / "demo" / "inbox.json"), "data/demo"),
]
# fpdf2 (the client handout PDF) ships font metric files alongside its code.
from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files("fpdf")
datas += [(str(p), "data/demo") for p in sorted((STAGE / "demo").glob("D*.pdf"))]

icon = STAGE / "carebridge.ico"

a = Analysis(
    [str(APP / "run_carebridge.py")],
    pathex=[str(APP)],
    datas=datas,
    hiddenimports=[
        "demo", "demo.samples", "demo.packets",
        "keyring.backends.Windows", "win32ctypes.core", "win32ctypes.pywin32",
    ],
    excludes=["tkinter", "numpy", "matplotlib", "pandas", "scipy", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ihh-care-bridge",
    console=True,
    upx=False,
    icon=str(icon) if icon.exists() else None,
    version=str(STAGE / "version.txt") if (STAGE / "version.txt").exists() else None,
)
