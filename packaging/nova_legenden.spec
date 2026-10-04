# PyInstaller build description. Run from the project root:
#   pyinstaller packaging/nova_legenden.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root / "backend")],
    datas=[(str(root / "ui" / "dist"), "ui/dist"),
           (str(root / "backend" / "nova_legend" / "legend" / "template_texts.json"), "nova_legend/legend")]
          + collect_data_files("ezdxf"),
    hiddenimports=(collect_submodules("nova_legend") + collect_submodules("uvicorn")
                   + collect_submodules("ezdxf.addons.drawing") + ["ezdxf.addons.importer"]
                   + collect_submodules("python_multipart") + ["multipart", "webview"]),
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NOVA-Legenden",
    console=False,
    icon=str(root / "packaging" / "app.ico"),
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="NOVA-Legenden")
