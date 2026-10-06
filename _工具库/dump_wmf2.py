# -*- coding: utf-8 -*-
"""dump_wmf2.py: 判定"渲染为空白的小 WMF 到底画了什么"。

背景（序1 实测）：`image9.wmf` 经 LibreOffice 转 PNG 为**全白**，若只看渲染会误判为"空白图"。
真相：它是 MathType 生成的 WMF，正文内容以 **MathML 注释**形式写在文件里：
    <!-- MathType@Translator@5@5@MathML2 (Clipboard).tdl@MathML 2.0 (Clipboard)@ -->
    <math ...><mi>&#x7684;</mi></math>
→ `&#x7684;` = U+7684 = "的"。

本脚本做两件事：
  1) 抽取 WMF 内所有 MathML `&#x....;` / 可读 ASCII 串 → `wmf_mathml.txt`
  2) 把十六进制转储 + ASCII 侧写 → `wmf_hexdump.txt`（便于人工确认 MathType 生成的 CO₂/O₂ 等）
再用 `soffice --headless --convert-to png --outdir wmfpng *.wmf` 做视觉交叉验证。
"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
M = BASE / "unpacked/word/media"
names = [p.name for p in sorted(M.iterdir()) if p.suffix.lower() == ".wmf"]

o1, o2 = [], []
for n in names:
    w = (M / n).read_bytes()
    txt = w.decode("latin-1")
    ents = re.findall(r"&#x([0-9A-Fa-f]{4,6});", txt)
    o1.append("=== %s (%d bytes) ===" % (n, len(w)))
    if ents:
        chars = "".join(chr(int(e, 16)) for e in ents)
        o1.append("  MathML entities: %s  ->  %r" % (ents, chars))
    else:
        o1.append("  (no MathML entities)")
    o1.append("  placeable=%s  bounds/inch=%s" %
              (w[:4] == b"\xd7\xcd\xc6\x9a", w[6:18].hex()))
    o2.append("=== %s (%d) ===" % (n, len(w)))
    for i in range(0, len(w), 16):
        ch = w[i:i + 16]
        o2.append("%04d  %-47s  %s" % (i, " ".join("%02x" % b for b in ch),
                                       "".join(chr(b) if 32 <= b < 127 else "." for b in ch)))

(BASE / "wmf_mathml.txt").write_text("\n".join(o1), encoding="utf-8")
(BASE / "wmf_hexdump.txt").write_text("\n".join(o2), encoding="utf-8")
print("ok wmf=%d" % len(names))
