# -*- coding: utf-8 -*-
"""probe_numpr.py: 逐段核验含 <w:numPr> 的段落（numId/ilvl/文本），判定是否可启用 NUM_AUTO_NUMBER（U48）。

输出 probe_numpr.txt（UTF-8）+ 终端 ASCII 摘要。
"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
doc = (BASE / "unpacked/word/document.xml").read_text(encoding="utf-8")

paras = re.findall(r"<w:p\b.*?</w:p>", doc, flags=re.S)
out = []
cnt = 0
numid_hist = {}
for i, p in enumerate(paras):
    if "<w:numPr>" not in p and "<w:numPr " not in p:
        continue
    cnt += 1
    mid = re.search(r"<w:numId w:val=\"(\d+)\"", p)
    ilvl = re.search(r"<w:ilvl w:val=\"(\d+)\"", p)
    mid = mid.group(1) if mid else "-"
    ilvl = ilvl.group(1) if ilvl else "-"
    numid_hist[mid] = numid_hist.get(mid, 0) + 1
    txt = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
    mtxt = "".join(re.findall(r"<m:t[^>]*>([^<]*)</m:t>", p))
    out.append("P%-4d numId=%-3s ilvl=%-2s | %s%s" % (
        i + 1, mid, ilvl, txt[:70], (" [M:" + mtxt[:40] + "]") if mtxt else ""))

out.insert(0, "### numPr 段落总数 = %d ；numId 分布 = %s" % (cnt, numid_hist))
(BASE / "probe_numpr.txt").write_text("\n".join(out), encoding="utf-8")
print("numPr paras=%d numId=%s" % (cnt, numid_hist))
print("written probe_numpr.txt")
