import re
from PyPDF2 import PdfReader

_ws = re.compile(r"\s+")
def clean_text(s: str) -> str:
    if not s:
        return ""
    return _ws.sub(" ", s).strip()

def load_pdf_pages(pdf_path):
    reader = PdfReader(str(pdf_path))
    pages = []
    for p in reader.pages:
        txt = p.extract_text() or ""
        pages.append(clean_text(txt))
    return pages