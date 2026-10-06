# -*- coding: utf-8 -*-
"""probe_tree.py: 打印含指定文本的段落的元素树(标签+文本), 查看 mc:AlternateContent/textbox 结构"""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
root = ET.parse(BASE / "unpacked/word/document.xml").getroot()
body = root.find(W + "body")

def short(t):
    return t.replace("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}", "w:") \
            .replace("{http://schemas.openxmlformats.org/markup-compatibility/2006}", "mc:") \
            .replace("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}", "wp:") \
            .replace("{http://schemas.openxmlformats.org/drawingml/2006/main}", "a:") \
            .replace("{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}", "wps:") \
            .replace("{urn:schemas-microsoft-com:vml}", "v:")

kw = sys.argv[1]
LOG = []
for p in body.iter(W + "p"):
    xml = ET.tostring(p, encoding="unicode")
    if kw not in xml:
        continue
    LOG.append("=" * 40)
    def rec(el, d=0):
        tag = short(el.tag)
        txt = el.text if el.tag != W + "t" else None
        if tag == "w:t":
            LOG.append("  " * d + "w:t %r" % (el.text or ""))
            return
        if tag in ("w:instrText",):
            LOG.append("  " * d + "%s %r" % (tag, el.text or ""))
            return
        LOG.append("  " * d + tag)
        for ch in el:
            rec(ch, d + 1)
    rec(p)
(BASE / "tree_probe.txt").write_text("\n".join(LOG), encoding="utf-8")
print("ok, matches:", sum(1 for x in LOG if x.startswith("====")))
