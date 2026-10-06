# -*- coding: utf-8 -*-
"""_chk_no_local_paths.py · 扫描**将被 git 跟踪**的文件，确认不含本机绝对路径。

比对两种写法：真实反斜杠 与 json/文档里常见的转义双反斜杠（\\\\）。
stdout 仅 ASCII（U2/U90）。用法：`<py> _chk_no_local_paths.py`（exit 0=干净 1=有命中）
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# 本机特征串（转义与未转义两种形态都覆盖）
# ⚠ 一律用 re.IGNORECASE 匹配：盘符大小写混用（`d:\Desktop` 与 `D:\Desktop`）
#   是真实存在的情形，早期版本只写大写 D ⇒ 小写形态整片漏网（U195）。
PATTERNS = [
    r"[A-Z]:\\\\?Desktop",                  # D:\Desktop / D:\\Desktop / d:\Desktop
    r"[A-Z]:\\\\?Users\\\\?Administrator",
    r"\.workbuddy",
    r"\\\\?Desktop\\\\?[^\\\s\"']*学位论文",
    r"[A-Z]:\\\\?[^\\\s\"']*课后题",          # 本工程的历史工作区
]
SKIP_PARTS = {".git", "__pycache__"}


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=True).stdout
    except Exception as e:                                  # 非 git 仓库则退回全盘扫描
        sys.stderr.write("git unavailable (%s); fallback walk\n" % e.__class__.__name__)
        acc = []
        for dp, dns, fns in os.walk(ROOT):
            dns[:] = [d for d in dns if d not in SKIP_PARTS]
            acc += [os.path.join(dp, f) for f in fns]
        return acc
    return [os.path.join(ROOT, p.decode("utf-8"))
            for p in out.split(b"\0") if p]


def main():
    hits = 0
    # 本脚本与迁移脚本**按设计**持有这些特征串（一个是检测规则，一个是替换规则），
    # 须排除，否则自触发误报。这是白名单而非漏洞：两者的字符串都是正则字面量。
    PATTERN_HOLDERS = {os.path.basename(__file__), "_迁移外部资料.py"}
    for f in tracked_files():
        if not os.path.isfile(f):
            continue
        if any(p in f for p in SKIP_PARTS) or f.endswith((".pyc", ".pyo")):
            continue
        if os.path.basename(f) in PATTERN_HOLDERS:
            continue
        try:
            txt = io.open(f, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        for pat in PATTERNS:
            for m in re.finditer(pat, txt, re.IGNORECASE):
                ln = txt.count("\n", 0, m.start()) + 1
                rel = os.path.relpath(f, ROOT)
                print("HIT %s:%d %s" % (rel, ln, m.group(0)[:40]))
                hits += 1
    print("FILES=%d HITS=%d" % (len(tracked_files()), hits))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())