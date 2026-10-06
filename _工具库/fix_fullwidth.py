# -*- coding: utf-8 -*-
"""fix_fullwidth.py: 交付件全角符号清零（《转换规范（优化版）》§六 零残留清单）

一次处理 4 个码位：
  U+FF0B ＋ -> '+'
  U+FF1D ＝ -> '='
  U+2550 ═ -> '='
  U+2022 • -> U+00B7 '·'

目标 md 由“脚本所在目录的父目录名 + .md”推出 —— 故本脚本应放在 `<输出目录>\\work\\` 下，
放在别处会找不到目标。脚本内不含中文字面量，stdout 仅 ASCII（规避 GBK 终端报错）。

【用法与纪律】
  python fix_fullwidth.py            # 就地清零并计数
  → 落盘 work\\fix_fw_log.txt；**随后必须重跑 audit.py**，
    并在该件《转换说明.md》第七节留「回改记录」（内容/处数/复跑结论），
    再回写 `_批次进度.md` 备注。
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent          # ...\<docx名>\work
DST = BASE.parent                               # ...\<docx名>\
md_path = DST / (DST.name + ".md")

if not md_path.is_file():
    raise SystemExit("target md not found: %s" % md_path.name.encode("ascii", "replace").decode())

text = md_path.read_text(encoding="utf-8")
FW = [("\uff0b", "+"), ("\uff1d", "="), ("\u2550", "="), ("\u2022", "\u00b7")]

log = []
t = text
for old, new in FW:
    n = t.count(old)
    if n:
        t = t.replace(old, new)
    log.append({"cp": "U+%04X" % ord(old), "to": new, "count": n})

md_path.write_text(t, encoding="utf-8")
(BASE / "fix_fw_log.txt").write_text(
    json.dumps({"md": md_path.name, "fixes": log}, ensure_ascii=True, indent=1),
    encoding="utf-8")
print("md:", md_path.name.encode("ascii", "replace").decode())
print("fixes:", json.dumps(log))
print("len_before:", len(text), "len_after:", len(t))
