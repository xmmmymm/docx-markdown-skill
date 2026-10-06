# -*- coding: utf-8 -*-
r"""_迁移外部资料.py · 把「课后题」工作区里被本 skill 依赖/引用的外部资料并入本工程。

**目的**：让本工程自包含——`_skill规划.md` / `_启动提示词.md` / `_skill经验归档.md`
原先引用 `<批次数组>\...` 下的规范、样板与四批归档，迁入后一律改为工程内相对路径，
不再依赖工程之外的任何文件。

**迁移清单**（源根由 `--src` 给出，默认见 DEFAULT_SRC）：
  _规范/转换规范（优化版）.md              ← <src>\转换规范（优化版）.md
  _样板/专题13 氮及其化合物（解析版）.md    ← <src>\04 氮及其化合物\...md
  _样板/images/                            ← <src>\04 氮及其化合物\images\*
  _历史批次/<钠|氯|硫|氮>/_批次规划.md      ← <src>\<批>\<批>\_批次规划.md
  _历史批次/<钠|氯|硫|氮>/_批次进度.md
  _历史批次/<钠|氯|硫|氮>/_批次经验归档.md
  _历史批次/氮/_收官复核_20260919.md        ← <src>\氮\氮\_收官复核_20260919.md

**不迁移**（已确认无用或冗余）：各批 `_工具库\` 母本副本（已被当前库取代）、
`.codebuddy\`、docx 源件、一次性探针脚本、`提示词*.txt`（非必读）。

**行为**：幂等（已存在且字节相同则跳过）；每个文件**逐字节 sha256 校验**；
stdout 仅 ASCII（U2/U90）。用法：`<py> _迁移外部资料.py --src "<源根>" [--dry-run]`
"""
import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# 源根**不设默认值**：本脚本是一次性迁移工具，写死本机路径会把个人信息带进仓库
# （U195）。调用时用 --src 显式给出当时的「课后题」工作区根目录。
REPORT = ROOT / "_迁移报告.txt"

# 四批：批次目录名（<批>\<批>\ 双层）
BATCHES = ["钠", "氯", "硫", "氮"]
SAMPLE_DIR = "04 氮及其化合物"
SAMPLE_MD = "专题13 氮及其化合物（解析版）.md"

# ── 迁移时脱敏（U195）──────────────────────────────────────────────
# 历史批次文档写于各批运行时，正文含大量**本机绝对路径**（工作区根、venv 的
# python.exe）。直接入库会把上一轮「路径相对化」的成果退回去，故迁移时同步替换。
# 顺序重要：先长后短（工作区 → 论文目录 → venv/workbuddy）。
SANITIZE = [
    (re.compile(r"[A-Za-z]:[\\/]+Desktop[\\/][^\\/\r\n]*?[\\/]课后题", re.I), "<工作区>"),
    (re.compile(r"[A-Za-z]:[\\/]+Desktop[\\/][^\\/\r\n]*", re.I), "<论文目录>"),
    (re.compile(r"[A-Za-z]:[\\/]+Users[\\/][^\\/\r\n]*?[\\/]\.workbuddy[\\/]"
                r"[^\s`'\"()<>]*?python\.exe", re.I), "<venv>\\python.exe"),
    (re.compile(r"[A-Za-z]:[\\/]+Users[\\/][^\\/\r\n]*?[\\/]\.workbuddy[^\s`'\"()<>]*",
                re.I), "<workbuddy>"),
]
sanitized_hits = [0]


