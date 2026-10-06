# -*- coding: utf-8 -*-
"""make_md.py: skeleton.txt -> 最终 md
版式: 封面多行标题合并为一行(单空格); 引用状态机(in_ans); 选项引用块;
      **答案区状态机(ans_sec, U47)**: 无「解析版」件以"含『答案』的短标题行"为答案区起点,
      其后各行按普通段落输出、不进引用块;
      管状表格(本件无总表, 全部表格不加粗); 图 ![](images/x)〔图：描述〕

【移植改动】只改 DOCNAME；必要时按源文调整 COVER_HEAD / COVER_CONT 前缀。
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import apply_fixes, log_summary

BASE = Path(__file__).resolve().parent
DST = BASE.parent
# 【skill 版·自动推导】DOCNAME = 输出目录名（= docx stem），与 fix_fullwidth.py 同口径；
# 特殊情况（成品名 ≠ 目录名）才手工覆盖。
DOCNAME = DST.name
MD_OUT = DST / (DOCNAME + ".md")

# 封面合并：首行前缀 + 后续行前缀。单行标题件无多行封面需合并（COVER_CONT 留空）。
COVER_HEAD = ""
COVER_CONT = ()

# ---- 图片描述 ----
desc = {}
keep = False
for ln in (BASE / "figure_desc.md").read_text(encoding="utf-8").split("\n"):
    # 【氯批次 序0 修订·通用，已同步钠批次】兼容各件 figure_desc.md 的小节命名差异
    #  （钠批次用 "## 保留插图"，氯批次用 "## 二、保留图逐张描述（N 张）"）：
    #  改用"小节标题含『保留』"判定，否则 keep 恒为 False、描述全成 ⟨DESC?⟩。
    if ln.startswith("## ") and "保留" in ln:
        keep = True
        continue
    if ln.startswith("## "):
        keep = False
    #  条目正则容纳：文件名加粗（**imageN.png**）与"文件名↔冒号"间夹的限定语
    #  （如"（第 12 题）"）；\w 改 [A-Za-z] 防越界匹配非 ASCII 词字符。
    m = re.match(r"- (image\d+\.[A-Za-z]+)[^：]*：(.*)", ln.replace("**", ""))
    if m and keep:
        desc[m.group(1)] = m.group(2).strip()

skel_raw = (BASE / "skeleton.txt").read_text(encoding="utf-8")
skel, fix_log = apply_fixes(skel_raw)
(BASE / "fix_log.json").write_text(json.dumps(fix_log, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

lines = skel.split("\n")

OPT_RE = re.compile(r"^(?:[A-Da-d][．．.]|①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩|⑪|⑫|⑬|⑭|⑮|⑯|⑰|⑱|⑲|⑳)")
# 【氯批次 序0 修订，已同步钠批次】源文答案标签可能写作【参考答案】（非【答案】），
#  必须一并识别为标签行，否则 in_ans 不置位、【解析】后的选项行会误入引用块。
# 【本件新增·通用】标签可**内联于题号行**：本件文末答案区形如 `19．【答案】①…；②…`，
#  其中 ②—⑪ 各自独占一行；若标签未识别 → in_ans 保持 False → 这些答案小项被判为"选项"
#  而误入引用块（本件实测 16/19 题命中）。故允许标签前带可选题号 `(?:\d+．)?`。
LABEL_RE = re.compile(r"^(?:\d+．)?【(答案|参考答案|解析|分析|详解|点睛)】")
# 【钠批次 序9 修订·通用，U47】无「解析版」件的答案区起点已见三种形态：
#  ① 独立行 `答案`（钠序7）；② 标题行「答案与分层梯度式解析」（钠序8）；③ 独立标题行「参考答案」（钠序9）。
#  统一用"短标题行含『答案』"判定；命中后 ans_sec=True，该行及其后各行按普通段落渲染（不进引用块），
#  否则答案区以 `②③` / `A.` 起首的行会被误入引用块。带【】的标签仍由 LABEL_RE 处理。
# 【氯批次 序4 修订·通用，已同步钠批次】① 答案区形态第 4 种：独立标题行「详解答案」（另有
#  「答案解析」一并容错）——四种形态（独立行`答案`／「答案与分层梯度式解析」／「参考答案」／
#  「详解答案」）通吃；② 题号分隔符可为全角句点或顿号（`1．`/`1、`，序4 全篇用顿号）。
#  U35 回归：对已交付氯序0–3 与钠序0–9 的全部 skeleton，`^\d+、` 命中 0 行 → 零影响。
# 【硫序7 新增·通用】答案区形态第 5 种：独立行 `标准答案：`（带全角/半角冒号）——旧式整行等同
#  判定（`^标准答案$`）不匹配带冒号者；改为「短标题词 + 可选尾冒号」。U35 影响面：全工作区
#  28 个已交付 skeleton.txt 中**仅本件新增命中 1 行**（`标准答案：`），其余 27 件 0 新增 → 纯超集。
ANS_SEC_RE = re.compile(r"^(参考答案|标准答案|答案|详解答案|答案解析|答案与[^\n]{0,30})[：:]?$")
# 【硫序6 新增·通用（U67）】题号可带「（多选）」/「（单选）」前缀（源文 `（多选）18．（2025春•淄博期中）…`）。
#  若不识别：答案区该题号行不重置 in_ans → 其题干选项行被误判为"解答正文"而**掉出引用块**，
#  与该区其余题的版式不一致。U35 回归：全工作区 27 个已交付 skeleton.txt 中**仅本件命中 2 行**，
#  其余 26 件零影响 → 纯超集。
QNUM_RE = re.compile(r"^(?:（多选）|（单选）)?\d+[．、]")
# 【氯批次 序1 新增·通用】讲义体例件无 "^数字．" 题号，题目以【典例N】/【变式N-M】起首；
#   若不并作题号起点，in_ans 状态机永不复位 → 只有首题选项进引用块（本件 15 个典例中 14 个不成块）。
QSTART_RE = re.compile(r"^【(典例|变式)")
FIG_RE = re.compile(r"⟨FIG:([^⟩]+)⟩")

def fig_md(name):
    d = desc.get(name, "⟨DESC?:" + name + "⟩")
    return "![](images/%s)〔图：%s〕" % (name, d)

def sub_fig(text):
    return FIG_RE.sub(lambda m: fig_md(m.group(1)), text)

blocks = []
in_ans = False
ans_sec = False   # U47：无「解析版」件的答案区起点（行含"答案"的短标题）
i = 0
tbl_count = 0
N = len(lines)
title_done = False

while i < N:
    ln = lines[i]
    i += 1
    stripped = ln.strip()
    if stripped == "":
        continue

    # ---- 封面多行标题合并 ----
    if not title_done and stripped.startswith(COVER_HEAD):
        parts = [re.sub(r"\s+", " ", stripped)]
        while i < N:
            nxt = lines[i].strip()
            if nxt.startswith(COVER_CONT):
                parts.append(re.sub(r"\s+", " ", nxt))
                i += 1
            else:
                break
        title_done = True
        blocks.append(" ".join(parts))
        continue

    # ---- 表格 ----
    if stripped == "<TBL>":
        rows = []
        while i < N and lines[i].strip() != "</TBL>":
            rows.append(lines[i])
            i += 1
        i += 1  # 消费 </TBL>
        tbl_count += 1
        # 按裸 "|||" 切分: 行首/行尾空白已被 normalize 清除, 用带空格分隔符会错位
        cells = [[c.strip() if c.strip() != "<MERGE>" else "" for c in r.split("|||")]
                 for r in rows]
        # 空表（<TBL> 紧跟 </TBL>）时 cells==[]，max() 会抛
        # ValueError: max() arg is an empty sequence ⇒ 裸栈中断 S6
        if not cells:
            continue
        ncol = max(len(r) for r in cells)
        cells = [r + [""] * (ncol - len(r)) for r in cells]
        out = []
        for ri, r in enumerate(cells):
            r = [sub_fig(c) for c in r]
            out.append("| " + " | ".join(r) + " |")
            if ri == 0:
                out.append("|" + "---|" * ncol)
        blocks.append("\n".join(out))
        continue

    # ---- 行首独立图片 -> 单独成块 ----
    m = re.match(r"^((?:⟨FIG:[^⟩]+⟩)+)(.*)$", stripped)
    if m:
        for name in FIG_RE.findall(m.group(1)):
            blocks.append(fig_md(name))
        stripped = m.group(2).strip()
        if stripped == "":
            continue

    if QNUM_RE.match(stripped) or QSTART_RE.match(stripped):
        in_ans = False
    if LABEL_RE.match(stripped):
        in_ans = True
    if ANS_SEC_RE.match(stripped):     # U47：答案区起点（该行本身仍按普通段落渲染）
        ans_sec = True

    is_opt = bool(OPT_RE.match(stripped)) and not in_ans and not ans_sec
    txt = sub_fig(stripped)

    if is_opt:
        qlines = [txt]
        while i < N:
            nxt = lines[i].strip()
            if nxt and OPT_RE.match(nxt) and not in_ans and not ans_sec:
                qlines.append(sub_fig(nxt))
                i += 1
            else:
                break
        blocks.append("\n>\n".join("> " + q for q in qlines))
        continue

    blocks.append(txt)

md = "\n\n".join(blocks) + "\n"

# 叠置条件归一(EQ 域已直接生成 =(Δ)=, 此处仅兜底)
md2 = re.sub(r"=\(=\(([^)]*)\)=\)(/[^)=]+)?=",
             lambda m: "=(%s%s)=" % (m.group(1), m.group(2) or ""), md)
if md2 != md:
    fix_log.append({"type": "re", "old": "=(=(X)=)=…", "new": "=(X(/Y))=",
                    "note": "叠置条件归一", "count": md.count("=(=(")})
    json.dump(fix_log, open(BASE / "fix_log.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
md = md2

MD_OUT.write_text(md, encoding="utf-8")
rep = ["md: %s" % MD_OUT.name,
       "blocks: %d, tables: %d" % (len(blocks), tbl_count),
       "--- fix_log ---"]
rep += ["   " + s for s in log_summary(fix_log)]
rep += ["DESC? missing: %d" % md.count("⟨DESC?"),
        "fig residual: %d" % md.count("⟨FIG"),
        "=(=( residual: %d" % md.count("=(=(")]
(BASE / "make_md_report.txt").write_text("\n".join(rep), encoding="utf-8")
print("md written:", MD_OUT.name.encode("ascii", "replace").decode("ascii"))
