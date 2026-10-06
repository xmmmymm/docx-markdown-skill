# -*- coding: utf-8 -*-
"""render_ole_fig.py: 非 MathType OLE（如 ACD/ChemSketch 双线桥图）的高质量渲染
- 输入: work/unpacked/word/media/<stem>.wmf  (OLE 的 v:imagedata 预览)
        -> soffice --headless --convert-to pdf --outdir work/wmfpdf <stem>.wmf
        （wmfpdf 目录须先存在；用法见 README「WMF→PNG/WMF→PDF」）
- 本脚本: PyMuPDF 高 DPI 栅格化 + 自动裁白 + 留边 -> work/olefig/<stem>.png
- 【skill 版·参数化】stem 由命令行第 1 参传入（ASCII 名，U93 安全）；
  多个 OLE 预览同图时渲染一次即可复用（U92）
"""
import sys
from pathlib import Path
import fitz
from PIL import Image, ImageChops

STEM = sys.argv[1] if len(sys.argv) > 1 else "image"
BASE = Path(__file__).resolve().parent
PDF = BASE / ("wmfpdf/%s.pdf" % STEM)
OUT = BASE / "olefig"
OUT.mkdir(exist_ok=True)

DPI = 600
doc = fitz.open(str(PDF))
page = doc[0]
pix = page.get_pixmap(dpi=DPI, alpha=False)
tmp = OUT / "_raw.png"
pix.save(str(tmp))
doc.close()

im = Image.open(tmp).convert("RGB")
# 自动裁白边
bg = Image.new("RGB", im.size, (255, 255, 255))
diff = ImageChops.difference(im, bg).convert("L")
bbox = diff.getbbox()
if bbox:
    im = im.crop(bbox)
# 四周留 6px 白边
pad = 6
out = Image.new("RGB", (im.size[0] + 2 * pad, im.size[1] + 2 * pad), (255, 255, 255))
out.paste(im, (pad, pad))
out.save(OUT / ("%s.png" % STEM))
tmp.unlink()
print("raw %s -> cropped %s" % ((pix.width, pix.height), out.size))
