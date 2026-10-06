# -*- coding: utf-8 -*-
"""probe_special.py: 探测 === / 下划线填空 / U+3000 / EQ域 / 第15题表首格"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
doc = (BASE / "unpacked/word/document.xml").read_text(encoding="utf-8")
out = []

# 1) EQ 域指令
instrs = re.findall(r"<w:instrText[^>]*>([^<]*)</w:instrText>", doc)
out.append("=== instrText (EQ fields) count=%d ===" % len(instrs))
seen = {}
for i in instrs:
    seen[i] = seen.get(i, 0) + 1
for k, v in seen.items():
    out.append("  x%d  %r" % (v, k))

# 2) 三个等号 "==="
out.append("=== '===' occurrences in document.xml: %d ===" % doc.count("==="))
for m in re.finditer(r"===", doc):
    s = max(0, m.start() - 400)
    out.append("  ...%s..." % doc[s:m.end()+120].replace("><", ">\n             <")[-700:])

# 3) 下划线字符 "_"
texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", doc)
und = [t for t in texts if "_" in t]
out.append("=== w:t containing '_' : %d ===" % len(und))
for t in und[:30]:
    out.append("  %r  (len=%d)" % (t, len(t)))

# 4) U+3000
u3000 = [t for t in texts if "\u3000" in t]
out.append("=== w:t containing U+3000 : %d ===" % len(u3000))
for t in u3000[:40]:
    out.append("  %r" % t)

# 5) 是否有 eq 相关的 fldSimple
flds = re.findall(r'<w:fldSimple[^>]*w:instr="([^"]*)"', doc)
out.append("=== fldSimple instrs ===")
for f in flds[:20]:
    out.append("  %r" % f)

(BASE / "probe_special.txt").write_text("\n".join(out), encoding="utf-8")
print("ok; instrText=%d, '==='=%d, _texts=%d, u3000=%d, fldSimple=%d" %
      (len(instrs), doc.count("==="), len(und), len(u3000), len(flds)))
