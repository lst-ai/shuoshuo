# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包設定：產出 dist/ShuoShuo/ShuoShuo.exe（資料夾模式，啟動較快）
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

datas = [("assets/icon.ico", "assets"), ("assets/icon.png", "assets")]
datas += collect_data_files("faster_whisper")   # 內含 VAD 模型
datas += collect_data_files("opencc")           # 簡繁轉換字典
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")
hidden = collect_submodules("pynput") + collect_submodules("keyring.backends") + ["sounddevice", "_sounddevice_data"]
datas += collect_data_files("_sounddevice_data")

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "torch", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ShuoShuo",
    icon="assets/icon.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ShuoShuo", upx=False)
