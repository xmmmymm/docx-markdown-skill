# -*- coding: utf-8 -*-
"""zoom_img.py: 局部放大 media 图，便于目验细节（导管长短等）"""
import sys
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
M = BASE / "unpacked/word/media"

# (文件名, 左, 上, 右, 下, 放大倍数) —— 【skill 版】按件填写；坐标为 0~1 相对值
# 用法示例：JOBS = [("image10.png", 0.80, 0.00, 1.00, 1.00, 4)]
JOBS = []
for name, l, t, r, b, z in JOBS:
    im = Image.open(M / name).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    im = bg.convert("RGB")
    w, h = im.size
    box = (int(w * l), int(h * t), int(w * r), int(h * b))
    c = im.crop(box)
    c = c.resize((c.size[0] * z, c.size[1] * z), Image.LANCZOS)
    q = BASE / ("imgview/zoom_%s_%d_%d.png" % (name, int(l * 100), int(r * 100)))
    c.save(q)
    print("saved", q.name, c.size)
