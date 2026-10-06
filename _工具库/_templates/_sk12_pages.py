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

# 逐个候选路径**都要**存在性校验：早期写法只校验 64 位路径，缺失时直接换成
# x86 路径却不复查 ⇒ 拿着不存在的 exe 去 subprocess.run（报错难定位）。
SOFFICE = None
for _c in (r"C:\Program Files\LibreOffice\program\soffice.exe",
           r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
    if os.path.exists(_c):
        SOFFICE = _c
        break
if not SOFFICE:
    print("NO_SOFFICE: LibreOffice not found (need soffice.exe)")
    raise SystemExit(2)

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
