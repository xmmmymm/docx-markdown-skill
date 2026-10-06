# -*- coding: utf-8 -*-
"""_chk_prompt_drift.py · 校验 _启动提示词.md 与 _skill规划.md 第十节逐字一致（stdout 仅 ASCII）。

用法：在 skill 根目录执行 `<py> _chk_prompt_drift.py`（exit 0=一致 1=漂移）
与 _templates/_sk7_genprompt.py 配对使用：先跑 genprompt 重新生成，再跑本脚本复核。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(ROOT, "_skill规划.md")
START = os.path.join(ROOT, "_启动提示词.md")
SEC = "## 十、提示词"


def body_of(txt, marker):
    i = txt.index(marker)
    j = txt.index("```", i)
    k = txt.index("```", j + 3)
    return txt[j + 3:k].strip("\n")


def main():
    plan = io.open(PLAN, encoding="utf-8").read()
    start = io.open(START, encoding="utf-8").read()
    b1 = body_of(plan, SEC)
    b2 = body_of(start, "# 试题提取 skill · 启动提示词")
    if b1 == b2:
        print("IDENTICAL chars=%d lines=%d" % (len(b1), len(b1.splitlines())))
        return 0
    print("DRIFT plan_chars=%d start_chars=%d" % (len(b1), len(b2)))
    l1, l2 = b1.splitlines(), b2.splitlines()
    for i in range(max(len(l1), len(l2))):
        a = l1[i] if i < len(l1) else "<none>"
        c = l2[i] if i < len(l2) else "<none>"
        if a != c:
            print("  line %d plan=%s" % (i + 1, a.encode("unicode_escape").decode("ascii")))
            print("  line %d star=%s" % (i + 1, c.encode("unicode_escape").decode("ascii")))
    return 1


if __name__ == "__main__":
    sys.exit(main())