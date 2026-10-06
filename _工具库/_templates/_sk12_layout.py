# -*- coding: utf-8 -*-
"""Item12: page layout probe - image bboxes + nearest text lines (to locate floating objects)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _sk93_target as T

W = T.work()
PDF = os.path.join(W, "pdf")
pdf = [p for p in os.listdir(PDF) if p.lower().endswith(".pdf")][0]
import pymupdf

doc = pymupdf.open(os.path.join(PDF, pdf))
for i in range(doc.page_count):
    pg = doc.load_page(i)
    H = pg.rect.height
    print("=== page %d h=%.0f ===" % (i + 1, H))
    words = pg.get_text("words")
    for im in pg.get_image_info(xrefs=True):
        x0, y0, x1, y1 = im["bbox"]
        print("IMG bbox=(%.0f,%.0f,%.0f,%.0f) w=%.0f h=%.0f" % (x0, y0, x1, y1, x1 - x0, y1 - y0))
        # nearest words: same row (vertical overlap) and within +/-40pt
        near = []
        for w in words:
            wx0, wy0, wx1, wy1, wt = w[0], w[1], w[2], w[3], w[4]
            if wy1 > y0 - 12 and wy0 < y1 + 12 and wx1 > x0 - 60 and wx0 < x1 + 60:
                near.append((round(wy0), round(wx0), wt))
        near.sort()
        print("   near_text=%s" % " | ".join(t for _, _, t in near[:24]))
print("done")
