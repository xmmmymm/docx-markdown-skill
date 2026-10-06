# -*- coding: utf-8 -*-
"""probe_chars.py: 字符普查"""
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
stream = (BASE / "content_stream.txt").read_text(encoding="utf-8")
lines = stream.split("\n")

out = []
out.append("### A. 字母后紧跟 ASCII 数字 (疑似下标损坏)")
for i, ln in enumerate(lines):
    for m in re.finditer(r"[A-Za-z][A-Za-z]?\d+", ln):
        out.append("L%-4d %-12s | %s" % (i + 1, m.group(0),
                                         ln[max(0, m.start() - 12):m.end() + 8]))

out.append("")
out.append("### B. 全部非 ASCII 字符统计")
cnt = Counter(stream)
for ch, n in sorted(cnt.items(), key=lambda x: (-x[1], x[0])):
    if ord(ch) > 127:
        out.append("U+%04X %r x%d" % (ord(ch), ch, n))
(BASE / "char_probe.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