def sanitize(text):
    """→ (新文本, 命中数)；幂等（占位符不含盘符，不会二次命中）。

    用函数式替换而非模板字符串：替换文本含 `\\p`（`<venv>\\python.exe`），
    在 re.subn 的**模板**语义里 `\\p` 是非法转义会抛 PatternError。
    """
    n = 0
    for pat, rep in SANITIZE:
        text, k = pat.subn(lambda m, _r=rep: _r, text)
        n += k
    return text, n


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_plan(src: Path):
    """→ [(src_path, dest_relpath, kind)]；kind 用于报告分组。"""
    plan = []
    # 1 总规范
    plan.append((src / "转换规范（优化版）.md", "_规范/转换规范（优化版）.md", "spec"))
    # 2 版式样板（md + 同目录 images）
    plan.append((src / SAMPLE_DIR / SAMPLE_MD, "_样板/" + SAMPLE_MD, "sample"))
    imgdir = src / SAMPLE_DIR / "images"
    if imgdir.is_dir():
        for p in sorted(imgdir.iterdir()):
            if p.is_file():
                plan.append((p, "_样板/images/" + p.name, "sample-img"))
    # 3 四批规划/进度/归档
    for b in BATCHES:
        base = src / b / b
        for name, kind in (("_批次规划.md", "plan"),
                           ("_批次进度.md", "progress"),
                           ("_批次经验归档.md", "archive")):
            plan.append((base / name, "_历史批次/%s/%s" % (b, name), kind))
    # 4 氮批收官复核
    for p in sorted((src / "氮" / "氮").glob("_收官复核*.md")):
        plan.append((p, "_历史批次/氮/" + p.name, "review"))
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True,
                    help="external work root to import from (no default on purpose)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resanitize", action="store_true",
                    help="only re-run sanitization in place on already-imported files")
    a = ap.parse_args()
    src = Path(a.src)
    if not src.is_dir():
        sys.stderr.write("BAD --src: not a directory\n")
        return 2

    plan = build_plan(src)
    lines = ["== _迁移外部资料 ==", "src: %s" % src, "plan_items=%d" % len(plan), ""]
    copied = skipped = missing = 0
    bad = []
    counts = {}
    for s, rel, kind in plan:
        if not s.is_file():
            missing += 1
            lines.append("MISSING %s" % rel)
            bad.append(rel)
            continue
        d = ROOT / rel
        counts[kind] = counts.get(kind, 0) + 1
        if a.dry_run:
            continue
        if d.is_file() and not a.resanitize and sha256(d) == sha256(s):
            skipped += 1
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.is_file() and a.resanitize:
            pass                                  # 就地脱敏，不重拷
        else:
            shutil.copy2(s, d)
        # 迁移即脱敏：历史批次文档写于各批运行时，正文里带大量本机绝对路径；
        # 直接入库等于把上一轮「路径相对化」的成果又退回去（U195）。
        if d.suffix.lower() in (".md", ".txt", ".json"):
            before = d.read_text(encoding="utf-8", errors="replace")
            after, n = sanitize(before)
            if after != before:
                d.write_text(after, encoding="utf-8", newline="\n")
                lines.append("SANITIZED %-46s hits=%d" % (rel, n))
                sanitized_hits[0] += n
        if not a.resanitize and sha256(d) != sha256(s):
            # 脱敏后哈希必然不同：只在未脱敏（二进制/图片）时断言
            if d.suffix.lower() not in (".md", ".txt", ".json"):
                bad.append("HASH-DIFF " + rel)
                lines.append("HASH-DIFF %s" % rel)
            else:
                copied += 1
        else:
            copied += 1

    lines.append("by_kind: " + ", ".join("%s=%d" % kv for kv in sorted(counts.items())))
    lines.append("copied=%d skipped(same)=%d missing=%d bad=%d sanitized_hits=%d"
                 % (copied, skipped, missing, len(bad), sanitized_hits[0]))
    if not a.dry_run:
        # 报告自身也过一遍脱敏：它含 `src: <本机路径>` 一行
        REPORT.write_text(sanitize("\n".join(lines) + "\n")[0],
                          encoding="utf-8", newline="\n")
    print("SRC=%s" % src)
    print("PLAN=%d COPIED=%d SKIP_SAME=%d MISSING=%d BAD=%d"
          % (len(plan), copied, skipped, missing, len(bad)))
    for k in sorted(counts):
        print("  %-12s %d" % (k, counts[k]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())