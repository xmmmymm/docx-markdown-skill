# -*- coding: utf-8 -*-
r"""audit.py: 机审最终 md
1 占位符零残留  2 题号==【答案】  3 表格数与列一致  4 图片三一致+描述
5 内容保持(md vs skeleton)  6 引用块结构  7 行尾离子  8 方程式守恒  9 空格三态
10 公式符号旁残余单空格（扫描前剔除〔图：…〕描述；只匹配"恰好 1 个"空格）

【移植改动】
- DOCNAME：本文档名（去 .md）。
- ANS_DIFF：`【答案】数 − 题号数` 的期望值。正常件 = 0；
  若源文自身重复标注答案（如序0 第14题连续两个【答案】）则设 1，并在 ANS_NOTE 写明白名单理由。

【第 10 项口径（钠批次 序3 修订，通用）】
扫描前先剔除 `![](...)〔图：…〕` 图描述片段（与第 5/8 项同口径），因为图描述里
会出现 `（Q2 A 项）` 这类拉丁/数字邻接，会被本项"系数后残余空格" `(?<=\d) +(?=[A-Z])`
命中，造出与正文无关的**假阳性 FAILS**（序3 实测 4 处）。
"""
import json, re, os, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import apply_fixes

BASE = Path(__file__).resolve().parent
DST = BASE.parent
# 【skill 版·自动推导】DOCNAME = 输出目录名（= docx stem），与 fix_fullwidth.py 同口径
DOCNAME = DST.name
ANS_DIFF = 0
ANS_NOTE = ""

md = (DST / (DOCNAME + ".md")).read_text(encoding="utf-8")
skel_raw = (BASE / "skeleton.txt").read_text(encoding="utf-8")
skel, _ = apply_fixes(skel_raw)
lines = md.split("\n")
report = {}

# 1 占位符零残留
resid = []
for pat, name in [(r"⟨MISSING", "MISSING"), (r"⟨DESC\?", "DESC?"), (r"<MERGE>", "MERGE"),
                  (r"\|\|\|", "|||"), (r"oleObject", "oleObject"), (r"\[\[", "[["),
                  (r"□", "□"), (r"\t", "Tab"), (r"⟨FIG", "FIG"), (r"⟨", "⟨"),
                  (r"＝", "＝"), (r"═", "═"), (r"•", "•"), (r"＋", "＋"), (r"⟪", "⟪")]:
    for m in re.finditer(pat, md):
        resid.append((name, md[:m.start()].count("\n") + 1))
report["1_占位符"] = resid

# 2 题号==【答案】
# 【氯批次 序0 修订·通用，已同步钠批次】源文答案标签可能是【参考答案】而非【答案】；
#  若只认【答案】，此类件第 2 项必然 FAILS（计数 0）。改按"答案类标签"计数。
# 【本件新增·通用】答案标签可**内联于题号行**（本件文末答案区形如 `1．【答案】D`）：
#  旧口径 ① 题号 `^\d+．` 会把答案行也计入（题干19+答案19=38）；② 答案行以数字起首、
#  非 `startswith(【答案】)` → 【答案】数记 0 → 第2项必然 FAILS。
#  收紧为：题号行排除含答案标签者；答案数按"行内含答案标签"统计（对"标签行首"件零影响，
#  对钠批次序7「1.C 解析…」无标签件亦零影响 → 向后兼容）。
ANS_LABELS = ("【答案】", "【参考答案】")
# 【硫序6 新增·通用（U67）】题号可带「（多选）」/「（单选）」前缀，口径与 make_md.QNUM_RE 一致，
#  否则题号数少计 → 第 2 项与 ANS_DIFF 不符。U35 回归：27 个已交付 skeleton 中仅本件命中，其余零影响。
qnums = [(i + 1, ln) for i, ln in enumerate(lines)
         if re.match(r"^(?:（多选）|（单选）)?\d+[．、]", ln) and not any(lb in ln for lb in ANS_LABELS)]
# 【氯批次 序4 修订·通用，已同步钠批次】题号分隔符容错顿号（`1、`，序4 全篇用顿号）；
#  U35 回归：已交付氯序0–3 / 钠序0–9 的全部 skeleton 中 `^\d+、` 命中 0 行 → 对已交付件零影响。
ans = [(i + 1, ln) for i, ln in enumerate(lines)
       if any(lb in ln for lb in ANS_LABELS)]
