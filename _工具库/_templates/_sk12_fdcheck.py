# -*- coding: utf-8 -*-
"""U120 图述预检：figure_desc.md 与成品 md 的禁用字符集扫描 + 逐图述 diff（必须 diff=0）。
Chinese paths only from _target.txt (U93). stdout ASCII."""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sk93_target as T

OUT = T.out()
STEM = T.stem()
WORK = os.path.join(OUT, "work")
MD = os.path.join(OUT, STEM + ".md")
FD = os.path.join(WORK, "figure_desc.md")
LOG = os.path.join(WORK, "_sk12_fdcheck.txt")

BAD = ["＝", "＋", "═", "•", "□", "\t", "⟨"]
out = []

fd_txt = io.open(FD, encoding="utf-8").read()
md_txt = io.open(MD, encoding="utf-8").read()

for label, txt in (("figure_desc.md", fd_txt), ("md", md_txt)):
    hits = {c: txt.count(c) for c in BAD}
    out.append("forbidden_%s=%s" % (label, {k: v for k, v in hits.items() if v}))

desc = {}
for ln in fd_txt.split("\n"):
    m = re.match(r"- (image\d+\.[A-Za-z]+)[^：]*：(.*)", ln.replace("**", ""))
    if m:
        desc[m.group(1)] = m.group(2).strip()

refs = re.findall(r"!\[\]\(images/([^)]+)\)〔图：([^〕]*)〕", md_txt)
diffs = []
for name, d in refs:
    if desc.get(name, "") != d.strip():
        diffs.append(name)
out.append("md_refs=%d fd_items=%d DIFF=%d %s" % (len(refs), len(desc), len(diffs), diffs))
unused = [n for n in desc if n not in [x[0] for x in refs]]
out.append("fd_not_referenced=%s" % unused)
out.append("VERDICT=%s" % ("OK" if not diffs else "DIFF"))

io.open(LOG, "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out).encode("ascii", "replace").decode())
