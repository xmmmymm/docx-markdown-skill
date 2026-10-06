# -*- coding: utf-8 -*-
"""list_docx.py: 逐字列出目标目录内全部 docx 的**精确文件名**（含多空格 / U+3000 的真实形态）。

为什么需要它：目录列表在终端/界面里会把 U+3000 与半角空格显示得难以区分，
多空格也可能被视觉合并；而输出目录名必须**逐字照搬**源 docx 名。
本脚本用 Python 直接取 `Path.name` 并落盘 JSON（UTF-8），供建「待处理队列」时逐字核对。

用法:
    python list_docx.py <目录绝对路径>

输出:
    - `<脚本所在目录>/docx_list.json`（UTF-8, ensure_ascii=False）：
        name / len / stem / spaces(半角空格数) / u3000(U+3000 个数) / tabs / mb
    - stdout 仅 ASCII 摘要（规避 Windows GBK 终端报错；中文一律看 JSON 文件）

注意事项:
    - 读 JSON 请用 read_file 工具，不要用终端 cat/type（会乱码）。
    - 严禁用 search_content / search_file 核对文件名（含空格/中文路径会静默返回 0）。
"""
import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    raise SystemExit("usage: python list_docx.py <dir absolute path>")

target = Path(sys.argv[1])
BASE = Path(__file__).resolve().parent
items = sorted(p.name for p in target.glob("*.docx"))

out = []
for name in items:
    p = target / name
    out.append({
        "name": name,
        "stem": p.stem,
        "len": len(name),
        "spaces": name.count(" "),
        "u3000": name.count("\u3000"),
        "tabs": name.count("\t"),
        "mb": round(p.stat().st_size / 1048576, 2),
    })

(BASE / "docx_list.json").write_text(
    json.dumps({"dir": str(target), "count": len(out), "docx": out},
               ensure_ascii=False, indent=1),
    encoding="utf-8")

print("target:", target.name.encode("ascii", "replace").decode())
print("docx count:", len(out))
for e in out:
    print("  len=%d spaces=%d u3000=%d mb=%s" % (e["len"], e["spaces"], e["u3000"], e["mb"]))
print("written: docx_list.json")
