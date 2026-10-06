# -*- coding: utf-8 -*-
"""inspect_xml.py: 按关键词打印 document.xml 上下文(repr), 用于判定脚本占位是否符合源文"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
xml = (BASE / "unpacked/word/document.xml").read_text(encoding="utf-8")

LOG = []
for kw in sys.argv[1:]:
    LOG.append("=" * 20 + " " + kw)
    start = 0
    n = 0
    while True:
        i = xml.find(kw, start)
        if i < 0:
            break
        n += 1
        LOG.append("--- hit %d at %d ---" % (n, i))
        LOG.append(repr(xml[max(0, i - 900): i + 900]))
        start = i + 1
    if n == 0:
        LOG.append("(not found)")
(BASE / "xml_probe_out.txt").write_text("\n".join(LOG), encoding="utf-8")
print("written")
