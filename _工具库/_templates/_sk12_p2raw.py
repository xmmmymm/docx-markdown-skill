# -*- coding: utf-8 -*-
"""Item12: raw XML of paragraphs that contain AlternateContent / textboxes."""
import io
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _sk93_target as T

W = T.work()
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"}
root = ET.parse(os.path.join(W, "unpacked", "word", "document.xml")).getroot()
body = root.find("w:body", NS)
# top-level paragraphs only
toplevel = body.findall("w:p", NS)
print("toplevel=%d" % len(toplevel))
sel = []
for i, p in enumerate(toplevel):
    x = ET.tostring(p, encoding="unicode")
    if "AlternateContent" in x or "txbxContent" in x:
        sel.append(i)
print("with_altcontent_paras=%s" % sel)
lines = []
for i in sel:
    x = ET.tostring(toplevel[i], encoding="unicode")
    lines.append("==== top-level P%d ====" % i)
    lines.append(x.replace("><", ">\n<"))
lines.append("==== all txbxContent texts ====")
for tb in body.iter("{%s}txbxContent" % NS["w"]):
    lines.append("txbx=%r" % "".join(t.text or "" for t in tb.iter("{%s}t" % NS["w"])))
io.open(os.path.join(W, "_sk12_p2raw.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote sel=%s" % sel)
