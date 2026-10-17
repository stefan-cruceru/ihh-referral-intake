"""Turn a faxed packet (PDF or images) into page images, in memory only."""

import io
from dataclasses import dataclass

from PIL import Image

LONG_EDGE = 1600  # px; enough to read handwriting on a 200 dpi fax without huge requests


@dataclass
class Page:
    number: int  # 1-based, as the coordinator sees it in the PDF
    image: Image.Image
    rotation: int = 0  # degrees clockwise needed to read it upright

    def jpeg(self, upright: bool = False, long_edge: int = LONG_EDGE, quality: int = 80) -> bytes:
        img = self.image
        if upright and self.rotation:
            img = img.rotate(-self.rotation, expand=True)
        scale = long_edge / max(img.size)
        if scale < 1:
            img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("L").save(buf, "JPEG", quality=quality)
        return buf.getvalue()


def load_packet(data: bytes, filename: str = "") -> list[Page]:
    name = filename.lower()
    if data[:5] == b"%PDF-" or name.endswith(".pdf"):
        return _from_pdf(data)
    return _from_image(data)


def _from_pdf(data: bytes) -> list[Page]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    pages = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            w, h = page.get_size()
            scale = min(LONG_EDGE / max(w, h), 200 / 72)
            pages.append(Page(i + 1, page.render(scale=scale).to_pil().convert("L")))
            page.close()
    finally:
        pdf.close()
    return pages


def _from_image(data: bytes) -> list[Page]:
    img = Image.open(io.BytesIO(data))
    pages = []
    i = 0
    while True:
        pages.append(Page(i + 1, img.convert("L").copy()))
        i += 1
        try:
            img.seek(i)  # multi-page TIFF, a common e-fax format
        except EOFError:
            break
    return pages
