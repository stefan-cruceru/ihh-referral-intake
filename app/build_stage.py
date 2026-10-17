"""Build-time staging for the exe: the icon and the version resource.

Everything goes to app/build/stage (gitignored). Run by build.ps1 before PyInstaller.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parent
STAGE = APP / "build" / "stage"
sys.path.insert(0, str(APP))

from carebridge import __version__  # noqa: E402


def icon(path: Path):
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, fill=(31, 111, 120, 255))
    w = 22
    d.arc([40, 96, size - 40, 300], start=200, end=340, fill="white", width=w)
    for x, top in ((72, 170), (128, 140), (184, 170)):
        d.line([x, top, x, 210], fill="white", width=w)
    img.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def version_file(path: Path):
    parts = [int(p) for p in __version__.split(".")] + [0]
    t = tuple(parts[:4])
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Community build for Illumination Health + Home'),
      StringStruct('FileDescription', 'IHH Care Bridge'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'ihh-care-bridge'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'ihh-care-bridge.exe'),
      StringStruct('ProductName', 'IHH Care Bridge'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")


if __name__ == "__main__":
    STAGE.mkdir(parents=True, exist_ok=True)
    icon(STAGE / "carebridge.ico")
    version_file(STAGE / "version.txt")
    print("staged in", STAGE)
