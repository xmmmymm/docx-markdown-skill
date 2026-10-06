# -*- coding: utf-8 -*-
# _sk7_genprompt.py · 从《_skill规划.md》提示词节自动抽取生成 ..\_启动提示词.md
# （防两版漂移：规划第十节为真源；无中文 argv，U93；stdout 仅 ASCII，U90）。
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))     # skill 工程根（试题提取skill\）
PLAN = os.path.join(ROOT, "_skill规划.md")
OUT = os.path.join(ROOT, "_启动提示词.md")

txt = io.open(PLAN, encoding="utf-8").read()
i = txt.index("## \u5341\u3001\u63d0\u793a\u8bcd")   # ## 十、提示词
j = txt.index("```", i)
k = txt.index("```", j + 3)
body = txt[j + 3:k].strip("\n")

head_lines = [
    "# 试题提取 skill · 启动提示词",
    "",
    "> 用法：新会话里**整段复制下面代码块内容**发送即可（先按提示词更新 `_target.txt` 三要素）。",
    "> 本文件代码块与《_skill规划.md》第十节代码块**逐字一致**——由 `_templates\\_sk7_genprompt.py`",
    "> 从规划第十节**自动抽取**（第十节为真源，防两版漂移）；改了第十节须重跑本脚本再交付。",
    "",
    "```",
]
out = "\n".join(head_lines) + "\n" + body + "\n```\n"
io.open(OUT, "w", encoding="utf-8", newline="\n").write(out)
print("WROTE _startup_prompt.md ; body_lines=%d body_chars=%d" % (
    len(body.splitlines()), len(body)))
