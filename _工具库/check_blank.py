# -*- coding: utf-8 -*-
"""check_blank.py: 像素级判定空白/装饰图(暗像素计数)"""
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
M = BASE / "unpacked/word/media"
# 【skill 版】默认遍历 media 全部位图；或命令行传文件名清单（ASCII 名，U93 安全）
if len(__import__("sys").argv) > 1:
    names = __import__("sys").argv[1:]
else:
    names = sorted(p.name for p in M.iterdir()
                   if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
out = []
for n in names:
    im = Image.open(M / n).convert("RGBA")
    px = im.load()
    w, h = im.size
    dark = 0
    alpha0 = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                alpha0 += 1
            elif (r + g + b) / 3 < 200:
                dark += 1
    out.append("%s %dx%d dark=%d alpha0=%d" % (n, w, h, dark, alpha0))
(BASE / "blank_check.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