report["2_题号_答案"] = {"题号数": len(qnums), "【答案】数": len(ans),
                        "差值": len(ans) - len(qnums), "白名单": ANS_NOTE,
                        "PASS": len(ans) - len(qnums) == ANS_DIFF}

# 3 表格
tables = []
cur = []
for ln in lines:
    if ln.startswith("|"):
        cur.append(ln)
    else:
        if cur:
            tables.append(cur); cur = []
if cur:
    tables.append(cur)
tbl_ok = True
tbl_info = []
for t in tables:
    ncols = set(ln.count("|") for ln in t)
    if len(ncols) != 1:
        tbl_ok = False
    tbl_info.append((len(t), sorted(ncols)))
src_tbls = skel.count("<TBL>")
report["3_表格"] = {"md表数": len(tables), "源表数": src_tbls, "列一致": tbl_ok,
                    "明细": tbl_info, "PASS": len(tables) == src_tbls and tbl_ok}

# 4 图片三一致
refs = re.findall(r"!\[\]\(images/([^)]+)\)", md)
figdesc = re.findall(r"!\[\]\(images/[^)]+\)〔图：([^〕]+)〕", md)
# images\ 缺失时不可直接 listdir（旧版会抛 FileNotFoundError 裸栈中断，
# 使"图全丢"这种最该报 FAILS 的情形反而拿不到报告）⇒ 退化为空列表，自然判 FAILS。
_IMGDIR = DST / "images"
files = sorted(os.listdir(_IMGDIR)) if _IMGDIR.is_dir() else []
report["4_图片"] = {"引用处数": len(refs), "唯一引用": len(set(refs)), "文件数": len(files),
                    "带描述数": len(figdesc), "images目录": "ok" if _IMGDIR.is_dir() else "MISSING",
                    "文件==唯一引用": sorted(set(refs)) == files,
                    "PASS": _IMGDIR.is_dir() and sorted(set(refs)) == files
                            and len(figdesc) == len(refs)}

# 5 内容保持
def norm_md(t):
    t = re.sub(r"!\[\]\(images/[^)]+\)〔图：[^〕]+〕", "", t)
    t = re.sub(r"^> ?", "", t, flags=re.M)
    t = t.replace("|", "").replace("**", "").replace("---", "")
    return t

def norm_skel(s):
    s = re.sub(r"⟨FIG:[^⟩]+⟩", "", s)
    for k in ("<TBL>", "</TBL>", "|||", "<MERGE>"):
        s = s.replace(k, "")
    return s

def cset(t):
    return Counter(re.sub(r"\s+", "", t))

cm, cs = cset(norm_md(md)), cset(norm_skel(skel))
only_md = cm - cs
only_sk = cs - cm
report["5_内容保持"] = {"仅md": dict(only_md), "仅skeleton": dict(only_sk),
                        "PASS": not only_md and not only_sk}

# 6 引用块结构
#   注意：仅"【答案】/【解析】/【分析】/【详解】/【点睛】"为标签；
#   【进行实验N】/【发现问题】等类标题不算标签（规范 §四.5 的 in_ans 语义）。
LABELS = ("【答案】", "【参考答案】", "【解析】", "【分析】", "【详解】", "【点睛】")
qbad = []
for i, ln in enumerate(lines):
    if ln.startswith("> ") and i + 1 < len(lines) and lines[i + 1].startswith("> "):
        qbad.append(("缺分隔", i + 1))
    if ln == ">":
        if not (i > 0 and lines[i - 1].startswith(">")) or \
           not (i + 1 < len(lines) and lines[i + 1].startswith(">")):
            qbad.append(("孤立分隔", i + 1))
    if re.match(r"^> (?:[A-Da-d][．.]|①|②|③|④|⑤)", ln):
        j = i - 1
        while j >= 0 and (lines[j].startswith(">") or lines[j] == ""):
            j -= 1
        if j >= 0 and lines[j].startswith(LABELS):
            qbad.append(("标签后误引", i + 1))
report["6_引用块"] = qbad

# 7 行尾离子
tail_bad = [i + 1 for i, ln in enumerate(lines) if re.search(r"[⁺⁻₊₋]\s*$", ln)]
report["7_行尾离子"] = tail_bad

