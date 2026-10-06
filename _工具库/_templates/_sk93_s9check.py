# -*- coding: utf-8 -*-
"""S9 zero-cost self-check + independent balance recompute (U56/U63/U91).
Chinese paths only appear as UTF-8 string constants read from _target.txt."""
import io
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sk93_target as T

PY = __import__("sys").executable
OUT = T.out()
STEM = T.stem()
MD = os.path.join(OUT, STEM + ".md")
WORK = os.path.join(OUT, "work")
IMG = os.path.join(OUT, "images")
LOG = os.path.join(WORK, "_sk93_s9_log.txt")

out = []


def p(s):
    out.append(s)


txt = io.open(MD, encoding="utf-8").read()
lines = txt.split("\n")
p("md_chars=%d md_lines=%d" % (len(txt), len(lines)))

pol = []
for r, _, fs in os.walk(WORK):
    for f in fs:
        if f.startswith("zoom_") and not f.endswith(".py"):
            pol.append(f)
        if f.startswith("_tmp") or f.startswith("_app"):
            pol.append(f)
        if f.endswith("_profile.txt") or f.endswith("_crop.png"):
            pol.append(f)
p("POLLUTION=%d %s" % (len(pol), pol[:8]))

imgs = sorted(os.listdir(IMG)) if os.path.isdir(IMG) else []
p("images=%d %s" % (len(imgs), imgs))
refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", txt)
p("md_img_refs=%d unique=%d" % (len(refs), len(set(refs))))
p("tu_kuai=%d" % len(re.findall(r"〔图：", txt)))
p("blockquote_lines=%d" % sum(1 for L in lines if L.startswith(">")))
p("bare_option_lines=%d" % len([i for i, L in enumerate(lines) if re.match(r"^[A-E][．.]\s", L)]))
p("qnum_caret=%d ans_tags=%d" % (len(re.findall(r"^\d+[．、]", txt, re.M)),
                                 len(re.findall(r"【答案】", txt))))

# U94 改判两查：figure_desc 逐图名计次 + 脚本/skeleton/md 的 mtime 链
fd = os.path.join(WORK, "figure_desc.md")
if os.path.exists(fd):
    fdtxt = io.open(fd, encoding="utf-8").read()
    dup = sorted({n for n in re.findall(r"(image\d+\.\w+)", fdtxt)
                  if len(re.findall(re.escape(n), fdtxt)) > 1})
    p("figure_desc_dup_names=%d %s" % (len(dup), dup[:8]))
for a, b in (("make_skeleton.py", "skeleton.txt"), ("figure_desc.md", STEM + ".md")):
    pa, pb = os.path.join(WORK, a), os.path.join(OUT, b)
    if os.path.exists(pa) and os.path.exists(pb):
        p("mtime_newer=%s>%s:%s" % (a, b, os.path.getmtime(pa) > os.path.getmtime(pb)))

ar = io.open(os.path.join(WORK, "audit_report.txt"), encoding="utf-8").read().split("\n")
p("audit_l1=%s" % ar[0])

r = subprocess.run([PY, T.tool("_sk_balance.py"), MD], capture_output=True)
p("balance_exit=%d" % r.returncode)
bo = os.path.join(WORK, "_sk_balance_out.txt")
if os.path.isfile(bo):
    p("balance_out_head=" + io.open(bo, encoding="utf-8").read()[:400].replace("\n", " | "))
p("balance_stdout=" + " ; ".join(r.stdout.decode("utf-8", "replace").strip().split("\n")[-3:]))

io.open(LOG, "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out).encode("ascii", "replace").decode())
