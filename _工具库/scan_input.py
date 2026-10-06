# -*- coding: utf-8 -*-
"""scan_input.py · 【skill 专属】扫描输入夹第一层 .docx → 生成批次队列 json。

三要素读 `_templates\\_target.txt` 的前两行（U93：中文路径只待在 UTF-8 文件里，
绝不作 argv 直传；第 3 行 stem 本脚本不用，只填两行也能跑）。
环境变量 SKILL_TARGET（按 TAB 分隔）可整体覆盖（ASCII 场景）。

产物：`<skill 根>\\_队列\\queue.json`：
  {"in_root":…, "out_root":…, "generated":…,
   "queue": [{"queue":N, "stem":…, "src_abs":…, "out_abs":…, "size":…}, …],
   "skipped": [非 docx / ~$ 临时件, …]}
- stem 逐字取自磁盘文件名（去 .docx），含连续空格/全角/`——` 等，**建目录勿手敲**
  （U78：队列 json 的 stem 是唯一真源）；
- 按文件名字典序排队，queue 序号从 0 起；用户可自行重排 json 后再开工；
- `.doc`（旧格式）/`~$`（Word 锁文件）/其他扩展名不进队列、只进 skipped 清单。

用法（stdout 仅 ASCII，U2/U90）：在 `_工具库` 目录内 `<py> scan_input.py`
（函数 `scan(in_root, out_root)` 另供 `_sk_info.py` 复用，保持队列口径单一真源）
"""
import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
TPL = BASE / "_templates"
QUEUE_DIR = BASE.parent / "_队列"


def scan(in_root, out_root):
    """扫描 <输入夹> 第一层 → 队列 payload（dict）。队列口径唯一真源。"""
    queue, skipped = [], []
    for p in sorted(Path(in_root).iterdir()):
        if p.is_dir():
            continue
        name = p.name
        if name.startswith("~$"):
            skipped.append(name)
            continue
        if name.lower().endswith(".docx"):
            stem = name[:-5]
            queue.append({"queue": len(queue), "stem": stem,
                          "src_abs": str(p),
                          "out_abs": str(Path(out_root) / stem),
                          "size": p.stat().st_size})
        else:
            skipped.append(name)
    return {"in_root": str(in_root), "out_root": str(out_root),
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "queue": queue, "skipped": skipped}


def write_queue(payload):
    """写 <skill 根>\\_队列\\queue.json（返回路径）。

    原子写（临时文件 + os.replace）：本文件是「开工第 1 步读进度」的对象，
    而非原子重写会让并发/紧随其后的读者读到半截 JSON（U184「sync 后复读」场景）。
    """
    QUEUE_DIR.mkdir(exist_ok=True)
    qp = QUEUE_DIR / "queue.json"
    tmp = qp.with_name(qp.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(qp))
    return qp


def main():
    raw = os.environ.get("SKILL_TARGET", "")
    if raw:
        # **保位**（空字段留 None）：SKILL_TARGET="in\t\tstem" 时若过滤掉空字段，
        # stem 会被挤到 out_root 位、所有 out_abs 全错；_sk_info.target_lines() 是
        # 保位的，两个工具对同一个变量必须同口径。
        parts = [p.strip() or None for p in raw.split("\t")]
    else:
        if not (TPL / "_target.txt").exists():
            sys.stderr.write("BAD _target.txt: missing (in _templates)\n")
            sys.exit(2)
        parts = [ln.strip() for ln in (TPL / "_target.txt").read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.lstrip().startswith("#")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        sys.stderr.write("BAD _target.txt: need 2 non-comment lines (input / output-root)\n")
        sys.exit(2)
    in_root, out_root = Path(parts[0]), Path(parts[1])
    if not in_root.is_dir():
        sys.stderr.write("BAD in_root: not a directory\n")
        sys.exit(2)

    payload = scan(in_root, out_root)
    write_queue(payload)
    print("QUEUE n=%d skipped=%d out=_queue/queue.json"
          % (len(payload["queue"]), len(payload["skipped"])))
    for it in payload["queue"]:
        # stem 是中文（U2/U90：stdout 只打 ASCII，中文详情看 UTF-8 的 queue.json）
        print("  q%-2d %8d B  %s" % (it["queue"], it["size"],
                                     it["stem"].encode("ascii", "replace").decode("ascii")))


if __name__ == "__main__":
    main()
