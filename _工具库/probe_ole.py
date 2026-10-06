# -*- coding: utf-8 -*-
"""probe_ole.py: 判定 work/unpacked/word/embeddings/oleObjectN.bin 的"真身"
—— 每到一件文档，`mtef_render.py` 若报 failed，先跑本脚本，再决定处置方式。

背景（钠批次 序2「专题1 钠及钠的氧化物拓展」实测）：
  源文里的 OLE 不止 MathType 一种。`CompObj` 流会写明真实程序：
    * `MathType 6.0 Equation` / `Equation.DSMT4`
        → 有 `Equation Native` 流 → 用 `mtef_render.py` 程序化还原成线性文本。
    * `ACD/ChemSketch`（画结构式的软件）
        → **没有** `Equation Native`，内部流是 **`\x01Ole10Native`**（注意 `\x01` 前缀，
          直接 `ole.openstream("Ole10Native")` 会 `OSError: file not found`）。
        → 无法程序化解析成文本；应按"图"处理：
          其 `v:imagedata` 预览 WMF（media/imageN.wmf）
          → `soffice --headless --convert-to pdf` → PyMuPDF 高 DPI 栅格化 + 裁白
          （脚本 `render_ole_fig.py`）→ 作为保留插图 `images/<预览同名>.png`。
          在 `make_skeleton.py` 中用 `OLE_FIG = {"oleObject13": "image19.png", ...}` 改判。

输出：work/ole_probe.txt（UTF-8，中文安全）+ 终端 ASCII 摘要。
"""
import hashlib
import olefile
from pathlib import Path

BASE = Path(__file__).resolve().parent
EMB = BASE / "unpacked/word/embeddings"

out = []
rows = []
for p in sorted(EMB.glob("oleObject*.bin"), key=lambda q: int(q.stem[9:])):
    name = p.stem
    data = p.read_bytes()
    out.append("=== %s (%d bytes) md5=%s ===" % (p.name, len(data), hashlib.md5(data).hexdigest()))
    try:
        if not olefile.isOleFile(str(p)):
            out.append("  !! 不是 OLE 复合文档；head hex=%s" % data[:32].hex())
            rows.append((name, "NOT-OLE", "-"))
            continue
        ole = olefile.OleFileIO(str(p))
        streams = ["/".join(s) for s in ole.listdir()]
        comp = ""
        for s in streams:
            if s.endswith("CompObj"):
                d = ole.openstream(s.split("/")).read()
                txt = "".join(chr(b) if 32 <= b < 127 else " " for b in d)
                comp = " ".join(txt.split())
        for s in streams:
            sz = ole.get_size(s.split("/")) if hasattr(ole, "get_size") else -1
            out.append("  stream %-28r size=%s" % (s, sz))
        out.append("  CompObj: %s" % comp)
        has_eq = any(s.endswith("Equation Native") for s in streams)
        has_native = any(s.endswith("Ole10Native") for s in streams)
        kind = ("MathType(可 MTEF 解析)" if has_eq
                else "非 MathType(按图处理)" if has_native
                else "未知")
        rows.append((name, kind, comp[:60]))
        # 非 MathType：抽取预览 WMF 名（由 rels 决定，见 probe_this 思路）
        ole.close()
    except Exception as e:
        out.append("  ERROR %s: %s" % (type(e).__name__, e))
        rows.append((name, "ERROR", str(e)[:60]))

out.insert(0, "## 汇总（oleObject → 类型 → CompObj）")
for r in rows:
    out.insert(1, "  %-16s %-22s %s" % r)
(BASE / "ole_probe.txt").write_text("\n".join(out), encoding="utf-8")

for r in rows:
    print("%-16s %-22s %s" % (r[0], r[1], r[2].encode("ascii", "replace").decode()))
print("written ole_probe.txt")
