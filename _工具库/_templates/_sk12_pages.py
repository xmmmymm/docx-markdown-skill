# -*- coding: utf-8 -*-
"""Item12: docx -> pdf -> page PNGs (for locating floating MathType objects). ASCII only stdout."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _sk93_target as T

OUT = T.out()
W = os.path.join(OUT, "work")
PDF = os.path.join(W, "pdf")
PNG = os.path.join(W, "pages")
os.makedirs(PDF, exist_ok=True)
os.makedirs(PNG, exist_ok=True)

SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.exe"
if not os.path.exists(SOFFICE):
    SOFFICE = r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"

docx = T.docx()
r = subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", PDF, docx],
                   capture_output=True, timeout=300)
print("soffice_exit=%d" % r.returncode)
pdfs = [p for p in os.listdir(PDF) if p.lower().endswith(".pdf")]
print("pdf=%s" % pdfs)

try:
    import fitz
except Exception as e:
    print("NO_PYMUPDF %s" % type(e).__name__)
    sys.exit(0)

for p in pdfs:
    doc = fitz.open(os.path.join(PDF, p))
    for i in range(doc.page_count):
        pg = doc.load_page(i)
        pix = pg.get_pixmap(dpi=300)
        dst = os.path.join(PNG, "%s_p%d.png" % (os.path.splitext(p)[0][:12], i + 1))
        pix.save(dst)
    print("pages=%d from %s" % (doc.page_count, p))
print("done=%d" % len([f for f in os.listdir(PNG) if f.endswith(".png")]))
