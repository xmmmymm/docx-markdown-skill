# -*- coding: utf-8 -*-
"""prep_images.py: 把所有 media 铺白底/放大后输出到 work/imgview/ 便于目验"""
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
SRC = BASE / "unpacked/word/media"
OUT = BASE / "imgview"
OUT.mkdir(exist_ok=True)

log = []
for p in sorted(SRC.iterdir(), key=lambda x: x.name):
    if p.suffix.lower() == ".wmf":
        continue
    im = Image.open(p)
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    out = bg.convert("RGB")
    scale = 1
    if max(out.size) < 400:
        scale = 3
        out = out.resize((out.size[0] * scale, out.size[1] * scale), Image.LANCZOS)
    q = OUT / ("%s_view.png" % p.stem)
    out.save(q)
    log.append("%s -> %s  (%dx%d, scale=%d, alpha=%s)" % (
        p.name, q.name, out.size[0], out.size[1], scale, im.mode))
(OUT / "prep_log.txt").write_text("\n".join(log), encoding="utf-8")
print("prepared", len(log))
