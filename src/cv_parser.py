import os
from pypdf import PdfReader


def load_cv_text(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"CV not found at {path}. Put your CV PDF there or update config.yaml."
        )
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(parts).strip()
    if len(text) < 100:
        raise ValueError("CV text looks empty or unreadable. Is the PDF a scanned image?")
    return text
