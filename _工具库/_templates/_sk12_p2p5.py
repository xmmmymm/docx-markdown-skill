# -*- coding: utf-8 -*-
"""Item12: structural dump of paragraphs 0-8 (runs / drawing / pict / txbx / OMML)."""
import io
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _sk93_target as T

W = T.work()
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
root = ET.parse(os.path.join(W, "unpacked", "word", "document.xml")).getroot()
body = root.find("w:body", NS)
paras = list(body.iter("{%s}p" % NS["w"]))

out = []
for i in range(0, 9):
    p = paras[i]
    out.append("=" * 20 + " P%d" % i)
    for r in p.iter("{%s}r" % NS["w"]):
        rpr = r.find("w:rPr", NS)
        vert = ""
        if rpr is not None:
            va = rpr.find("w:vertAlign", NS)
            if va is not None:
                vert = "[%s]" % va.get("{%s}val" % NS["w"])
        items = []
        for ch in r:
            tag = ch.tag
            if tag == "{%s}t" % NS["w"]:
                items.append("T=%r" % (ch.text or ""))
            elif tag == "{%s}tab" % NS["w"]:
                items.append("TAB")
            elif tag == "{%s}drawing" % NS["w"]:
                anch = ch.find("wp:anchor", NS) is not None
                blips = [b.get("{%s}embed" % NS["r"]) for b in ch.iter("{%s}blip" % NS["a"])]
                tb = "".join(t.text or "" for t in ch.iter("{%s}t" % NS["w"]))
                items.append("DRAWING(anchor=%s,blips=%s,txb=%r)" % (anch, blips, tb))
            elif tag == "{%s}pict" % NS["w"]:
                ole = ch.find(".//o:OLEObject", NS)
                imd = [x.get("{%s}id" % NS["r"]) for x in ch.iter("{%s}imagedata" % NS["v"])]
                items.append("PICT(ole=%s,imagedata=%s)" % (ole is not None, imd))
            elif tag == "{%s}object" % NS["w"]:
                items.append("OBJECT")
            elif tag == "{%s}AlternateContent" % NS["w"]:
                items.append("ALTCONTENT")
            else:
                items.append(tag.replace("{%s}" % NS["w"], "w:"))
        if items:
            out.append("  R%s %s" % (vert, " ".join(items)))
    omml = p.findall(".//m:oMath", NS)
    for k, om in enumerate(omml):
        txt = "".join(t.text or "" for t in om.iter("m:t"))
        out.append("  OMML[%d] text=%r" % (k, txt))
        out.append("    tree=" + ET.tostring(om, encoding="unicode")[:600].replace("\n", ""))
io.open(os.path.join(W, "_sk12_p0p8.txt"), "w", encoding="utf-8").write("\n".join(out))
print("paras=%d len=%d" % (len(paras), len("\n".join(out))))
print("\n".join(out[:40]))
