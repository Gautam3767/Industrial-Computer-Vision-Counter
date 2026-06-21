# PyInstaller spec — build a double-clickable desktop binary (Roadmap Phase 8).
#
#   pip install -r requirements-dev.txt
#   pyinstaller CVObjectCounter.spec
#
# Output: dist/CVObjectCounter (.app on macOS, .exe folder on Windows).
# Model weights are intentionally NOT bundled — run download_models.py, or let
# Ultralytics fetch them on first use, alongside the binary.

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("conveyor_tracker.yaml", "."),
    ],
    hiddenimports=[
        "pyqtgraph",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CVObjectCounter",
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="CVObjectCounter",
)

app = BUNDLE(
    coll,
    name="CVObjectCounter.app",
    bundle_identifier="ai.avitri.cvobjectcounter",
)