# 8 方程式守恒
SUBD = dict(zip("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
SUPD = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-"))

def parse_species(s):
    s = s.strip()
    charge = 0
    m = re.search(r"([⁺⁻⁽⁾0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+)$", s)
    if m and re.search(r"[⁺⁻]", m.group(1)):
        tok = m.group(1)
        num = ""
        for ch in tok:
            if ch in "⁰¹²³⁴⁵⁶⁷⁸⁹":
                num += SUPD[ch]
            elif ch == "⁺":
                charge += int(num) if num else 1; num = ""
            elif ch == "⁻":
                charge -= int(num) if num else 1; num = ""
        s = s[:m.start()]
    s = re.sub(r"\((s|l|g|aq)\)$", "", s)
    atoms = {}

    def walk(t, mult):
        i = 0
        while i < len(t):
            ch = t[i]
            if ch in "([{":
                depth = 1; j = i + 1
                while j < len(t) and depth:
                    if t[j] in "([{":
                        depth += 1
                    if t[j] in ")]}":
                        depth -= 1
                    j += 1
                k = j; nstr = ""
                while k < len(t) and t[k] in "₀₁₂₃₄₅₆₇₈₉0123456789":
                    nstr += SUBD.get(t[k], t[k]); k += 1
                walk(t[i + 1:j - 1], mult * (int(nstr) if nstr else 1))
                i = k
            elif ch.isupper():
                j = i + 1
                while j < len(t) and t[j].islower():
                    j += 1
                el = t[i:j]
                k = j; nstr = ""
                while k < len(t) and t[k] in "₀₁₂₃₄₅₆₇₈₉0123456789":
                    nstr += SUBD.get(t[k], t[k]); k += 1
                atoms[el] = atoms.get(el, 0) + mult * (int(nstr) if nstr else 1)
                i = k
            else:
                i += 1
    walk(s, 1)
    return atoms, charge

def check_eq(eq):
    eq = re.sub(r"=\([^)]*\)=", "=", eq)
    for sep in ("⇌", "=", "→"):
        if sep in eq:
            parts = eq.split(sep)
            break
    else:
        return None
    if len(parts) != 2:
        return None

    def side(sd):
        tot = {}; q = 0
        for term in re.split(r"[+＋]", sd):
            term = term.strip()
            if not term:
                continue
            if re.match(r"^e[⁺⁻]$", term):
                q += -1 if term == "e⁻" else 1
                continue
            m = re.match(r"^(\d+(?:\.\d+)?|\(\d+\)/\(\d+\))", term)
            coef = 1.0
            if m:
                c = m.group(1)
                if "/" in c:
                    a, b = c.strip("()").split(")/(")
                    coef = float(a) / float(b)
                else:
                    coef = float(c)
                term = term[m.end():]
            if not term or not re.search(r"[A-Z]", term):
                continue
            a, c2 = parse_species(term)
            for k, v in a.items():
                tot[k] = tot.get(k, 0) + v * coef
            q += c2 * coef
        return tot, q

    l = side(parts[0]); r = side(parts[1])
    if not l[0] or not r[0]:
        return None
    probs = []
    for k in set(l[0]) | set(r[0]):
        if abs(l[0].get(k, 0) - r[0].get(k, 0)) > 1e-9:
            probs.append("%s:%g/%g" % (k, l[0].get(k, 0), r[0].get(k, 0)))
    if abs(l[1] - r[1]) > 1e-9:
        probs.append("电荷:%g/%g" % (l[1], r[1]))
    return probs

eq_bad = []
EQ_RE = re.compile(r"[A-Za-z₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻()\[\]⋅·\d]+"
                   r"(?:[+＋][A-Za-z₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻()\[\]⋅·\d ]+)*"
                   r"(?:=\([^)]*\)=|=|⇌|→)[^，。；、：\s〕]*")
#   本节只作"疑似"提示，**不计入 FAILS**（"→"会把'一步转化关系'误判为方程式，须人工判读）。
for i, ln in enumerate(lines):
    t = re.sub(r"!\[\]\(images/[^)]+\)〔图：[^〕]+〕", "", ln)
    t = re.sub(r"^> ?", "", t)
    t = re.sub(r"^【[^】]*】", "", t)
    t = re.sub(r"^[（(]\d+[)）]", "", t)
    fracs = []
    t = re.sub(r"\(\d+\)/\(\d+\)", lambda m: "\x00%d\x00" % (fracs.append(m.group(0)) or len(fracs) - 1), t)
    for m in EQ_RE.finditer(t):
        eq = m.group(0).strip()
        eq = re.sub(r"\x00(\d+)\x00", lambda mm: fracs[int(mm.group(1))], eq)
        if len(eq) < 5:
            continue
        if eq.startswith(("H=", "K=", "Kₛ")) or "ΔH" in eq:
            continue
        r = check_eq(eq)
        if r:
            eq_bad.append((i + 1, eq, r))
report["8_方程式"] = eq_bad

# 9 空格三态
#  【序7 修订·通用】扫描前先剔除 `![](...)〔图：…〕` 图描述片段（与第 5/8/10 项同口径，U42）：
#  图描述是本轮生成的自由文本（如图内两行标注按换行线性化时汉字间留了空格），
#  命中会造成与源文排版无关的假阳性。
sp = []
for i, ln in enumerate(lines):
    t9 = re.sub(r"!\[\]\(images/[^)]+\)〔图：[^〕]+〕", "", ln)
    for m in re.finditer(r"[\u4e00-\u9fff] [\u4e00-\u9fff]", t9):
        sp.append((i + 1, t9[max(0, m.start() - 12):m.end() + 12]))
report["9_词间空格"] = sp

# 10 公式符号旁残余单空格（须为 0）
#  口径（钠批次 序4 修订，通用）：只匹配**恰好一个**空格（残余"单"空格）。
#  连在一起的 ≥2 个空格属"填空多空格/答案字段分隔"（规范 §四.6 保留），不属本项；
#  否则【答案】`(4)     =     …` 这类"题号括号 ) + 多空格 + 比较符 ="
#  会被 `(?<=[…()]) +(?=[=+])` 误判（`)` 被当成公式括号）。多空格若真属公式旁，
#  已由 normalize 的 `(?<=[公式类]) *= *(?=[公式类])` 先行清理，本项只作复核。
_F = r"0-9A-Za-z₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹()\[\]"
SPC_RE = re.compile(r"(?<=[" + _F + r"]) (?=[=+])"
                    r"|(?<=[=+]) (?=[" + _F + r"])"
                    r"|(?<=[A-Za-z₀-₉)]) (?=[↑↓])"
                    r"|(?<=[A-Za-z₀-₉)]) (?=\()"
                    # 【序7 收窄】"系数后残余空格"加负向断言 (?![.．])：源文同行选项 Tab→单空格后
                    #  出现 `A.1∶1 B.2∶1`（比值以数字收尾 + 下一选项字母 B），"1 B" 被误判为
                    #  "系数+元素"；"选项字母后紧跟点号不匹配"消除该假阳性
                    #  （与 U32/U36 同源：收窄规则，不改正文）。
                    r"|(?<=\d) (?=[A-Z](?![.．]))")
sp2 = []
for i, ln in enumerate(lines):
    # 先剔除〔图：…〕描述（与第 5/8 项同口径），否则描述内 "（Q2 A 项）" 的 "2 A"
    # 会命中"系数后残余空格"规则，造出与正文无关的假阳性 FAILS。
    t = re.sub(r"!\[\]\(images/[^)]+\)〔图：[^〕]+〕", "", ln)
    for m in SPC_RE.finditer(t):
        sp2.append((i + 1, t[max(0, m.start() - 14):m.end() + 14]))
report["10_符号旁空格"] = sp2

fails = []
if resid:
    fails.append("占位符")
if not report["2_题号_答案"]["PASS"]:
    fails.append("题号答案")
if not report["3_表格"]["PASS"]:
    fails.append("表格")
if not report["4_图片"]["PASS"]:
    fails.append("图片")
if not report["5_内容保持"]["PASS"]:
    fails.append("内容保持")
if qbad:
    fails.append("引用块")
if sp2:
    fails.append("符号旁空格")

(BASE / "audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str),
                                        encoding="utf-8")

out = []
out.append("FAILS: %s" % ("、".join(fails) if fails else "无(全部通过)"))
out.append("1 占位符残留: %d %s" % (len(resid), resid[:10]))
out.append("2 题号/答案: %s" % report["2_题号_答案"])
out.append("3 表格: %s" % report["3_表格"])
out.append("4 图片: %s" % report["4_图片"])
out.append("5 内容保持 仅md=%s 仅skeleton=%s" % (dict(only_md), dict(only_sk)))
out.append("6 引用块问题: %s" % qbad)
out.append("7 行尾离子(复核): %s" % tail_bad)
out.append("8 方程式疑似不守恒: %d" % len(eq_bad))
for e in eq_bad:
    out.append("    %s" % (e,))
out.append("9 词间空格: %s" % sp)
out.append("10 符号旁残余单空格: %s" % sp2)
(BASE / "audit_report.txt").write_text("\n".join(out), encoding="utf-8")
print("written audit_report.txt (GBK terminal: see file for details)")
