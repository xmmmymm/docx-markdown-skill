# -*- coding: utf-8 -*-
"""_sk0_baseline.py · 【skill 专属】基线指纹比对（防手滑改坏 CORE 脚本）。

指纹文件：`..\\_基线指纹.json`（skill 工程根，与 `_skill规划.md` 同级）。
**改 CORE 须三步**（缺一不可）：
  ① 先过 U35 回归（新旧同源 exec 比对，全工作区语料，见氮批归档 U100 范式）；
  ② 在 `..\\_skill经验归档.md` 记「工具库改动」（改了什么/为什么/影响面）；
  ③ 跑 `--write` 重新登记指纹（本脚本会核对归档当日有登记，无则警告）。

用法（stdout 仅 ASCII，U2/U90）：
  <py> _sk0_baseline.py            # 比对模式：SAME/NEW/CHANGED/MISSING，全同 exit 0
  <py> _sk0_baseline.py --write    # 登记/重写指纹（写入后自动复跑一次比对自证）
"""
import hashlib
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
FP = BASE.parent / "_基线指纹.json"
ARCHIVE = BASE.parent / "_skill经验归档.md"

# 27 项 CORE（与 `_build_port.py` 的 VERBATIM + COPY_EDIT 同清单）
CORE = [
    "s1_unpack.py", "prep_images.py", "inspect_xml.py", "dump_para.py",
    "dump_wmf2.py", "probe_chars.py", "probe_fix2.py", "probe_hf.py",
    "probe_numpr.py", "probe_ole.py", "probe_omml.py", "probe_special.py",
    "probe_tree.py", "list_docx.py", "zoom_profile.py", "fix_fullwidth.py",
    "mtef_render.py", "omml_render.py", "extract_content.py", "normalize.py",
    "make_md.py", "make_skeleton.py", "audit.py", "copy_images.py",
    "check_blank.py", "zoom_img.py", "render_ole_fig.py",
]
# skill 专属脚本（改动同样须登记，但不算 27 CORE）
SKILL_ONLY = ["scan_input.py", "_sk_info.py", "_sk_balance.py", "_sk_imgprep.py",
              "_sk_watchdog.py", "_sk0_baseline.py"]

WRITE = "--write" in sys.argv[1:]


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest().upper()[:8]


current = {}
for name in CORE + SKILL_ONLY:
    p = BASE / name
    if p.exists():
        current[name] = md5(p)

if WRITE:
    payload = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
               "core_count": len([n for n in current if n in CORE]),
               "skill_only_count": len([n for n in current if n in SKILL_ONLY]),
               "files": current}
    FP.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                  encoding="utf-8")
    if ARCHIVE.exists():
        today = time.strftime("%Y-%m-%d")
        if today not in ARCHIVE.read_text(encoding="utf-8"):
            print("WARN: archive has no entry dated today -- "
                  "record the change in _skill_archive.md (rule 2)")
    print("WROTE fingerprint ; files=%d" % len(current))

# ---- 比对 ----
if not FP.exists():
    print("NO FINGERPRINT FILE -- run with --write first")
    sys.exit(2)
old = json.loads(FP.read_text(encoding="utf-8")).get("files", {})
same = changed = missing = 0
diffs = []
for name, h in sorted(old.items()):
    if name not in current:
        missing += 1
        diffs.append("MISSING %s" % name)
    elif current[name] != h:
        changed += 1
        diffs.append("CHANGED %s %s -> %s" % (name, h, current[name]))
new = [n for n in current if n not in old]
same = len(old) - changed - missing
for n in new:
    diffs.append("NEW     %s %s" % (n, current[n]))
print("SAME=%d CHANGED=%d MISSING=%d NEW=%d" % (same, changed, missing, len(new)))
for d in diffs:
    print(" ", d)
if new:
    print("HINT: %d new script(s) not in fingerprint; run --write to register" % len(new))
# NEW 也须计入失败：新增脚本若不入指纹，此后它被改坏就再也检测不出来
sys.exit(0 if (changed == 0 and missing == 0 and not new) else 1)
