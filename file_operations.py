import os
import tempfile
from io import BytesIO
from pypdf import PdfWriter, PdfReader

def read_pdf_bytes(path: str) -> bytes:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PDF not found: {path}")

    with open(path, "rb") as fh:
        header = fh.read(5)
        if header != b"%PDF-":
            raise ValueError(f"File does not appear to be a PDF: {path}")
        fh.seek(0)
        return fh.read()

def save_pdf_bytes(data: bytes, path: str) -> None:
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

def strip_pdf_metadata(pdf_bytes: bytes) -> bytes:

    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.add_metadata({
        "/Author":       "",
        "/Creator":      "",
        "/Producer":     "",
        "/Subject":      "",
        "/Title":        "",
        "/Keywords":     "",
        "/CreationDate": "",
        "/ModDate":      "",
    })

    try:
        writer._root_object.pop("/Metadata", None) 
    except Exception:
        pass  # non-fatal exception
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()
