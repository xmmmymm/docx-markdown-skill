# -*- coding: utf-8 -*-
"""probe_omml.py: Word 原生公式（OMML m:oMath）载体判定 + numPr 段落计数。

三连判之一（另两个：probe_special.py / probe_ole.py）。
输出 probe_omml.txt（UTF-8 中文安全）+ 终端 ASCII 摘要。
计数落盘 JSON：carrier_counts.json
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
doc = (BASE / "unpacked/word/document.xml").read_text(encoding="utf-8")

counts = {
    "oMath": doc.count("<m:oMath"),
    "oMathPara": doc.count("<m:oMathPara"),
    "m_bar": doc.count("<m:bar"),
    "m_limLow": doc.count("<m:limLow"),
    "m_limUpp": doc.count("<m:limUpp"),
    "m_groupChr": doc.count("<m:groupChr"),
    "m_sSub": doc.count("<m:sSub>"),
    "m_sSubSup": doc.count("<m:sSubSup>"),
    "m_sSup": doc.count("<m:sSup>"),
    "m_f": doc.count("<m:f>"),
    "m_d": doc.count("<m:d>"),
    "m_m": doc.count("<m:m>"),
    "m_eqArr": doc.count("<m:eqArr"),
    "m_txbxContent": doc.count("w:txbxContent"),
    "w_object": doc.count("<w:object"),
    "w_instrText": doc.count("<w:instrText"),
    "w_fldChar": doc.count("<w:fldChar"),
    "w_numPr": doc.count("<w:numPr>"),
    "w_numPr_loose": doc.count("<w:numPr"),
    "w_alternateContent": doc.count("mc:AlternateContent"),
    "w_fallback": doc.count("mc:Fallback"),
    "u2009": doc.count("\u2009"),
    "u2005": doc.count("\u2005"),
    "u200b": doc.count("\u200b"),
}
(BASE / "carrier_counts.json").write_text(
    json.dumps(counts, ensure_ascii=False, indent=1), encoding="utf-8")

out = ["### 载体计数（document.xml）"]
for k, v in counts.items():
    out.append("  %-24s %d" % (k, v))

# 逐 oMath 文本（最多 60 个，每项截断 160 字）
paras = re.findall(r"<m:oMath[ >].*?</m:oMath>", doc, flags=re.S)
out.append("")
out.append("### oMath 逐对象文本（前 60 个，按 m:t 拼接）")
for i, p in enumerate(paras[:60]):
    txt = "".join(re.findall(r"<m:t[^>]*>([^<]*)</m:t>", p))
    out.append("  #%d  %r" % (i + 1, txt[:160]))
out.append("  (总 oMath = %d)" % len(paras))

(BASE / "probe_omml.txt").write_text("\n".join(out), encoding="utf-8")

print("oMath=%d oMathPara=%d w:object=%d w:instrText=%d w:numPr=%d" % (
    counts["oMath"], counts["oMathPara"], counts["w_object"],
    counts["w_instrText"], counts["w_numPr"]))
print("m:sSub=%d m:f=%d m:m=%d m:bar=%d m:groupChr=%d" % (
    counts["m_sSub"], counts["m_f"], counts["m_m"],
    counts["m_bar"], counts["m_groupChr"]))
print("written probe_omml.txt / carrier_counts.json")
