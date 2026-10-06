# -*- coding: utf-8 -*-
"""probe_fix2.py: 把 ⟨S⟩/⟨P⟩/⟨OLE⟩/⟨IMG⟩ 全部替换成哨兵后，再找**真正的** ASCII 下标损坏。

⚠ 易错点：若直接 `re.sub(r"⟨[^⟩]*⟩", "", s)` 会把正确的 `Na⟨S⟩2⟨/S⟩O` 变成 `Na2O`，
   制造大量**假阳性**（序0/序1 均踩过）。必须先屏蔽 ⟨S⟩…⟨/S⟩、⟨P⟩…⟨/P⟩ 整段，再屏蔽其余占位符。

用法：先跑 extract_content.py，再在 work/ 下运行本脚本 → probe_fix2.txt
然后把命中项按「先长后短」写入 normalize.STR_FIXES（NaHCO3/Na2CO3/BaCO3/BaCl2 → Na2O2 → Na2O → CO2 → O2）。
"""
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
s = (BASE / "content_stream.txt").read_text(encoding="utf-8")
t = re.sub(r"⟨S⟩.*?⟨/S⟩", "\x01", s)
t = re.sub(r"⟨P⟩.*?⟨/P⟩", "\x02", t)
t = re.sub(r"⟨[^⟩]*⟩", "\x03", t)

out = []
out.append("### 真正的 ASCII 下标损坏候选 (屏蔽正确上下标后)")
n = 0
for i, ln in enumerate(t.split("\n")):
    for m in re.finditer(r"[A-Za-z][a-z]?\d+", ln):
        n += 1
        out.append("  L%-4d %-8s | %s" % (i + 1, m.group(0), ln[max(0, m.start() - 20):m.end() + 16]))
out.append("  TOTAL=%d" % n)

out.append("")
out.append("### 原始(未屏蔽)流里 ASCII 字母+数字 的 token 计数(仅供对照)")
c = Counter(m.group(0) for m in re.finditer(r"[A-Za-z][a-z]?\d+", t))
for k, v in sorted(c.items(), key=lambda x: -x[1]):
    out.append("  %-8s x%d" % (k, v))

(BASE / "probe_fix2.txt").write_text("\n".join(out), encoding="utf-8")
print("ok total=%d" % n)
