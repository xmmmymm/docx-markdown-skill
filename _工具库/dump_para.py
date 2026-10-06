# -*- coding: utf-8 -*-
"""dump_para.py: 按段落序号 dump 子元素序列(紧凑), 用于核对域/EQ/上下标构造"""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
root = ET.parse(BASE / "unpacked/word/document.xml").getroot()
body = root.find(W + "body")
paras = list(body.iter(W + "p"))

def short(tag):
    return tag.replace(W, "w:")

LOG = []
for idx in sys.argv[1:]:
    i = int(idx)
    p = paras[i]
    LOG.append("=" * 30 + " P%d" % i)
    for r in p.iter(W + "r"):
        vert = ""
        rpr = r.find(W + "rPr")
        if rpr is not None:
            va = rpr.find(W + "vertAlign")
            if va is not None:
                vert = "[%s]" % va.get(W + "val")
        items = []
        for ch in r:
            t = short(ch.tag)
            if t == "w:t":
                items.append("t=%r" % (ch.text or ""))
            elif t == "w:instrText":
                items.append("INSTR=%r" % (ch.text or ""))
            elif t == "w:fldChar":
                items.append("FLD:%s" % ch.get(W + "fldCharType"))
            elif t == "w:tab":
                items.append("TAB")
            elif t == "w:object":
                items.append("OBJECT")
            elif t == "w:drawing":
                items.append("DRAWING")
            elif t == "w:pict":
                items.append("PICT")
            elif t == "w:rPr":
                pass
            else:
                items.append(t)
        if items:
            LOG.append("  R%s %s" % (vert, " ".join(items)))
(BASE / "para_dump.txt").write_text("\n".join(LOG), encoding="utf-8")
print("written; total paras", len(paras))
