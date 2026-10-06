# -*- coding: utf-8 -*-
"""probe_hf.py: 打印页眉/页脚文本, 确认无正文内容"""
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
out = []
for fn in ["header1.xml", "footer1.xml"]:
    p = BASE / "unpacked/word" / fn
    if not p.exists():
        out.append("%s: (missing)" % fn)
        continue
    root = ET.parse(p).getroot()
    out.append("== %s" % fn)
    for para in root.iter(W + "p"):
        txt = "".join(t.text or "" for t in para.iter(W + "t"))
        out.append("   %r" % txt)
(BASE / "hf_probe.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
